"""Read-only CLI survey for future AI Hardware & Model Setup wizard.

Does not install models or drivers, format disks, or enable inference services.
The eventual web installer must authenticate and request explicit owner consent.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import shutil
import subprocess

from .ai_hardware import inspect_hardware, proposal
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
    parser.add_argument("--probe-npu", action="store_true",
                        help="Run read-only hailortcli firmware identification")
    parser.add_argument("--model-registry", help="Existing model registry JSON, if configured")
    options = parser.parse_args(argv)
    snapshot = inspect_hardware()
    if options.probe_npu:
        snapshot = replace(snapshot, hailo_initialized=verify_hailo10h())
    result = {"inventory": snapshot.as_dict(),
              "wizard_proposal": proposal(snapshot,
                                          pcie_nvme_boot=options.pcie_nvme_boot)}
    if options.model_registry:
        registry = ModelStorageRegistry(options.model_registry)
        result["registered_models"] = {
            name: {"availability": registry.availability(name), "path": entry.path,
                   "stored_sha256": entry.sha256, "device_uuid": entry.device_uuid}
            for name, entry in registry.models.items()
        }
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
