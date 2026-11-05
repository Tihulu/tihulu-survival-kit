# SPDX-License-Identifier: AGPL-3.0-only
"""Small bounded, in-memory pairing and remote-command relay.

Prototype only. A display ACK means its web client received a command, NOT
that a tuner, recording, HDMI screen, TV stream, or volume actually changed.
Sessions and queues disappear on process restart. No automatic polling.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hmac
import secrets
from threading import RLock
import time

from .remote_control import RemoteCommandPolicy

COMMANDS = (RemoteCommandPolicy.SIMPLE | RemoteCommandPolicy.CHANNEL)
MAX_PENDING = 64
PAIR_TTL = 120
SESSION_TTL = 3600
DELIVERY_TTL = 180


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
             item_id: str = "") -> dict:
        with self._lock:
            remote = self.remote(token)
            if action not in COMMANDS:
                raise ValueError("Unsupported command")
            if action == "select_channel" and (not profile_id or not item_id):
                raise ValueError("Select channel needs profile and item")
            if action in ("next_channel", "previous_channel") and not profile_id:
                raise ValueError("Channel navigation needs profile")
            if len(profile_id) > 100 or len(item_id) > 100:
                raise ValueError("Identifier exceeds length limit")
            queue = self._queues[remote.target_id]
            if sum(self._commands.get(k, {}).get("state") == "pending" for k in queue) >= MAX_PENDING:
                raise ValueError("Remote command queue full")
            identifier = secrets.token_urlsafe(18)
            item = {"command_id": identifier, "target_id": remote.target_id,
                    "owner": remote.owner, "action": action,
                    "profile_id": profile_id, "item_id": item_id,
                    "state": "pending", "created_at": self.clock()}
            self._commands[identifier] = item
            queue.append(identifier)
            return {"command_id": identifier, "state": "pending",
                    "detail": "Queued for browser display, not tuned"}

    def poll(self, display_token: str) -> list[dict]:
        with self._lock:
            target = self.display(display_token)
            pending = []
            queue = self._queues[target.target_id]
            while queue and len(pending) < 32:
                identifier = queue.popleft()
                item = self._commands.get(identifier)
                if item is None or item["state"] != "pending":
                    continue
                item["state"] = "delivered_unacknowledged"
                pending.append({key:item[key] for key in
                                ("command_id", "action", "profile_id", "item_id")})
            return pending

    def acknowledge(self, display_token: str, command_id: str,
                    *, accepted: bool) -> dict:
        with self._lock:
            target = self.display(display_token)
            item = self._commands.get(command_id)
            if item is None or item["target_id"] != target.target_id:
                raise KeyError("Command not present on this display")
            if item["state"] != "delivered_unacknowledged":
                raise ValueError("Command not pending display acknowledgement")
            item["state"] = "display_received" if accepted else "display_rejected"
            return {"command_id": command_id, "state": item["state"],
                    "detail": "Browser acknowledgement only; no media playback"}
 
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
