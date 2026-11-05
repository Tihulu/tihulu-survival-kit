# SPDX-License-Identifier: AGPL-3.0-only
"""Receive-only SDR lease broker shared by Radio, RTL-433 and Flight Radar.

This is an IN-PROCESS arbitration library, not a physical USB daemon. Only
trusted authenticated service code may call it. The same singleton instance
must be passed to all consumers; cross-process flock/systemd integration is
a required deployment gate. No process or recording is killed for a switch.
"""
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
import secrets


class ReceiverBusy(RuntimeError):
    def __init__(self, receiver_id: str, active_app: str):
        self.receiver_id, self.active_app = receiver_id, active_app
        super().__init__(f"{receiver_id} is in use by {active_app}.")


@dataclass(frozen=True)
class TunerLease:
    token: str
    receiver_id: str
    app_id: str
    owner_id: str
    purpose: str
    protected: bool = False


class SDRResourceBroker:
    """Exclusive RF control with explicit shared same-stream subscribers."""

    def __init__(self):
        self._lock = RLock()
        self._leases: dict[str, TunerLease] = {}

    def active(self, receiver_id: str) -> dict:
        with self._lock:
            leases = [v for v in self._leases.values()
                      if v.receiver_id == receiver_id]
            if not leases:
                return {"state": "free", "receiver_id": receiver_id,
                        "subscriber_count": 0}
            first = leases[0]
            return {
                "state": "occupied", "receiver_id": receiver_id,
                "app_id": first.app_id, "purpose": first.purpose,
                "protected": any(v.protected for v in leases),
                "subscriber_count": len(leases),
            }

    def acquire(self, receiver_id: str, *, app_id: str, owner_id: str,
                purpose: str, explicit_permission: bool,
                share_stream: bool = False, protected: bool = False) -> TunerLease:
        if not explicit_permission:
            raise PermissionError("Receiver permission must be granted.")
        if not all(isinstance(v, str) and v.strip() for v in
                   (receiver_id, app_id, owner_id, purpose)):
            raise ValueError("Receiver, app, owner and RF purpose are required.")
        with self._lock:
            current = [v for v in self._leases.values()
                       if v.receiver_id == receiver_id]
            if current and not (share_stream and all(
                    v.app_id == app_id and v.purpose == purpose for v in current)):
                raise ReceiverBusy(receiver_id, current[0].app_id)
            lease = TunerLease(secrets.token_urlsafe(24), receiver_id, app_id,
                               owner_id, purpose, protected)
            self._leases[lease.token] = lease
            return lease

    def release(self, token: str, *, owner_id: str) -> bool:
        with self._lock:
            lease = self._leases.get(token)
            if lease is None:
                raise KeyError("Unknown receiver lease.")
            if lease.owner_id != owner_id:
                raise PermissionError("Only the holder may release a receiver lease.")
            del self._leases[token]
            return not any(x.receiver_id == lease.receiver_id
                           for x in self._leases.values())

    def request_switch(self, receiver_id: str, *,
                       requester_app: str, explicit_permission: bool) -> dict:
        """Pure proposal: no force-kill or implicit retune of protected jobs."""
        if not explicit_permission:
            raise PermissionError("Owner-approved switch required.")
        status = self.active(receiver_id)
        return {
            "receiver_id": receiver_id,
            "requester_app": requester_app,
            "current": status,
            "switch_authorized": status["state"] == "free",
            "requires_stop_ack": status["state"] == "occupied",
            "protected_recording": status.get("protected", False),
        }
