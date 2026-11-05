# Flight Radar Center — Native Survival Kit integration (experimental)

**Development state 2026-11-05:** Draft PR #4, stacked on the existing experimental service manager Draft PR #1. **Not a released Raspberry Pi application, standalone HTTP server, actual USB/readsb controller or certified aviation service.** The standalone [Tihulu Flight Radar](https://github.com/Tihulu/tihulu-flight-radar) remains an independently maintained cross-platform desktop app; source audited at main commit \`ce1eb6e2a71c58e06db49812d8165d961046041b\` (v0.3.0 preview).

## Routing and service ownership

- Planned Home navigation: **Radio & SDR Center → Flight Radar**. A mountable WSGI adapter handles \`/flight-radar\` with the same responsive frontend for all screen sizes, and \`/api/flight-radar/*\` API routes.
- Planned host routes are \`http://tihulu.lan/flight-radar\` on an actual configured Pi AP with its own DNS; \`http://tihulu.local/flight-radar\` when mDNS/Avahi discovery and the client support it; verified LAN/AP interface IP fallback; optional explicitly configured \`tuhulu.local\` compatibility alias. These URLs **do not work until an actual Tihulu gateway, TLS/host authorization, DNS/Avahi and reverse-proxy mount exist**. Never expose the handler directly to the WAN.
- The WSGI adapter \`tihulu_runtime/flight_radar_http.py\` **does not create a socket or login system**: it requires the parent Portal to inject a trusted authenticated owner/device identity, CSRF issuer/validator and explicit hostname allowlist. Browser-provided identity strings are never treated as authorization.
- \`tihulu_runtime/catalog.py\` declares \`flight_radar\` as **optional, installed=False** until verified by the package manager. Stage4 Hard ON allows foreground work when installed; Background and Startup OFF by default. A real web session holds an owner-scoped Stage4 lease and same-ADS-B-stream SDR receiver lease. Closing one subscribed phone doesn't release another client's stream.
- Physical USB 1090-MHz receiver start/stop remains **HTTP 501 / unavailable** until a reliable readsb controller with restricted permissions and **process-shared** SDR lock is installed. No arbitrary systemd commands, receiver force-kill, driver installs or root shell.

## Real data model and modes

The standalone desktop app's \`core.py\` and \`map_focus.js\` were read. We created a web-safe stdlib-only native model with equivalent semantics instead of embedding Qt/PySide6 or copying the standalone desktop UI.

- \`flight_radar_model.py\`: real-only local \`readsb\` aircraft.json normalization, 60-second contact/position freshness, source-specific UTC timestamps, reliable **six-digit ICAO-only** join, original feed identities/provenance, field-level merge that will not overwrite a newer local position with an older Internet position. Mode S with no valid position stays a list contact, not a plotted coordinate. Source-tagged external MLAT is **not claimed to be single-receiver local MLAT**.
- \`flight_radar_sources.py\`: local verified-size/mtime JSON file, fixed-endpoint adapters for owner-authorized ADSB.lol and OpenSky. **Internet OFF by default**. Bounded 4-MiB HTTPS JSON, no redirects or client-input URLs, OAuth bearer kept server-side, minimum interval with fresh-cache-only reuse. Live provider queries, licensing and production quotas have **not** been exercised or certified. ADSB.fi is a candidate only until its terms are independently verified.
- Four modes: **Antenna Only**, **Internet Only** (doesn't lease RTL-SDR), **Hybrid** (local plus authorized Internet with provenance) and **Automatic** (limited available-source selection, not yet energy-meter/adaptive policy).
- \`sdr_resource_broker.py\` is a **single-process** exclusive tuner lease layer shared with the optional \`channel_explorer.py\` hook and \`channel_app_registry.py\`. It prevents same-process FM/DAB/RTL-433/1090 conflict and allows multiple subscribed clients on the same \`adsb_1090\` stream. It is **not** a cross-process/OS lock, and will not interrupt a separately running recording. Multiple devices must be tested.
- The actual Nooelec NESDR SMArt v5 received ADS-B under readsb on the user's desktop; **no Raspberry Pi 5 ADS-B reception was measured by this PR**. Hauppauge DVB-T2 hardware is a different USB tuner.

## UI: one adaptive screen, same backend

\`prototype/flight_radar.html\` and \`prototype/flight_radar.js\` have a compact dark style and use one URL for all clients. Desktop uses map and sidebar, tablet adaptive split, phone map plus sheet/navigation. Content uses **English** (code and API messages too), with keyboard focus and reduced-motion CSS. Resize/orientation preserve selected plane and camera state.

The canvas draws only aircraft with real recent coordinates and actual track heading when present. Initial focus uses the nearest aircraft if a trusted receiver/device location is known, otherwise an actually received cluster medoid. A map with no coordinates shows a truthful waiting state rather than a hard-coded city or country. Manual movement pauses automatic recentering; focus/follow requires explicit interaction. Device geolocation is an **explicit user action** and browser permission; the origin must actually be HTTPS/secure context where the API requires it. A bare HTTP \`.lan\` link does not guarantee geolocation.

**Maps:** default is an offline geographic coordinate grid (works without tile downloads or Internet). The user may explicitly choose **Online OpenStreetMap**. Only currently visible tiles are fetched from \`https://tile.openstreetmap.org\`, with browser caching behavior, a bounded in-memory tile list, no bulk prefetch and prominent OSM credit. An online-tile failure leaves the honest coordinate grid. A fully licensed offline MBTiles/PMTiles/vector dataset, package manager, region selection and on-device tile server are **not implemented**. Do not bulk-download public OSM tile servers; see the [OSMF tile usage policy](https://operations.osmfoundation.org/policies/tiles/).

## Optional history and current API

\`flight_radar_history.py\` provides a **separate optional** owner-scoped SQLite writer and JSON/CSV/GeoJSON export of real observations. Disabled by default. Its caller must pass verified storage volume approval; loss of an external SSD does not silently relocate private history. History retention/quota, cancelled job lifecycle and actual owner UI are still release gates. The WSGI handler currently responds **501** for history/stream routes (not connected to the separate history library), and has no live WebSocket/SSE implementation.

Available WSGI routes (only after mounting in authenticated Portal):

| HTTP | Path | Status |
|---|---|---|
| GET | \`/flight-radar\` | Responsive page asset from same-origin mount |
| GET | \`/flight-radar/app.js\` | English client JS |
| GET | \`/api/flight-radar/bootstrap\` | Trusted gateway's CSRF token; no anonymous bootstrap |
| GET | \`/api/flight-radar/status\` | Current owner session count, optional module and SDR lease info |
| GET | \`/api/flight-radar/sources\` | Available modes and configured providers, no secrets |
| POST | \`/api/flight-radar/session\` | Explicit on-demand session with owner/device permission and CSRF |
| GET | \`/api/flight-radar/aircraft?session=...\` | Fresh actual observations or explicit unavailable source |
| GET | \`/api/flight-radar/statistics?session=...\` | Current aircraft/position counts and source statuses |
| DELETE | \`/api/flight-radar/session/{id}\` | Owner's session lease release; other clients retained |
| GET | \`/api/flight-radar/history\` | **501 — not integrated yet** |
| GET | \`/api/flight-radar/stream\` | **501 — no SSE/WebSocket** |
| POST | \`/api/flight-radar/receiver/start\` / \`stop\` | **501 — real USB/readsb adapter required** |

The live source JSON contains UTC contact/position timestamps and position provenance; no route, aircraft position or current signal metric is synthesized.

## Verified tests and remaining work

CI workflow \`.github/workflows/flight-radar-tests.yml\` tests Python 3.11 and 3.12, the **entire** experimental unit-test suite and Node browser JS syntax. Test fixtures use synthetic readsb responses and mock receiver provider adapters; they are **not** proof of physical USB, authenticated production gateway, actual API provider Internet success or Pi5 thermal/energy performance. Latest check status must be read from the Draft PR; do not assume a previous commit's CI applies to the newest head.

Remaining priority gates: mount in the actual Survival Kit portal with authentication/HTTPS and session heartbeat/reconnect; stable Linux USB device IDs and restricted readsb lifecycle under an OS-wide lock; proven noninterrupting FM/DAB/RTL433/ADS-B arbitration; real provider permissions and quotas; licensed offline map packs and history UI/API; genuine Pi5 and multi-browser/client tests; measured memory/energy, Stage10 Setup Wizard and removable storage recovery.

No claim of aviation navigation, air traffic control, safety-critical collision avoidance or authoritative government Emergency information.
