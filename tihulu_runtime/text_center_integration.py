# SPDX-License-Identifier: AGPL-3.0-only
"""Fail-closed integration boundary for Tihulu/TIHULU-TEXT-CENTER.

Import the reference capability/inventory code lazily; never fork its catalogue,
start its loopback server on LAN, open RF, or create a separate SDR broker.
Only trusted authenticated Tihulu code may call these functions. Actual tuner
control requires a true cross-process reservation AND the shared Kit broker.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Protocol
import secrets

from .sdr_resource_broker import SDRResourceBroker

TEXT_PAGES = {
    100: "Main Index", 200: "News & Headlines",
    300: "Weather & Meteorological Bulletins",
    400: "Radio & Broadcast Data", 500: "Emergency Information",
    600: "Blogs, BBS & Local Messages", 700: "Offline Wiki & Library",
    800: "Utilities, Gemini, Gopher & Text Networks",
    850: "About", 860: "Protocols, Dependencies & Receiver Status",
}


class TextCenterUnavailable(RuntimeError):
    """Missing optional reference code, receiver guard or real decoder backend."""


class CrossProcessReservation(Protocol):
    def release(self) -> None: ...


class CrossProcessGuard(Protocol):
    def reserve(self, receiver_id: str, purpose: str) -> CrossProcessReservation: ...


class RFCaptureBackend(Protocol):
    def start(self, *, receiver_id: str, frequency_hz: int,
              duration_seconds: int) -> object: ...
    def stop(self, handle: object) -> bool: ...


@dataclass(frozen=True)
class TextCenterSession:
    id: str
    owner_id: str
    receiver_id: str
    frequency_hz: int
    duration_seconds: int
    purpose: str


class TextCenterIntegration:
    """One owner-scoped passive source + explicit bounded FM-RDS lease.

    The broker is the SAME singleton used by Flight Radar/Radio/RTL-433.
    A real cross-process guard cannot be replaced by standalone application
    flock files, pgrep, or a single-process broker. RF is unavailable by
    default until both a guard and validated capture adapter are injected.
    """

    def __init__(self, *, broker: SDRResourceBroker,
                 guard: CrossProcessGuard | None = None,
                 backend: RFCaptureBackend | None = None,
                 inventory: Callable[[], dict] | None = None,
                 catalog: Callable[[dict], list[dict]] | None = None):
        if not isinstance(broker, SDRResourceBroker):
            raise TypeError("Existing shared SDRResourceBroker is required")
        self.broker, self.guard, self.backend = broker, guard, backend
        self._inventory, self._catalog = inventory, catalog
        self._lock = RLock()
        self._sessions: dict[str, tuple] = {}

    def passive_discover(self, *, owner_id: str,
                         receiver_ids: tuple[str, ...] = ()) -> dict:
        """Read-only, on-demand; NO network request, tuner open or RF retune."""
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise PermissionError("Authenticated owner required")
        if any(not isinstance(x, str) or not x.strip() for x in receiver_ids):
            raise ValueError("Trusted receiver IDs are required")
        try:
            if self._inventory is None or self._catalog is None:
                from textcenter.receivers import receiver_inventory
                from textcenter.capabilities import capability_catalog
                inventory = (self._inventory or receiver_inventory)()
                capabilities = (self._catalog or capability_catalog)(inventory)
            else:
                inventory = self._inventory()
                capabilities = self._catalog(inventory)
        except ImportError:
            return {
                "status": "dependency_missing", "source": "TIHULU-TEXT-CENTER",
                "backend": "not_installed", "rf_receiver_tuned": False,
                "connected_decoder": False, "background_polling": False,
                "pages": TEXT_PAGES.copy(), "capabilities": [], "receivers": [],
                "note": "The optional reference package is not installed.",
            }
        if not isinstance(inventory, dict) or not isinstance(capabilities, list):
            raise TextCenterUnavailable("Reference capability data unavailable")
        return {
            "status": "passive_only", "source": "TIHULU-TEXT-CENTER",
            "backend": "optional_reference", "rf_receiver_tuned": False,
            "connected_decoder": False, "background_polling": False,
            "pages": TEXT_PAGES.copy(), "capabilities": capabilities,
            "receivers": [self.broker.active(rid) for rid in receiver_ids],
            "inventory": inventory,
            "note": "Device or tool detection does not prove received signal.",
        }

    def start_fm_rds(self, *, owner_id: str, receiver_id: str,
                     frequency_hz: int, duration_seconds: int,
                     user_triggered: bool = False) -> TextCenterSession:
        """Explicit 10-90s FM RDS only; never bypass global RF ownership."""
        if not user_triggered:
            raise PermissionError("Manual user request required; background OFF")
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise PermissionError("Authenticated owner required")
        if not isinstance(receiver_id, str) or not receiver_id.strip():
            raise ValueError("Trusted receiver ID required")
        if type(frequency_hz) is not int or not 87_500_000 <= frequency_hz <= 108_000_000:
            raise ValueError("FM frequency must be an integer in 87.5-108 MHz")
        if type(duration_seconds) is not int or not 10 <= duration_seconds <= 90:
            raise ValueError("FM capture duration must be 10-90 seconds")
        if self.guard is None or self.backend is None:
            raise TextCenterUnavailable(
                "Cross-process receiver reservation and real RDS adapter required")
        with self._lock:
            reservation = self.guard.reserve(receiver_id, "fm_rds")
            try:
                lease = self.broker.acquire(
                    receiver_id, app_id="text_center", owner_id=owner_id,
                    purpose="fm_rds", explicit_permission=True, protected=False)
            except BaseException:
                reservation.release()
                raise
            try:
                handle = self.backend.start(
                    receiver_id=receiver_id, frequency_hz=frequency_hz,
                    duration_seconds=duration_seconds)
            except BaseException:
                self.broker.release(lease.token, owner_id=owner_id)
                reservation.release()
                raise
            session = TextCenterSession(secrets.token_urlsafe(20), owner_id,
                                        receiver_id, frequency_hz,
                                        duration_seconds, "fm_rds")
            self._sessions[session.id] = (session, lease.token, reservation, handle)
            return session

    def stop_fm_rds(self, session_id: str, *, owner_id: str) -> bool:
        """Keep BOTH leases until decoder confirms it actually stopped."""
        with self._lock:
            session, token, reservation, handle = self._sessions[session_id]
            if session.owner_id != owner_id:
                raise PermissionError("Only capture owner can stop")
            if self.backend is None or not self.backend.stop(handle):
                return False
            self.broker.release(token, owner_id=owner_id)
            reservation.release()
            del self._sessions[session_id]
            return True

    def sessions(self, *, owner_id: str) -> list[TextCenterSession]:
        if not owner_id:
            raise PermissionError("Authenticated owner required")
        with self._lock:
            return [s for s, _, _, _ in self._sessions.values()
                    if s.owner_id == owner_id]
