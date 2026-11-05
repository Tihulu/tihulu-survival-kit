# Stage 5 — Hardware-aware AI upgrades (development prototype)

**2026-11-05 status:** Code is being added on Draft PR #1. There is **no installed Tihulu Core image, functional user-facing Model Manager, full Installation Wizard, actual Hailo inference, or real Pi/remote GPU benchmarking** yet. Design signoff for Stage 5 was pending; the user's new implementation request authorizes incremental development without implying full-stage approval.

## Three distinct execution modes

- **cpu_local** — Preserve original 1.5–1.7B Light, ~3B Balanced, ~8B Maximum/Experimental *CPU profile targets*. Compatible GGUF needs an installed and tested llama.cpp backend. This is intended to remain the offline fallback, with actual RAM/KV/PSI/thermal limits.
- **npu_local** — Raspberry Pi AI HAT+ 2: Hailo-10H advertised 40 INT4 TOPS and 8 GB separate accelerator RAM. Hailo compatibility requires supported Hailo HEF/GenAI model, exact runtime, firmware/driver verification, not arbitrary CPU GGUF. NPU memory must not be added to host RAM.
- **remote_server** — Explicit owner-approved private HTTPS to an optional Linux/Windows/macOS host with supported NVIDIA, AMD, Apple Silicon or CPU hardware. Ollama, llama.cpp and vLLM REST API shapes are distinguished. Remote host outage must not disable the Pi's other offline functions.

Model recommendation categories such as fastest, lowest RAM, energy, Turkish, multilingual, translation, summarization, reasoning and Wikipedia/RAG must use **actual source-backed tests**. The current ranking library returns **Not Tested** when a metric or tested usable runtime budget is absent.

## Actual Python code and developer diagnostics

The currently implemented standard-library modules are:

| File | What works today | Not yet provided |
|---|---|---|
| tihulu_runtime/ai_hardware.py | Read-only Pi/Linux CPU and PCI Hailo survey, conservative model compatibility, user-configurable CPU/NPU/remote fallback, evidence-only recommendations | Real model loading, GPU/VRAM agent, benchmarks, multilingual evaluations |
| tihulu_runtime/ai_setup.py | Re-runnable read-only console wizard survey, optional bounded Hailo firmware identity verification | Actual installer package actions, web UI and post-install inference |
| tihulu_runtime/ai_volumes.py | Linux mountinfo, free space, mount filesystem, stable UUID mapping | Hardware SSD type, SMART and measured throughput |
| tihulu_runtime/ai_model_storage.py | Owner-gated SHA256 model registry, verified source, non-destructive copy/hash/registry switch, external UUID matching | Backend-specific actual path reload, live worker lock, power-failure migration recovery |
| tihulu_runtime/ai_remote.py | Explicit HTTPS/private-network Ollama, Hailo-Ollama, llama.cpp, vLLM API clients; model discovery, non-streaming prompt, no redirects/proxies | Web pairing, real GPU telemetry, live cancellation, production portal auth and storage for tokens |

In a developer checkout of the repository, read-only hardware detection is runnable directly:

    python3 -m tihulu_runtime.ai_setup
    python3 -m tihulu_runtime.ai_setup --probe-npu --pcie-nvme-boot
    python3 -m tihulu_runtime.ai_setup --model-registry /path/to/existing/registry.json

The --probe-npu option executes the official read-only hailortcli fw-control identify with timeout. Without verifying exact HAILO10H identity and installed runtime the NPU does not become the default. Hardware discovery never installs software or erases/modifies the SSD. The --pcie-nvme-boot flag is currently supplied by the operator; automatic NVMe boot topology recognition is still needed.

## Hailo prerequisites: official guidance, NOT auto-applied

Official Raspberry Pi documentation describes Raspberry Pi OS **Trixie 64-bit** with compatible firmware and AI HAT+ 2 dependency package **hailo-h10-all**, DKMS, HailoRT and reboot before checking hailortcli firmware identity. Earlier AI HAT/Kit uses a DIFFERENT hailo-all bundle; packages must not be mixed. Use only when Raspberry Pi OS, IIAB/HAS and real Pi firmware compatibility are confirmed. Consult official sources:

- https://www.raspberrypi.com/documentation/computers/ai.html
- https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html
- https://github.com/hailo-ai/hailo_model_zoo_genai/blob/main/docs/USAGE.rst

