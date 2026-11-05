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

## Phase 2: cooperating-process lock, Stage4 leases and guarded tuning (2026-11-05)

**Implemented (experimental):** tihulu_runtime/sdr_capture.py and tests/test_sdr_capture.py.
All code is an internal trusted library, not a deployed Pi daemon, authenticated
network API, physical SDR validation, recorded audio journal or browser stream.

### Service lifecycle and scan safety
- ManagedFmCapture: explicit foreground ServiceManager radio lease,
  Linux SdrCooperativeLock and RtlFmStream worker. A launch failure releases
  the cooperative lock and Stage4 service lease. Protected recording and
  attached listener checks occur BEFORE process termination. Only a
  confirmed successful worker stop releases the hardware/service leases.
- ManagedSdrScan: wraps the existing ChannelExplorer rather than
  replacing its region/channel database. Requires explicit user action,
  trusted probe backend and 1..256 radio points, then holds the same
  Stage4 service lease and per-receiver lock across the entire scan chunk.
  A cooperating FM stream blocks both manual tuning and DAB/other scans.
  The TV-001 DVB frontend remains an independent receiver.
- Hard OFF stays OFF by default when user has chosen it. Stage4 one-time
  owner-bound grants allow explicitly approved foreground tuning without
  silently enabling background or startup.
- Scans retain source provenance: energy_only is not a decoded station;
  published frequency candidates do not imply actual reception.

### Advisory device lock limitations
- SdrCooperativeLock uses a private 0700 lock directory, owner-only 0600
  no-follow lock files, nonblocking Linux flock, opaque hash-based names,
  and never unlinks active lock files. CI includes a separate Python
  subprocess holding the lock; the second process is blocked.
- This is an *advisory* lock among cooperating Tihulu processes using
  the same user, canonical receiver ID and lock directory. Gqrx, welle.io,
  rtl_test and other noncooperating programs can still open the USB
  device. Real USB-busy errors must be handled by the worker.
- USB VID/PID alone cannot associate a physical tuner with a librtlsdr
  index. A trusted USB identity and index mapper, host-level ownership
  across service accounts, crash recovery and actual Pi power
  measurements are still REQUIRED before claiming production safety.

### Exact CI
Dedicated Stage8 SDR GitHub Actions run
https://github.com/Tihulu/tihulu-survival-kit/actions/runs/42099621596
PASS in both Python 3.11 and Python 3.12: 45 synthetic tests per version
(15 SDR/FM, 20 capture/lock/scan, 10 DAB-local) and Basic/Expert
Radio Center JavaScript syntax. No real Pi or RF signal was exercised.
The global Stage4/5 suite is still failing on a separately owned
ai_smoke_admission unknown job counts test; never report overall CI PASS.

### Remaining
A trusted AppManager job adapter and durable server-owned task journal;
actual trusted USB device-index mapping and noncooperating-device handling;
sandboxed DAB decoder process, real RDS/spectrum/constellation and
web authentication; protected NVMe master recorder/flush ACK;
Pi 5 8GB CPU/RAM/USB power test and independent DVB-T2 coexistence.

## Phase 3: welle.io-style opt-in DAB automatic scanning

User request: Radio Center needs automatic DAB/DAB+ discovery comparable
to welle.io's channel scan, NOT just manual tuning or static frequency seeds.

Public implementation:
- tihulu_runtime/dab_auto_scan.py: DabAutoScanner builds a regional
  quick candidate scan (DE/NRW/Köln: national 5C, NRW 9A, WDR 11D),
  or a full Band III 5A..12D 32-block frequency scan. Optional 13A..13F
  provides 6 extra, user-selected blocks, without claiming any local
  broadcasting service at those frequencies. The catalog is the
  **existing** FrequencyLibrary, preserving provenance.
- data/channel_frequency_presets.json: only the 6 published upper-raster
  block centres were added to a new discrete group with explicit
  published-frequency-seed_NOT_received semantics. Nothing says Turkey
  or any city actually receives DAB. If a selected region lacks published
  quick candidates, choose Full Scan manually.
