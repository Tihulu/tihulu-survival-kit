# Flight Radar Center — full tar1090 first, lightweight map second

**2026-11-06 · experimental Stage8/9 integration, not a deployed Pi product**

This implementation extends existing Flight Radar Center Draft PR #4 and its
provider policy Draft PR #5. It does **not** modify the independently usable
`Tihulu/tihulu-flight-radar` desktop application. It does not vendor or
rewrite tar1090, invent observations, run receiver processes, create licensed
offline map packages, or merge to main.

## Upstream audit and compatibility

- Exact upstream tree audited: `wiedehopf/tar1090` master commit
  `5d59b1ba2c5e30eb23f1161940367b7767f10ad5`.
- Source: https://github.com/wiedehopf/tar1090
- tar1090 **GPL-2.0-or-later**. Serve the original installed upstream assets,
  retain their original copyright, license and attribution; do not silently
  copy upstream JS into the Kit under a different license.
- Official frontend: original `html/index.html`, `early.js`,
  `defaults.js`, `config.js`, `script.js`, styles/icons/libs.
- Upstream `nginx.conf` / `88-tar1090.conf` map **relative** data roots:
  `data/`, `chunks/`, `globe_history/`, `aircraft_sil/` and optional
  `osm_tiles_offline/` and `openfreemap_offline/`. Some chunk/trace files
  are gzip-encoded despite non-.gz extensions; the gateway sets the
  corresponding headers for recognized upstream formats.
- The actual **installed Pi package version, dynamic decoder mode, assets,
  Linux capabilities, data/chunks/history paths and copyright details still
  must be inspected on the physical system**. Reading upstream master is not
  proof a tar1090 package is installed or that its JS works with this mount.
- Upstream `README-query.md` documents `?icao=...&noIsolation`,
  `?pTracks`, `?allTracks`, `?zoom`, filters and many more options.
  The gateway preserves query parameters on redirects instead of
  inventing a weaker subset of tar1090 UI functionality.

## Native same-origin routing (no Qt wrapper and no new public port)

```text
/flight-radar                  -> /flight-radar/map (when full tar1090 installed)
                              -> light dashboard if missing; never claim full
/flight-radar/map              -> /flight-radar/tar1090/   (primary full map)
                              -> /flight-radar/light-map?full_map_unavailable=1
/flight-radar/tar1090/         -> ORIGINAL installed tar1090 index.html
/flight-radar/tar1090/*.js    -> ORIGINAL installed assets (incl. libs/images)
/flight-radar/tar1090/data/*  -> trusted readsb JSON root, as available
/flight-radar/tar1090/chunks/* -> trusted tar1090 service runtime chunks
/flight-radar/tar1090/globe_history/* -> optional installed history root
/flight-radar/light-map       -> existing low-resource map and source UI
/api/flight-radar/*           -> existing authenticated FlightRadarCenter API
```

These routes only exist in a **mountable Python WSGI handler**;
there is currently no verified Survival Kit production reverse proxy/gateway
or real `tihulu.lan` DNS connection. The existing trusted gateway must provide
owner authentication, device/session identity, host allowlist, origin/CSRF on
mutations, TLS/HTTP local policy and shutdown/cancellation hooks. Never
serve tar1090 unprotected on a new public port.

Implementation: `tihulu_runtime/tar1090_gateway.py` and updates to
`flight_radar_http.py`, plus existing `prototype/flight_radar.html/js`.
The default trusted conventional Linux paths are **candidates only**:
`/usr/local/share/tar1090/html`, `/run/readsb`, `/run/tar1090`.
A real installer must verify package version and actual runtime paths and
supply `Tar1090Gateway(Tar1090Paths(...))`. Optional roots must be explicitly
configured, not guessed or taken from HTTP inputs. `html` must contain a
complete minimal upstream asset set before it counts as installed.

## Map camera and responsive behavior

- Primary map is the upstream native tar1090 page, **not** the simplified
  canvas or an iframe; consequently original table, filters, multi-selection,
  keyboard shortcuts, labels and overlays remain reachable *if* dependencies
  exist and browser QA confirms them.
