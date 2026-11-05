# SPDX-License-Identifier: AGPL-3.0-only
"""On-demand DAB+ Band III automatic scan orchestration for Radio Center.

Reads published *channel grid* as tune candidates; only a backend reading
from an actual decoder can promote a multiplex/service to received status.
No daemon, network listener, scanning-on-open, artificial channel results,
or programmatic favorite overwrite. The future authenticated Pi gateway
must provide a real timeout-bounded decoder/probe and stable USB mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import re

from .channel_explorer import (
    ChannelStore, DetectedService, FrequencyLibrary, Receiver,
    ReceiverBackend, ScanRecord, TunePoint,
)
from .sdr_capture import ManagedSdrScan


@dataclass(frozen=True)
class DabScanBlock:
    channel: str
    frequency_hz: int
    source: str = "published_dab_band_iii_raster_NOT_received"

    @property
    def point(self) -> TunePoint:
        return TunePoint("dab", self.frequency_hz)


@dataclass(frozen=True)
class DabScanPlan:
    scope: str
    country: str
    region: str
    blocks: tuple[DabScanBlock, ...]
    include_13_extension: bool = False
    background_enabled: bool = False


@dataclass(frozen=True)
class DabScanProgress:
    scanned: int
    total: int
    channel: str
    frequency_hz: int
    state: str
    decoded_service_count: int


@dataclass(frozen=True)
class DabScanResult:
    owner_id: str
    receiver_id: str
    plan: DabScanPlan
    records: tuple[ScanRecord, ...]
    cancelled: bool
    # Neither this result nor any DB entry implies verified radio playback.
    physical_pi_rf_validated: bool = False

    @property
    def decoded_services(self) -> tuple[tuple[DabScanBlock, DetectedService], ...]:
        block_by_hz = {b.frequency_hz: b for b in self.plan.blocks}
        return tuple(
            (block_by_hz[record.frequency_hz], service)
            for record in self.records
            if record.state == "service_decoded" and
            record.frequency_hz in block_by_hz
            for service in record.services
        )

    @property
    def multiplex_count(self) -> int:
        return sum(record.state == "service_decoded" for record in self.records)


class DabAutoScanner:
    """Manual-click scan, shared SDR foreground lease, incremental progress.

    'quick' uses ONLY locally published candidate DAB presets for region +
    nationwide, not presumed active services. 'full' scans the standard
    32 discrete Band III blocks; opt-in extension adds 6 more blocks.
    If a selected country has no quick DAB candidate, request full instead.
    """

    def __init__(self, library: FrequencyLibrary, scanner: ManagedSdrScan):
        self.library = library
        self.scanner = scanner

    def plan(self, *, country: str, region: str,
             scope: str = "quick",
             include_13_extension: bool = False) -> DabScanPlan:
        if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError("Two-letter country code required")
        if not isinstance(region, str) or not region or len(region) > 120:
            raise ValueError("Explicit selected region required")
        if scope not in ("quick", "full"):
            raise ValueError("DAB scope must be quick or full")
        if type(include_13_extension) is not bool:
            raise ValueError("Extended band requires explicit boolean option")
        if scope == "quick" and include_13_extension:
            raise ValueError("13A-13F extension is only offered in full-band mode")

        core = self.library.channel_group_points("dab_band_iii")
        expected_core = tuple(f"{i}{letter}" for i in range(5, 13)
                              for letter in "ABCD")
        if len(core) != 32 or any(p.mode != "dab" for p in core):
            raise ValueError("Invalid standard DAB channel grid")
        all_blocks = [
            DabScanBlock(channel, point.frequency_hz)
            for channel, point in zip(expected_core, core)
        ]
        if scope == "full" and include_13_extension:
            ext = self.library.channel_group_points("dab_band_iii_ext_13")
            if len(ext) != 6 or any(p.mode != "dab" for p in ext):
                raise ValueError("Invalid extended DAB channel grid")
            all_blocks.extend(
                DabScanBlock(f"13{letter}", point.frequency_hz)
                for letter, point in zip("ABCDEF", ext)
            )
        if (len({block.frequency_hz for block in all_blocks}) != len(all_blocks)
                or any(not 174_000_000 <= b.frequency_hz <= 240_000_000
                       for b in all_blocks)
                or any(left.frequency_hz >= right.frequency_hz
                       for left, right in zip(all_blocks, all_blocks[1:]))):
            raise ValueError("Malformed published DAB raster")

        if scope == "quick":
            # This is a candidate frequency list, NOT proof the local service
            # actually broadcasts or the Pi has a compatible decoder.
            suggested = {
                p.frequency_hz for p in self.library.list_presets(country=country,
                                                                   kind="dab")
                if p.region in (region, "ALL")
            }
            all_blocks = [b for b in all_blocks if b.frequency_hz in suggested]
            if not all_blocks:
                raise ValueError(
                    "No published DAB quick candidates in this region; use full scan")
        return DabScanPlan(scope, country, region, tuple(all_blocks),
                           include_13_extension, background_enabled=False)

    def run(self, plan: DabScanPlan, receiver: Receiver, *, owner_id: str,
            job_id: str, backend: ReceiverBackend | None,
            user_triggered: bool = False,
            on_progress: Callable[[DabScanProgress], None] | None = None,
            should_cancel: Callable[[], bool] | None = None,
            grant_token: str | None = None) -> DabScanResult:
        if not user_triggered:
            raise PermissionError("DAB auto-scan only runs on explicit user action")
        if not isinstance(plan, DabScanPlan) or not plan.blocks:
            raise ValueError("Non-empty published DAB scan plan required")
        if not owner_id or not job_id:
            raise PermissionError("Trusted owner and server job required")
        if backend is None:
            raise ValueError("Real trusted DAB decoder probe not installed")
        if (receiver.kind != "radio_sdr" or "dab" not in receiver.supported_modes
                or not all(receiver.supports("dab", b.frequency_hz)
                           for b in plan.blocks)):
            raise ValueError("Receiver is not verified DAB-capable across scan")
        expected = self.plan(country=plan.country, region=plan.region,
                             scope=plan.scope,
                             include_13_extension=plan.include_13_extension)
        if expected.blocks != plan.blocks:
            raise ValueError("Client cannot provide arbitrary DAB frequencies")
        by_freq = {block.frequency_hz: block for block in plan.blocks}

        def forward(record: ScanRecord, completed: int, total: int) -> None:
            if on_progress is None:
                return
            block = by_freq[record.frequency_hz]
            on_progress(DabScanProgress(
                completed, total, block.channel, block.frequency_hz,
                record.state,
                len(record.services) if record.state == "service_decoded" else 0,
            ))

        # Progress callback is deliberately non-null to ensure cancellation
        # and individual frequency results are handled during ONE lock/lease.
        records = self.scanner.scan(
            receiver, tuple(block.point for block in plan.blocks),
            owner_id=owner_id, job_id=job_id, backend=backend,
            user_triggered=True, grant_token=grant_token,
            on_progress=forward,
            should_cancel=should_cancel,
        )
        return DabScanResult(owner_id, receiver.receiver_id, plan, records,
                             cancelled=len(records) < len(plan.blocks))

    @staticmethod
    def save_selected(result: DabScanResult, store: ChannelStore, *,
                      owner_id: str,
                      selected: tuple[tuple[int, str], ...],
                      mark_favorites: bool = False) -> tuple[str, ...]:
        """Only explicitly chosen *decoded services* enter persistent owner DB.

        No implicit delete or replacement of existing stations/favorites.
        Pending raw-signal/locked-mux entries cannot masquerade as services.
        """
        if not isinstance(result, DabScanResult) or owner_id != result.owner_id:
            raise PermissionError("Only the scan owner may save results")
        if type(mark_favorites) is not bool or len(selected) > 256:
            raise ValueError("Invalid save selection")
        available = {
            (record.frequency_hz, service.service_id): (record, service)
            for record in result.records if record.state == "service_decoded"
            for service in record.services
        }
        if len(selected) != len(set(selected)):
            raise ValueError("Duplicate service selection")
        if any(key not in available for key in selected):
            raise ValueError("Cannot persist a non-decoded or absent DAB service")
        return tuple(store.save(owner_id=owner_id,
                                record=available[key][0],
                                service=available[key][1],
                                favorite=mark_favorites)
                     for key in selected)
