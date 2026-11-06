# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only existing independent Text Center SQLite archive integration.

No Store() constructor: the independent class would create/alter the DB schema.
No DB migration, network request, radio tune, feed refresh or write permission.
A single trusted device owner is bound explicitly until verified per-user ACL
and separate SQLite ownership are implemented.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import stat
from typing import Iterator

MAX_PAGE_ITEMS = 60
MAX_ARTICLE_ITEMS = 30
MAX_EVENTS = 40
SOURCE_PATTERN = re.compile(r"[^\x00-\x1f\x7f]{1,90}\Z")
ARTICLE_ID = re.compile(r"[a-f0-9]{32}\Z", re.ASCII)

# Verify the exact contract needed to interpret independent imported data.
REQUIRED_COLUMNS = {
    "pages": {"source_id", "page", "subpage", "title", "body", "language",
              "received_at", "station", "frequency_hz", "medium", "provenance"},
    "events": {"source_id", "title", "body", "received_at", "station",
               "language", "frequency_hz", "medium", "provenance"},
    "articles": {"id", "source_name", "source_url", "title", "body", "url",
                 "published_at", "observed_at", "medium"},
}


class TextArchiveUnavailable(RuntimeError):
    """Read-only local source is absent or its schema is incompatible."""


class TextCenterArchive:
    """A read-only local archive for exactly one verified Tihulu owner.

    Configuring archive owner/path is a trusted deployment/administrator action,
    never a URL parameter, browser header, or user-selected file path. Other
    accounts must NOT be allowed to read this legacy single-owner database.
    """

    def __init__(self, db_file: str | Path, *, owner_id: str):
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("Verified owner ID must be configured")
        self.owner_id = owner_id
        self.db_file = Path(db_file).expanduser()
        if not self.db_file.is_absolute():
            raise ValueError("Archive path must be absolute")

    def _require_owner(self, owner_id: str) -> None:
        if owner_id != self.owner_id:
            raise PermissionError("Text Center archive owner mismatch")

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        try:
            # Fail closed; no new DB, no symlink redirection and no migration.
            path_stat = self.db_file.lstat()
            if not stat.S_ISREG(path_stat.st_mode):
                raise TextArchiveUnavailable("Configured archive is not a regular SQLite file")
            uri = self.db_file.as_uri() + "?mode=ro"
            db = sqlite3.connect(uri, uri=True, timeout=1.0)
        except (OSError, sqlite3.Error) as exc:
            raise TextArchiveUnavailable("Independent Text Center archive unavailable") from exc
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA busy_timeout=1000")
            db.execute("PRAGMA trusted_schema=OFF")
            for table, required in REQUIRED_COLUMNS.items():
                # The SQL table identifier is from a fixed constant, not input.
                existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                if not required.issubset(existing):
                    raise TextArchiveUnavailable(
                        "Independent Text Center archive schema is incompatible")
            yield db
        except sqlite3.Error as exc:
            raise TextArchiveUnavailable("Read-only Text Center query failed") from exc
        finally:
            db.close()

    def counts(self, *, owner_id: str) -> dict:
        self._require_owner(owner_id)
        with self._read() as db:
            counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                      for name in REQUIRED_COLUMNS}
        return {"status": "read_only", "source": "independent_textcenter_sqlite",
                "received_live": False, "verified_official_alert": False,
                "counts": counts}

    def pages(self, *, owner_id: str) -> list[dict]:
        """Return only bounded index metadata, no unverified live status."""
        self._require_owner(owner_id)
        with self._read() as db:
            rows = db.execute(
                "SELECT source_id, page, subpage, title, language, received_at,"
                " station, frequency_hz, medium, provenance"
                " FROM pages ORDER BY received_at DESC LIMIT ?",
                (MAX_PAGE_ITEMS,)).fetchall()
            return [dict(row) | {"cache_state": "imported_not_live",
                                 "verified_official_alert": False} for row in rows]

    def page(self, *, owner_id: str, source_id: str,
             page: int, subpage: int = 0) -> dict | None:
        self._require_owner(owner_id)
        if not isinstance(source_id, str) or not SOURCE_PATTERN.fullmatch(source_id):
            raise ValueError("Invalid broadcast source ID")
        if type(page) is not int or not 100 <= page <= 899:
            raise ValueError("Page number must be 100-899")
        if type(subpage) is not int or not 0 <= subpage <= 99:
            raise ValueError("Subpage must be 0-99")
        with self._read() as db:
            row = db.execute(
                "SELECT source_id, page, subpage, title, body, language,"
                " received_at, station, frequency_hz, medium, provenance"
                " FROM pages WHERE source_id=? AND page=? AND subpage=?",
                (source_id, page, subpage)).fetchone()
            return (dict(row) | {"cache_state": "imported_not_live",
                                 "verified_official_alert": False}
                    if row else None)

    def articles(self, *, owner_id: str) -> list[dict]:
        """Read existing cached Internet articles without initiating RSS fetch."""
        self._require_owner(owner_id)
        with self._read() as db:
            rows = db.execute(
                "SELECT id, source_name, source_url, title, substr(body,1,1800) AS excerpt, url,"
                " published_at, observed_at, medium FROM articles"
                " ORDER BY observed_at DESC LIMIT ?",
                (MAX_ARTICLE_ITEMS,)).fetchall()
            # Retain publisher, original timestamps and medium; a cache is not
            # a live request or a corroborated current headline.
            return [dict(row) | {"cache_state": "cached_internet",
                                 "live": False, "verified_official_alert": False}
                    for row in rows]

    def events(self, *, owner_id: str) -> list[dict]:
        """Source-attributed receiver imports, never official alert claims."""
        self._require_owner(owner_id)
        with self._read() as db:
            rows = db.execute(
                "SELECT source_id, title, substr(body,1,1800) AS excerpt, received_at, station,"
                " language, frequency_hz, medium, provenance FROM events"
                " ORDER BY received_at DESC LIMIT ?",
                (MAX_EVENTS,)).fetchall()
            return [dict(row) | {"cache_state": "imported_not_live",
                                 "verified_official_alert": False}
                    for row in rows]

    def article(self, *, owner_id: str, article_id: str) -> dict | None:
        """Fetch the full original saved Internet article by its source ID."""
        self._require_owner(owner_id)
        if not isinstance(article_id, str) or not ARTICLE_ID.fullmatch(article_id):
            raise ValueError("Invalid cached article ID")
        with self._read() as db:
            row = db.execute(
                "SELECT id, source_name, source_url, title, body, url,"
                " published_at, observed_at, medium"
                " FROM articles WHERE id=?", (article_id,)).fetchone()
            return (dict(row) | {"cache_state": "cached_internet",
                                 "live": False, "verified_official_alert": False}
                    if row else None)
