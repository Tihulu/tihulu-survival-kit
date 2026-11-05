# TV Teletext + Radio Data + Text Networks — Candidate v1

**5 Nov 2026 · documented architecture only; no RF scan, receive/transmit, streaming or active chat integration performed.**

## Already purchased
The Hauppauge **WinTV-soloHD model 01589** tuner (Amazon ASIN B0152XLPFS) is marked **purchased**, not confirmed delivered. Official DE box list includes portable DVB-T/T2 antenna. One DVB-T/T2/C tuner; no FM/DAB, no general wideband SDR, no LoRa transmit, no satellite dish reception. It can expose raw transport stream data with the proper Linux kernel firmware/driver and demux. Never assume TV signal or particular teletext track is currently available. Manufacturer: https://hauppauge.de/site/products/data_solohd.html

## TV data:
- **Classical Teletext**: DVB may carry EBU/System B teletext as DVB-TXT per ETSI EN 300 472. Search for teletext PIDs/stream descriptors in *tuned* broadcast, then decode into page 100-899 and subtitles. Try ARD Text (page 100; subtitle 150), ZDFtext (subtitle 777), Turkey TRT TELEGÜN (TRT still documents it). Do not infer that TRT teletext is terrestrially accessible in every Turkish region or available on an unrelated German DVB multiplex. ARD in 2025 replaced the old BR Text on BR Fernsehen with ARD Text.
- **Additional DVB data**: present/following EPG, full EIT programme schedule, DVB subtitles, language tracks, audio description where actually carried; expose signal parameters/frequency, stream metadata and per-station service IDs.
- **HbbTV**: AIT signalling and some broadcast-side application content may be carried, but working interactivity typically requires full HbbTV browser/DSM-CC and often internet return path. Do not label this "two-way Teletext from antenna". HbbTV embedding must respect content restrictions.
- **Channel changes**: a single tuner generally cannot decode unrelated RF multiplexes at the same moment. Receiving TV+teletext from the same locked multiplex may work if demux/driver allows multi-PID; never retune away from an active user-authorized recording. Queue/ask for takeover. A cache of watched teletext pages can be temporary, but **do not** delete original TV recordings or user exports as "news cache".
- **Region**: user chooses Germany -> Bundesland -> city/postcode or Turkey -> il -> city; local scan when owner starts it. Other countries later. Display "available from broadcaster" separately from "received on this tuner now".
- **Implementation test** (future): capture DVB TS with Tvheadend/tv tools, inspect stream descriptors and teletext descriptors, run compatible decoder (libzvbi/FFmpeg only after confirming feature and format), verify page bytes, correct language, page cycling, caption time, 24h temporary cache and RF mute/edge cases. Do NOT claim tested teletext today.

Sources: https://dvb.org/?standard=specification-for-conveying-itu-r-system-b-teletext-in-dvb-bitstreams ; https://hilfe.ard.de/artikel/untertitel-am-fernseher-aktivieren/ ; https://www.zdf.de/unternehmen/verantwortung/barrierefreiheit-faq-100.html ; https://www.trt.net.tr/corporate/teletext ; https://developer.hbbtv.org/guide/introduction/overview-about-hbbtv-architecture

## Radio data receive-only:
- **DAB+** digital radio: DLS/DLS+, Slideshow (SLS), Journaline, EPG, TPEG. Germany DAB+ FAQ documents these as optional broadcaster/receiver capabilities. Need separate supported SDR/DAB receiver, tuner is NOT enough.
- **FM RDS**: RadioText, PS/PTY and optional RT+ and traffic metadata; separate suitable FM SDR.
- **APRS/AX.25**: publicly observable amateur packet locations, weather, short messages, bulletins with compatible VHF SDR plus decoder and appropriate antenna. RF reception is not the same as legal ability to transmit. APRS.fi over Internet is an optional separate source, not an offline radio network.
- **HF facsimile / weather text**: optional compatible HF receiver and suitable antenna; current DWD schedules must be fetched before promising coverage. Do not silently tune and record continuously.

Sources: https://www.dabplus.de/faq/ ; https://aprs.fi/doc/guide/guide.html

## Two-way BBS, chat, old-school text communities — not teletext:
- **CB Packet Radio LK0NOD, LK0BOX / LKCHAT**: actual Germany project with BBS, chat, online access. Its own 2026 documentation lists CH24 27.235 MHz and CH77 26.925 MHz. Requires suitable CB transceiver/TNC and lawful use for RF; web access only needs Internet. Do not promise signal in Köln.
  - https://www.lk0nod.de/lk0nod-hilfe-online.html
- **DB0APK-7/9 amateur Packet Radio node+BBS (DK0PI)**: documented 438.150 MHz store-and-forward BBS (OpenBCM/LinBPQ); use suitable transceiver and authorization to transmit.
  - https://www.dk0pi.de/2025-05-06-packet-radio-mailbox.html
- **Meshtastic LoRa**: real two-way off-grid group/direct messages using separate EU-compliant LoRa transceiver. Rheinland community documents EU868 **ShortSlow**; Schleswig-Holstein Mesh SH documents EU868 **LongFast**. Presets/channels must match region; regulations and coverage checked. A TV DVB-T2 antenna is not a LoRa transceiver. Local message networks may exist even without the Internet.
  - https://www.meshrheinland.de/meshtastic/grundeinstellungen
  - https://mesh-sh.de/
  - https://meshtastic.org/docs/introduction/
- **Winlink** radio email: require a valid amateur-radio license or authorized public service credentials per operator. Messages over IP are an alternative access path but not equivalent to having RF connectivity. Add a guarded connector only after user supplies authorization and transceiver.
  - https://winlink.org/user
- **Teletext art / Teefax viewers**: can bookmark web teletext-format communities; they are NOT DVB broadcast chat. https://teletextart.co.uk/teletext-links

### Next UI (Radio & TV Data)
Channel > **Teletekst** > page no / previous-next / subpages / text language / copy-export; **DVB EPG**; **Radio Data** > RDS / DLS+ / Journaline / APRS; **Mesaj Ağları** > view/listen / (only if authorized: connect/send); **Community / Forum** > region-specific BBS, Meshtastic communities, bookmarked web links. All inputs use a shared **hardware capability registry** that visibly distinguishes "purchased", "connected", "decoder ready", "signal detected" and "available service". Never mark a USB TV tuner as a transmitter.

Idle/resource policy: TV/news/teletext background refresh OFF by default, no constant active tuner lock, no surprise transmission or Internet. User-triggered operations acquire Stage4 leases, and active recording is protected. News/social items still expire after 24h; original saved audio/TV recordings and user-created exports persist.
