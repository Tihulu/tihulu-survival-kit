# SDR Radio Integration — Stage 8 experimental foundation (2026-11-05)

**Status:** first implementation slice on a separate feature branch; not deployed.
This complements the existing Stage 4 ServiceManager, SharedChannelWorkspace,
RegionChannelManager and protected media architecture. It is **not** a new
project, a replacement for DVB-T2, or an approved full Stage 8 release.

## Hardware evidence versus planned capability

- **Owner-verified external workstation:** Pop!_OS 24.04, NESDR SMArt v5
  RTL2832U USB ID 0bda:2838; rtl_test 2.048 MSPS, audible FM through Gqrx,
  successful DAB+ and station metadata/audio through welle.io Expert Mode.
- **Raspberry Pi 5:** SDR driver/index/USB current, actual RF reception, Pi
  8GB CPU/RAM/thermal, rtl_fm, welle-cli and simultaneous client performance
  **not tested**. The Linux sysfs ID is generic RTL2832U, so model/serial and
  physical rtl_fm index must be confirmed by an authorized owner.
- **Independent TV-001:** Hauppauge WinTV-soloHD 01589 is a separate Linux DVB
  frontend. It must not be probed with rtl_fm or assumed compatible with
  welle-cli. Its ARM64/HEVC/antenna functionality remains unverified.
- No transmit capability is implemented or assumed.

## Integration map (existing code preserved)

```text
Tihulu Home / Region Setup / Hardware Manager / Task Center
   |               |                  |
   |  RegionChannelManager + shared ChannelStore (per-owner SQLite)
   |               |
   +-- Radio Center Basic / Expert -- ChannelExplorer / future RF telemetry
   |                                     |
   |                                Trusted auth + device broker
   |                                     |
   |                 +-------------------+----------------------+
   |                 |                                          |
   |           SDR-001 (RTL-SDR)                       TV-001 (DVB-T2)
   |                 |                                          |
   |         FM: rtl_fm [first adapter]               LinuxDvbV5Backend
   |         DAB+: welle-cli [pending]                TVHeadend [future]
   |         RDS/IQ/ADS-B [pending]                   EPG/Teletext [future]
   |                 |
   |      shared decoded stream + owner-controlled session
   |                 |
   +-- Protected recording master (future persistent NVMe journal)
   +-- Subtitle Studio: VAD/ASR -> Translator -> optional AI (future)
   +-- Emergency: RF is supporting evidence, NOT verified official alert
   +-- Stage 4 ServiceManager -> no implicit background scanner
```

## First implemented slice

`tihulu_runtime/sdr_radio.py` provides:

1. **Non-invasive USB inventory:** read-only sysfs enumeration of RTL2832U
   0bda:2838 and *presence* of `rtl_fm`/`welle-cli`; never opens USB,
   self-selects a device revision, installs packages or scans. Used by future
   Setup Wizard with `setup_inventory()`. For local inspection:
   `python3 -m tihulu_runtime.sdr_radio`.
2. **Explicit capability bridge:** `receiver_candidate()` creates the existing
   `channel_explorer.Receiver(kind="radio_sdr")` only from capabilities
   the trusted backend has independently verified. The default lower bound
   of 25 MHz does not silently assert working direct-sampling HF. Model brand
   cannot be established from the generic VID/PID.
3. **Single-center tuner reservation:** `SdrTunerBroker` rejects a second
   capture even at the same frequency, unless a verified shared decoded stream
   explicitly lets a listener join *without retuning*. Recording holds cannot
   be released without an explicit safe-stop acknowledgement; listeners cannot
   silently be detached by an unrelated owner. Separate physical receiver IDs
   have independent sessions.
4. **Actual optional FM process adapter:** `RtlFmStream` launches allowlisted
   `rtl_fm` in shell-free mode only following explicit service-layer use,
   outputs raw mono **32 kHz S16 PCM** to a trusted consumer, and tears down
   the process and reservation on stop/failure. Not a stereo/RDS decoder, not
   a network audio player, not a tuner-service daemon, and **not field-tested
   with this hardware**. A running process or any PCM is not proof of an
   identified broadcast station. Never expose the raw process object in a
   browser/LAN API.
5. **Mock-only tests** cover USB identification, capability boundaries,
   physical tuner exclusivity, recording protection, safe command parameters
   and process lifecycle. No driver or spectrum is spoofed.

### Manual workstation/authorised Pi bench order (not yet performed)

