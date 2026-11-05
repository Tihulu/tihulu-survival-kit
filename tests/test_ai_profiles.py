"""Pure modular AI mode routing tests. No HAT, hardware, models or power meter."""
import unittest
from tihulu_runtime.ai_hardware import ModelSpec, InferenceTarget
from tihulu_runtime.ai_profiles import (
    ProfileModels, ProfilePreference, choose_profile, is_hat_upgrade_candidate,
)


MODELS = (
    ModelSpec("cpu-small", "gguf", 1.7, "Q4", 1000, 2048,
              {"cpu_local": 1000}, frozenset({"cpu_local"})),
    ModelSpec("cpu-medium", "gguf", 3.0, "Q4", 2000, 4096,
              {"cpu_local": 2400}, frozenset({"cpu_local"})),
    ModelSpec("hailo-balanced", "hailo", 3.0, "INT4", 2000, 4096,
              {"npu_local": 2500}, frozenset({"npu_local"})),
    ModelSpec("hailo-advanced", "hailo", 5.0, "INT4", 3000, 4096,
              {"npu_local": 4500}, frozenset({"npu_local"})),
)
SLOTS = ProfileModels("cpu-small", "cpu-medium", "hailo-balanced", "hailo-advanced")
CPU = InferenceTarget("cpu_local", True, 3000)
NPU = InferenceTarget("npu_local", True, 8000,
                      frozenset({"hailo-balanced", "hailo-advanced"}))
REMOTE = InferenceTarget("remote_server", True, 100000)


def run(preference=None, *, hat=False, installed=None, targets=None,
        base_storage=True):
    return choose_profile(
        preference or ProfilePreference(), SLOTS, models=MODELS,
        targets=tuple(targets if targets is not None else (CPU, NPU, REMOTE)),
        installed_verified_model_ids=frozenset(installed if installed is not None
                                                 else {m.identifier for m in MODELS}),
        hat10h_verified=hat, base_storage_available=base_storage,
    )


