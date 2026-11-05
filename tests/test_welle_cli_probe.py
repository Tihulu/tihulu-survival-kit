# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic upstream-style welle-cli process, no physical RF in CI."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import stat
import textwrap
import unittest

from tihulu_runtime.channel_explorer import (
    ChannelExplorer, ChannelStore, FrequencyLibrary, Receiver, TunePoint,
)
from tihulu_runtime import Module, ServiceManager
from tihulu_runtime.sdr_capture import ManagedSdrScan
from tihulu_runtime.dab_auto_scan import DabAutoScanner
from tihulu_runtime.welle_cli_probe import (
    MAX_CAPTURE_BYTES, WelleCliDabProbe, WelleCliProbeError,
    dab_channel_map, interpret_welle_cli_log, UniqueRtlReceiverGate,
)


CATALOG = Path(__file__).resolve().parents[1] / "data/channel_frequency_presets.json"


def mock_radio():
    return Receiver("usb-sdr:1-2", "radio_sdr",
                    frozenset({"dab"}), 25_000_000, 1_750_000_000,
                    connected=True)


class TestWelleCliProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = FrequencyLibrary.from_json(CATALOG)
        self.point = TunePoint("dab", 222_064_000)
        self.radio = mock_radio()

    def fake_binary(self, body: str) -> Path:
        file = self.root / "fake-welle-cli"
        file.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body),
                        encoding="utf-8")
        file.chmod(0o700)
        return file

    def probe(self, *, script: str, mapping=None, point=None):
        binary = self.fake_binary(script)
        scanner = WelleCliDabProbe(
            self.library, executable=binary,
            verified_single_device=mapping,
            dwell_seconds=4)
        return scanner, scanner.probe(self.radio, point or self.point)

    def test_freq_channel_grid_uses_existing_source_backed_table(self):
        mapping = dab_channel_map(self.library)
        self.assertEqual(len(mapping), 38)
        self.assertEqual(mapping[178352000], "5C")
        self.assertEqual(mapping[202928000], "9A")
        self.assertEqual(mapping[222064000], "11D")
        self.assertEqual(mapping[239200000], "13F")

    def test_command_never_enables_http_dump_audio_or_unknown_driver(self):
        cli = WelleCliDabProbe(
            self.library, executable=Path("/usr/bin/welle-cli"),
            verified_single_device=lambda _: True)
        command = cli.command(self.point)
        self.assertEqual(command[1:3], ("-c", "11D"))
        self.assertIn("rtl_sdr", command)
        self.assertIn("-F", command)
        self.assertIn("-T", command)
        self.assertIn("-p", command)
        self.assertFalse({"-w", "-D", "-d", "-f", "-C"} & set(command))
        self.assertGreater(len(command[-1]), 32)
        self.assertNotIn("--", command)
        with self.assertRaises(ValueError):
            cli.command(TunePoint("fm", 222064000))
        with self.assertRaises(ValueError):
            cli.command(TunePoint("dab", 222064000, offset_hz=200))
        with self.assertRaises(ValueError):
            cli.command(TunePoint("dab", 222000000))

    def test_default_fail_closed_without_verified_tuner_map(self):
        fake = self.fake_binary("raise SystemExit(99)\n")
        cli = WelleCliDabProbe(self.library, executable=fake)
        with self.assertRaisesRegex(WelleCliProbeError, "mapping"):
            cli.probe(self.radio, self.point)

    def test_explicit_false_identity_rejects_before_any_subprocess(self):
        fake = self.fake_binary("raise SystemExit(99)\n")
        cli = WelleCliDabProbe(
            self.library, executable=fake,
            verified_single_device=lambda rid: False)
        with self.assertRaisesRegex(WelleCliProbeError, "mapping"):
            cli.probe(self.radio, self.point)

    def test_mock_local_decoder_returns_real_shape_labelled_service(self):
        script = r'''
import sys
print("New Service: 0xD011", flush=True)
print("Ensemble label: Test Ensemble", flush=True)
print("Service list", file=sys.stderr, flush=True)
print("  [0xd011] Synthetic WDR [component 0 ASCTy: DAB+ ] [subch 5 bitrate:96]", file=sys.stderr, flush=True)
print("  [0xd012] Test Data [component 1 ASCTy: unknown ]", file=sys.stderr, flush=True)
assert sys.stdin.readline().strip() == "."
'''
        cli, result = self.probe(script=script, mapping=lambda rid: rid == "usb-sdr:1-2")
        self.assertEqual(result.state, "service_decoded")
        self.assertIsNone(result.signal_quality)
        self.assertEqual([(s.service_id, s.label) for s in result.services],
                         [("0xD011", "Synthetic WDR")])
        # Unknown-component data entry must not be mislabelled as audio.
        self.assertNotIn("-w", cli.command(self.point))

    def test_only_unlabelled_fic_service_id_means_locked_not_station(self):
        reading = interpret_welle_cli_log(
            b"New Service: 0xD011\nEnsemble label: TEST\n",
            timed_out=True, returncode=None)
        self.assertEqual(reading.state, "signal_locked")
        self.assertFalse(reading.services)

    def test_idle_no_result_does_not_invent_services_or_snr(self):
        reading = interpret_welle_cli_log(
            b"Wait for sync\n", timed_out=True, returncode=None)
        self.assertEqual(reading.state, "no_signal")
        self.assertIsNone(reading.signal_quality)
        self.assertFalse(reading.services)
        self.assertIn("not proven", reading.technical_details)

    def test_nonzero_child_and_usb_errors_never_appear_as_no_signal(self):
        for data in (b"Could not start device\n", b"RTL_SDR: No devices found",
                     b"RTL_SDR: Opening rtl-sdr failed"):
            with self.subTest(data=data):
                with self.assertRaises(WelleCliProbeError):
                    interpret_welle_cli_log(data, timed_out=False,
                                           returncode=1)
        with self.assertRaises(WelleCliProbeError):
            interpret_welle_cli_log(b"", timed_out=False, returncode=2)

    def test_rogue_lines_not_promoted_to_services(self):
        reading = interpret_welle_cli_log(
            b"Service list\n  [0x123] Missing label\n",
            timed_out=False, returncode=0)
        # A service with just a label and no component should not be
        # presented as confirmed playable audio.
        self.assertNotEqual(reading.state, "service_decoded")

    def test_invalid_receiver_fails_before_device_open(self):
        fake = self.fake_binary("raise SystemExit(99)\n")
        cli = WelleCliDabProbe(
            self.library, executable=fake, verified_single_device=lambda _: True)
        invalid = Receiver("tv:0", "dvb_tuner", frozenset({"dvb_t2"}),
                           100000000, 800000000, connected=True)
        with self.assertRaises(WelleCliProbeError):
            cli.probe(invalid, self.point)

    def test_missing_executable_fails_without_web_fallback(self):
        cli = WelleCliDabProbe(
            self.library, executable=self.root / "missing-cli",
            verified_single_device=lambda _: True)
        with self.assertRaises(WelleCliProbeError):
            cli.probe(self.radio, self.point)

    def test_bounded_timeout_terminates_silent_decoder(self):
        pidfile = self.root / "pid"
        script = f'''
import os
from pathlib import Path
import time
Path({str(pidfile)!r}).write_text(str(os.getpid()))
print("Wait for sync", flush=True)
time.sleep(60)
'''
        cli, result = self.probe(script=script, mapping=lambda _: True)
        self.assertEqual(result.state, "no_signal")
        pid = int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_log_overflow_fails_closed_and_kills_decoder(self):
        script = f'''
import sys
sys.stdout.write("x"*{MAX_CAPTURE_BYTES + 4096})
sys.stdout.flush()
'''
        fake = self.fake_binary(script)
        cli = WelleCliDabProbe(
            self.library, executable=fake, verified_single_device=lambda _: True)
        with self.assertRaisesRegex(WelleCliProbeError, "bounded budget"):
            cli.probe(self.radio, self.point)

    def test_scanner_classifies_backend_failures_separately(self):
        script = 'raise SystemExit(1)\n'
        binary = self.fake_binary(script)
        cli = WelleCliDabProbe(
            self.library, executable=binary,
            verified_single_device=lambda rid: True)
        record = ChannelExplorer().scan(
            self.radio, (self.point,), backend=cli, user_triggered=True)[0]
        self.assertEqual(record.state, "scan_failed")
        self.assertFalse(record.services)

    def fake_sysfs_device(self, name: str = "1-2"):
        root = self.root / "sysfs"
        device = root / name
        device.mkdir(parents=True)
        (device / "idVendor").write_text("0bda\n")
        (device / "idProduct").write_text("2838\n")
        return root

    def test_unique_device_gate_checks_native_count_and_usb_path(self):
        sysfs = self.fake_sysfs_device()
        gate = UniqueRtlReceiverGate(sysfs_root=sysfs, count=lambda: 1)
        self.assertTrue(gate("usb-sdr:1-2"))
        self.assertFalse(gate("usb-sdr:1-3"))
        self.assertFalse(UniqueRtlReceiverGate(
            sysfs_root=sysfs, count=lambda: 2)("usb-sdr:1-2"))
        self.assertFalse(UniqueRtlReceiverGate(
            sysfs_root=sysfs, count=lambda: 0)("usb-sdr:1-2"))
        self.fake_sysfs_device("1-3")
        self.assertFalse(gate("usb-sdr:1-2"))

    def test_unique_device_gate_refuses_missing_native_library(self):
        sysfs = self.fake_sysfs_device()
        def failed_count():
            raise WelleCliProbeError("no native library")
        gate = UniqueRtlReceiverGate(sysfs_root=sysfs, count=failed_count)
        self.assertFalse(gate("usb-sdr:1-2"))

    def test_end_to_end_foreground_lease_lock_decoder_and_selected_store(self):
        sysfs = self.fake_sysfs_device()
        src = r'''
import sys
channel = sys.argv[sys.argv.index("-c") + 1]
assert "-w" not in sys.argv and "-D" not in sys.argv
assert sys.stdin.readline().strip() == "."
if channel == "11D":
    print("New Service: 0xD011", flush=True)
    print("Service list", file=sys.stderr, flush=True)
    print("  [0xd011] Mock Audio [component 0 ASCTy: DAB+ ] [subch 5 bitrate:96]", file=sys.stderr, flush=True)
else:
    print("Wait for sync", flush=True)
'''
        binary = self.fake_binary(src)
        decoder = WelleCliDabProbe(
            self.library, executable=binary,
            verified_single_device=UniqueRtlReceiverGate(
                sysfs_root=sysfs, count=lambda: 1),
            dwell_seconds=4)
        class Adapter:
            def __init__(self):
                self.starts = []
                self.stops = []
            def start(self, module_id):
                self.starts.append(module_id)
            def stop(self, module_id):
                self.stops.append(module_id)
        adapter = Adapter()
        services = ServiceManager([Module("radio", installed=True)], adapter)
        scanner = DabAutoScanner(self.library, ManagedSdrScan(
            services, ChannelExplorer(), lock_root=self.root / "locks"))
        progress = []
        plan = scanner.plan(country="DE", region="Nordrhein-Westfalen",
                            scope="quick")
        result = scanner.run(
            plan, self.radio, owner_id="alice", job_id="dab:scan",
            backend=decoder, user_triggered=True, on_progress=progress.append)
        self.assertEqual(len(result.records), 3)
        self.assertEqual([record.state for record in result.records],
                         ["no_signal", "no_signal", "service_decoded"])
        self.assertEqual(len(result.decoded_services), 1)
        self.assertEqual(result.decoded_services[0][1].label, "Mock Audio")
        self.assertEqual([p.channel for p in progress], ["5C", "9A", "11D"])
        self.assertEqual(services.snapshot()["radio"]["active_tasks"], 0)
        self.assertEqual(adapter.starts, ["radio"])
        self.assertEqual(adapter.stops, ["radio"])
        store = ChannelStore(":memory:")
        self.addCleanup(store.close)
        selected = ((222_064_000, "0xD011"),)
        ids = scanner.save_selected(
            result, store, owner_id="alice", selected=selected,
            mark_favorites=True)
        self.assertEqual(len(ids), 1)
        self.assertEqual(store.list(owner_id="alice")[0]["label"], "Mock Audio")
        self.assertTrue(store.list(owner_id="alice")[0]["favorite"])

    def test_timeout_value_restricted(self):
        for value in (-1, 0, 3, 41, "10", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                WelleCliDabProbe(self.library,
                                executable=Path("/usr/bin/welle-cli"),
                                dwell_seconds=value)


if __name__ == "__main__":
    unittest.main()
