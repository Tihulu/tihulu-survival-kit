# Text & Data Center — Survival Kit Wave 1 integration

Date: 2026-11-06. Status: **PARTIAL PASSIVE BRIDGE / TEST STUB; no live receiver, full UI or Pi 5 deployment.** All user-facing Text Center content must remain English.

## Verified repository state
- Independent reference: https://github.com/Tihulu/TIHULU-TEXT-CENTER at exact main HEAD 0107a9bf5cd374943afcd9e89d49d6f8fcc94191.
- Survival Kit branch base: feature/flight-radar-tar1090-full-map-2026-11-06 at 3bdd6f12e2a4d5dfe8aa13f629ddc1918b46da51. Stage 1–9 designs approved; Stage 10 review pending.
- The independent reference has an existing Python 3.11+ stdlib server bound to loopback 127.0.0.1:8787; numbered local pages; SQLite imported broadcast pages and source-attributed events; RSS/Atom/JSON Feed; passive receiver/capability inventory; manual FM energy survey with rtl_power; synthetic-tested on-demand FM RDS through rtl_fm and redsea; single-owner notebook; responsive HTML/CSS/JS. No Pi5 decoder deployment.
- Code inspected: textcenter/core.py, http_app.py, receivers.py, capabilities.py, conflicts.py, fm_survey.py, fm_rds.py, scan_catalog.py; web/index.html, app.js, styles.css; tests/test_*.py; docs/SURVIVAL_KIT_INTEGRATION.md, AUTO_DISCOVERY.md, ROADMAP.md, README.md.
- No explicit repository LICENSE file was present in inspected root; confirm copy/redistribution rights before vendoring reference source. This branch does NOT vendor it.

## Newly implemented now (limited scope)

1. tihulu_runtime/text_center_integration.py is an owner-scoped passive discovery and shared-SDR reservation contract. It lazily reads the installed reference inventory and 31-capability catalogue when actually available, and reports missing dependencies without inventing station or decoder data.
2. It requires the SAME in-process SDRResourceBroker used by Radio/Flight Radar. FM RDS start is blocked unless a separately implemented REAL cross-process reservation and device-mapped decoder backend are supplied. An external process check or standalone file lock alone is not enough. Only explicit owner action, 87.5–108 MHz and 10–90 seconds; stop ACK required before release. Other tuner/recording owners never preempted.
3. tihulu_runtime/text_center_http.py defines a narrow GET-only authenticated WSGI route family under /text-center/api/ with trusted internal TLS gateway flag, exact hostname allowlist, real owner session callback and no exposed standalone port, BBS writes, RF start, uncontrolled POST or general proxy.
4. tests/test_text_center_*.py test mocked owner authorization, passive side-effect freedom, protected ADS-B collision, hard parameter limits, cleanup, stop ACK and route blocks. These tests do NOT verify actual RTL-SDR or Raspberry Pi hardware.

GET endpoints: /text-center/api/status, /text-center/api/discovery, /text-center/api/capabilities, /text-center/api/pages. They are ONLY mountable by a future authenticated Tihulu Core portal that supplies an owner identity and sets the privileged WSGI environment value after real HTTPS verification. The currently open PR DOES NOT mount the original Text Center HTML UI. Target final UI: authenticated https://tihulu.lan/text-center/ when hotspot DNS and TLS really exist, no direct public port.

## Complete channel/navigation contract

Numbered page system: 100 Main Index; 200 News; 300 Weather; 400 Radio & Broadcast Data; 500 Emergency; 600 Blogs/BBS; 700 Offline Wiki/Library; 800 Gemini/Gopher/Utilities/Text Networks; 850 About; 860 Protocols/Dependencies/Receivers.

Preserve reference Modern and Classic Teletext UI modes, persistent settings, mobile/tablet/desktop touch+keyboard accessibility, live page and subpage navigation, bookmark/search/history, honest source badges, stale timestamps and error/unavailable states. Full UI parity is NOT implemented in this Wave 1 bridge.

Canonical provenance classes: genuine Live RF; Internet; Cached; Offline; Verified Official Alert (only from authenticated official Emergency Center). Original source, decoder, frequency/PID when actually known, received/published timestamp and freshness must be preserved. Mere reference pages, signal-energy peaks, manually imported pages or politician statements are NOT automatically received stations or official alerts.

## Dependency and future integration matrix

