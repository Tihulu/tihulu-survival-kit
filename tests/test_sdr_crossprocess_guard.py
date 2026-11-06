"""No-RF Linux cross-process lock tests, including separate Python processes."""
from pathlib import Path
import os
import stat
import subprocess
import sys
import tempfile
import unittest

from tihulu_runtime.sdr_resource_broker import ReceiverBusy, SDRResourceBroker
from tihulu_runtime.sdr_crossprocess_guard import (
    LinuxFlockSDRGuard, SDRGuardUnavailable,
)
from tihulu_runtime.text_center_integration import TextCenterIntegration


@unittest.skipUnless(sys.platform == "linux", "Linux-only flock service")
class LinuxCrossProcessSDRGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "shared-locked-receivers"
        self.guard = LinuxFlockSDRGuard(
            self.root, external_use_audit=lambda rid: True)

    def test_non_linux_safety_and_audit_required(self):
        with self.assertRaises(SDRGuardUnavailable):
            LinuxFlockSDRGuard(self.root)
        with self.assertRaises(SDRGuardUnavailable):
            LinuxFlockSDRGuard(self.root, external_use_audit=lambda rid: None).reserve(
                "physical-rtl-01", "fm_rds")
        with self.assertRaises(SDRGuardUnavailable):
            LinuxFlockSDRGuard(self.root, external_use_audit=lambda rid: False).reserve(
                "physical-rtl-01", "fm_rds")
        session = self.guard.reserve("physical-rtl-01", "fm_rds")
        session.release()

    def test_permission_and_identity_validation(self):
        for rid in ("", "../other", "abc/other", ".bad", "back\\slash",
                    "a" * 1000, True, None):
            with self.subTest(id=rid), self.assertRaises(ValueError):
                self.guard.reserve(rid, "fm_rds")
        with self.assertRaises(ValueError):
            self.guard.reserve("physical-rtl-01", "")
        self.assertFalse(self.root.exists())
        guard = LinuxFlockSDRGuard(Path(self.temp.name) / "secret",
                                  external_use_audit=lambda rid: True)
        reservation = guard.reserve("physical-rtl-01", "fm_rds")
        self.assertEqual(stat.S_IMODE(guard.lock_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(next(guard.lock_dir.iterdir()).stat().st_mode), 0o600)
        reservation.release()
        reservation.release()

    def test_lock_symlink_and_bad_dir_are_refused(self):
        my_root = Path(self.temp.name) / "insecure"
        my_root.mkdir(mode=0o755)
        with self.assertRaises(SDRGuardUnavailable):
            LinuxFlockSDRGuard(my_root, external_use_audit=lambda _: True).reserve(
                "physical-rtl-01", "fm_rds")
        symlink = Path(self.temp.name) / "symlink-dir"
        symlink.symlink_to(my_root, target_is_directory=True)
        with self.assertRaises(SDRGuardUnavailable):
            LinuxFlockSDRGuard(symlink, external_use_audit=lambda _: True).reserve(
                "physical-rtl-01", "fm_rds")

    def test_two_guards_same_process_exclusive(self):
        first = self.guard.reserve("physical-rtl-01", "1090_adsb")
        second_guard = LinuxFlockSDRGuard(self.root, external_use_audit=lambda _: True)
        with self.assertRaises(ReceiverBusy):
            second_guard.reserve("physical-rtl-01", "fm_rds")
        # Second independent physical SDR can work concurrently.
        other = second_guard.reserve("physical-rtl-02", "fm_rds")
        other.release()
        first.release()
        second = second_guard.reserve("physical-rtl-01", "fm_rds")
        second.release()

    def test_real_other_process_lock_collision_and_release(self):
        script = (
            "import sys\n"
            "from tihulu_runtime.sdr_crossprocess_guard import LinuxFlockSDRGuard\n"
            "g=LinuxFlockSDRGuard(sys.argv[1], external_use_audit=lambda _: True)\n"
            "r=g.reserve('physical-rtl-01','1090_adsb')\n"
            "print('LOCKED', flush=True)\n"
            "sys.stdin.readline()\n"
            "r.release()\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script, str(self.root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        first_line = proc.stdout.readline()
        if first_line != "LOCKED\n":
            err = proc.stderr.read()
            self.fail("Secondary Python process could not reserve lock: " + err)
        with self.assertRaises(ReceiverBusy):
            self.guard.reserve("physical-rtl-01", "fm_rds")
        proc.stdin.write("\n")
        proc.stdin.flush()
        self.assertEqual(proc.wait(timeout=6), 0, proc.stderr.read())
        reservation = self.guard.reserve("physical-rtl-01", "fm_rds")
        reservation.release()

    def test_integration_still_blocks_on_missing_backend(self):
        bridge = TextCenterIntegration(broker=SDRResourceBroker(), guard=self.guard)
        with self.assertRaises(RuntimeError):
            bridge.start_fm_rds(owner_id="owner", receiver_id="physical-rtl-01",
                frequency_hz=98_600_000, duration_seconds=20, user_triggered=True)
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
