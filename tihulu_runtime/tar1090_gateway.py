# SPDX-License-Identifier: AGPL-3.0-only
"""Same-origin authenticated *file gateway* for a real installed tar1090.

This module neither vendors nor reimplements tar1090. It serves an existing,
trusted installation with its original HTML/JS/CSS, data, chunks and history
paths from a parent WSGI app that MUST authenticate every request.

Upstream tar1090: https://github.com/wiedehopf/tar1090 (GPL-2.0-or-later).
Respect its source/license/attribution and package dependencies. This gateway
does NOT create decoder JSON, download map tiles or start a readsb process.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import mimetypes
import re

PREFIX = "/flight-radar/tar1090/"
GERMANY_CONFIG = (
    b"// Tihulu geographical viewport fallback (not a receiver coordinate).\n"
    b"// Installed operator config.js may override these values below.\n"
    b"DefaultCenterLat = 51.1657;\n"
    b"DefaultCenterLon = 10.4515;\n"
)
STATIC_MAX = 16 * 1024 * 1024
DATA_MAX = 32 * 1024 * 1024
CACHELESS = ("data", "config.js", "chunks")
# Exact upstream web roots: nginx.conf and 88-tar1090.conf, reviewed at
# https://github.com/wiedehopf/tar1090
DATA_ROOTS = frozenset({
    "data", "chunks", "globe_history", "aircraft_sil",
    "osm_tiles_offline", "openfreemap_offline",
})
ENCODED_GZIP = re.compile(r"^(?:chunk_|current_).+\.gz$|\.binCraft$|^globe.*\.json$")


class Tar1090Unavailable(RuntimeError):
    """Missing installed upstream assets, disabled data or invalid file request."""


@dataclass(frozen=True)
class Tar1090Paths:
    """Only trusted installer/admin configuration can provide these roots.

    No path is taken from HTTP query strings, user input or browser headers.
    """
    html: Path
    data: Path | None = None
    chunks: Path | None = None
    globe_history: Path | None = None
    aircraft_sil: Path | None = None
    osm_tiles_offline: Path | None = None
    openfreemap_offline: Path | None = None


@dataclass(frozen=True)
class TarAsset:
    body: bytes
    content_type: str
    headers: tuple[tuple[str, str], ...] = ()


class Tar1090Gateway:
    """Read-only, filename-safe tar1090 mount; authentication is external."""

    def __init__(self, paths: Tar1090Paths):
        self.paths = paths

    def installed(self) -> bool:
        """Assets installed does not mean a working decoder or RF messages."""
        root = self.paths.html
        return (root.is_dir() and not root.is_symlink()
                and (root / "index.html").is_file()
                and (root / "defaults.js").is_file()
                and (root / "script.js").is_file())

    @staticmethod
    def _safe(root: Path, relative: str, *, max_bytes: int) -> bytes:
        if (not relative or "\x00" in relative or "\\" in relative
                or "%" in relative or "?" in relative or "#" in relative
                or relative.startswith("/") or "//" in relative):
            raise Tar1090Unavailable("Invalid tar1090 asset path.")
        parts = PurePosixPath(relative).parts
        if not parts or any(p in ("", ".", "..") for p in parts):
            raise Tar1090Unavailable("Invalid tar1090 asset path.")
        try:
            base = root.resolve(strict=True)
            target = root.joinpath(*parts)
            if (root.is_symlink()
                    or any(root.joinpath(*parts[:i]).is_symlink()
                           for i in range(1, len(parts) + 1))
                    or not target.resolve(strict=True).is_relative_to(base)
                    or not target.is_file()):
                raise Tar1090Unavailable("tar1090 asset is unavailable.")
            size = target.stat().st_size
            if not 0 <= size <= max_bytes:
                raise Tar1090Unavailable("tar1090 asset exceeds size limit.")
            with target.open("rb") as handle:
                data = handle.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise Tar1090Unavailable("tar1090 asset exceeds size limit.")
            return data
        except (OSError, RuntimeError) as exc:
            if isinstance(exc, Tar1090Unavailable):
                raise
            raise Tar1090Unavailable("tar1090 asset is unavailable.") from exc

    def initial_aircraft_focus(self) -> str | None:
        """Select a FRESH actual local ADS-B ICAO, never a fabricated marker.

        Only uses trusted readsb snapshots. Browser GPS may take precedence in
        tar1090 itself if permitted; it is not readable by this server.
        When receiver.json lacks real coordinates, Germany is a *selection
        heuristic only*, never a claimed receiver position.
        """
        if self.paths.data is None:
            return None
        from .flight_radar_sources import read_local_readsb, SourceUnavailable
        from .flight_radar_model import real
        import json
        import math
        import time

        try:
            aircraft = read_local_readsb(self.paths.data / "aircraft.json")
        except (SourceUnavailable, OSError):
            return None
        now = time.time()
        positioned = [a for a in aircraft if a.icao and a.located(now)]
        if not positioned:
            return None
        reference = (51.1657, 10.4515)
        try:
            raw = self._safe(self.paths.data, "receiver.json",
                             max_bytes=128 * 1024)
            receiver = json.loads(raw)
            lat = real(receiver.get("lat"), -90, 90)
            lon = real(receiver.get("lon"), -180, 180)
            if lat is not None and lon is not None:
                reference = (lat, lon)
        except (Tar1090Unavailable, ValueError, AttributeError, TypeError):
            pass

        def distance(a):
            lat1, lon1 = (math.radians(x) for x in reference)
            lat2, lon2 = math.radians(a.latitude), math.radians(a.longitude)
            h = (math.sin((lat2 - lat1) / 2) ** 2
                 + math.cos(lat1) * math.cos(lat2)
                 * math.sin((lon2 - lon1) / 2) ** 2)
            return 2 * math.asin(min(1.0, math.sqrt(max(0.0, h))))

        return min(positioned, key=distance).icao

    def asset(self, path: str) -> TarAsset:
        """Return an installed tar1090 resource with upstream relative URLs.

        The parent WSGI app must check its existing login and host allowlist
        *before* calling this function. This method never issues HTTP.
        """
        if not path.startswith(PREFIX):
            raise Tar1090Unavailable("Unknown tar1090 route.")
        if not self.installed():
            raise Tar1090Unavailable("Full tar1090 map is not installed.")
        relative = path[len(PREFIX):] or "index.html"
        first, sep, remainder = relative.partition("/")
        root = self.paths.html
        if first in DATA_ROOTS and sep:
            root = getattr(self.paths, first)
            if root is None:
                raise Tar1090Unavailable("tar1090 data dependency is not configured.")
            relative = remainder
        elif first in DATA_ROOTS:
            raise Tar1090Unavailable("A tar1090 asset file is required.")
        in_data = root != self.paths.html
        body = self._safe(root, relative,
                          max_bytes=DATA_MAX if in_data else STATIC_MAX)
        if root == self.paths.html and relative == "config.js":
            # Original upstream config executes AFTER this fallback; actual
            # site location from receiver.json and explicit user config win.
            body = GERMANY_CONFIG + body
        extension = PurePosixPath(relative).suffix.lower()
        content_type = {
            ".js": "text/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".svg": "image/svg+xml",
            ".wasm": "application/wasm",
            ".gz": "application/json",
            ".zst": "application/octet-stream",
        }.get(extension) or mimetypes.guess_type(relative)[0] or "application/octet-stream"
        headers = [("Cache-Control", "no-store"),
                   ("X-Content-Type-Options", "nosniff"),
                   ("Referrer-Policy", "same-origin")]
        # The upstream tar1090 webserver maps compressed readsb/history
        # blobs with explicit encoding. Without these headers the browser's
        # JSON/history/chunks/trace loaders fail even when assets are present.
        if relative.endswith(".gz"):
            headers.append(("Content-Encoding", "gzip"))
        elif (in_data and extension == ".binCraft"
              or in_data and extension == ".json"
              and PurePosixPath(relative).name.startswith("globe")):
            headers.append(("Content-Encoding", "gzip"))
        return TarAsset(body, content_type, tuple(headers))
