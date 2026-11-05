# Signal Explorer — Manual Tune, Preset Lists, Frequency Sweeps and Discovered Services

**November 5, 2026 — experimental bounded scan-plan and discovered-channel logic; no live RF signal received or decoder connected.** This standalone module is shared with **TV Center**, **Radio Center**, and **News Center**, but its main browser-accessible app does not depend on News.

## User-facing app: Signal Explorer

- **Sources** — select attached DVB-T/T2/C USB TV tuner or separate SDR/radio receiver. Display Connected / Driver / Antenna / Currently Tuned Multiplex, rather than assuming that a purchased tuner is plugged in.
- **Presets** — imported country/region/channel manifests with published date/official source. First small verified-reference Germany/NRW list in `data/signal_frequency_presets.json`; other regions need sourced up-to-date frequency tables and genuine scans. User may add, edit and export their own **presets** separately from observed results.
- **Manual Tune** — user enters exact frequency, Hz/kHz/MHz, modulation/mode, bandwidth, optional tuning offset/AFC/ppm for SDR (not guaranteed for DVB), presses Tune and sees measured lock/signal only once real adapter is connected.
- **Quick Scan / Regional Scan** — scans country presets. **Frequency Sweep** — bounded sequential configurable start/stop/step in supported band; optional randomized scan *order* only, not mystical out-of-band discovery. Physical hardware cannot cover arbitrary modes or unlimited frequencies.
- **Discovered Services** — sort/filter by band, frequency, broadcaster, actual lock, service type (TV, radio, Teletext, captions, EPG, DAB text, RDS or decoded public packet). Favorite, label/rename locally, export channel list, rescan and **Tune** to a recorded frequency. Distinguish `reference preset`, `signal detected`, `service decoded`, and `no usable reception`.
- **Teletext and Data Browser** — pages 100–899, subpages, search, links/interactive selection if locally represented, program information and EPG; a local decoder/browser can render actually broadcast pages. Real Teletext is **one-way**: a button on a viewer cannot transmit back to a broadcaster.
- **Community Web Browser** — browse legitimate online Teletext-art pages, BBS websites/forums and their interactive web controls when WAN is present. A genuine local Wi-Fi BBS can run on the Pi after separate backend/auth implementation. Do not falsely imply public RF chat send/receive from the DVB antenna. External web interactions require normal website logins/permissions, safe URL handling and normal browser standards.
- **Radio digital text / amateur listening** — FM RDS, DAB+/Journaline, permitted amateur radio voice/bulletin/AX.25/packet reception with an SDR and suitable antenna/driver and decoder. A carrier alone is `unknown signal`, not automatically an amateur broadcast or chat forum. Private/encrypted/inadvertently overheard communications must not be indexed or redistributed. Any RF sending needs separate authorized TX-capable radio and legal compliance.
- **Translator + Local AI** — selected decoded public texts or permitted web pages share Stage4 Translator and Local AI workers with News Center, Browser, PDF and Radio. On-demand translation/summary/Q&A across multiple original sources; no automated chat claims, no background model loading.
- **Tuner safety** — one Hauppauge soloHD frontend cannot retune to another mux while recording. Allow read-only same-mux demux only after real confirmation. Missing radio SDR cannot be replaced by TV tuner. Connected hardware/driver mode check precedes scan.
- **Power and privacy** — no automatic continuous scan, bounded scan steps, owner explicit request, preserve ongoing radio/TV recordings, do not transmit, retain only user-selected public source metadata; set optional background OFF by default.

## Preloaded example reference frequencies

| Mode | Frequency | Service/region | Published evidence |
|---|---:|---|---|
| DVB-T2 UHF 26 | **514 MHz** | WDR Köln Colonius / NRW regional service | [WDR DVB-T2 frequency table](https://www1.wdr.de/unternehmen/der-wdr/empfang-technik/dvb-tzwei-hd-128.html) |
| DAB+ 11D | **222.064 MHz** | WDR NRW | [WDR DAB+ frequency table](https://www1.wdr.de/unternehmen/der-wdr/empfang-technik/dab-plus-128.html) |
| DAB+ 9A | **202.928 MHz** | WDR Regional | [WDR DAB+ frequency table](https://www1.wdr.de/unternehmen/der-wdr/empfang-technik/dab-plus-128.html) |
| DAB+ 5C | **178.352 MHz** | Deutschlandradio national ensemble | [Deutschlandfunk frequency search](https://www.deutschlandfunk.de/frequenzsuche) |
| FM | **91.3 MHz** | Deutschlandfunk Köln | [Deutschlandfunk Cologne listing](https://www.deutschlandfunk.de/frequenzsuche) |

DAB+ station ensembles are not individually decoded without a real DAB receiver. DVB terrestrial reception varies by antenna, region and RF conditions. This subset is **not** the entire national channel list, and frequencies can be updated; full Germany/Turkey preset imports must be source verified rather than fabricated.

## Implementation notes

- `tihulu_runtime/signal_explorer.py`: pure Python explicit bounded range/preset scan state machine, observed service catalog, favorites and tune gating. External authenticated USB DVB and SDR adapters remain **unimplemented**, as do actual device probing, scan progress, disk persistence and arbitrary frequency protocols.
- `tests/test_signal_explorer.py`: mock receiver tests for known frequencies, no unsolicited scans, recording-safety, mode verification, unknown carriers, no transmit and discovery/tune.
- `data/signal_frequency_presets.json`: small, sourced NRW/DAB/FM starter manifest, no claimed local reception.
- Future: validated Linux DVB `/dev/dvb/adapter*` frontend enumeration, daps/v4l2 scan/tune and actual PID/TS parsing for TV; separate rtl-sdr or compatible hardware, demodulators for analog/DAB text, a frequency manager shared by TV/Radio/Signal Explorer; a user-visible device list and mode-specific bandwidth/ppm/AFC with real measured RSSI/lock.
- A `News` link may import a decoded item only with source/provenance and owner selection; **News Center is not the only way to browse data**.

**License:** Original Tihulu source AGPL-3.0-only; broadcaster data, public web pages, artwork, recordings and third-party decoders retain their respective rights.
