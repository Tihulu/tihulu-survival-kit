# Tihulu Local BBS / Forum — Planned Optional Feature

**Status: design only.** Broadcast teletext and FM/DAB radio text are **one-way** services. Two phones or computers connected to the Tihulu Kit Wi-Fi hotspot could instead exchange local messages through a **web-based bulletin board/forum**, without Internet access or additional radio hardware. No such server has been built or deployed yet.

## Proposed features and boundaries

- Home → Communication → Local Forum: topics, threaded replies, direct/group messaging, and text-first posting. Attachments disabled by default. UI language options are English, Turkish, and German, independent of the engineering documentation language.
- Only authorized devices/accounts may access messages. Guests must not read another user's private messages by default. Production deployment requires HTTPS, strong authentication, access control, CSRF defenses, and privacy tests.
- Offline access is limited to the **local Wi-Fi/LAN served by the Pi**. This does not magically reach remote users or become a Meshtastic, CB Packet, APRS, or Winlink gateway.
- Planned optional-service defaults: **Hard Enabled ON / Background OFF / Startup OFF**. Start on demand, unload after the last active user if safe, and permit opting into background operation. Closing one user's view must not interrupt another user's active forum work.
- The News Center's **24-hour expiry does not apply to user-created forum posts**. Message retention, deletion permissions, backup, and private-chat history require separate explicit user-facing controls.
- Proposed SQLite storage must enforce per-account authorization and deletion, with upload quotas, spam/abuse protections, and rate limiting. The forum must never write to protected system files.
- Optional future bridges to Meshtastic or packet-radio BBS require an **explicit manual action**, compatible and permitted transmitter hardware, and local regulatory checks. **No automatic message forwarding or RF transmission**.
- The `local_bbs` catalog entry is a logical placeholder with `installed=False`, not a running app.

## Relation to other communication sources

TV teletext and RDS/DAB are receive-only; a separate authorized transceiver enables some two-way radio services. The Local BBS needs only a reachable Pi hotspot/LAN and an installed forum server, once implemented.

See [Radio Text and Messaging Networks](RADIO_TEXT_AND_MESSAGING_NETWORKS.md) and [Stage 4 Service Manager](SERVICE_MANAGER_EXPERIMENT.md).
