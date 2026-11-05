# SPDX-License-Identifier: AGPL-3.0-only
"""Trusted in-process remote command policy for future LAN TV/radio control.

This is NOT a network API, WebSocket service, pairing protocol, media renderer,
or a Raspberry Pi-connected phone remote. Owner/device authorization must be
implemented by an authenticated server before exposing any commands on LAN.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .channel_explorer import ChannelExplorer, Receiver, ReceiverBackend
from .region_channel_manager import ChannelLineupStore


@dataclass(frozen=True)
class RemoteTarget:
    owner_id: str
    target_id: str
    medium: str  # 'tv' or 'radio'
    connected: bool = False


@dataclass(frozen=True)
class RemoteResult:
    status: str
    command: str
    detail: str = ""
    item_id: str = ""


class RemoteRenderer(Protocol):
    """Only a trusted, authenticated backend may implement this interface."""
    def execute(self, target: RemoteTarget, command: str, *, item: dict | None,
                value: int | None) -> bool: ...


class RemoteCommandPolicy:
    SIMPLE = frozenset({"volume_up", "volume_down", "mute", "stop",
                        "subtitles", "teletext", "play_pause"})
    CHANNEL = frozenset({"select_channel", "next_channel", "previous_channel"})
    # Translator/AI require server-owned leases, source text, permission and
    # actual installed models; generic renderer commands cannot impersonate them.
    INTEGRATION = frozenset({"translate", "ask_ai"})

    def __init__(self, lineups: ChannelLineupStore,
                 explorer: ChannelExplorer | None = None):
        self.lineups = lineups
        self.explorer = explorer or ChannelExplorer()
        self._targets: dict[str, RemoteTarget] = {}
        self._active_item: dict[str, str] = {}

    def register_target(self, target: RemoteTarget, *,
                        trusted_server: bool = False) -> None:
        if not trusted_server:
            raise PermissionError("Only trusted session broker may register screens")
        if not target.owner_id or not target.target_id or target.medium not in ("tv","radio"):
            raise ValueError("Invalid display/player registration")
        self._targets[target.target_id] = target

    def command(self, *, owner_id: str, paired_owner_id: str, target_id: str,
                action: str, user_triggered: bool = False,
                profile_id: str | None = None,
                item_id: str | None = None, value: int | None = None,
                receiver: Receiver | None = None,
                tuner_backend: ReceiverBackend | None = None,
                renderer: RemoteRenderer | None = None) -> RemoteResult:
        # The future network handler must validate both owner IDs using the
        # authenticated pairing session; these are trusted internal arguments.
        if not user_triggered or not owner_id or paired_owner_id != owner_id:
            raise PermissionError("Explicit owner-paired remote action required")
        target = self._targets.get(target_id)
        if target is None or target.owner_id != owner_id:
            raise PermissionError("Target does not belong to authenticated owner")
        if action not in self.SIMPLE | self.CHANNEL | self.INTEGRATION:
            raise ValueError("Command not in remote allowlist")
        if not target.connected:
            return RemoteResult("target_offline", action, "Display/player is not connected")
        if action in self.INTEGRATION:
            return RemoteResult("integration_missing", action,
                                "Use source-grounded shared Translator/AI services")
        selected: dict | None = None
        if action in self.CHANNEL:
            if not profile_id:
                raise ValueError("Channel commands require an owner profile")
            items = self.lineups.items(owner_id=owner_id,profile_id=profile_id,
                                       media=target.medium)
            if not items:
                return RemoteResult("no_channels", action)
            ids = [item["item_id"] for item in items]
            if action == "select_channel":
                if item_id not in ids:
                    raise KeyError("Channel not available to target's owner/medium")
                chosen = item_id
            else:
                current = self._active_item.get(target_id)
                index = ids.index(current) if current in ids else (
                    -1 if action == "next_channel" else 0)
                delta = 1 if action == "next_channel" else -1
                chosen = ids[(index + delta) % len(ids)]
            selected = next(i for i in items if i["item_id"] == chosen)
            if receiver is None or tuner_backend is None:
                return RemoteResult("backend_missing", action,
                                    "No verified tuner and playback adapter", chosen)
            reading = self.lineups.tune_item(
                owner_id=owner_id,profile_id=profile_id,item_id=chosen,
                receiver=receiver,backend=tuner_backend,
                explorer=self.explorer,user_triggered=True)
            if reading.state not in ("service_decoded","signal_locked"):
                return RemoteResult(reading.state, action, reading.detail, chosen)
        if renderer is None:
            return RemoteResult("backend_missing", action,
                                "No trusted TV/radio playback renderer connected",
                                selected["item_id"] if selected else "")
        if type(value) is not int and value is not None:
            raise ValueError("Remote value must be an integer")
        if value is not None and not 0 <= value <= 100:
            raise ValueError("Remote value out of range")
        acknowledged = renderer.execute(target, action, item=selected, value=value)
        if not acknowledged:
            return RemoteResult("not_acknowledged", action, "Device rejected command")
        if selected is not None:
            self._active_item[target_id] = selected["item_id"]
        return RemoteResult("acknowledged", action,
                            "Trusted renderer acknowledged; not a broadcast quality claim",
                            selected["item_id"] if selected else "")
