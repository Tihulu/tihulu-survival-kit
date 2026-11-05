# SPDX-License-Identifier: AGPL-3.0-only
"""Opt-in local readsb and legitimate HTTPS aircraft data sources.

No background worker, cloud upload, external host-selected URL or localhost
SSRF endpoint. Real provider terms, consent and attribution must be shown by
the future authenticated Setup and Source Manager UI.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode
import json
import math
import time

from .flight_radar_model import (Aircraft, RadarDataError, FEED_AGE_LIMIT,
                                  MAX_AIRCRAFT, from_readsb, merge_aircraft, real)

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MODES = frozenset({"antenna", "internet", "hybrid", "automatic"})
ADSB_LOL = "https://api.adsb.lol"
OPENSKY = "https://opensky-network.org"


class SourceUnavailable(RuntimeError):
    """Unavailable, rate-limited, missing or unverifiable external source."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise SourceUnavailable("Network redirect refused for source safety.")


def _fetch_json(url: str, headers: dict[str, str]) -> dict:
    """Static HTTPS provider URL only; never accept arbitrary client URLs."""
    if not (url.startswith(ADSB_LOL + "/v2/lat/") or
            url.startswith(OPENSKY + "/api/states/all?")):
        raise SourceUnavailable("Provider URL is not allowlisted.")
    try:
        request = Request(url, headers={
            "Accept": "application/json", "User-Agent": "TihuluSurvivalKitFlightRadar/0.1",
            **headers})
        with build_opener(_NoRedirect()).open(request, timeout=5) as response:
            if response.status != 200:
                raise SourceUnavailable("Provider returned an unexpected status.")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise SourceUnavailable("Provider response exceeds size limit.")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise SourceUnavailable("Invalid provider JSON response.")
        return data
    except (HTTPError, URLError, TimeoutError, OSError, ValueError,
            UnicodeError) as exc:
        # Do not include secrets/URLs or provider-returned HTML in the result.
        raise SourceUnavailable("Provider request failed or was rate limited.") from exc


def read_local_readsb(file: str | Path, *, at_utc: float | None = None
                      ) -> tuple[Aircraft, ...]:
    """Read only a trusted installed readsb JSON path, no auto-start of USB."""
    now = time.time() if at_utc is None else at_utc
    path = Path(file)
    try:
        stats = path.stat()
        if not path.is_file() or path.is_symlink():
            raise SourceUnavailable("Local decoder file is unavailable.")
        if stats.st_size > MAX_RESPONSE_BYTES or stats.st_size < 2:
            raise SourceUnavailable("Local decoder snapshot size is invalid.")
        if abs(now - stats.st_mtime) > FEED_AGE_LIMIT:
            raise SourceUnavailable("Local decoder is not updating.")
        with path.open("rb") as f:
            raw = f.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise SourceUnavailable("Local decoder snapshot exceeds size limit.")
        return from_readsb(json.loads(raw), source_id="local-readsb",
                           origin="local", at_utc=now)
    except (OSError, UnicodeError, ValueError, RadarDataError) as exc:
        raise SourceUnavailable("Local readsb data is missing, invalid or stale.") from exc


@dataclass(frozen=True)
class ProviderConfig:
    id: str
    latitude: float
    longitude: float
    radius_nm: int = 80
    enabled: bool = False
    min_interval_seconds: int = 60
    oauth_bearer: str | None = field(default=None, repr=False, compare=False)  # trusted secrets only

    def __post_init__(self) -> None:
        if self.id not in ("adsb.lol", "opensky"):
            raise ValueError("Unsupported aircraft provider.")
        if (real(self.latitude, -90, 90) is None or
                real(self.longitude, -180, 180) is None):
            raise ValueError("Verified region coordinates required.")
        if (type(self.radius_nm) is not int or not 1 <= self.radius_nm <= 250
                or type(self.min_interval_seconds) is not int
                or self.min_interval_seconds < 30):
            raise ValueError("Unsafe provider query or rate limit.")


def _opensky_states(data: dict, *, at_utc: float) -> dict:
    feed = real(data.get("time"), 0)
    if feed is None or abs(at_utc - feed) > FEED_AGE_LIMIT:
        raise SourceUnavailable("OpenSky data is stale.")
    rows = data.get("states")
    if not isinstance(rows, list) or len(rows) > MAX_AIRCRAFT:
        raise SourceUnavailable("Invalid OpenSky state list.")
    converted = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 17:
            continue
        contact_time = real(row[4], 0)
        position_time = real(row[3], 0)
        if contact_time is None:
            continue
        kind = "mlat" if row[16] == 2 else "adsb_icao" if row[16] == 0 else "other"
        a = {"hex": row[0], "flight": row[1],
             "seen": max(0, feed - contact_time),
             "type": kind, "lat": row[6], "lon": row[5]}
        if position_time is not None:
            a["seen_pos"] = max(0, feed - position_time)
        if (v := real(row[7])) is not None:
            a["alt_baro"] = v * 3.280839895
        if (v := real(row[9], 0)) is not None:
            a["gs"] = v * 1.94384449
        if (v := real(row[10], 0, 360)) is not None:
            a["track"] = v
        if (v := real(row[11])) is not None:
            a["baro_rate"] = v * 196.850394
        converted.append(a)
    return {"now": feed, "aircraft": converted}


