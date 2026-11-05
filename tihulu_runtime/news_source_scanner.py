# SPDX-License-Identifier: AGPL-3.0-only
"""User-selected News inputs and scan scheduling boundary.

No hardware backend is installed here. Do not present a declared source or
a purchased DVB receiver as a working radio/teletext broadcast or news feed.
A trusted HTTPS/owner-auth API must authorize requests before using this code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Mapping, Protocol
import json


MEDIA = frozenset({"internet", "tv_antenna", "radio_antenna"})
TV_TYPES = frozenset({"dvb_teletext", "dvb_si_epg"})
RADIO_TYPES = frozenset({"dab_data", "fm_rds", "amateur_ax25_aprs"})


@dataclass(frozen=True)
class NewsInput:
    id: str
    name: str
    medium: str
    category: str
    country: str
    verified: bool = False


@dataclass(frozen=True)
class InputPreferences:
    """Unchecked sources and unchecked transports never initiate a scan."""
    enabled_media: frozenset[str] = frozenset({"internet"})
    selected_source_ids: frozenset[str] = frozenset()
    country: str = "DE"
    # No automatic or background RF scans, even if optional Background ON later.
    scan_on_open: bool = False


@dataclass(frozen=True)
class ScanContext:
    """Derived by a trusted server from actual probes and protected task state."""
    internet_available: bool = False
    dvb_receiver_ready: bool = False
    radio_receiver_ready: bool = False
    active_tv_recording: bool = False
    # This can only be set by a tested same-multiplex demultiplexer.
    verified_same_mux_no_retune: bool = False


@dataclass(frozen=True)
class ScanResult:
    source_id: str
    medium: str
    state: str
    explanation: str
    entries_found: int = 0


class NewsInputAdapter(Protocol):
    """Future real adapter: validated Internet API, DVB Teletext or SDR decoder.

    The adapter must verify broadcast PID/decoded page or data framing, identity,
    network rights and its result origin. This prototype supplies no adapters.
    """
    def scan(self, source: NewsInput) -> int: ...


class NewsSourceRouter:
    """Generates explicit source scan outcomes. Never silently tunes/transmits.

    The caller must keep user-scoped preferences/private credentials outside the
    public shared catalog and pass measured hardware state into ScanContext.
    The source list below is candidates, NOT verified live channels.
    """

    def __init__(self, inputs: list[NewsInput]):
        if len({src.id for src in inputs}) != len(inputs):
            raise ValueError("Source IDs must be unique")
        if any(src.medium not in MEDIA for src in inputs):
            raise ValueError("Unknown scan transport")
        self.inputs = {src.id: src for src in inputs}
        self._scan_lock = RLock()

    @classmethod
    def from_project_catalogs(cls, directory: str | Path) -> "NewsSourceRouter":
        directory = Path(directory)
        news = json.loads((directory / "news_sources_candidates.json").read_text(encoding="utf-8"))
        radio = json.loads((directory / "radio_text_networks.json").read_text(encoding="utf-8"))
        result: list[NewsInput] = []
        for row in news["sources"]:
            # Never trust an unverified candidate as a known reachable Internet URL.
            result.append(NewsInput(
                "internet:" + row["id"], row["name"], "internet",
                row["kind"], row["country"], verified=False,
            ))
        for row in radio["services"]:
            medium = ("tv_antenna" if row["data_type"] in TV_TYPES
                      else "radio_antenna" if row["data_type"] in RADIO_TYPES
                      else None)
            if medium is not None:
                result.append(NewsInput(
                    medium + ":" + row["id"], row["name"], medium,
                    row["data_type"], row.get("country", "ALL"),
                    verified=False,
                ))
        return cls(result)

    def available_sources(self, *, medium: str | None = None, country: str | None = None
                          ) -> list[NewsInput]:
        if medium is not None and medium not in MEDIA:
            raise ValueError("Unknown source medium")
        return [s for s in self.inputs.values() if
                (medium is None or s.medium == medium) and
                (country is None or s.country in (country, "ALL", "WORLD"))]

    def scan(self, selection: InputPreferences, context: ScanContext,
             *, user_triggered: bool = False,
             adapters: Mapping[str, NewsInputAdapter] | None = None
             ) -> list[ScanResult]:
        """A scan only happens on explicit user action. Background is always OFF.

        No implicit tuner retune, automatic RF transmit, or network scraping.
        Adapterless prototype returns honest 'integration_missing' statuses.
        """
        if not user_triggered:
            raise PermissionError("Source scan needs an explicit user action")
        if not selection.enabled_media.issubset(MEDIA):
            raise ValueError("Unrecognized medium")
        if not selection.selected_source_ids.issubset(self.inputs):
            raise ValueError("Unknown selected source")
        if selection.country not in ("DE", "TR", "ALL"):
            raise ValueError("Unsupported regional profile")
        adapters = adapters or {}
        # Never run two explicit source scans concurrently against one tuner.
        with self._scan_lock:
            results: list[ScanResult] = []
            for source_id in sorted(selection.selected_source_ids):
                src = self.inputs[source_id]
                if src.medium not in selection.enabled_media:
                    continue
                # Region does not auto-certify availability: do not look for an
                # unselected country's local terrestrial broadcast.
                if src.medium != "internet" and selection.country != "ALL" and (
                        src.country not in ("ALL", selection.country)):
                    results.append(ScanResult(src.id, src.medium, "region_mismatch",
                                              "Select the local broadcast region first"))
                    continue
                if src.medium == "tv_antenna" and not context.dvb_receiver_ready:
                    results.append(ScanResult(src.id, src.medium, "hardware_unavailable",
                                              "A real connected and supported DVB tuner is required"))
                    continue
                if src.medium == "radio_antenna" and not context.radio_receiver_ready:
                    results.append(ScanResult(src.id, src.medium, "hardware_unavailable",
                                              "A separate supported radio SDR/receiver is required"))
                    continue
                if (src.medium == "tv_antenna" and context.active_tv_recording
                        and not context.verified_same_mux_no_retune):
                    results.append(ScanResult(src.id, src.medium, "recording_protected",
                                              "No retuning while a TV recording holds the tuner"))
                    continue
                if src.medium == "internet" and not context.internet_available:
                    results.append(ScanResult(src.id, src.medium, "offline",
                                              "Internet input selected, but no connectivity"))
                    continue
                # No adapters (or unverified source endpoints): never imply the
                # service was actually scanned or actual content was received.
                if not src.verified:
                    results.append(ScanResult(src.id, src.medium, "source_unverified",
                                              "Candidate source; verify actual feed or broadcast service before scanning"))
                    continue
                adapter = adapters.get(src.medium)
                if adapter is None:
                    results.append(ScanResult(src.id, src.medium, "integration_missing",
                                              "Decoder/feed backend is not installed"))
                    continue
                try:
                    count = adapter.scan(src)
                    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                        raise ValueError("Adapter returned an invalid item count")
                except Exception:
                    # Do not expose private endpoint URLs or secrets via error text.
                    results.append(ScanResult(src.id, src.medium, "scan_failed",
                                              "Backend scan failed; check logs and tuner/network permissions"))
                else:
                    results.append(ScanResult(src.id, src.medium, "checked",
                                              "Verified backend checked this source", count))
            return results
