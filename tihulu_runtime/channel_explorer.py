# SPDX-License-Identifier: AGPL-3.0-only
"""Receive-only, owner-triggered multi-band broadcast discovery core.

This is NOT a connected hardware implementation. Real receiver capabilities,
locks, signal readings and decoded services must come from trusted adapters.
No receiver is opened by simply loading the frequency preset catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from threading import RLock
from typing import Protocol
import hashlib
import json
import sqlite3


MODES = frozenset({"dvb_t", "dvb_t2", "dvb_c", "fm", "dab", "am", "hf", "nfm", "usb", "lsb"})
DVB_MODES = frozenset({"dvb_t", "dvb_t2", "dvb_c"})
ANALOG_MODES = MODES - DVB_MODES
STATUS_ORDER = {"service_decoded": 0, "signal_locked": 1, "energy_only": 2,
                "no_signal": 3, "backend_missing": 4, "hardware_missing": 5,
                "recording_protected": 6, "scan_failed": 7}


@dataclass(frozen=True)
class FrequencyPreset:
    id: str
    name: str
    country: str
    region: str
    kind: str
    frequency_hz: int
    source: str
    bandwidth_hz: int | None = None
    locality: str = ""
    channel: str = ""


@dataclass(frozen=True)
class ScanBand:
    id: str
    country: str
    name: str
    kind: str
    start_hz: int
    stop_hz: int
    step_hz: int
    bandwidth_hz: int | None = None


@dataclass(frozen=True)
class Receiver:
    """Values must be probed on the server, never guessed from a product listing."""
    receiver_id: str
    kind: str  # 'dvb_tuner' or 'radio_sdr'
    supported_modes: frozenset[str]
    min_hz: int
    max_hz: int
    connected: bool = False
    locked_frequency_hz: int | None = None
    recording_active: bool = False
    share_locked_mux: bool = False
    fine_tune_supported: bool = False

    def supports(self, kind: str, frequency_hz: int) -> bool:
        return (self.connected and kind in self.supported_modes and
                self.min_hz <= frequency_hz <= self.max_hz and
                (self.kind == "dvb_tuner") == (kind in DVB_MODES))


@dataclass(frozen=True)
class TunePoint:
    mode: str
    frequency_hz: int
    bandwidth_hz: int | None = None
    offset_hz: int = 0

    @property
    def tuned_hz(self) -> int:
        return self.frequency_hz + self.offset_hz


@dataclass(frozen=True)
class DetectedService:
    """Returned only from an actual receiver backend; never infer from preset."""
    service_id: str
    label: str
    content_kind: str  # tv/radio/teletext/data/unknown
    is_encrypted: bool | None = None


@dataclass(frozen=True)
class ProbeReading:
    """Backend measured data. A signal level does not prove a decoded station."""
    state: str  # no_signal, energy_only, signal_locked, service_decoded
    signal_quality: float | None = None  # percent when supported; otherwise None
    services: tuple[DetectedService, ...] = ()
    technical_details: str = ""


@dataclass(frozen=True)
class ScanRecord:
    receiver_id: str
    mode: str
    frequency_hz: int
    state: str
    services: tuple[DetectedService, ...] = ()
    signal_quality: float | None = None
    detail: str = ""
    source: str = "measured_by_receiver"
    from_preset: str = ""


class ReceiverBackend(Protocol):
    def probe(self, receiver: Receiver, point: TunePoint) -> ProbeReading: ...


class FrequencyLibrary:
    """Published-frequency seeds are never reclassified as received channels."""

    def __init__(self, presets: list[FrequencyPreset], bands: list[ScanBand],
                 channel_groups: dict[str, tuple[TunePoint, ...]] | None = None):
        if len({p.id for p in presets}) != len(presets):
            raise ValueError("Duplicate preset ID")
        if len({b.id for b in bands}) != len(bands):
            raise ValueError("Duplicate band ID")
        self.presets = {p.id: p for p in presets}
        self.bands = {b.id: b for b in bands}
        self.channel_groups = channel_groups or {}

    @classmethod
    def from_json(cls, file: str | Path) -> "FrequencyLibrary":
        obj = json.loads(Path(file).read_text(encoding="utf-8"))
        if obj["status"] != "published_frequency_seed_NOT_received":
            raise ValueError("Frequency catalog must not pretend to have received RF")
        presets = [FrequencyPreset(p["id"], p["label"], p["country"], p["region"],
                                    p["kind"], p["frequency_hz"], p["source"],
                                    p.get("bandwidth_hz"), p.get("locality", ""),
                                    p.get("channel", "")) for p in obj["frequencies"]]
        bands = [ScanBand(b["id"], b["country"], b["name"], b["kind"],
                          b["start_hz"], b["stop_hz"], b["step_hz"],
                          b.get("bandwidth_hz")) for b in obj["bands"]]
        for p in presets:
            if p.kind not in MODES or not (100_000 <= p.frequency_hz <= 2_000_000_000):
                raise ValueError("Invalid preset")
            if not p.source.startswith("https://"):
                raise ValueError("Source attribution required")
        for band in bands:
            if band.kind not in MODES or not (
                    100_000 <= band.start_hz <= band.stop_hz <= 2_000_000_000
                    and band.step_hz > 0):
                raise ValueError("Invalid scan band")
        groups: dict[str, tuple[TunePoint,...]] = {}
        for group in obj.get('channel_groups', []):
            if group['id'] in groups or group['kind'] not in MODES:
                raise ValueError('Duplicate/invalid channel group')
            if not group['source'].startswith('https://'):
                raise ValueError('Channel group needs a published source')
            points = tuple(TunePoint(group['kind'], p['frequency_hz'])
                           for p in group['points'])
            if not points or len(points) > 256 or any(
                    not 100_000 <= p.frequency_hz <= 2_000_000_000 for p in points):
                raise ValueError('Invalid discrete frequency group')
            groups[group['id']] = points
        return cls(presets, bands, groups)

    def channel_group_points(self, group_id: str) -> tuple[TunePoint, ...]:
        """Use discrete DAB channel centers; DAB spacing is not uniform."""
        return self.channel_groups[group_id]

    def list_presets(self, country: str | None = None, kind: str | None = None
                     ) -> list[FrequencyPreset]:
        return [p for p in self.presets.values()
                if (country is None or p.country == country)
                and (kind is None or p.kind == kind)]

    def preset_points(self, ids: list[str]) -> tuple[TunePoint, ...]:
        if len(ids) > 256:
            raise ValueError("Maximum 256 explicit frequencies per scan")
        return tuple(TunePoint(self.presets[p].kind, self.presets[p].frequency_hz,
                               self.presets[p].bandwidth_hz) for p in ids)

    def band_points(self, band_id: str, *, page: int = 0,
                    page_size: int = 128) -> tuple[TunePoint, ...]:
        band = self.bands[band_id]
        if not (1 <= page_size <= 256) or page < 0:
            raise ValueError("Invalid scan chunk")
        total = ((band.stop_hz - band.start_hz) // band.step_hz) + 1
        if page * page_size >= total:
            return ()
        start = page * page_size
        stop = min(total, start + page_size)
        return tuple(TunePoint(band.kind, band.start_hz + i * band.step_hz,
                               band.bandwidth_hz) for i in range(start, stop))


class ChannelExplorer:
    """Single-tuner exclusive scans, user-selected plan and fine tuning.

    Consent and owner permissions are validated by the future authenticated API.
    A backend must be installed and pass through actual receiver capabilities.
    """

    def __init__(self):
        self._receiver_locks: dict[str, RLock] = {}
        self._guard = RLock()

    def _lock(self, receiver_id: str) -> RLock:
        with self._guard:
            return self._receiver_locks.setdefault(receiver_id, RLock())

    def scan(self, receiver: Receiver, points: tuple[TunePoint, ...], *,
             user_triggered: bool = False,
             backend: ReceiverBackend | None = None) -> tuple[ScanRecord, ...]:
        if not user_triggered:
            raise PermissionError("An explicit authorized scan action is required")
        if len(points) > 256:
            raise ValueError("Maximum 256 frequencies per scan chunk")
        results: list[ScanRecord] = []
        with self._lock(receiver.receiver_id):
            for point in points:
                if point.mode not in MODES:
                    raise ValueError("Invalid reception mode")
                if not isinstance(point.frequency_hz, int) or point.frequency_hz <= 0:
                    raise ValueError("Invalid frequency")
                if abs(point.offset_hz) > 500_000:
                    raise ValueError("Manual fine-tune offset exceeds 500 kHz")
                if point.offset_hz and not receiver.fine_tune_supported:
                    results.append(ScanRecord(receiver.receiver_id, point.mode,
                                              point.tuned_hz, "hardware_missing",
                                              detail="Receiver does not support fine tuning"))
                    continue
                freq = point.tuned_hz
                if not receiver.supports(point.mode, freq):
                    results.append(ScanRecord(receiver.receiver_id, point.mode, freq,
                                              "hardware_missing",
                                              detail="Receiver unavailable or mode/band unsupported"))
                    continue
                # No retune while a service or original recording owns this
                # physical receiver. Same-frequency sharing requires a *tested*
                # demux and exact lock frequency equality.
                if receiver.recording_active and not (
                        receiver.share_locked_mux and
                        point.mode in DVB_MODES and
                        receiver.locked_frequency_hz == freq):
                    results.append(ScanRecord(receiver.receiver_id, point.mode, freq,
                                              "recording_protected",
                                              detail="Retuning could interrupt an active recording"))
                    continue
                if backend is None:
                    results.append(ScanRecord(receiver.receiver_id, point.mode, freq,
                                              "backend_missing",
                                              detail="No verified receiver/decoder backend installed"))
                    continue
                try:
                    reading = backend.probe(receiver, point)
                    if reading.state not in ("no_signal", "energy_only",
                                             "signal_locked", "service_decoded"):
                        raise ValueError("Invalid signal reading")
                    if reading.signal_quality is not None and not (
                            isinstance(reading.signal_quality, (int, float))
                            and 0 <= reading.signal_quality <= 100):
                        raise ValueError("Invalid signal quality")
                    if reading.services and reading.state != "service_decoded":
                        raise ValueError("Unverified services are not decoded")
                    if reading.state == "service_decoded" and not reading.services:
                        raise ValueError("No service metadata decoded")
                except Exception:
                    results.append(ScanRecord(receiver.receiver_id, point.mode, freq,
                                              "scan_failed",
                                              detail="Receiver scan failed; inspect authorized device logs"))
                    continue
                results.append(ScanRecord(
                    receiver.receiver_id, point.mode, freq, reading.state,
                    reading.services, reading.signal_quality, reading.technical_details))
        return tuple(results)

    def manual_tune(self, receiver: Receiver, *, mode: str, frequency_hz: int,
                    fine_offset_hz: int = 0, bandwidth_hz: int | None = None,
                    user_triggered: bool = False,
                    backend: ReceiverBackend | None = None) -> ScanRecord:
        return self.scan(receiver, (TunePoint(mode, frequency_hz, bandwidth_hz,
                                               fine_offset_hz),),
                         user_triggered=user_triggered, backend=backend)[0]

    @staticmethod
    def sort_discovered(records: tuple[ScanRecord, ...]) -> list[ScanRecord]:
        # Confirmed decoded services first; only measured quality breaks ties.
        return sorted(records, key=lambda r: (
            STATUS_ORDER.get(r.state, 999),
            -(r.signal_quality if r.signal_quality is not None else -1),
            r.mode, r.frequency_hz))


class ChannelStore:
    """Persistent per-owner received/manual channel library.

    The authenticated API must determine owner IDs server-side. New entries
    are not auto-exported into user media and are not subject to News TTL.
    """

    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(path)
        self._db.execute("""CREATE TABLE IF NOT EXISTS channels (
            owner_id TEXT NOT NULL,
            key TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            frequency_hz INTEGER NOT NULL,
            service_id TEXT NOT NULL,
            content_kind TEXT NOT NULL DEFAULT 'unknown',
            label TEXT NOT NULL,
            state TEXT NOT NULL,
            source TEXT NOT NULL,
            favorite INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(owner_id, key)
        )""")
        # Forward migration for channel lists created before content_kind.
        cols = {c[1] for c in self._db.execute('PRAGMA table_info(channels)')}
        if 'content_kind' not in cols:
            self._db.execute("ALTER TABLE channels ADD COLUMN content_kind TEXT NOT NULL DEFAULT 'unknown'")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def save(self, *, owner_id: str, record: ScanRecord,
             service: DetectedService | None = None,
             custom_label: str | None = None,
             favorite: bool = False) -> str:
        if not owner_id or record.state not in (
                "service_decoded", "signal_locked", "energy_only"):
            raise ValueError("Only user-approved measured discoveries may be stored")
        if service is not None and service not in record.services:
            raise ValueError("Service was not returned by the measured receiver")
        service_id = service.service_id if service is not None else ""
        content_kind = service.content_kind if service is not None else 'unclassified'
        label = custom_label or (service.label if service else (
            "Unclassified signal" if record.state == "energy_only"
            else f"Frequency {record.frequency_hz} Hz"))
        if not label.strip() or len(label) > 180:
            raise ValueError("Channel label length invalid")
        key = hashlib.sha256(json.dumps([
            record.receiver_id, record.mode, record.frequency_hz, service_id
        ], separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
        self._db.execute("""INSERT INTO channels (
          owner_id,key,receiver_id,mode,frequency_hz,service_id,content_kind,label,state,source,favorite
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(owner_id,key) DO UPDATE SET
          label=excluded.label,state=excluded.state,source=excluded.source,
          content_kind=excluded.content_kind,
          favorite=MAX(channels.favorite,excluded.favorite)""",
          (owner_id,key,record.receiver_id,record.mode,record.frequency_hz,
           service_id,content_kind,label,record.state,record.source,1 if favorite else 0))
        self._db.commit()
        return key

    def list(self, *, owner_id: str, only_favorites: bool = False) -> list[dict]:
        if not owner_id:
            raise ValueError("Owner required")
        query = """SELECT key,receiver_id,mode,frequency_hz,service_id,
                    content_kind,label,state,source,favorite FROM channels WHERE owner_id=?"""
        if only_favorites:
            query += " AND favorite=1"
        query += " ORDER BY favorite DESC, label COLLATE NOCASE, frequency_hz"
        rows = self._db.execute(query, (owner_id,)).fetchall()
        names=("key","receiver_id","mode","frequency_hz","service_id",
               "content_kind","label","state","source","favorite")
        return [dict(zip(names, row)) for row in rows]

    def set_favorite(self, key: str, *, owner_id: str, favorite: bool) -> None:
        if not owner_id:
            raise ValueError("Owner required")
        cur = self._db.execute("UPDATE channels SET favorite=? WHERE key=? AND owner_id=?",
                               (int(favorite),key,owner_id))
        self._db.commit()
        if cur.rowcount != 1:
            raise KeyError("Channel not found for this owner")

    def remove(self, key: str, *, owner_id: str) -> None:
        if not owner_id:
            raise ValueError("Owner required")
        cur = self._db.execute("DELETE FROM channels WHERE key=? AND owner_id=?",
                               (key,owner_id))
        self._db.commit()
        if cur.rowcount != 1:
            raise KeyError("Channel not found for this owner")

    def save_manual(self, *, owner_id: str, receiver_id: str, mode: str,
                    frequency_hz: int, label: str) -> str:
        """Save a user-named candidate without ever claiming a received signal."""
        if mode not in MODES or not isinstance(frequency_hz, int) or (
                not 100_000 <= frequency_hz <= 2_000_000_000):
            raise ValueError("Invalid manually entered frequency")
        if not receiver_id.strip() or len(receiver_id)>120:
            raise ValueError("Receiver ID invalid")
        if not owner_id or not label.strip() or len(label)>180:
            raise ValueError("Owner or label invalid")
        key=hashlib.sha256(json.dumps([receiver_id,mode,frequency_hz,"manual"],
                 separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
        self._db.execute("""INSERT INTO channels
           (owner_id,key,receiver_id,mode,frequency_hz,service_id,content_kind,
            label,state,source,favorite)
           VALUES (?,?,?,?,?,?,?,?,?,?,0)
           ON CONFLICT(owner_id,key) DO UPDATE SET label=excluded.label""",
           (owner_id,key,receiver_id,mode,frequency_hz,"","unverified",label,
            "manual_unverified","user_entry"))
        self._db.commit()
        return key
