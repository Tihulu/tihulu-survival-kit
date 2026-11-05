# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic SDR Stage-8 tests. No physical USB or RF reception claimed."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from tihulu_runtime.channel_explorer import Receiver, TunePoint
from tihulu_runtime.sdr_radio import (
    RtlFmStream, SdrBusy, SdrTunerBroker, discover_usb_sdr,
    fm_command, receiver_candidate, setup_inventory,
)


def sdr(receiver_id="sdr-1", modes=frozenset({"fm", "dab"})):
    return Receiver(receiver_id, "radio_sdr", modes,
                    25_000_000, 1_750_000_000, connected=True)


class FakeProcess:
    def __init__(self, pcm=b"\x01\x02" * 100):
        self.stdout = io.BytesIO(pcm)
        self.exited = False
        self.terminated = False
        self.killed = False

    def poll(self):
        return 1 if self.exited else None

    def terminate(self):
        self.exited = self.terminated = True

    def wait(self, timeout=None):
        self.exited = True
        return 0

    def kill(self):
        self.exited = self.killed = True


class UsbInventoryTests(unittest.TestCase):
    def test_empty_or_absent_sysfs(self):
        self.assertEqual(discover_usb_sdr("/not/a/device/tree"), ())
        with tempfile.TemporaryDirectory() as temp:
            status = setup_inventory(temp, which=lambda cmd: None)
            self.assertFalse(status["usb_present"])
            self.assertFalse(status["background_scanning"])
            self.assertFalse(status["auto_open_receiver"])
            self.assertFalse(status["dvb_t2_hd_supported_by_this_receiver"])
            self.assertFalse(status["pi_rf_reception_verified"])

    def test_usb_identity_is_generic_chipset_not_verified_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            good = root / "1-2"
            good.mkdir()
            (good / "idVendor").write_text("0bda\n")
            (good / "idProduct").write_text("2838\n")
            (good / "product").write_text("RTL2838UHIDIR\n")
            other = root / "1-3"
            other.mkdir()
            (other / "idVendor").write_text("2040\n")
            (other / "idProduct").write_text("0265\n")
            found = discover_usb_sdr(root)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].usb_path, "1-2")
            self.assertEqual(found[0].identity_confidence,
                             "rtl2832u_compatible_usb_id_only")
            status = setup_inventory(root, which=lambda cmd:
                                     "/usr/bin/" + cmd if cmd == "rtl_fm" else None)
            self.assertTrue(status["usb_present"])
            self.assertTrue(status["backend_executables"]["fm_rtl_fm"])
            self.assertFalse(status["backend_executables"]["dab_welle_cli"])
            self.assertTrue(status["model_confirmation_required"])

    def test_verified_mode_required_before_shared_receiver(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "1-1"
            root.mkdir()
            (root / "idVendor").write_text("0bda")
            (root / "idProduct").write_text("2838")
            device = discover_usb_sdr(temp)[0]
            with self.assertRaises(ValueError):
                receiver_candidate(device, verified_modes=frozenset())
            with self.assertRaises(ValueError):
                receiver_candidate(device, verified_modes=frozenset({"dvb_t2"}))
            r = receiver_candidate(device, verified_modes=frozenset({"fm"}))
            self.assertTrue(r.supports("fm", 98_600_000))
            self.assertFalse(r.supports("dab", 222_064_000))
            self.assertFalse(r.supports("dvb_t2", 514_000_000))


class TunerBrokerTests(unittest.TestCase):
    def setUp(self):
        self.broker = SdrTunerBroker()
        self.receiver = sdr()
        self.fm = TunePoint("fm", 98_600_000)

    def test_default_idle_and_single_frequency_reservation(self):
        self.assertEqual(self.broker.snapshot("sdr-1")["state"], "idle")
        self.broker.reserve(self.receiver, self.fm, owner_id="alice", job_id="job")
        with self.assertRaises(SdrBusy):
            self.broker.reserve(self.receiver, self.fm, owner_id="alice", job_id="other")
        with self.assertRaises(SdrBusy):
            self.broker.reserve(self.receiver, TunePoint("dab", 222_064_000),
                                owner_id="bob", job_id="other")
        self.assertEqual(self.broker.snapshot("sdr-1")["frequency_hz"],
                         98_600_000)

    def test_independent_dvb_tuner_rejected_but_second_sdr_separate(self):
        dvb = Receiver("dvb", "dvb_tuner", frozenset({"dvb_t2"}),
                       470_000_000, 690_000_000, True)
        with self.assertRaises(ValueError):
            self.broker.reserve(dvb, self.fm, owner_id="alice", job_id="x")
        self.broker.reserve(self.receiver, self.fm, owner_id="alice", job_id="a")
        self.broker.reserve(sdr("sdr-2"), TunePoint("dab", 222_064_000),
                            owner_id="alice", job_id="b")
        self.assertEqual(self.broker.snapshot("sdr-2")["mode"], "dab")

    def test_reject_invalid_modes_or_unauthorized_owners(self):
        with self.assertRaises(PermissionError):
            self.broker.reserve(self.receiver, self.fm, owner_id="", job_id="a")
        with self.assertRaises(ValueError):
            self.broker.reserve(self.receiver, TunePoint("dvb_t2", 514_000_000),
                                owner_id="alice", job_id="a")
        self.broker.reserve(self.receiver, self.fm, owner_id="alice", job_id="a")
        with self.assertRaises(PermissionError):
            self.broker.release("sdr-1", owner_id="bob", job_id="a")

    def test_recording_protection_requires_explicit_safe_stop(self):
        self.broker.reserve(self.receiver, self.fm, owner_id="alice", job_id="a")
        self.broker.mark_recording("sdr-1", owner_id="alice", job_id="a", active=True)
        with self.assertRaises(SdrBusy):
            self.broker.release("sdr-1", owner_id="alice", job_id="a")
        self.broker.release("sdr-1", owner_id="alice", job_id="a",
                            recording_stop_confirmed=True)
        self.assertEqual(self.broker.snapshot("sdr-1")["state"], "idle")

    def test_shared_listeners_require_verified_fanout_and_exact_frequency(self):
        self.broker.reserve(self.receiver, self.fm, owner_id="alice", job_id="a")
        with self.assertRaises(SdrBusy):
            self.broker.join("sdr-1", self.fm, listener_id="phone", owner_id="bob")
        self.broker.mark_shared_stream_ready("sdr-1", owner_id="alice",
                                             job_id="a", ready=True)
        with self.assertRaises(SdrBusy):
            self.broker.join("sdr-1", TunePoint("fm", 98_900_000),
                             listener_id="phone", owner_id="bob")
        self.broker.join("sdr-1", self.fm, listener_id="phone", owner_id="bob")
        with self.assertRaises(PermissionError):
            self.broker.leave("sdr-1", listener_id="phone", owner_id="charlie")
        with self.assertRaises(SdrBusy):
            self.broker.release("sdr-1", owner_id="alice", job_id="a")
        self.broker.leave("sdr-1", listener_id="phone", owner_id="bob")
        self.broker.release("sdr-1", owner_id="alice", job_id="a")


class FmBackendTests(unittest.TestCase):
    def test_fm_argv_is_bounded_and_never_shell_string(self):
        cmd = fm_command(frequency_hz=98_600_000, ppm=-3, gain_db=14.4)
        self.assertEqual(cmd[0], "rtl_fm")
        self.assertEqual(cmd[cmd.index("-M") + 1], "wbfm")
        self.assertEqual(cmd[cmd.index("-f") + 1], "98600000")
        self.assertEqual(cmd[-1], "-")
        for kwargs in (
            {"frequency_hz": 222_064_000},
            {"frequency_hz": 98_600_000, "device_index": -1},
            {"frequency_hz": 98_600_000, "ppm": 10000},
            {"frequency_hz": 98_600_000, "gain_db": float("nan")},
            {"frequency_hz": 98_600_000, "binary": "/bin/sh"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                fm_command(**kwargs)

    def test_missing_backend_does_not_reserve_tuner(self):
        broker = SdrTunerBroker()
        stream = RtlFmStream(broker, which=lambda _: None)
        with self.assertRaises(FileNotFoundError):
            stream.start(sdr(), frequency_hz=98_600_000,
                         owner_id="alice", job_id="a")
        self.assertEqual(broker.snapshot("sdr-1")["state"], "idle")

    def test_process_failures_release_tuner_reservation(self):
        broker = SdrTunerBroker()
        def broken(*args, **kwargs):
            raise OSError("busy")
        stream = RtlFmStream(broker, which=lambda _: "/usr/bin/rtl_fm",
                             popen=broken)
        with self.assertRaises(OSError):
            stream.start(sdr(), frequency_hz=98_600_000,
                         owner_id="alice", job_id="a")
        self.assertEqual(broker.snapshot("sdr-1")["state"], "idle")

    def test_start_read_stop_is_on_demand_and_safe(self):
        broker = SdrTunerBroker()
        called = []
        process = FakeProcess()
        def factory(args, **kwargs):
            called.append((args, kwargs))
            return process
        stream = RtlFmStream(broker, which=lambda _: "/usr/bin/rtl_fm",
                             popen=factory)
        self.assertFalse(called)
        stream.start(sdr(), frequency_hz=98_600_000,
                     owner_id="alice", job_id="a")
        self.assertEqual(called[0][0][0], "/usr/bin/rtl_fm")
        self.assertFalse(called[0][1]["shell"])
        self.assertEqual(stream.read_pcm(4), b"\x01\x02\x01\x02")
        with self.assertRaises(SdrBusy):
            stream.start(sdr(), frequency_hz=98_600_000,
                         owner_id="alice", job_id="b")
        stream.stop()
        self.assertTrue(process.terminated)
        self.assertEqual(broker.snapshot("sdr-1")["state"], "idle")
        stream.stop()

    def test_exited_worker_is_not_reported_as_received_station(self):
        process = FakeProcess(b"")
        process.exited = True
        stream = RtlFmStream(SdrTunerBroker(), which=lambda _: "/usr/bin/rtl_fm",
                             popen=lambda *a, **k: process)
        stream.start(sdr(), frequency_hz=98_600_000,
                     owner_id="alice", job_id="a")
        with self.assertRaises(RuntimeError):
            stream.read_pcm(128)
        stream.stop()


if __name__ == "__main__":
    unittest.main()
