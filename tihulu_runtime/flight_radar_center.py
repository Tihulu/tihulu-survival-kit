# SPDX-License-Identifier: AGPL-3.0-only
"""On-demand Flight Radar sessions over Stage4 and shared SDR leases.

Do not start/kill system readsb or open real USB hardware from this prototype.
A device adapter must attest physical ownership of an RTL-SDR before a
production user-facing Start Receiver action may be enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable
import secrets
import time

from .flight_radar_sources import AircraftSourceManager, MODES
from .sdr_resource_broker import SDRResourceBroker, ReceiverBusy, TunerLease
from .service_manager import ServiceManager, Blocked, Busy


@dataclass(frozen=True)
class RadarSession:
    id: str
    owner_id: str
    device_id: str
    mode: str
    service_task_id: str
    tuner_lease: TunerLease | None
    started_utc: float
    online_allowed: bool


class FlightRadarCenter:
    """Trusted coordinator; authorization must happen BEFORE calling methods."""

    def __init__(self, services: ServiceManager, broker: SDRResourceBroker,
                 sources: AircraftSourceManager, *,
                 receiver_id: str = "rtl-sdr-0",
                 receiver_available: Callable[[], bool] = lambda: False,
                 clock=time.time):
        self.services, self.broker, self.sources = services, broker, sources
        self.receiver_id, self.receiver_available = receiver_id, receiver_available
        self.clock = clock
        self._lock = RLock()
        self._sessions: dict[str, RadarSession] = {}

    def open_session(self, *, owner_id: str, device_id: str,
                     mode: str = "antenna", online_allowed: bool = False,
                     explicit_owner_permission: bool = False) -> RadarSession:
        if not owner_id or not device_id or not explicit_owner_permission:
            raise PermissionError("Authenticated owner and receiver permission required.")
        if mode not in MODES:
            raise ValueError("Invalid Flight Radar source mode.")
        with self._lock:
            task = "flight:" + secrets.token_urlsafe(16)
            self.services.acquire("flight_radar", task_id=task, owner_id=owner_id)
            lease = None
            try:
                wants_antenna = mode in ("antenna", "hybrid", "automatic")
                if wants_antenna and self.receiver_available():
                    # A second subscribed client may read the SAME 1090 MHz
                    # stream without independently retuning physical hardware.
                    try:
                        lease = self.broker.acquire(
                            self.receiver_id, app_id="flight_radar",
                            owner_id=owner_id, purpose="adsb_1090",
                            explicit_permission=True, share_stream=True)
                    except ReceiverBusy:
                        if not (mode in ("hybrid", "automatic") and online_allowed):
                            raise
                        # Online data may continue while FM/DAB/RTL433 owns SDR.
                sid = secrets.token_urlsafe(24)
                session = RadarSession(sid, owner_id, device_id, mode,
                                       task, lease, self.clock(), online_allowed)
                self._sessions[sid] = session
                return session
            except BaseException:
                if lease is not None:
                    self.broker.release(lease.token, owner_id=owner_id)
                self.services.release(task, owner_id=owner_id)
                raise

    def get_session(self, session_id: str, *, owner_id: str) -> RadarSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError("Session no longer exists.")
            if session.owner_id != owner_id:
                raise PermissionError("Only owning users may read Flight Radar sessions.")
            return session

    def snapshot(self, session_id: str, *, owner_id: str) -> dict:
        session = self.get_session(session_id, owner_id=owner_id)
        # Live source availability from trusted installed hardware, not
        # a user-agent hint or a database entry claiming a USB dongle exists.
        local_permitted = (session.tuner_lease is not None and
                           self.receiver_available())
        result = self.sources.snapshot(mode=session.mode,
                                       online_allowed=session.online_allowed,
                                       local_allowed=local_permitted)
        result["receiver"] = self.broker.active(self.receiver_id)
        result["session_id"] = session.id
        result["receiver_ready"] = bool(local_permitted)
        result["physical_receiver_control_installed"] = False
        return result

    def stop_session(self, session_id: str, *, owner_id: str) -> bool:
        """Only the owner's view lease ends; other subscribed clients survive."""
        with self._lock:
            session = self.get_session(session_id, owner_id=owner_id)
            if session.tuner_lease:
                self.broker.release(session.tuner_lease.token, owner_id=owner_id)
            self.services.release(session.service_task_id, owner_id=owner_id)
            del self._sessions[session_id]
            self.services.sweep_idle()
            return True

    def status(self, *, owner_id: str) -> dict:
        if not owner_id:
            raise PermissionError("Authentication required.")
        with self._lock:
            user_sessions = sum(x.owner_id == owner_id for x in self._sessions.values())
            return {
                "module_id": "flight_radar",
                "stage": "experimental",
                "active_owner_sessions": user_sessions,
                "receiver": self.broker.active(self.receiver_id),
                "physical_receiver_control_installed": False,
                "background_default": False,
                "startup_default": False,
                "supports_cpu_base": True,
                "ai_required": False,
            }
