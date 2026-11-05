# SPDX-License-Identifier: AGPL-3.0-only
"""Receiver-agnostic, explicit Signal Explorer plan and discovered-service catalog.

No Linux DVB/SDR driver, RF access, web browser or transmission is supplied.
Only validated backend adapters may report observed signals.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol
from threading import RLock
import uuid

MODES = frozenset({"dvb_t2", "dvb_t", "dvb_c", "dab_plus", "fm", "am", "ssb", "packet_rx"})
DVB = frozenset({"dvb_t2", "dvb_t", "dvb_c"})
RADIO = MODES - DVB
BANDS_HZ = {
    "dvb_t2": (470_000_000, 694_000_000),
    "dvb_t": (470_000_000, 694_000_000),
    "dvb_c": (47_000_000, 862_000_000),
    "dab_plus": (174_000_000, 240_000_000),
    "fm": (87_500_000, 108_000_000),
    "am": (148_500, 30_000_000),
    "ssb": (148_500, 30_000_000),
    "packet_rx": (1_000_000, 1_000_000_000),
}


class ScanDenied(RuntimeError):
    pass


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    country: str
    area: str
    mode: str
    frequency_hz: int
    bandwidth_hz: int | None
    reference: str
    verified_status: str = "published_reference_not_received"


@dataclass(frozen=True)
class ScanPlan:
    mode: str
    frequencies_hz: tuple[int, ...]
    bandwidth_hz: int | None = None
    owner_requested: bool = False
    decoder_allowlist: frozenset[str] = frozenset({"service_info", "teletext", "epg", "broadcast_text"})
    # Passive receive ONLY. No arbitrary user-supplied transmission command.
    transmit: bool = False


@dataclass(frozen=True)
class Observation:
    frequency_hz: int
    mode: str
    signal_observed: bool
    # A driver should use measurements/status from the actual receiver.
    services: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    signal_db: float | None = None
    station_id: str | None = None
    original_locator: str | None = None


@dataclass(frozen=True)
class FoundStation:
    id: str
    frequency_hz: int
    mode: str
    service_name: str
    formats: tuple[str, ...]
    # Measured, not estimated from a region/preset.
    signal_db: float | None
    original_locator: str | None
    discovered: bool = True


@dataclass(frozen=True)
class ReceiverState:
    device_id: str
    connected: bool
    supported_modes: frozenset[str]
    current_frequency_hz: int | None = None
    active_recording: bool = False
    safe_same_mux: bool = False
    # Do not claim SDR support merely because a DVB tuner was bought.
    receive_only: bool = True


class ReceiverAdapter(Protocol):
    def observe(self, *, mode: str, frequency_hz: int, bandwidth_hz: int | None
                ) -> Observation: ...
    def tune(self, *, mode: str, frequency_hz: int, bandwidth_hz: int | None) -> None: ...


class SignalExplorer:
    """Bounded scan and manual tune orchestration, not real RF software.

    A caller must authenticate owner privileges, verify actual hardware/driver
    state, and obtain the appropriate ServiceManager lease before calling scan.
    This class cannot bypass those outer trust boundaries.
    """
    def __init__(self):
        self._lock = RLock()
        self._found: dict[tuple[str, int, str], FoundStation] = {}
        self._favorites: set[tuple[str, int, str]] = set()

    @staticmethod
    def sweep(mode: str, *, start_hz: int, stop_hz: int,
              step_hz: int, bandwidth_hz: int | None = None,
              owner_requested: bool = False) -> ScanPlan:
        """Sequential bounded search, not genuinely random RF blind scanning."""
        if mode not in MODES:
            raise ValueError("Unsupported mode")
        if step_hz <= 0 or stop_hz < start_hz:
            raise ValueError("Invalid scan step/range")
        low, high = BANDS_HZ[mode]
        if not low <= start_hz <= stop_hz <= high:
            raise ValueError("Frequency outside declared receive-mode range")
        if (stop_hz - start_hz)//step_hz + 1 > 1024:
            raise ValueError("Scan requires more than 1024 steps; split it")
        return ScanPlan(mode=mode, frequencies_hz=tuple(range(
            start_hz, stop_hz+1, step_hz)), bandwidth_hz=bandwidth_hz,
            owner_requested=owner_requested)

    @staticmethod
    def from_presets(presets: list[Preset], *, owner_requested: bool) -> list[ScanPlan]:
        grouped: dict[tuple[str, int | None], list[int]] = {}
        for p in presets:
            if p.mode not in MODES:
                raise ValueError("Unknown preset mode")
            grouped.setdefault((p.mode,p.bandwidth_hz), []).append(p.frequency_hz)
        return [ScanPlan(mode, tuple(sorted(set(freqs))), band,
                         owner_requested=owner_requested)
                for (mode,band),freqs in grouped.items()]

    def _check(self, plan: ScanPlan, state: ReceiverState) -> None:
        if not plan.owner_requested or plan.transmit:
            raise ScanDenied("Explicit owner request and receive-only mode required")
        if not state.connected or plan.mode not in state.supported_modes:
            raise ScanDenied("Compatible connected receiver/driver required")
        if not plan.frequencies_hz or len(plan.frequencies_hz) > 1024:
            raise ValueError("Bounded non-empty scan list required")
        lo, hi = BANDS_HZ[plan.mode]
        if any(type(hz) is not int or hz < lo or hz > hi for hz in plan.frequencies_hz):
            raise ValueError("Invalid frequency in scan")
        if state.active_recording and not (state.safe_same_mux and
                len(set(plan.frequencies_hz)) == 1 and
                plan.frequencies_hz[0] == state.current_frequency_hz):
            raise ScanDenied("Recording protected: no retune across frequencies")

    def scan(self, plan: ScanPlan, state: ReceiverState, receiver: ReceiverAdapter
             ) -> list[FoundStation]:
        with self._lock:
            self._check(plan, state)
            found: list[FoundStation] = []
            for hz in plan.frequencies_hz:
                observed = receiver.observe(mode=plan.mode, frequency_hz=hz,
                                            bandwidth_hz=plan.bandwidth_hz)
                if observed.frequency_hz != hz or observed.mode != plan.mode:
                    raise ScanDenied("Receiver returned a mismatched frequency/mode")
                if not observed.signal_observed:
                    continue
                # An unknown carrier is listed as Unknown signal, never
                # automatically treated as an amateur's private conversation.
                for name in (observed.services or ("Unknown signal",)):
                    if not name.strip() or len(name) > 140:
                        raise ValueError("Invalid decoded service name")
                    key=(plan.mode,hz,name)
                    previous=self._found.get(key)
                    station=FoundStation(
                        id=previous.id if previous else str(uuid.uuid4()),
                        frequency_hz=hz, mode=plan.mode, service_name=name,
                        formats=tuple(observed.formats),
                        signal_db=observed.signal_db,
                        original_locator=observed.original_locator)
                    self._found[key]=station
                    found.append(station)
            return found

    def discovered(self) -> list[FoundStation]:
        with self._lock:
            return sorted(self._found.values(), key=lambda s:(s.mode, s.frequency_hz,s.service_name))

    def favorite(self, station_id: str) -> None:
        with self._lock:
            items={s.id:k for k,s in self._found.items()}
            if station_id not in items:
                raise KeyError(station_id)
            self._favorites.add(items[station_id])

    def tune(self, station_id: str, *, state: ReceiverState,
             receiver: ReceiverAdapter, owner_requested: bool,
             bandwidth_hz: int | None = None) -> FoundStation:
        with self._lock:
            item=next((s for s in self._found.values() if s.id == station_id),None)
            if item is None:
                raise KeyError(station_id)
            self._check(ScanPlan(item.mode,(item.frequency_hz,),bandwidth_hz,
                                owner_requested=owner_requested),state)
            receiver.tune(mode=item.mode,frequency_hz=item.frequency_hz,
                          bandwidth_hz=bandwidth_hz)
            return item
