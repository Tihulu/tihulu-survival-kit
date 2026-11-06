# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only owner-authenticated Text Center WSGI status/discovery routes.

No listener, RF backend, RSS downloader or multi-user BBS is created. A real
authenticated TLS Tihulu portal MUST mount this adapter and inject its trusted
owner session into the callback and the WSGI environment. The standalone Text
Center /api/rds/start and other POST routes are never forwarded.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit, parse_qs
from .text_center_archive import TextCenterArchive, TextArchiveUnavailable
from .text_center_integration import TextCenterIntegration, TEXT_PAGES

MAX_RESPONSE_BYTES = 131_072


class TextCenterWSGI:
    """Mount under /text-center/api after real Kit gateway authentication."""

    def __init__(self, bridge: TextCenterIntegration, *, authorize,
                 allowed_hosts: frozenset[str], receiver_ids=(),
                 archive: TextCenterArchive | None = None):
        if not callable(authorize) or not allowed_hosts:
            raise ValueError("Real session callback and exact hostname allowlist required")
        if any(not isinstance(host, str) or not host or "/" in host or ":" in host
               for host in allowed_hosts):
            raise ValueError("Allowed hosts must not include ports or schemes")
        self.bridge, self.authorize = bridge, authorize
        self.allowed_hosts = frozenset(host.lower() for host in allowed_hosts)
        self.receiver_ids = tuple(receiver_ids)
        if archive is not None and not isinstance(archive, TextCenterArchive):
            raise TypeError("Configured TextCenterArchive required")
        self.archive = archive

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
                              "archive_configured": self.archive is not None,
                              "note": "Wave 1 bridge; original UI and decoders pending integration"})
        if path == "/text-center/api/pages":
            return send(200, {"pages": TEXT_PAGES})
        if path.startswith("/text-center/api/archive/"):
            if self.archive is None:
                return send(503, {"error": "Owner archive not configured"})
            # Reject wrong-owner access before interpreting IDs/query details.
            if owner_id != self.archive.owner_id:
                return send(403, {"error": "Archive owner permission denied"})
            name = path.removeprefix("/text-center/api/archive/")
            if name not in ("status", "pages", "page", "articles", "article", "events"):
                return send(404, {"error": "Unknown archive route"})
            raw_query = environ.get("QUERY_STRING", "")
            if not isinstance(raw_query, str) or len(raw_query) > 512:
                return send(400, {"error": "Invalid archive query"})
            try:
                q = parse_qs(raw_query, keep_blank_values=True, max_num_fields=4)
                accepted = {
                    "status": frozenset(),
                    "pages": frozenset(),
                    "page": frozenset({"source_id", "number", "subpage"}),
                    "articles": frozenset(),
                    "article": frozenset({"id"}),
                    "events": frozenset(),
                }
                if not set(q).issubset(accepted[name]):
                    raise ValueError("Unknown archive query parameter")
                def one(key, default=None):
                    values = q.get(key)
                    if values is None:
                        if default is not None:
                            return default
                        raise ValueError("Required archive query parameter missing")
                    if len(values) != 1:
                        raise ValueError("Duplicate archive query parameter")
                    return values[0]
                if name == "status":
                    result = self.archive.counts(owner_id=owner_id)
                elif name == "pages":
                    result = {"items": self.archive.pages(owner_id=owner_id),
                              "source": "independent_textcenter_sqlite",
                              "live": False}
                elif name == "page":
                    result = self.archive.page(
                        owner_id=owner_id, source_id=one("source_id"),
                        page=int(one("number")), subpage=int(one("subpage", "0")))
                elif name == "articles":
                    result = {"items": self.archive.articles(owner_id=owner_id),
                              "source": "independent_textcenter_sqlite",
                              "live": False}
                elif name == "article":
                    result = self.archive.article(
                        owner_id=owner_id, article_id=one("id"))
                else:
                    result = {"items": self.archive.events(owner_id=owner_id),
                              "source": "independent_textcenter_sqlite",
                              "live": False, "verified_official_alert": False}
            except (ValueError, TypeError):
                return send(400, {"error": "Invalid archive query"})
            except PermissionError:
                return send(403, {"error": "Archive owner permission denied"})
            except (TextArchiveUnavailable, OSError):
                return send(503, {"error": "Read-only independent archive unavailable"})
            if result is None:
                return send(404, {"error": "No such archived item"})
            return send(200, result)
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
