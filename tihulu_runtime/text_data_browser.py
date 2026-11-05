# SPDX-License-Identifier: AGPL-3.0-only
"""Text/Data portal navigation: DVB Teletext pages vs true interactive sites.

No DVB decoder, remote-login proxy or Tihulu BBS server is bundled here.
Trusted content and page metadata must come from a separately authorized,
actual frontend/decoder. Text processing may reuse news_assist shared workers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from urllib.parse import urlparse

from .news_assist import NewsText
from .news_source_scanner import InputPreferences


@dataclass(frozen=True)
class TextPortal:
    id: str
    title: str
    transport: str
    interactive: bool
    requires_internet: bool
    availability: str
    link: str | None
    starting_page: int | None


@dataclass(frozen=True)
class BroadcastTextPage:
    source_id: str
    page_number: int
    subpage: int
    title: str
    content: str
    language: str
    received_at: str
    station: str
    frequency_hz: int
    linked_pages: tuple[int, ...] = ()


class TextDataNavigator:
    """Strict local Teletext page logic and external HTTPS portal listing."""

    def __init__(self, portals: list[TextPortal]):
        if len({p.id for p in portals}) != len(portals):
            raise ValueError("Duplicate portal ID")
        for p in portals:
            if p.transport == "web_https":
                parsed = urlparse(p.link or "")
                if parsed.scheme != "https" or not parsed.netloc or parsed.username:
                    raise ValueError("Untrusted portal URL")
            elif p.link is not None:
                raise ValueError("Non-web portals cannot declare remote links")
            if p.transport == "dvb_teletext" and p.interactive:
                raise ValueError("Broadcast Teletext is receive-only")
        self.portals={p.id:p for p in portals}

    @classmethod
    def from_json(cls, filename: str | Path) -> "TextDataNavigator":
        data = json.loads(Path(filename).read_text(encoding="utf-8"))
        return cls([
            TextPortal(id=p["id"],title=p["title"],transport=p["transport"],
                       interactive=p["interactive"],
                       requires_internet=p["requires_internet"],
                       availability=p["availability"],link=p.get("link"),
                       starting_page=p.get("starting_page"))
            for p in data["portals"]
        ])

    @staticmethod
    def validate_page_number(page: int, subpage: int = 0) -> None:
        if not (type(page) is int and 100 <= page <= 899 and
                type(subpage) is int and 0 <= subpage <= 99):
            raise ValueError("Teletext page must be 100-899; subpage 0-99")

    @classmethod
    def open_page(cls, decoded: BroadcastTextPage, *,
                  chosen_page: int, chosen_subpage: int = 0) -> BroadcastTextPage:
        """Only display when the real decoder returned this requested page.

        This does not send commands to the broadcast station and cannot
        perform messaging through a one-way DVB receiver.
        """
        cls.validate_page_number(chosen_page, chosen_subpage)
        if (decoded.page_number != chosen_page or
                decoded.subpage != chosen_subpage or not decoded.content.strip()
                or not decoded.received_at or not decoded.station
                or not decoded.source_id or decoded.frequency_hz <= 0):
            raise RuntimeError("Requested page is not available from a real decoder")
        return decoded

    @classmethod
    def linked_page_numbers(cls, current: BroadcastTextPage) -> tuple[int, ...]:
        for page in current.linked_pages:
            cls.validate_page_number(page)
        return current.linked_pages

    @staticmethod
    def browser_url(portal: TextPortal) -> str:
        if portal.transport != "web_https" or not portal.link:
            raise RuntimeError("Portal cannot be opened as a browser website")
        return portal.link

    @staticmethod
    def to_news_text(decoded: BroadcastTextPage) -> NewsText:
        """Normalize actual broadcast text for the shared Translator/AI.

        No claim that an arbitrary Teletext page is independent journalism.
        Caller must have explicit selection/auth and content-rights approval.
        """
        TextDataNavigator.open_page(decoded,chosen_page=decoded.page_number,
                                     chosen_subpage=decoded.subpage)
        return NewsText(
            item_id=f"{decoded.source_id}:{decoded.page_number}:{decoded.subpage}:{decoded.received_at}",
            source_id="tv_antenna:"+decoded.source_id,
            medium="tv_antenna",title=decoded.title,
            original_text=decoded.content,language=decoded.language,
            published_at=decoded.received_at,
            provenance=f"DVB {decoded.station}, {decoded.frequency_hz} Hz, "
                       f"Teletext page {decoded.page_number}/{decoded.subpage}",
            source_type="broadcast_teletext",source_locator=str(decoded.page_number),
        )

    @staticmethod
    def selection_for_page(page: NewsText, *,
                           enabled_media: frozenset[str] = frozenset({"tv_antenna"})
                           ) -> InputPreferences:
        """Helper; authenticated owner/source consent still required upstream."""
        if "tv_antenna" not in enabled_media:
            raise PermissionError("TV input not selected")
        return InputPreferences(enabled_media=enabled_media,
                                selected_source_ids=frozenset({page.source_id}),
                                country="ALL")
