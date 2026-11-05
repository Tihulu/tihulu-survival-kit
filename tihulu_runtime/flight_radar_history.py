# SPDX-License-Identifier: AGPL-3.0-only
"""Optional, owner-scoped real-aircraft history and bounded export.

OFF by default. The caller must authorize both the owner and the trusted
database volume (internal NVMe or separately mounted external SSD). This
library never formats, mounts, downloads or scans an entire storage device.
"""
from __future__ import annotations
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
import csv
import io
import json
import sqlite3
import time

from .flight_radar_model import Aircraft

MAX_RECORDS_PER_BATCH = 1000
MAX_EXPORT_ROWS = 10000


@dataclass(frozen=True)
class HistoryPolicy:
    enabled: bool = False
    retention_days: int = 7
    max_database_bytes: int = 50 * 1024 * 1024

    def __post_init__(self):
        if (type(self.retention_days) is not int or
                not 1 <= self.retention_days <= 365 or
                type(self.max_database_bytes) is not int or
                not 1 * 1024 * 1024 <= self.max_database_bytes <= 10 * 1024**3):
            raise ValueError("Unsafe aircraft history retention or size budget.")


class FlightHistory:
    """Trusted backend helper. Call with policy.enabled=True ONLY on opt-in."""

    def __init__(self, database: str | Path, policy: HistoryPolicy = HistoryPolicy(),
                 *, storage_verified: bool = False):
        self.database = Path(database)
        self.policy = policy
        self.storage_verified = storage_verified

    def _open(self) -> sqlite3.Connection:
        # Parent mount/path must be a trusted preselected writable volume.
        # No automatic fallback to another disk when external SSD disappears.
        if not self.storage_verified:
            raise PermissionError("Trusted configured storage/mount verification required.")
        if not self.database.parent.is_dir():
            raise FileNotFoundError("Configured history storage is unavailable.")
        db = sqlite3.connect(self.database)
        db.execute("""CREATE TABLE IF NOT EXISTS observations(
            owner_id TEXT NOT NULL, observed_utc REAL NOT NULL, key TEXT NOT NULL,
            position_utc REAL, latitude REAL, longitude REAL,
            source_ids TEXT NOT NULL, position_kind TEXT,
            payload TEXT NOT NULL)""")
        db.execute("""CREATE INDEX IF NOT EXISTS aircraft_history_owner_time
                      ON observations(owner_id,observed_utc DESC)""")
        return db

    def record(self, *, owner_id: str, items: list[Aircraft],
               at_utc: float | None = None) -> int:
        if not self.policy.enabled:
            return 0
        if not owner_id:
            raise PermissionError("Authenticated owner required.")
        if len(items) > MAX_RECORDS_PER_BATCH:
            raise ValueError("History batch is too large.")
        now = time.time() if at_utc is None else at_utc
        with closing(self._open()) as db, db:
            cutoff = now - self.policy.retention_days * 86400
            db.execute("DELETE FROM observations WHERE observed_utc < ?", (cutoff,))
            current_bytes = self.database.stat().st_size
            if current_bytes >= self.policy.max_database_bytes - 256 * 1024:
                raise OSError("History size quota reached. No observations written.")
            rows = []
            for a in items:
                if a.observed_utc < cutoff or a.observed_utc > now + 1:
                    continue
                data = a.as_dict(now)
                # Never include missing/stale positions in a GeoJSON track.
                rows.append((owner_id, a.observed_utc, a.key,
                             a.position_utc if a.located(now) else None,
                             a.latitude if a.located(now) else None,
                             a.longitude if a.located(now) else None,
                             ",".join(a.source_ids), a.position_kind,
                             json.dumps(data, allow_nan=False, separators=(",", ":"))))
            db.executemany("""INSERT INTO observations(
                owner_id,observed_utc,key,position_utc,latitude,longitude,
                source_ids,position_kind,payload) VALUES(?,?,?,?,?,?,?,?,?)""", rows)
            return len(rows)

    def list(self, *, owner_id: str, limit: int = 100,
             since_utc: float = 0) -> list[dict]:
        if not owner_id:
            raise PermissionError("Authenticated owner required.")
        if type(limit) is not int or not 1 <= limit <= MAX_EXPORT_ROWS:
            raise ValueError("Invalid history query limit.")
        if not self.policy.enabled or not self.database.is_file():
            return []
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT payload FROM observations
                   WHERE owner_id=? AND observed_utc>=?
                   ORDER BY observed_utc DESC LIMIT ?""",
                (owner_id, since_utc, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def export(self, *, owner_id: str, format: str = "json",
               limit: int = MAX_EXPORT_ROWS) -> str:
        """Return owner-authorized data only. Export file writing is separate."""
        rows = self.list(owner_id=owner_id, limit=limit)
        if format == "json":
            return json.dumps({"aircraft": rows}, ensure_ascii=False)
        if format == "geojson":
            features = []
            for a in rows:
                if not a.get("position_available"):
                    continue
                if a.get("latitude") is None or a.get("longitude") is None:
                    continue
                features.append({"type": "Feature",
                    "geometry": {"type": "Point",
                                 "coordinates": [a["longitude"], a["latitude"]]},
                    "properties": {
                        "icao": a["icao"], "callsign": a["callsign"],
                        "source_ids": a["source_ids"],
                        "observed_utc": a["observed_utc"],
                        "position_utc": a["position_utc"],
                        "position_kind": a["position_kind"]}})
            return json.dumps({"type": "FeatureCollection", "features": features},
                              ensure_ascii=False)
        if format == "csv":
            fields = ("icao", "callsign", "observed_utc", "position_utc",
                      "latitude", "longitude", "altitude_ft",
                      "ground_speed_kt", "position_kind", "source_id")
            file = io.StringIO()
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for a in rows:
                writer.writerow({key: a.get(key) for key in fields})
            return file.getvalue()
        raise ValueError("Unsupported export format. Use json, csv or geojson.")