The Hailo-Ollama installed model list uses /api/tags, and its separate download-supported GenAI list uses /hailo/v1/list. These MUST NOT be treated as the entire generic Hugging Face GGUF catalogue. Hailo-Ollama has limited concurrent GenAI workloads. Current code makes no automatic model pulls.

### Pi 5 PCIe and existing Acer FA100 NVMe boot

The Pi 5 has one ordinary externally accessible PCIe lane/ribbon connection. A standard PCIe NVMe HAT for the existing Acer FA100 and AI HAT+ 2 are **not presumed simultaneously compatible**. A USB 3.0 NVMe enclosure may be an alternative for system boot/model storage, but bootloader order, root filesystem identity, actual throughput, power draw and persistent partition layout MUST be tested before any migration. Do NOT format the existing NVMe, run a whole-disk HAS setup script on the boot drive or buy a generic unverified PCIe splitter expecting it to work. Test single-powerbank voltage/current headroom after the added Hailo/USB SSD load.

## Model storage rules

The registry stores exact path, hash, size and optional UUID. Reading an external model bound to an absent UUID fails closed. Owner-gated migration copies into an existing permitted directory, checks disk headroom and SHA256, fsyncs, updates metadata atomically and **retains the old model file**. A production UI MUST pass the exact selected SSD UUID, require actual mounted writable storage and coordinate an active-worker/model lease before migrating. There is currently no safe general-purpose web endpoint for moving an active model.

Model execution directly from an SSD needs backend-specific model-path support; the registry alone does not make Hailo/Ollama load from any arbitrary path. SSD bytes are not host RAM, dedicated NPU memory or GPU VRAM. Missing model disks must not trigger automatic replacement downloads onto the internal disk.

## Realistic continuation milestones

1. Authenticated AI Hardware & Model Setup step in the future actual Core installer, responsive Model Manager UI and Software & Update Center package inventory; owner permission gates for drivers, multi-gigabyte weights and network data.
2. Real Pi OS/PCIe/NVMe mapping, supported accelerator package version checks, Hailo model manifest/HEF handling, validated after-upgrade reinstall-free recovery.
3. External SSD model path adapter and engine locks, crash-safe bulk move, hybrid per-model storage, optional offline USB imports and model updates.
4. Private remote pairing and hardware agent (read-only by default), actual GPU/VRAM detection, live streaming with Stop and fair scheduling across multiple clients.
5. Real Pi 5 8 GB and Hailo-10H tests with Kiwix/Kolibri, active original radio recording, thermal/power, multilingual TR/EN/DE, RAG accuracy, CPU/remote fallback and SSD disconnect/reconnect.

## References and status

- [Secure remote inference guide](REMOTE_AI_SERVER_SETUP.md)
- https://www.raspberrypi.com/documentation/computers/ai.html
- https://github.com/hailo-ai/hailo_model_zoo_genai

**No claims of real hardware test success. No installed models, driver changes, disk repartitioning or remote GPU operation have been performed by this PR.**

## Checkpoint 066 experimental Base/Balanced/Advanced operating profiles

The owner wants to physically remove AI HAT+ 2 for a lower-resource setup **without reinstalling or losing basic offline AI**. New system operation profiles **Base (tested CPU-only GGUF), Balanced (tested CPU or separately approved compatible Hailo model), Advanced (verified Hailo-10H compatible model)**, with separately approved `Auto` routing. This is **not** the old Light/Balanced/Maximum model-size shortlist and **not** Eco/Balanced/Custom energy policy. A CPU Base model and boot volume must remain usable after shutting down, disconnecting power, removing HAT and booting again. AI HAT+ 2 and the existing Pi5 NVMe HAT share the exposed PCIe path; current simultaneous NVMe-boot/HAT feasibility is unverified. No hot unplug, auto-reformat, downloads, remote/cloud fallback, or presumed watt savings. Validate device/runtime/model allowlist, original chats, file/wiki RAG permissions, USB storage and actual whole-system energy.

Draft-only code: [router](../../tihulu_runtime/ai_profiles.py), [22 mocked tests](../../tests/test_ai_profiles.py), [compact mode selector simulation](../../prototype/ai_mode_profiles.html) and [full implementation cautions](MODULAR_AI_MODES_BASE_BALANCED_ADVANCED.md). No tested local inference, Hailo GenAI or physical energy benchmark exists. Whole Stage5 not approved.
