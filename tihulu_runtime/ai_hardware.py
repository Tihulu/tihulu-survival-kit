"""Read-only Stage-5 AI hardware survey, model compatibility and safe routing.

No drivers, downloads, remote connections or hardware inference are performed.
Presence of a Hailo PCIe device does not prove driver/runtime initialization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import platform
import re
import shutil

BACKENDS = ("cpu_local", "npu_local", "remote_server")
LEGACY_PROFILE_PARAMETERS = {"Light": (1.5, 2.0), "Balanced": (2.5, 4.5),
                             "Maximum/Experimental": (7.0, 9.0)}
HAILO_PCI_VENDOR = "0x1e60"


@dataclass(frozen=True)
class Volume:
    path: str
    fs_type: str
    device: str
    available_bytes: int
    total_bytes: int
    device_uuid: str | None = None


@dataclass(frozen=True)
class HardwareSnapshot:
    architecture: str
    board: str
    system_ram_bytes: int
    hailo_pci_devices: tuple[str, ...]
    cpu_runtime_found: bool
    hailo_runtime_found: bool
    volumes: tuple[Volume, ...]
    hailo_initialized: bool | None = None
    dedicated_npu_ram_bytes: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class InferenceTarget:
    backend: str
    ready: bool
    memory_budget_bytes: int | None
    verified_model_ids: frozenset[str] = frozenset()
    label: str = ""
    latency_ms: float | None = None
    energy_joules_per_query: float | None = None

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise ValueError("Unknown inference backend")
        if self.memory_budget_bytes is not None and self.memory_budget_bytes < 0:
            raise ValueError("Negative memory budget")


@dataclass(frozen=True)
class ModelSpec:
    identifier: str
    format: str
    parameters_b: float
    quantization: str
    storage_bytes: int
    context_tokens: int
    peak_bytes_by_backend: dict[str, int]
    supported_backends: frozenset[str]
    license_id: str = "unknown"
    language_quality: dict[str, float] | None = None
    task_quality: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if not self.identifier or self.format not in ("gguf", "hailo"):
            raise ValueError("Model ID or format invalid")
        if self.parameters_b <= 0 or self.storage_bytes < 0 or self.context_tokens <= 0:
            raise ValueError("Invalid model dimensions")
        if not self.supported_backends.issubset(BACKENDS):
            raise ValueError("Unknown backend in model declaration")
        if self.format == "hailo" and "cpu_local" in self.supported_backends:
            raise ValueError("Hailo model is not a CPU GGUF")
        if self.format == "gguf" and "npu_local" in self.supported_backends:
            raise ValueError("Arbitrary GGUF cannot be declared Hailo-compatible")
        for key, value in self.peak_bytes_by_backend.items():
            if key not in BACKENDS or value <= 0:
                raise ValueError("Invalid runtime footprint")


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", errors="replace").rstrip("\x00\n ")
    except (OSError, ValueError):
        return ""


def inspect_hardware(*, root: str | Path = "/",
                     mount_paths: tuple[str, ...] = ("/", "/library", "/media", "/mnt")) -> HardwareSnapshot:
    """Non-privileged Linux survey; root permits deterministic sysfs mock fixtures.

    Only the real / root can expose actual mount capacity; external SSD type,
    persistent UUID, firmware and working runtime require separate verification.
    """
    root = Path(root)
    arch = platform.machine().lower()
    board = _read_text(root / "proc/device-tree/model") or "unknown"
    match = re.search(r"^MemTotal:\s*(\d+)\s+kB",
                      _read_text(root / "proc/meminfo"), re.MULTILINE)
    ram_bytes = int(match.group(1)) * 1024 if match else 0
    hailo = []
    try:
        for device in (root / "sys/bus/pci/devices").iterdir():
            if _read_text(device / "vendor").lower() == HAILO_PCI_VENDOR:
                hailo.append(device.name)
    except OSError:
        pass
    found_hailo = bool(shutil.which("hailortcli") or shutil.which("hailo-ollama"))
    cpu_runtime = bool(shutil.which("llama-server") or shutil.which("llama-cli"))
    volumes = []
    if root == Path("/"):
        for name in mount_paths:
            path = Path(name)
            if not path.is_dir() or not os.path.ismount(path):
                continue
            try:
                stat = os.statvfs(path)
                volumes.append(Volume(str(path), "unknown", "unknown",
                                      stat.f_bavail * stat.f_frsize,
                                      stat.f_blocks * stat.f_frsize))
            except OSError:
                continue
    return HardwareSnapshot(arch, board, ram_bytes, tuple(sorted(hailo)),
                            cpu_runtime, found_hailo, tuple(volumes))


def proposal(snapshot: HardwareSnapshot, *, pcie_nvme_boot: bool = False,
             remote_configured: bool = False) -> dict:
    """Re-runnable, side-effect-free install wizard plan. No activation from PCI detection."""
    detected = bool(snapshot.hailo_pci_devices)
    ready = detected and snapshot.hailo_runtime_found and snapshot.hailo_initialized is True
    return {
        "recommended_profile": (
            "AI HAT+ 2 optimized candidate" if ready else
            "NPU detected; initialization verification required" if detected else
            "Raspberry Pi CPU / standalone CPU fallback"
        ),
        "npu_detected": detected,
        "npu_usable": ready,
        "npu_memory_bytes": snapshot.dedicated_npu_ram_bytes if ready else None,
        "cpu_fallback": True,
        "remote_option_available": True,
        "remote_configured": remote_configured,
        "pcie_conflict_warning": bool(detected and pcie_nvme_boot),
        "storage_alternative": "Verified USB 3.0 SSD" if detected and pcie_nvme_boot else None,
        "actions_require_owner_confirmation": [
            "install driver/runtime", "download models", "move storage",
            "connect remote server"
        ],
        "installation_performed": False,
    }


def compatibility(model: ModelSpec, target: InferenceTarget) -> tuple[str, str]:
    """Preflight compatibility: separate from measured speed and answer quality."""
    if not target.ready:
        return "unavailable", "Runtime or server is not verified ready"
    if target.backend not in model.supported_backends:
        return "incompatible", "Model format/architecture unsupported by backend"
    if target.backend == "npu_local" and model.identifier not in target.verified_model_ids:
        return "not_verified", "Hailo model missing from runtime-verified allowlist"
    needed = model.peak_bytes_by_backend.get(target.backend)
    if needed is None or target.memory_budget_bytes is None:
        return "not_tested", "Missing measured runtime or usable memory budget"
    if needed > target.memory_budget_bytes:
        return "insufficient_memory", "Runtime peak including KV exceeds tested headroom"
    return "compatible", "Runtime, model and declared memory budget pass preflight"


def choose_backend(model: ModelSpec, targets: tuple[InferenceTarget, ...], *,
                   order: tuple[str, ...] = BACKENDS, force: str | None = None) -> dict:
    if force is not None and force not in BACKENDS:
        raise ValueError("Unknown forced backend")
    if not order or any(name not in BACKENDS for name in order) or len(set(order)) != len(order):
        raise ValueError("Invalid or repeated backend order")
    available = {target.backend: target for target in targets}
    attempts = []
    for backend in ((force,) if force else order):
        target = available.get(backend)
        status, reason = (compatibility(model, target) if target else
                          ("unavailable", "Backend not configured"))
        attempts.append({"backend": backend, "status": status, "reason": reason})
        if status == "compatible":
            return {
                "selected": backend, "attempts": attempts,
                "fallback_used": backend != order[0] if not force else False,
            }
    return {"selected": None, "attempts": attempts, "fallback_used": False}


def recommendations(models: tuple[ModelSpec, ...], targets: tuple[InferenceTarget, ...],
                    measurements: dict[str, dict] | None = None) -> dict:
    """Only rank with real supplied metrics; unknown means Not Tested."""
    measurements = measurements or {}
    metrics = {
        "fastest": ("tokens_per_second", True),
        "lowest_ram": ("observed_peak_memory_bytes", False),
        "lowest_energy": ("joules_per_response", False),
        "turkish": ("turkish_score", True),
        "multilingual": ("multilingual_score", True),
        "translation": ("translation_score", True),
        "summarization": ("summarization_score", True),
        "wikipedia_rag": ("wikipedia_rag_score", True),
        "reasoning": ("reasoning_score", True),
        "overall": ("overall_score", True),
    }
    answer = {}
    for label, (metric, higher) in metrics.items():
        values = []
        for model in models:
            for target in targets:
                if compatibility(model, target)[0] != "compatible":
                    continue
                key = f"{target.backend}|{model.identifier}"
                value = measurements.get(key, {}).get(metric)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                    values.append((float(value), key))
        if values:
            best = (max if higher else min)(values)
            answer[label] = {"model_target": best[1], "measured": best[0]}
        else:
            answer[label] = {"model_target": None, "status": "Not Tested"}
    return answer


def diagnostic_json(snapshot: HardwareSnapshot) -> str:
    return json.dumps({"inventory": snapshot.as_dict(), "setup": proposal(snapshot)}, indent=2)
