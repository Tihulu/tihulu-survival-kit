# SPDX-License-Identifier: AGPL-3.0-only
"""Pure modular AI mode routing: Base, Balanced, Advanced and consented Auto.

This is a read-only *policy prototype*, not a model runner, HAT hotplug driver,
power meter or full setup wizard. A trusted owner-authenticated backend must
provide verified device state, model availability and memory budgets. Hardware
removal is only supported after powering down the Pi and disconnecting power.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ai_hardware import InferenceTarget, ModelSpec, compatibility

PROFILES = frozenset({"Auto", "Base", "Balanced", "Advanced"})


@dataclass(frozen=True)
class ProfileModels:
    """Independent installed weight IDs; Hailo models are not CPU GGUF models."""

    base_cpu: str
    balanced_cpu: str | None = None
    balanced_npu: str | None = None
    advanced_npu: str | None = None

    def __post_init__(self) -> None:
        if not self.base_cpu:
            raise ValueError("A Base CPU model identifier is required")
        ids = [v for v in (self.base_cpu, self.balanced_cpu,
                           self.balanced_npu, self.advanced_npu) if v]
        if len(ids) != len(set(ids)):
            raise ValueError("Each deployment slot must identify its own model")


@dataclass(frozen=True)
class ProfilePreference:
    """Saved owner configuration, distinct from the effective runtime profile."""

    requested: str = "Auto"
    auto_advanced_approved: bool = False
    balanced_npu_approved: bool = False

    def __post_init__(self) -> None:
        if self.requested not in PROFILES:
            raise ValueError("Unknown operation profile")


@dataclass(frozen=True)
class ProfileRoute:
    requested: str
    effective: str | None
    backend: str | None
    model_id: str | None
    status: str
    explanation: str
    attempted: tuple[tuple[str, str, str], ...] = ()

    @property
    def ready(self) -> bool:
        return self.model_id is not None and self.backend is not None


def choose_profile(preference: ProfilePreference, slots: ProfileModels, *,
                   models: tuple[ModelSpec, ...],
                   targets: tuple[InferenceTarget, ...],
                   installed_verified_model_ids: frozenset[str],
                   hat10h_verified: bool,
                   base_storage_available: bool = True) -> ProfileRoute:
    """Select an existing compatible on-device model, never auto-download.

    `hat10h_verified` must be the result of a trusted hardware/firmware check,
    not simply the presence of a PCI ID. CPU Base must be accessible after
    a physical *shutdown/removal/reboot* cycle. Neither remote nor cloud is an
    automatic fallback, even when a remote_server target is in `targets`.
    `installed_verified_model_ids` represents trusted verified model files.
    """
    lookup = {m.identifier: m for m in models}
    if len(lookup) != len(models):
        raise ValueError("Duplicate model identifier")
    by_backend = {t.backend: t for t in targets}
    if len(by_backend) != len(targets):
        raise ValueError("Duplicate inference backend")
    attempted: list[tuple[str, str, str]] = []

    requested = preference.requested
    # Auto remains Base until Advanced auto-upgrade is separately approved.
    desired = ("Advanced" if hat10h_verified and preference.auto_advanced_approved
               else "Base") if requested == "Auto" else requested

    if desired == "Base":
        candidates = [("Base", "cpu_local", slots.base_cpu)]
    elif desired == "Balanced":
        candidates = (
            ([("Balanced", "npu_local", slots.balanced_npu)]
             if preference.balanced_npu_approved and hat10h_verified else [])
            + [("Balanced", "cpu_local", slots.balanced_cpu),
               ("Base", "cpu_local", slots.base_cpu)]
        )
    elif not hat10h_verified:  # Advanced preference held, HAT physically absent/unready
        candidates = [("Base", "cpu_local", slots.base_cpu)]
    else:
        candidates = [
            ("Advanced", "npu_local", slots.advanced_npu),
            ("Balanced", "npu_local", slots.balanced_npu),
            ("Balanced", "cpu_local", slots.balanced_cpu),
            ("Base", "cpu_local", slots.base_cpu),
        ]

    for effective, backend, model_id in candidates:
        if not model_id:
            attempted.append((effective, backend, "model_not_configured"))
            continue
        if backend == "cpu_local" and model_id == slots.base_cpu and not base_storage_available:
            attempted.append((effective, backend, "base_storage_unavailable"))
            continue
        if model_id not in installed_verified_model_ids:
            attempted.append((effective, backend, "model_not_installed_or_unverified"))
            continue
        model = lookup.get(model_id)
        if model is None:
            attempted.append((effective, backend, "model_manifest_missing"))
            continue
        target = by_backend.get(backend)
        if backend == "npu_local" and not hat10h_verified:
            attempted.append((effective, backend, "npu_not_verified"))
            continue
        state, explanation = (compatibility(model, target) if target else
                              ("unavailable", "Backend not installed or ready"))
        attempted.append((effective, backend, state))
        if state != "compatible":
            continue
        if requested == "Auto" and desired == "Advanced" and effective == "Advanced":
            explanation = "Owner-approved Auto: verified AI HAT+ 2 model selected"
        elif requested == "Advanced" and effective != "Advanced":
            explanation = "Advanced unavailable; using an already-installed local fallback"
        elif requested == "Auto" and desired == "Base":
            explanation = "Auto Base default; no unapproved acceleration"
        elif effective != desired:
            explanation = "Selected profile unavailable; downgraded without reinstalling"
        else:
            explanation = "Compatible installed local model selected"
        return ProfileRoute(requested, effective, backend, model_id,
                            "ready" if effective == desired else "downgraded",
                            explanation, tuple(attempted))
    return ProfileRoute(requested, None, None, None,
                        "local_ai_unavailable",
                        "No verified installed compatible on-device model; core remains available",
                        tuple(attempted))


def is_hat_upgrade_candidate(preference: ProfilePreference,
                             *, hat10h_verified: bool,
                             advanced_model_installed: bool) -> dict[str, object]:
    """UI-only suggestion. It never invokes installers, changes profile or touches PCIe."""
    return {
        "offer_advanced_install": bool(hat10h_verified and not advanced_model_installed),
        "offer_auto_advanced_consent": bool(hat10h_verified and
                                             not preference.auto_advanced_approved),
        "physical_hot_removal_supported": False,
        "installer_executed": False,
        "note": ("Keep Base on a boot-accessible disk before changing PCIe topology. "
                 "Installing/unplugging a HAT requires Pi power OFF."),
    }