- At `/flight-radar/map` without an explicit query, a bounded trusted
  `readsb aircraft.json` check chooses the nearest **fresh genuine ICAO
  positional aircraft** to configured `receiver.json` location. If receiver
  coordinates are absent, the nearest aircraft to Germany's published default
  geographic viewport is a labeled **heuristic**, NOT a receiver/user location.
  Documented tar1090 `?icao={real_id}&noIsolation` gives the first focus
  without hiding the aircraft table. No actual aircraft? No `?icao` is
  produced. tar1090's own `receiver.json` and browser location handling
  still require real runtime/browser verification.
- `config.js` is served unmodified *after* an in-memory fallback prelude
  setting `DefaultCenterLat=51.1657` and `DefaultCenterLon=10.4515`.
  The real operator's `config.js` retains final say; genuine `receiver.json`
  site coordinates take precedence in upstream. No files are overwritten.
- Lightweight fallback defaults to Germany on a zero-plane/no-location start.
  If verified receiver/device location exists, use that; on first **fresh real**
  aircraft contact, auto-focus near genuine receiver/GPS or Germany heuristic.
  Manual pan, selection, and explicit Show Germany remain functional.
- Native tar1090 smartphone/tablet UI comes from upstream, not a separate
  reduced aircraft list. Actual screenshots, portrait/landscape, keyboard,
  pinch and saved selected-aircraft state must be verified before release.

## Security, privacy, offline and feature boundaries

- All served tar1090 file requests pass the same **parent WSGI authentication
  and exact trusted-host allowlist** before any disk read. Gateway rejects
  path traversal, encoded path escapes, symlink files, unconfigured roots,
  oversize assets and missing dependencies; no arbitrary URLs/systemd commands.
  GET-only routes do not create SDR leases, turn on decoder services or install
  anything.
- A restrictive same-origin CSP prevents silent third-party online image/API
  calls from native upstream frontend by default. Full geographic map tiles
  require separately licensed **offline tile assets** through trusted roots,
  OR explicit vetted/consented online map source settings. A working empty
  coordinate map is not proof all tar1090 basemaps work offline.
- **Important:** Native tar1090 reads the local decoder's real readsb data,
  not automatically merged Internet ADS-B. Hybrid/Internet Only mode's
  source-labeled aircraft in the current lightweight API **are not yet
  injected into the full tar1090 map**. A separate versioned normalized
  tar1090-compatible hybrid output adapter, preserving source and MLAT,
  is a release blocker. Never write internet positions into the original
  readsb file or label remote data as local SDR RF.
- Legacy tar1090 `re-api` mode (`--tar1090-use-api`) is NOT mounted by
  this initial read-only file gateway. A verified Unix socket proxy/adapter
  is required before enabling that decoder mode; keep classic data/chunks
  configuration otherwise. History/replay/heatmap/trace JSON are served
  only when installed and explicitly configured, with real retention and
  external SSD quotas; no fabricated heatmap or unlimited SD writes.
- Empty receiver data must never invent a plane, and a decoder process being
  active is not proof of actual RF messages. Physical Start/Stop/Restart,
  tar1090 service health, per-owner source settings, multiple SDR competing
  processes, full responsive visual verification and HAS/Guide/Setup wiring
  remain open work.
- This module is CPU-only; AI HAT+2 does not enable aircraft position tracking.

## Tests and release gates

`tests/test_flight_radar_tar1090.py` uses **mock files only** to check:
auth, host allowlist, original upstream asset route, config Germany fallback,
pTracks query compatibility, data/chunks and gzip headers, missing history,
path traversal/symlink, real positioned readsb nearest-ICAO selection,
Mode S without coordinates, stale/no aircraft, no installation fallback,
and safe redirect normalization. CI uses Python 3.11/3.12 and Node syntax
checks. **No physical Raspberry Pi, genuine tar1090 install, RF message,
licensed map tile, phone browser screenshot or actual Nextcloud/SSD test is
performed by these fixtures**.

Minimum real acceptance after separate owner permission: confirm
`/flight-radar`, `/flight-radar/map`, `/flight-radar/tar1090/?pTracks`,
`/flight-radar/light-map`, nested map JS/CSS/icons, data snapshots,
history/range/heatmaps when enabled, readsb Start→Stop→Start→Restart, idle
and multi-client ownership, authenticated device-IP and local name routing,
mobile/iPad/desktop responsive controls and unmodified original RF history.

**Stage governance:** Stages1–7 DESIGN approved; Stage8 review open, not
whole-stage approved; Stage9–10 not approved. No main merge or standalone
app changes. Latest standalone v0.3.1 main and full tar1090 handoff remain
authoritative; only proven features may be marked implemented.
