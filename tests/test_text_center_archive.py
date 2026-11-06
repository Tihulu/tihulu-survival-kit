"""Read-only independent Text Center archive contract tests (fixture only).

Creates a clearly labeled SYNTHETIC SQLite fixture, not a real received signal.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tihulu_runtime.text_center_archive import (
    TextCenterArchive, TextArchiveUnavailable,
)


class TextArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "owner-example.db"
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE pages (
                    source_id TEXT, page INTEGER, subpage INTEGER, title TEXT,
                    body TEXT, language TEXT, received_at TEXT, station TEXT,
                    frequency_hz INTEGER, medium TEXT, provenance TEXT,
                    PRIMARY KEY(source_id,page,subpage));
                CREATE TABLE articles (
                    id TEXT PRIMARY KEY, source_name TEXT, source_url TEXT,
                    title TEXT, body TEXT, url TEXT, published_at TEXT,
                    observed_at TEXT, medium TEXT);
                CREATE TABLE events (
                    id TEXT, source_id TEXT, title TEXT, body TEXT,
                    received_at TEXT, station TEXT, language TEXT,
                    frequency_hz INTEGER, medium TEXT, provenance TEXT);
            """)
            db.execute(
                "INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("Test DAB: Köln", 451, 2, "Synthetic decoder page",
                 "FIRST LINE\nSECOND LINE", "de", "2026-11-06T00:00:00+00:00",
                 "Test-only receiver", 222_064_000, "journaline",
                 "Unit fixture, not a live RF signal"))
            db.execute(
                "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?)",
                ("a" * 32, "Example Internet Feed", "https://example.com/rss",
                 "Synthetic RSS article", "X" * 4_000,
                 "https://example.com/story", "2026-11-05T00:00:00+00:00",
                 "2026-11-06T00:00:00+00:00", "internet_feed"))
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("e" * 32, "test-sdr", "Synthetic RadioText",
                 "Hello from offline fixture", "2026-11-06T00:00:00+00:00",
                 "Test receiver", "en", 98_600_000, "fm_rds",
                 "Unit fixture, not actual broadcast"))
        self.archive = TextCenterArchive(self.path, owner_id="real-server-owner")

    def test_owner_bound_counts_and_read_only_semantics(self):
        counts = self.archive.counts(owner_id="real-server-owner")
        self.assertEqual(counts["counts"], {"pages": 1, "articles": 1, "events": 1})
        self.assertFalse(counts["received_live"])
        self.assertFalse(counts["verified_official_alert"])
        with self.assertRaises(PermissionError):
            self.archive.pages(owner_id="attacker")
        with self.assertRaises(PermissionError):
            self.archive.articles(owner_id="")
        with self.assertRaises(PermissionError):
            self.archive.page(owner_id="attacker", source_id="Test DAB: Köln", page=451)

    def test_real_source_metadata_is_preserved_without_live_claim(self):
        rows = self.archive.pages(owner_id="real-server-owner")
        self.assertEqual(rows[0]["source_id"], "Test DAB: Köln")
        self.assertEqual(rows[0]["station"], "Test-only receiver")
        self.assertEqual(rows[0]["frequency_hz"], 222_064_000)
        self.assertEqual(rows[0]["medium"], "journaline")
        self.assertFalse(rows[0]["verified_official_alert"])
        detail = self.archive.page(owner_id="real-server-owner",
                                   source_id="Test DAB: Köln", page=451, subpage=2)
        self.assertEqual(detail["body"], "FIRST LINE\nSECOND LINE")
        self.assertEqual(detail["cache_state"], "imported_not_live")
        self.assertEqual(detail["provenance"], "Unit fixture, not a live RF signal")
        self.assertIsNone(self.archive.page(owner_id="real-server-owner",
                                            source_id="Test DAB: Köln", page=451, subpage=0))

    def test_cached_articles_are_bounded_and_full_detail_remains_available(self):
        articles = self.archive.articles(owner_id="real-server-owner")
        self.assertEqual(len(articles), 1)
        self.assertEqual(len(articles[0]["excerpt"]), 1800)
        self.assertNotIn("body", articles[0])
        self.assertEqual(articles[0]["source_url"], "https://example.com/rss")
        self.assertEqual(articles[0]["cache_state"], "cached_internet")
        self.assertFalse(articles[0]["live"])
        full = self.archive.article(owner_id="real-server-owner", article_id="a" * 32)
        self.assertEqual(len(full["body"]), 4000)
        self.assertFalse(full["verified_official_alert"])
        with self.assertRaises(ValueError):
            self.archive.article(owner_id="real-server-owner",
                                 article_id="' OR 1=1 --")
        self.assertIsNone(self.archive.article(owner_id="real-server-owner",
                                               article_id="f" * 32))

    def test_events_are_attributed_not_official_or_live(self):
        rows = self.archive.events(owner_id="real-server-owner")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["medium"], "fm_rds")
        self.assertEqual(rows[0]["station"], "Test receiver")
        self.assertEqual(rows[0]["cache_state"], "imported_not_live")
        self.assertFalse(rows[0]["verified_official_alert"])
        self.assertEqual(rows[0]["excerpt"], "Hello from offline fixture")

    def test_strict_page_validation_and_read_only_sqlite(self):
        for bad in ("", "\x00", "A" * 91, None, True):
            with self.subTest(source=bad), self.assertRaises(ValueError):
                self.archive.page(owner_id="real-server-owner",
                                  source_id=bad, page=451)
        for bad in (99, 900, False, "451"):
            with self.subTest(page=bad), self.assertRaises(ValueError):
                self.archive.page(owner_id="real-server-owner",
                                  source_id="test", page=bad)
        for bad in (-1, 100, "2", False):
            with self.subTest(subpage=bad), self.assertRaises(ValueError):
                self.archive.page(owner_id="real-server-owner",
                                  source_id="test", page=451, subpage=bad)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM pages").fetchone()[0], 1)

    def test_missing_path_and_wrong_schema_do_not_create_or_migrate(self):
        missing = Path(self.tmp.name) / "not-existing.db"
        a = TextCenterArchive(missing, owner_id="real-server-owner")
        with self.assertRaises(TextArchiveUnavailable):
            a.counts(owner_id="real-server-owner")
        self.assertFalse(missing.exists())
        bad = Path(self.tmp.name) / "wrong.db"
        with sqlite3.connect(bad) as db:
            db.execute("CREATE TABLE unrelated (x TEXT)")
        other = TextCenterArchive(bad, owner_id="real-server-owner")
        with self.assertRaises(TextArchiveUnavailable):
            other.pages(owner_id="real-server-owner")
        with sqlite3.connect(bad) as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='pages'").fetchone()[0],
                0)

    def test_symlink_archive_is_denied(self):
        symlink = Path(self.tmp.name) / "shortcut.db"
        symlink.symlink_to(self.path)
        with self.assertRaises(TextArchiveUnavailable):
            TextCenterArchive(symlink, owner_id="real-server-owner").counts(
                owner_id="real-server-owner")


if __name__ == "__main__":
    unittest.main()