| Channel / service | Required real dependency | Current status |
|---|---|---|
| FM RDS, RadioText, RT+; optional traffic/TMC | Nooelec/compatible SDR, suitable FM antenna, rtl_fm, redsea JSON, real hardware lease; TMC licensed tables separately | Standalone bounded RDS adapter synthetic-tested; Kit bridge refuses RF until global broker and real cross-process lock |
| DAB+ DLS/DLS+, Journaline, MOT Slideshow, EPG, TPEG | Compatible DAB decoder exposing real ensemble/service fields; Journaline codec/patent/licensing check | Reference catalogue/import only; no Kit decoder |
| DVB-T2 Teletext pages/subpages, EPG, HbbTV signals | Hauppauge WinTV-soloHD 01589 firmware/frontend, real transport stream + Teletext PID and decoder | Not hardware verified; web ARD Text must NOT be shown as received TV Teletext |
| DRM digital text/EWF; RTTY/Radiotelex; NAVTEX 518 kHz; HF WeatherFAX | Actual compatible HF direct-sampling/receiver and antenna, propagation and per-protocol decoders | Candidate only; Nooelec v5 HF Q-branch feasibility must be tested |
| APRS / AX.25 receive-only | Compatible public amateur band receiver, privacy/authorization | No transmit; hardware/decoder blocked |
| RSS / Atom / JSON Feed / News & Politics | Owner-selected verified HTTPS sources, rate/size limits, shared News cache 24h/30MB and publisher provenance | Standalone import exists; common Kit News DB/retention NOT integrated |
| Gemini, Gopher, external BBS | Native safe protocol clients, bounded parsing, offline snapshots, consent for plaintext Telnet | Web directory links only; native clients pending |
| Local authenticated multi-user BBS | Kit owner session, per-user ACL, quotas, moderation, audit trail | Standalone single-owner notebook only; multi-user gateway blocked |
| Meshtastic/LoRa and packet TX | Separate LoRa-capable transceiver, legal region/airtime controls, user-approved transmit | Absent; RTL-SDR cannot transmit |
| Emergency CAP/BBK/NINA/AFAD | Authenticated official source, validity/expiry, source integrity | Reuse existing Emergency Center; no RDS/Journaline emergency-text elevation |
| Wiki, Kolibri, PDF, Browser, Translate-first AI | One actual Kiwix/Kolibri, installed offline files, existing Translator + selected CPU/NPU/remote AI, owner consent, optional SSD | Planned single shared services; not implemented in this bridge |

## Auto Discover / RF scanning policy

Auto Discover is passive: USB/DVB node candidates, decoder executables, known active receiver tasks, region preset catalogue, source/cache status. No tuner open, retune, RF energy scan, network fetch, auto LLM or hidden background job.

Real FM spectrum scanner may later call rtl_power ONLY via an explicit, bounded, cancellable hardware lease; each peak remains unidentified energy until separate genuine rtl_fm/redsea decoding. DAB/DVB/HF modes need dedicated validated adapters. Single RTL-SDR cannot independently tune 1090-MHz ADS-B, FM, DAB and APRS simultaneously. Extra receivers must be separately discovered and assigned. Protected master recordings stay with original Radio/TV services.

Background work defaults OFF. Optional future schedules require owner authorization, low CPU/RAM/battery/network quotas and true Task Center Stop acknowledgment. Shared News data, region frequency presets, Emergency originals, Translator/AI and storage must not be duplicated into an inconsistent second service.

## Waves and real blockers

Wave 1: DONE now — passive source catalogue, shared broker contract, owner-only GET WSGI, synthetic regression tests, this integration matrix. BLOCKED — complete responsive original UI under /text-center/, actual physical cross-process SDR reservation, genuine FM decoder wired through it, common News storage and authenticated local BBS. The standalone reference works independently but is NOT an integrated Kit radio service.

Wave 2: test true DAB DLS/MOT/EPG, DVB Teletext service+PID/subpages, protected recordings, source verification, authenticated local multi-user BBS.

Wave 3: Gemini/Gopher native clients, Journaline license-dependent integration, HF DRM/RTTY/NAVTEX/WeatherFAX, APRS RX and authorized separate Meshtastic/LoRa hardware, consented shared AI/Translator/offline SSD. No automatic radio transmission.

Engineering acceptance: actual Pi5, Nooelec, Hauppauge, mobile Safari/Android Chrome/iPad/desktop responsive browser, authorized same-origin TLS and CSRF, per-user resource policy, real source timestamps, recording protection, offline cache, power/RAM tests. CI mock PASS does not prove these capabilities. The source repository and existing Survival Kit feature/review branches must remain untouched until normal PR review/merge.

### Synthetic tests

On the full Survival Kit branch, run Python unittest discovery filtered to test_text_center_*.py and compileall for the two new runtime modules. No extra Python dependency is required for the basic bridge; actual reference installation and decoder packages are OPTIONAL and independently verified.

### Release ownership

Preserve public Flight Radar native full tar1090 PRIMARY and lightweight SECONDARY, DAB automatic scan design, News/Radio/TV/ Emergency authority separation, region catalogs, existing UI and approved stages; no redesign. Implement added features as additive gated work, with honest implemented/blocked statuses. DO NOT merge into main automatically.
