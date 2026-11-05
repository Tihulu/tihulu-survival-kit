# SPDX-License-Identifier: AGPL-3.0-only
"""Pure/mocked Flight Radar tests. No hardware, WAN, models or map tiles."""
import io
import json
import os
import time
import tempfile
import unittest
from pathlib import Path

from tihulu_runtime.flight_radar_model import (
    from_readsb, merge_aircraft, RadarDataError)
from tihulu_runtime.flight_radar_sources import (
    AircraftSourceManager, ProviderConfig, read_local_readsb,
    SourceUnavailable, _opensky_states)
from tihulu_runtime.sdr_resource_broker import SDRResourceBroker, ReceiverBusy
from tihulu_runtime.flight_radar_center import FlightRadarCenter
from tihulu_runtime.flight_radar_http import FlightRadarWSGI
from tihulu_runtime.service_manager import ServiceManager, Module, Blocked
from tihulu_runtime.channel_explorer import ChannelExplorer, Receiver, TunePoint


def data(now):
    return {"now": now, "messages": 100, "aircraft": [
        {"hex": "ABC123", "type": "adsb_icao", "seen": 1, "seen_pos": 2,
         "lat": 50.99, "lon": 6.87, "flight": "FLT123", "alt_baro": 18000,
         "gs": 310, "track": 40, "rssi": -26},
        {"hex": "DEF456", "type": "mode_s", "seen": 1, "rssi": -34},
        {"hex": "777777", "type": "adsb_icao", "seen": 100,
         "lat": 9, "lon": 9, "seen_pos": 100},
    ]}


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.now = 1793890000.0

    def test_local_only_real_aircraft(self):
        rows = from_readsb(data(self.now), source_id="local-readsb",
                           origin="local", at_utc=self.now)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].icao, "abc123")
        self.assertTrue(rows[0].located(self.now))
        self.assertEqual(rows[1].latitude, None)
        self.assertFalse(rows[1].located(self.now))
        self.assertEqual(rows[1].as_dict(self.now)["position_available"], False)

    def test_stale_position_never_drawn(self):
        snap = data(self.now)
        snap["aircraft"][0]["seen_pos"] = 80
        rows = from_readsb(snap, source_id="local-readsb",
                           origin="local", at_utc=self.now)
        self.assertIsNone(rows[0].latitude)
        self.assertEqual(rows[0].as_dict(self.now)["longitude"], None)

    def test_invalid_coordinates_do_not_become_positions(self):
        snap = data(self.now)
        for point in (120, True, float("inf"), None):
            snap["aircraft"][0]["lat"] = point
            rows = from_readsb(snap, source_id="local-readsb",
                               origin="local", at_utc=self.now)
            self.assertIsNone(rows[0].position_utc)

    def test_missing_future_and_old_feed_refused(self):
        for feed_time in (self.now - 100, self.now + 100, None):
            snap = data(self.now)
            snap["now"] = feed_time
            with self.assertRaises(RadarDataError):
                from_readsb(snap, source_id="local-readsb",
                            origin="local", at_utc=self.now)

    def test_nonicao_ids_do_not_merge_across_sources(self):
        snap = data(self.now)
        snap["aircraft"] = [{"hex": "~123456", "seen": 0},
                            {"seen": 0}]
        local = from_readsb(snap, source_id="local-readsb",
                            origin="local", at_utc=self.now)
        web = from_readsb(snap, source_id="adsb.lol",
                          origin="internet", at_utc=self.now)
        self.assertEqual(len(merge_aircraft([local, web], at_utc=self.now)), 4)

    def test_external_mlat_provenance_never_called_local_computed(self):
        snap = data(self.now)
        snap["aircraft"][0]["type"] = "mlat"
        row = from_readsb(snap, source_id="adsb.lol",
                          origin="internet", at_utc=self.now)[0]
        self.assertEqual(row.position_kind, "external_mlat")
        self.assertEqual(row.provenance[0]["origin"], "internet")

    def test_merge_prefer_fresher_local_position_even_if_online_newer_contact(self):
        local = data(self.now)
        local["aircraft"][0]["seen"] = 2
        local["aircraft"][0]["seen_pos"] = 1
        online = data(self.now)
        online["aircraft"][0].update(
            {"seen": 0, "seen_pos": 12, "lat": 44.0, "lon": 10.0,
             "type": "mlat", "flight": "WEB_NEW"})
        l = from_readsb(local, source_id="local-readsb", origin="local",
                        at_utc=self.now)
        o = from_readsb(online, source_id="adsb.lol", origin="internet",
                        at_utc=self.now)
        merged = merge_aircraft([o, l], at_utc=self.now)
        a = next(i for i in merged if i.icao == "abc123")
        self.assertEqual(a.latitude, 50.99)
        self.assertEqual(a.position_kind, "adsb")
        self.assertEqual(set(a.source_ids), {"local-readsb", "adsb.lol"})
        self.assertEqual(len(a.provenance), 2)
        self.assertEqual(a.callsign, "WEB_NEW")

    def test_newer_internet_position_can_be_used_and_is_labeled(self):
        local = data(self.now)
        local["aircraft"][0]["seen_pos"] = 25
        online = data(self.now)
        online["aircraft"][0].update(
            {"seen_pos": 1, "lat": 50.3, "lon": 6.4, "type": "mlat"})
        a = next(x for x in merge_aircraft([
            from_readsb(local, source_id="local-readsb", origin="local",
                        at_utc=self.now),
            from_readsb(online, source_id="adsb.lol", origin="internet",
                        at_utc=self.now)], at_utc=self.now)
                 if x.icao == "abc123")
        self.assertEqual(a.position_kind, "external_mlat")
        self.assertEqual(a.latitude, 50.3)

    def test_oversized_aircraft_feed_fails(self):
        snap = {"now": self.now, "aircraft": [{}] * 10001}
        with self.assertRaises(RadarDataError):
            from_readsb(snap, source_id="adsb.lol",
                        origin="internet", at_utc=self.now)

    def test_opaque_labels_do_not_infer_aircraft_type(self):
        snap = data(self.now)
        snap["aircraft"][0].pop("t", None)
        row = from_readsb(snap, source_id="local-readsb",
                          origin="local", at_utc=self.now)[0]
        self.assertIsNone(row.aircraft_type)
        self.assertEqual(row.rssi_dbfs, -26)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.now = time.time()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "aircraft.json"
        self.path.write_text(json.dumps(data(self.now)), encoding="utf-8")
        self.calls = []
        self.ticks = [0.0]

    def fetch(self, url, headers):
        self.calls.append((url, headers))
        return {"now": self.now, "ac": [
            {"hex": "fabcde", "seen": 0, "seen_pos": 0, "lat": 51.1,
             "lon": 7.5, "type": "mlat"}
        ]}

    def manager(self, enabled=False):
        return AircraftSourceManager(self.path, providers=(
            ProviderConfig("adsb.lol", 51.0, 7.0, enabled=enabled),),
            fetcher=self.fetch, clock=lambda: self.now,
            monotonic=lambda: self.ticks[0])

    def test_local_read_file_is_real_and_fresh(self):
        result = read_local_readsb(self.path, at_utc=self.now)
        self.assertEqual(len(result), 2)

    def test_missing_file_fails_closed(self):
        self.path.unlink()
        with self.assertRaises(SourceUnavailable):
            read_local_readsb(self.path, at_utc=self.now)

    def test_antenna_only_never_uses_internet(self):
        x = self.manager(enabled=True).snapshot(mode="antenna")
        self.assertEqual(x["count"], 2)
        self.assertFalse(self.calls)
        self.assertEqual(x["source_status"]["local"], "live")

    def test_internet_only_without_consent_no_fetch(self):
        x = self.manager(enabled=True).snapshot(mode="internet",
                                                online_allowed=False)
        self.assertEqual(x["count"], 0)
        self.assertFalse(self.calls)
        self.assertEqual(x["source_status"]["internet"], "not_authorized_or_offline")

    def test_internet_provider_explicit_consent(self):
        x = self.manager(enabled=True).snapshot(
            mode="internet", online_allowed=True)
        self.assertEqual(x["count"], 1)
        self.assertEqual(x["aircraft"][0]["position_kind"], "external_mlat")
        self.assertEqual(len(self.calls), 1)
        self.assertIn("/v2/lat/51.000000/lon/7.000000/dist/80",
                      self.calls[0][0])

    def test_hybrid_combines_and_preserves_source_ids(self):
        x = self.manager(enabled=True).snapshot(
            mode="hybrid", online_allowed=True)
        self.assertEqual(x["count"], 3)
        self.assertEqual(x["source_status"]["local"], "live")

    def test_local_receiver_busy_in_hybrid_can_still_use_internet(self):
        x = self.manager(enabled=True).snapshot(
            mode="hybrid", online_allowed=True, local_allowed=False)
        self.assertEqual(x["count"], 1)
        self.assertEqual(x["source_status"]["local"], "disabled")

    def test_provider_throttle_avoids_repeated_fetch(self):
        m = self.manager(enabled=True)
        m.snapshot(mode="internet", online_allowed=True)
        m.snapshot(mode="internet", online_allowed=True)
        self.assertEqual(len(self.calls), 1)
        self.ticks[0] = 61
        m.snapshot(mode="internet", online_allowed=True)
        self.assertEqual(len(self.calls), 2)

    def test_reject_unsafe_region_or_provider(self):
        for args in [("adsb.lol", 99, 0), ("adsb.fi", 52, 7),
                     ("opensky", True, 7)]:
            with self.assertRaises(ValueError):
                ProviderConfig(*args, enabled=True)

    def test_opensky_position_source_label(self):
        row = ["abc123", "FLT", "DE", self.now-2, self.now-1,
               7.0, 51.0, 3000, False, 100, 42, 2,
               None, None, None, False, 2]
        converted = _opensky_states({"time": self.now, "states": [row]},
                                    at_utc=self.now)
        data = from_readsb(converted, source_id="opensky",
                           origin="internet", at_utc=self.now)
        self.assertEqual(data[0].position_kind, "external_mlat")
        self.assertAlmostEqual(data[0].altitude_ft, 9842.519685, places=2)


