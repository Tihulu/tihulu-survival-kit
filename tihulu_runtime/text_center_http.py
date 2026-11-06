# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only owner-authenticated Text Center WSGI status/discovery routes.

No listener, RF backend, RSS downloader or multi-user BBS is created. A real
authenticated TLS Tihulu portal MUST mount this adapter and inject its trusted
owner session into the callback and the WSGI environment. The standalone Text
Center /api/rds/start and other POST routes are never forwarded.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit
from .text_center_integration import TextCenterIntegration, TEXT_PAGES

MAX_RESPONSE_BYTES = 131_072


class TextCenterWSGI:
    """Mount under /text-center/api after real Kit gateway authentication."""

    def __init__(self, bridge: TextCenterIntegration, *, authorize,
                 allowed_hosts: frozenset[str], receiver_ids=()):
        if not callable(authorize) or not allowed_hosts:
            raise ValueError("Real session callback and exact hostname allowlist required")
        if any(not isinstance(host, str) or not host or "/" in host or ":" in host
               for host in allowed_hosts):
            raise ValueError("Allowed hosts must not include ports or schemes")
        self.bridge, self.authorize = bridge, authorize
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self.receiver_ids = tuple(receiver_ids)

    def __call__(self, environ: dict, start_response):
        def send(code: int, result: dict):
            raw = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(raw) > MAX_RESPONSE_BYTES:
                code, raw = 413, b'{"error":"Response exceeds limit"}'
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(raw))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("X-Frame-Options", "DENY"),
                ("Referrer-Policy", "no-referrer"),
            ]
            description = {200: "OK", 400: "Bad Request", 401: "Unauthorized",
                           403: "Forbidden", 404: "Not Found",
                           405: "Method Not Allowed", 413: "Content Too Large",
                           503: "Service Unavailable"}[code]
            start_response(f"{code} {description}", headers)
            return [raw]

        # Not a client HTTP header: only privileged gateway middleware can set
        # this WSGI environment flag after its real TLS and login checks.
        if environ.get("tihulu.trusted_gateway") is not True:
            return send(403, {"error": "Authenticated TLS portal required"})
        host = environ.get("HTTP_HOST", "").split(":")[0].lower()
        if host not in self.allowed_hosts:
            return send(403, {"error": "Unrecognized portal hostname"})
        if environ.get("REQUEST_METHOD", "").upper() != "GET":
            return send(405, {"error": "Only passive GET supported; no RF or BBS writes"})
        try:
            identity = self.authorize(environ)
        except (ValueError, PermissionError):
            identity = None
        if not isinstance(identity, tuple) or len(identity) != 2:
            return send(401, {"error": "Sign in required"})
        owner_id, is_owner = identity
        if not isinstance(owner_id, str) or not owner_id.strip():
            return send(401, {"error": "Sign in required"})
        if is_owner is not True:
            return send(403, {"error": "Owner-only until per-user text ACL exists"})
        raw_path = environ.get("PATH_INFO", "")
        if not isinstance(raw_path, str) or len(raw_path) > 256:
            return send(400, {"error": "Invalid path"})
        path = urlsplit(raw_path).path
        if path == "/text-center/api/status":
            return send(200, {"state": "passive_bridge_only", "owner_scoped": True,
                              "background": False, "hardware_tuning": False,
                              "standalone_ui_mounted": False,
                              "note": "Wave 1 bridge; original UI and decoders pending integration"})
        if path == "/text-center/api/pages":
            return send(200, {"pages": TEXT_PAGES})
        if path not in ("/text-center/api/discovery", "/text-center/api/capabilities"):
            return send(404, {"error": "Unknown Text Center route"})
        try:
            data = self.bridge.passive_discover(
                owner_id=owner_id, receiver_ids=self.receiver_ids)
        except (ValueError, PermissionError, OSError, RuntimeError):
            return send(503, {"error": "Passive capability discovery unavailable"})
        if path.endswith("/capabilities"):
            return send(200, {"status": data["status"],
                              "capabilities": data["capabilities"],
                              "source": data["source"], "hardware_tuning": False})
        return send(200, data)
