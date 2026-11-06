# Cross-app SDR / tuner service ownership and automatic release contract

Status: **mandatory integration requirement**, not a claim that the Survival Kit
has implemented or validated this broker yet. Written 2026-11-06, for
Tihulu Survival Kit, Flight Radar, Text Center, satellite data, RTL-433,
FM/DAB+, DVB-T2 and every future antenna-using module.

## User-visible non-negotiable behavior

**Default: close app → release the RF receiver.** Every desktop, mobile,
Raspberry Pi portal and local-web module must show real **START / STOP**
controls (with exact receiver, service ownership, status and failure
reasons). The default background receiver policy is **OFF**. A user may
opt into an explicitly labelled *keep receiving in the background* mode
only with an associated tray/daemon status, responsible owner and Stop
button; doing so must never happen as a side effect of installing,
opening a page, a passive hardware scan or accepting an OS permission.

Release applies to the physical receiver (and any powered frontends),
not merely the web page, radio player or map viewer. A running map
server or cached aircraft.json is NOT evidence that the USB tuner is
free. Stopping a receiver must be verified by the backend and hardware
lease closure, not inferred from an idle frontend or terminated tab.

## Resource and ownership model

1. Discover receivers passively using stable VID/PID, physical USB port,
   receiver serial if available, driver backend and current process
   ownership. Treat the same Nooelec NESDR SMArt v5 (0bda:2838) as **one
   tuner**: readsb/ADS-B 1090 MHz, rtl_fm, welle-cli/DAB, RTL-433, satellite
   reception and other RTL2832U receivers cannot tune different bands
   simultaneously. Treat a distinct Hauppauge DVB-T2 frontend as a
   separate physical lease.
