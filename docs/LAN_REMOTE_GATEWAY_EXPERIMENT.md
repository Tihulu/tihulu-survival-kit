# Experimental regional-channel API and LAN remote gateway

**Snapshot:** November 5, 2026. **Branch:** `feature/on-demand-service-manager-2026-11-05`, draft PR #1. **Not installed on Raspberry Pi; not a production TV/Radio player.** The gateway transports authenticated browser commands and persists user lineups but does **not** tune receivers, decode DVB, start a recording, play video, change system volume, generate subtitles or run local AI.

## What this actually adds

The previous static HTML prototype used local browser storage and a same-browser `BroadcastChannel`. The additional gateway, `tihulu_runtime/lan_remote_gateway.py`, provides a real standard-library HTTP API, SQLite-backed regional/channel lists, and a server-side expiring phone/display pairing and command queue (in `lan_remote_broker.py`). `prototype/lan_remote.html` and `prototype/lan_remote.js` communicate with that API using same-origin `fetch`.

A remote client and the display may be different browsers/machines when both reach the **same securely configured Pi server**. No actual two-device hardware test has been performed, and command acknowledgement means only that the browser display received the request; it is **not** receiver, media, or executor acknowledgement.

No RF action occurs through this server. It is also not connected to `RemoteCommandPolicy`'s trusted media renderer: a production implementation must additionally require a trusted execution broker and distinguish `browser_received`, `tuner_locked`, `service_decoded`, `playback_started` and `playback_failed` states.

## Local developer run (loopback only)

From the repository root with Python 3.11+:

```bash
mkdir -p "$HOME/.local/share/tihulu-survival-kit"
export TIHULU_OWNER_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(40))')"
python3 -m tihulu_runtime.lan_remote_gateway \
  --host 127.0.0.1 --port 8443 \
  --db "$HOME/.local/share/tihulu-survival-kit/lineups.sqlite"
```

Open `http://127.0.0.1:8443/` in a browser **on the same machine**. Enter the generated owner token in the Setup tab to authenticate. Keep this token private; it is a local single-owner administrator credential. The browser does not intentionally store it in URLs, cookies or localStorage, but developer tools, malware or a compromised host can still read in-memory credentials. Do not share the token, publish it in GitHub, paste it into screenshots or deploy the prototype on untrusted hosts.

After entering the token, choose Germany/Türkiye → region → city; create a named channel profile, select published frequency candidates and add custom entries. Changes persist in the SQLite file. A country/city candidate is not evidence of a received channel.

Open the **Display** tab on the display browser and register a TV/radio screen. It shows an **eight-digit, single-use code valid for 120 seconds**. Open the **Phone remote** view in another browser tab or in a securely connected separate device and enter the code. The remote obtains a time-limited bearer token (up to 60 minutes). It can send allowlisted channel, volume, playback, subtitle and Teletext *requests*. The display polls **only while its tab is visible**, paints the request on screen and returns a `display_received` response. Nothing is physically tuned or played. Revoke the display to invalidate the paired remote. Restarting the server clears all in-memory sessions and command queues, but preserves saved SQLite channel profiles.

## Optional LAN testing (must use TLS)

A remote device **cannot** connect to `127.0.0.1` on the Pi because that is loopback, and plain HTTP must **not** be exposed to other hosts. The gateway refuses non-loopback listening unless both TLS certificate and private key are explicitly supplied:

```bash
python3 -m tihulu_runtime.lan_remote_gateway \
  --host 0.0.0.0 --port 8443 \
  --db "$HOME/.local/share/tihulu-survival-kit/lineups.sqlite" \
  --cert /secure/path/lan-fullchain.pem --key /secure/path/lan-key.pem \
  --hostname tihulu.lan --hostname tihulu.local --hostname 10.10.10.10
```

**Use a valid, trusted certificate** matching the DNS name/IP via SAN and keep the private key readable only by its service owner. Certificate issuance, OS/firewall configuration, DNS setup, HTTPS trust on phones, reverse proxy and Raspberry Pi hardware are not part of this implementation. Do **not** bypass browser TLS errors for a real deployment. A dedicated Pi hostname, trusted local CA or supported proxy configuration should be evaluated before production release.

The intended names require separate provisioning:

