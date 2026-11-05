# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic welle.io-style DAB+ quick/full auto-scan acceptance gates.

No SDR, Pi, real welle-cli instance, or RF reception is exercised here.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tihulu_runtime import Blocked, Module, ServiceManager
from tihulu_runtime.channel_explorer import (
    ChannelExplorer, ChannelStore, DetectedService, FrequencyLibrary,
    ProbeReading, Receiver, TunePoint,
)
from tihulu_runtime.sdr_capture import ManagedFmCapture, ManagedSdrScan
from tihulu_runtime.sdr_radio import RtlFmStream, SdrBusy, SdrTunerBroker
from tihulu_runtime.dab_auto_scan import DabAutoScanner, DabScanPlan, DabScanBlock


CATALOG = Path(__file__).resolve().parents[1] / "data/channel_frequency_presets.json"


class FakeAdapter:
    def __init__(self):
        self.starts = []
        self.stops = []

    def start(self, module_id):
        self.starts.append(module_id)

    def stop(self, module_id):
        self.stops.append(module_id)


def radio(*, modes=frozenset({"fm", "dab"}), id="usb-sdr:1-2"):
    return Receiver(id, "radio_sdr", modes, 25_000_000, 1_750_000_000,
                    connected=True)


class MockDabProbe:
    """Synthetic decoder; never represents a real received DAB service."""

    def __init__(self):
        self.calls = []

    def probe(self, receiver, point):
        self.calls.append(point.frequency_hz)
        if point.frequency_hz == 222_064_000:
            return ProbeReading("service_decoded", signal_quality=83.0,
                services=(DetectedService("0xD011", "Synthetic WDR", "radio"),))
        if point.frequency_hz == 178_352_000:
            return ProbeReading("signal_locked", signal_quality=50)
        return ProbeReading("no_signal")


