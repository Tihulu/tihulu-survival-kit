# Channel & Signal Explorer — Television, Radio, Teletext and Text Networks

**Development snapshot:** November 5, 2026. Public experimental Stage 4 [draft PR #1](https://github.com/Tihulu/tihulu-survival-kit/pull/1). **No Raspberry Pi image, real connected tuner scan, RF hardware test, working ASR/LLM installation or full Text Browser deployment.** Technical docs and candidate frequencies are not observed reception.

## Shared product design

A separate **Channel & Signal Explorer** is available from Tihulu Home outside News Center. TV Center, Radio Center, News Center and the Text/Data Browser share:

- **Frequency library:** Region/country and delivery standards, source-backed **published presets** distinctly labelled `published_not_received`. 16 entries initially from official **WDR, Deutschlandfunk Kultur, TRT** and the documented **LK0NOD packet-radio node**; add official/published sources through periodically reviewed versioned packs.
- **Manual frequency:** user-entered frequency, standard, bandwidth where relevant, step and optional **fine-tune offset** (currently ±500 kHz maximum in experimental validation, subject to actual frontend capabilities). Changing the tuner while another user is recording requires safe scheduling or explicit takeover; a setting is not an RF measurement.
- **Discover/scan:** select single presets, manual frequency, or a bounded **band sweep**. Example UHF television channel grid 21–48 uses 8 MHz centers, requiring a DVB-T2 frontend. FM 87.5–108 MHz and amateur public 144–146 / 430–440 MHz receive-only candidate sweeps require a **different supported radio SDR**. A band allocation is not a list of active amateur stations. Up to **256** user-selected attempts in one request (recommend 128/page), not unlimited permanent sweeping.
- **Signal classification:** backend may report no signal, RF energy only, confirmed DVB lock, decoded programme services. Never turn an unidentified spectrum peak into a fabricated station name or publicly retransmit private communications.
- **Results list:** annotate medium, country/region, frequency/channel, decoded service ID, source type (TV, audio-only DVB radio, text/data), original/encrypted status where known, actual signal quality if the backend provides it, access restrictions, last-measured scan provenance. Sorting decoded > locked > mere energy; optionally by measured quality. No invented SNR/dBm or service logos.
- **Shared favorites:** authenticated owner-only SQLite channel list shared with **TV**, **Radio**, **Text Data** and News (when source permitted). Presets and manually entered channels are **candidate-only** until a real scan obtains a service; user labels stay visible with a warning. Original recordings and saved channels are **not** subject to News Center 24h cache expiry. DVB audio-only services should appear in Radio even though received through the TV tuner.

## Actual device categories

### Hauppauge WinTV-soloHD EU 01589 (reported purchased)

- **Single DVB-T/T2/C tuner; receive-only**, not general SDR/analogue FM/DAB, not DVB-S satellite receiver or RF transmitter. It may receive audio-only DVB services from a tuned multiplex, and exposes DVB Teletext/EPG/subtitles *only where carried*.
- Experimental `tihulu_runtime/linux_dvb_backend.py` optionally uses Linux `dvbv5-scan` **once per explicitly selected DVB-T/T2 physical frequency**, with a generated allowlisted DVBv5 initial file. Uses `-F` to prevent unrequested NIT expansion, restricts binary, adapter index and runtime, and parses only services reported for the selected frequency. It requires an existing Linux DVB frontend `/dev/dvb/adapterN/frontendM` and the distribution's `dvb-tools`. It has **not been run with the purchased tuner**; do not claim detected DVB or Teletext by parsing programme names. DVB-C manual tuning remains **unsupported by this experimental adapter** until symbol rate and modulation handling are verified.
- **Protected recordings:** physical tuner must not be retuned to a different multiplex while an actual recording/TV view owns it. Same frequency sharing only after decoder/demux verification. An operating system-level receiver lock broker is not complete; trusted `Receiver` context in experimental tests must ultimately come from actual system/Task Center evidence.

### Radio SDR (not confirmed purchased)

- FM RDS, DAB+ DLS/Journaline, analogue AM, shortwave and amateur VHF/UHF/NFM/SSB reception require suitable actual SDR/HF front-end, antenna, band support and compatible demodulation software. **These backends are not yet installed or integrated.**
- Low frequency (e.g. public CB packet node **26.925/27.235 MHz**, known public ham HF allocations) may require a specific HF-capable receiver; an ordinary TV antenna does not make it work.
- Legal RX/TX obligations, privacy and access authorizations depend on country and service. Do not transmit, record protected private communications, or provide an unrestricted rebroadcasting proxy. RF transmit requires separate owner consent, compatible equipment and lawful authorization.
- A sweep cannot magically decode arbitrary modulation. **Energy detected ≠ service decoded**; if an unknown service is found, it stays **Unclassified** until a compatible demodulator identifies it.

## Verified frequency starter examples (not measured locally)

| Region | Service / ensemble | Published frequency | Receiver | Primary reference |
|---|---|---|---|---|
| Germany, Cologne/Bonn | WDR DVB-T2 K26 | 514 MHz | WinTV DVB tuner | [WDR DVB-T2](https://www1.wdr.de/unternehmen/der-wdr/empfang-technik/dvb-tzwei-hd-128.html) |
| Germany, Düsseldorf | WDR DVB-T2 K46 | 674 MHz | WinTV DVB tuner | WDR DVB-T2 |
| Germany, NRW | WDR DAB+ 11D / 9A | 222.064 / 202.928 MHz | Separate DAB receiver | [WDR DAB+](https://www1.wdr.de/unternehmen/der-wdr/empfang-technik/dab-plus-128.html) |
| Germany | National DAB+ 5C | 178.352 MHz | Separate DAB receiver | [Deutschlandfunk Kultur frequency search](https://www.deutschlandfunkkultur.de/frequenzsuche) |
| Cologne | WDR 2 FM | 98.6 MHz | Separate FM receiver | [WDR FM](https://www1.wdr.de/unternehmen/der-wdr/empfang-technik/ukw-senderstandorte-100.amp) |
| Turkey, Izmir Merkez | TRT Radyo 1 / TRT FM | 94.7 / 91.2 MHz | Separate FM receiver | [TRT Izmir](https://radyo.trt.net.tr/frekanslar/izmir-merkez) |
| Germany, LK0NOD | CB packet BBS CH24/CH77 | 27.235 / 26.925 MHz | HF-capable receiver to listen; separate authorized transmitter to participate | [LK0NOD](https://www.lk0nod.de/packet-radio/index.html) |

No invented terrestrial TRT DVB-T2 frequency is included for Izmir. Country, locality and delivery standard must match the real transmitter, receiver and cable/antenna input. A Germany DVB-T2 receiver may find private encrypted programmes; do not claim decryptability.

## Text/Data Browser and actual interaction

- **DVB Teletext:** Page 100–899, subpage, broadcaster/region and actual frequency selection, cached received page list, related page links, next/previous, source language, optional text search, copy/export. A decoder must return real page content; **broadcast teletext cannot accept chat messages back**.
- **Internet Teletext-style sites and blogs:** Open actual HTTPS pages in a full browser, following site navigation, forms and links under the user's own session. Candidate links include [Teletext Art](https://teletextart.co.uk/teletext-links), [LK0NOD forum](https://www.lk0nod.de/forum/) and [LK0NOD browser terminal](https://www.lk0nod.de/telnet.html). **Do not automatically store credentials**, silently proxy private accounts or promise site iframes that may be blocked by CSP/X-Frame-Options. An external site's own posting rules and internet access apply.
- **Packet-radio text BBS/chat:** A legitimate two-way RF session requires a separate compatible CB/ham transceiver + proper authorization. A receive-only SDR can listen to decodable public data but cannot send. The **Tihulu Local BBS** remains an unimplemented LAN-only forum.
- **Translator and Local AI:** Selected real Teletext page content or user-permitted website text may be converted into attributed `NewsText` using `TextDataNavigator.to_news_text()`, then passed to the **same optional shared `translator` / `local_ai` services** as News, Browser, PDF and Radio. For web pages, a browser text extraction and owner selection/rights gate must be implemented. The code does **not** currently fetch external pages, interpret HTML, translate or invoke actual LLMs. A model cannot automatically control websites or post messages on behalf of a user.

## Source files in experimental PR

- `data/channel_frequency_presets.json`: sourced frequency seeds, band scan plans, no received station claims.
- `tihulu_runtime/channel_explorer.py`: bounded scanning, fine tuning, actual receiver-capability validation, guarded active recording, typed measured results, per-user SQLite saved channels/favorites, manual unverified entries.
- `tihulu_runtime/linux_dvb_backend.py`: experimental explicit DVB-T/T2 scan adapter; no actual device or SDR integration.
- `tihulu_runtime/channel_app_registry.py`: common TV/Radio/Text channel library view and safe tune interface.
- `data/text_data_portals.json` and `tihulu_runtime/text_data_browser.py`: Teletext page navigation validation, browser portal directory and source-preserving AI/Translator conversion.
- `prototype/channel_explorer.html`, `prototype/tv_center.html`, `prototype/radio_center.html`: **standalone browser demonstrations**, including real outgoing links to Internet sites but no physical scanning or Pi runtime.
- Tests: `test_channel_explorer.py`, `test_linux_dvb_backend.py`, `test_channel_app_registry.py`, `test_text_data_browser.py`; run `python3 -m unittest discover -s tests -v`.

## Production completion gates

1. On the actual Pi5 8GB, verify `lsusb`, `/dev/dvb/adapter*`, kernel module/firmware, frontend probes, and real `dvbv5-scan` results against at least one physically received DVB-T2 multiplex. Avoid conflating a TV device's USB enumeration with actual service lock.
2. Implement real multi-user frontend leases/reservations and safe recording journal; no unintended retune or recording corruption. Test TV-only, DVB radio, audio+Teletext on same physical mux, manual tuning with fine offset when supported, and scanning with multiple client tabs.
3. Implement FM/DAB SDR backends, actual receiver capability discovery, narrowband amateur/public decoding, measured dB/quality, tuner calibration and hardware frequency correction. No RF transmission by default.
4. Integrate a proper Teletext decoder (DVB VBI/PID and ETSI EN 300 472) and page caching; ensure source titles are real, timestamped and channel-specific. Add HbbTV separately where legal and supported.
5. Browser text-site interaction must obey user login, CORS/CSP, secure HTTPS, credentials and source/rights boundaries. Restore browser state without background RAM leaks; no claims of automatic remote forum posting.
6. Use a single owner-specific channel library and measured scan results, Favorites/Export, name/frequency sorting, unknown-signal labels, source attribution and region language independence.
7. Connect shared Translator/Local AI service leases only on explicit action, with missing model/language states, source-grounded outputs and archive retention. Do not apply News 24h cache deletion to saved channel lists or personal recordings.
8. Report measured Pi5 RAM/CPU/thermals/duty cycle, passive listening privacy, source content rights and regional antenna limitations. Do not merge this draft as a released TV/Radio app without these checks.

**Project license:** Original Tihulu work under [AGPL-3.0-only](https://github.com/Tihulu/tihulu-survival-kit/blob/main/LICENSE); broadcaster programme material, websites, data and embedded third-party software have their own terms.
