# SPDX-License-Identifier: AGPL-3.0-only
"""welle-cli transport tests use fake localhost HTTP and synthetic payloads."""
from __future__ import annotations

import json
import struct
import unittest

from tihulu_runtime.welle_local import WelleLocalReader, WelleLocalError


class FakeResponse:
    def __init__(self, data=b"", status=200, length=None):
        self.payload = data
        self.status = status
        self.length = length

    def getheader(self, name):
        if name == "Content-Length":
            return self.length
        return None

    def read(self, length):
        return self.payload[:length]


class FakeConnection:
    def __init__(self, host, port, *, timeout, fixtures, calls):
        self.calls, self.fixtures = calls, fixtures
        self.calls.append(("construct", host, port, timeout))
        self.path = None

    def request(self, method, path, headers=None):
        self.path = path
        self.calls.append(("request", method, path))

    def getresponse(self):
        return self.fixtures[self.path]

    def close(self):
        self.calls.append(("close",))


def reader(fixtures):
    calls = []
    def factory(host, port, *, timeout):
        return FakeConnection(host, port, timeout=timeout, fixtures=fixtures, calls=calls)
    return WelleLocalReader(connection_factory=factory), calls


class WelleLocalReaderTests(unittest.TestCase):
    def test_inert_until_read_and_only_loopback(self):
        sample, calls = reader({"/channel": FakeResponse(b"11D\n")})
        self.assertFalse(calls)
        self.assertEqual(sample.channel(), "11D")
        self.assertEqual(calls[0][:3], ("construct", "127.0.0.1", 7979))
        self.assertEqual(calls[1], ("request", "GET", "/channel"))
        self.assertEqual(calls[-1], ("close",))

    def test_port_and_timeout_validation(self):
        for opts in ({"port": 80}, {"port": 999999},
                     {"timeout": 0}, {"timeout": 50},
                     {"port": "7979"}):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                WelleLocalReader(**opts)

    def test_channel_does_not_claim_rf_lock(self):
        sample, _ = reader({"/channel": FakeResponse(b"5C")})
        self.assertEqual(sample.channel(), "5C")
        sample2, _ = reader({"/channel": FakeResponse(b"<script>bad</script>")})
        with self.assertRaises(WelleLocalError):
            sample2.channel()

    def test_metadata_tagged_as_decoder_report_only(self):
        body = json.dumps({"ensemble": "fake", "services": []}).encode()
        sample, _ = reader({"/mux.json": FakeResponse(body)})
        out = sample.mux()
        self.assertTrue(out["decoder_reported"])
        self.assertFalse(out["physical_rf_validated_by_tihulu"])
        self.assertEqual(out["ensemble_data"]["services"], [])

    def test_metadata_bad_json_rejected(self):
        for body in (b"not json", b"[1,2]", b'{"x": NaN}'):
            sample, _ = reader({"/mux.json": FakeResponse(body)})
            with self.subTest(body=body), self.assertRaises(WelleLocalError):
                sample.mux()

    def test_spectrum_little_endian_and_finite(self):
        sample, _ = reader({"/spectrum": FakeResponse(struct.pack("<fff", 1.5, 0, -2))})
        self.assertEqual(sample.samples("/spectrum"), (1.5, 0.0, -2.0))
        bad, _ = reader({"/spectrum": FakeResponse(struct.pack("<f", float("nan")))})
        with self.assertRaises(WelleLocalError):
            bad.samples("/spectrum")

    def test_wrong_frming_and_oversized_rejected(self):
        for payload in (b"", b"123", b"x" * 65540):
            sample, _ = reader({"/spectrum": FakeResponse(payload)})
            with self.subTest(length=len(payload)), self.assertRaises(WelleLocalError):
                sample.samples("/spectrum")

    def test_no_remote_urls_channel_post_or_stream_access(self):
        sample, calls = reader({})
        for path in ("http://example.com", "/channel?set=11D", "/mp3/1234",
                     "/fic", "/status", "/"):
            with self.subTest(path=path), self.assertRaises(PermissionError):
                sample._get(path)
        self.assertEqual(calls, [])

    def test_error_http_and_large_response_fail_closed(self):
        for response in (FakeResponse(status=302), FakeResponse(length="262145"),
                         FakeResponse(length="abc"), FakeResponse(b"x" * 262145)):
            sample, _ = reader({"/mux.json": response})
            with self.assertRaises(WelleLocalError):
                sample.mux()

    def test_complete_expert_snapshot_is_opt_in(self):
        readings = struct.pack("<ff", 2.0, 3.0)
        sample, calls = reader({
            "/channel": FakeResponse(b"11D"),
            "/mux.json": FakeResponse(b'{"label":"mock"}'),
            "/spectrum": FakeResponse(readings),
            "/constellation": FakeResponse(readings),
            "/impulseresponse": FakeResponse(readings),
        })
        self.assertFalse(calls)
        out = sample.expert_snapshot()
        self.assertEqual(out["status"], "decoder_reported_not_independently_rf_verified")
        self.assertEqual(out["channel"], "11D")
        self.assertEqual(out["rf_spectrum"], (2.0, 3.0))
        self.assertEqual(len([c for c in calls if c[0] == "request"]), 5)


if __name__ == "__main__":
    unittest.main()
