"""Authenticated-backend *core* for managing views and server jobs.

Not a public API: no HTTP auth, real process supervisor or live Pi services here.
Closing a tab releases only its view lease. Jobs are server-owned, not tab-owned.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock
from typing import Callable
import secrets
import time

from .service_manager import ServiceManager, Busy


@dataclass(frozen=True)
class AppView:
    id: str
    app_id: str
    owner_id: str
    device_id: str
    opened_at: float
    heartbeat_at: float


@dataclass(frozen=True)
class ServerJob:
    id: str
    app_id: str
    owner_id: str
    label: str
    kind: str
    state: str
    started_at: float
    cancel_requested_at: float | None = None


class AppManager:
    """Window-like per-device sessions plus durable server-job registry.

    Only a trusted, authenticated server should call this class. A real executor
    must implement cancellation, persistence and safe recording finalization.
    """

    def __init__(self, services: ServiceManager,
                 clock: Callable[[], float] = time.monotonic):
        self.services = services
        self.clock = clock
        self._lock = RLock()
        self._views: dict[str, AppView] = {}
        self._jobs: dict[str, ServerJob] = {}

    def open_app(self, app_id: str, *, owner_id: str, device_id: str) -> AppView:
        if not owner_id or not device_id:
            raise ValueError("Authenticated user and device required")
        with self._lock:
            view_id = secrets.token_urlsafe(18)
            self.services.acquire(app_id, task_id="view:" + view_id,
                                  owner_id=owner_id, mode="foreground")
            now = self.clock()
            view = AppView(view_id, app_id, owner_id, device_id, now, now)
            self._views[view_id] = view
            return view

    def heartbeat(self, view_id: str, *, owner_id: str) -> None:
        with self._lock:
            view = self._owned_view(view_id, owner_id)
            self._views[view_id] = replace(view, heartbeat_at=self.clock())

    def _owned_view(self, view_id: str, owner_id: str) -> AppView:
        view = self._views[view_id]
        if view.owner_id != owner_id:
            raise PermissionError("Cannot manage another user's app window")
        return view

    def close_app(self, view_id: str, *, owner_id: str) -> None:
        """Close one view, NOT all server jobs nor another device's tabs."""
        with self._lock:
            self._owned_view(view_id, owner_id)
            self.services.release("view:" + view_id, owner_id=owner_id)
            del self._views[view_id]

    def sweep_disconnected_views(self, *, timeout_seconds: float = 120) -> list[str]:
        """Release abandoned passive views; never cancel durable jobs.

        Should be triggered by a short cleanup timer. Heartbeats may be
        suspended on iOS; a view might need to re-open on resume.
        """
        if timeout_seconds <= 0:
            raise ValueError("Positive timeout required")
        with self._lock:
            stale = [v for v in self._views.values()
                     if self.clock() - v.heartbeat_at >= timeout_seconds]
            for view in stale:
                self.close_app(view.id, owner_id=view.owner_id)
            return [v.id for v in stale]

    def start_job(self, app_id: str, *, owner_id: str, label: str,
                  kind: str = "normal", mode: str = "foreground") -> ServerJob:
        if kind not in ("normal", "recording", "file_transfer", "long_ai",
                        "import", "navigation"):
            raise ValueError("Unknown job kind")
        if not owner_id or not label:
            raise ValueError("User and job label required")
        with self._lock:
            job_id = secrets.token_urlsafe(18)
            self.services.acquire(app_id, task_id="job:" + job_id,
                                  owner_id=owner_id, mode=mode)
            job = ServerJob(job_id, app_id, owner_id, label, kind,
                            "running", self.clock())
            self._jobs[job_id] = job
            return job

    def _owned_job(self, job_id: str, owner_id: str) -> ServerJob:
        job = self._jobs[job_id]
        if job.owner_id != owner_id:
            raise PermissionError("Cannot access another user's job")
        return job

    def request_cancel(self, job_id: str, *, owner_id: str,
                       recording_confirmed: bool = False) -> ServerJob:
        """Request, do not claim, cancellation. Executor must acknowledge.

        A radio/emergency recording may contain unique original content: never
        silently truncate or delete it. Safe flush is the executor's job.
        """
        with self._lock:
            job = self._owned_job(job_id, owner_id)
            if job.kind == "recording" and not recording_confirmed:
                raise Busy("Recording active: explicit stop and safe-save required")
            if job.state != "running":
                raise Busy("Job not currently running")
            updated = replace(job, state="cancel_requested",
                              cancel_requested_at=self.clock())
            self._jobs[job_id] = updated
            return updated

    def executor_ack_finished(self, job_id: str, *, outcome: str,
                              trusted_backend: bool = False) -> ServerJob:
        """Only a real server executor may report stopped/completed/failed."""
        if not trusted_backend:
            raise PermissionError("Executor authorization required")
        if outcome not in ("completed", "cancelled", "failed"):
            raise ValueError("Invalid final job state")
        with self._lock:
            job = self._jobs[job_id]
            if job.state not in ("running", "cancel_requested"):
                raise Busy("Job already finalized")
            self.services.release("job:" + job_id, owner_id=job.owner_id)
            updated = replace(job, state=outcome)
            self._jobs[job_id] = updated
            return updated

    def list_views(self, *, owner_id: str) -> list[AppView]:
        with self._lock:
            return [v for v in self._views.values() if v.owner_id == owner_id]

    def list_jobs(self, *, owner_id: str, include_finished: bool = False) -> list[ServerJob]:
        with self._lock:
            return [j for j in self._jobs.values() if j.owner_id == owner_id
                    and (include_finished or j.state in ("running", "cancel_requested"))]

    def trusted_active_job_counts(self, *, trusted_backend: bool = False) -> dict[str, int]:
        """Return privacy-preserving aggregate admission information.

        Only trusted server schedulers may see these cross-owner counts.
        A cancel_requested recording is still protected until executor ACK.
        This is a snapshot, not an atomic lock against future new jobs.
        """
        if not trusted_backend:
            raise PermissionError("Trusted backend required for global job counts")
        with self._lock:
            active = [j for j in self._jobs.values()
                      if j.state in ("running", "cancel_requested")]
            protected = sum(j.kind == "recording" or
                            j.app_id in ("emergency_monitor", "emergency_center")
                            for j in active)
            return {
                "protected": protected,
                "long_ai": sum(j.kind == "long_ai" for j in active),
                "all_active": len(active),
            }

    def overview(self, *, owner_id: str) -> dict:
        """No invented RAM: actual runtime comes from adapter metrics later."""
        with self._lock:
            owned_views = self.list_views(owner_id=owner_id)
            owned_jobs = self.list_jobs(owner_id=owner_id)
            return {
                "views": [vars(v) for v in owned_views],
                "jobs": [vars(j) for j in owned_jobs],
                "services": self.services.snapshot(),
                "actual_memory_metrics": None,
                "backend_integrated": False,
            }