class TestDabAutoScan(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "locks"
        self.adapter = FakeAdapter()
        self.service = ServiceManager([Module("radio", installed=True)],
                                      self.adapter)
        library = FrequencyLibrary.from_json(CATALOG)
        self.explorer = ChannelExplorer()
        self.scanner = DabAutoScanner(library, ManagedSdrScan(
            self.service, self.explorer, lock_root=self.root))
        self.radio = radio()
        self.probe = MockDabProbe()

    def quick(self, **kwargs):
        return self.scanner.plan(country="DE", region="Nordrhein-Westfalen",
                                 scope="quick", **kwargs)

    def full(self, **kwargs):
        return self.scanner.plan(country="DE", region="Nordrhein-Westfalen",
                                 scope="full", **kwargs)

    def run_scan(self, plan=None, **kwargs):
        args = dict(plan=plan or self.quick(), receiver=self.radio,
                    owner_id="alice", job_id="dab:1", backend=self.probe,
                    user_triggered=True)
        args.update(kwargs)
        return self.scanner.run(**args)

    def test_quick_scan_uses_only_published_de_nrw_candidates(self):
        plan = self.quick()
        self.assertEqual([b.channel for b in plan.blocks], ["5C", "9A", "11D"])
        self.assertEqual([b.frequency_hz for b in plan.blocks],
                         [178352000, 202928000, 222064000])
        self.assertFalse(plan.background_enabled)
        self.assertEqual(plan.blocks[0].source,
                         "published_dab_band_iii_raster_NOT_received")

    def test_full_channel_grid_includes_all_32_unique_discrete_centers(self):
        plan = self.full()
        self.assertEqual(len(plan.blocks), 32)
        self.assertEqual((plan.blocks[0].channel, plan.blocks[-1].channel),
                         ("5A", "12D"))
        self.assertEqual(plan.blocks[0].frequency_hz, 174928000)
        self.assertEqual(plan.blocks[-1].frequency_hz, 229072000)
        self.assertEqual(len({b.frequency_hz for b in plan.blocks}), 32)

    def test_explicit_full_upper_extension_has_38(self):
        plan = self.full(include_13_extension=True)
        self.assertEqual(len(plan.blocks), 38)
        self.assertEqual([b.channel for b in plan.blocks[-6:]],
                         ["13A", "13B", "13C", "13D", "13E", "13F"])
        self.assertEqual(plan.blocks[-1].frequency_hz, 239200000)
        with self.assertRaises(ValueError):
            self.quick(include_13_extension=True)

    def test_other_regions_do_not_inherit_nrw_candidate_list(self):
        with self.assertRaises(ValueError):
            self.scanner.plan(country="TR", region="İzmir", scope="quick")
        with self.assertRaises(ValueError):
            self.scanner.plan(country="DE", region="Berlin", scope="quick")
        self.assertEqual(len(self.scanner.plan(country="TR", region="İzmir",
                                                scope="full").blocks), 32)

    def test_auto_scan_explicit_only_and_no_unattended_hardware_use(self):
        with self.assertRaises(PermissionError):
            self.run_scan(user_triggered=False)
        self.assertEqual(self.probe.calls, [])
        self.assertEqual(self.adapter.starts, [])
        with self.assertRaises(ValueError):
            self.run_scan(backend=None)
        self.assertEqual(self.adapter.starts, [])

    def test_quick_scan_reports_live_progress_and_only_verified_services(self):
        progress = []
        result = self.run_scan(on_progress=progress.append)
        self.assertEqual(len(result.records), 3)
        self.assertEqual([(p.scanned, p.total, p.channel) for p in progress],
                         [(1, 3, "5C"), (2, 3, "9A"), (3, 3, "11D")])
        self.assertEqual([r.state for r in result.records],
                         ["signal_locked", "no_signal", "service_decoded"])
        self.assertEqual(result.multiplex_count, 1)
        self.assertEqual([(b.channel, s.service_id) for b,s
                          in result.decoded_services], [("11D", "0xD011")])
        self.assertFalse(result.cancelled)
        self.assertFalse(result.physical_pi_rf_validated)
        self.assertEqual(self.service.snapshot()["radio"]["active_tasks"], 0)
        self.assertEqual(self.adapter.stops, ["radio"])

    def test_full_scan_is_bounded_and_skips_all_unknown_services(self):
        result = self.run_scan(plan=self.full())
        self.assertEqual(len(result.records), 32)
        self.assertEqual(result.multiplex_count, 1)
        self.assertEqual(len(result.decoded_services), 1)
        self.assertEqual(len(self.probe.calls), 32)

    def test_cancel_after_one_block_returns_partial_without_lock_leak(self):
        seen = []
        progress = lambda p: seen.append(p.channel)
        result = self.run_scan(plan=self.full(), on_progress=progress,
                               should_cancel=lambda: len(seen) >= 1)
        self.assertTrue(result.cancelled)
        self.assertEqual(seen, ["5A"])
        self.assertEqual(len(self.probe.calls), 1)
        self.assertEqual(self.service.snapshot()["radio"]["active_tasks"], 0)
        self.assertEqual(self.adapter.stops, ["radio"])

    def test_cancel_before_first_block_does_not_probe(self):
        result = self.run_scan(should_cancel=lambda: True)
        self.assertTrue(result.cancelled)
        self.assertFalse(result.records)
        self.assertEqual(self.probe.calls, [])

    def test_fm_receiver_lock_rejects_all_band_dab_auto_scan(self):
        class Process:
            def __init__(self):
                self.stdout = None
                self.terminated = False
            def poll(self):
                return None
            def terminate(self):
                self.terminated = True
            def wait(self, timeout=None):
                return 0
        proc = Process()
        stream = RtlFmStream(SdrTunerBroker(), which=lambda _: "/usr/bin/rtl_fm",
                             popen=lambda *a, **k: proc)
        fm = ManagedFmCapture(self.service, stream, lock_root=self.root)
        fm.start(self.radio, frequency_hz=98_600_000,
                 owner_id="alice", job_id="fm:1", device_index=0)
        with self.assertRaises(SdrBusy):
            self.run_scan(plan=self.full())
        self.assertFalse(proc.terminated)
        self.assertFalse(self.probe.calls)
        fm.stop(owner_id="alice", job_id="fm:1")
        self.assertEqual(self.service.snapshot()["radio"]["active_tasks"], 0)

    def test_hard_off_without_owner_grant_cannot_scan(self):
        self.service.set_policy("radio", hard=False, owner_verified=True)
        with self.assertRaises(Blocked):
            self.run_scan()
        self.assertFalse(self.probe.calls)

    def test_hard_off_one_time_approval_scoped_to_specific_job(self):
        self.service.set_policy("radio", hard=False, owner_verified=True)
        token = self.service.authorize_once(task_id="dab:1", owner_id="alice",
                         scopes={"radio"}, owner_verified=True).token
        result = self.run_scan(grant_token=token)
        self.assertEqual(len(result.records), 3)
        self.assertFalse(self.service.policies["radio"].hard)
        self.assertFalse(self.service.policies["radio"].background)
        with self.assertRaises(Blocked):
            self.run_scan(job_id="dab:2", grant_token=token)

    def test_unsupported_dab_receiver_rejected_without_starting_radio(self):
        with self.assertRaises(ValueError):
            self.run_scan(receiver=radio(modes=frozenset({"fm"})))
        self.assertEqual(self.adapter.starts, [])
        with self.assertRaises(ValueError):
            self.run_scan(receiver=Receiver("usb-dvb:0", "dvb_tuner",
                 frozenset({"dvb_t2"}), 100000000, 800000000, connected=True))
        self.assertFalse(self.probe.calls)

    def test_malicious_changed_scan_plan_rejected(self):
        original = self.full()
        corrupted = DabScanPlan(original.scope, original.country,
                                original.region,
                                original.blocks[:-1]+(DabScanBlock("12D", 200000000),))
        with self.assertRaises(ValueError):
            self.run_scan(plan=corrupted)
        self.assertFalse(self.probe.calls)

    def test_channel_store_requires_explicit_owner_selected_decoded_service(self):
        result = self.run_scan()
        store = ChannelStore(":memory:")
        self.addCleanup(store.close)
        self.assertEqual(store.list(owner_id="alice"), [])
        with self.assertRaises(ValueError):
            self.scanner.save_selected(result, store, owner_id="alice",
                                       selected=((178352000, "0xnotdecoded"),))
        with self.assertRaises(PermissionError):
            self.scanner.save_selected(result, store, owner_id="bob",
                                       selected=((222064000, "0xD011"),))
        keys = self.scanner.save_selected(
            result, store, owner_id="alice",
            selected=((222064000, "0xD011"),), mark_favorites=True)
        self.assertEqual(len(keys), 1)
        data = store.list(owner_id="alice")
        self.assertEqual(data[0]["label"], "Synthetic WDR")
        self.assertEqual(data[0]["state"], "service_decoded")
        self.assertEqual(data[0]["favorite"], 1)
        self.assertEqual(store.list(owner_id="bob"), [])
        self.scanner.save_selected(result, store, owner_id="alice",
                                   selected=((222064000,"0xD011"),))
        self.assertEqual(store.list(owner_id="alice")[0]["favorite"], 1)

    def test_callback_crash_always_unlocks_and_does_not_save_result(self):
        def fail_on_first(_):
            raise RuntimeError("UI disconnected")
        with self.assertRaises(RuntimeError):
            self.run_scan(on_progress=fail_on_first)
        self.assertEqual(self.service.snapshot()["radio"]["active_tasks"], 0)
        self.assertEqual(self.adapter.stops, ["radio"])


if __name__ == "__main__":
    unittest.main()
