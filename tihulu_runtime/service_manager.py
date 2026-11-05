"""Stage-4 optional-service policy engine (stdlib only; NOT a deployed Pi daemon).

Trusted backend code must authenticate owners before calling administrative methods.
This library deliberately never accepts arbitrary shell commands or unit identifiers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import RLock
from typing import Callable, Protocol
import json
import os
import secrets
import tempfile
import time


class ServiceError(RuntimeError):
    pass


class Blocked(ServiceError):
    """Dependency unavailable, disabled, or owner confirmation required."""


class Busy(ServiceError):
    """Active task must be finished/cancelled safely before a hard disable."""


@dataclass(frozen=True)
class Module:
    id: str
    dependencies: tuple[str, ...] = ()
    installed: bool = False
    idle_seconds: float = 0.0


@dataclass(frozen=True)
class Policy:
    hard: bool | None = True
    background: bool | None = False
    startup: bool | None = False


@dataclass(frozen=True)
class Grant:
    token: str
    task_id: str
    owner_id: str
    scopes: frozenset[str]
    expires_at: float


@dataclass(frozen=True)
class Lease:
    task_id: str
    owner_id: str
    modules: tuple[str, ...]
    mode: str


class Adapter(Protocol):
    def start(self, module_id: str) -> None: ...
    def stop(self, module_id: str) -> None: ...


class ServiceManager:
    """Thread-safe state machine; a lease represents a *server-owned* task.

    Window/tab navigation never implicitly releases a durable recording/scan lease.
    Leases and one-time grants are intentionally volatile across process restarts.
    """

    def __init__(self, modules: list[Module], adapter: Adapter,
                 state_file: str | Path | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._lock = RLock()
        self.modules = {m.id: m for m in modules}
        if len(self.modules) != len(modules):
            raise ValueError("Duplicate module id")
        if any(not m.id or m.id.startswith("core") for m in modules):
            raise ValueError("Protected core must never be managed as an optional module")
        self.adapter = adapter
        self.clock = clock
        self.state_file = Path(state_file) if state_file is not None else None
        self.policies = {
            name: Policy(None, None, None) if name == "emergency_monitor" else Policy()
            for name in self.modules
        }
        self._leases: dict[str, Lease] = {}
        self._grants: dict[str, Grant] = {}
        self._counts = {name: 0 for name in self.modules}
        self._running: set[str] = set()
        self._deadlines: dict[str, float] = {}
        self.background_paused = False
        # Check cycles and unknown dependencies before operating anything.
        for name in self.modules:
            self._resolve(name)
        self._load()

    def _resolve(self, name: str) -> tuple[str, ...]:
        result: list[str] = []
        visiting: set[str] = set()
        seen: set[str] = set()

        def visit(item: str) -> None:
            if item not in self.modules:
                raise ValueError("Unknown dependency: " + item)
            if item in visiting:
                raise ValueError("Circular dependency: " + item)
            if item in seen:
                return
            visiting.add(item)
            for dep in self.modules[item].dependencies:
                visit(dep)
            visiting.remove(item)
            seen.add(item)
            result.append(item)

        visit(name)
        return tuple(result)

    def _load(self) -> None:
        if self.state_file is None or not self.state_file.exists():
            return
        data = json.loads(self.state_file.read_text(encoding="utf-8"))
        for name, values in data.get("policies", {}).items():
            if name not in self.modules or not isinstance(values, dict):
                continue
            allowed_none = name == "emergency_monitor"
            if all(values.get(k) in (True, False, None) and
                   (allowed_none or values.get(k) is not None)
                   for k in ("hard", "background", "startup")):
                self.policies[name] = Policy(**{k: values[k] for k in
                                                 ("hard", "background", "startup")})

    def _save(self) -> None:
        if self.state_file is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps({"version": 1, "policies": {
            k: asdict(v) for k, v in self.policies.items()
        }}, indent=2, sort_keys=True)
        fd, tmp = tempfile.mkstemp(prefix=".tihulu-", dir=self.state_file.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, self.state_file)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def set_policy(self, module_id: str, *, hard: bool | None = None,
                   background: bool | None = None, startup: bool | None = None,
                   owner_verified: bool = False) -> None:
        """Owner-authenticated administrative operation, not a public HTTP API.

        Use configure_emergency() for emergency-monitor's initial explicit choice.
        None means 'leave unchanged' here.
        """
        if not owner_verified:
            raise PermissionError("Authenticated owner confirmation required")
        with self._lock:
            if module_id not in self.modules:
                raise KeyError(module_id)
            if module_id == "emergency_monitor":
                raise Blocked("Use configure_emergency for explicit monitoring consent")
            old = self.policies[module_id]
            if hard is False and self._counts[module_id]:
                raise Busy("Active tasks still hold this service")
            self.policies[module_id] = replace(
                old,
                hard=old.hard if hard is None else hard,
                background=old.background if background is None else background,
                startup=old.startup if startup is None else startup,
            )
            self._save()

    def configure_emergency(self, *, enabled: bool, background: bool,
                            startup: bool, owner_verified: bool = False) -> None:
        if not owner_verified:
            raise PermissionError("Emergency monitoring requires owner choice")
        with self._lock:
            if not enabled and self._counts.get("emergency_monitor", 0):
                raise Busy("Stop active monitoring safely before disabling")
            if "emergency_monitor" not in self.modules:
                raise KeyError("emergency_monitor")
            self.policies["emergency_monitor"] = Policy(
                enabled, background if enabled else False, startup if enabled else False)
            self._save()

    def authorize_once(self, *, task_id: str, owner_id: str,
                       scopes: set[str], owner_verified: bool = False,
                       lifetime_seconds: float = 3600) -> Grant:
        """A separate trusted/UI authorization step, NOT a client-supplied bypass."""
        if not owner_verified or not owner_id or not task_id:
            raise PermissionError("Verified owner and bound task are required")
        with self._lock:
            if task_id in self._leases:
                raise Busy("Task is already running")
            if not scopes or not scopes.issubset(self.modules):
                raise ValueError("Grant scopes must be exact known optional services")
            if "emergency_monitor" in scopes:
                raise Blocked("Emergency monitoring requires persistent explicit setup")
            if lifetime_seconds <= 0 or lifetime_seconds > 3600:
                raise ValueError("Temporary authorization limited to <= 1 hour")
            grant = Grant(secrets.token_urlsafe(24), task_id, owner_id,
                          frozenset(scopes), self.clock() + lifetime_seconds)
            self._grants[grant.token] = grant
            return grant

    def acquire(self, module_id: str, *, task_id: str, owner_id: str,
                mode: str = "foreground", grant_token: str | None = None) -> Lease:
        if mode not in ("foreground", "background", "startup"):
            raise ValueError("Unrecognized operation mode")
        if not task_id or not owner_id:
            raise ValueError("Server job id and owner id required")
        with self._lock:
            if task_id in self._leases:
                raise Busy("Duplicate job id")
            order = self._resolve(module_id)
            grant = self._grants.get(grant_token or "")
            if grant is not None and (grant.task_id != task_id or
                                      grant.owner_id != owner_id or
                                      self.clock() >= grant.expires_at):
                grant = None
            for name in order:
                if not self.modules[name].installed:
                    raise Blocked(name + ": not installed")
                policy = self.policies[name]
                if policy.hard is None:
                    raise Blocked(name + ": owner setup not configured")
                if policy.hard is False and not (
                        mode == "foreground" and grant and name in grant.scopes):
                    raise Blocked(name + ": Hard OFF; owner decision required")
                if mode == "background" and (
                        policy.background is not True or self.background_paused):
                    raise Blocked(name + ": background disabled")
                if mode == "startup" and name == module_id and policy.startup is not True:
                    raise Blocked(name + ": startup disabled")
            started: list[str] = []
            try:
                for name in order:
                    if name not in self._running:
                        self.adapter.start(name)
                        self._running.add(name)
                        started.append(name)
            except Exception:
                for name in reversed(started):
                    try:
                        self.adapter.stop(name)
                        self._running.remove(name)
                    except Exception:
                        pass
                raise
            for name in order:
                self._counts[name] += 1
                self._deadlines.pop(name, None)
            lease = Lease(task_id, owner_id, order, mode)
            self._leases[task_id] = lease
            # Grants never persist and are consumed by a single matching task.
            if grant:
                self._grants.pop(grant.token, None)
            return lease

    def release(self, task_id: str, *, owner_id: str) -> None:
        with self._lock:
            lease = self._leases.get(task_id)
            if lease is None:
                raise KeyError(task_id)
            if lease.owner_id != owner_id:
                raise PermissionError("Only the owning job can release its lease")
            self._leases.pop(task_id)
            for name in lease.modules:
                self._counts[name] -= 1
                if self._counts[name] == 0:
                    self._deadlines[name] = self.clock() + self.modules[name].idle_seconds

    def sweep_idle(self) -> list[str]:
        """Call from a short timer, after request completion, or on app access."""
        with self._lock:
            now = self.clock()
            # Consumers must be stopped before their dependencies.
            priority = {name: len(self._resolve(name)) for name in self.modules}
            ready = sorted(
                (name for name, deadline in self._deadlines.items()
                 if deadline <= now and self._counts[name] == 0),
                key=lambda n: priority[n], reverse=True)
            stopped: list[str] = []
            for name in ready:
                if name in self._running:
                    self.adapter.stop(name)
                    self._running.remove(name)
                    stopped.append(name)
                self._deadlines.pop(name, None)
            # Expired one-time grants do not survive idle cleanup.
            self._grants = {token: g for token, g in self._grants.items()
                            if g.expires_at > now}
            return stopped

    def pause_optional_background(self, paused: bool, *,
                                  owner_verified: bool = False) -> None:
        if not owner_verified:
            raise PermissionError("Owner authorization required")
        with self._lock:
            # Existing user-started server tasks and original recordings survive.
            self.background_paused = paused

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {name: {
                "installed": module.installed,
                "policy": asdict(self.policies[name]),
                "controller_state": "start_requested" if name in self._running else "stopped",
                "active_tasks": self._counts[name],
                "idle_stop_pending": name in self._deadlines,
            } for name, module in self.modules.items()}


class UserSystemdAdapter:
    """Optional, deliberately unprivileged allowlist-based adapter.

    Only explicitly registered Tihulu user services; NOT Pi core/network/root
    units. This does not create, install, or configure any actual systemd units.
    """

    def __init__(self, units: dict[str, str]):
        self.units = dict(units)
        for unit in units.values():
            if not unit.startswith("tihulu-") or not unit.endswith(".service"):
                raise ValueError("Only allowlisted tihulu-*.service units accepted")
            if any(x in unit for x in ("core", "portal", "network", "hotspot", "auth")):
                raise ValueError("Core system services may not be managed here")

    def _run(self, verb: str, module_id: str) -> None:
        import subprocess
        if module_id not in self.units:
            raise Blocked(module_id + ": no allowlisted user service mapping")
        subprocess.run(["systemctl", "--user", verb, self.units[module_id]],
                       check=True, timeout=30, shell=False)

    def start(self, module_id: str) -> None:
        self._run("start", module_id)

    def stop(self, module_id: str) -> None:
        self._run("stop", module_id)
