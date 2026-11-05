"""Explicit trusted remote inference for Ollama and OpenAI-compatible servers.

Nothing is contacted on import. Owner-approved configuration, TLS trust and
backend authorization belong to the eventual authenticated Tihulu controller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
import ipaddress
import json
import socket


class RemoteAIError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class RemoteEndpoint:
    base_url: str
    flavor: str  # ollama, hailo_ollama, llamacpp, vllm
    bearer_token: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.flavor not in ("ollama", "hailo_ollama", "llamacpp", "vllm"):
            raise ValueError("Unsupported remote backend API")
        url = urlsplit(self.base_url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError("Remote URL must be an explicit http(s) origin without embedded credentials")
        if url.path not in ("", "/") or url.query or url.fragment:
            raise ValueError("Remote endpoint must be an origin, not an arbitrary URL path")
        if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("Remote LAN inference requires verified HTTPS; HTTP only on loopback")
        try:
            port = url.port
        except ValueError as exc:
            raise ValueError("Invalid port") from exc
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("Invalid port")


def _private_host(host: str) -> None:
    """Refuse public remote addresses; HTTPS/ACL still required against DNS rebinding."""
    addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    if not addresses:
        raise RemoteAIError("Remote host has no resolved private address")
    for item in addresses:
        address = ipaddress.ip_address(item[4][0].split("%")[0])
        if not (address.is_private or address.is_loopback or address in cgnat):
            raise RemoteAIError("Remote host resolves outside private LAN/tailnet")


class RemoteAIClient:
    """Non-streaming API client. Uses OS-trusted HTTPS and rejects redirects."""

    def __init__(self, endpoint: RemoteEndpoint, *, timeout: float = 15):
        if not 0 < timeout <= 120:
            raise ValueError("Invalid request timeout")
        self.endpoint = endpoint
        self.timeout = timeout
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _request(self, path: str, payload: dict | None = None) -> dict:
        _private_host(urlsplit(self.endpoint.base_url).hostname or "")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.endpoint.bearer_token:
            headers["Authorization"] = "Bearer " + self.endpoint.bearer_token
        req = Request(self.endpoint.base_url.rstrip("/") + path, data=body,
                      headers=headers, method="POST" if body is not None else "GET")
        try:
            with self._opener.open(req, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise RemoteAIError("Response exceeded 2 MiB limit")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise RemoteAIError("Remote JSON object required")
                return data
        except (OSError, ValueError) as exc:
            raise RemoteAIError("Remote model API unavailable or returned invalid JSON") from exc

    def list_installable_hailo_models(self) -> tuple[str, ...]:
        """Only models in /hailo/v1/list are Hailo-Ollama pull candidates."""
        if self.endpoint.flavor != "hailo_ollama":
            raise RemoteAIError("Only Hailo-Ollama provides this catalogue")
        names = self._request("/hailo/v1/list").get("models", ())
        if not isinstance(names, list):
            raise RemoteAIError("Hailo catalogue response invalid")
        return tuple(name for name in names if isinstance(name, str))

    def list_models(self) -> tuple[str, ...]:
        if self.endpoint.flavor in ("ollama", "hailo_ollama"):
            response = self._request("/api/tags")
            return tuple(model["name"] for model in response.get("models", ())
                         if isinstance(model, dict) and isinstance(model.get("name"), str))
        response = self._request("/v1/models")
        return tuple(model["id"] for model in response.get("data", ())
                     if isinstance(model, dict) and isinstance(model.get("id"), str))

    def generate(self, *, model: str, prompt: str) -> str:
        if not model or not prompt:
            raise ValueError("Explicit model and prompt required")
        if self.endpoint.flavor in ("ollama", "hailo_ollama"):
            payload = self._request("/api/generate", {
                "model": model, "prompt": prompt, "stream": False})
            result = payload.get("response")
        else:
            payload = self._request("/v1/chat/completions", {
                "model": model, "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            })
            choices = payload.get("choices") or []
            result = (choices[0].get("message") or {}).get("content") if choices else None
        if not isinstance(result, str):
            raise RemoteAIError("Remote API returned no text answer")
        return result
