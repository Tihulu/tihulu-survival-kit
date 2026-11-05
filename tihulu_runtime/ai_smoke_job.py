# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental Stage4 lease wrapper for the optional Base CPU smoke.

Trusted server use only: not a public HTTP endpoint or real Pi supervisor.
Does NOT promise live process cancellation or atomic preemption of a newly
started recording. Those remain release blockers until an async executor,
process-group termination and shared resource scheduler exist.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import Lock
from typing import Callable

from .ai_cpu_smoke import CpuSmokeResult, cpu_smoke_test
from .ai_smoke_admission import (
    HostObservation, SmokeAdmission, evaluate_smoke_admission,
    read_linux_host_observation,
)
from .app_manager import AppManager
from .service_manager import Blocked, Busy


@dataclass(frozen=True)
class SmokeJobAttempt:
    state: str
    admission: SmokeAdmission
    job_id: str | None = None
    result: CpuSmokeResult | None = None
    job_final_state: str | None = None
    cancel_safe_during_execution: bool = False
    power_energy_measured: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


class CpuSmokeJobCoordinator:
    """Synchronous foreground task with resource admission + Stage4 lease.

    A shared coordinator serializes its own calls, but is NOT a global
    multi-process lock. A trusted backend must ensure a SINGLE scheduler for
    all optional heavy AI on the Pi before exposing this to users.
    """

    def __init__(self, apps: AppManager, *,
                 resource_sampler: Callable[[], HostObservation] =
                 read_linux_host_observation,
                 smoke_executor: Callable[..., CpuSmokeResult] = cpu_smoke_test):
        self.apps = apps
        self.resource_sampler = resource_sampler
        self.smoke_executor = smoke_executor
        self._lock = Lock()

    def run_once(self, registry: object, model_id: str, *, owner_id: str,
                 explicit_owner_consent: bool = False,
                 power_source_verified: bool = False,
                 model_expected_peak_bytes: int | None = None,
                 runner: str | None = None,
                 timeout_seconds: int = 90,
                 threads: int = 2) -> SmokeJobAttempt:
        """Only foreground; no automatic background/startup invocation.

        Caller-supplied booleans must come from trusted authorization/hardware
        adapters, not unauthenticated web requests. A platform-specific cgroup
        and cancellable process executor are REQUIRED for production.
        """
        if not owner_id:
            raise ValueError("Authenticated owner required")
        if not self._lock.acquire(blocking=False):
            return SmokeJobAttempt(
                "coordinator_busy",
                SmokeAdmission(False, "coordinator_busy", False, False))
        try:
            sample = self.resource_sampler()
            services = self.apps.services.snapshot()
            counts = self.apps.trusted_active_job_counts(trusted_backend=True)
            admission = evaluate_smoke_admission(
                sample,
                stage4_service=services.get("local_ai"),
                trusted_job_counts=counts,
                model_expected_peak_bytes=model_expected_peak_bytes,
                owner_confirmed=explicit_owner_consent,
                power_source_verified=power_source_verified,
            )
            if not admission.allowed:
                return SmokeJobAttempt("denied", admission)
            try:
                job = self.apps.start_job(
                    "local_ai", owner_id=owner_id,
                    label="Owner-authorized Base CPU smoke",
                    kind="long_ai", mode="foreground")
            except (Busy, Blocked, KeyError):
                return SmokeJobAttempt("stage4_acquire_denied", admission)
            try:
                smoke = self.smoke_executor(
                    registry, model_id, explicit_owner_consent=True,
                    service_allowed=True, resource_budget_allowed=True,
                    runner=runner, timeout_seconds=timeout_seconds,
                    threads=threads)
                # Completed means the *diagnostic ran*, not that the LLM passed.
                # A user cancellation request is not falsely marked cancelled
                # without a real subprocess termination acknowledgement.
                final = "completed" if smoke.passed else "failed"
                self.apps.executor_ack_finished(
                    job.id, outcome=final, trusted_backend=True)
                return SmokeJobAttempt("finished", admission, job.id,
                                       smoke, final)
            except Exception:
                self.apps.executor_ack_finished(
                    job.id, outcome="failed", trusted_backend=True)
                return SmokeJobAttempt("executor_error", admission, job.id,
                                       job_final_state="failed")
        finally:
            self._lock.release()
