# SPDX-License-Identifier: AGPL-3.0-only
"""Fail-closed resource admission for opt-in CPU Base smoke tests.

This is a trusted-backend policy helper, NOT a Pi daemon or power meter.
It does not start jobs, grant file access, override Stage4 or change disks.
A future authenticated executor must sample resources and enforce a cgroup,
verify the power source, and recheck concurrency immediately at admission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

MiB = 1024 * 1024
MIN_RESERVE_BYTES = 768 * MiB
DEFAULT_THERMAL_LIMIT_MILLIC = 75_000


@dataclass(frozen=True)
class HostObservation:
    memory_total_bytes: int | None = None
    memory_available_bytes: int | None = None
    cpu_temp_millic: int | None = None
    source: str = "unknown"

    def __post_init__(self) -> None:
        if (self.memory_total_bytes is not None and self.memory_total_bytes < 0 or
            self.memory_available_bytes is not None and self.memory_available_bytes < 0 or
            self.cpu_temp_millic is not None and self.cpu_temp_millic < 0):
            raise ValueError("Invalid hardware observation")


@dataclass(frozen=True)
class SmokeAdmission:
    allowed: bool
    state: str
    measured_memory: bool
    measured_temperature: bool
    measured_energy: bool = False
    protected_jobs: int = 0
    other_ai_jobs: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def read_linux_host_observation(*, root: str | Path = "/") -> HostObservation:
    """Read the CURRENT host, without privileged commands or writes.

    A supplied root is for deterministic tests. Report missing metrics as None,
    never a fabricated temperature, memory or battery/watt reading.
    """
    root = Path(root)
    try:
        data = (root / "proc/meminfo").read_text(encoding="ascii", errors="replace")
    except OSError:
        data = ""
    def mem(key: str) -> int | None:
        found = re.search(rf"^{key}:\s*(\d+)\s+kB\s*$", data, re.M)
        return int(found.group(1)) * 1024 if found else None
    try:
        temp = int((root / "sys/class/thermal/thermal_zone0/temp").read_text().strip())
    except (OSError, ValueError):
        temp = None
    return HostObservation(mem("MemTotal"), mem("MemAvailable"), temp,
                           "linux_proc_sysfs" if data or temp is not None else "unavailable")


def evaluate_smoke_admission(observation: HostObservation, *,
                             stage4_service: dict | None,
                             trusted_job_counts: dict | None,
                             model_expected_peak_bytes: int | None,
                             owner_confirmed: bool = False,
                             power_source_verified: bool = False,
                             max_temperature_millic: int = DEFAULT_THERMAL_LIMIT_MILLIC,
                             reserve_bytes: int = MIN_RESERVE_BYTES) -> SmokeAdmission:
    """Allow ONLY a foreground, single-client, already-installed CPU smoke.

    No user-provided values should be treated as trusted sensor readings.
    `power_source_verified` is NOT watt measurement: it needs a separate
    hardware/PSU confirmation adapter. Do not label energy 'measured'.
    """
    # A missing or incomplete scheduler snapshot is never proof that no
    # protected recording/AI task exists. Do not silently assume zero.
    jobs_valid = (isinstance(trusted_job_counts, dict) and
                  {"protected", "long_ai"}.issubset(trusted_job_counts))
    jobs = trusted_job_counts if jobs_valid else {}
    protected = jobs.get("protected", -1)
    other_ai = jobs.get("long_ai", -1)
    measured_memory = (observation.memory_total_bytes is not None and
                       observation.memory_available_bytes is not None)
    measured_temperature = observation.cpu_temp_millic is not None
    def verdict(reason: str) -> SmokeAdmission:
        return SmokeAdmission(False, reason, measured_memory,
                              measured_temperature, protected_jobs=protected
                              if type(protected) is int and protected >= 0 else 0,
                              other_ai_jobs=other_ai
                              if type(other_ai) is int and other_ai >= 0 else 0)
    if owner_confirmed is not True:
        return verdict("owner_consent_required")
    if not isinstance(stage4_service, dict) or not stage4_service.get("installed"):
        return verdict("optional_ai_not_installed")
    pol = stage4_service.get("policy")
    if not isinstance(pol, dict) or pol.get("hard") is not True:
        return verdict("stage4_hard_off")
    # Background/Startup OFF are compatible with an explicit foreground test.
    if (type(protected) is not int or protected < 0 or
            type(other_ai) is not int or other_ai < 0):
        return verdict("job_status_unknown")
    if protected:
        return verdict("protected_activity_running")
    if other_ai:
        return verdict("another_ai_task_running")
    if not measured_memory or not measured_temperature:
        return verdict("resource_metrics_unavailable")
    if power_source_verified is not True:
        return verdict("power_source_unverified")
    if (type(model_expected_peak_bytes) is not int or model_expected_peak_bytes <= 0 or
            type(reserve_bytes) is not int or reserve_bytes < MIN_RESERVE_BYTES):
        return verdict("model_budget_unverified")
    if (type(max_temperature_millic) is not int or
            not 40_000 <= max_temperature_millic <= DEFAULT_THERMAL_LIMIT_MILLIC):
        return verdict("unsafe_temperature_limit")
    if observation.cpu_temp_millic >= max_temperature_millic:
        return verdict("cpu_too_hot")
    if observation.memory_available_bytes > observation.memory_total_bytes:
        return verdict("memory_metrics_inconsistent")
    if observation.memory_available_bytes - model_expected_peak_bytes < reserve_bytes:
        return verdict("insufficient_memory_headroom")
    return SmokeAdmission(True, "eligible_for_foreground_lease",
                          True, True, measured_energy=False,
                          protected_jobs=0, other_ai_jobs=0)
