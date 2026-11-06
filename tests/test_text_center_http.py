"""Synthetic authenticated Text Center WSGI tests; no RF or TLS listener."""
import json
import unittest
from tihulu_runtime.sdr_resource_broker import SDRResourceBroker
from tihulu_runtime.text_center_integration import TextCenterIntegration
from tihulu_runtime.text_center_http import TextCenterWSGI


class TextCenterHTTPTests(unittest.TestCase):
    def setUp(self):
        bridge = TextCenterIntegration(
            broker=SDRResourceBroker(),
            inventory=lambda: {"rtl_usb_count": 1, "connected_decoder": False},
            catalog=lambda inv: [{"id": "fm_rds", "state": "manual_capture"}])
        self.app = TextCenterWSGI(
            bridge, authorize=lambda env: env.get("test.identity"),
            allowed_hosts=frozenset({"tihulu.lan", "tihulu.local"}),
            receiver_ids=("rtl-A",))

    def request(self, path, *, method="GET", host="tihulu.lan",
                trusted=True, identity=("owner", True)):
        environ = {
            "PATH_INFO": path, "REQUEST_METHOD": method, "HTTP_HOST": host,
            "tihulu.trusted_gateway": trusted, "test.identity": identity,
        }
        response = []
        body = b"".join(self.app(
            environ, lambda status, headers: response.append((status, dict(headers)))))
        return int(response[0][0][:3]), response[0][1], json.loads(body)

    def test_owner_passive_discovery_and_nocache(self):
        code, headers, result = self.request("/text-center/api/discovery")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertFalse(result["rf_receiver_tuned"])
        self.assertEqual(result["receivers"][0]["state"], "free")

    def test_explicit_gateway_auth_owner_and_host(self):
        self.assertEqual(self.request("/text-center/api/status", trusted=False)[0], 403)
        self.assertEqual(self.request("/text-center/api/status", host="evil.example")[0], 403)
        self.assertEqual(self.request("/text-center/api/status", identity=None)[0], 401)
        self.assertEqual(
            self.request("/text-center/api/status", identity=("guest", False))[0], 403)

    def test_no_sdr_or_bbs_write_route(self):
        for path in ("/text-center/api/rds/start",
                     "/text-center/api/scans/start",
                     "/text-center/api/bulletins",
                     "/text-center/api/feeds/refresh"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path, method="POST")[0], 405)
                self.assertEqual(self.request(path)[0], 404)

    def test_passive_status_and_source_catalog(self):
        status, _, body = self.request("/text-center/api/status")
        self.assertEqual(status, 200)
        self.assertFalse(body["hardware_tuning"])
        self.assertFalse(body["standalone_ui_mounted"])
        status, _, body = self.request("/text-center/api/capabilities")
        self.assertEqual(status, 200)
        self.assertEqual(body["capabilities"][0]["id"], "fm_rds")
        self.assertFalse(body["hardware_tuning"])
        status, _, body = self.request("/text-center/api/pages")
        self.assertEqual(status, 200)
        self.assertIn("860", body["pages"])

    def test_unknown_route_and_unsafe_method(self):
        self.assertEqual(self.request("/text-center/api/not-real")[0], 404)
        self.assertEqual(self.request(
            "/text-center/api/status", method="DELETE")[0], 405)


if __name__ == "__main__":
    unittest.main()