class AircraftSourceManager:
    """One-shot snapshots, explicit WAN permission and monotonic rate gate.

    Owner-specific cache and provider configuration are external to this module.
    No unrequested retry/loop/background polling is started by construction.
    """

    def __init__(self, local_json: str | Path, *,
                 providers: tuple[ProviderConfig, ...] = (),
                 fetcher=_fetch_json,
                 clock=time.time, monotonic=time.monotonic):
        self.local_json = Path(local_json)
        self.providers = providers
        self.fetcher = fetcher
        self.clock, self.monotonic = clock, monotonic
        self._lock = RLock()
        self._last: dict[str, float] = {}
        self._cached: dict[str, tuple[Aircraft, ...]] = {}

    def _online(self, policy: ProviderConfig, now: float) -> tuple[Aircraft, ...]:
        if not policy.enabled:
            raise SourceUnavailable("Online provider not enabled by owner.")
        prev = self._last.get(policy.id)
        if prev is not None and self.monotonic() - prev < policy.min_interval_seconds:
            # Cache used only when the individual aircraft remains genuinely fresh.
            # Returns no data after freshness expires; never pretend a cache is live.
            cache = self._cached.get(policy.id, ())
            fresh = tuple(a for a in cache if 0 <= now - a.observed_utc <= 60)
            if fresh:
                return fresh
            raise SourceUnavailable("Provider rate limit cooldown; no fresh cached data.")
        self._last[policy.id] = self.monotonic()  # even failures respect rate budget
        lat, lon = policy.latitude, policy.longitude
        if policy.id == "adsb.lol":
            url = f"{ADSB_LOL}/v2/lat/{lat:.6f}/lon/{lon:.6f}/dist/{policy.radius_nm}"
            data = self.fetcher(url, {})
        else:
            # Bounding box is conservative and deliberately not global.
            lat_delta = min(4.16, policy.radius_nm / 60)
            lon_delta = min(180, lat_delta / max(0.05, math.cos(math.radians(lat))))
            params = {
                "lamin": max(-90, lat - lat_delta),
                "lomin": max(-180, lon - lon_delta),
                "lamax": min(90, lat + lat_delta),
                "lomax": min(180, lon + lon_delta),
            }
            if not policy.oauth_bearer:
                raise SourceUnavailable("OpenSky OAuth2 token is not configured.")
            data = self.fetcher(OPENSKY + "/api/states/all?" + urlencode(params),
                                {"Authorization": "Bearer " + policy.oauth_bearer})
            data = _opensky_states(data, at_utc=now)
        result = from_readsb(data, source_id=policy.id,
                             origin="internet", at_utc=now)
        self._cached[policy.id] = result
        return result

    def snapshot(self, *, mode: str = "antenna", online_allowed: bool = False,
                 local_allowed: bool = True) -> dict:
        if mode not in MODES:
            raise ValueError("Unsupported source mode.")
        with self._lock:
            now = self.clock()
            status = {}
            feeds: list[tuple[Aircraft, ...]] = []
            get_local = mode in ("antenna", "hybrid", "automatic") and local_allowed
            get_online = (mode in ("internet", "hybrid", "automatic") and
                          online_allowed)
            if get_local:
                try:
                    items = read_local_readsb(self.local_json, at_utc=now)
                    feeds.append(items)
                    status["local"] = "live"
                except SourceUnavailable:
                    status["local"] = "unavailable"
            else:
                status["local"] = "disabled" if mode != "internet" else "not_selected"
            enabled = [p for p in self.providers if p.enabled]
            if get_online:
                for p in enabled:
                    try:
                        items = self._online(p, now)
                        feeds.append(items)
                        status[p.id] = "live"
                    except (SourceUnavailable, RadarDataError):
                        status[p.id] = "unavailable_or_rate_limited"
            elif mode in ("internet", "hybrid", "automatic"):
                status["internet"] = "not_authorized_or_offline"
            results = merge_aircraft(feeds, at_utc=now)
            return {
                "mode": mode, "utc": now, "source_status": status,
                "online_enabled": bool(online_allowed and enabled),
                "aircraft": [a.as_dict(now) for a in results],
                "count": len(results),
                "positioned": sum(a.located(now) for a in results),
                "offline": not get_online,
                "data_available": any(v == "live" for v in status.values()),
            }
