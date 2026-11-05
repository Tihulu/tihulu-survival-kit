# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic Stage8 cooperative-lock and Stage4 managed FM lifecycle tests."""
from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tihulu_runtime import Module, ServiceManager, Blocked
from tihulu_runtime.channel_explorer import (ChannelExplorer, ProbeReading,
                                            Receiver, TunePoint)
from tihulu_runtime.sdr_radio import RtlFmStream, SdrBusy, SdrTunerBroker
from tihulu_runtime.sdr_capture import (ManagedFmCapture, ManagedSdrScan,
                                         SdrCooperativeLock)


class Adapter:
    def __init__(self):
        self.started = []
        self.stopped = []

    def start(self, module_id):
        self.started.append(module_id)

    def stop(self, module_id):
        self.stopped.append(module_id)


class FakeProcess:
    def __init__(self):
        self.exited = False
        self.terminated = False
        self.stdout = io.BytesIO(b"\x01\x00" * 200)

    def poll(self):
        return 0 if self.exited else None

    def terminate(self):
        self.exited = self.terminated = True

    def wait(self, timeout=None):
        self.exited = True

    def kill(self):
        self.exited = True


def receiver(receiver_id="usb-sdr:1-2"):
    return Receiver(receiver_id, "radio_sdr", frozenset({"fm", "dab"}),
                    25_000_000, 1_750_000_000, connected=True)


