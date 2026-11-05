# Task & Window Manager — Stage 4 incremental implementation

**5 Nov 2026:** backend `tihulu_runtime/app_manager.py` provides a tested **logical window/session and server-job manager** that uses the existing Stage4 shared service leases. It does NOT claim that a Pi desktop window manager or browser UI is currently deployed. Current running-service status is based on the experimental adapter's control state, *not* observed OS process metrics.

## Desired user experience
Settings > **Çalışan Uygulamalar** (phone-first, also tablet/desktop):
- Views by app (News, TV, Radio, AI, Browser, Kiwix, Kolibri, Maps, Files, etc.), grouped by the requesting device/user; inspect "Etkin / Kapalı / Kullanımda" plus Hard/Background/Startup policies.
- Multi-select: **Seçilileri aç** / **Seçilileri kapat** (only own views), **Arka planı duraklat**, **Gelecek açılışta başlat** toggles. "Kapat" asks what to do with active work but never blindly kills an authorized file transfer, AI analysis or TV/audio recording.
- Tabs in phone/desktop are lightweight **views**; their disconnect may release a stale view, while server-authorized **jobs continue**, listed in a persistent Task Center after reconnect.
- Each long operation has separate "Durdur" -> **İptal isteniyor** -> trusted executor ACK. No UI "success" before real process ACK. Recording termination needs owner confirmation and safe filesystem flush; original data untouched.
- Do NOT display per-process RAM, CPU, Watts or idle stop as real measured values before OS integration; use "not measured".
- Never expose another user’s session without admin ACL. Protected Pi Core, hotspot, auth, disk mounts and recovery never listed under stoppable optional apps.
- Emergency uses explicit opt-in; choosing "Eco" never silently disables an enabled monitoring policy.

## Current code
`AppManager.open_app`: obtains view-specific lease; `close_app`: releases only that tab/view; concurrent views share worker.

`AppManager.start_job`: server-owned long operation independent of view. `request_cancel`: marks requested only; `executor_ack_finished`: only trusted backend can mark finished and release its lease.

`sweep_disconnected_views`: reaps stale passive tabs, not associated jobs; actual server task persistence through process reboot, OS process lifecycle, frontend reconnection and authentication still require integration.

Run tests:
```
python3 -m unittest discover -s tests -v
```

## Before shipping
Implement authenticated HTTPS API and CSRF with server-side owner trust (never client-controlled `owner_verified`/`trusted_backend`), process observations from systemd/D-Bus/cgroups, safe radio/TV capture handling, actual cancel signals and Job Manager persistence, UI state reconciliation, no duplicate service workers, hardware tests on Pi5 8GB. Build a separate limited remote API for subscribed user roles. Do not publish an unauthenticated HTTP wrapper around this library.
