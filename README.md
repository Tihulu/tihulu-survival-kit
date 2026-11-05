# Tihulu Survival Kit

**Languages:** **English** · [Turkish](README.tr.md) · German *(planned)*

> [!IMPORTANT]
> **Work in progress — November 5, 2026.** Tihulu is a planned offline-first Raspberry Pi 5 project. **There is no released Tihulu Core image, installer, working portal, or fully validated Raspberry Pi hardware setup.** A [draft development PR](https://github.com/Tihulu/tihulu-survival-kit/pull/1) contains experimental software, not a ready-to-install product.

Tihulu Survival Kit aims to provide a **portable, modular, offline-first knowledge and survival-information hub** with education, navigation, on-device AI, radio, television, and local communication. Phones, tablets, and computers will access the installed services through a local browser, even when the internet is unavailable, subject to the content actually installed.

## Development status

| Component | Current status |
|---|---|
| Public architecture and first-use guides | Documentation available on `main` |
| Optional service manager, shared leases and task lifecycle | Experimental Python code and tests in [draft PR #1](https://github.com/Tihulu/tihulu-survival-kit/pull/1) |
| Running Applications / Window Manager | Standalone interactive demo; not a real device controller |
| Germany/Turkey regions and political/news sources | Candidate data only; no live feed integrations |
| Secure Pi image, first-run wizard, Wi-Fi hotspot and web portal | **Not yet released** |
| AI inference, actual DVB TV/Teletext reception, radio decoding, official emergency alerts | **Not deployed or hardware-verified** |

See [Engineering Development Status](docs/DEVELOPMENT_STATUS.md). Automated prototype unit-test success does **not** establish physical Pi or RF compatibility.

## First-use essentials (planned)

| Item | Planned configuration |
|---|---|
| Local hotspot SSID | **Tihulu Kit** |
| Wi-Fi passphrase | **Unique and owner-provisioned**, never publicly embedded |
| Owner account | Created during secure setup, distinct from Wi-Fi credentials |
| Hotspot hostname | **`tihulu.lan`**, when the Pi actually runs its own AP/DNS |
| Hotspot fallback IP | **`10.10.10.10`**, intended for that hotspot only |
| Pi connected to a home router | **`tihulu.local`** where mDNS works, or its actual router-assigned IP |
| `tihulu.lan` on the home router | Requires a separate router DNS alias; **not automatic** |
| Direct PC Ethernet | Actual link address of the Pi, with optional mDNS |
| Camera/GPS access | Explicit user consent and a trusted HTTPS browser context where needed |

**Installing ordinary Raspberry Pi OS Lite does not create the Tihulu Wi-Fi network or portal.** These settings require a real future installer.

The same authenticated Tihulu interface is intended to work across the Pi's own hotspot, a home router connected via Ethernet or **secondary USB Wi-Fi**, and a properly configured direct Ethernet cable to a PC. Windows ICS, macOS Internet Sharing or Linux NetworkManager can optionally share connectivity from a computer; a cable alone does not enable this. The router LAN will not automatically resolve `tihulu.lan`, and the hotspot fallback IP should not be mistaken for a router LAN address.

The main guides are now available in English: [First-start information](docs/START_HERE.md), [Network and access](docs/NETWORK_ACCESS.md).

## Hardware and energy targets

| Component | Planned or known status |
|---|---|
| Main computer | **Raspberry Pi 5, 8 GB RAM, ARM64** |
| Storage | Approximately **1 TB NVMe** using a Pi 5-compatible PCIe/M.2 HAT |
| Power/cooling | Appropriate Pi 5 supply capability (**5 V / 5 A** target), active cooling and a tested powerbank |
| Network interfaces | Built-in Wi-Fi as a local AP, Ethernet, optional second USB Wi-Fi client |
| SDR radio receiver | Separate receive-only USB SDR candidate; **not confirmed purchased** |
| DVB television | **Hauppauge WinTV-soloHD 01589 European model**, USB **DVB-T/T2/C**, **reported purchased** (Amazon ASIN `B0152XLPFS`) |
| TV antenna | User reports it purchased/ordered; arrival and specific included accessories not verified |
| Clients | iOS, Android, Windows, Linux and macOS browsers |

A DVB-T2 TV tuner **is not** a general-purpose FM/DAB SDR, LoRa or packet-radio transmitter, or DVB-S/S2 satellite receiver. Pi5 ARM64 kernel/firmware support, actual signal lock, and H.265/HEVC playback still require real tests.

The Pi's **8 GB RAM** and shared power budget limit simultaneous large AI models, speech tasks, tuner operation, NVMe, networking and video processing. Battery life and thermal limits cannot be inferred from advertised product figures.

## Installation — not available yet

When Tihulu Core is implemented, the intended installation experience is:

1. Select a vetted **Minimal Core**, **Full Offline**, or **Custom/Hybrid** image, with an optional PC preparation workflow.
2. Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to write the verified image to the correct NVMe device. **Imaging can erase the selected disk.**
3. Boot the Pi, connect to the configured hotspot or an allowed local network, and create secure owner credentials.
4. Choose preferred interface language **independently** from country/region.
5. Use **Quick Setup**, a conventional Next/Back flow, or **Advanced Settings** with real download sizes and permission prompts.
6. Install missing Wikipedia ZIM archives, courses, maps, AI/translation models or optional modules later through the planned Update Center.

There is **no functional installer, image, or verified download checksum** currently offered here. Future releases must be published under [GitHub Releases](https://github.com/Tihulu/tihulu-survival-kit/releases). Detailed preliminary [Installation Guide (English)](docs/INSTALLATION.md).

## Planned applications

| Module | Intended functionality |
|---|---|
| **Offline Knowledge** | Original English/Turkish Wikipedia ZIM archives, Kiwix and existing HAS/IIAB reference and preparedness materials |
| **Learning** | Kolibri courses and educational media |
| **Offline Maps** | Regional OSM map tiles, actual routing graphs/geocoder, optional user-authorized phone GPS |
| **Emergency Center** | Time-stamped official-source alerts by region, explicit monitoring controls and preserved original recordings |
| **Local AI** | On-device GGUF model profiles, consent-based file/RAG search, chats and cancellable jobs |
| **Translator, OCR, ASR/TTS** | Shared on-demand language workers, optional live phone-camera OCR and timed subtitles |
| **Browser** | Ordinary browsing/PDF support plus offline wiki/courses; translate non-supported languages before optional grounded AI analysis |
| **Files / Office / Media** | NVMe and USB, permissioned Nextcloud/WebDAV, Office/PDF and media playback |
| **TV Center** | Country/region channel lists, owner-added channels, DVB auto/manual scanning, recorded/live subtitles, EPG and Teletext |
| **Radio / Text Data** | Optional SDR radio, FM RDS/RadioText, DAB+ DLS/Journaline, and documented APRS candidate reception |
| **Message Networks** | Optional local offline Wi-Fi BBS/forum and separate, lawful Meshtastic or packet-radio interfaces with compatible hardware |
| **News & Politics** | User-selected mainstream, independent, public, opposition and party-published sources in Germany/Turkey, plus worldwide verified public political accounts |
| **Daily Discovery** | Sourced daily article/fact, survival tip, dictionary word, profanity/slang definition and offline Wikipedia A-to-B link challenge |
| **Service & Update Center** | Install/refresh options, per-app Hard/Background/Startup policies, memory-conscious scheduling and safe stop controls |

**These are planned capabilities, not a list of installed applications.** The architecture may incorporate selected capabilities from [HAS Prepper Disk](https://github.com/schematrix/HAS_Prepper_Disk), [Internet-in-a-Box](https://github.com/iiab/iiab), [Kiwix](https://www.kiwix.org/), [Kolibri](https://learningequality.org/kolibri/), [Project NOMAD](https://github.com/Crosstalk-Solutions/project-nomad) and [OpenStreetMap](https://www.openstreetmap.org/). Their actual packaging, ARM64 support, attribution and licenses must be checked separately.

## Background tasks, memory and app management

**Running Applications / Task Center** is planned as a browser-based manager, not a replacement for the Linux desktop window manager. Users should be able to multi-select optional apps, open or close views, change **Hard Enabled / Background Enabled / Start at Boot**, and see real CPU/RAM use once instrumentation exists.

Closing a browser tab **must not cancel an authorized server-owned TV/radio recording, file transfer, or long AI task**. A real stop action must request cancellation, wait for safe backend finalization, and only then display **Stopped**. Core network/authentication/storage services and consented Emergency monitoring receive additional protection.

Common Translator/ASR/AI workers should share one backend instance with task leases, using RAM only when needed. **News background fetching is OFF by default**. A user may enable bounded scheduled updates; the intended local article/social cache expires **24 hours after publication** with a **30 MB target limit**, never deleting original media recordings, forum posts or personal files. Those cache and scheduler features are **not implemented** by the current data files.

An experimental [task/service management prototype](https://github.com/Tihulu/tihulu-survival-kit/pull/1) and its tests exist in a draft branch.

## Regional television, Teletext and radio messaging

The proposed **Region Manager** starts with all **16 German federal states** and **81 Turkish provinces**. Country, region, language, frequency and saved channel profiles are independent. A channel's official website or directory presence does **not** prove terrestrial DVB reception or an authorized embeddable live stream.

The purchased TV receiver may carry ARD Text, ZDFtext, TRT TELEGUN, EPG and DVB subtitles **only where the tuned real broadcast includes these services**. Teletext is **one-way**, so users cannot reply over the same TV receiver.

A separate radio/SDR receiver and suitable antenna are necessary for FM RDS/DAB text or APRS reception. **Two-way** CB/ham packet BBS, Meshtastic or Winlink require suitable transmitting hardware, network coverage and relevant authorization. A future **Tihulu Local BBS** would support authenticated LAN-only messages without RF transmit hardware.

News catalog candidates include public broadcasters, critical/opposition and independent journalism, mainstream organizations, and political party self-publications across the spectrum. Public statements by politicians are not the same as verified journalism. Real account handles, APIs and streaming availability must be checked before enabling feeds.

## Browser camera OCR, safety and privacy

The intended OCR workflow is **request permission → choose a camera or text area → read selected frames → inspect/copy → optionally translate/ask AI → save or stop**. A Tihulu server cannot silently access a user's phone/desktop camera or full local disk. Camera/geolocation may require trusted HTTPS; video frames are not stored permanently by default. Unsupported OCR/translation languages must show accurate missing-package states.

No real Wi-Fi password, TLS key, API token, private source file, personal location or account secret should be committed. Local home-network reachability is not public internet access; owner authentication, device permissions and scoped file access are still needed. Emergency content must have official source/time provenance and may go stale when monitoring is disabled.

**Tihulu is not an official emergency-warning service, medical device, or substitute for emergency responders.**

## Acceptance tests and release requirements

An actual Tihulu release must first validate Raspberry Pi 5 boot from NVMe, hardware power/thermals, local HTTPS, hotspot and home-router networking, phone/PC browsers, real offline Wikipedia/course/map packages, camera permissions, concurrency, AI memory and cancellation, DVB/SDR reception, original audio/video preservation, user authorization, honest emergency timestamps and safe updates.

See the [Development Status](docs/DEVELOPMENT_STATUS.md) for open work. Passing tests of prototype policy classes alone is **not** sufficient.

## Documentation

| Document | Language |
|---|---|
| [Engineering Development Status](docs/DEVELOPMENT_STATUS.md) | English |
| [First-start essentials](docs/START_HERE.md) | English |
| [Installation guide](docs/INSTALLATION.md) | English |
| [Network access guide](docs/NETWORK_ACCESS.md) | English |
| [Live OCR and device permissions](docs/LIVE_OCR_AND_PERMISSIONS.md) | English |
| [Features and system architecture](docs/FEATURES_AND_ARCHITECTURE.md) | English |
| [Development collaboration policy](AGENTS.md) | English by default for GitHub engineering, localized files welcome |

**English is the primary documentation language.** All linked main guides are in English. The original Turkish README and guide translations are preserved as [README.tr.md](README.tr.md) and [docs/tr](docs/tr/). A future German translation will be linked only once prepared.

## License

The original Tihulu Survival Kit code and project-authored documentation are licensed under the **GNU Affero General Public License version 3.0 only (AGPL-3.0-only)**. See the complete [LICENSE](LICENSE) text.

**AGPLv3 includes a network-use source-sharing requirement:** When a modified covered program is used to interact with users over a network, those users must be offered its corresponding source as required by section 13. Future Tihulu web interfaces should include a visible **Source Code / License** link. This license does **not** replace the independent licenses of bundled third-party software, offline Wikipedia data, datasets, media, fonts or hardware firmware; redistribution requires compliance with those terms as well.

## Contributions and licensing

Please use [GitHub Issues](https://github.com/Tihulu/tihulu-survival-kit/issues) for suggestions or technical reports; do not post private credentials, tokens, locations or files. GitHub engineering communication should generally be in **English**. Turkish and German documentation, translations and user-interface text are explicitly welcome.

The project's original work is AGPL-3.0-only, while third-party software and offline content retain their own attribution and licensing requirements. A complete redistributable Tihulu appliance image has not yet been published.

---

**Release status: NOT RELEASED.** Documentation and an experimental draft branch exist; Pi hardware integration and production deployment remain outstanding.
