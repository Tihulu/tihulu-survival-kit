# SPDX-License-Identifier: AGPL-3.0-only
"""News Center multi-select, on-demand offline translation and AI test suite."""
import unittest

from tihulu_runtime import Module, ServiceManager
from tihulu_runtime.news_source_scanner import InputPreferences
from tihulu_runtime.news_assist import (
    NewsAssistCoordinator, NewsAssistRequest, NewsText,
)


class WorkerAdapter:
    def __init__(self):
        self.running = set()
        self.starts = []
        self.stops = []

    def start(self, name):
        self.running.add(name)
        self.starts.append(name)

    def stop(self, name):
        self.running.remove(name)
        self.stops.append(name)


class FakeTranslator:
    def __init__(self):
        self.calls = []

    def supports(self, source_language, target_language):
        return (source_language, target_language) in {
            ("de", "tr"), ("de", "en"), ("en", "tr"), ("en", "de"),
            ("tr", "en"), ("tr", "de")
        }

    def translate(self, text, source_language, target_language):
        self.calls.append((source_language, target_language))
        return f"[{target_language} translation of {source_language}] {text}"


class FakeAI:
    def __init__(self):
        self.summaries = []
        self.questions = []

    def supports_language(self, language):
        return language in ("tr", "en")

    def summarize(self, text, language, source_label):
        self.summaries.append((text, language, source_label))
        return f"SUMMARY({language}): {text[:50]}"

    def answer(self, question, materials, language, *, compare=False):
        self.questions.append((question, materials, language, compare))
        return f"{'COMPARE' if compare else 'ANSWER'}({language}): {len(materials)} sources"