class Adapter:
    def __init__(self): self.running = set()
    def start(self, name): self.running.add(name)
    def stop(self, name): self.running.remove(name)


class CenterTests(unittest.TestCase):
    def setUp(self):
        self.now = time.time()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "aircraft.json"
        self.path.write_text(json.dumps(data(self.now)))
        self.adapter = Adapter()
        self.services = ServiceManager([Module("flight_radar", installed=True),
                                        Module("radio", installed=True)], self.adapter)
        self.broker = SDRResourceBroker()
        self.source = AircraftSourceManager(self.path, clock=lambda: self.now)
        self.center = FlightRadarCenter(
            self.services, self.broker, self.source,
            receiver_id="nesdr-1", receiver_available=lambda: True,
            clock=lambda: self.now)

    def open(self, owner="alice", device="phone", mode="antenna"):
        return self.center.open_session(owner_id=owner, device_id=device,
                                        mode=mode, explicit_owner_permission=True)

    def test_no_permission_denies_start(self):
        with self.assertRaises(PermissionError):
            self.center.open_session(owner_id="alice", device_id="phone")
        self.assertEqual(self.broker.active("nesdr-1")["state"], "free")

    def test_missing_installed_worker_blocks(self):
        services = ServiceManager([Module("flight_radar", installed=False)], self.adapter)
        center = FlightRadarCenter(services, self.broker, self.source,
                                   receiver_available=lambda: True)
        with self.assertRaises(Blocked):
            center.open_session(owner_id="alice", device_id="phone",
                                explicit_owner_permission=True)

    def test_multi_device_same_adsb_stream_share(self):
        one=self.open()
        two=self.open(owner="bob",device="tablet")
        self.assertEqual(self.broker.active("nesdr-1")["subscriber_count"], 2)
        self.center.stop_session(one.id,owner_id="alice")
        self.assertEqual(self.broker.active("nesdr-1")["subscriber_count"], 1)
        x=self.center.snapshot(two.id,owner_id="bob")
        self.assertEqual(x["count"], 2)
        self.center.stop_session(two.id,owner_id="bob")
        self.assertEqual(self.broker.active("nesdr-1")["state"], "free")

    def test_cross_owner_restrictions(self):
        s=self.open()
        with self.assertRaises(PermissionError):
            self.center.snapshot(s.id,owner_id="bob")
        with self.assertRaises(PermissionError):
            self.center.stop_session(s.id,owner_id="bob")
        self.center.stop_session(s.id,owner_id="alice")

    def test_single_tuner_fm_conflict(self):
        radio=self.broker.acquire("nesdr-1",app_id="radio",owner_id="bob",
                                  purpose="fm",explicit_permission=True)
        with self.assertRaises(ReceiverBusy):
            self.open()
        self.assertEqual(self.services.snapshot()["flight_radar"]["active_tasks"], 0)
        self.broker.release(radio.token,owner_id="bob")

    def test_hybrid_falls_back_if_fm_owns_tuner(self):
        radio=self.broker.acquire("nesdr-1",app_id="radio",owner_id="bob",
                                  purpose="fm",explicit_permission=True)
        s=self.center.open_session(owner_id="alice",device_id="pc",
            mode="hybrid",online_allowed=True,explicit_owner_permission=True)
        self.assertIsNone(s.tuner_lease)
        self.assertEqual(self.center.snapshot(s.id,owner_id="alice")["source_status"]["local"],
                         "disabled")
        self.center.stop_session(s.id,owner_id="alice")
        self.broker.release(radio.token,owner_id="bob")

    def test_internet_only_never_claims_sdr(self):
        s=self.open(mode="internet")
        self.assertEqual(self.broker.active("nesdr-1")["state"],"free")
        self.center.stop_session(s.id,owner_id="alice")

    def test_shared_broker_blocks_channel_explorer_scan(self):
        s=self.open()
        explorer=ChannelExplorer(shared_broker=self.broker)
        receiver=Receiver("nesdr-1","radio_sdr",frozenset({"fm"}),
                          24_000_000,1_700_000_000,connected=True)
        with self.assertRaises(ReceiverBusy):
            explorer.scan(receiver,(TunePoint("fm",98_600_000),),
                          user_triggered=True,trusted_owner_id="bob")
        self.center.stop_session(s.id,owner_id="alice")
        result=explorer.scan(receiver,(TunePoint("fm",98_600_000),),
                             user_triggered=True,trusted_owner_id="bob")
        self.assertEqual(result[0].state,"backend_missing")
        self.assertEqual(self.broker.active("nesdr-1")["state"],"free")


