"""Task/window semantics: no real Pi/systemd, no fake RAM measurements."""
import unittest

from tihulu_runtime import Module, ServiceManager
from tihulu_runtime.app_manager import AppManager
from tihulu_runtime.service_manager import Busy


class Fake:
    def __init__(self):
        self.running = set()
        self.starts = []
        self.stops = []

    def start(self, app):
        self.running.add(app)
        self.starts.append(app)

    def stop(self, app):
        self.running.remove(app)
        self.stops.append(app)


class WindowAndJobTests(unittest.TestCase):
    def setUp(self):
        self.clock_value = 100.0
        self.adapter = Fake()
        self.services = ServiceManager(
            [Module("news", installed=True),
             Module("radio", installed=True),
             Module("local_ai", installed=True)], self.adapter,
            clock=lambda: self.clock_value)
        self.windows = AppManager(self.services, clock=lambda: self.clock_value)

    def test_two_tabs_shared_worker_only_starts_once(self):
        a = self.windows.open_app("news", owner_id="alice", device_id="phone")
        b = self.windows.open_app("news", owner_id="alice", device_id="desktop")
        self.assertEqual(self.adapter.starts, ["news"])
        self.windows.close_app(a.id, owner_id="alice")
        self.services.sweep_idle()
        self.assertIn("news", self.adapter.running)
        self.windows.close_app(b.id, owner_id="alice")
        self.services.sweep_idle()
        self.assertNotIn("news", self.adapter.running)

    def test_recording_survives_tab_switch_and_window_close(self):
        view = self.windows.open_app("radio", owner_id="alice", device_id="phone")
        recording = self.windows.start_job("radio", owner_id="alice",
                                           label="Original signal", kind="recording")
        self.windows.close_app(view.id, owner_id="alice")
        self.services.sweep_idle()
        self.assertIn("radio", self.adapter.running)
        self.assertEqual(self.windows.list_jobs(owner_id="alice")[0].state, "running")
        with self.assertRaises(Busy):
            self.windows.request_cancel(recording.id, owner_id="alice")
        self.windows.request_cancel(recording.id, owner_id="alice",
                                    recording_confirmed=True)
        self.assertIn("radio", self.adapter.running)
        self.windows.executor_ack_finished(recording.id, outcome="cancelled",
                                           trusted_backend=True)
        self.services.sweep_idle()
        self.assertNotIn("radio", self.adapter.running)

    def test_request_cancel_not_claim_execution_finished(self):
        job = self.windows.start_job("local_ai", owner_id="alice",
                                     label="Long AI analysis", kind="long_ai")
        result = self.windows.request_cancel(job.id, owner_id="alice")
        self.assertEqual(result.state, "cancel_requested")
        self.assertIn("local_ai", self.adapter.running)
        with self.assertRaises(PermissionError):
            self.windows.executor_ack_finished(job.id, outcome="cancelled")
        self.windows.executor_ack_finished(job.id, outcome="cancelled",
                                           trusted_backend=True)
        self.services.sweep_idle()
        self.assertNotIn("local_ai", self.adapter.running)

    def test_guest_cannot_see_or_close_owners_windows(self):
        v = self.windows.open_app("news", owner_id="alice", device_id="phone")
        self.assertEqual(self.windows.list_views(owner_id="bob"), [])
        with self.assertRaises(PermissionError):
            self.windows.close_app(v.id, owner_id="bob")
        job = self.windows.start_job("news", owner_id="alice",
                                     label="Refresh sources")
        with self.assertRaises(PermissionError):
            self.windows.request_cancel(job.id, owner_id="bob")
        self.assertEqual(self.windows.list_jobs(owner_id="bob"), [])

    def test_stale_view_cleanup_never_cancels_server_job(self):
        v = self.windows.open_app("radio", owner_id="alice", device_id="phone")
        job = self.windows.start_job("radio", owner_id="alice",
                                     label="Scheduled recording", kind="recording")
        self.clock_value += 150
        self.assertEqual(self.windows.sweep_disconnected_views(), [v.id])
        self.services.sweep_idle()
        self.assertIn("radio", self.adapter.running)
        self.assertEqual(self.windows.list_jobs(owner_id="alice")[0].id, job.id)

    def test_running_job_not_stopped_by_background_off(self):
        v = self.windows.open_app("local_ai", owner_id="alice", device_id="phone")
        job = self.windows.start_job("local_ai", owner_id="alice",
                                     label="Document RAG", kind="long_ai")
        self.windows.close_app(v.id, owner_id="alice")
        self.services.sweep_idle()
        self.assertIn("local_ai", self.adapter.running)
        self.windows.executor_ack_finished(job.id, outcome="completed",
                                           trusted_backend=True)
        self.services.sweep_idle()
        self.assertFalse(self.adapter.running)

    def test_app_hard_off_does_not_allow_view(self):
        self.services.set_policy("news", hard=False, owner_verified=True)
        with self.assertRaises(Exception):
            self.windows.open_app("news", owner_id="alice", device_id="phone")


if __name__ == "__main__":
    unittest.main()
