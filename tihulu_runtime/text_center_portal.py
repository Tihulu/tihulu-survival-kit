# SPDX-License-Identifier: AGPL-3.0-only
"""Authenticated, read-only preview of the INSTALLED Text Center source UI.

The source HTML/CSS/favicon is loaded from an owner-installed, separately
versioned Text Center package. NO vendored copy of that repository is shipped
here. Its standalone JavaScript is NOT executed: it targets unprotected /api/
write/scan endpoints. A small Kit-controlled GET-only client takes its place.

This is an incremental *read-only* visual integration, not full Modern/Classic
feature parity. All HTML/static assets are protected by the real Kit gateway.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from .text_center_http import TextCenterWSGI

MAX_SOURCE_ASSET_BYTES = 256 * 1024

_ASSETS = {
    "/text-center/": ("index.html", "text/html; charset=utf-8"),
    "/text-center/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/text-center/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
_SHIP_ASSETS = {
    "/text-center/assets/kit-app.js": ("text_center_kit_preview.js", "text/javascript; charset=utf-8"),
    "/text-center/assets/kit-mode.css": ("text_center_kit_mode.css", "text/css; charset=utf-8"),
}


class TextCenterPortalWSGI:
    """Only serve exact read-only UI files, never standalone process writes."""

    def __init__(self, *, api: TextCenterWSGI,
                 source_web_dir: str | Path,
                 kit_assets_dir: str | Path | None = None):
        if not isinstance(api, TextCenterWSGI):
            raise TypeError("Trusted read-only TextCenterWSGI required")
        self.api = api
        self.source_web_dir = Path(source_web_dir)
        self.kit_assets_dir = (Path(kit_assets_dir) if kit_assets_dir is not None
                               else Path(__file__).resolve().parents[1] / "prototype")

    @staticmethod
    def _reply(start_response, status: int, data: bytes,
               mime: str = "text/plain; charset=utf-8"):
        messages = {200: "OK", 401: "Unauthorized", 403: "Forbidden",
                    404: "Not Found", 405: "Method Not Allowed",
                    413: "Content Too Large", 503: "Service Unavailable"}
        start_response(f"{status} {messages[status]}", [
            ("Content-Type", mime), ("Content-Length", str(len(data))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "no-referrer"),
            ("Content-Security-Policy",
             "default-src 'none'; script-src 'self'; style-src 'self'; "
             "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
             "form-action 'self'; frame-ancestors 'none'"),
        ])
        return [data]

    @staticmethod
    def _load_asset(root: Path, filename: str) -> bytes:
        # The filename must come from a fixed allowlist, never a URL fragment.
        root = root.resolve(strict=True)
        path = (root / filename).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Static asset path is outside installed source")
        if path.stat().st_size > MAX_SOURCE_ASSET_BYTES:
            raise ValueError("Static source asset exceeds limit")
        return path.read_bytes()

    @staticmethod
    def _rewrite_html(data: bytes) -> bytes:
        original = data.decode("utf-8")
        # Strict adapter: source markup must contain these anchors. If upstream
        # changes, refuse partial/insecure preview until reviewed.
        replacements = {
            'href="/favicon.svg"': 'href="/text-center/favicon.svg"',
            'href="/assets/styles.css"': 'href="/text-center/assets/styles.css"',
            'src="/assets/app.js"': 'src="/text-center/assets/kit-app.js"',
        }
        for key, value in replacements.items():
            if original.count(key) != 1:
                raise ValueError("Unexpected Text Center source HTML version")
            original = original.replace(key, value, 1)
        if '<div class="message" id="notification"' not in original:
            raise ValueError("Missing Text Center status anchor")
        if original.count("</head>") != 1:
            raise ValueError("Missing source document head")
        original = original.replace(
            "</head>",
            '<link rel="stylesheet" href="/text-center/assets/kit-mode.css">'
            "</head>", 1)
        original = original.replace(
            '<div class="message" id="notification"',
            '<button type="button" id="kit-visual-mode" class="action ghost" '
            'aria-pressed="false" title="Toggle Modern/Classic Teletext">'
            'CLASSIC TELETEXT</button>'
            '<div class="message" id="notification"', 1)
        original = original.replace(
            "Local archive ready", "Local archive status not checked")
        original = original.replace(
            "STANDALONE MODE • 127.0.0.1 • NO BACKGROUND POLLING",
            "SURVIVAL KIT / READ-ONLY INTEGRATION PREVIEW • NO RF TUNING")
        original = original.replace(
            "A home for broadcast text, independent feeds, archival pages and local messages.",
            "An authenticated view of the independent Text Center. "
            "Import, scan, receiver and messaging actions are unavailable until "
            "the shared Kit services have passed security tests.")
        return original.encode("utf-8")

    def __call__(self, environ: dict, start_response):
        # The API performs the same auth for its own JSON endpoints; UI assets
        # MUST also be gated. Never copy owner/session IDs from HTTP headers.
        if environ.get("tihulu.trusted_gateway") is not True:
            return self._reply(start_response, 403, b"Trusted TLS portal required")
        host = environ.get("HTTP_HOST", "").split(":")[0].lower()
        if host not in self.api.allowed_hosts:
            return self._reply(start_response, 403, b"Unrecognized portal hostname")
        try:
            identity = self.api.authorize(environ)
        except (ValueError, PermissionError):
            identity = None
        if not isinstance(identity, tuple) or len(identity) != 2:
            return self._reply(start_response, 401, b"Sign in required")
        owner, is_owner = identity
        if not isinstance(owner, str) or not owner.strip():
            return self._reply(start_response, 401, b"Sign in required")
        if is_owner is not True:
            return self._reply(start_response, 403, b"Owner only until ACL integration")
        if environ.get("REQUEST_METHOD", "").upper() != "GET":
            return self._reply(start_response, 405, b"Read-only preview")
        raw_path = environ.get("PATH_INFO", "")
        if not isinstance(raw_path, str) or len(raw_path) > 256:
            return self._reply(start_response, 404, b"Unknown Text Center route")
        path = urlsplit(raw_path).path
        if path.startswith("/text-center/api/"):
            return self.api(environ, start_response)
        if path == "/text-center":
            path = "/text-center/"
        if path in _ASSETS:
            filename, mime = _ASSETS[path]
            root = self.source_web_dir
        elif path in _SHIP_ASSETS:
            filename, mime = _SHIP_ASSETS[path]
            root = self.kit_assets_dir
        else:
            return self._reply(start_response, 404, b"Unknown Text Center asset")
        try:
            data = self._load_asset(root, filename)
            if path == "/text-center/":
                data = self._rewrite_html(data)
        except (OSError, UnicodeError, ValueError):
            return self._reply(start_response, 503,
                               b"Text Center source assets unavailable or changed")
        return self._reply(start_response, 200, data, mime)