class ApiTests(CenterTests):
    def setUp(self):
        super().setUp()
        self.http = FlightRadarWSGI(
            self.center, authorize=lambda e:(e.get("test.owner","alice"),True),
            validate_csrf=lambda e:e.get("HTTP_X_CSRF_TOKEN")=="pass",
            issue_csrf=lambda e:"pass",
            allowed_hosts=frozenset({"tihulu.lan","10.10.10.10"}))

    def call(self, path, method="GET", payload=None, *, host="tihulu.lan",
             origin="http://tihulu.lan", token="pass", owner="alice"):
        raw=json.dumps(payload).encode() if payload is not None else b""
        env={"PATH_INFO":path.split("?")[0],
             "QUERY_STRING":path.split("?",1)[1] if "?" in path else "",
             "REQUEST_METHOD":method,"HTTP_HOST":host,
             "HTTP_ORIGIN":origin,
             "wsgi.url_scheme":"http","HTTP_X_CSRF_TOKEN":token,
             "wsgi.input":io.BytesIO(raw),"CONTENT_LENGTH":str(len(raw)),
             "test.owner":owner,"tihulu.device_id":"test-device"}
        status=[]
        chunks=list(self.http(env,lambda s,h:status.append((s,h))))
        return int(status[0][0].split()[0]), (
            chunks[0].decode("utf-8") if chunks else "")

    def test_html_same_origin_preview(self):
        status,page=self.call("/flight-radar")
        self.assertEqual(status,200)
        self.assertIn("Flight Radar Center",page)

    def test_bootstrap_requires_portal_identity(self):
        status,text=self.call("/api/flight-radar/bootstrap")
        self.assertEqual(status,200)
        self.assertEqual(json.loads(text)["csrf_token"],"pass")

    def test_unknown_host_forbidden(self):
        status,_=self.call("/api/flight-radar/status",host="evil.example")
        self.assertEqual(status,403)

    def test_invalid_csrf_denies_receiver_session(self):
        status,_=self.call("/api/flight-radar/session","POST",
                           {"mode":"antenna","online_allowed":False},token="bad")
        self.assertEqual(status,403)
        self.assertEqual(self.broker.active("nesdr-1")["state"],"free")

    def test_post_and_read_real_data_then_stop(self):
        code,raw=self.call("/api/flight-radar/session","POST",
                           {"mode":"antenna","online_allowed":False})
        self.assertEqual(code,201)
        sid=json.loads(raw)["session_id"]
        code,raw=self.call("/api/flight-radar/aircraft?session="+sid)
        self.assertEqual(code,200)
        x=json.loads(raw)
        self.assertEqual(x["count"],2)
        self.assertIsNone(x["aircraft"][1]["latitude"])
        code,raw=self.call("/api/flight-radar/session/"+sid,"DELETE")
        self.assertEqual(code,200)
        self.assertEqual(self.broker.active("nesdr-1")["state"],"free")

    def test_disallowed_hardware_action_does_not_fake_start(self):
        code,raw=self.call("/api/flight-radar/receiver/start","POST",{})
        self.assertEqual(code,501)
        self.assertIn("adapter",raw)

    def test_no_history_fake(self):
        code,raw=self.call("/api/flight-radar/history")
        self.assertEqual(code,501)


if __name__ == "__main__":
    unittest.main()