- Confirm physical tuner model and map its RTL library **device index**.
- Check `python3 -m tihulu_runtime.sdr_radio` inventory fields without
  opening the tuner.
- Install approved `rtl_fm` on the device and stop Gqrx/welle.io before
  allocating the *same* USB SDR. Device-busy errors remain possible because
  other programs do not coordinate with Tihulu's in-process broker.
- Connect to trusted audio consumer for streamed S16 PCM, and log sample
  length/rate + actual audible reception. Test 98.6 MHz only as a published
  Köln/NRW candidate, not a guaranteed channel.
- Next validate welle-cli DAB+ directly on the Pi via an **isolated localhost
  service**, before reverse-proxy auth or exposing metadata/audio to devices.
- Measure Pi power (idle/FM/DAB/Expert/recording), RSS/CPU and thermal load.
  Test unplug/device-busy/restart/recording protection separately.

## Backend selection

| Backend | Initial role | Current adapter state | Explicit limitation |
|---|---|---|---|
| `rtl_fm` (rtl-sdr) | lightweight FM PCM | process adapter implemented, untested with RF | mono PCM, no RDS/technical FFT |
| `welle-cli` (welle.io) | DAB/DAB+ and service data | read-only loopback telemetry reader + executable detection; no decoder supervisor | authenticated proxy, Pi CPU proof remain pending |
| `welle.io` GUI | reference and proven workstation test | not embedded | Flatpak/GUI != backend web service |
| `Gqrx` | proven workstation FM and spectrum reference | not embedded | heavyweight GUI, no shared Pi tuner control |
| `SoapySDR` / `OpenWebRX+` | future wideband/IQ and Expert mode | research only | CPU/network exposure/security and licensing |
| `readsb`/ADS-B | future aircraft receive-only mode | not integrated | 1090 MHz and antenna; takes exclusive tuner |
| `LinuxDvbV5Backend` | **TV-001 only**, preserved | existing experimental DVB adapter | not an RTL-SDR FM/DAB backend |

**DAB+ next adapter gate:** Upstream welle-cli supports RTL-SDR, one channel
at a time, `-C 1 -w PORT`, `/mux.json`, `/spectrum`,
`/constellation`, `/impulseresponse`, `/fic`, and per-service audio.
The webserver must be supervised, bound/isolated on loopback and
authenticated/authorised at Tihulu's boundary **before integration**.
Don't expose welle-cli's direct `/channel` retuning endpoint to guests.
A complete DAB multiplex can host several services within the same tuner
center; simultaneous decoding count depends on host and verified backend,
not independent RF tune freedom.

Upstream references:
- https://github.com/AlbrechtL/welle.io
- https://github.com/AlbrechtL/welle.io/wiki/Using-the-welle-cli-Web-Interface
- https://manpages.debian.org/testing/rtl-sdr/rtl_fm.1.en.html
- https://support.nooelec.com/hc/en-us/articles/360005805834-NESDR-Series

## Existing data and regional setup remain authoritative

- `data/region_profiles.json`: German states and Turkish provinces.
- `data/region_channel_catalog.json`: curated city/channel candidates.
- `data/channel_frequency_presets.json`: published presets and DAB channel
  group. **Published != received != decoded.** User saved channels continue
  in owner-scoped SQLite independent of news cache TTL.
- Optional large data packs require explicit owner consent, source and pinned
  hash verification as already documented in
  `docs/REGION_CHANNEL_LINEUPS_AND_REMOTE.md`.
- Scans remain explicit and bounded; no default background RDS or DAB scan.
  No region can turn on unauthorized radio listening.

## UI contracts and existing micro-window IDs

- **MW-07 / MW-44:** Setup Wizard device detected vs compatible driver vs
  physical bench verified, USB index/manual identification, upgrade flow.
- **MW-29:** SDR-001 antenna -> FM (RDS pending) / DAB multiplex / receive-only
  data; Basic station card and Expert diagnostics.
- **MW-27:** TV-001 independent DVB frontend -> TV/EPG/Text/recording; do not
  route through the RTL-SDR FM engine.
- **MW-43:** built-in region candidates, optional signed/pinned large
  catalogue, offline channel favorites and manual entries.
- **MW-09 / MW-10 / MW-48:** Stage 4 Hard/Background/Startup service controls,
  explicit temporary grants, recorder/task persistence and safe stop.