- ManagedSdrScan.scan(..., on_progress, should_cancel): holds one Stage4
  *foreground* lease and one cooperating-process SDR lock for the entire
  plan, even though probes are run one at a time. Each probe yields
  progress; cancellation checked *between* frequencies. Decoder backend
  is responsible for a bounded per-channel dwell / abort time and actual
  RF/service verification. No automatic background/startup scan.
- Actual discoveries are classified by ChannelExplorer as no_signal,
  energy_only, signal_locked, service_decoded, scan_failed. Only
  service_decoded with actual decoder service metadata becomes a station
  choice. The save_selected method persists only user-picked decoded
  service IDs to existing owner-scoped ChannelStore; existing favorites
  are not destroyed or silently overwritten. Browsing region presets
  never populates received channels.
- prototype/radio_center.html: accessible "Otomatik DAB+ Tarama" setup
  with quick/full/upper-band choices and dormant progress/status UI.
  **The real RF start and cancel buttons remain disabled in this UI
  preview** because authenticated worker bridge, bounded real welle-cli
  probe and hardware index mapping are not implemented yet. No fake
  percentages or fake received stations are shown.

Test cases: tests/test_dab_auto_scan.py checks plan sizes/known frequencies,
DE vs TR provenance, opt-in only, incremental progress, cancel before/during,
same physical SDR lock vs FM, Hard OFF grant, invalid DAB capability/plan
rejection, decoded-only user-selected DB save, and cleanup on UI callback
failure. Tests use a fake probe, not actual welle-cli or real RF.

Upstream welle.io project:
https://github.com/AlbrechtL/welle.io documents its GUI channel scan and
welle-cli single-multiplex webserver. The latter does **not** directly
provide a proven safe multi-block scan interface through our existing
read-only WelleLocalReader; the future trusted process supervisor must
handle each band block and decoder lifecycle, never publicly expose a
welle-cli server or abuse read-only endpoints as a tuning API.

## Phase 4: bounded real welle-cli invocation (NO web listener)

**Source-verified behavior, 2026-11-05:**
The upstream welle.io README / welle-cli man page describe the
`-c CHANNEL`, `-F rtl_sdr`, `-p NAME` and `-T` options. The upstream
`src/welle-cli/welle-cli.cpp` waits for DAB synchronization, then emits
a `Service list` containing true service IDs, UTF-8 labels and DAB/
DAB+ audio components (where compiled with ALSA). The upstream
`src/various/Socket.cpp` **binds -w webserver to INADDR_ANY** and the
`src/input/rtl_sdr.cpp` driver opens the **first working** indexed
receiver. Avoid uncontained `-w`; a connection to 127.0.0.1 is not
proof that the decoder is private.

Upstream source:
- https://github.com/AlbrechtL/welle.io/blob/master/src/welle-cli/welle-cli.cpp
- https://github.com/AlbrechtL/welle.io/blob/master/src/input/rtl_sdr.cpp
- https://github.com/AlbrechtL/welle.io/blob/master/src/various/Socket.cpp

**Implemented in public branch:** `tihulu_runtime/welle_cli_probe.py`.
This is a real subprocess implementation but **no real SDR was used** to
validate it. It provides a `ReceiverBackend.probe` for the previously
implemented `DabAutoScanner.run(...)` and `ManagedSdrScan` single
foreground radio service lease / cooperating hardware lock:

- Only the exact 5A..12D / opt-in 13A..13F approved channel grid can
  be probed. Builds an argument list without a shell or arbitrary
  commands; starts `welle-cli -c <channel> -F rtl_sdr -T -p
  TIHULU_SCAN_DO_NOT_PLAY_ANY_RADIO_SERVICE_0123456789`. The long
  nonmatching `-p` selector lists services without playing audio.
  Never sends `-w` or `-D` (which writes dump files), `-d`,
  `-f`, or `-C`. Sends `.` to stdin to let the tool quit cleanly
  after it prints the service list.