class LockTests(unittest.TestCase):
    def test_advisory_lock_competes_without_unlinking(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "sdr"
            a = SdrCooperativeLock("usb-sdr:1-2", root=root)
            b = SdrCooperativeLock("usb-sdr:1-2", root=root)
            self.assertFalse(a.held)
            with a:
                self.assertTrue(a.held)
                self.assertEqual(a.lock_name, b.lock_name)
                with self.assertRaises(SdrBusy):
                    b.acquire()
            with b:
                self.assertTrue(b.held)
            self.assertTrue((root / a.lock_name).exists())

    def test_different_receivers_do_not_contend(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "sdr"
            with SdrCooperativeLock("usb-sdr:1-2", root=root):
                with SdrCooperativeLock("usb-sdr:1-3", root=root) as second:
                    self.assertTrue(second.held)

    def test_file_and_path_inputs_fail_closed(self):
        for name in ("../../etc", "/dev/sdr", "", "with whitespace",
                     "a" * 129, "sdr\n1"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                SdrCooperativeLock(name)
        with TemporaryDirectory() as folder:
            root = Path(folder) / "sdr"
            root.mkdir(mode=0o755)
            with self.assertRaises(PermissionError):
                SdrCooperativeLock("usb-sdr:1-2", root=root).acquire()
            os.chmod(root, 0o700)
            filename = root / SdrCooperativeLock("usb-sdr:1-2", root=root).lock_name
            filename.symlink_to(Path(folder) / "destination")
            with self.assertRaises(OSError):
                SdrCooperativeLock("usb-sdr:1-2", root=root).acquire()

    def test_separate_python_process_holding_lock_blocks_other_process(self):
        # The independent subprocess holds a lock until parent signals stdin.
        # It proves flock works across cooperating process boundaries.
        with TemporaryDirectory() as folder:
            root = Path(folder) / "sdr"
            child_code = (
                "import sys\n"
                "from tihulu_runtime.sdr_capture import SdrCooperativeLock\n"
                "lock=SdrCooperativeLock('usb-sdr:1-2',root=sys.argv[1])\n"
                "lock.acquire()\n"
                "print('locked',flush=True)\n"
                "sys.stdin.readline()\n"
                "lock.release()\n"
            )
            child = subprocess.Popen(
                [sys.executable, "-u", "-c", child_code, str(root)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "locked")
                with self.assertRaises(SdrBusy):
                    SdrCooperativeLock("usb-sdr:1-2", root=root).acquire()
                child.stdin.write("\n")
                child.stdin.flush()
                _out, err = child.communicate(timeout=5)
                self.assertEqual(child.returncode, 0, err)
                with SdrCooperativeLock("usb-sdr:1-2", root=root):
                    pass
            finally:
                if child.poll() is None:
                    child.kill()
                    child.communicate(timeout=5)


class ManagedFmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "locks"
        self.adapter = Adapter()
        self.services = ServiceManager([Module("radio", installed=True)],
                                       self.adapter)
        self.broker = SdrTunerBroker()
        self.processes = []
        def start_fake(*args, **kwargs):
            process = FakeProcess()
            self.processes.append(process)
            return process
        self.worker = RtlFmStream(self.broker, which=lambda _: "/usr/bin/rtl_fm",
                                  popen=start_fake)
        self.managed = ManagedFmCapture(self.services, self.worker,
                                        lock_root=self.root)
        self.radio = receiver()

    def begin(self, *, job_id="job-1", owner_id="alice", receiver_override=None):
        self.managed.start(receiver_override or self.radio, frequency_hz=98_600_000,
                           owner_id=owner_id, job_id=job_id, device_index=0)

    def test_inert_and_on_demand_with_background_off(self):
        self.assertEqual(self.managed.snapshot()["state"], "idle")
        self.assertEqual(self.adapter.started, [])
        self.assertFalse(self.managed.snapshot()["background_scan_enabled"])
        self.begin()
        self.assertTrue(self.managed.snapshot()["cooperative_device_lock_held"])
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 1)
        self.assertEqual(self.managed.read_pcm(4), b"\x01\x00\x01\x00")
        self.managed.stop(owner_id="alice", job_id="job-1")
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 0)
        self.assertEqual(self.managed.snapshot()["state"], "idle")
        self.assertEqual(self.adapter.stopped, ["radio"])

    def test_hard_off_denies_capture_and_does_not_open_device(self):
        self.services.set_policy("radio", hard=False, owner_verified=True)
        with self.assertRaises(Blocked):
            self.begin()
        self.assertFalse(self.processes)
        self.assertFalse(self.root.exists())

    def test_wrong_owner_cannot_stop_worker_or_lease(self):
        self.begin()
        with self.assertRaises(PermissionError):
            self.managed.stop(owner_id="bob", job_id="job-1")
        self.assertFalse(self.processes[0].terminated)
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 1)
        self.managed.stop(owner_id="alice", job_id="job-1")

    def test_second_coordinator_cannot_reopen_same_physical_receiver(self):
        self.begin()
        services2 = ServiceManager([Module("radio", installed=True)], Adapter())
        worker2 = RtlFmStream(SdrTunerBroker(), which=lambda _: "/usr/bin/rtl_fm",
                              popen=lambda *a, **k: FakeProcess())
        another = ManagedFmCapture(services2, worker2, lock_root=self.root)
        with self.assertRaises(SdrBusy):
            another.start(self.radio, frequency_hz=98_600_000,
                          owner_id="bob", job_id="job-2", device_index=0)
        self.assertEqual(services2.snapshot()["radio"]["active_tasks"], 0)
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 1)
        self.managed.stop(owner_id="alice", job_id="job-1")

    def test_failed_worker_start_releases_lock_and_service(self):
        missing = RtlFmStream(SdrTunerBroker(), which=lambda _: None)
        managed = ManagedFmCapture(self.services, missing, lock_root=self.root)
        with self.assertRaises(FileNotFoundError):
            managed.start(self.radio, frequency_hz=98_600_000,
                          owner_id="alice", job_id="job-1", device_index=0)
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 0)
        with SdrCooperativeLock(self.radio.receiver_id, root=self.root):
            pass

    def test_recording_and_listeners_keep_all_leases_until_safe_stop(self):
        self.begin()
        self.broker.mark_recording(self.radio.receiver_id, owner_id="alice",
                                   job_id="job-1", active=True)
        with self.assertRaises(SdrBusy):
            self.managed.stop(owner_id="alice", job_id="job-1")
        self.assertFalse(self.processes[0].terminated)
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 1)
        with self.assertRaises(SdrBusy):
            SdrCooperativeLock(self.radio.receiver_id, root=self.root).acquire()

        self.broker.mark_shared_stream_ready(self.radio.receiver_id,
                                             owner_id="alice", job_id="job-1",
                                             ready=True)
        self.broker.join(self.radio.receiver_id, TunePoint("fm", 98_600_000),
                         listener_id="phone", owner_id="bob")
        with self.assertRaises(SdrBusy):
            self.managed.stop(owner_id="alice", job_id="job-1",
                              recording_stop_confirmed=True)
        self.assertFalse(self.processes[0].terminated)
        self.broker.leave(self.radio.receiver_id, listener_id="phone",
                          owner_id="bob")
        # Synthetic only: real NVMe recorder must first flush and acknowledge.
        self.managed.stop(owner_id="alice", job_id="job-1",
                          recording_stop_confirmed=True)
        self.assertTrue(self.processes[0].terminated)
        self.assertFalse(self.managed.snapshot()["cooperative_device_lock_held"])

    def test_manual_authorized_tune_validation_before_service_start(self):
        with self.assertRaises(ValueError):
            self.managed.start(self.radio, frequency_hz=222_064_000,
                               owner_id="alice", job_id="bad", device_index=0)
        self.assertFalse(self.adapter.started)
        self.assertFalse(self.root.exists())

    def test_can_release_then_reuse_same_receiver(self):
        self.begin()
        self.managed.stop(owner_id="alice", job_id="job-1")
        self.begin(job_id="job-2")
        self.managed.stop(owner_id="alice", job_id="job-2")
        self.assertEqual(len(self.processes), 2)


class MockProbe:
    def __init__(self):
        self.probed = []

    def probe(self, receiver, point):
        self.probed.append((receiver.receiver_id, point.mode, point.tuned_hz))
        return ProbeReading("energy_only", signal_quality=12.5,
                            technical_details="mock-not-a-station")


class ManagedSdrScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "locks"
        self.adapter = Adapter()
        self.services = ServiceManager([Module("radio", installed=True)],
                                       self.adapter)
        self.radio = receiver()
        self.explorer = ChannelExplorer()
        self.scanner = ManagedSdrScan(self.services, self.explorer,
                                      lock_root=self.root)
        self.probe = MockProbe()
        self.fm = TunePoint("fm", 98_600_000)

    def do_scan(self, points=None, **overrides):
        args = dict(receiver=self.radio, points=(self.fm,) if points is None else points,
                    owner_id="alice", job_id="scan-1", backend=self.probe,
                    user_triggered=True)
        args.update(overrides)
        return self.scanner.scan(**args)

    def test_explicit_scan_uses_shared_explorer_and_releases_resources(self):
        readings = self.do_scan((self.fm, TunePoint("dab", 222_064_000)))
        self.assertEqual(len(readings), 2)
        self.assertEqual([r.state for r in readings], ["energy_only", "energy_only"])
        self.assertEqual(readings[0].detail, "mock-not-a-station")
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 0)
        self.assertEqual(self.adapter.started, ["radio"])
        self.assertEqual(self.adapter.stopped, ["radio"])
        with SdrCooperativeLock(self.radio.receiver_id, root=self.root):
            pass

    def test_scan_is_opt_in_and_needs_real_adapter(self):
        with self.assertRaises(PermissionError):
            self.do_scan(user_triggered=False)
        with self.assertRaises(ValueError):
            self.do_scan(backend=None)
        self.assertEqual(self.adapter.started, [])
        self.assertEqual(self.probe.probed, [])

    def test_bad_modes_cannot_route_dvb_to_sdr(self):
        with self.assertRaises(ValueError):
            self.do_scan(points=(TunePoint("dvb_t2", 514_000_000),))
        with self.assertRaises(ValueError):
            self.do_scan(points=(TunePoint("fm", 2_000_000_000),))
        with self.assertRaises(ValueError):
            self.do_scan(points=tuple())
        self.assertEqual(self.probe.probed, [])
        self.assertEqual(self.adapter.started, [])

    def test_existing_fm_stream_prevents_manual_or_multi_point_retune(self):
        broker = SdrTunerBroker()
        process = FakeProcess()
        stream = RtlFmStream(broker, which=lambda _: "/usr/bin/rtl_fm",
                             popen=lambda *a, **k: process)
        fm = ManagedFmCapture(self.services, stream, lock_root=self.root)
        fm.start(self.radio, frequency_hz=98_600_000, owner_id="alice",
                 job_id="listen-1", device_index=0)
        with self.assertRaises(SdrBusy):
            self.scanner.manual_tune(self.radio, point=self.fm, owner_id="bob",
                                     job_id="scan-2", backend=self.probe,
                                     user_triggered=True)
        self.assertFalse(self.probe.probed)
        self.assertFalse(process.terminated)
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 1)
        fm.stop(owner_id="alice", job_id="listen-1")
        result = self.scanner.manual_tune(
            self.radio, point=self.fm, owner_id="bob", job_id="scan-2",
            backend=self.probe, user_triggered=True)
        self.assertEqual(result.state, "energy_only")

    def test_failed_probe_releases_all_leases(self):
        class Broken:
            def probe(self, receiver, point):
                raise RuntimeError("device disconnected")
        results = self.do_scan(backend=Broken())
        self.assertEqual(results[0].state, "scan_failed")
        self.assertEqual(self.services.snapshot()["radio"]["active_tasks"], 0)
        with SdrCooperativeLock(self.radio.receiver_id, root=self.root):
            pass

    def test_hard_off_blocks_scan_before_lock(self):
        self.services.set_policy("radio", hard=False, owner_verified=True)
        with self.assertRaises(Blocked):
            self.do_scan()
        self.assertEqual(self.probe.probed, [])
        self.assertFalse(self.root.exists())

    def test_one_time_owner_grant_allows_only_selected_foreground_scan(self):
        self.services.set_policy("radio", hard=False, owner_verified=True)
        grant = self.services.authorize_once(
            task_id="scan-1", owner_id="alice", scopes={"radio"},
            owner_verified=True)
        outcome = self.do_scan(grant_token=grant.token)
        self.assertEqual(outcome[0].state, "energy_only")
        self.assertFalse(self.services.policies["radio"].hard)
        self.assertFalse(self.services.policies["radio"].background)
        with self.assertRaises(Blocked):
            self.do_scan(job_id="scan-2", grant_token=grant.token)

    def test_canonical_usb_receiver_id_required(self):
        other = receiver("faked-sdr-id")
        with self.assertRaises(ValueError):
            self.do_scan(receiver=other)
        self.assertFalse(self.adapter.started)


if __name__ == "__main__":
    unittest.main()
