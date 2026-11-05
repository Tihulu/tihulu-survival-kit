# Modular AI modes — Base / Balanced / Advanced

**Status, 2026-11-05:** Pure Python routing prototype and standalone HTML simulation only, in Draft PR #1. Not deployed on Pi, no actual AI HAT+ 2 model inference, power measurement, or physical removal test. Whole Stage 5 design still under review.

## Why these are deployment profiles, not model-size aliases

- **Base:** HAT-independent compatible CPU GGUF (small enough for a verified Pi 5 RAM budget) stored where it remains available in both HAT-present and HAT-removed layouts. This is the **offline fallback**.
- **Balanced:** a tested medium CPU model, or a separately owner-authorized compatible Hailo model. If model/device is not ready, choose installed Base. Do not assume accelerator inference uses more/less total energy without measurements.
- **Advanced:** verified Hailo-10H and compatible Hailo generative model, not general GGUF. If physically absent, Advanced *preference* persists while effective profile downgrades to **Base**; if Hailo is present but incompatible/unavailable, an already-installed verified Balanced or Base can be selected.
- **Auto:** a routing policy, not a fourth model-quality tier. Defaults to Base until Advanced automatic promotion is explicitly approved. If owner has consented and the HAT/model are verified, may choose Advanced; after a safe power-off/HAT removal/reboot, return to Base without reinstall.

Historical **Light / Balanced / Maximum (Experimental)** describe CPU model-size target tiers and remain available for model choice. Existing **Eco / Balanced / Custom** in `ai_energy.py` describe energy/evidence strategy, not the new system profiles. CPU/Hailo/remote are **backend types**. These axes must not be conflated.

## Developer prototype

- [Pure router](../../tihulu_runtime/ai_profiles.py): `ProfileModels` slot identities, `ProfilePreference`, `choose_profile` and `is_hat_upgrade_candidate`. No hardware writes, model downloads, disk formatting, inference, remote network, or auto-installer actions. It **requires trusted upstream installed model identity, observed memory budget, readiness and Hailo-10H firmware verification**. It rejects a model not compatible with its backend/memory or not present in the runtime-verified model allowlist. Remote backend is **never** an automatic fallback.
- [Mock-only tests](../../tests/test_ai_profiles.py): 22 declared tests for HAT absent/present, preserved owner preference, Auto opt-in, forcing Base while HAT is present, NPU runtime missing, model missing, memory mismatch, base storage missing and no remote fallback.
- [Compact demo](../../prototype/ai_mode_profiles.html): dark responsive profile selector with **simulated** HAT and model toggles. This HTML is **not wired to the Python router or any hardware**, so its Balanced status is informational rather than a tested model route. The on-screen hardware switch does not control an actual PCIe board.

Run the test suite in a developer checkout:

```bash
python3 -m unittest tests.test_ai_profiles -v
python3 -m unittest discover -s tests -v
```

Do not claim the tests have passed without an observed local or CI execution. Python library is policy and needs actual authenticated installer/inference routing before any runtime promises.

## Installation and physical swap warning

The AI HAT+ 2 connects to **Raspberry Pi 5 PCIe**. Existing NVMe HAT for OS boot also ordinarily uses that same Pi 5 PCIe connector, so the full Pi root/model storage layout must be redesigned and tested for both HAT-present and HAT-absent configurations. A validated USB 3 SSD boot/layout might work, but do not automatically migrate or reformat the existing owner NVMe. Avoid unverified passive PCIe splitters. The Base GGUF model must be on media accessible **with and without** HAT+ 2; an unplugged external SSD cannot support offline fallback.

Physically changing the HAT is **NOT HOT SWAPPABLE**: shut down Pi and disconnect **all power** before attaching/removing HAT, then reboot and re-probe device/driver and compatible model. An unexpected runtime NPU failure can trigger an application-level downgrade to a separate CPU model with careful job reconciliation; don't repeat non-idempotent actions automatically or erase data.

Official Raspberry Pi AI HAT guidance: https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html
Official GenAI/driver guidance: https://www.raspberrypi.com/documentation/computers/ai.html

## Future runtime integration gates

1. Verified Pi5 first boot CPU GGUF model and actual inference; alternative storage topology that still boots with HAT+ 2 installed and HAT physically absent.
2. Device/firmware/driver verification (`hailortcli fw-control identify`), supported Hailo GenAI model registry, independent host vs HAT memory, No NPU model means no fake Advanced.
3. Owner-authenticated saved profile vs effective routing; explicit model install, HAT presence change recovery, no unapproved remote fallback/download.
4. Stage4 protected Service/Energy worker leases and index/parser compatibility; proper model unloading, false energy ranking prohibited.
5. Measure total system idle W and task joules, with comparable work and actual battery/SSD/USB/TV/SDR conditions. Account for AI HAT idle draw and any remote server power.
6. Keep all offline Guide, Kiwix, Files and verified Emergency functions available even without a Local AI model.

No claim of completed physical hardware, installer or energy tests is made in this document.

## Checkpoint 067 — Read-only boot-medium evidence added

A non-mutating diagnostic `python3 -m tihulu_runtime.ai_setup --boot-topology` now calls `ai_boot_topology.py` and provides a conservative root-drive classification with physical HAT change **never automatically authorized**. See [BOOT_TOPOLOGY_PREFLIGHT.md](BOOT_TOPOLOGY_PREFLIGHT.md) for the supported `/proc` / UUID scan, explicit unknown states and actual two-configuration Pi test procedure. The `ai_mode_profiles.html` card now has a **simulated** disk type selector to explain PCIe NVMe risk. This change is not a functioning bootloader, installer or proven energy saving. 13 synthetic tests were executed and passed locally; CI and real device verification remain outstanding.

## Checkpoint 068 — Proving a Base mode without silently burning power

A configured Base CPU model is not necessarily operational. The draft `ai_base_readiness.py` policy now requires distinct evidence of selected model ID, accessible expected SSD, valid GGUF marker, checked owner-registered hash, found CPU runtime, and a real successful model-specific CPU inference test. The CLI `--base-readiness` can gather currently available metadata with **optional explicit** `--verify-base-hash` (off by default; potentially expensive for multi-GB models). It never runs an inference test or authorizes a physical HAT swap, and a single successful current boot never proves the other hardware layout. See [Base preflight guide](BASE_READINESS_PREFLIGHT.md). 16 Base and 13 boot synthetic tests passed locally; GitHub-wide CI/hardware evaluation remain pending.