class AssistTests(unittest.TestCase):
    def setUp(self):
        self.worker = WorkerAdapter()
        self.service = ServiceManager([
            Module("news", installed=True),
            Module("translator", installed=True),
            Module("local_ai", installed=True),
        ], self.worker)
        self.svc = NewsAssistCoordinator(self.service)
        self.texts = [
            NewsText("a", "tv_antenna:ard_text", "tv_antenna",
                     "German teletext article", "Ein kurzer Text.",
                     "de", "2026-11-05T08:00:00+01:00", "DVB 1 / page 100",
                     "broadcast_teletext", "page 100"),
            NewsText("b", "internet:example_news", "internet",
                     "English article", "A source-reported claim.",
                     "en", "2026-11-05T08:20:00+01:00", "official example RSS",
                     "independent_news", "https://example.invalid/story"),
            NewsText("c", "radio_antenna:fm_rds", "radio_antenna",
                     "FM station information", "Station bulletin text.",
                     "en", "2026-11-05T08:40:00+01:00", "FM RDS decoder",
                     "radio_metadata"),
        ]
        self.prefs = InputPreferences(
            enabled_media=frozenset({"internet", "tv_antenna", "radio_antenna"}),
            selected_source_ids=frozenset(t.source_id for t in self.texts),
            country="ALL")
        self.t = FakeTranslator()
        self.ai = FakeAI()

    def run_assist(self, request, **kwargs):
        return self.svc.process(request, self.texts, self.prefs,
                                owner_id="owner", explicit_user_action=True,
                                translator=self.t, ai=self.ai, **kwargs)

    def test_three_transport_multi_item_multi_language_and_ai_in_same_task(self):
        result = self.run_assist(NewsAssistRequest(
            item_ids=("a", "b", "c"),
            translate_to=("tr", "de"),
            summaries=True,
            question="What does each source report?",
            compare_sources=True,
            ai_language="tr"))
        self.assertEqual(set(result.translated), {"a", "b", "c"})
        self.assertEqual(set(result.summaries), {"a", "b", "c"})
        self.assertIn("3 sources", result.comparison)
        self.assertIn("3 sources", result.answers)
        self.assertTrue(all(x[1] == "tr" for x in self.ai.summaries))
        self.assertTrue(any("tv_antenna:ard_text" in x[2] for x in self.ai.summaries))
        self.assertEqual(self.worker.starts.count("translator"), 1)
        self.assertEqual(self.worker.starts.count("local_ai"), 1)
        self.assertEqual(self.service.snapshot()["translator"]["active_tasks"], 0)
        self.assertEqual(self.service.snapshot()["local_ai"]["active_tasks"], 0)
        self.service.sweep_idle()
        self.assertFalse(self.worker.running)

    def test_translate_only_does_not_wake_local_ai(self):
        result = self.run_assist(NewsAssistRequest(
            item_ids=("a", "b"), translate_to=("tr",)))
        self.assertEqual(len(result.translated), 2)
        self.assertEqual(self.worker.starts, ["translator"])
        self.assertEqual(self.ai.summaries, [])

    def test_foreign_source_is_translated_before_llm(self):
        self.run_assist(NewsAssistRequest(
            item_ids=("a",), summaries=True, ai_language="tr"))
        self.assertEqual(self.ai.summaries[0][1], "tr")
        self.assertIn("[tr translation of de]", self.ai.summaries[0][0])

    def test_background_or_unapproved_request_fails_without_model_start(self):
        with self.assertRaises(PermissionError):
            self.svc.process(NewsAssistRequest(item_ids=("a",), summaries=True),
                             self.texts, self.prefs, owner_id="owner",
                             translator=self.t, ai=self.ai)
        self.assertEqual(self.worker.starts, [])

    def test_unselected_radio_source_is_not_usable(self):
        p = InputPreferences(enabled_media=frozenset({"internet", "tv_antenna"}),
                             selected_source_ids=frozenset(t.source_id for t in self.texts))
        with self.assertRaises(PermissionError):
            self.svc.process(NewsAssistRequest(item_ids=("c",), summaries=True),
                             self.texts, p, owner_id="owner",
                             explicit_user_action=True, ai=self.ai)
        self.assertEqual(self.worker.starts, [])

    def test_comparison_requires_different_sources(self):
        with self.assertRaises(ValueError):
            self.run_assist(NewsAssistRequest(item_ids=("a",), compare_sources=True))
        other = NewsText("other", self.texts[0].source_id, self.texts[0].medium,
                         "Other page", "Page 200 text", "de",
                         "2026-11-05T08:10:00+01:00", "DVB page 200")
        with self.assertRaises(ValueError):
            self.svc.process(NewsAssistRequest(item_ids=("a", "other"),
                                               compare_sources=True),
                             self.texts + [other], self.prefs, owner_id="owner",
                             explicit_user_action=True, translator=self.t,
                             ai=self.ai)

    def test_no_ai_service_installed_reports_missing_dependency(self):
        m = ServiceManager([Module("translator", installed=True),
                            Module("local_ai", installed=False)], WorkerAdapter())
        svc = NewsAssistCoordinator(m)
        with self.assertRaises(Exception):
            svc.process(NewsAssistRequest(item_ids=("a",), summaries=True),
                        self.texts, self.prefs, owner_id="owner",
                        explicit_user_action=True, translator=self.t, ai=self.ai)
        self.assertEqual(m.snapshot()["translator"]["active_tasks"], 0)

    def test_unknown_language_pair_fails_before_worker_load(self):
        bad = NewsText("missing", "internet:example_news", "internet",
                       "Untranslated", "中文消息", "zh",
                       "2026-11-05T08:00:00+01:00", "trusted source")
        with self.assertRaises(RuntimeError):
            self.svc.process(NewsAssistRequest(
                item_ids=("missing",), summaries=True, ai_language="tr"),
                [bad], self.prefs, owner_id="owner",
                explicit_user_action=True, translator=self.t, ai=self.ai)
        self.assertEqual(self.worker.starts, [])

    def test_models_unload_after_engine_failure(self):
        class BrokenAI(FakeAI):
            def summarize(self, text, language, source_label):
                raise RuntimeError("Engine crashed")
        with self.assertRaises(RuntimeError):
            self.svc.process(
                NewsAssistRequest(item_ids=("a",), summaries=True, ai_language="tr"),
                self.texts, self.prefs, owner_id="owner",
                explicit_user_action=True, translator=self.t, ai=BrokenAI())
        self.service.sweep_idle()
        self.assertFalse(self.worker.running)

    def test_hard_off_worker_blocks_no_silent_bypass(self):
        self.service.set_policy("translator", hard=False, owner_verified=True)
        with self.assertRaises(Exception):
            self.run_assist(NewsAssistRequest(item_ids=("a",),
                                              translate_to=("tr",)))
        self.assertEqual(self.worker.starts, [])

    def test_unattributed_text_rejected(self):
        bad = NewsText("fake", "internet:example_news", "internet", "No source",
                       "a claim", "en", "2026-11-05T08:00:00+01:00", "")
        with self.assertRaises(PermissionError):
            self.svc.process(NewsAssistRequest(item_ids=("fake",), summaries=True),
                             [bad], self.prefs, owner_id="owner",
                             explicit_user_action=True, ai=self.ai)
        self.assertEqual(self.worker.starts, [])

    def test_source_selection_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            self.run_assist(NewsAssistRequest(item_ids=("a", "a"),
                                             translate_to=("en",)))


if __name__ == "__main__":
    unittest.main()
