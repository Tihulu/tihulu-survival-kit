# Tihulu Stage 4 — Experimental On-Demand Service Manager

**Status — November 5, 2026:** This branch contains a Python standard-library **service policy and lease-management prototype**, including automated unit tests. **Nothing has been installed on a Raspberry Pi.** A production UI, authenticated API, real systemd service mappings, installer/image, Kiwix/Kolibri/LLM/SDR integration, and physical RAM/power measurements remain outstanding. The prototype does not currently download news, receive radio broadcasts, or load AI models. A functional Tihulu Home/hotspot has not yet been released.

## Policy and lifecycle contract

- **Hard Enabled**, **Background Enabled**, **Start at Boot**, **Installed**, and **Observed Runtime** are distinct concepts. An installed optional module may start on the user's explicit foreground request despite Background OFF / Startup OFF; disabling background processing prevents unattended polling, warm-up, and scheduled work.
- **Hard OFF must not be bypassed silently.** After verified owner authorization, a bounded one-time grant can enable an explicitly scoped service for one task (maximum one hour). The saved Hard OFF preference remains unchanged. A later mobile dependency-resolution dialog must offer: **Enable only for this task**, **Enable persistently**, or **Continue without it**.
- **Shared workers:** Browser translation, Radio captions, and multiple browser tabs must acquire leases on a single Translator/ASR/LLM worker rather than launching duplicates. When the last task releases its lease, an optional idle timeout permits the worker to stop. Closing a browser view must not terminate a separate, authorized server-owned recording or long job.
- **Emergency monitoring** requires an explicit setup decision; an unconfigured state is not equivalent to ON or OFF. Turning monitoring off stops new polling/notifications, without deleting original recorded alerts, personal files, or history.
- **Protected core services** are not optional: Pi OS, NVMe mounts, Tihulu Kit Wi-Fi AP, DNS/DHCP, authenticated portal, recovery, and the offline Guide are outside this manager. The optional adapter allows only explicitly mapped `tihulu-*.service` **user** units, not arbitrary root/system services.
- **News policy:** Rolling 24-hour retention and a 30 MB cache cap belong to a separate future News storage implementation. The present library controls whether a news worker may start; it is not an article downloader, cache cleaner, or scheduler.
- **Resource budgets:** CPU/RAM/PSI, energy usage, job admission, power policy, durable crash recovery, and safe recording finalization still require actual integration and measurements on the Pi 5 (8 GB). No wattage, performance, or available-memory measurements are claimed.
- **Client capture:** Server-owned jobs may continue after a tab changes or disconnects. Client-owned camera/microphone acquisition cannot be promised to continue from a backgrounded phone browser. Per-job Task Center controls and robust cancellation remain to be integrated.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```

## Minimal example with a fake adapter

```python
from tihulu_runtime import Module, ServiceManager

class Fake:
    def start(self, module_id):
        print("start", module_id)

    def stop(self, module_id):
        print("stop", module_id)

manager = ServiceManager([Module("translator", installed=True)], Fake())
manager.acquire("translator", task_id="browser-translate-1", owner_id="owner")
manager.release("browser-translate-1", owner_id="owner")
manager.sweep_idle()
```

The logical catalog in `tihulu_runtime/catalog.py` covers News, Kiwix, Kolibri, Maps/Router, Local AI, Translator/OCR/ASR/TTS, Browser, Radio, TV, Emergency, Files/Nextcloud, PDF/Office/Media, Subtitle Studio, NOMAD utilities, local BBS, and Update Checker. It deliberately initializes these entries as `installed=False`; a catalog entry never proves a service is present or running.

**Security boundary:** A production API must derive `owner_verified` from authenticated server-side sessions and role/CSRF checks; it must never trust `owner_verified=true` from clients. The Python library is not safe to expose directly over an unauthenticated network.

**Design reference:** Approved private Stage 4 Checkpoint 043, plans 55/57/58, and multi-tab/multi-device job model in plan 70. Design approval is not deployment.
