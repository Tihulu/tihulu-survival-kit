"""Mock/fixture-only smoke admission and Stage4 task lifecycle tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest import TestCase, main
from unittest.mock import Mock

from tihulu_runtime import Module, ServiceManager
from tihulu_runtime.app_manager import AppManager
from tihulu_runtime.ai_cpu_smoke import CpuSmokeResult
from tihulu_runtime.ai_smoke_admission import (
    HostObservation, evaluate_smoke_admission, read_linux_host_observation,
)
from tihulu_runtime.ai_smoke_job import CpuSmokeJobCoordinator


GiB = 1024 ** 3


def healthy():
    return HostObservation(8 * GiB, 5 * GiB, 45_000, "synthetic")


def admit(obs=None, **changes):
    opts = dict(stage4_service={"installed": True,
                                "policy": {"hard": True, "background": False,
                                           "startup": False}},
                trusted_job_counts={"protected": 0, "long_ai": 0},
                model_expected_peak_bytes=2 * GiB, owner_confirmed=True,
                power_source_verified=True)
    opts.update(changes)
    return evaluate_smoke_admission(obs or healthy(), **opts)


class AdmissionTests(TestCase):
    def test_safe_foreground_with_background_off(self):
        out = admit()
        self.assertTrue(out.allowed)
        self.assertEqual(out.state, "eligible_for_foreground_lease")
        self.assertTrue(out.measured_memory)
        self.assertTrue(out.measured_temperature)
        self.assertFalse(out.measured_energy)

    def test_no_owner_consent(self):
        self.assertEqual(admit(owner_confirmed=False).state,
                         "owner_consent_required")

    def test_optional_ai_not_installed(self):
        self.assertEqual(admit(stage4_service={}).state,
                         "optional_ai_not_installed")

    def test_stage4_hard_off(self):
        self.assertEqual(admit(stage4_service={"installed": True,
                                               "policy": {"hard": False}}).state,
                         "stage4_hard_off")

    def test_protected_recording_blocks_heavy_ai(self):
        out = admit(trusted_job_counts={"protected": 1, "long_ai": 0})
        self.assertEqual(out.state, "protected_activity_running")
        self.assertEqual(out.protected_jobs, 1)

    def test_ai_concurrency_blocked(self):
        self.assertEqual(admit(trusted_job_counts={"protected": 0, "long_ai": 1}).state,
                         "another_ai_task_running")

    def test_unknown_job_counts_fail_closed(self):
        for counts in (None, {}, {"protected": False, "long_ai": 0},
                       {"protected": -1, "long_ai": 0}):
            self.assertEqual(admit(trusted_job_counts=counts).state,
                             "job_status_unknown")

    def test_temperature_unavailable_fails(self):
        self.assertEqual(admit(HostObservation(8 * GiB, 5 * GiB)).state,
                         "resource_metrics_unavailable")

    def test_ram_unavailable_fails(self):
        self.assertEqual(admit(HostObservation(cpu_temp_millic=44_000)).state,
                         "resource_metrics_unavailable")

    def test_unsafe_psu_or_battery_unknown_fails(self):
        self.assertEqual(admit(power_source_verified=False).state,
                         "power_source_unverified")

    def test_unknown_model_memory_peak_fails(self):
        self.assertEqual(admit(model_expected_peak_bytes=None).state,
                         "model_budget_unverified")
        self.assertEqual(admit(model_expected_peak_bytes=0).state,
                         "model_budget_unverified")

    def test_memory_reserve_and_peak_budget(self):
        self.assertEqual(admit(HostObservation(8 * GiB, 2 * GiB + 700 * 1024**2,
                                              40_000)).state,
                         "insufficient_memory_headroom")

    def test_hot_cpu_blocks(self):
        self.assertEqual(admit(HostObservation(8 * GiB, 5 * GiB, 75_000)).state,
                         "cpu_too_hot")

    def test_inconsistent_memory_metrics(self):
        self.assertEqual(admit(HostObservation(4 * GiB, 5 * GiB, 40_000)).state,
                         "memory_metrics_inconsistent")

    def test_safe_limits_cannot_be_weakened(self):
        self.assertEqual(admit(max_temperature_millic=98_000).state,
                         "unsafe_temperature_limit")
        self.assertEqual(admit(reserve_bytes=0).state,
                         "model_budget_unverified")

    def test_linux_sysfs_sampler_reads_only(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "proc").mkdir()
            (root / "proc/meminfo").write_text(
                "MemTotal: 8000000 kB\nMemAvailable: 3800000 kB\n")
            (root / "sys/class/thermal/thermal_zone0").mkdir(parents=True)
            (root / "sys/class/thermal/thermal_zone0/temp").write_text("42123\n")
            before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            result = read_linux_host_observation(root=root)
            after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(result.memory_available_bytes, 3800000 * 1024)
            self.assertEqual(result.cpu_temp_millic, 42123)

    def test_missing_linux_metrics_are_not_faked(self):
        with TemporaryDirectory() as folder:
            result = read_linux_host_observation(root=folder)
            self.assertIsNone(result.memory_total_bytes)
            self.assertIsNone(result.cpu_temp_millic)


class FakeAdapter:
    def __init__(self):
        self.active = set()
    def start(self, module_id):
        self.active.add(module_id)
    def stop(self, module_id):
        self.active.remove(module_id)


class CoordinatorTests(TestCase):
    def setUp(self):
        self.adapter = FakeAdapter()
        self.services = ServiceManager(
            [Module("local_ai", installed=True), Module("radio", installed=True),
             Module("emergency_monitor", installed=True)], self.adapter)
        self.apps = AppManager(self.services)
        self.smoke = Mock(return_value=CpuSmokeResult(
            "base", "b"*64, "runner-v1", "marker_observed",
            elapsed_seconds=1.0, marker_observed=True))
        self.manager = CpuSmokeJobCoordinator(
            self.apps, resource_sampler=healthy, smoke_executor=self.smoke)

    def run_case(self, **updates):
        data = dict(owner_id="alice", explicit_owner_consent=True,
                    power_source_verified=True, model_expected_peak_bytes=2 * GiB)
        data.update(updates)
        return self.manager.run_once(object(), "base", **data)

    def test_untrusted_cannot_enumerate_global_job_counts(self):
        with self.assertRaises(PermissionError):
            self.apps.trusted_active_job_counts()
        self.assertEqual(self.apps.trusted_active_job_counts(trusted_backend=True)
                         ["protected"], 0)

    def test_job_completed_and_lease_released(self):
        result = self.run_case()
        self.assertEqual(result.state, "finished")
        self.assertEqual(result.job_final_state, "completed")
        self.assertTrue(result.result.passed)
        self.assertFalse(result.cancel_safe_during_execution)
        self.assertEqual(self.services.snapshot()["local_ai"]["active_tasks"], 0)
        self.assertEqual(self.apps.list_jobs(owner_id="alice"), [])
        self.assertEqual(self.apps.list_jobs(owner_id="alice", include_finished=True)[0].state,
                         "completed")
        self.smoke.assert_called_once()

    def test_hard_off_no_job_no_inference(self):
        self.services.set_policy("local_ai", hard=False, owner_verified=True)
        result = self.run_case()
        self.assertEqual(result.admission.state, "stage4_hard_off")
        self.assertIsNone(result.job_id)
        self.smoke.assert_not_called()

    def test_no_consent_never_runs(self):
        out = self.run_case(explicit_owner_consent=False)
        self.assertEqual(out.admission.state, "owner_consent_required")
        self.smoke.assert_not_called()

    def test_protected_radio_recording_blocks_new_test(self):
        rec = self.apps.start_job("radio", owner_id="bob", label="RF",
                                  kind="recording")
        out = self.run_case()
        self.assertEqual(out.admission.state, "protected_activity_running")
        self.smoke.assert_not_called()
        self.apps.executor_ack_finished(rec.id, outcome="completed",
                                        trusted_backend=True)

    def test_atomic_job_creation_denies_new_recording_after_snapshot(self):
        # Simulate a recording arriving AFTER the sampled count but BEFORE
        # the controller starts a heavy AI job. Stage4 must recheck under lock.
        original = self.apps.trusted_active_job_counts
        def stale_sample(*, trusted_backend=False):
            recording = self.apps.start_job("radio", owner_id="bob",
                                            label="Started during AI admission",
                                            kind="recording")
            self.addCleanup(lambda: self.apps.executor_ack_finished(
                recording.id, outcome="completed", trusted_backend=True))
            return {"protected": 0, "long_ai": 0, "all_active": 0}
        self.apps.trusted_active_job_counts = stale_sample
        try:
            out = self.run_case()
        finally:
            self.apps.trusted_active_job_counts = original
        self.assertEqual(out.state, "stage4_acquire_denied")
        self.smoke.assert_not_called()

    def test_cancel_requested_recording_still_blocks(self):
        rec = self.apps.start_job("radio", owner_id="bob", label="RF",
                                  kind="recording")
        self.apps.request_cancel(rec.id, owner_id="bob", recording_confirmed=True)
        self.assertEqual(self.run_case().admission.state, "protected_activity_running")
        self.apps.executor_ack_finished(rec.id, outcome="cancelled",
                                        trusted_backend=True)

    def test_other_users_ai_blocks_without_revealing_identity(self):
        ai = self.apps.start_job("local_ai", owner_id="bob", label="Long",
                                 kind="long_ai")
        self.assertEqual(self.run_case().admission.state, "another_ai_task_running")
        self.assertEqual(self.apps.trusted_active_job_counts(
            trusted_backend=True)["long_ai"], 1)
        self.apps.executor_ack_finished(ai.id, outcome="completed", trusted_backend=True)

    def test_missing_power_verification_blocks(self):
        self.assertEqual(self.run_case(power_source_verified=False).admission.state,
                         "power_source_unverified")
        self.smoke.assert_not_called()

    def test_inference_failure_still_releases_lease(self):
        self.smoke.return_value = CpuSmokeResult("base", "b"*64, "v1", "runner_failed")
        out = self.run_case()
        self.assertEqual(out.job_final_state, "failed")
        self.assertEqual(self.services.snapshot()["local_ai"]["active_tasks"], 0)

    def test_executor_exception_still_releases_lease(self):
        self.smoke.side_effect = RuntimeError("fake")
        out = self.run_case()
        self.assertEqual(out.state, "executor_error")
        self.assertEqual(out.job_final_state, "failed")
        self.assertEqual(self.services.snapshot()["local_ai"]["active_tasks"], 0)

    def test_cancel_requested_is_not_falsely_reported_executed_cancel(self):
        def finish_after_cancel(*args, **kwargs):
            job = self.apps.list_jobs(owner_id="alice")[0]
            self.apps.request_cancel(job.id, owner_id="alice")
            return CpuSmokeResult("base", "b"*64, "v1", "marker_observed",
                                  marker_observed=True)
        self.smoke.side_effect = finish_after_cancel
        out = self.run_case()
        self.assertEqual(out.job_final_state, "completed")
        self.assertFalse(out.cancel_safe_during_execution)
        self.assertEqual(self.services.snapshot()["local_ai"]["active_tasks"], 0)

    def test_coordinator_lock_serializes_self(self):
        self.assertTrue(self.manager._lock.acquire(blocking=False))
        try:
            out = self.run_case()
            self.assertEqual(out.state, "coordinator_busy")
            self.smoke.assert_not_called()
        finally:
            self.manager._lock.release()


    def test_owner_cancel_ack_after_worker_termination(self):
        entered = Event()
        def fake_cancelled(*args, cancel_event, **kwargs):
            entered.set()
            self.assertTrue(cancel_event.wait(timeout=2))
            return CpuSmokeResult("base", "b"*64, "v1", "cancelled")
        self.manager.smoke_executor = fake_cancelled
        results = []
        thread = Thread(target=lambda: results.append(self.run_case()))
        thread.start()
        try:
            self.assertTrue(entered.wait(timeout=2))
            job = self.apps.list_jobs(owner_id="alice")[0]
            with self.assertRaises(PermissionError):
                self.manager.request_cancel(job.id, owner_id="bob")
            self.manager.request_cancel(job.id, owner_id="alice")
        finally:
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0].job_final_state, "cancelled")
        self.assertTrue(results[0].cancel_safe_during_execution)
        self.assertEqual(self.services.snapshot()["local_ai"]["active_tasks"], 0)

    def test_unconfirmed_process_termination_keeps_service_lease(self):
        self.smoke.return_value = CpuSmokeResult(
            "base", "b"*64, "v1", "termination_unconfirmed")
        out = self.run_case()
        self.assertEqual(out.state, "termination_unconfirmed")
        self.assertIsNone(out.job_final_state)
        self.assertEqual(self.services.snapshot()["local_ai"]["active_tasks"], 1)
        self.assertEqual(self.apps.list_jobs(owner_id="alice")[0].state, "running")


if __name__ == "__main__":
    main()
