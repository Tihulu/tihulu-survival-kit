# Tihulu Survival Kit — Installation and First Configuration

> **Project status — November 5, 2026:** This is a **proposed installation guide**, not a working installer manual. The repository currently provides **no released Tihulu Core image, image builder, GitHub bootstrap script, or production distribution**. The steps below will be actionable **only after the relevant software is published**. Installing ordinary Raspberry Pi OS Lite does **not** automatically install Tihulu apps, the hotspot, Home or Guide. Do not run an unverified `curl | bash` command.

## Contents

1. [Hardware and prerequisites](#1-hardware-and-prerequisites)
2. [Choose an installation method](#2-choose-an-installation-method)
3. [Write a verified image to NVMe](#3-write-a-verified-image-to-nvme)
4. [First boot, hotspot and addresses](#4-first-boot-hotspot-and-addresses)
5. [Quick, Standard and Advanced setup](#5-quick-standard-and-advanced-setup)
6. [Content, model and map downloads](#6-content-model-and-map-downloads)
7. [Network and PC internet sharing](#7-network-and-pc-internet-sharing)
8. [HTTPS, phone camera and live OCR](#8-https-phone-camera-and-live-ocr)
9. [Services and updates](#9-services-and-updates)
10. [Validation, troubleshooting and data safety](#10-validation-troubleshooting-and-data-safety)

## 1. Hardware and prerequisites

**Target hardware configuration, still requiring real end-to-end validation:**

- **Raspberry Pi 5 (8 GB RAM)** with active cooling, a compatible Pi 5 NVMe PCIe/M.2 HAT/adapter, and an adequately rated supply matching the Pi's USB-C power requirements.
- Approximately **1 TB NVMe** storage (Acer FA100 is a design example). A USB-to-NVMe adapter for writing from a desktop computer may be useful. **Writing a disk image may erase all data on the selected target.**
- A phone, tablet or computer for initial access (iOS, Android, Windows, macOS or Linux).
- Optional: a **second USB Wi-Fi adapter** for router/client mode while keeping the built-in Pi hotspot; Ethernet cable for router or direct-PC access; USB SDR and appropriate antenna; powerbank; USB storage.
- Internet is **optional for already-installed content**, but a minimal Core cannot magically include full Wikipedia archives, routable offline maps, OCR language packs or large AI models. Missing packages must be installed later through permitted online downloads or verified USB import.
- **TV hardware update:** The project owner reports purchasing a **Hauppauge WinTV-soloHD EU 01589** USB DVB-T2/C tuner and obtaining/ordering a TV antenna. Compatibility, driver firmware, accessories and local reception remain unverified; this is not an SDR receiver.

This configuration is a **target**, not an endorsed, tested shipping device. Enclosure, cooling, battery, and RF components need actual hardware validation.

## 2. Choose an installation method

| Proposed future method | Intended use | Benefit / limitation |
|---|---|---|
| **Tihulu Minimal Core** | Small first-boot setup on phone with later selective package installation | Minimal initial image; Wi-Fi and offline Guide included *if the future image actually implements them* |
| **Tihulu Full Offline** | Ready-to-use local archives and learning resources on first boot | Very large image; inspect a real manifest of installed content |
| **Tihulu Custom / Hybrid Image Builder** | Prepare selected packages from a computer | Choose which modules to bundle, install later or omit |
| **Complete Setup on PC** | Preconfigure an image before placing NVMe in the Pi | Avoid repeating setup on Pi if the image is genuinely configured and verified |
| **Raspberry Pi OS Lite + GitHub (advanced)** | Low-level development or manual future installation | **No production Tihulu bootstrap exists yet.** Stock Pi OS will not create Tihulu Kit, `tihulu.lan`, Home, or Guide |

**There is no downloadable Tihulu release at present.** When releases become available, use only real artifacts published under [Releases](https://github.com/Tihulu/tihulu-survival-kit/releases) with verified checksums or signatures. An empty Releases page is expected while the project is in development.

### Temporary Pi OS preparation for developers — NOT a Tihulu installation

A developer who wants to test the hardware before Tihulu ships can use the official [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to install **64-bit Raspberry Pi OS Lite** to supported storage. This installs only Raspberry Pi OS; **there will be no Tihulu hotspot, portal or application suite**. Use owner-specific credentials and never publish secrets in issues, public logs or example configs.

## 3. Write a verified image to NVMe

*These instructions apply only when a genuine Tihulu image has been released.*

1. Obtain the exact published `.img` or `.img.xz` file and verify its **actual version, origin and SHA-256 digest/signature** against official release metadata.
2. Connect NVMe to your computer through a suitable USB-to-NVMe adapter. **Back up anything important** and verify the target model, capacity and device identity **twice**.
3. Open **Raspberry Pi Imager → Use Custom**, choose the real Tihulu image, select the correct NVMe target and allow verification to complete. Standard Raspberry Pi Imager is **not** claimed to have built-in Tihulu-specific Wikipedia/map/model selection; that would require a separate Tihulu Image Builder.
4. Attach NVMe/HAT to the Pi 5 and connect cooling and adequate power. Verify Pi EEPROM/firmware, HAT and NVMe boot compatibility on the actual hardware.
5. A public shared image must **not** contain universal admin or Wi-Fi passwords. These should be created through secure, device-specific first-run provisioning.

## 4. First boot, hotspot and addresses

Planned identifiers after Core is installed:

- **Hotspot SSID:** `Tihulu Kit`.
- **Hotspot passphrase:** Owner-generated/provisioned securely, **not published on GitHub**.
- **Pi hotspot URL/address:** `tihulu.lan`, proposed fallback IP `10.10.10.10`, only when the appropriate AP/DNS services are truly installed.
- **Pi on the home router:** `tihulu.local` if mDNS is supported, otherwise the Pi's **actual router-assigned IP**.
- **`tihulu.lan` on home-router Wi-Fi:** Only if the router resolves that name via an explicitly provided DNS alias.
- **Direct Ethernet to computer:** Pi's actual link IP or mDNS when supported; **not automatic internet sharing**.
- **No WAN:** Installed local apps and previously downloaded archives can still be available.

See [Network Access](NETWORK_ACCESS.md). Using a router does not automatically expose a Pi to the public internet; using the Pi's hotspot does not require a phone to have WAN connectivity.

## 5. Quick, Standard and Advanced setup

### Quick Setup (recommended)

1. Establish a user session and securely create/confirm the owner account and Wi-Fi passphrase.
2. Select **English / Turkish / German UI language** independently from location.
3. Choose one or more **countries/regions** and see how they affect **map tiles, actual routing graph, geocoder** and the **Emergency My Countries** filter.
4. Choose Ethernet, second USB Wi-Fi, optional PC Internet Sharing, or **Continue Offline**.
5. Review package status: **installed / install now / requires download consent / install later / incompatible**. Show actual download sizes, free disk space, model/content license and metered-network usage.
6. Make an **explicit Emergency monitoring choice**. Merely selecting a country or region must **not silently enable alerts**.
7. Choose **Start Installation**; only once basic Core is genuinely ready should the UI offer **Open Home**. Any larger deferred archives must be labelled as pending.

### Standard Setup

Offer the same choices in short, understandable **Next / Back** screens, with safe defaults rather than requiring technical configuration knowledge.

### Advanced / Custom Setup

Allow individual selection of apps, Wikipedia ZIM editions, Kolibri courses, languages, OCR/ASR/TTS packs, the three candidate local AI model profiles, map tiles **plus real routing/geocoding data**, power policy, independent **Hard/Background/Startup** settings, NVMe storage and swap configuration.

**Proposed resource defaults:** Core remains protected; even when optional packages are installed, background and startup execution is generally **OFF** until user-authorized foreground use. Light for system AI and Balanced for chat are **candidate defaults**, subject to real Pi tests and download approval. An experimental Maximum/8B model must not be downloaded automatically.

## 6. Content, AI model and map downloads

Distinguish two completion states:

- **Core Ready:** Secure Home, Guide, owner credentials, network settings and package management work; not all desired large archives need to be present yet.
- **Full Offline Ready:** The **user-selected**, manifest-listed Wikipedia/Kiwix content, Kolibri courses, real route/geocoder data, AI models, language packs and application binaries are **present and verified**. Missing packages must not be shown as installed.

Any download should disclose origin, license, compatible version, actual size, required temporary disk space and optional verified offline USB-import path. Large, full original-language English/Turkish Wikipedia ZIM archives remain a design requirement even if they cannot fit into a Minimal Core; they should be marked **Install Later**, not silently removed from the scope.

## 7. Network and sharing a computer's internet

The intended product will support the built-in Pi hotspot **in parallel with** home-router Ethernet, a second USB Wi-Fi client and direct computer Ethernet. Simply connecting a Pi to a computer's Ethernet port does **not** share that computer's Wi-Fi internet. The owner must enable **Windows ICS**, **macOS Internet Sharing** or Linux NetworkManager **Shared to other computers** on the computer itself. Display real IP, gateway and DNS results; sharing may disappear when the PC sleeps.

Instructions: [Network Access](NETWORK_ACCESS.md).

## 8. HTTPS, phone camera and Live OCR

The proposed **Camera → Live OCR** feature asks permission before accessing a camera, lets the user choose an image/region and sampling interval, and returns text which can **optionally** be translated or passed to AI. Closing the camera stops the stream. Permanent video or original-frame saving requires a **separate user decision**. Provide **Choose File / Take Photo** alternatives on client devices.

**Critical:** Live camera and geolocation features may require a **browser-trusted HTTPS secure origin** and OS/browser permissions. Accessing an ordinary HTTP page at `10.10.10.10` **does not mean the camera will work**. Do not claim live OCR is ready until a real trusted-certificate workflow has been tested on target devices.

Details: [Live Camera OCR and Device Permissions](LIVE_OCR_AND_PERMISSIONS.md).

## 9. Services and updates

- **Installed:** Package files genuinely available. **Hard ON:** User-invoked start is permitted. **Background OFF:** No automatic background task, but authorized manual use can run. **Startup OFF:** Not started automatically at boot. **Runtime:** Actual current process state, which must be measured.
- For example, if the user requests a Chinese page translated before an AI summary, a permitted installed Translator starts first, followed by a compatible LLM. When a required service is **Hard OFF**, the UI must offer **Enable for this task / Enable persistently / Continue without it**. Hard OFF must not be bypassed silently.
- For live radio captions, ASR and optional Translator are started only while needed by active clients. Confirmed original emergency recordings must **never** be deleted as temporary cache data.
- The planned **Software & Update Center** should show real installed/compatible versions, sources, download sizes, packages selected for update and user approval. Large automatic downloads are **not default**.

## 10. Validation, troubleshooting and data safety

| Symptom | First checks |
|---|---|
| `Tihulu Kit` is missing | Actual Core image installed? Pi boot, power, HAT and AP service status |
| `tihulu.lan` cannot be reached | Are you on Pi hotspot? On router LAN, use mDNS `tihulu.local` or actual IP |
| Pi connected to PC but no usable IP | Ethernet link, PC DHCP/ICS, link-local or configured static subnet |
| Camera/OCR unavailable | Certificate trust, browser/OS permission, installed OCR worker and language pack |
| Wikipedia/map not available | Does setup mark it actually **Installed** or merely **Install Later**? |
| Local AI is slow | Pi 8 GB RAM; test smaller Light profile and concurrent work, recording and swap pressure; no guaranteed rate |
| Emergency alerts are missing | Opted-in monitoring, valid source permissions/country, WAN/feed freshness, offline status |

**Backups and data protection:** Back up NVMe before imaging. Updates, cleanup and reset workflows must protect user files, learning progress, original received emergency-audio recordings, private settings and AI history. A destructive reset must show exactly what will be removed **before** any action.

## References and related guides

- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- [Raspberry Pi Getting Started / NVMe / Boot documentation](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Raspberry Pi Remote Access / mDNS](https://www.raspberrypi.com/documentation/computers/remote-access.html)
- [Getting Started](START_HERE.md)
- [Network Access](NETWORK_ACCESS.md)
- [Live OCR and Permissions](LIVE_OCR_AND_PERMISSIONS.md)
- [Features and Architecture](FEATURES_AND_ARCHITECTURE.md)
- [Main README](../README.md)
- [Turkish translation](tr/INSTALLATION.md)
