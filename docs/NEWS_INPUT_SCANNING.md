# News & Politics — Selectable Internet, TV Teletext and Radio Text Inputs

**Status — November 5, 2026: experimental source router and UI demonstration, NOT real news harvesting.** There is no deployed Pi service, authenticated API, connected TV tuner, radio SDR, verified publisher API or working Teletext decoder in this repository.

## Product decision: three independently selectable inputs

In News Center → Sources & Scan, give the owner:

- **[x] Internet** — verified authorized RSS/Atom, public news APIs, official political account APIs and permitted broadcaster links; **ON by default** when consent and connectivity exist.
- **[ ] TV Antenna** — DVB-T/T2/C **Teletext news pages**, channel/EPG/EIT metadata and available broadcast subtitles through the Hauppauge WinTV-soloHD 01589 once detected with a working driver. **OFF by default**; do not start or retune the tuner without explicit owner action.
- **[ ] Radio Antenna** — FM **RDS/RadioText**, DAB+ **DLS/Journaline** and optionally public APRS bulletins/weather data, **if carried and supported by a separate suitable SDR/receiver and antenna**. **OFF by default**. The USB DVB TV tuner **cannot substitute** for the separate radio receiver.

Each transport opens a per-source checklist. Selecting a transport is *not* automatically selecting every source. The owner can choose countries, broadcaster channels, specific Teletext/data stations, publisher domains and political accounts independently, then press **Scan selected sources**. Include **Unselect all** and per-source hide/block preferences in a later authenticated UI.

### What constitutes a source scan?

- **Internet:** A verified backend checks only selected allowed public/authorized feed endpoints, respecting platform API and rights restrictions. **No unverified URL, live API access or working RSS ingestion has been implemented.** Do not invent account names, live feed links or articles.
- **Teletext (TV):** Driver and DVB tuning must be verified; inspect PAT/PMT, data PIDs/Teletext descriptors and decode actually carried pages (e.g., ARD Text, ZDFtext, TRT TELEGUN **only where the tuned multiplex carries them**). Page 100 may be an index. Extract **news pages and original timestamp**, not arbitrary subtitles passed off as articles. DVB EPG can give programme descriptions, **not** guaranteed political news. Optional TV subtitles may be used as separate grounded text excerpts from real broadcasts with rights/attribution.
- **Radio text:** Inspect an actual supported FM/RDS receiver stream or DAB DLS/Journaline decoder output. RDS song titles and station identifiers are *metadata*, **not automatically news**. APRS messages/weather are user/ham-generated RF data, **not independently verified journalism**. Show a clear broadcast/source label and do not classify them as verified official alerts.
- **No antenna:** The applicable receiver input says **Hardware unavailable**, not "scan successful"; an unrelated purchased tuner is not evidence that radio hardware is ready.
- **No internet:** Internet input says **Offline**; TV/Radio can still be used where genuine RF reception and drivers are available.
- **Active TV recording:** Never retune or interrupt an existing user-authorized recording. Only a separately verified same-multiplex, no-retune decoder may share an existing DVB transport lock. Otherwise show **Recording protected — scan deferred**.
- **Region:** Germany Bundesland/municipality and Turkey province/district profiles are independent of UI language. Candidate country metadata are not RF signal evidence.
- **Storage:** News-derived text metadata should obey the **24-hour publication-age cache** and 30 MB design cap; no original programme recordings, user BBS messages or saved files are deleted by news refresh. This cache engine is **not yet implemented**.

## Code in this draft

- `tihulu_runtime/news_source_scanner.py`: read-only source selection, explicit scan gates and honest outcomes; accepts no raw shell command, tuner frequency or network URL. Actual backend adapters remain external; the catalog initially marks every candidate unverified.
- `data/news_sources_candidates.json`: internet source candidates; no invented RSS, social-media handles or working URLs.
- `data/radio_text_networks.json`: documented broadcaster/teletext and separate radio-data candidates; only `dvb_teletext`/`dvb_si_epg` become TV choices, only `dab_data`/`fm_rds`/`amateur_ax25_aprs` become Radio choices. Non-news metadata must be labelled accordingly.
- `prototype/news_inputs.html`: local browser interface demonstration with independent medium switches, per-source selection, and explicit Scan Now. It does not communicate with hardware or any remote news API.
- `tests/test_news_source_scanner.py`: ensures background scans, unselected sources, missing hardware, unsafe tuner retunes and unverified signal claims are blocked.

Run tests with `python3 -m unittest discover -s tests -v`.

## Integration backlog — before calling this a working News app

1. Add owner-authenticated persistent per-user selections and independent Hard/Background/Startup policies; do not let a website request start system tools without server approval.
2. Implement secure Internet RSS/Atom/API adapters using independently validated source URLs, API/robots/legal requirements, polling limits, regional permissions, source timestamp provenance and cross-source article deduplication.
3. Attach actual tested Tvheadend/DVB demux and libzvbi/Teletext parser (or equivalent), with tuner ownership and service leases for multi-client recordings. **No received page is presently verified**.
4. Attach suitable separate SDR/DAB/FM decoding for radio text, not the DVB television frontend. Do not transmit RF.
5. Add the rolling 24-hour text cache and per-source last-checked/signal freshness states, without deleting original user data.
6. Present typed article cards with source/medium/time/rights labels; feed claims and Teletext content to local translation/AI **only when explicitly requested**, with original text available and no fabricated conclusions.
7. Validate on actual Pi5/USB hardware and only then update README status from prototype to integrated.

**Licensing:** This project's original implementation is [AGPL-3.0-only](https://github.com/Tihulu/tihulu-survival-kit/blob/main/LICENSE); broadcasters, news articles, signal content, firmware and other upstream works keep their separate rights.
