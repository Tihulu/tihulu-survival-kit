# Task & Window Manager — Stage 4 Incremental Prototype

**November 5, 2026:** `tihulu_runtime/app_manager.py` implements a tested *logical app-view and server-owned job registry*, using the Stage 4 shared service leases. This is **not** a desktop window manager or a deployed Tihulu browser UI. Reported controller states are not measurements of operating-system processes.

## Planned user experience

Under **Settings → Running Applications** (mobile first, with tablet and desktop parity):

- Group app views by application and authenticated user/device, showing active/closed/in-use states plus independent Hard Enabled / Background Enabled / Start at Boot settings.
- Allow multi-select **Open selected**, **Close selected**, and **Pause optional background tasks**. Closing a view must not blindly terminate an authorized file transfer, AI analysis, radio/TV capture, or recording.
- Tabs and windows are lightweight **views**; disconnected passive views may be released after an idle policy. Independent server-owned **jobs** must remain visible in Task Center after reconnect.
- Long-running work offers **Request cancellation** → **Cancellation requested** → trusted executor acknowledgment. No success notification until the actual executor confirms. Recording termination requires an explicit owner confirmation, safe flush/finalization, and preservation of source media.
- Show actual CPU, memory, energy, and systemd state **only after** instrumenting and validating them. Until then, label metrics **not measured**.
- Never expose another user's private sessions or jobs without a real authorization policy. Protected Pi core, hotspot, auth, mounts, and recovery never appear as killable optional processes.
- Emergency monitoring remains an explicit owner decision and is never silently switched off by an Eco profile.

## Code boundaries

- `AppManager.open_app`: acquires one view-specific lease; `close_app` releases only that view. Multiple active views share the underlying worker.
- `AppManager.start_job`: creates an independently owned server task. `request_cancel` only marks a request; `executor_ack_finished` is the privileged completion callback.
- `sweep_disconnected_views`: releases stale passive views, **not** durable jobs.
- `prototype/task_manager.html`: standalone interactive visual **demo** only. It performs no real device/process operations, authentication, or persistent writes.

## Test command

```bash
python3 -m unittest discover -s tests -v
```

## Still required before a production release

Build authenticated HTTPS APIs, server-side owner/role checks, CSRF protection, real systemd/D-Bus/cgroup metrics, resource quotas, safe recording and file operations, executor cancellation, durable job storage across reboot, state reconciliation, a functional mobile UI, and hardware tests on a Pi 5 with 8 GB RAM. Do not publish an unauthenticated HTTP wrapper around this library.
