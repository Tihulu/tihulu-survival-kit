# SPDX-License-Identifier: AGPL-3.0-only
"""Small bounded, in-memory pairing and remote-command relay.

Prototype only. A display ACK means its web client received a command, NOT
that a tuner, recording, HDMI screen, TV stream, or volume actually changed.
Sessions and queues disappear on process restart. No automatic polling.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
import re
import secrets
from threading import RLock
import time

from .remote_control import RemoteCommandPolicy

COMMANDS = (RemoteCommandPolicy.SIMPLE | RemoteCommandPolicy.CHANNEL)
MAX_PENDING = 64
PAIR_TTL = 120
SESSION_TTL = 3600
DELIVERY_TTL = 180
RETRY_AFTER_SECONDS = 5
MAX_DELIVERY_ATTEMPTS = 3


@dataclass
class TargetSession:
    owner: str
    target_id: str
    medium: str
    display_token: str
    expires_at: float
    pairing_code: str
    pairing_expires_at: float


@dataclass
class PairedRemote:
    owner: str
    target_id: str
    medium: str
    expires_at: float


class LanRemoteBroker:
    """In-process relay. Server must authenticate owner and secure transport."""

    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self._lock = RLock()
        self._targets: dict[str, TargetSession] = {}
        self._remotes: dict[str, PairedRemote] = {}
        self._commands: dict[str, dict] = {}
        self._queues: dict[str, deque[str]] = {}
        self._failed: dict[str, list[float]] = {}
        self._global_failed: list[float] = []

    def _purge(self) -> None:
        now = self.clock()
        expired = [k for k,v in self._targets.items() if v.expires_at <= now]
        for target_id in expired:
            self._targets.pop(target_id, None)
            self._queues.pop(target_id, None)
        self._remotes = {k:v for k,v in self._remotes.items()
                         if v.expires_at > now and v.target_id in self._targets}
        self._commands = {k:v for k,v in self._commands.items()
                          if v["created_at"] + DELIVERY_TTL > now
                          and v["target_id"] in self._targets}
        # Evict stale queue references even when a paired screen never polls.
        # This matters on memory-limited devices that remain powered for days.
        for target_id in list(self._queues):
            self._queues[target_id] = deque(
                ident for ident in self._queues[target_id]
                if ident in self._commands
                and self._commands[ident]["state"] == "pending")
        # Completed status history must stay bounded under high-volume paired
        # remote activity. Pending commands are protected by per-target limits.
        if len(self._commands) > 2_048:
            completed = sorted(
                (v for v in self._commands.values() if v["state"] != "pending"),
                key=lambda v: v["created_at"])
            for item in completed[:len(self._commands) - 2_048]:
                self._commands.pop(item["command_id"], None)
        for peer in list(self._failed):
            attempts = [t for t in self._failed[peer] if now - t < 120]
            if attempts:
                self._failed[peer] = attempts
            else:
                self._failed.pop(peer, None)
        self._global_failed = [t for t in self._global_failed if now - t < 120]

    @staticmethod
    def _token() -> str:
        return secrets.token_urlsafe(32)

    def register(self, *, owner: str, medium: str) -> dict:
        if not owner or medium not in ("tv", "radio"):
            raise ValueError("Owner and TV/radio medium required")
        with self._lock:
            self._purge()
            if sum(v.owner == owner for v in self._targets.values()) >= 8:
                raise ValueError("Maximum eight concurrent display sessions")
            identifier = secrets.token_urlsafe(18)
            active_codes = {v.pairing_code for v in self._targets.values()
                            if v.pairing_expires_at > self.clock()}
            for _ in range(12):
                code = f"{secrets.randbelow(100_000_000):08d}"
                if code not in active_codes:
                    break
            else:
                raise RuntimeError("Could not allocate distinct pairing code")
            session = TargetSession(owner, identifier, medium, self._token(),
                                    self.clock() + SESSION_TTL,
                                    code, self.clock() + PAIR_TTL)
            self._targets[identifier] = session
            self._queues[identifier] = deque()
            return {"target_id": identifier, "display_token": session.display_token,
                    "pairing_code": code, "pairing_seconds": PAIR_TTL,
                    "medium": medium}

    def pair(self, code: str, *, peer: str) -> dict:
        if not isinstance(code, str) or len(code) != 8 or not code.isascii() or not code.isdigit():
            raise ValueError("Eight-digit pairing code required")
        with self._lock:
            self._purge()
            failures = self._failed.get(peer, [])
            if len(failures) >= 5 or len(self._global_failed) >= 30:
                raise PermissionError("Pairing temporarily rate limited")
            match = next((s for s in self._targets.values()
                          if s.pairing_expires_at > self.clock()
                          and hmac.compare_digest(s.pairing_code, code)), None)
            if match is None:
                self._failed.setdefault(peer, []).append(self.clock())
                self._global_failed.append(self.clock())
                raise PermissionError("Pairing code not recognized or expired")
            match.pairing_expires_at = 0
            match.pairing_code = ""
            token = self._token()
            self._remotes[token] = PairedRemote(
                match.owner, match.target_id, match.medium,
                min(self.clock() + SESSION_TTL, match.expires_at))
            return {"remote_token": token, "target_id": match.target_id,
                    "medium": match.medium, "session_seconds": SESSION_TTL}

    def display(self, token: str) -> TargetSession:
        with self._lock:
            self._purge()
            match = next((s for s in self._targets.values()
                          if hmac.compare_digest(s.display_token, token)), None)
            if match is None:
                raise PermissionError("Invalid display session")
            return match

    def remote(self, token: str) -> PairedRemote:
        with self._lock:
            self._purge()
            match = next((s for t,s in self._remotes.items()
                          if hmac.compare_digest(t, token)), None)
            if match is None:
                raise PermissionError("Invalid remote session")
            return match

    def send(self, token: str, *, action: str, profile_id: str = "",
             item_id: str = "", request_id: str = "") -> dict:
        """Queue once per remote request ID, even when an HTTP response is lost."""
        with self._lock:
            remote = self.remote(token)
            if action not in COMMANDS:
                raise ValueError("Unsupported command")
            if action == "select_channel" and (not profile_id or not item_id):
                raise ValueError("Select channel needs profile and item")
            if action in ("next_channel", "previous_channel") and not profile_id:
                raise ValueError("Channel navigation needs profile")
            if not isinstance(profile_id, str) or not isinstance(item_id, str):
                raise ValueError("Identifiers must be strings")
            if len(profile_id) > 100 or len(item_id) > 100:
                raise ValueError("Identifier exceeds length limit")
            if not isinstance(request_id, str) or (
                    request_id and re.fullmatch(r"[A-Za-z0-9_-]{12,80}", request_id) is None):
                raise ValueError("Invalid idempotency request ID")
            request_key = (hashlib.sha256(
                (token + "\x00" + request_id).encode("utf-8")).hexdigest()
                if request_id else "")
            if request_key:
                # Duplicate POST with the same remote token and request ID must
                # never create a second volume/channel command.
                for previous in self._commands.values():
                    if previous.get("request_key") != request_key:
                        continue
                    if (previous["action"], previous["profile_id"],
                            previous["item_id"]) != (action, profile_id, item_id):
                        raise ValueError("Request ID reused with different command")
                    return {"command_id": previous["command_id"],
                            "state": previous["state"],
                            "detail": "Existing browser command; not requeued"}
            queue = self._queues[remote.target_id]
            active_count = sum(
                item["target_id"] == remote.target_id and item["state"] in (
                    "pending", "delivered_unacknowledged")
                for item in self._commands.values())
            if active_count >= MAX_PENDING:
                raise ValueError("Remote command queue full")
            identifier = secrets.token_urlsafe(18)
            item = {"command_id": identifier, "target_id": remote.target_id,
                    "owner": remote.owner, "action": action,
                    "profile_id": profile_id, "item_id": item_id,
                    "state": "pending", "created_at": self.clock(),
                    "last_delivery_at": None, "attempts": 0,
                    "request_key": request_key}
            self._commands[identifier] = item
            queue.append(identifier)
            return {"command_id": identifier, "state": "pending",
                    "detail": "Queued for browser display, not tuned"}

    def poll(self, display_token: str) -> list[dict]:
        """Retry unacknowledged commands with stable IDs; not at-most-once RF."""
        with self._lock:
            target = self.display(display_token)
            now = self.clock()
            received: list[dict] = []
            def deliver(item):
                item["state"] = "delivered_unacknowledged"
                item["last_delivery_at"] = now
                item["attempts"] += 1
                received.append({key:item[key] for key in (
                    "command_id", "action", "profile_id", "item_id")})
            unconfirmed = sorted((
                item for item in self._commands.values()
                if item["target_id"] == target.target_id and
                item["state"] == "delivered_unacknowledged" and
                item["last_delivery_at"] is not None and
                now - item["last_delivery_at"] >= RETRY_AFTER_SECONDS),
                key=lambda item: (item["last_delivery_at"], item["created_at"]))
            for item in unconfirmed:
                if item["attempts"] >= MAX_DELIVERY_ATTEMPTS:
                    # Delivery outcome is unknown. Never claim media success,
                    # and never keep retrying a potentially non-idempotent action.
                    item["state"] = "delivery_uncertain"
                elif len(received) < 32:
                    deliver(item)
            queue = self._queues[target.target_id]
            while queue and len(received) < 32:
                identifier = queue.popleft()
                item = self._commands.get(identifier)
                if item is None or item["state"] != "pending":
                    continue
                deliver(item)
            return received

    def acknowledge(self, display_token: str, command_id: str,
                    *, accepted: bool) -> dict:
        with self._lock:
            target = self.display(display_token)
            item = self._commands.get(command_id)
            if item is None or item["target_id"] != target.target_id:
                raise KeyError("Command not present on this display")
            desired = "display_received" if accepted else "display_rejected"
            if item["state"] == desired:
                # HTTP response to a previous ACK may have been lost.
                return {"command_id": command_id, "state": desired,
                        "detail": "Browser acknowledgement already stored; no media playback"}
            if item["state"] not in ("delivered_unacknowledged", "delivery_uncertain"):
                raise ValueError("Command not awaiting display acknowledgement")
            item["state"] = desired
            return {"command_id": command_id, "state": desired,
                    "detail": "Browser acknowledgement only; no media playback"}

    def disconnect_remote(self, remote_token: str) -> None:
        """Explicit paired-phone sign out, independent of display revocation."""
        with self._lock:
            self.remote(remote_token)
            self._remotes.pop(remote_token, None)

    def status(self, remote_token: str, command_id: str) -> dict:
        with self._lock:
            remote = self.remote(remote_token)
            item = self._commands.get(command_id)
            if item is None or item["target_id"] != remote.target_id:
                raise KeyError("Command not available to remote")
            return {"command_id": command_id, "state": item["state"],
                    "detail": "No physical tuner / media confirmation"}

    def revoke(self, *, owner: str, target_id: str) -> None:
        with self._lock:
            target = self._targets.get(target_id)
            if target is None or target.owner != owner:
                raise PermissionError("Target not owned")
            self._targets.pop(target_id)
            self._queues.pop(target_id, None)
            self._purge()
