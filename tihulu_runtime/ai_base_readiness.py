# SPDX-License-Identifier: AGPL-3.0-only
"""Fail-closed Base CPU continuity assessment; policy, NOT an AI inference runner.

A one-boot Linux survey cannot prove that a removable PCIe AI HAT+ 2 layout
will boot. This assessment NEVER authorizes physical hardware changes.
Trusted code must supply model registry/volume/format/inference observations;
client-side form values must never be used as evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from .ai_boot_topology import BootTopology, hat_change_advisory

STATES = frozenset({
    'base_not_configured', 'base_storage_unavailable', 'base_format_unverified',
    'base_checksum_unverified', 'cpu_runtime_unavailable',
    'cpu_inference_unverified', 'current_boot_candidate',
})


@dataclass(frozen=True)
class BaseEvidence:
    model_id: str | None = None
    storage_status: str = 'unknown'
    gguf_header_checked: bool = False
    checksum_verified: bool = False
    cpu_runtime_detected: bool = False
    cpu_inference_passed: bool = False
    tested_model_id: str | None = None

    def __post_init__(self) -> None:
        # A claimed smoke test is valid only when tagged to the exact model.
        if self.cpu_inference_passed and (
            not self.tested_model_id or self.tested_model_id != self.model_id
        ):
            raise ValueError('CPU smoke test evidence must match Base model')
        if self.storage_status not in {
            'unknown', 'storage_unavailable', 'integrity_unknown',
            'present_not_reverified', 'hash_verified',
        }:
            raise ValueError('Unknown trusted model registry status')


@dataclass(frozen=True)
class BaseReadiness:
    state: str
    current_boot_candidate: bool
    two_physical_layouts_verified: bool
    hardware_swap_approved: bool
    base_model_id: str | None
    boot_root_class: str
    boot_risk: str
    missing_checks: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def assess_base_readiness(topology: BootTopology, model: BaseEvidence) -> BaseReadiness:
    """Evaluate current-boot evidence without promising future physical boot.

    current_boot_candidate means observed/tested model/runtime conditions in
    the *current* layout only. Two-configuration proof is ALWAYS false here.
    """
    problems = []
    if not model.model_id:
        problems.append('base_not_configured')
    if model.storage_status == 'storage_unavailable':
        problems.append('base_storage_unavailable')
    elif model.storage_status not in {'hash_verified', 'present_not_reverified'}:
        problems.append('base_storage_unverified')
    if not model.gguf_header_checked:
        problems.append('base_format_unverified')
    if not model.checksum_verified or model.storage_status != 'hash_verified':
        problems.append('base_checksum_unverified')
    if not model.cpu_runtime_detected:
        problems.append('cpu_runtime_unavailable')
    if not model.cpu_inference_passed:
        problems.append('cpu_inference_unverified')
    risk = hat_change_advisory(topology)['state']
    if risk == 'pcie_root_conflict':
        problems.append('pcie_root_conflict')
    elif risk == 'boot_root_unverified':
        problems.append('boot_root_unverified')
    elif risk == 'usb_transport_unverified':
        problems.append('root_transport_unverified')
    # Even microSD current root is not proof of two independent boots.
    problems.append('second_physical_boot_not_verified')
    # Use order of gates to report the most actionable first blocker.
    if 'base_not_configured' in problems:
        state = 'base_not_configured'
    elif 'base_storage_unavailable' in problems or 'base_storage_unverified' in problems:
        state = 'base_storage_unavailable'
    elif 'base_format_unverified' in problems:
        state = 'base_format_unverified'
    elif 'base_checksum_unverified' in problems:
        state = 'base_checksum_unverified'
    elif 'cpu_runtime_unavailable' in problems:
        state = 'cpu_runtime_unavailable'
    elif 'cpu_inference_unverified' in problems:
        state = 'cpu_inference_unverified'
    else:
        state = 'current_boot_candidate'
    return BaseReadiness(
        state=state,
        current_boot_candidate=(state == 'current_boot_candidate'),
        two_physical_layouts_verified=False,
        hardware_swap_approved=False,
        base_model_id=model.model_id,
        boot_root_class=topology.root_class,
        boot_risk=risk,
        missing_checks=tuple(problems),
    )
