# Base CPU fallback preflight — model evidence is not a working AI test

**2026-11-05 status:** Experimental Draft PR #1 CLI plus immutable policy library. **16** new policy cases and **13** existing boot-topology fixture cases passed in an isolated development container (29/29). No actual Raspberry Pi or model execution has been performed. Three new CLI mock tests and all-repository GitHub Actions results remain unverified.

## Intended user behavior

Tihulu's operational profiles **Base**, **Balanced**, **Advanced** (and consent-controlled **Auto**) must not break when AI HAT+ 2 is unavailable. Base means a **separate compatible small CPU GGUF model**, not the same Hailo-specific compiled model on the CPU. Original offline Kiwix content, files, maps and protected services remain accessible even if no Local AI model is installed.

An authorized setup process must check that **all** of the following are true for Base:
1. The owner intentionally configured a Base model ID in an already-verified local model registry.
2. Its actual model bytes are on an accessible approved volume; an external SSD must match its expected stable UUID.
3. Model integrity is actually reverified (SHA256), and its format is consistent with the expected CPU GGUF. The first four `GGUF` bytes are a *minimal header check*, not full architecture compatibility.
4. A compatible CPU inference runtime is truly installed and accessible. Seeing a `llama-server` binary in the PATH does not prove a model can be loaded.
5. An **actual** model-specific CPU inference smoke test succeeds, with source provenance, memory/thermal check and no background service override.
6. Both HAT-absent and HAT-present *physical Pi boots*, core services and the Base model location are independently validated. One running Pi boot does not prove both configurations.

## Current read-only CLI

```bash
# Without model ID, reports Base not configured. No heavy model checksum:
python3 -m tihulu_runtime.ai_setup --boot-topology --base-readiness

# Existing model registry, quick metadata only:
python3 -m tihulu_runtime.ai_setup --base-readiness \
  --model-registry /owner-approved/path/registry.json \
  --base-model-id some-cpu-model

# Explicit potentially time-consuming large model hash/header verification:
python3 -m tihulu_runtime.ai_setup --boot-topology --base-readiness \
  --model-registry /owner-approved/path/registry.json \
  --base-model-id some-cpu-model --verify-base-hash
```

`--base-model-id` requires both `--model-registry` and `--base-readiness`. `--verify-base-hash` additionally requires the model ID. No model is downloaded, installed, loaded into RAM, inferred with or moved; no EEPROM, PCIe, disk, HAT or volume configuration is modified.

A hash scan may read multiple gigabytes and draw CPU/SSD power. It is deliberately OFF unless explicitly requested; do not run it automatically every boot in a low-energy environment.

## Output safety interpretation

- `base_not_configured`: no approved Base model ID.
- `base_storage_unavailable`: model volume is offline, registry metadata cannot establish integrity, or bytes inaccessible.
- `base_format_unverified`: GGUF header not read or invalid; a header alone is still insufficient.
- `base_checksum_unverified`: no successful SHA256 check of the owner-registered bytes.
- `cpu_runtime_unavailable`: compatible CPU runner not detected.
- `cpu_inference_unverified`: other checks may pass, but no actual CPU answer test was run.
- `current_boot_candidate`: future trusted source might demonstrate a working model on one boot; **still not a guarantee across physical HAT changes**. Current CLI never sets real inference proof and therefore does not reach this state.
- `hardware_swap_approved=false` and `two_physical_layouts_verified=false` **always** in this pure evaluator. Neither a GGUF checksum nor `root=/dev/mmcblk0p2` is a green light for PCIe hardware changes.

Input `BaseEvidence` must come from a trusted owner-authenticated service, not directly from untrusted browser form fields. A claimed inference result is bound to an exact model ID and otherwise rejected; additional future attestation of revision/sha and runtime is required.

## Code and tests

- [Policy library](../../tihulu_runtime/ai_base_readiness.py)
- [16 unit tests](../../tests/test_ai_base_readiness.py)
- [Optional CLI integration](../../tihulu_runtime/ai_setup.py)
- [CLI mock cases](../../tests/test_ai_setup.py)
- [Boot topology diagnostic](BOOT_TOPOLOGY_PREFLIGHT.md)

Local isolated test command used:

```bash
python -m unittest discover -s tests -v
```

**29/29** for just the two fixture files available in that isolated workspace. This is not evidence that the full repository or the added CLI tests pass. The GitHub CI workflow now supports Python 3.11/3.12 test suite + Node inline HTML syntax checking with optional manual trigger, but no successful workflow result was observed on the latest PR head. Do not merge to `main` until independent tests and hardware acceptance.

## Hardware warning

Raspberry Pi AI HAT+ 2 and a Pi 5 NVMe HAT typically depend on the same standard exposed PCIe connection. Before attempting a swap, verify the operating system boot medium, EEPROM boot order, Base model drive and PSU arrangement in each tested configuration. **Shut down and disconnect all power before connecting/disconnecting the AI HAT.** The software only issues warnings; it cannot physically certify a safe swap or guarantee lower total energy. Official documentation: https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html .
