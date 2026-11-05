# Stage 4 / Stage 5 — CPU Base smoke resource admission and supervised cancellation

**Status 2026-11-05:** Experimental, library-only integration on public Draft PR #1. Not a deployed Pi daemon, authenticated web endpoint or proven complete resource/energy supervisor. No real GGUF or Raspberry Pi hardware has been tested by this change. Newly added synthetic tests are committed but a full passing GitHub Actions run is not yet verified.

## Why this is different from the manual CPU smoke CLI

The earlier `ai_setup --run-base-cpu-smoke` is a **manual operator diagnostic**: its `--smoke-service-allowed` and `--smoke-resource-budget-ok` flags are operator claims, not live measurements, and this CLI still takes the older timeout-bounded subprocess path **without live UI cancellation**.

The new **backend-only** `CpuSmokeJobCoordinator` links `AppManager`, `ServiceManager`, a read-only Linux memory/temperature sampler and `cpu_smoke_test(..., cancel_event=...)` to create a **foreground Stage 4 `long_ai` server job**. It is **not yet exposed through an HTTP API or production setup wizard**. This avoids pretending that an HTML checkbox is sufficient to grant a task or a working hardware/runtime.

## Exact admission contract

`ai_smoke_admission.read_linux_host_observation` only reads `/proc/meminfo` (`MemTotal`, `MemAvailable`) and `/sys/class/thermal/thermal_zone0/temp`; missing inputs stay Unknown. It never measures watts, PSU draw, battery capacity or remaining Joules.

`evaluate_smoke_admission` requires all of:
- An authenticated, explicitly consenting owner (the caller is responsible for authentication).
- `local_ai` installed and Hard ON in Stage 4 service snapshot; background/startup may remain OFF because this is an owner-launched foreground test.
- A **trusted cross-owner aggregate** of active server jobs with no recording/emergency job and no other running/stop-pending `long_ai` job. Another owner's identity and private job labels are not exposed.
- Measured host memory and temperature. Trusted model peak-RAM estimate must leave **at least 768 MiB** usable after expected model consumption; the observed CPU temperature must be below **75 °C**. These conservative thresholds are experimental, not tested Pi5 safety guarantees.
- A separately verified power-source/PSU/battery headroom acknowledgment from a **trusted** hardware adapter; the current library cannot independently measure wattage. If absent/unknown, admission is denied. No energy savings are claimed.
- A fresh Stage 4 job lease at start. The AppManager additionally rechecks active protected/heavy tasks atomically under its job lock to reduce the snapshot-to-start race. **A new protected recording starting *after* an AI job has begun is not yet guaranteed to preempt it.** A future shared system-wide scheduler must implement priority/preemption and real cross-process quotas.

Denied admission returns a reason without creating a server job or opening model files. The class uses a **single coordinator-local mutex**, not a distributed Pi-wide lock. It must be instantiated as a singleton by a trusted server and only used through an authenticated endpoint.

## Cancellation and process lifetime

For coordinator-driven tests the CPU subprocess is started in a separate Linux session/group. An owner request via `CpuSmokeJobCoordinator.request_cancel(job_id, owner_id)` moves the AppManager job to `cancel_requested` and signals the Event to the active runner. The runner:
- uses a fixed CPU-only/offline `llama-cli` command and previously verified GGUF;
- reads at most **8 KiB** of stdout into volatile memory; stderr is discarded; no raw generated text is persisted;
- polls cancellation and the wall timeout, requests process-group SIGTERM, then SIGKILL on an unresponsive direct child, waiting for the child to terminate;
- reports `cancelled` only after the direct child is reaped. A failed termination attempt is `termination_unconfirmed`, not `cancelled`;
- marks the task `completed` only if the diagnostic finishes successfully, `failed` for errors, or `cancelled` on acknowledged termination. Only the trusted executor acknowledges the final job and releases the Stage 4 lease;
- keeps the lease/job unresolved if process termination is **not confirmed**, pending privileged/manual recovery, instead of falsely claiming a free worker.

The subprocess **version probe** remains a bounded `subprocess.run` and the SHA256 verification might read multiple gigabytes before cancellation takes effect; cancellation responsiveness **during file hash is not yet guaranteed**. Process-group signals alone cannot prove every descendant that deliberately escaped the process group has stopped; full production enforcement needs a systemd scope/cgroup, memory and CPU quotas, artifact limits and a watchdog. No live PCIe HAT changes are authorized.

## Source files and tests

- [Trusted aggregate counts, Stage4 jobs and view leases](../../tihulu_runtime/app_manager.py)
- [Read-only host metrics and deny-by-default admission](../../tihulu_runtime/ai_smoke_admission.py)
- [Stage4 job coordinator and owner cancellation](../../tihulu_runtime/ai_smoke_job.py)
- [Supervised, bounded CPU subprocess](../../tihulu_runtime/ai_cpu_smoke.py)
- [32 new mocked/fixture admission and coordinator tests](../../tests/test_ai_smoke_admission.py)
- [22 CPU smoke tests including 5 new cancellation/timeout/output-cap cases](../../tests/test_ai_cpu_smoke.py)
- [Existing AppManager tests](../../tests/test_app_manager.py)

To run from a developer checkout:

```bash
python3 -m unittest tests.test_ai_smoke_admission tests.test_ai_cpu_smoke tests.test_app_manager -v
python3 -m unittest discover -s tests -v
```

**Test files have been committed; a passing full-suite/CI result is not yet confirmed**. Tests involving fake `llama-cli` scripts are *not* actual model inference. The terminal command from Checkpoint069 does not automatically use the coordinator.

## Next production gates

1. Confirm successful Python 3.11/3.12 GitHub Actions tests with logs, address any process-race failure, and measure RAM/temperature under physical Pi5 load.
2. Bind a **trusted live power-supply/battery source** to the admission. Do not trust browser `power_source_verified=true` or infer joules from voltage or NPU TOPS.
3. Replace coordinator-local singleton with a **shared durable job scheduler** that atomically prioritizes new Emergency/TV/Radio recording requests, preempts optional heavy AI when required, and works across multiple users/processes.
4. Run CPU model execution in a real systemd scope/cgroup with memory, CPU and log/output limits, process cancellation acknowledgment and crash/reboot recovery, including during checksum verification.
5. Connect the owner-authenticated wizard/Task Center with explicit consent, status and error states. Ensure source indexes on external SSD are not implicitly opened, copied or erased by this diagnostic.
6. Verify approved real Base GGUF and llama.cpp on Pi5, HAT/no-HAT physical boot layouts after power-off, and real energy/performance metrics. No unverified auto-remote fallback.

**Stage statuses unchanged:** Stages 1–4 design approved, Stage 5–9 whole-stage review pending, Stage 10 pending; this draft code is not a released Pi installer.
