# SPDX-License-Identifier: AGPL-3.0-only
"""Owner-scoped regional channel selections, separate from measured RF results.

Only an authenticated server should supply owner IDs and receiver state.
The bundled country/city index contains published *candidates*, not decoded TV.
Neither constructing a profile nor editing a channel operates a receiver.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sqlite3
from typing import Callable
from urllib.request import urlopen
from uuid import uuid4

from .channel_explorer import (
    ChannelExplorer, FrequencyLibrary, FrequencyPreset, MODES, Receiver,
    ReceiverBackend, ScanRecord,
)

PACK_URL = re.compile(
    r"https://raw\.githubusercontent\.com/Tihulu/tihulu-survival-kit/"
    r"[0-9a-f]{40}/data/channel_packs/[A-Za-z0-9_.-]+\.json\Z"
)


def _text(value: str, *, max_length: int = 120) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError("Invalid text field")
    return value.strip()


def _frequency(value: int) -> int:
    if type(value) is not int or not 100_000 <= value <= 2_000_000_000:
        raise ValueError("Frequency must be an integer Hz in supported bounds")
    return value


class RegionChannelCatalog:
    """Small bundled geography + source-backed preset IDs; optional verified packs."""

    def __init__(self, region_file: str | Path, city_file: str | Path,
                 frequency_file: str | Path):
        regions = json.loads(Path(region_file).read_text(encoding="utf-8"))
        manifest = json.loads(Path(city_file).read_text(encoding="utf-8"))
        if (regions["operational_status"] != "design_seed_only"
                or manifest["status"] != "published_candidates_not_received"
                or manifest["schema_version"] != 1):
            raise ValueError("Region catalog cannot imply real reception")
        self.regions = {c["iso"]: tuple(c["regions"]) for c in regions["countries"]}
        self.library = FrequencyLibrary.from_json(frequency_file)
        self.city_options = manifest["city_options"]
        self.countrywide = manifest["countrywide_candidates"]
        self.region_candidates = manifest["region_candidates"]
        self.city_candidates: dict[tuple[str, str, str], list[str]] = {}
        for g in manifest["city_candidates"]:
            key = (g["country"], g["region"], g["city"])
            if key in self.city_candidates:
                raise ValueError("Duplicate city seed")
            self.validate_location(*key)
            self.city_candidates[key] = g["preset_ids"]
        for country, ids in self.countrywide.items():
            for pid in ids:
                self._validate_preset(pid, country, "ALL")
        for country, regions_map in self.region_candidates.items():
            for region, ids in regions_map.items():
                self.validate_location(country, region, None)
                for pid in ids:
                    self._validate_preset(pid, country, region)
        for (country, region, city), ids in self.city_candidates.items():
            for pid in ids:
                self._validate_preset(pid, country, region)
        self.download_policy = manifest["download_policy"]
        self._installed_packs: set[str] = set()

    def validate_location(self, country: str, region: str, city: str | None) -> None:
        if country not in self.regions or region not in self.regions[country]:
            raise ValueError("Unknown country/region")
        if city is not None:
            _text(city, max_length=100)

    def cities(self, country: str, region: str) -> tuple[str, ...]:
        self.validate_location(country, region, None)
        configured = tuple(self.city_options.get(country, {}).get(region, ()))
        # Every Turkish province is available for local city-center selection,
        # without claiming its channels have been catalogued.
        if country == "TR" and region not in configured:
            return (region,) + configured
        return configured

    def _validate_preset(self, preset_id: str, country: str, region: str) -> None:
        p = self.library.presets[preset_id]
        if p.country != country or p.region not in (region, "ALL"):
            raise ValueError("Mismatched geography in published frequency preset")

    def candidates(self, country: str, region: str, city: str
                   ) -> tuple[FrequencyPreset, ...]:
        """City-specific first, then region-wide, then national *candidates*."""
        self.validate_location(country, region, city)
        ids = (self.city_candidates.get((country, region, city), [])
               + self.region_candidates.get(country, {}).get(region, [])
               + self.countrywide.get(country, []))
        seen: set[str] = set()
        result = []
        for pid in ids:
            if pid not in seen:
                seen.add(pid)
                result.append(self.library.presets[pid])
        return tuple(result)

    def eligible_preset(self, country: str, region: str, city: str,
                        preset_id: str) -> FrequencyPreset:
        for preset in self.candidates(country, region, city):
            if preset.id == preset_id:
                return preset
        raise ValueError("Preset not in this location's candidate list")

    def install_pack(self, pack_id: str, *, user_triggered: bool,
                     opener: Callable = urlopen) -> int:
        """Opt-in GitHub pack import with pinned immutable URL, size and digest.

        No network action occurs for an empty configured pack list.
        Caller must authenticate the user and check storage/pack permissions.
        """
        if not user_triggered:
            raise PermissionError("Remote catalog fetch requires explicit consent")
        packs = {p["id"]: p for p in self.download_policy["packs"]}
        pack = packs[pack_id]
        url = pack["url"]
        maximum = min(int(self.download_policy["max_uncompressed_bytes"]), 1_048_576)
        if (not PACK_URL.fullmatch(url) or maximum < 1 or
                not re.fullmatch(r"[0-9a-f]{64}", pack["sha256"])):
            raise ValueError("Untrusted or unpinned GitHub pack")
        with opener(url, timeout=10) as response:
            if response.geturl() != url:
                raise ValueError("GitHub catalog redirect rejected")
            body = response.read(maximum + 1)
        if len(body) > maximum or hashlib.sha256(body).hexdigest() != pack["sha256"]:
            raise ValueError("Catalog exceeds size limit or digest mismatch")
        doc = json.loads(body.decode("utf-8"))
        if (doc.get("schema_version") != 1 or
                doc.get("status") != "published_candidates_not_received"):
            raise ValueError("Invalid remote candidate pack")
        # Large future packs can provide new published candidate frequencies,
        # not merely geographic labels. Validate everything before mutation.
        new_presets: dict[str, FrequencyPreset] = {}
        for record in doc.get("frequencies", []):
            pid = _text(record["id"])
            if pid in self.library.presets or pid in new_presets:
                raise ValueError("Cannot overwrite or duplicate a frequency seed")
            country, region = record["country"], record["region"]
            if country not in self.regions or (region != "ALL"
                and region not in self.regions[country]):
                raise ValueError("Invalid downloaded frequency geography")
            mode = record["kind"]
            hz = _frequency(record["frequency_hz"])
            url = record["source"]
            if mode not in MODES or not isinstance(url, str) or not (
                    url.startswith("https://")):
                raise ValueError("Downloaded candidate requires mode and source")
            bandwidth = record.get("bandwidth_hz")
            if bandwidth is not None:
                _frequency(bandwidth)
            new_presets[pid] = FrequencyPreset(
                pid, _text(record["label"], max_length=180), country, region,
                mode, hz, url, bandwidth, record.get("locality", ""),
                record.get("channel", ""))
        parsed: dict[tuple[str,str,str], list[str]] = {}
        for group in doc["city_candidates"]:
            key = (group["country"], group["region"], group["city"])
            self.validate_location(*key)
            ids = list(group["preset_ids"])
            if not ids or len(ids) > 256:
                raise ValueError("Invalid city pack size")
            for pid in ids:
                preset = new_presets.get(pid) or self.library.presets.get(pid)
                if preset is None or preset.country != key[0] or preset.region not in (
                        key[1], "ALL"):
                    raise ValueError("Unknown or geographically mismatched pack preset")
            if key in parsed:
                raise ValueError("Duplicate downloaded city group")
            parsed[key] = ids
        # Atomic in-memory update; never rewrite measured RF history or owner
        # preferences. Persisted pack files need an authenticated server cache.
        self.library.presets.update(new_presets)
        for key, ids in parsed.items():
            self.city_candidates[key] = list(dict.fromkeys(
                self.city_candidates.get(key, []) + ids))
        self._installed_packs.add(pack_id)
        return len(parsed)


class ChannelLineupStore:
    """Persistent local SQLite profiles; caller must be trusted owner context."""

    def __init__(self, path: str | Path, catalog: RegionChannelCatalog):
        self.catalog = catalog
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""CREATE TABLE IF NOT EXISTS region_lineups (
            owner_id TEXT NOT NULL, profile_id TEXT NOT NULL,
            country TEXT NOT NULL, region TEXT NOT NULL, city TEXT NOT NULL,
            label TEXT NOT NULL, PRIMARY KEY(owner_id,profile_id)
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS region_lineup_items (
            owner_id TEXT NOT NULL, profile_id TEXT NOT NULL,
            item_id TEXT NOT NULL, position INTEGER NOT NULL,
            preset_id TEXT, label TEXT NOT NULL, mode TEXT NOT NULL,
            frequency_hz INTEGER NOT NULL, bandwidth_hz INTEGER,
            offset_hz INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL,
            state TEXT NOT NULL, PRIMARY KEY(owner_id,profile_id,item_id),
            FOREIGN KEY(owner_id,profile_id) REFERENCES
              region_lineups(owner_id,profile_id) ON DELETE CASCADE
        )""")
        self.db.commit()

    def close(self):
        self.db.close()

    def create(self, *, owner_id: str, country: str, region: str,
               city: str, label: str) -> str:
        _text(owner_id)
        self.catalog.validate_location(country, region, city)
        _text(label)
        identifier = uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO region_lineups VALUES (?,?,?,?,?,?)",
                            (owner_id, identifier, country, region, city, label))
        return identifier

    def profiles(self, *, owner_id: str) -> list[dict]:
        _text(owner_id)
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM region_lineups WHERE owner_id=? ORDER BY label,profile_id",
            (owner_id,))]

    def _profile(self, owner_id: str, profile_id: str) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM region_lineups WHERE owner_id=? AND profile_id=?",
            (_text(owner_id), _text(profile_id))).fetchone()
        if row is None:
            raise KeyError("Profile not available to this owner")
        return row

    def items(self, *, owner_id: str, profile_id: str,
              media: str = "all") -> list[dict]:
        self._profile(owner_id, profile_id)
        if media not in ("all", "tv", "radio"):
            raise ValueError("Unknown channel medium")
        rows = self.db.execute(
            "SELECT * FROM region_lineup_items WHERE owner_id=? AND profile_id=? "
            "ORDER BY position,item_id", (owner_id, profile_id))
        return [dict(row) for row in rows if (
            media == "all" or (row["mode"].startswith("dvb_") == (media == "tv")))]

    def _append(self, owner_id, profile_id, preset_id, label, mode, frequency_hz,
                bandwidth_hz, source, state):
        number = self.db.execute(
            "SELECT COALESCE(MAX(position),-1)+1 FROM region_lineup_items "
            "WHERE owner_id=? AND profile_id=?", (owner_id, profile_id)).fetchone()[0]
        item_id = uuid4().hex
        self.db.execute("""INSERT INTO region_lineup_items (
            owner_id,profile_id,item_id,position,preset_id,label,mode,
            frequency_hz,bandwidth_hz,offset_hz,source,state
        ) VALUES (?,?,?,?,?,?,?,?,?,0,?,?)""",
            (owner_id,profile_id,item_id,number,preset_id,label,mode,
             frequency_hz,bandwidth_hz,source,state))
        return item_id

    def add_presets(self, *, owner_id: str, profile_id: str,
                    preset_ids: list[str]) -> list[str]:
        p = self._profile(owner_id, profile_id)
        if not preset_ids or len(preset_ids) > 256 or len(set(preset_ids)) != len(preset_ids):
            raise ValueError("Select between 1 and 256 unique checkboxes")
        chosen = [self.catalog.eligible_preset(
            p["country"],p["region"],p["city"],pid) for pid in preset_ids]
        existing = {r["preset_id"] for r in self.items(owner_id=owner_id,
                         profile_id=profile_id) if r["preset_id"]}
        created = []
        with self.db:
            for preset in chosen:
                if preset.id not in existing:
                    created.append(self._append(
                        owner_id,profile_id,preset.id,preset.name,preset.kind,
                        preset.frequency_hz,preset.bandwidth_hz,
                        preset.source,"published_not_received"))
                    existing.add(preset.id)
        return created

    def add_custom(self, *, owner_id: str, profile_id: str,
                   label: str, mode: str, frequency_hz: int,
                   bandwidth_hz: int | None = None) -> str:
        self._profile(owner_id, profile_id)
        _text(label, max_length=180)
        if mode not in MODES:
            raise ValueError("Unsupported reception mode")
        _frequency(frequency_hz)
        if bandwidth_hz is not None:
            _frequency(bandwidth_hz)
        with self.db:
            return self._append(owner_id,profile_id,None,label,mode,
                                frequency_hz,bandwidth_hz,
                                "user_entry","manual_unverified")

    def edit(self, *, owner_id: str, profile_id: str, item_id: str,
             label: str, mode: str, frequency_hz: int,
             offset_hz: int = 0) -> None:
        self._profile(owner_id, profile_id)
        _text(label, max_length=180)
        if mode not in MODES or type(offset_hz) is not int or abs(offset_hz) > 500_000:
            raise ValueError("Invalid mode/fine adjustment")
        _frequency(frequency_hz)
        # Editing a published candidate makes it a user entry, not sourced RF.
        with self.db:
            cur = self.db.execute("""UPDATE region_lineup_items
                SET label=?,mode=?,frequency_hz=?,offset_hz=?,
                    bandwidth_hz=NULL,preset_id=NULL,
                    source='user_entry',state='manual_unverified'
                WHERE owner_id=? AND profile_id=? AND item_id=?""",
                (label,mode,frequency_hz,offset_hz,owner_id,profile_id,item_id))
            if cur.rowcount != 1:
                raise KeyError("Item not available to this owner")

    def reorder(self, *, owner_id: str, profile_id: str,
                item_ids: list[str]) -> None:
        current = {i["item_id"] for i in self.items(owner_id=owner_id,
                                                     profile_id=profile_id)}
        if len(item_ids) != len(current) or set(item_ids) != current:
            raise ValueError("Ordering must be a complete unique item permutation")
        with self.db:
            for position, item_id in enumerate(item_ids):
                self.db.execute("""UPDATE region_lineup_items SET position=?
                    WHERE owner_id=? AND profile_id=? AND item_id=?""",
                    (position,owner_id,profile_id,item_id))

    def remove(self, *, owner_id: str, profile_id: str, item_ids: list[str]) -> None:
        current = {i["item_id"] for i in self.items(owner_id=owner_id,
                                                     profile_id=profile_id)}
        if len(item_ids) != len(set(item_ids)) or not set(item_ids) <= current:
            raise KeyError("Selected item not owned by this profile")
        with self.db:
            for item_id in item_ids:
                self.db.execute("""DELETE FROM region_lineup_items
                    WHERE owner_id=? AND profile_id=? AND item_id=?""",
                    (owner_id,profile_id,item_id))

    def tune_item(self, *, owner_id: str, profile_id: str,
                  item_id: str, receiver: Receiver,
                  user_triggered: bool = False,
                  explorer: ChannelExplorer | None = None,
                  backend: ReceiverBackend | None = None) -> ScanRecord:
        if not user_triggered:
            raise PermissionError("Tuning requires authorized explicit user action")
        row = next((i for i in self.items(owner_id=owner_id,profile_id=profile_id)
                    if i["item_id"] == item_id),None)
        if row is None:
            raise KeyError("Channel not available to this owner")
        return (explorer or ChannelExplorer()).manual_tune(
            receiver,mode=row["mode"],frequency_hz=row["frequency_hz"],
            fine_offset_hz=row["offset_hz"],bandwidth_hz=row["bandwidth_hz"],
            backend=backend,user_triggered=True)