- `tihulu.local` relies on an operational mDNS announcement and client mDNS support; this server does not install or configure Avahi.
- `tihulu.lan` requires a local DNS resolver or hotspot DNS override; it does not automatically resolve through mDNS.
- `10.10.10.10` is a planned hotspot address, not verified or assigned by this server. A matching IP SAN and correct network routing are needed for HTTPS.

The gateway binds only when launched explicitly. It does **not** start at boot, establish an AP, use the Internet, browse to GitHub, start an AI model, decode an antenna, or run background jobs. Client command polling occurs only while the display is open and visible, at a modest interval.

## Authentication, pairing and API limits

- `TIHULU_OWNER_TOKEN`: strong random ASCII secret, minimum 32 characters. Gateway deliberately supports **one local development owner**, `local-owner`, not a complete multi-user auth system. Do not treat it as a hardened production accounts service.
- A trusted owner session registers a TV or radio display (max 8 concurrent sessions), obtains a display bearer and a one-use eight-digit code. The code expires after 120 seconds; repeated bad guesses are rate limited by peer and globally. A valid code is consumed at pairing.
- A paired remote session expires after up to one hour, is restricted to the target's TV/radio medium, and may only *read* saved owner lineups. Owner-only mutations cannot use a remote bearer. Display revocation invalidates remote sessions; secrets are never placed in query strings.
- Only allowlisted simple remote commands and channel selections are accepted. Channel requests are checked against the owner's actual saved profile/items and target medium; the server does not execute an RF or playback action. Incoming bodies are capped at 16 KiB; commands are capped at 64 pending per display, with bounded in-memory retention.
- Only allowlisted Host headers are accepted. Browser Origin values on API requests must match the exact actual scheme/host; no permissive CORS headers or cookies are emitted. CSP prevents third-party scripts/frames, JSON responses are `no-store`, and the server suppresses logs containing request paths/tokens.
- Access tokens are held only in the active web page memory; refreshing the page requires entering the owner token/pairing again. Pairing state is volatile, intentionally.
- Explicit user permission and an actual authenticated owner API remain mandatory for real scanning. This gateway never acquires a tuner lease. The service-manager worker lease and real physical tuner broker still need integration.

### Available endpoints

| Method | Path | Required scope | Meaning |
|---|---|---|---|
| GET | `/api/health` | Public | Honest experimental integration flags |
| GET | `/api/regions`, `/api/cities`, `/api/candidates` | Owner | Administrative regions and published-only candidates |
| GET | `/api/profiles`, `/api/items` | Owner or paired remote (read-only, medium-scoped) | Owner SQLite lists |
| POST | `/api/profiles`, `/api/items/presets`, `/api/items/custom`, `/api/items/edit`, `/api/items/reorder`, `/api/items/remove` | Owner | Persist selections and edits, no RF |
| POST | `/api/display/register`, `/api/display/revoke` | Owner | Create/revoke display pairing |
| POST | `/api/remote/pair` | Code + rate limit | Consume one-time code, create paired remote |
| POST | `/api/remote/send` | Paired remote | Queue display command only |
| GET | `/api/display/poll` | Display bearer | Read its pending commands |
| POST | `/api/display/ack` | Display bearer | Confirm browser receipt only |
| GET | `/api/remote/status` | Paired remote | Read pending/delivered/received status |

There are no permanent remote keys, no arbitrary shell commands, no multicast or unapproved radio transmissions, no background news/API polling and no combined source/feed cache purge.

## Tests and remaining release gates

Run `python3 -m unittest discover -s tests -v`. `tests/test_lan_gateway.py` covers actual loopback HTTP request/response, owner checks, persistent SQLite channel lists, remote pairing, expiry, revocation, one-time codes, command acknowledgement, target media restrictions, rejected cross-origin/host requests, rate limits, bound queue capacity, response security headers and TLS-only LAN binding policy.

Tests use no SDR/DVB hardware, no real stream, no Pi network, no TLS certificate, and no separate phone. Browser UI has not been end-to-end tested in a mobile Safari/Firefox environment. **Do not merge into `main` as a finished LAN remote.**

Before production: trusted app accounts, real HTTPS certificate trust and DNS, hardened reverse proxy, actual two-device pairing tests, robust client reconnect and delivery retries, a physical tuner lock/recording journal with executor ACK, playback renderer / stream, DVB subtitle and Teletext decoding, source-grounded Translator/AI jobs, RAM/CPU/thermal measurements, and explicit cancellation rules for durable recordings.
