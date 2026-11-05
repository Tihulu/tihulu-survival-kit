# SPDX-License-Identifier: AGPL-3.0-only
"""Shared TV/Radio/Text Explorer channel-list facade (backend only).

Saved channels are one per-owner database, not separate inconsistent lists.
This facade assumes owner_id was derived from a real authenticated session.
"""
from __future__ import annotations
from dataclasses import dataclass
from .channel_explorer import (
    DVB_MODES, ChannelExplorer, ChannelStore, DetectedService,
    FrequencyLibrary, Receiver, ReceiverBackend, ScanRecord, TunePoint,
)

TV_FILTER=frozenset({"tv","teletext","data"})
RADIO_MODES=frozenset({"fm","dab","am","hf","nfm","usb","lsb"})


@dataclass(frozen=True)
class AppScanSummary:
    app: str
    scanned_frequencies: int
    decoded_services: int
    signal_only_count: int
    unavailable_count: int


class SharedChannelWorkspace:
    """TV and Radio use the *same* frequency plans, tuner locks and saved list."""

    def __init__(self, library: FrequencyLibrary, store: ChannelStore,
                 explorer: ChannelExplorer | None = None):
        self.library=library
        self.store=store
        self.explorer=explorer or ChannelExplorer()

    @staticmethod
    def _accept(app: str, mode: str, service_kind: str = "") -> bool:
        if app=="all":
            return True
        if app=="tv":
            return mode in DVB_MODES and service_kind != "radio"
        if app=="radio":
            return mode in RADIO_MODES or (
                mode in DVB_MODES and service_kind=="radio")
        if app=="text":
            return mode in DVB_MODES and service_kind in ("data","teletext")
        raise ValueError("App must be tv, radio, text or all")

    def saved(self, *, owner_id: str, app: str = "all",
              favorites_only: bool = False) -> list[dict]:
        records=self.store.list(owner_id=owner_id,only_favorites=favorites_only)
        return [r for r in records
                if self._accept(app,r["mode"],r["content_kind"])]

    def presets(self, *, country: str | None = None, app: str = "all") -> list:
        if app not in ("tv","radio","text","all"):
            raise ValueError("Unknown app")
        return [p for p in self.library.list_presets(country=country)
                if (app in ("all","text") or self._accept(
                    app,p.kind,"data" if app=="text" else "")) and
                (app != "text" or p.kind in DVB_MODES)]

    def scan_presets(self, *, owner_id: str, app: str, preset_ids: list[str],
                     receiver: Receiver, backend: ReceiverBackend | None = None,
                     user_triggered: bool = False,
                     save_discoveries: bool = False) -> tuple[ScanRecord,...]:
        if not owner_id:
            raise PermissionError("Authenticated owner required")
        # Reject cross-app / wrong-kind preset requests *before* touching tuner.
        for preset_id in preset_ids:
            p=self.library.presets[preset_id]
            if not (app=="all" or self._accept(app,p.kind,"data" if app=="text" else "")):
                raise ValueError("Preset incompatible with this application")
        points=self.library.preset_points(preset_ids)
        results=self.explorer.scan(receiver,points,backend=backend,
                                   user_triggered=user_triggered)
        if save_discoveries:
            for r in results:
                if r.state=="service_decoded":
                    for service in r.services:
                        self.store.save(owner_id=owner_id,record=r,service=service)
                elif r.state in ("signal_locked","energy_only"):
                    self.store.save(owner_id=owner_id,record=r)
        return results

    def scan_band(self, *, owner_id: str, app: str, band_id: str,
                  receiver: Receiver, page: int = 0,
                  page_size: int = 128, backend: ReceiverBackend | None = None,
                  user_triggered: bool = False) -> tuple[ScanRecord,...]:
        if not owner_id:
            raise PermissionError("Authenticated owner required")
        b=self.library.bands[band_id]
        if app!="all" and not self._accept(app,b.kind,"data" if app=="text" else ""):
            raise ValueError("Band not compatible with application")
        if app=="text" and b.kind not in DVB_MODES:
            raise ValueError("Teletext needs DVB broadcast data")
        return self.explorer.scan(receiver,self.library.band_points(band_id,page=page,
                                   page_size=page_size),backend=backend,
                                   user_triggered=user_triggered)

    def tune_saved(self, *, owner_id: str, channel_key: str, receiver: Receiver,
                   offset_hz: int = 0,
                   backend: ReceiverBackend | None = None,
                   user_triggered: bool = False) -> ScanRecord:
        records=[r for r in self.store.list(owner_id=owner_id)
                 if r["key"]==channel_key]
        if not records:
            raise KeyError("Saved channel not found for user")
        ch=records[0]
        return self.explorer.manual_tune(
            receiver,mode=ch["mode"],frequency_hz=ch["frequency_hz"],
            fine_offset_hz=offset_hz,backend=backend,user_triggered=user_triggered)
