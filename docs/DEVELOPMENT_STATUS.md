# Tihulu Survival Kit — Engineering Status and Next Integrations

**Status: experimental development / no public release.** Updated November 5, 2026.

This is a public summary of the planned product and demonstrable repository state. It is not a report of operational emergency monitoring, compatible radio reception, AI inference, or a working Pi hotspot.

## Repository branches and implementation status

| Item | Status | Where to look |
|---|---|---|
| Public English README and main guides | Documentation on `main` | [README](../README.md) and [Documentation Index](README.md) |
| Stage 4 optional-service policy and shared worker leases | Experimental Python source and unit tests | [Draft PR #1](https://github.com/Tihulu/tihulu-survival-kit/pull/1) |
| Per-device logical app views, server-owned jobs, cancellation-request semantics | Experimental library and tests | Draft PR #1, `tihulu_runtime/app_manager.py` |
| Running Applications / Task Manager visual interface | **Standalone demo**, not a device controller | Draft PR #1, `prototype/task_manager.html` |
| DVB Teletext, RDS/DAB/APRS and messaging network directory | **Candidate metadata**, no RF integration | Draft PR #1, `data/radio_text_networks.json` |
| News & Politics Center, worldwide official political accounts, 24h news cache | Planned; no real source ingestion, feeds or live API keys | Integration backlog below |
| Region & Broadcast Manager (Germany/Turkey) | Planned; no live DVB frequency scan or channel listings verified | Integration backlog below |
| Offline Local BBS forum on Pi hotspot | Planned only | Draft PR #1 documentation |
| Actual Pi5 NVMe boot image, captive portal and authenticated runtime | Not implemented or benchmarked | Future release |

Automated tests exercise local policy and job registry behavior, not OS/systemd integration, actual cancellation of real processes, radio signal demodulation, subtitle translation, or Pi5 8GB performance.

## Purchased/project hardware and actual verification

The project owner reports **purchasing a European Hauppauge WinTV-soloHD 01589** USB DVB-T/T2/C receiver, Amazon.de ASIN `B0152XLPFS`, along with TV antenna equipment. **Physical arrival, exact accessories and Linux/Pi5 firmware, signal and HEVC playback compatibility have not been verified.** The receiver is a receive-only digital terrestrial/cable TV tuner and is not an FM/DAB general-purpose SDR or LoRa/packet transmitter. A separate suitable SDR or radio transceiver is needed for other RF data services; no generic SDR purchase is assumed.

## News input selection and scan experiment (November 5, 2026)

The experimental [draft PR #1](https://github.com/Tihulu/tihulu-survival-kit/pull/1) includes a selectable **Internet / TV Antenna / Radio Antenna** source router, explicit manual scan gates, tests, and a **local-only UI prototype** in `prototype/news_inputs.html`. Sources can be individually selected, and the prototype distinguishes unverified source candidates from actual hardware availability.

**Important:** The code does **not** perform physical DVB tuning, decode Teletext pages, read RDS/DAB data, fetch live RSS or social API results, or check real antenna reception. Those require actual connected hardware, validated broadcaster sources, secure backends and per-user authorization. The TV receiver cannot be treated as a general radio SDR, and an active television recording must not be interrupted by a scan.

See the [project license](../LICENSE): original Tihulu work is **GNU AGPL version 3.0 only**; third-party content and software retain their own licenses.

## Multi-source News translation and AI experiment (November 5, 2026)

Draft PR #1 includes `tihulu_runtime/news_assist.py`: a dependency-injected, **experimental** local assistant coordinator that accepts multiple source-attributed text items from selected Internet/DVB/Radio inputs, supports multiple requested output translation languages, and optionally invokes **Summarize**, **Ask a question**, and **Compare different sources** in one authorized foreground task. It acquires the same Stage 4 `translator` and `local_ai` worker leases used elsewhere, validates missing installed language pairs and models, and releases worker leases after success or failure. Unit tests use mock engines; **there is currently no deployed Translator/LLM model or real ingest/decoder connected**.

The English `prototype/news_inputs.html` displays a multi-select UI for independent transports, individual source candidates, output languages and AI actions. Its task preview never claims to perform actual translation or analysis. The original text and source attribution, cache rules, owner permissions and the protected recording state remain essential future production requirements.

## Upcoming user-requested functional scopes

### 1. Region & Broadcast Manager

- Germany (16 federal states) and Turkey (81 provinces), then supported other regions; country/state/province/district or postcode selection independent from UI language.
- Separate **actual received DVB-T2/DVB-C channels** from broadcaster Internet links/authorized IPTV and unsupported or unavailable sources.
- Local frequency tables, auto/manual DVB tune, signal/lock diagnostics **only when a real tuner works**. Preserve previous regional profiles and favorites across changes.
- Channel directory targets public and private German/Turkish broadcasters, original DVB subtitles, and Teletext/EPG/HbbTV signal metadata where the actual multiplex carries them.

### 2. News & Politics Center

- Owner-selectable directory covering conventional/public-service, independent, critical/opposition and self-published political sources across Germany and Turkey; includes smaller left/right/fringe organizations. Party publication and original statements must be clearly distinguished from independently verified reporting.
- Worldwide politician, parliament and public-institution official social accounts, only after account identity and permitted feed APIs are validated. No invented handles, unauthorized scraping or implied political endorsements.
- **Default background OFF** and foreground refresh on entry (optional). Owner may opt into bounded, timer-driven background refresh.
- **24-hour publication-age retention** for cached articles/social posts, **30 MB target cache**, minimal text/metadata and no automatic video downloads; preserve original radio/TV recordings, user files, BBS posts and saved source subscriptions.
- Optional user-invoked offline Translator and AI source comparison via shared workers; no automatic always-resident LLM.

### 3. Running Applications / Task Center

- Separate app availability, Hard Enabled, Background Enabled and Start at Boot; show real observed resource use only after instrumentation.
- Bulk-select optional application views to open/close; closing a tab must not cancel authorized server-owned TV/radio recordings, file transfers, or long AI tasks.
- Per-job cancellation request with **real executor acknowledgment** before marking stopped; safe recording finalization, protected Pi core and independent Emergency monitoring permission.

### 4. Teletext / Radio Data / Message Networks

- With the purchased TV tuner: receive DVB Teletext, subtitles, EPG and HbbTV signalling **only when present in a tuned transport stream**. Teletext cannot send messages.
- Separate capable radio receivers/decoders for FM RDS/RadioText, DAB+ DLS/Journaline/slides, APRS and applicable weather text. Suitable antennas/hardware still required.
- True two-way off-grid radio communication (Meshtastic, CB packet BBS, amateur packet and Winlink) needs lawful compatible **transmitting** equipment and applicable authorization. No automatic TX. An optional offline **Tihulu Local BBS** would instead work among devices on the local Pi Wi-Fi/LAN when installed.

## Language and contribution guidance

Use English by default for code review, issues, PRs, commit messages, technical decisions and developer-facing documents. **Localized Turkish/German/English content is permitted**, including UI labels, help pages and language-specific documentation. See [AGENTS.md](../AGENTS.md). Future localized README variants will be a separate task.

## Before any production or release claim

Actual Raspberry Pi 5 ARM64 tests: secure boot and NVMe integrity, real local HTTPS/auth, tuner firmware and RF lock, source/public broadcast legality, decoded Teletext pages, cache expiry, user privacy, systemd process control, multi-device concurrency, true cancellation and safe audio/video recording flush, sustained memory/power/thermals, platform API terms, and offline recovery.

**Release status must remain "planned" or "experimental" until these gates pass.**

## Documentation language

The [main README](../README.md), [documentation index](README.md), and core guides (Getting Started, Installation, Network Access, Live OCR and System Architecture) are now **in English**. The original Turkish editions are preserved under [docs/tr/](tr/) and [README.tr.md](../README.tr.md). Legacy `*_TR.md` links display English compatibility notices and link to the moved translations. This is a documentation update, **not a new implementation/release claim**.
