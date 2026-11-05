# SPDX-License-Identifier: AGPL-3.0-only
"""Explicit News Internet/TV/Radio source-selection and scan-safety tests."""
import unittest
from pathlib import Path

from tihulu_runtime.news_source_scanner import (
    InputPreferences, NewsInput, NewsSourceRouter, ScanContext
)


ROOT = Path(__file__).resolve().parents[1] / "data"


class FakeAdapter:
    def __init__(self, count=2):
        self.count = count
        self.calls = []

    def scan(self, source):
        self.calls.append(source.id)
        return self.count


class SourceInputTests(unittest.TestCase):
    def setUp(self):
        self.router = NewsSourceRouter.from_project_catalogs(ROOT)
        self.internet = self.router.available_sources(medium="internet")
        self.tv = self.router.available_sources(medium="tv_antenna")
        self.radio = self.router.available_sources(medium="radio_antenna")

    def test_default_internet_only_and_no_sources_automatically_selected(self):
        defaults = InputPreferences()
        self.assertEqual(defaults.enabled_media, frozenset({"internet"}))
        self.assertEqual(defaults.selected_source_ids, frozenset())
        self.assertFalse(defaults.scan_on_open)
        self.assertGreater(len(self.internet), 60)
        self.assertTrue(self.tv)
        self.assertTrue(self.radio)

    def test_selected_off_media_are_not_scanned(self):
        ids = frozenset({self.internet[0].id, self.tv[0].id, self.radio[0].id})
        selected = InputPreferences(selected_source_ids=ids)
        r = self.router.scan(selected, ScanContext(internet_available=True),
                             user_triggered=True)
        self.assertEqual([x.source_id for x in r], [self.internet[0].id])

    def test_no_user_action_no_scan(self):
        with self.assertRaises(PermissionError):
            self.router.scan(InputPreferences(
                selected_source_ids=frozenset({self.internet[0].id})),
                ScanContext(internet_available=True))

    def test_absent_hardware_and_offline_are_reported(self):
        ids = frozenset({self.internet[0].id, self.tv[0].id, self.radio[0].id})
        selected = InputPreferences(enabled_media=frozenset(
            {"internet", "tv_antenna", "radio_antenna"}),
            selected_source_ids=ids)
        result = self.router.scan(selected, ScanContext(), user_triggered=True)
        states = {r.medium:r.state for r in result}
        self.assertEqual(states["internet"], "offline")
        self.assertEqual(states["tv_antenna"], "hardware_unavailable")
        self.assertEqual(states["radio_antenna"], "hardware_unavailable")

    def test_tv_scan_cannot_retune_recording(self):
        source = next(x for x in self.tv if x.country == "DE")
        selected = InputPreferences(enabled_media=frozenset({"tv_antenna"}),
                                    selected_source_ids=frozenset({source.id}))
        result = self.router.scan(selected,
               ScanContext(dvb_receiver_ready=True, active_tv_recording=True),
               user_triggered=True)
        self.assertEqual(result[0].state, "recording_protected")

    def test_dvb_tuner_does_not_count_as_radio_receiver(self):
        source = next(x for x in self.radio if x.country in ("ALL", "DE"))
        selected = InputPreferences(enabled_media=frozenset({"radio_antenna"}),
                                    selected_source_ids=frozenset({source.id}))
        result = self.router.scan(selected,
               ScanContext(dvb_receiver_ready=True, radio_receiver_ready=False),
               user_triggered=True)
        self.assertEqual(result[0].state, "hardware_unavailable")

    def test_unverified_sources_never_claim_real_scan(self):
        source = next(x for x in self.tv if x.country == "DE")
        selected = InputPreferences(enabled_media=frozenset({"tv_antenna"}),
                                    selected_source_ids=frozenset({source.id}))
        result = self.router.scan(selected, ScanContext(dvb_receiver_ready=True),
                                  user_triggered=True)
        self.assertEqual(result[0].state, "source_unverified")
        self.assertEqual(result[0].entries_found, 0)

    def test_hardware_ready_does_not_imply_tuner_receives_turkish_tv_in_germany(self):
        source = next(x for x in self.tv if x.country == "TR")
        selected = InputPreferences(enabled_media=frozenset({"tv_antenna"}),
                                    selected_source_ids=frozenset({source.id}),
                                    country="DE")
        result = self.router.scan(selected, ScanContext(dvb_receiver_ready=True),
                                  user_triggered=True)
        self.assertEqual(result[0].state, "region_mismatch")

    def test_verified_adapter_is_called_only_when_every_gate_passes(self):
        source = NewsInput("internet:test_verified", "Test URL", "internet",
                           "test_rss", "ALL", verified=True)
        router = NewsSourceRouter([source])
        adapter = FakeAdapter()
        selection = InputPreferences(selected_source_ids=frozenset({source.id}))
        a = router.scan(selection, ScanContext(internet_available=True),
                        user_triggered=True, adapters={"internet":adapter})
        self.assertEqual(a[0].state, "checked")
        self.assertEqual(a[0].entries_found, 2)
        self.assertEqual(adapter.calls, [source.id])

    def test_integration_missing_not_success(self):
        source = NewsInput("internet:verified", "Verified", "internet",
                           "rss", "ALL", verified=True)
        r = NewsSourceRouter([source]).scan(
            InputPreferences(selected_source_ids=frozenset({source.id})),
            ScanContext(internet_available=True), user_triggered=True)
        self.assertEqual(r[0].state, "integration_missing")

    def test_invalid_source_and_media_fail_closed(self):
        with self.assertRaises(ValueError):
            self.router.scan(InputPreferences(selected_source_ids=frozenset({"unknown"})),
                             ScanContext(), user_triggered=True)
        with self.assertRaises(ValueError):
            self.router.scan(InputPreferences(enabled_media=frozenset({"satellite"}),
                                               selected_source_ids=frozenset()),
                             ScanContext(), user_triggered=True)


if __name__ == "__main__":
    unittest.main()
