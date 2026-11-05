"""Stage 5 Local AI sources: mock-only policy tests, no real files/SSD or AI."""
import unittest

from tihulu_runtime.ai_sources import (
    IndexIntent, KnowledgeSource, SourceSelector, StorageObservation,
    prepare_index_job,
)


def inventory():
    return [
        KnowledgeSource("wiki-en", "wikipedia", "Wikipedia English"),
        KnowledgeSource("wiki-tr", "wikipedia", "Wikipedia Türkçe"),
        KnowledgeSource("books", "collection", "Kitap Arşivim", "alice"),
        KnowledgeSource("pdf", "file", "Selected PDF", "alice"),
        KnowledgeSource("folder", "folder", "Documents", "alice"),
        KnowledgeSource("bob-private", "file", "Secret", "bob"),
        KnowledgeSource("missing", "collection", "Unmounted books", "alice", False),
    ]


def disk(kind="external", uuid="SSD-A", free=100_000, reserve=2_000,
         mounted=True, writable=True, supported=True):
    return StorageObservation(kind, uuid if kind == "external" else None,
                              mounted, writable, supported, free, reserve)


class SourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.selector = SourceSelector(inventory())

    def test_wiki_only_no_personal_grant(self):
        result = self.selector.select("alice", ["wiki-en"])
        self.assertEqual([s.source_id for s in result], ["wiki-en"])

    def test_multiple_sources_wikipedia_always_last(self):
        result = self.selector.select("alice", ["wiki-tr", "books", "pdf", "wiki-en"],
                                      trusted_file_grants=["pdf", "books"])
        self.assertEqual([s.source_id for s in result],
                         ["pdf", "books", "wiki-en", "wiki-tr"])

    def test_books_only_does_not_select_wikipedia(self):
        result = self.selector.select("alice", ["books"], trusted_file_grants=["books"])
        self.assertEqual([s.source_id for s in result], ["books"])

    def test_no_private_grant_even_if_source_listed(self):
        with self.assertRaises(PermissionError):
            self.selector.select("alice", ["books"])

    def test_cannot_read_another_users_files_even_with_grant(self):
        with self.assertRaises(PermissionError):
            self.selector.select("alice", ["bob-private"],
                                 trusted_file_grants=["bob-private"])

    def test_missing_source_is_not_selected(self):
        with self.assertRaises(ValueError):
            self.selector.select("alice", ["missing"], trusted_file_grants=["missing"])

    def test_unknown_source_does_not_become_fake_catalog_entry(self):
        with self.assertRaises(ValueError):
            self.selector.select("alice", ["made-up"])

    def test_duplicate_request_rejected(self):
        with self.assertRaises(ValueError):
            self.selector.select("alice", ["wiki-en", "wiki-en"])

    def test_duplicate_inventory_rejected(self):
        with self.assertRaises(ValueError):
            SourceSelector(inventory() + [inventory()[0]])

    def test_source_owner_required(self):
        with self.assertRaises(ValueError):
            KnowledgeSource("not-scoped", "file", "No owner")

    def test_no_authenticated_owner_rejected(self):
        with self.assertRaises(ValueError):
            self.selector.select("", ["wiki-en"])


class IndexAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.sources = SourceSelector(inventory()).select(
            "alice", ["wiki-en", "books", "folder"],
            trusted_file_grants=["books", "folder"])
        self.target = disk()

    def request(self, **kwargs):
        return IndexIntent(source_id="books", mode="semantic", storage_kind="external",
                           storage_uuid="SSD-A", quota_bytes=20_000,
                           estimated_peak_bytes=10_000, **kwargs)

    def evaluate(self, intent=None, **overrides):
        opts = dict(explicit_owner_approval=True, hard_enabled=True,
                    background_allowed=True, startup_allowed=True,
                    storage=self.target)
        opts.update(overrides)
        return prepare_index_job(self.sources, intent or self.request(), **opts)

    def test_default_is_direct_only_not_index(self):
        d = self.evaluate(IndexIntent("wiki-en"), storage=None)
        self.assertEqual(d.state, "direct_only")
        self.assertFalse(d.can_start)

    def test_explicit_multi_source_index_preflight(self):
        self.assertTrue(self.evaluate().can_start)

    def test_background_opt_in_possible_on_external_ssd(self):
        result = self.evaluate(self.request(background=True))
        self.assertTrue(result.can_start)
        self.assertEqual(result.state, "eligible_for_real_backend")

    def test_index_without_owner_approval_is_blocked(self):
        self.assertEqual(self.evaluate(explicit_owner_approval=False).state, "approval_required")

    def test_hard_off_cannot_be_bypassed(self):
        self.assertEqual(self.evaluate(hard_enabled=False).state, "hard_disabled")

    def test_background_off_wins(self):
        self.assertEqual(
            self.evaluate(self.request(background=True), background_allowed=False).state,
            "background_disabled")

    def test_separate_boot_setting(self):
        self.assertEqual(
            self.evaluate(self.request(background=True, start_after_reboot=True),
                          startup_allowed=False).state, "startup_disabled")

    def test_selected_ssd_not_mounted(self):
        self.assertEqual(self.evaluate(storage=disk(mounted=False)).state,
                         "storage_unavailable")

    def test_ssd_uuid_not_same_as_selected(self):
        self.assertEqual(self.evaluate(storage=disk(uuid="different")).state,
                         "storage_mismatch")

    def test_no_hidden_nvme_fallback(self):
        self.assertEqual(self.evaluate(storage=disk(kind="internal")).state,
                         "storage_mismatch")

    def test_readonly_or_unsupported_filesystem(self):
        self.assertEqual(self.evaluate(storage=disk(writable=False)).state,
                         "storage_incompatible")
        self.assertEqual(self.evaluate(storage=disk(supported=False)).state,
                         "storage_incompatible")

    def test_estimate_and_quota_required(self):
        request = IndexIntent("books", "semantic", storage_kind="external",
                              storage_uuid="SSD-A", quota_bytes=0,
                              estimated_peak_bytes=0)
        self.assertEqual(self.evaluate(request).state, "estimate_required")

    def test_peak_temp_space_and_reserve_honored(self):
        self.assertEqual(self.evaluate(storage=disk(free=11_000)).state,
                         "insufficient_space")
        self.assertEqual(self.evaluate(self.request(), storage=disk(free=12_000)).state,
                         "eligible_for_real_backend")
        request = IndexIntent("books", "semantic", storage_kind="external",
                              storage_uuid="SSD-A", quota_bytes=5_000,
                              estimated_peak_bytes=10_000)
        self.assertEqual(self.evaluate(request).state, "insufficient_space")

    def test_index_source_must_be_selected(self):
        request = IndexIntent("bob-private", "semantic", storage_kind="external",
                              storage_uuid="SSD-A", quota_bytes=20_000,
                              estimated_peak_bytes=10_000)
        self.assertEqual(self.evaluate(request).state, "source_not_selected")

    def test_watch_requires_background_and_folder_scope(self):
        with self.assertRaises(ValueError):
            self.request(watch_changes=True)
        self.assertEqual(self.evaluate(self.request(background=True,
                          watch_changes=True)).state, "eligible_for_real_backend")
        wiki = IndexIntent("wiki-en", "semantic", background=True,
                           watch_changes=True, storage_kind="external",
                           storage_uuid="SSD-A", quota_bytes=20_000,
                           estimated_peak_bytes=10_000)
        self.assertEqual(self.evaluate(wiki).state, "watch_unsupported")

    def test_disabled_index_cannot_schedule_background(self):
        with self.assertRaises(ValueError):
            IndexIntent("wiki-en", background=True)
        with self.assertRaises(ValueError):
            IndexIntent("wiki-en", start_after_reboot=True)

    def test_external_storage_needs_explicit_uuid(self):
        with self.assertRaises(ValueError):
            IndexIntent("books", mode="semantic", storage_kind="external")

    def test_internal_index_explicit_choice_allowed(self):
        request = IndexIntent("books", "keyword", storage_kind="internal",
                              estimated_peak_bytes=1000, quota_bytes=4000)
        self.assertTrue(self.evaluate(request, storage=disk(kind="internal")).can_start)


if __name__ == "__main__":
    unittest.main()