2. A shared \`ReceiverLeaseBroker\` arbitrates every actual acquisition:
   \`receiver_id\`, \`owner_app\`, \`owner_process\`, \`owner_session\`,
   \`source_kind\`, \`scope\`, \`started_by_app\`, \`lease_deadline\`,
   \`background_allowed\`, \`protected_recording\`, \`state\`.
   Default exclusive access per physical tuner. Multiplexed services on
   an already tuned DAB ensemble may share ONE decoder and one lease;
   do not duplicate RTL USB handles.
3. **Ownership ≠ detection.** A process found running when the app
   opens is externally managed. Do not kill or retune it simply
   because a new app window/tab closes. Only release app-launched
   children, app-owned systemd units (tracked from a previously
   inactive state), and authorized leases. A process not started by
   the app remains external and requires explicit user-mediated
   handoff. No global pkill, broad killall, reset, force-stop, or
   indiscriminate \`systemctl stop readsb\` in shutdown handlers.
4. App-managed children use their own process group/job object.
   Graceful stop → bounded wait → kill only that process tree →
   release file descriptor/device lock → verify tuner can be acquired.
   Close must wait for in-flight Start/Restart worker completion before
   releasing, preventing a delayed subprocess from acquiring a tuner
   **after** the UI has closed. Report cleanup failures instead of
   saying *receiver freed*.
5. Browser-based interfaces must send best-effort same-origin,
   CSRF-authenticated unload/session-close signals **and** have
   server-side lease TTL/heartbeat enforcement. Browser \`pagehide\`
   and \`sendBeacon\` are not guaranteed to fire on crash or OS kill;
   a watchdog must release app-owned tuner sessions when heartbeats
   expire. Multiple tabs must have independent session identities;
   closing one tab must never stop another tab's established lease.
   Server shutdown/SIGTERM and host desktop close paths must also
   release leases. Automatic idle expiry must not erase recordings
   or SQLite archives.
6. Services (readsb, tar1090, welle-cli, RTL-433, FM decoders,
   DVB transports, and future satellite protocols) expose:
   **Start**, **Stop**, **Restart** (where meaningful), **Current
   owner**, **Receiver free/busy**, **Last RF evidence**, **Auto-stop on
   exit** and **Background receiving** status. Starting a frontend
   map without RF must not implicitly start readsb. Starting a
   decoder must be an explicit action, not passive source discovery.
7. A service originally started by an external systemd unit does NOT
   become app-owned just because the UI observes it running. If it
   was enabled at OS boot, app closing normally leaves that external
   service alone and shows a clear *external receiver still busy*
   warning. Users can stop it explicitly through its source app's
   controls. Do not disable startup units without explicit separate
   consent. If the app itself started it, release it on close by
   default and leave system-wide boot enablement unchanged.
8. Never preempt protected recordings, Flight Radar/readsb, another
   app's shared tuner, or remote receiver sessions. Handoffs require
   user consent and a two-phase transaction: request handoff, stop
   current owning service, confirm lock release, then start new decoder;
   on failures, preserve ownership state and offer safe explicit
   rollback. If reactivating the previous owner on exit, require that
   the broker remembered the exact previous state and that no other
   owner took the lease in the meantime.
9. Keep **receive-only** constraints. No automatic APRS/packet/other
   RF transmit or fake emergency broadcasts; internet overlays are
   source-labelled and separate from actual antenna reception.
10. On Raspberry Pi and offline portal, default radio/News/AI
    background polling OFF. Multi-device support maps separate
    receiver IDs to modes, and a mode without a physical RTL receiver
    cannot turn on an SDR worker.

## Cross-platform service rules

| Platform | Lifecycle |
|---|---|
| Pop!_OS / Ubuntu / Debian | Narrowly allowed systemctl controls for app-owned readsb etc, child process groups, no root blanket rights |
| Raspberry Pi | Shared local broker/daemon and web session leases, watchdog, bounded RAM/CPU |
| Windows x64 | Spawned subprocess group/Job Object, explicit termination and process exit verification |
| macOS Apple Silicon | Child process groups, native app shutdown callback, hardware entitlement diagnostics |
| GitHub Pages frontend | Cannot access USB or stop a local service by itself; must connect to a user-installed, origin-restricted loopback companion. Companion owns leases and watchdog |

**No web UI or GitHub Pages client may claim a radio service was stopped
without a confirmed response from its backend owner.**

## Existing independent code / migration constraints

- Flight Radar: \`Tihulu/tihulu-flight-radar\`, draft
  [receiver exit release PR #7](https://github.com/Tihulu/tihulu-flight-radar/pull/7).
  Its Start/Stop/Restart already exist; review service-mode ownership and
  do not stop pre-existing OS readsb automatically.
- Text Center: \`Tihulu/TIHULU-TEXT-CENTER\`. Draft
  [RF lifecycle/managed DAB controls](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pulls).
  Existing FM RDS, audio, spectrum and live FM/TV sessions own their
  subprocess groups and use app-local stop paths. The proposed new
  managed DAB process must stop ONLY its own welle-cli child and leave
  externally started welle-cli and readsb alone.
- Keep open, in-progress [FM/DAB auto discovery PR #8](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/8) and
  [FM/MOT/audio/install PR #10](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/10)
  intact. Do not copy stale entire frontend/backend files over their
  latest heads. Agent branches must be merged selectively, with CI
  and hardware verification.
- Survival Kit project is still an architecture/handoff repository;
  this contract does **not** mean its full broker has been written.
  Do not quietly mark central service integration as complete.

## Verification / acceptance

- **One SDR contention:** Start Flight Radar app-managed readsb.
  Closing Flight Radar must stop app-owned capture and free RTL USB;
  Text Center can then start FM/DAB. Reverse handoff follows same
  rule. A pre-existing, externally started readsb should **not** be
  stopped by closing a viewer; status must identify the owner and
  offer an explicit Stop operation.
- **Failure:** Trigger missing sudo permission, blocked USB and
  failed child termination. UI must show failure, not a green
  *released* marker.
- **Browser:** Close/refresh Text Center tab, close its native wrapper,
  kill/interrupt the HTTP server normally, and simulate a browser
  crash without unload events. Owned DAB/FM should auto-stop within
  a documented bounded TTL, without affecting an external readsb or
  separately started welle-cli. Two tabs must not stop each other's
  receiver unintentionally.
- **Concurrent RF:** Under one dongle, ADS-B + FM or DAB + RTL-433
  must conflict explicitly. Independent DVB frontend must not be
  blocked by a different receiver unless truly shared hardware.
- **Persistence:** Stop/close must retain saved FM/DAB recordings,
  verified RDS/DLS, MOT slideshow, ADS-B JSON and offline archives.
- **CI:** Linux mocked process lifecycle, server starts/stops,
  CSRF, child-only kill, watchdog, restart and close-during-start.
  Physical acceptance on actual Pop!_OS NESDR and independent
  Raspberry Pi/Windows/macOS runs remain separate gates.
