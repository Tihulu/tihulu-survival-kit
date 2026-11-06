"""Authenticated real SQLite READ-only Text Center WSGI archive tests (fixtures)."""
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from urllib.parse import urlencode

from tihulu_runtime.sdr_resource_broker import SDRResourceBroker
from tihulu_runtime.text_center_integration import TextCenterIntegration
from tihulu_runtime.text_center_http import TextCenterWSGI
from tihulu_runtime.text_center_archive import TextCenterArchive


class TextCenterArchiveHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbfile = Path(self.tmp.name) / "trusted-owner-text.db"
        with sqlite3.connect(self.dbfile) as db:
            db.executescript("""
              CREATE TABLE pages (source_id TEXT, page INTEGER, subpage INTEGER,
                title TEXT, body TEXT, language TEXT, received_at TEXT,
                station TEXT, frequency_hz INTEGER, medium TEXT, provenance TEXT);
              CREATE TABLE articles (id TEXT PRIMARY KEY, source_name TEXT,
                source_url TEXT, title TEXT, body TEXT, url TEXT,
                published_at TEXT, observed_at TEXT, medium TEXT);
              CREATE TABLE events (source_id TEXT, title TEXT, body TEXT,
                received_at TEXT, station TEXT, language TEXT,
                frequency_hz INTEGER, medium TEXT, provenance TEXT);
            """)
            db.execute("INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       ("Test DAB: Köln", 451, 2, "Fake fixture only",
                        "Original\nTwo lines", "de", "2026-11-06T00:00:00+00:00",
                        "Test receiver", 222064000, "journaline",
                        "Unit test import, NOT live data"))
            db.execute("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?)",
                       ("f" * 32, "Test RSS Feed", "https://example.org/rss",
                        "Fake cached article", "Cached contents",
                        "https://example.org/story", "2026-11-05", "2026-11-06",
                        "internet_feed"))
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
                       ("fixture-sdr", "Radio text", "Not actually received",
                        "2026-11-06T00:00:00+00:00", "Test receiver", "en",
                        98600000, "fm_rds", "Synthetic fixture"))
        self.archive = TextCenterArchive(self.dbfile, owner_id="ownerA")
        self.api = TextCenterWSGI(
            TextCenterIntegration(broker=SDRResourceBroker(),
                inventory=lambda: {"rtl_usb_count": 0},
                catalog=lambda _: []),
            authorize=lambda env: env.get("test.identity"),
            allowed_hosts=frozenset({"tihulu.lan"}), archive=self.archive)

    def request(self, route, *, params=None, method="GET",
                identity=("ownerA", True), trusted=True):
        started = []
        raw = self.api({
            "PATH_INFO": route,
            "QUERY_STRING": urlencode(params) if isinstance(params, dict) else (params or ""),
            "REQUEST_METHOD": method, "HTTP_HOST": "tihulu.lan",
            "tihulu.trusted_gateway": trusted,
            "test.identity": identity,
        }, lambda status, headers: started.append((status, dict(headers))))
        return int(started[0][0][:3]), started[0][1], json.loads(b"".join(raw))

    def test_read_only_original_cached_metadata_and_detail(self):
        status, headers, counts = self.request("/text-center/api/archive/status")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(counts["counts"]["pages"], 1)
        status, _, pages = self.request("/text-center/api/archive/pages")
        self.assertEqual(status, 200)
        self.assertFalse(pages["live"])
        self.assertEqual(pages["items"][0]["source_id"], "Test DAB: Köln")
        status, _, page = self.request("/text-center/api/archive/page",
            params={"source_id": "Test DAB: Köln", "number": "451", "subpage": "2"})
        self.assertEqual(status, 200)
        self.assertEqual(page["body"], "Original\nTwo lines")
        self.assertFalse(page["verified_official_alert"])
        self.assertEqual(page["provenance"], "Unit test import, NOT live data")
        status, _, articles = self.request("/text-center/api/archive/articles")
        self.assertEqual(status, 200)
        self.assertEqual(articles["items"][0]["cache_state"], "cached_internet")
        self.assertNotIn("body", articles["items"][0])
        status, _, article = self.request("/text-center/api/archive/article",
                                          params={"id": "f"*32})
        self.assertEqual(status, 200)
        self.assertEqual(article["body"], "Cached contents")
        status, _, events = self.request("/text-center/api/archive/events")
        self.assertEqual(status, 200)
        self.assertEqual(events["items"][0]["medium"], "fm_rds")
        self.assertFalse(events["items"][0]["verified_official_alert"])

    def test_reject_all_mutations_and_wrong_owner(self):
        for endpoint in ("status", "pages", "page", "articles", "article", "events"):
            with self.subTest(endpoint=endpoint):
                path = "/text-center/api/archive/" + endpoint
                self.assertEqual(self.request(path, method="POST")[0], 405)
                self.assertEqual(self.request(path, identity=None)[0], 401)
                self.assertEqual(self.request(path, trusted=False)[0], 403)
                self.assertEqual(self.request(path, identity=("other", True))[0], 403)
        self.assertEqual(self.request("/text-center/api/archive/unknown")[0], 404)

    def test_parameter_validation_and_missing_content(self):
        path = "/text-center/api/archive/page"
        for params in (
            "", "number=451", "source_id=test&number=451&number=452",
            "source_id=hello&number=9999", "source_id=hello&number=abc",
            "source_id=hello&number=451&subpage=102",
            "source_id=hello&number=451&subpage=2&noise=1&noise2=2",
        ):
            with self.subTest(query=params):
                self.assertEqual(self.request(path, params=params)[0], 400 if
                    params not in ("source_id=hello&number=451&subpage=2&noise=1&noise2=2",)
                    else 400)
        self.assertEqual(self.request(path, params={"source_id":"not-seen","number":"451"})[0], 404)
        self.assertEqual(self.request("/text-center/api/archive/article",
                                      params={"id": "' UNION SELECT * FROM pages"})[0], 400)
        self.assertEqual(self.request("/text-center/api/archive/article",
                                      params={"id": "a"*32})[0], 404)
        self.assertEqual(self.request("/text-center/api/archive/page",
                                      params="source_id=x&number=451&x=1&y=2&z=3")[0], 400)

    def test_missing_optional_archive_fails_closed(self):
        api = TextCenterWSGI(
            TextCenterIntegration(broker=SDRResourceBroker(),
                                  inventory=lambda: {}, catalog=lambda _: []),
            authorize=lambda _: ("ownerA", True),
            allowed_hosts=frozenset({"tihulu.lan"}))
        recorded = []
        result = api({
            "tihulu.trusted_gateway": True, "HTTP_HOST": "tihulu.lan",
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/text-center/api/archive/pages"
        }, lambda code, headers: recorded.append(code))
        self.assertEqual(recorded[0][:3], "503")
        self.assertIn(b"not configured", b"".join(result))


if __name__ == "__main__":
    unittest.main()