- **MW-49:** existing Base/Balanced/Advanced local AI mode picker. Radio
  reception does NOT require AI or a remote GPU.
- `prototype/radio_center.html` is a clearly labeled **static interaction
  preview**; toggles do not start tuners and sample metrics are not telemetry.
- Private UI ownership: Plan82, Plan83, Stage8 Plan71/72, Plan78/79 and
  traceability Plan56. Do not copy private screenshots/assets into public
  source without approval.

## Next implementation / blocking gates

1. Attach USB inventory result to an authenticated Setup/Hardware Manager
   and record model confirmation without leaking USB serials.
2. Add actual OS-level receiver/device locks, map device index to USB path,
   acquire/release Stage4 service lease, and guard ChannelExplorer scans while
   stream or protected recording is live. In-process locks alone are inadequate.
3. Build a sandboxed localhost `welle-cli` adapter, structured ensemble
   metadata and bounded metrics; only backend-verified values appear live.
4. Implement RDS with a separately verified decoder; IQ/FFT waterfall rate
   and DAB FIC/CRC/TII/impulse response must be genuine backend measurements.
5. Implement safe media fanout, durable NVMe original recording journal,
   power-loss recovery, retention rules and authorised multi-client controls.
6. Validate Pi 5 ARM64 SDR/FM/DAB, separate DVB-T2 receiver, USB power,
   CPU/RAM, antenna and RF interference before changing Stage8 release status.
7. Validate all selectable locale variants and accessibility on phones and PC.

**Security:** no public rtl_tcp, unrestricted welle-cli, unauthenticated
tuner commands, RF transmissions, guaranteed emergency alerts, or default
continuous scanning. Only a trusted internal caller may approve changing a
capture ownership or sharing policy. All native upstream licenses are reviewed
before redistribution; no binaries vendored in this slice.

## Phase 1b — local DAB telemetry reader (experimental; no live Pi reception)

`tihulu_runtime/welle_local.py` provides `WelleLocalReader`, a conservative
**read-only connector for an already-running welle-cli HTTP server**.
It never launches welle-cli, changes DAB channels, scans RF, requests the
continuous `/fic` endpoint, fetches `/mp3/<SID>` streams, or opens a
LAN listener. The HTTP destination is fixed at `127.0.0.1` with a
nonprivileged configurable port; only five allowlisted GET routes are
usable (`/channel`, `/mux.json`, `/spectrum`,
`/constellation`, `/impulseresponse`).

The reader enforces short timeouts, 256 KiB response caps, small finite
float32 spectrum series and strict decoder metadata JSON. It marks data
`decoder_reported_not_independently_rf_verified`, because being able to
read a decoder process does not itself prove the actual broadcast or
safety/official alert validity. No requested real antenna/tuner evidence
has been fabricated by these tests.

`tests/test_welle_local.py` uses synthetic HTTP fakes to check read
behaviour, localhost-only access, rejected endpoints, oversized/malformed
payloads, and opt-in Expert snapshots. To activate this in the actual
Survival Kit product, provide an OS-isolated decoder, a trusted service
lease and an owner-authenticated app gateway; **do not expose welle-cli
directly to a shared or untrusted LAN**. Pi ARM64 performance, welle-cli
API-version behaviour and real metrics remain unvalidated.

## Recording-safe worker stop and isolated CI — Phase 1c

A Phase 1c regression revealed a sequencing hazard: stopping the FM process
before the tuner broker denies release could interrupt protected original
audio despite the broker's recording flag. `RtlFmStream.stop()` now uses
`SdrTunerBroker.release_after()`: ownership, protected recording and active
listener gates are checked under the broker mutex **before** the worker is
terminated, and remain held throughout worker shutdown. A trusted caller
may pass `recording_stop_confirmed=True` only after a durable recorder
flush/ACK; that actual journal/ACK mechanism is **not implemented yet**.
The feature's safety check is in-process, not a cross-process USB device lock.

Additional synthetic tests cover both protected recording and attached
listener denial. `.github/workflows/sdr-radio-tests.yml` separately runs
SDR + local DAB tests under Python 3.11/3.12 and validates the Radio Center
inline JavaScript with Node. This explicit isolated matrix is **not a
replacement for whole-repository Stage4/5 checks** and does not claim
physical Pi/Nooelec RF verification. At Phase1b the global CI still had
one unrelated `ai_smoke_admission` failure; coordinate on the owning
AI branch before release.
