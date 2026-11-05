# SPDX-License-Identifier: AGPL-3.0-only
"""Mountable same-origin WSGI route adapter for native Survival Kit Flight Radar.

No autonomous network listener. A *trusted existing* Survival Kit gateway
must supply authentication, CSRF validation and exact permitted hosts.
Never use a browser header as owner identity or accept a user-supplied path,
systemd unit or shell command. Real USB/readsb lifecycle is not implemented.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs
import json

from .flight_radar_center import FlightRadarCenter
from .flight_radar_sources import MODES

MAX_REQUEST = 4096
ASSETS = {
    "/flight-radar": ("flight_radar.html", "text/html; charset=utf-8"),
    "/flight-radar/": ("flight_radar.html", "text/html; charset=utf-8"),
    "/flight-radar/app.js": ("flight_radar.js", "text/javascript; charset=utf-8"),
}
STATUS = {200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request",
          401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
          405: "Method Not Allowed", 409: "Conflict", 413: "Content Too Large",
          422: "Unprocessable Content", 500: "Server Error",
          501: "Not Implemented", 503: "Unavailable"}


class FlightRadarWSGI:
    """Mount into authenticated Survival Kit HTTP reverse proxy; no new port."""

    def __init__(self, center: FlightRadarCenter, *,
                 authorize, validate_csrf, allowed_hosts: frozenset[str],
                 issue_csrf=None, assets_dir: Path | None = None):
        if not callable(authorize) or not callable(validate_csrf) or not allowed_hosts:
            raise ValueError("Authenticated gateway and explicit host allowlist required.")
        self.center = center
        self.authorize = authorize
        self.validate_csrf = validate_csrf
        self.issue_csrf = issue_csrf
        self.allowed_hosts = allowed_hosts
        self.assets_dir = assets_dir or Path(__file__).resolve().parents[1] / "prototype"

    def __call__(self, environ: dict, start_response):
        try:
            path = environ.get("PATH_INFO", "")
            method = environ.get("REQUEST_METHOD", "GET").upper()
            raw_host = environ.get("HTTP_HOST", "").split(":")[0].lower()
            if raw_host not in self.allowed_hosts:
                return self._send(start_response, 403, {"error": "Unrecognized hostname."})
            if method not in ("GET", "POST", "DELETE"):
                return self._send(start_response, 405, {"error": "Method not permitted."})
            # Auth callback must be the existing trusted portal session middleware.
            identity = self.authorize(environ)
            if not isinstance(identity, tuple) or len(identity) != 2:
                return self._send(start_response, 401, {"error": "Sign in required."})
            owner_id, can_control = identity
            if not isinstance(owner_id, str) or not owner_id:
                return self._send(start_response, 401, {"error": "Sign in required."})
            if method != "GET":
                origin = environ.get("HTTP_ORIGIN")
                expected = ("https" if environ.get("wsgi.url_scheme") == "https"
                            else "http") + "://" + environ.get("HTTP_HOST", "")
                if origin != expected or not self.validate_csrf(environ):
                    return self._send(start_response, 403, {"error": "CSRF or origin check failed."})
                if can_control is not True:
                    return self._send(start_response, 403, {"error": "Receiver control not permitted."})
            if method == "GET" and path in ASSETS:
                filename, kind = ASSETS[path]
                return self._send_static(start_response, filename, kind)
            if not path.startswith("/api/flight-radar/"):
                return self._send(start_response, 404, {"error": "Unknown route."})
            endpoint = path.removeprefix("/api/flight-radar/")
            if method == "GET":
                params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)
                sid = params.get("session", [""])[0]
                if endpoint == "bootstrap":
                    if not callable(self.issue_csrf) or can_control is not True:
                        return self._send(start_response, 403, {
                            "error": "Authenticated control and CSRF integration unavailable."})
                    return self._send(start_response, 200, {
                        "csrf_token": self.issue_csrf(environ),
                        "receiver_controls_ready": False})
                if endpoint == "status":
                    return self._send(start_response, 200, self.center.status(owner_id=owner_id))
                if endpoint == "sources":
                    return self._send(start_response, 200, {
                        "modes": ["antenna", "internet", "hybrid", "automatic"],
                        "configured_online_providers": [
                            p.id for p in self.center.sources.providers if p.enabled],
                        "provider_query_policy": "Explicit consent and rate limits required",
                    })
                if endpoint in ("aircraft", "statistics"):
                    data = self.center.snapshot(sid, owner_id=owner_id)
                    if endpoint == "statistics":
                        data = {"utc": data["utc"], "count": data["count"],
                                "positioned": data["positioned"],
                                "source_status": data["source_status"]}
                    return self._send(start_response, 200, data)
                if endpoint == "history":
                    return self._send(start_response, 501, {
                        "error": "History is not installed. No observations are stored."})
                if endpoint == "stream":
                    return self._send(start_response, 501, {
                        "error": "SSE/streaming is not installed. Use bounded polling."})
                return self._send(start_response, 404, {"error": "Unknown Flight Radar API route."})
            if method == "POST" and endpoint == "session":
                length = environ.get("CONTENT_LENGTH", "")
                if not length.isdecimal() or not 0 < int(length) <= MAX_REQUEST:
                    return self._send(start_response, 413, {"error": "Invalid request size."})
                body = environ["wsgi.input"].read(int(length))
                payload = json.loads(body)
                if not isinstance(payload, dict) or set(payload) != {"mode", "online_allowed"}:
                    return self._send(start_response, 422, {"error": "Invalid session request."})
                if payload["mode"] not in MODES or type(payload["online_allowed"]) is not bool:
                    return self._send(start_response, 422, {"error": "Invalid source mode or consent."})
                # Device identifier is server-scoped, not a user-supplied device token.
                device = environ.get("tihulu.device_id")
                if not isinstance(device, str) or not device:
                    return self._send(start_response, 403, {"error": "Authenticated device required."})
                session = self.center.open_session(
                    owner_id=owner_id, device_id=device, mode=payload["mode"],
                    online_allowed=payload["online_allowed"],
                    explicit_owner_permission=True)
                return self._send(start_response, 201, {
                    "session_id": session.id, "mode": session.mode,
                    "online_allowed": session.online_allowed,
                    "receiver_attached": session.tuner_lease is not None,
                })
            if method == "DELETE" and endpoint.startswith("session/"):
                sid = endpoint.removeprefix("session/")
                self.center.stop_session(sid, owner_id=owner_id)
                return self._send(start_response, 200, {"stopped": True})
            if method == "POST" and endpoint in ("receiver/start", "receiver/stop"):
                return self._send(start_response, 501, {
                    "error": "Hardware control requires verified shared SDR/readsb adapter."})
            return self._send(start_response, 404, {"error": "Operation is not available."})
        except (KeyError, ValueError, json.JSONDecodeError):
            return self._send(start_response, 400, {"error": "Invalid request or unknown session."})
        except PermissionError:
            return self._send(start_response, 403, {"error": "Not authorized for this session."})
        except Exception as exc:
            # No raw exception to client; do not leak owner files or stacktraces.
            if exc.__class__.__name__ in ("Blocked", "Busy", "ReceiverBusy"):
                return self._send(start_response, 409, {"error": "Receiver or service is unavailable.",
                                                       "reason": str(exc)[:120]})
            return self._send(start_response, 503, {"error": "Flight Radar service is unavailable."})

    @staticmethod
    def _send(start_response, code: int, result: dict):
        data = json.dumps(result, allow_nan=False).encode("utf-8")
        start_response(f"{code} {STATUS[code]}", [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "same-origin"),
            ("Content-Length", str(len(data)))])
        return [data]

    def _send_static(self, start_response, filename: str, content_type: str):
        try:
            raw = (self.assets_dir / filename).read_bytes()
        except OSError:
            return self._send(start_response, 503, {"error": "Flight Radar assets not installed."})
        start_response("200 OK", [
            ("Content-Type", content_type),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Content-Security-Policy", "default-src 'self'; script-src 'self'; "
             "style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; "
             "object-src 'none'; frame-ancestors 'self'"),
            ("Content-Length", str(len(raw)))])
        return [raw]
