# AI HAT+ 2 after installation — boot-time detection, updates and mode changes

> **Status (November 6, 2026):** This is the approved direction of the **Stage 10 review amendment**, not a functioning Raspberry Pi boot detector or released setup app. Read [SSH access](SSH_ACCESS.md) only when advanced diagnostics are needed.

## Owner workflow

1. **Before changing PCIe hardware, power off the Raspberry Pi completely** and check its real boot drive. A Pi 5 using the single exposed PCIe lane for NVMe boot may not be able to use that same connector for an AI HAT+ 2 without a separately verified storage/PCIe arrangement. If removing the NVMe HAT prevents boot, software cannot perform any detection.
2. Connect an actually compatible AI HAT+ 2 only after resolving physical mounting, boot storage, power and cooling; then power on.
3. On **every successful boot**, a planned lightweight read-only inventory compares Pi/PCIe/Hailo, attached disk/SSD and available runtime with the **last verified inventory**. No automatic LLM load, driver install, model download or mode switch occurs merely from detecting a new device.
4. If the HAT is newly present, the authenticated owner sees **New AI hardware detected** in `Home > Notifications`, `Settings > Hardware`, and `AI Hardware & Model Setup`. A **Check again** control is also available later without OS reinstallation.
5. The Setup panel distinguishes **Detected hardware**, **Driver/runtime installed**, **Compatible NPU model installed**, **Operational after real load/test**, and **Current AI mode**. These are separate states.
6. Offer compatible missing Hailo runtime/driver/model packages in **Software & Update Center**, including verified source, size/license, expected space, optional reboot and owner approval. A package may be marked **Pending reboot**. Unknown or unsupported means unavailable, never an invented AI result.
7. The owner chooses **CPU Local**, **Hailo NPU Local** (only when compatible and tested), **Private LAN Remote AI** (separately authenticated and consented), or **Auto / preferred**. The previously working CPU model/configuration and accessible storage remain as fallback. Never silently send private content to a remote server.
8. If HAT is removed after full power-off, NPU fails or external SSD is missing, the kit should retain offline Home/Guide/Radio and offer the previously verified CPU fallback **only if still installed/usable**, while showing the NPU/model as unavailable. No silent reinstall or deletion of models/history/recordings.

## On-device Guide integration (planned)

`Guide > Hardware upgrades > AI HAT+ 2`, `Settings > Hardware > Detect changes`, `AI Hardware & Model Setup > Recheck`, and `Software & Update Center > Hardware dependencies`. Show last detection time, source of evidence, real effective vs preferred mode and owner-visible rollback result. Do not request the entire first-boot Setup Wizard again.

## Acceptance before claiming implementation

Actual Pi5 cold-boot before and after power-off HAT attachment and removal; genuine Hailo-10H hardware ID, driver, compatible model load and inference; unchanged NVMe boot/USB SSD mount; user-approved updates and reboot verification; absence of model/driver and no-boot recovery; radio recording protection; cross-device Settings/Guide behavior; no unauthorised background network use. Mock tests are not hardware acceptance.
