"""Read-only original Text Center UI mount tests: no network or RF hardware."""
from pathlib import Path
import json
import tempfile
import unittest

from tihulu_runtime.sdr_resource_broker import SDRResourceBroker
from tihulu_runtime.text_center_integration import TextCenterIntegration
from tihulu_runtime.text_center_http import TextCenterWSGI
from tihulu_runtime.text_center_portal import TextCenterPortalWSGI

SOURCE_HTML = """<!doctype html><html lang="en"><head>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/styles.css">
<script src="/assets/app.js" defer></script>
</head><body>
<div class="status-line"><span class="status-dot green"></span> Local archive ready</div>
<div class="message" id="notification" hidden></div>
<span>STANDALONE MODE • 127.0.0.1 • NO BACKGROUND POLLING</span>
</body></html>"""


class TextCenterPortalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / "installed-text-center" / "web"
        root.mkdir(parents=True)
        (root / "index.html").write_text(SOURCE_HTML, encoding="utf-8")
        (root / "styles.css").write_text(".sidebar {display:block}", encoding="utf-8")
        (root / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
        self.root = root
        bridge = TextCenterIntegration(
            broker=SDRResourceBroker(),
            inventory=lambda: {"rtl_usb_count": 0},
            catalog=lambda _: [{"id": "fm_rds", "state": "manual_capture"}])
        api = TextCenterWSGI(
            bridge, authorize=lambda env: env.get("test.identity"),
            allowed_hosts=frozenset({"tihulu.lan"}))
        self.app = TextCenterPortalWSGI(api=api, source_web_dir=root)

    def request(self, path, *, method="GET", host="tihulu.lan",
                trusted=True, identity=("owner", True)):
        environ = {
            "PATH_INFO": path, "HTTP_HOST": host, "REQUEST_METHOD": method,
            "tihulu.trusted_gateway": trusted, "test.identity": identity
        }
        results = []
        chunks = self.app(environ, lambda status, headers:
                          results.append((status, dict(headers))))
        payload = b"".join(chunks)
        return int(results[0][0][:3]), results[0][1], payload

    def test_owner_original_markup_reused_but_unsafe_js_replaced(self):
        status, headers, raw = self.request("/text-center/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b'/text-center/assets/styles.css', raw)
        self.assertIn(b'/text-center/assets/kit-mode.css', raw)
        self.assertIn(b'/text-center/assets/kit-app.js', raw)
        self.assertIn(b'id="kit-visual-mode"', raw)
        self.assertNotIn(b'src="/assets/app.js"', raw)
        self.assertNotIn(b'Local archive ready', raw)
        self.assertIn(b"READ-ONLY INTEGRATION PREVIEW", raw)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_exact_allowlisted_assets_and_original_js_is_not_served(self):
        for path, target in [
            ("/text-center/assets/styles.css", b".sidebar"),
            ("/text-center/favicon.svg", b"<svg"),
            ("/text-center/assets/kit-app.js", b"/text-center/api/"),
            ("/text-center/assets/kit-mode.css", b"kit-classic-teletext"),
        ]:
            with self.subTest(path=path):
                status, _, raw = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(target, raw)
        for path in [
            "/text-center/assets/app.js", "/text-center/assets/../index.html",
            "/text-center/../../etc/passwd", "/text-center/AGENTS.md",
            "/text-center/api/rds/start",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/text-center/")[0], 200)
        self.assertEqual(self.request("/text-center")[0], 200)

    def test_fails_closed_for_untrusted_or_missing_user(self):
        self.assertEqual(self.request("/text-center/", trusted=False)[0], 403)
        self.assertEqual(self.request("/text-center/", host="evil.example")[0], 403)
        self.assertEqual(self.request("/text-center/", identity=None)[0], 401)
        self.assertEqual(
            self.request("/text-center/", identity=("guest", False))[0], 403)

    def test_api_uses_existing_owner_only_bridge_and_no_post(self):
        status, _, raw = self.request("/text-center/api/status")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)["hardware_tuning"])
        status, _, raw = self.request("/text-center/api/capabilities")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["capabilities"][0]["id"], "fm_rds")
        for path in ("/text-center/", "/text-center/api/status",
                     "/text-center/api/rds/start", "/text-center/api/bulletins"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path, method="POST")[0], 405)

    def test_unverified_or_unsafe_source_layout_fails_closed(self):
        self.root.joinpath("index.html").write_text(
            '<html><script src="/unknown.js"></script></html>', encoding="utf-8")
        self.assertEqual(self.request("/text-center/")[0], 503)
        self.root.joinpath("index.html").unlink()
        self.assertEqual(self.request("/text-center/")[0], 503)

    def test_symlink_asset_escape_is_denied(self):
        outside = Path(self.temp.name) / "outside.css"
        outside.write_text("secret-not-served", encoding="utf-8")
        self.root.joinpath("styles.css").unlink()
        self.root.joinpath("styles.css").symlink_to(outside)
        status, _, payload = self.request("/text-center/assets/styles.css")
        self.assertEqual(status, 503)
        self.assertNotIn(b"secret-not-served", payload)


if __name__ == "__main__":
    unittest.main()
