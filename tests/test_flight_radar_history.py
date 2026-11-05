# SPDX-License-Identifier: AGPL-3.0-only
"""Optional owner-scoped history: synthetic fixtures, no actual RF data."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tihulu_runtime.flight_radar_model import from_readsb
from tihulu_runtime.flight_radar_history import FlightHistory, HistoryPolicy


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "radar.sqlite"
        self.now = 1793890000.0
        snapshot = {"now":self.now,"aircraft":[
            {"hex":"ABC123","seen":0,"seen_pos":1,"lat":51.0,"lon":7.0,
             "flight":"REALONLY","type":"adsb_icao"},
            {"hex":"DEF456","seen":0,"type":"mode_s"}
        ]}
        self.items=list(from_readsb(snapshot,source_id="local-readsb",
                                    origin="local",at_utc=self.now))

    def store(self, enabled=True, verified=True):
        return FlightHistory(self.file, HistoryPolicy(enabled=enabled),
                             storage_verified=verified)

    def test_history_off_default_no_files_written(self):
        self.assertEqual(self.store(enabled=False).record(
            owner_id="alice",items=self.items,at_utc=self.now), 0)
        self.assertFalse(self.file.exists())

    def test_missing_storage_verification_does_not_create_database(self):
        with self.assertRaises(PermissionError):
            self.store(verified=False).record(
                owner_id="alice",items=self.items,at_utc=self.now)
        self.assertFalse(self.file.exists())

    def test_owner_isolated_real_rows(self):
        db=self.store()
        self.assertEqual(db.record(owner_id="alice",items=self.items,
                                   at_utc=self.now),2)
        self.assertEqual(db.list(owner_id="bob"),[])
        self.assertEqual(len(db.list(owner_id="alice")),2)

    def test_geojson_only_real_positions_with_correct_order(self):
        db=self.store()
        db.record(owner_id="alice",items=self.items,at_utc=self.now)
        geo=json.loads(db.export(owner_id="alice",format="geojson"))
        self.assertEqual(len(geo["features"]),1)
        self.assertEqual(geo["features"][0]["geometry"]["coordinates"],[7.0,51.0])
        self.assertEqual(geo["features"][0]["properties"]["position_kind"],"adsb")

    def test_json_and_csv_export_only_owner_records(self):
        db=self.store()
        db.record(owner_id="alice",items=self.items,at_utc=self.now)
        self.assertEqual(len(json.loads(db.export(owner_id="alice"))["aircraft"]),2)
        csvdata=db.export(owner_id="alice",format="csv")
        self.assertIn("position_utc",csvdata)
        self.assertIn("abc123",csvdata)
        self.assertEqual(json.loads(db.export(owner_id="bob"))["aircraft"],[])

    def test_unverified_history_path_or_bad_limit_not_accepted(self):
        db=self.store()
        with self.assertRaises(PermissionError):
            db.record(owner_id="",items=self.items,at_utc=self.now)
        with self.assertRaises(ValueError):
            db.list(owner_id="alice",limit=999999)

    def test_missing_parent_must_not_fallback_to_internal_ssd(self):
        db=FlightHistory(Path(self.tmp.name)/"missing"/"history.sqlite",
                         HistoryPolicy(enabled=True),storage_verified=True)
        with self.assertRaises(FileNotFoundError):
            db.record(owner_id="alice",items=self.items,at_utc=self.now)

    def test_unknown_export_format_denied(self):
        with self.assertRaises(ValueError):
            self.store().export(owner_id="alice",format="kml")


if __name__=="__main__":
    unittest.main()
