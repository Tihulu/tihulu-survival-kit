# Regional channel setup, editable lineups, and TV/radio remote — Stage 8/9 experiment

**Snapshot:** 2026-11-05. **Branch:** `feature/on-demand-service-manager-2026-11-05`; **PR:** [public draft #1](https://github.com/Tihulu/tihulu-survival-kit/pull/1). Not a shipped or Pi-installed app.

## User flow

1. In first-run setup, choose **country → state/province → city**. Germany's 16 federal states and Turkey's 81 provinces come from `data/region_profiles.json`. The city selector supplies a small curated list and allows a custom city name; the latter cannot magically supply unsourced frequencies.
2. View the **published but not locally received** channel candidates for the selected city, then region, then country. For example, Köln: WDR DVB-T2 K26/514 MHz, WDR DAB+ 11D/222.064 MHz, national DAB+ 5C/178.352 MHz and WDR 2 FM/98.6 MHz (plus other curated local candidates). İzmir Merkez: TRT FM channel seeds, including TRT Radyo 1 at 94.7 MHz. Source URLs remain attached to frequency seeds. These lists **do not establish local coverage, successful demodulation, or decryptability**.
3. Select multiple checkboxes and save a named regional lineup. You may maintain multiple region profiles and switch among them; selection never triggers an RF scan. An unknown city initially has no city-local candidates, rather than a fabricated station list.
4. Insert your own label/mode/frequency entry, edit a saved entry (including ±500 kHz tuning offset), reorder, remove, and request tuning of an individual entry. Edits turn published candidates into clearly **user-entered unverified** data instead of attributing the modified frequency to an official source.
5. Select a TV or radio player screen and open the remote on a phone or second browser. Channel up/down follows the stored order. In production the paired owner, display session, tuner lock, receiver, playback backend and device acknowledgement are checked before reporting success. A tuner scanner must not interrupt an active recording.

## Bundled catalog, future opt-in downloads

- `data/region_channel_catalog.json` is a small on-device index referencing existing `data/channel_frequency_presets.json` IDs, rather than duplicating the frequency database. NRW has a handful of example cities, İzmir has a few city choices. A city with no local station references is explicitly left unpopulated.
- `tihulu_runtime/region_channel_manager.py`: country/region/city validation, source-backed candidate lookup, owner-scoped SQLite lineup storage, preset/multi-selection, manual entries, custom ordering and editing, explicit tune path via the shared `ChannelExplorer`.
- Packs for additional cities may eventually live under `data/channel_packs/*.json` in this public repository. **No additional pack is published or listed in the manifest yet.** Avoid fetching entire national city catalogs during setup.
- The backend implements an **opt-in** pack importer for trusted manifest entries with a URL pinned to a 40-character Git commit SHA on `raw.githubusercontent.com/Tihulu/tihulu-survival-kit/.../data/channel_packs/*.json`, 64-character SHA-256 hash, a strict 1 MiB response limit and no accepted redirects. Packs can add `frequencies` (published candidate records with HTTPS source URLs) and `city_candidates` references. Existing IDs cannot be overwritten, and remote frequency geography must match. It never runs in the background. The future authenticated updater must persist verified pack bytes into a managed cache and reverify them when loading; the current test-only importer modifies only process-local candidate lookup.
- Existing owner lineups, received channel database, original TV/radio recordings and personal files **never** expire under the News Center 24-hour cache policy.
- City list status is kept separate from live tuner measurement; when connected, measured discoveries belong to the existing `ChannelStore` and verified receiver backend.

Example future pack JSON (not a current authoritative channel assignment):

```json
{
  "schema_version": 1,
  "status": "published_candidates_not_received",
  "frequencies": [
    {
      "id": "tr_example_station",
      "country": "TR",
      "region": "Ankara",
      "kind": "fm",
      "frequency_hz": 99000000,
      "label": "Example candidate (documentation only)",
      "source": "https://example.org/official-source"
    }
  ],
  "city_candidates": [
    {
      "country": "TR",
      "region": "Ankara",
      "city": "Ankara",
      "preset_ids": ["tr_example_station"]
    }
  ]
}
```

The example is **not** real station data and must never be shipped as an actual frequency preset. Review authoritative transmitter/regulator sources before publishing city packs.

## Remote and network addressing

- `tihulu_runtime/remote_control.py` is a trusted **in-process command policy**, not a network server. Register targets through a trusted backend, require owner/paired-owner authentication, enforce a strict command allowlist, and require real tuner and playback acknowledgements for channel-selection success. Translator/AI requests return `integration_missing` until a source-grounded shared service pipeline exists.
- `prototype/region_channel_setup.html`: interactive browser preview with locally saved profiles. **LocalStorage on one browser origin is not shared owner/phone storage**; this does not replace the SQLite backend.
- `prototype/remote_control.html` and `prototype/remote_display.html` can demonstrate event delivery via `BroadcastChannel` only between **same-origin pages in the same browser context**. This will not deliver remote commands from a separate phone or Pi over LAN; no actual TV stream is played.
- Desired desktop URL **`http://tihulu.local`** may work if the Pi advertises mDNS and the desktop supports it. Desired phone URL **`http://tihulu.lan`** requires Tihulu hotspot/local DNS to resolve that name; the `.lan` address is not automatically provided by mDNS. A deployed hotspot could also expose a documented local IP fallback such as `http://10.10.10.10`. **None of these endpoints is currently deployed or verified.**
- Production remote design: single authenticated Pi HTTPS backend, owner-paired screen sessions, short-lived pairing codes, session revocation, CSRF and origin checks, WebSocket or authorized polling delivery with ACK, two-way display state, TLS trust handling, and cross-client tuner lease serialization. Do not serve unauthenticated TV/volume/recording controls over the hotspot. TV playback uses an independently implemented broadcaster/decoder/player pipeline; the protocol itself provides no video.
- At least one Pi or connected PC display must be online. **“Open TV” means launch/play Tihulu TV Center on that display**, not physically power on an arbitrary TV over RF. Hardware HDMI-CEC control is a separate feature and needs actual compatible equipment.

## AI, Translator and per-channel details

- A remote can choose source language/translation target, select received Teletext or DVB subtitle text, request a translation, summary or question through the shared on-demand `translator` / `local_ai` service leases. Never fabricate subtitled speech, EPG, channel metadata or a translation from the frequency alone. Preserve original source, broadcaster, timestamps and rights.
- A manual frequency or offset changes only after an explicit owner action and receiver capability check; `Receiver.recording_active` must prevent destructive tuning even if the requested frequency equals the current mux unless a proven non-retuning shared demux reader exists.
- The purchased Hauppauge WinTV-soloHD 01589 supports DVB-T/T2/C reception, not FM/DAB+, satellite or general SDR. All FM/DAB candidates require separate appropriate radio equipment.

## Verification and next gates

Run `python3 -m unittest discover -s tests -v`, and inspect the exact branch-head Actions checks. Mock tests cover candidate geography, 16/81 administrative regions, multiple selections, custom entries, safe editing/reordering, owner isolation, opt-in pinned pack checking, command allowlisting, recording preservation and missing backend states. This does **not** constitute Pi5 tuner or cross-phone/browser verification.

**Still missing:** installed receiver discovery, a production setup wizard with account-aware state sync, verified city-wide frequency imports, verified optional pack persistence, authenticated LAN API and pairing, streaming renderer and WebSocket relay, real video/radio playback, DVB Teletext/subtitle/EPG decoders, shared Translator/LLM inference, end-to-end mobile tests, RAM/power measurements and regional live broadcast validation.

Keep draft PR #1 separate from `main`. Do not claim hardware validation or release sign-off.


## New local gateway continuation — November 5, 2026

The next experimental increment has a **real optional stdlib HTTP(S) API** for shared SQLite channel profiles and a limited server-side browser-command relay, rather than relying solely on same-origin `BroadcastChannel` events. See [LAN Remote Gateway Experiment](LAN_REMOTE_GATEWAY_EXPERIMENT.md). The server is opt-in; it listens on loopback by default and refuses non-loopback binds without explicit TLS certificate and key. A phone and computer can both use its browser UI when the Pi HTTPS host is reachable and properly trusted, but this has **not** been physically cross-device tested. Command status `display_received` means that a browser saw the request; it never claims real DVB tuning, playback, radio decoding, recorded media safety, subtitles or local AI. Device-side player and RF integration remain mandatory.

With example port 8443, the URL would be `https://tihulu.lan:8443/` (not automatically `https://tihulu.lan/` without a trusted reverse proxy on the standard HTTPS port). Neither `.lan` local DNS nor `.local` mDNS is provisioned by this server. The owner token and certificate keys are never embedded in the repository, UI source, browser URL or channel list.
