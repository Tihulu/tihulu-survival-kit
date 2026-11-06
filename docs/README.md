# Tihulu Survival Kit — Documentation

**Primary documentation language: English.** Tihulu is **not yet a released or installable Raspberry Pi appliance**. This index lists design guides and factual implementation status, not verified operating instructions for an already deployed device.

## Start here

- [Getting Started](START_HERE.md) — hotspot name, passwords, network addresses, first boot and FAQ.
- [Installation & First Configuration](INSTALLATION.md) — hardware, imaging and proposed first-run wizard.
- [Network Access](NETWORK_ACCESS.md) — Pi Wi-Fi hotspot, router Ethernet, second USB Wi-Fi, direct PC Ethernet and HTTPS.
- [Live Camera OCR & Permissions](LIVE_OCR_AND_PERMISSIONS.md) — camera consent, local processing, language packs and privacy.
- [Features & System Architecture](FEATURES_AND_ARCHITECTURE.md) — planned modules, boundaries, resources and validation.
- [Engineering Development Status](DEVELOPMENT_STATUS.md) — real repository status, experimental PRs and missing integrations.
- [Channel & Signal Explorer (experimental branch)](https://github.com/Tihulu/tihulu-survival-kit/blob/feature/on-demand-service-manager-2026-11-05/docs/CHANNEL_SIGNAL_EXPLORER.md) — published frequencies, manual/band scans, TV/Radio saved channels and Text/Data Browser constraints.

## Language versions

The English files above are the default documentation. [Turkish translations](tr/) are kept in a dedicated language directory, and the [Turkish README](../README.tr.md) is available separately. A German documentation set is **not yet complete**. Legacy `*_TR.md` paths are short **English compatibility notices** pointing readers to the new English and localized paths.

GitHub development communication is normally English; locale-specific UI/documentation files may use their own language as described in [AGENTS.md](../AGENTS.md).

## Implementation notes

The main branch contains documentation, while the experimental [draft PR #1](https://github.com/Tihulu/tihulu-survival-kit/pull/1) contains Python policy and logical job-manager prototypes, tests and candidate data catalogs. No Pi image, verified DVB/SDR device compatibility, secure production portal, live political news feeds or working OCR service has been released.

## SSH, security and post-install hardware

- [SSH & Terminal Access](SSH_ACCESS.md) — planned Linux user `tihulu-kit`, conditional Wi-Fi/LAN SSH commands, owner-only local credential setup, password/SSH-key changes and troubleshooting.
- [AI HAT+ 2 after installation](AI_HARDWARE_UPGRADES.md) — detect added/removed NPU hardware after a safe power-off and reboot, show verified driver/model readiness and offer consented CPU/NPU/remote mode changes.
- Turkish: [SSH erişimi](tr/SSH_ACCESS.md) · [Sonradan AI HAT yükseltme](tr/AI_HARDWARE_UPGRADES.md).
- German: [SSH-Zugang](de/SSH_ACCESS.md) · [AI-Hardware nachrüsten](de/AI_HARDWARE_UPGRADES.md).

These are **planned Guide chapters**, not proof of a shipped interactive Guide or implemented hardware detection. Personal OS passwords are not published.