- Bounded 4..40-second per-block dwell, stdout/stderr size 128 KiB,
  no unbounded `communicate()`, plus SIGTERM/SIGKILL process-group
  cleanup on timeout/error. No decoder launched by browsing the UI
  or reading presets. Cancellation from DAB scanner is checked between
  channel probes; the bound can delay cancellation within a block.
- A genuine upstream-style labelled service list with DAB/DAB+
  audio component yields `service_decoded` and user-selectable
  service IDs; FIC `New Service`/ensemble label without labelled
  services yields `signal_locked` ONLY. The absence of a decoded
  service within dwell is a `no_signal` scan classification, **not
  proof that the RF spectrum is silent**. Audio, RDS, picture, SNR,
  quality percentage and physical Pi RF reception are NOT claimed.
  Decoder backend errors produce `scan_failed`.
- Default identity gate is missing = FAIL CLOSED. The new
  `UniqueRtlReceiverGate` checks the canonical receiver sysfs
  `0bda:2838` USB path AND `librtlsdr` reports exactly one
  device before upstream `-F rtl_sdr` can choose that first unit.
  This count-only check neither opens a tuner nor proves reception.
  A second RTL device, missing library, mismatched sysfs identity,
  noncooperating outside process or device unplug needs separate
  handling. The future trusted authenticated Pi service must own
  an allowlisted package-managed welle-cli binary and this gate;
  never expose the gate to untrusted client inputs.
- Actual webserver-based DAB playback / Expert RF telemetry remains
  a **separate** feature needing verified network namespace or
  equally strong 127.0.0.1 isolation. The existing
  `WelleLocalReader` intentionally only READS an already-isolated
  service and is not used by this no-web auto scanner.

**Synthetic CI:** `tests/test_welle_cli_probe.py` runs real child
Python processes pretending to be welle-cli, with actual Linux
subprocess/timeout/kill tests, fake sysfs + librtlsdr count, and
an end-to-end `DabAutoScanner -> ManagedSdrScan -> WelleCliDabProbe ->
ChannelStore` path. These tests do not decode real DAB RF.
Dedicated SDR CI run:
https://github.com/Tihulu/tihulu-survival-kit/actions/runs/42109454946
Python 3.11 and 3.12 both PASS **79 synthetic tests each**
(15 SDR radio + 20 SDR/Stage4 + 16 DAB auto scan +
18 no-web welle CLI + 10 local DAB reader), plus Radio Center
JavaScript syntax. Global Stage4-5 CI remains independently red on
unrelated AI admission state.

**Next acceptance:** Pi5 direct USB reception on 5C/9A/11D with
real installed welle-cli built with RTLSDR+ALSA, reliable per-block
decoder dwell and UTF-8 service labels, power/thermal/USB coexistence,
actual Task Center owner job status and trusted cancellable gateway.
Do not enable UI's "Start RF Scan" until these conditions and real
authenticated application wiring are satisfied.

## Main-project Stage8 integration and actionable work package

This Radio integration is **not standalone**: it belongs to the existing Tihulu Survival Kit Stage8 implementation roadmap and is tracked in [public epic #3](https://github.com/Tihulu/tihulu-survival-kit/issues/3) with 12 tickets `SDR-DAB-01…12`. Read the [main-project DAB auto-scan roadmap](radio/DAB_AUTO_SCAN_STAGE8_ROADMAP.md) for per-feature acceptance, dependencies, Basic/Expert UI, region Quick / Full 32 / extended 38, Task Center ownership and real Pi release gates. The private canonical Stage8 Plan92/Plan93 and existing MW-29/26/43/07/44/09/10/48 (plus independent TV MW-27) are cross-referenced without exposing private planning history in public.

**Current engineering truth:** browser preview and synthetic Python backend exist; no authenticated Pi API, no real web streaming, no working Pi DAB/HE-AAC service receiver, no live scan button, no original-audio durable recorder, no multi-dongle USB identity guarantee or whole-suite green CI. Published frequency seeds remain NOT received; automatic scans are opt-in and background OFF. This document is technical evidence, not a standalone shipped application.
