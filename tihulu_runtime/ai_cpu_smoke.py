# SPDX-License-Identifier: AGPL-3.0-only
"""Explicit, bounded CPU-only GGUF smoke test for an owner-approved model.

This is a local diagnostic, not a cloud call, background worker, deployment
benchmark, or authorization for physical HAT changes. Do not invoke from an
unauthenticated UI. The caller must enforce service leases and resource limits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import re
import shutil
import stat
import subprocess
import time

MARKER = "TIHULU_CPU_OK"
PROMPT = f"Reply with exactly {MARKER} and nothing else."
MAX_SECONDS = 180
MAX_THREADS = 4
MAX_TOKENS = 32


@dataclass(frozen=True)
class CpuSmokeResult:
    model_id: str
    model_sha256: str | None
    runner_version: str | None
    status: str
    elapsed_seconds: float | None = None
    marker_observed: bool = False
    output_saved: bool = False
    cloud_used: bool = False
    energy_measured: bool = False
    current_boot_only: bool = True
    physical_swap_approved: bool = False

    @property
    def passed(self) -> bool:
        return self.status == "marker_observed"

    def as_dict(self) -> dict:
        return asdict(self)


def _runner_binary(binary: str | Path | None) -> str | None:
    """Use a local executable explicitly chosen by a trusted operator."""
    candidate = str(binary) if binary is not None else shutil.which("llama-cli")
    if not candidate:
        return None
    path = Path(candidate)
    if path.name != "llama-cli" or not path.is_absolute() or path.is_symlink():
        return None
    try:
        mode = path.stat().st_mode
    except OSError:
        return None
    if not stat.S_ISREG(mode) or not os.access(path, os.X_OK):
        return None
    return str(path)


def cpu_smoke_test(registry: object, model_id: str, *,
                   explicit_owner_consent: bool = False,
                   service_allowed: bool = False,
                   resource_budget_allowed: bool = False,
                   runner: str | Path | None = None,
                   timeout_seconds: int = 90,
                   threads: int = 2,
                   predict_tokens: int = 16) -> CpuSmokeResult:
    """Run llama-cli with a fixed local GGUF path and CPU-only options.

    Registry must be *trusted and owner-scoped*. Its verified_path(model_id)
    rechecks file/SSD UUID and SHA-256 on this invocation. No browser-provided
    path is accepted as a model. The subprocess emits no private user text;
    raw stdout/stderr are discarded and never returned by this function.

    A marker match is a tiny model-execution smoke result, NOT a full quality
    evaluation or reliable proof of human-style reasoning, power consumption,
    thermals, or HAT-present/HAT-removed dual-boot operation.
    """
    def result(status: str, *, sha: str | None = None,
               version: str | None = None, elapsed: float | None = None,
               marker: bool = False) -> CpuSmokeResult:
        return CpuSmokeResult(model_id, sha, version, status, elapsed, marker)

    if not model_id or not isinstance(model_id, str):
        return result("invalid_model_id")
    if not explicit_owner_consent:
        return result("owner_consent_required")
    if not service_allowed:
        return result("service_disabled")
    if not resource_budget_allowed:
        return result("resource_budget_not_approved")
    if (type(timeout_seconds) is not int or not 5 <= timeout_seconds <= MAX_SECONDS
            or type(threads) is not int or not 1 <= threads <= MAX_THREADS
            or type(predict_tokens) is not int or not 1 <= predict_tokens <= MAX_TOKENS):
        return result("unsafe_limits")
    entries = getattr(registry, "models", None)
    if not isinstance(entries, dict) or model_id not in entries:
        return result("unregistered_model")
    entry = entries[model_id]
    sha = getattr(entry, "sha256", None)
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
        return result("untrusted_model_digest")
    # This is potentially an expensive disk scan. It happens ONLY on consent.
    try:
        model_file = Path(registry.verified_path(model_id))
        if not model_file.is_file() or model_file.is_symlink():
            return result("model_unavailable", sha=sha)
        with model_file.open("rb") as file:
            if file.read(4) != b"GGUF":
                return result("not_gguf", sha=sha)
    except (OSError, ValueError, RuntimeError, KeyError):
        return result("model_unavailable", sha=sha)
    binary = _runner_binary(runner)
    if not binary:
        return result("cpu_runner_unavailable", sha=sha)
    # Avoid inherited llama.cpp configuration, Hugging Face tokens and network
    # proxy variables. The program is given only an existing local model path.
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
           "LC_ALL": "C.UTF-8"}
    try:
        version_check = subprocess.run([binary, "--version"], env=env,
                                       capture_output=True, text=True,
                                       errors="replace", timeout=5,
                                       check=False)
    except (OSError, subprocess.TimeoutExpired):
        return result("runner_version_unavailable", sha=sha)
    raw_version = (version_check.stdout or version_check.stderr or "").strip()
    if version_check.returncode or not raw_version:
        return result("runner_version_unavailable", sha=sha)
    # Version identifier only; no paths, user data or raw model output stored.
    version = raw_version.splitlines()[0][:100]
    argv = [binary, "--model", str(model_file), "--prompt", PROMPT,
            "--n-predict", str(predict_tokens), "--ctx-size", "512",
            "--threads", str(threads), "--n-gpu-layers", "0",
            "--no-kv-offload", "--no-op-offload", "--no-conversation",
            "--single-turn", "--no-display-prompt",
            "--no-show-timings", "--color", "off"]
    start = time.monotonic()
    try:
        completed = subprocess.run(argv, env=env, capture_output=True,
                                   text=True, errors="replace",
                                   timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        return result("timed_out", sha=sha, version=version,
                      elapsed=round(time.monotonic() - start, 3))
    except OSError:
        return result("runner_failed_to_start", sha=sha, version=version,
                      elapsed=round(time.monotonic() - start, 3))
    elapsed = round(time.monotonic() - start, 3)
    if completed.returncode != 0:
        return result("runner_failed", sha=sha, version=version,
                      elapsed=elapsed)
    # The --no-display-prompt option must be supported by the installed runner.
    # This marker is a basic output observation, not a full semantic model test.
    marker = MARKER in completed.stdout
    return result("marker_observed" if marker else "generation_unverified",
                  sha=sha, version=version, elapsed=elapsed, marker=marker)
