"""Read-only CLI survey for future AI Hardware & Model Setup wizard.

Does not install models or drivers, format disks, or enable inference services.
The eventual web installer must authenticate and request explicit owner consent.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

from .ai_hardware import inspect_hardware, proposal
from .ai_boot_topology import inspect_boot_topology, hat_change_advisory
from .ai_base_readiness import BaseEvidence, assess_base_readiness
from .ai_cpu_smoke import cpu_smoke_test
from .ai_model_storage import ModelStorageRegistry


def verify_hailo10h(*, timeout: int = 5) -> bool:
    """Read-only firmware identity check; vendor ID alone is not sufficient."""
    if not shutil.which("hailortcli"):
        return False
    try:
        result = subprocess.run(["hailortcli", "fw-control", "identify"],
                                capture_output=True, text=True, timeout=timeout,
                                check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    report = (result.stdout + "\n" + result.stderr).lower().replace("-", "").replace("_", "")
    return result.returncode == 0 and "hailo10h" in report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Tihulu AI upgrade survey")
    parser.add_argument("--pcie-nvme-boot", action="store_true",
                        help="Warn about existing PCIe NVMe HAT boot topology")
    parser.add_argument("--boot-topology", action="store_true",
                        help="Read-only root disk/PCIe HAT boot-layout diagnostic")
    parser.add_argument("--probe-npu", action="store_true",
                        help="Run read-only hailortcli firmware identification")
    parser.add_argument("--model-registry", help="Existing model registry JSON, if configured")
    parser.add_argument("--base-readiness", action="store_true",
                        help="Assess read-only Base model evidence on THIS boot, not dual-boot safety")
    parser.add_argument("--base-model-id",
                        help="Owner-approved Base model ID from the existing model registry")
    parser.add_argument("--verify-base-hash", action="store_true",
                        help="Explicitly SHA256-verify the Base file (can be slow; never loads model)")
    parser.add_argument("--run-base-cpu-smoke", action="store_true",
                        help="EXPLICITLY load Base model for bounded CPU-only inference")
    parser.add_argument("--smoke-service-allowed", action="store_true",
                        help="Operator confirms optional AI worker is allowed; not auto-checked")
    parser.add_argument("--smoke-resource-budget-ok", action="store_true",
                        help="Operator confirms no protected recording/emergency/low-power blocker")
    parser.add_argument("--smoke-llama-cli",
                        help="Operator-selected absolute trusted llama-cli executable")
    parser.add_argument("--smoke-timeout", type=int, default=90,
                        help="Bounded inference timeout in seconds (5..180)")
    parser.add_argument("--smoke-threads", type=int, default=2,
                        help="CPU thread count (1..4)")
    options = parser.parse_args(argv)
    if options.base_model_id and (not options.model_registry or not options.base_readiness):
        parser.error("--base-model-id needs --model-registry and --base-readiness")
    if options.verify_base_hash and not options.base_model_id:
        parser.error("--verify-base-hash needs --base-model-id")
    if options.run_base_cpu_smoke and (
        not options.base_readiness or not options.base_model_id or not options.model_registry
    ):
        parser.error("--run-base-cpu-smoke requires --base-readiness, --base-model-id and --model-registry")
    if (options.smoke_service_allowed or options.smoke_resource_budget_ok or
            options.smoke_llama_cli) and not options.run_base_cpu_smoke:
        parser.error("smoke-related options need --run-base-cpu-smoke")
    snapshot = inspect_hardware()
    if options.probe_npu:
        snapshot = replace(snapshot, hailo_initialized=verify_hailo10h())
    boot = inspect_boot_topology() if options.boot_topology or options.base_readiness else None
    nvme_root = bool(boot and boot.root_class == "pcie_nvme")
    result = {"inventory": snapshot.as_dict(),
              "wizard_proposal": proposal(snapshot,
                                          pcie_nvme_boot=options.pcie_nvme_boot or nvme_root)}
    if boot is not None:
        result["boot_topology"] = boot.as_dict()
        result["hat_change_advisory"] = hat_change_advisory(boot)
    registry = ModelStorageRegistry(options.model_registry) if options.model_registry else None
    if registry is not None:
        result["registered_models"] = {
            name: {"availability": registry.availability(name), "path": entry.path,
                   "stored_sha256": entry.sha256, "device_uuid": entry.device_uuid}
            for name, entry in registry.models.items()
        }
    if options.base_readiness:
        model_id = (options.base_model_id
                    if registry is not None and options.base_model_id in registry.models
                    else None)
        status = registry.availability(model_id) if model_id else "unknown"
        checksum_verified = False
        gguf_header_checked = False
        if model_id and options.verify_base_hash and not options.run_base_cpu_smoke:
            # This is an explicit read-only large-file verification, NOT inference.
            try:
                checked_path = registry.verified_path(model_id)
                checksum_verified = True
                status = "hash_verified"
                with Path(checked_path).open("rb") as stream:
                    gguf_header_checked = stream.read(4) == b"GGUF"
            except (OSError, ValueError, RuntimeError):
                status = "integrity_unknown"
        smoke = None
        if options.run_base_cpu_smoke:
            # Manual CLI flags are operator attestations, NOT measurements or
            # a replacement for a future authenticated Stage4 service broker.
            smoke = cpu_smoke_test(
                registry, options.base_model_id, explicit_owner_consent=True,
                service_allowed=options.smoke_service_allowed,
                resource_budget_allowed=options.smoke_resource_budget_ok,
                runner=options.smoke_llama_cli, timeout_seconds=options.smoke_timeout,
                threads=options.smoke_threads)
            result["cpu_smoke"] = smoke.as_dict()
            hashed = {
                "not_gguf", "cpu_runner_unavailable", "runner_version_unavailable",
                "timed_out", "runner_failed_to_start", "runner_failed",
                "generation_unverified", "marker_observed",
            }
            if smoke.status in hashed:
                status = "hash_verified"
                checksum_verified = True
                gguf_header_checked = smoke.status != "not_gguf"
            elif smoke.status == "model_unavailable":
                status = "integrity_unknown"
        evidence = BaseEvidence(
            model_id=model_id, storage_status=status,
            gguf_header_checked=gguf_header_checked,
            checksum_verified=checksum_verified,
            cpu_runtime_detected=snapshot.cpu_runtime_found or
                                 bool(smoke and smoke.runner_version),
            cpu_inference_passed=bool(smoke and smoke.passed),
            tested_model_id=model_id if smoke and smoke.passed else None,
        )
        result["base_readiness"] = assess_base_readiness(boot, evidence).as_dict()
        result["base_readiness"]["actual_inference_test_executed"] = bool(
            smoke and smoke.runner_version and smoke.status not in {
                "cpu_runner_unavailable", "runner_version_unavailable"
            })
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