class ModularModeTests(unittest.TestCase):
    def test_auto_without_hat_defaults_base(self):
        result = run(hat=False)
        self.assertEqual((result.effective, result.backend, result.model_id),
                         ("Base", "cpu_local", "cpu-small"))
        self.assertEqual(result.status, "ready")

    def test_advanced_request_no_hat_falls_to_base(self):
        choice = run(ProfilePreference("Advanced"), hat=False)
        self.assertEqual((choice.effective, choice.status),
                         ("Base", "downgraded"))
        self.assertEqual(choice.model_id, "cpu-small")

    def test_auto_after_hat_reinstalled_without_consent_stays_base(self):
        self.assertEqual(run(hat=True).model_id, "cpu-small")

    def test_auto_with_prior_approval_and_verified_hat_uses_advanced(self):
        result = run(ProfilePreference("Auto", auto_advanced_approved=True), hat=True)
        self.assertEqual((result.effective, result.backend, result.model_id),
                         ("Advanced", "npu_local", "hailo-advanced"))

    def test_auto_restores_base_after_powered_off_hat_removal(self):
        pref = ProfilePreference("Auto", auto_advanced_approved=True)
        before = run(pref, hat=True)
        after = run(pref, hat=False)
        self.assertEqual(before.effective, "Advanced")
        self.assertEqual(after.effective, "Base")
        self.assertEqual(after.model_id, "cpu-small")
        self.assertEqual(pref.requested, "Auto")  # Stable preference not rewritten.
        self.assertEqual(run(pref, hat=True).effective, "Advanced")

    def test_base_can_be_forced_with_hat_still_connected(self):
        self.assertEqual(run(ProfilePreference("Base"), hat=True).backend,
                         "cpu_local")

    def test_balanced_cpu_without_hat(self):
        result = run(ProfilePreference("Balanced"), hat=False)
        self.assertEqual((result.effective, result.model_id),
                         ("Balanced", "cpu-medium"))

    def test_balanced_npu_requires_separate_approval_and_verified_hat(self):
        pref = ProfilePreference("Balanced", balanced_npu_approved=True)
        self.assertEqual(run(pref, hat=True).model_id, "hailo-balanced")
        self.assertEqual(run(ProfilePreference("Balanced"), hat=True).model_id,
                         "cpu-medium")
        self.assertEqual(run(pref, hat=False).model_id, "cpu-medium")

    def test_balanced_falls_back_to_base_when_cpu_medium_missing(self):
        result = run(ProfilePreference("Balanced"), hat=False,
                     installed={"cpu-small"})
        self.assertEqual(result.effective, "Base")
        self.assertEqual(result.status, "downgraded")

    def test_hailo_is_not_a_cpu_fallback(self):
        result = run(ProfilePreference("Advanced"), hat=False,
                     installed={"hailo-advanced"})
        self.assertFalse(result.ready)
        self.assertEqual(result.status, "local_ai_unavailable")

    def test_advanced_no_model_but_hat_uses_cpu_fallback(self):
        result = run(ProfilePreference("Advanced"), hat=True,
                     installed={"cpu-small"})
        self.assertEqual(result.model_id, "cpu-small")
        self.assertEqual(result.status, "downgraded")

    def test_detected_but_not_verified_hat_cannot_route_npu(self):
        result = run(ProfilePreference("Advanced"), hat=False,
                     targets=(CPU, NPU, REMOTE))
        self.assertEqual(result.backend, "cpu_local")

    def test_npu_driver_runtime_not_ready(self):
        result = run(ProfilePreference("Advanced"), hat=True,
                     targets=(CPU, InferenceTarget("npu_local", False, 8000,
                             frozenset({"hailo-advanced", "hailo-balanced"}))))
        self.assertEqual(result.backend, "cpu_local")
        self.assertEqual(result.status, "downgraded")

    def test_npu_allowlist_requires_verified_model(self):
        result = run(ProfilePreference("Advanced"), hat=True,
                     targets=(CPU, InferenceTarget("npu_local", True, 8000)))
        self.assertEqual(result.backend, "cpu_local")

    def test_no_unapproved_remote_fallback(self):
        result = run(ProfilePreference("Advanced"), hat=False,
                     installed={"hailo-advanced"}, targets=(REMOTE,))
        self.assertFalse(result.ready)
        self.assertIsNone(result.backend)

    def test_fallback_disk_missing_does_not_fake_cpu_ability(self):
        result = run(ProfilePreference("Base"), hat=False, base_storage=False)
        self.assertEqual(result.status, "local_ai_unavailable")
        self.assertIn(("Base", "cpu_local", "base_storage_unavailable"),
                      result.attempted)

    def test_no_cpu_runtime_keeps_core_but_ai_unavailable(self):
        result = run(ProfilePreference("Base"), targets=(REMOTE,))
        self.assertFalse(result.ready)
        self.assertEqual(result.status, "local_ai_unavailable")

    def test_missing_model_weights_not_auto_downloaded(self):
        result = run(ProfilePreference("Advanced"), hat=True, installed=set())
        self.assertFalse(result.ready)
        self.assertTrue(any(x[2] == "model_not_installed_or_unverified"
                            for x in result.attempted))

    def test_strict_manifest_and_memory_fit(self):
        too_small = InferenceTarget("cpu_local", True, 100)
        result = run(ProfilePreference("Base"), targets=(too_small,))
        self.assertFalse(result.ready)
        self.assertEqual(result.attempted[-1][2], "insufficient_memory")

    def test_unknown_mode_or_duplicate_slots_rejected(self):
        with self.assertRaises(ValueError):
            ProfilePreference("Ultra")
        with self.assertRaises(ValueError):
            ProfileModels("cpu-small", balanced_cpu="cpu-small")
        with self.assertRaises(ValueError):
            ProfileModels("")

    def test_upgrade_suggestion_never_installs_or_hotunplugs(self):
        outcome = is_hat_upgrade_candidate(ProfilePreference(), hat10h_verified=True,
                                           advanced_model_installed=False)
        self.assertTrue(outcome["offer_advanced_install"])
        self.assertFalse(outcome["physical_hot_removal_supported"])
        self.assertFalse(outcome["installer_executed"])

    def test_unverified_hat_does_not_offer_install(self):
        result = is_hat_upgrade_candidate(ProfilePreference(), hat10h_verified=False,
                                          advanced_model_installed=False)
        self.assertFalse(result["offer_advanced_install"])


if __name__ == "__main__":
    unittest.main()
