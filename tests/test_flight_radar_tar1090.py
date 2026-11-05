# SPDX-License-Identifier: AGPL-3.0-only
"""Mock-only tar1090 gateway tests; no real RF, HTTP listener or online tiles."""
from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from tihulu_runtime.tar1090_gateway import (
    Tar1090Gateway, Tar1090Paths, Tar1090Unavailable)
from tihulu_runtime.flight_radar_http import FlightRadarWSGI


class RichMapTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.html = root / "installed" / "html"
        self.data = root / "readsb"
        self.chunks = root / "chunks"
        for directory in (self.html, self.data, self.chunks):
            directory.mkdir(parents=True)
        (self.html / "index.html").write_text(
            "<html><title>tar1090 REAL upstream fixture</title></html>")
        (self.html / "defaults.js").write_text("let DefaultCenterLat = 40.56;")
        (self.html / "script.js").write_text("/* upstream JS fixture */")
        (self.html / "config.js").write_text("DefaultZoomLvl = 7;")
        (self.html / "style.css").write_text("body { color: white; }")
        (self.html / "libs").mkdir()
        (self.html / "libs" / "ol.js").write_text("// upstream lib")
        (self.chunks / "chunks.json").write_text('{"chunks":[]}')
        (self.chunks / "chunk_0.gz").write_bytes(b"compressed-fixture")
        self.gateway = Tar1090Gateway(Tar1090Paths(
            html=self.html, data=self.data, chunks=self.chunks))

    def json_data(self, aircraft):
        now = time.time()
        (self.data / "aircraft.json").write_text(
            json.dumps({"now": now, "aircraft": aircraft}))
        (self.data / "receiver.json").write_text(
            json.dumps({"lat": 50.94, "lon": 6.95}))
        return now

    def request(self, path, *, query="", authorized=True, host="tihulu.lan"):
        app = FlightRadarWSGI(
            None,
            tar1090=self.gateway,
            authorize=lambda _: ("verified-owner", True) if authorized else None,
            validate_csrf=lambda _: True,
            allowed_hosts=frozenset({"tihulu.lan", "tihulu.local", "10.10.10.10"}))
        environ = {
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "REQUEST_METHOD": "GET",
            "HTTP_HOST": host,
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(b""),
        }
        status = []
        content = b"".join(app(environ, lambda code, headers:
                               status.append((code, dict(headers)))))
        return int(status[0][0].split()[0]), status[0][1], content

    def test_original_html_libraries_and_config_are_served(self):
        self.assertTrue(self.gateway.installed())
        for path in ("", "libs/ol.js", "style.css"):
            asset = self.gateway.asset("/flight-radar/tar1090/" + path)
            self.assertTrue(asset.body)
        config = self.gateway.asset("/flight-radar/tar1090/config.js")
        self.assertIn(b"DefaultCenterLat = 51.1657", config.body)
        self.assertIn(b"DefaultCenterLon = 10.4515", config.body)
        self.assertTrue(config.body.endswith(b"DefaultZoomLvl = 7;"))
        # Germany is a map fallback, NOT a fictitious receiver coordinate.
        self.assertNotIn(b"SiteLat =", config.body)

    def test_data_and_chunk_paths_keep_upstream_semantics(self):
        self.json_data([])
        asset = self.gateway.asset("/flight-radar/tar1090/data/aircraft.json")
        self.assertEqual(json.loads(asset.body)["aircraft"], [])
        chunk = self.gateway.asset("/flight-radar/tar1090/chunks/chunk_0.gz")
        self.assertIn(("Content-Encoding", "gzip"), chunk.headers)

    def test_no_unconfigured_optional_globe_or_history_files(self):
        with self.assertRaises(Tar1090Unavailable):
            self.gateway.asset("/flight-radar/tar1090/globe_history/2026/file.json")
        with self.assertRaises(Tar1090Unavailable):
            self.gateway.asset("/flight-radar/tar1090/data/traces/10/trace.json")

    def test_path_traversal_encoded_paths_and_symlinks_fail(self):
        forbidden = ("../secret", "libs/../secret", "libs//ol.js",
                     "libs/%2e%2e/secret", "libs/\\secret", "/etc/passwd")
        for item in forbidden:
            with self.subTest(item=item), self.assertRaises(Tar1090Unavailable):
                self.gateway.asset("/flight-radar/tar1090/" + item)
        (self.html / "other.js").symlink_to(self.data / "receiver.json")
        with self.assertRaises(Tar1090Unavailable):
            self.gateway.asset("/flight-radar/tar1090/other.js")

    def test_default_full_map_is_native_routed_no_iframe(self):
        code, headers, body = self.request("/flight-radar")
        self.assertEqual(code, 302)
        self.assertEqual(headers["Location"], "/flight-radar/map")
        code, headers, body = self.request("/flight-radar/map", query="pTracks=8")
        self.assertEqual(code, 302)
        self.assertEqual(headers["Location"], "/flight-radar/tar1090/?pTracks=8")
        code, headers, body = self.request("/flight-radar/tar1090/")
        self.assertEqual(code, 200)
        self.assertIn(b"upstream fixture", body)
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])

    def test_no_positions_still_opens_native_full_map(self):
        self.json_data([])
        self.assertIsNone(self.gateway.initial_aircraft_focus())
        code, headers, _ = self.request("/flight-radar/map")
        self.assertEqual(code, 302)
        self.assertEqual(headers["Location"], "/flight-radar/tar1090/")
        code, _, body = self.request("/flight-radar/tar1090/")
        self.assertEqual(code, 200)
        self.assertIn(b"<html>", body)

    def test_fresh_real_aircraft_priority_nearest_receiver(self):
        self.json_data([
            {"hex": "ABC123", "seen": 0, "seen_pos": 0,
             "lat": 50.94, "lon": 6.97, "type": "adsb_icao"},
            {"hex": "DEF456", "seen": 0, "seen_pos": 0,
             "lat": 55.0, "lon": 9.0, "type": "adsb_icao"},
        ])
        self.assertEqual(self.gateway.initial_aircraft_focus(), "abc123")
        code, headers, _ = self.request("/flight-radar/map")
        self.assertEqual(code, 302)
        self.assertIn("icao=abc123", headers["Location"])
        self.assertIn("noIsolation=", headers["Location"])

    def test_mode_s_only_never_invents_map_positions(self):
        self.json_data([{"hex": "ABC123", "seen": 0, "type": "mode_s"}])
        self.assertIsNone(self.gateway.initial_aircraft_focus())

    def test_stale_or_missing_feed_does_not_claim_position(self):
        self.json_data([{"hex": "ABC123", "seen": 100, "seen_pos": 100,
                         "lat": 50.9, "lon": 6.9}])
        self.assertIsNone(self.gateway.initial_aircraft_focus())
        (self.data / "aircraft.json").unlink()
        self.assertIsNone(self.gateway.initial_aircraft_focus())

    def test_hostname_and_auth_protect_every_tar1090_asset(self):
        self.json_data([])
        code, _, _ = self.request("/flight-radar/tar1090/data/aircraft.json",
                                  authorized=False)
        self.assertEqual(code, 401)
        code, _, _ = self.request("/flight-radar/tar1090/data/aircraft.json",
                                  host="evil.example")
        self.assertEqual(code, 403)
        code, _, _ = self.request("/flight-radar/tar1090/data/aircraft.json",
                                  host="tihulu.local")
        self.assertEqual(code, 200)

    def test_missing_installation_explicit_light_map_fallback(self):
        (self.html / "script.js").unlink()
        self.assertFalse(self.gateway.installed())
        code, headers, _ = self.request("/flight-radar/map")
        self.assertEqual(code, 302)
        self.assertEqual(headers["Location"],
                         "/flight-radar/light-map?full_map_unavailable=1")
        code, _, _ = self.request("/flight-radar/tar1090/")
        self.assertEqual(code, 503)

    def test_unsafe_redirect_query_is_normalized(self):
        code, headers, _ = self.request("/flight-radar/map", query="pTracks&zoom=9")
        self.assertEqual(code, 302)
        self.assertIn("pTracks=", headers["Location"])
        self.assertIn("zoom=9", headers["Location"])
        code, headers, _ = self.request("/flight-radar/map", query="hello=%0D%0A")
        self.assertEqual(code, 302)
        self.assertNotIn("\r", headers["Location"])
        self.assertNotIn("\n", headers["Location"])


if __name__ == "__main__":
    unittest.main()
