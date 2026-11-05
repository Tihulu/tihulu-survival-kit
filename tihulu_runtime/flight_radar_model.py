# SPDX-License-Identifier: AGPL-3.0-only
"""Shared Flight Radar observation contract: actual ADS-B/Mode S data only.

Independent of the standalone Qt app; deliberately contains no PySide6,
network access, SDR control, geolocation defaults or synthetic aircraft.
Compatible readsb field semantics are documented with the upstream app.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
import math
import re
import time

POSITION_AGE_LIMIT = 60.0
CONTACT_AGE_LIMIT = 60.0
FEED_AGE_LIMIT = 15.0
MAX_AIRCRAFT = 10000
ICAO = re.compile(r"[0-9a-fA-F]{6}\Z")
KNOWN_TYPES = frozenset({"adsb_icao", "adsb_icao_nt", "adsr_icao", "tisb_icao",
                         "mlat", "mode_s", "other"})
EMPTY = object()


class RadarDataError(ValueError):
    """Untrusted or outdated feed cannot be shown as live."""


def real(value: object, low: float | None = None,
         high: float | None = None) -> float | None:
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    x = float(value)
    if low is not None and x < low or high is not None and x > high:
        return None
    return x


def clean_text(value: object, *, max_length: int = 32) -> str | None:
    if not isinstance(value, str):
        return None
    value = "".join(c for c in value.strip() if c.isprintable())
    return value[:max_length] or None


@dataclass(frozen=True)
class Aircraft:
    key: str
    icao: str | None
    source_id: str
    observed_utc: float
    position_utc: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    position_kind: str | None = None
    callsign: str | None = None
    aircraft_type: str | None = None
    altitude_ft: float | None = None
    ground_speed_kt: float | None = None
    track_deg: float | None = None
    vertical_rate_fpm: float | None = None
    rssi_dbfs: float | None = None
    source_ids: tuple[str, ...] = ()
    provenance: tuple[dict, ...] = ()

    def located(self, at_utc: float | None = None) -> bool:
        now = time.time() if at_utc is None else at_utc
        return (self.position_utc is not None and
                self.latitude is not None and self.longitude is not None and
                0 <= now - self.position_utc <= POSITION_AGE_LIMIT)

    def as_dict(self, now: float) -> dict:
        result = asdict(self)
        result["position_available"] = self.located(now)
        result["contact_age_seconds"] = max(0, round(now - self.observed_utc, 1))
        result["position_age_seconds"] = (
            max(0, round(now - self.position_utc, 1)) if self.position_utc is not None
            else None)
        if not result["position_available"]:
            result["latitude"] = None
            result["longitude"] = None
        return result


def _kind(item: dict, origin: str) -> str:
    t = item.get("type")
    if t == "mlat":
        return "external_mlat" if origin == "internet" else "local_mlat_reported"
    if t in ("tisb_icao", "adsr_icao"):
        return "broadcast_relay"
    if t in ("adsb_icao", "adsb_icao_nt"):
        return "adsb"
    if t == "mode_s":
        return "mode_s_no_position"
    return "unknown"


def from_readsb(snapshot: object, *, source_id: str, origin: str,
                at_utc: float | None = None) -> tuple[Aircraft, ...]:
    """Normalize readsb-compatible JSON (including adsb.lol v2 ac list).

    Only verified UTC timestamps and real positions enter the live model.
    Non-ICAO identifiers remain source-isolated. Never infer location.
    """
    now = time.time() if at_utc is None else at_utc
    if origin not in ("local", "internet") or not source_id or ":" in source_id:
        raise RadarDataError("Invalid trusted source identity.")
    if not isinstance(snapshot, dict):
        raise RadarDataError("Aircraft source must contain a JSON object.")
    rows = snapshot.get("aircraft", snapshot.get("ac"))
    if not isinstance(rows, list) or len(rows) > MAX_AIRCRAFT:
        raise RadarDataError("Invalid or oversized aircraft list.")
    feed_time = real(snapshot.get("now"), 0)
    if feed_time is None or abs(now - feed_time) > FEED_AGE_LIMIT:
        raise RadarDataError("Feed timestamp is missing, stale or in the future.")
    result = []
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        age = real(item.get("seen"), 0)
        if age is None or age > CONTACT_AGE_LIMIT:
            continue
        observed = feed_time - age
        if observed > now + 1 or now - observed > CONTACT_AGE_LIMIT + FEED_AGE_LIMIT:
            continue
        raw_hex = item.get("hex")
        raw_hex = raw_hex.strip().lower() if isinstance(raw_hex, str) else ""
        icao = raw_hex if ICAO.fullmatch(raw_hex) else None
        # Never merge non-ICAO or missing IDs across feeds; array index is scoped
        # to THIS exact source snapshot, not a stable transponder identity.
        key = f"icao:{icao}" if icao else f"opaque:{source_id}:{index}"
        lat = real(item.get("lat"), -90, 90)
        lon = real(item.get("lon"), -180, 180)
        pos_age = real(item.get("seen_pos"), 0)
        pos_time = (feed_time - pos_age if pos_age is not None and
                    pos_age <= POSITION_AGE_LIMIT else None)
        if pos_time is None or pos_time > now + 1 or now - pos_time > POSITION_AGE_LIMIT:
            lat = lon = pos_time = None
        if lat is None or lon is None:
            lat = lon = pos_time = None
        kind = _kind(item, origin) if pos_time is not None else None
        # Internet MLAT is NEVER relabeled as local ADS-B or local MLAT.
        alt = real(item.get("alt_baro"), -3000, 80000)
        if alt is None:
            alt = real(item.get("alt_geom"), -3000, 80000)
        flight = clean_text(item.get("flight"))
        ac_type = clean_text(item.get("t"), max_length=16)
        record = {
            "source_id": source_id, "origin": origin, "seen_utc": observed,
            "position_utc": pos_time, "position_kind": kind,
            "has_position": pos_time is not None,
        }
        result.append(Aircraft(
            key=key, icao=icao, source_id=source_id, observed_utc=observed,
            position_utc=pos_time, latitude=lat, longitude=lon,
            position_kind=kind, callsign=flight, aircraft_type=ac_type,
            altitude_ft=alt, ground_speed_kt=real(item.get("gs"), 0, 1500),
            track_deg=real(item.get("track"), 0, 360),
            vertical_rate_fpm=real(item.get("baro_rate"), -15000, 15000),
            rssi_dbfs=real(item.get("rssi"), -150, 20) if origin == "local" else None,
            source_ids=(source_id,), provenance=(record,),
        ))
    return tuple(result)


def merge_aircraft(feeds: list[tuple[Aircraft, ...]], *,
                   at_utc: float | None = None) -> list[Aircraft]:
    """Deduplicate only reliable ICAO, merge fields by per-source freshness.

    A Mode S contact without position must not erase a valid position. An
    older Internet position must never replace a newer local coordinate.
    """
    now = time.time() if at_utc is None else at_utc
    grouped: dict[str, list[Aircraft]] = {}
    for feed in feeds:
        for a in feed:
            if now - a.observed_utc > CONTACT_AGE_LIMIT or a.observed_utc > now + 1:
                continue
            grouped.setdefault(a.key, []).append(a)
    combined = []
    for key, items in grouped.items():
        # Contact fields follow freshest contact, tie-breaking toward local data.
        items.sort(key=lambda a: (a.observed_utc,
                    int(any(p["origin"] == "local" for p in a.provenance))), reverse=True)
        best = items[0]
        pos = max((a for a in items if a.located(now)),
                  key=lambda a: (a.position_utc, int(
                      any(p["origin"] == "local" for p in a.provenance))),
                  default=None)
        fields = {}
        for name in ("callsign", "aircraft_type", "altitude_ft", "ground_speed_kt",
                     "track_deg", "vertical_rate_fpm", "rssi_dbfs"):
            fields[name] = next((getattr(a, name) for a in items
                                 if getattr(a, name) is not None), None)
        source_ids = tuple(dict.fromkeys(a.source_id for a in items))
        evidence = tuple(p for a in items for p in a.provenance)
        combined.append(replace(
            best, source_ids=source_ids, provenance=evidence,
            latitude=pos.latitude if pos else None,
            longitude=pos.longitude if pos else None,
            position_utc=pos.position_utc if pos else None,
            position_kind=pos.position_kind if pos else None, **fields))
    return sorted(combined, key=lambda a: (a.observed_utc, a.key), reverse=True)
