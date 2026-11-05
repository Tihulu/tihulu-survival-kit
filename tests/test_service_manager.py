"""No Pi or systemd required: test the policy and lease safety contract."""
import json
import tempfile
import unittest
from pathlib import Path
from tihulu_runtime import (Module, ServiceManager, Blocked, Busy,
                            default_catalog, UserSystemdAdapter)


class Fake:
    def __init__(self):
        self.running = set()
        self.starts = []
        self.stops = []
        self.fail_on = None

    def start(self, name):
        if name == self.fail_on:
            raise RuntimeError("simulated unavailable engine")
        self.running.add(name)
        self.starts.append(name)

    def stop(self, name):
        self.running.remove(name)
        self.stops.append(name)


class TestManager(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.fake = Fake()
        mods = [Module("radio", installed=True),
                Module("asr", installed=True),
                Module("translator", installed=True),
                Module("captions", ("radio", "asr", "translator"), True),
                Module("local_ai", installed=True, idle_seconds=20),
                Module("news", installed=True),
                Module("emergency_monitor", installed=True)]
        self.s = ServiceManager(mods, self.fake, clock=lambda: self.now)

    def test_no_background_wake(self):
        with self.assertRaises(Blocked):
            self.s.acquire("news", task_id="n", owner_id="alice", mode="background")
        self.assertEqual(self.fake.starts, [])

    def test_foreground_runs_with_bg_and_startup_off(self):
        self.s.acquire("news", task_id="n", owner_id="alice")
        self.assertEqual(self.fake.running, {"news"})
        self.s.release("n", owner_id="alice")
        self.s.sweep_idle()
        self.assertFalse(self.fake.running)

    def test_shared_worker_not_stopped_while_other_tab_uses_it(self):
        self.s.acquire("captions", task_id="radio-captions", owner_id="alice")
        self.s.acquire("translator", task_id="browser-translate", owner_id="alice")
        self.s.release("radio-captions", owner_id="alice")
        self.s.sweep_idle()
        self.assertEqual(self.fake.running, {"translator"})
        self.s.release("browser-translate", owner_id="alice")
        self.s.sweep_idle()
        self.assertFalse(self.fake.running)
        self.assertEqual(self.fake.starts.count("translator"), 1)

    def test_hard_off_requires_explicit_grant(self):
        self.s.set_policy("local_ai", hard=False, owner_verified=True)
        with self.assertRaises(Blocked):
            self.s.acquire("local_ai", task_id="t1", owner_id="alice")
        grant = self.s.authorize_once(task_id="t1", owner_id="alice",
                                      scopes={"local_ai"}, owner_verified=True)
        self.s.acquire("local_ai", task_id="t1", owner_id="alice",
                       grant_token=grant.token)
        self.s.release("t1", owner_id="alice")
        self.assertFalse(self.s.policies["local_ai"].hard)
        self.now += 21
        self.s.sweep_idle()
        self.assertNotIn("local_ai", self.fake.running)
        with self.assertRaises(Blocked):
            self.s.acquire("local_ai", task_id="t2", owner_id="alice",
                           grant_token=grant.token)

    def test_grant_cannot_cross_owner_or_task(self):
        self.s.set_policy("asr", hard=False, owner_verified=True)
        g = self.s.authorize_once(task_id="t1", owner_id="alice",
                                  scopes={"asr"}, owner_verified=True)
        with self.assertRaises(Blocked):
            self.s.acquire("asr", task_id="t1", owner_id="bob", grant_token=g.token)
        with self.assertRaises(Blocked):
            self.s.acquire("asr", task_id="t2", owner_id="alice", grant_token=g.token)

    def test_grant_expires_and_not_valid_for_background(self):
        self.s.set_policy("asr", hard=False, owner_verified=True)
        g = self.s.authorize_once(task_id="t", owner_id="alice",
                                  scopes={"asr"}, owner_verified=True,
                                  lifetime_seconds=10)
        self.now += 11
        with self.assertRaises(Blocked):
            self.s.acquire("asr", task_id="t", owner_id="alice",
                           grant_token=g.token)

    def test_no_unapproved_admin_toggle(self):
        with self.assertRaises(PermissionError):
            self.s.set_policy("asr", hard=False)
        with self.assertRaises(PermissionError):
            self.s.authorize_once(task_id="t", owner_id="bob", scopes={"asr"})

    def test_emergency_requires_choice(self):
        with self.assertRaises(Blocked):
            self.s.acquire("emergency_monitor", task_id="e", owner_id="alice")
        self.s.configure_emergency(enabled=False, background=False,
                                   startup=False, owner_verified=True)
        with self.assertRaises(Blocked):
            self.s.acquire("emergency_monitor", task_id="e", owner_id="alice")
        self.s.configure_emergency(enabled=True, background=True,
                                   startup=False, owner_verified=True)
        self.s.acquire("emergency_monitor", task_id="e", owner_id="alice",
                       mode="background")

    def test_recording_survives_browser_caption_exit(self):
        self.s.acquire("radio", task_id="recording", owner_id="alice")
        self.s.acquire("captions", task_id="caption", owner_id="alice")
        self.s.release("caption", owner_id="alice")
        self.s.sweep_idle()
        self.assertEqual(self.fake.running, {"radio"})
        self.s.release("recording", owner_id="alice")
        self.s.sweep_idle()
        self.assertFalse(self.fake.running)

    def test_idle_model_unload(self):
        self.s.acquire("local_ai", task_id="chat", owner_id="alice")
        self.s.release("chat", owner_id="alice")
        self.now += 19
        self.assertEqual(self.s.sweep_idle(), [])
        self.now += 1
        self.assertEqual(self.s.sweep_idle(), ["local_ai"])

    def test_active_task_not_hard_disabled(self):
        self.s.acquire("captions", task_id="t", owner_id="alice")
        with self.assertRaises(Busy):
            self.s.set_policy("asr", hard=False, owner_verified=True)

    def test_background_pause_does_not_cancel_foreground(self):
        self.s.acquire("radio", task_id="recording", owner_id="alice")
        self.s.pause_optional_background(True, owner_verified=True)
        self.assertIn("radio", self.fake.running)
        self.s.release("recording", owner_id="alice")

    def test_start_failure_rolls_back(self):
        self.fake.fail_on = "translator"
        with self.assertRaises(RuntimeError):
            self.s.acquire("captions", task_id="t", owner_id="alice")
        self.assertEqual(self.fake.running, set())
        self.assertEqual(self.s.snapshot()["radio"]["active_tasks"], 0)

    def test_persistence_only_policies_not_grants(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            m1 = ServiceManager([Module("local_ai", installed=True)], Fake(), p)
            m1.set_policy("local_ai", hard=False, owner_verified=True)
            m1.authorize_once(task_id="t", owner_id="alice",
                              scopes={"local_ai"}, owner_verified=True)
            self.assertEqual(json.loads(p.read_text())["policies"]["local_ai"]["hard"], False)
            m2 = ServiceManager([Module("local_ai", installed=True)], Fake(), p)
            self.assertFalse(m2.policies["local_ai"].hard)
            with self.assertRaises(Blocked):
                m2.acquire("local_ai", task_id="t", owner_id="alice")

    def test_missing_install_never_starts(self):
        m = ServiceManager(default_catalog(), Fake())
        with self.assertRaises(Blocked):
            m.acquire("kiwix", task_id="k", owner_id="alice")

    def test_cycle_and_protected_core_rejected(self):
        with self.assertRaises(ValueError):
            ServiceManager([Module("a", ("b",)), Module("b", ("a",))], Fake())
        with self.assertRaises(ValueError):
            ServiceManager([Module("core_hotspot", installed=True)], Fake())

    def test_emergency_not_bypassable_via_general_policy(self):
        with self.assertRaises(Blocked):
            self.s.set_policy("emergency_monitor", hard=True, owner_verified=True)
        with self.assertRaises(Blocked):
            self.s.acquire("emergency_monitor", task_id="e", owner_id="alice")

    def test_startup_enabled_app_may_start_disabled_startup_dependency(self):
        self.s.set_policy("captions", startup=True, owner_verified=True)
        self.s.acquire("captions", task_id="startup-captions",
                       owner_id="system", mode="startup")
        self.assertIn("asr", self.fake.running)
        self.assertFalse(self.s.policies["asr"].startup)
        self.s.release("startup-captions", owner_id="system")

    def test_only_allowlisted_units(self):
        with self.assertRaises(ValueError):
            UserSystemdAdapter({"bad": "NetworkManager.service"})
        with self.assertRaises(ValueError):
            UserSystemdAdapter({"bad": "tihulu-core.service"})


if __name__ == "__main__":
    unittest.main()
