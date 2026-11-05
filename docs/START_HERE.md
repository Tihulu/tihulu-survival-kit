# Getting Started — First Things to Know

> **Project status (November 5, 2026):** Tihulu Survival Kit is in planning and experimental development. There is **no released installable Tihulu image, automatic installer, functional local web portal, or on-device Guide**. This page documents the intended user experience and safe preparation; it is **not** a connection guide for a currently running Tihulu installation.
>
> **Security:** The public repository must never contain real Wi-Fi, administrator, Nextcloud or Hugging Face passwords/tokens. Any future public installation image must not use a shared, hard-coded administrator password.

## How will I connect?

After a future Tihulu Core installation and first-run configuration are complete, these are the intended access paths:

| Your device is connected to | How the Pi is connected | Preferred address | Fallback |
|---|---|---|---|
| Pi's own **Tihulu Kit** Wi-Fi | Built-in Pi hotspot; no internet required | `https://tihulu.lan` when HTTPS/DNS is properly configured | `10.10.10.10` (hotspot-only address) |
| Home router/modem Wi-Fi or LAN | Pi connected to router via **Ethernet** | `tihulu.local` if mDNS works | The Pi's **actual router-assigned local IP** |
| Home router/modem Wi-Fi or LAN | Pi connected to router through its **second USB Wi-Fi adapter** | `tihulu.local` if mDNS works | The Pi's **actual router-assigned local IP** |
| Computer directly wired to Pi | Direct Pi-to-PC Ethernet cable | `tihulu.local` if link/mDNS support it | The Pi's **actual direct-Ethernet IP** |

Addresses above are **design targets**, not active addresses today. The final scheme (`https://` versus any limited onboarding HTTP endpoint) depends on tested server and certificate configuration.

**Key points**

- **`Tihulu Kit` is the intended SSID, not a password.** Each device must have an owner-defined or securely provisioned **unique hotspot password**. Never look for a published working password in GitHub.
- **`tihulu.lan` belongs to the Pi-managed hotspot DNS design.** It is **not guaranteed** to work on your home router's Wi-Fi; a local router DNS record or alias may be needed.
- **`tihulu.local` relies on mDNS/Avahi** and client/network support. Guest Wi-Fi isolation, separate VLANs, blocked multicast or client limitations may prevent discovery. Use the Pi's actual address in that case.
- **`10.10.10.10` is the proposed Pi hotspot IP**, not the Pi's home-router LAN address.
- Browser camera, microphone and geolocation often require a **trusted secure HTTPS context**. A basic local HTTP connection may display a page but not permit live OCR or camera use. See [Network Access](NETWORK_ACCESS.md).

## What will first boot look like? (planned)

1. Obtain a **real published, verified Tihulu Core or Full Offline image** and write it to NVMe. **No such image has been released yet.** Installing Raspberry Pi OS Lite alone does not create Tihulu.
2. Attach NVMe/HAT, cooling and adequate power to the Pi 5. Once Core is actually installed, connect to its **Tihulu Kit** Wi-Fi. Alternatively, use router Ethernet, a secondary USB Wi-Fi client, or direct Pi-to-PC Ethernet.
3. Join the appropriate local network and open the **correct interface-specific address** in your browser.
4. Create the initial **administrator account**, and check the hotspot SSID/password. **Administrator and Wi-Fi passwords must differ.**
5. Choose **Quick Setup** (recommended), **Standard Next/Back**, or **Advanced**. Set UI language (English/Turkish/German), independent country/region selection, map area and Emergency monitoring preferences.
6. Inspect the setup summary: **installed**, **install now**, **download requires consent**, **install later**, or **unsupported**. Do not silently download large Wikipedia ZIMs, maps/routing graphs or LLMs. Offline first use should remain an option.
7. After secure Core setup, open **Tihulu Home** and manage missing optional packages via the future **Software & Update Center**.

## What should the first-run Guide show? (planned)

- **Home:** Installed and active applications, connectivity and storage status.
- **Network:** Tihulu hotspot, second USB Wi-Fi uplink, router Ethernet/direct PC Ethernet and actual usable URLs/IP addresses, with copy controls.
- **Setup:** Quick, Standard and Advanced installers, plus an install-later path.
- **Applications:** Kiwix/Wikipedia, Kolibri, Maps, Emergency, Radio, TV, Browser, Local AI, Translator/OCR, Files, PDF, Office and media apps **only when their components are actually installed**.
- **Service / Startup / Energy Manager:** Independent Hard/Background/Startup settings, safe idle-stop and power/resource visibility.
- **Files and Camera:** Phone file chooser, gallery and user-authorized camera/Live OCR; desktop drag-and-drop and file chooser, subject to device/browser permission.

## Frequently asked questions

**Where do I get the Wi-Fi password?** From the device-specific first-run provisioning procedure or a securely customized local configuration. Neither this guide nor the public repository contains a shared password. The planned **Settings → Network → Tihulu Hotspot** page should allow an authorized owner to change it later.

**Why doesn't `tihulu.lan` open?** First verify you are actually on the **Tihulu Kit** network. On a home router's Wi-Fi, try `tihulu.local` if supported or the Pi's current LAN IP instead. See [Network Troubleshooting](NETWORK_ACCESS.md).

**Does Tihulu work without internet?** Only for the applications and content packages that were previously installed. A missing Wikipedia archive, map or AI model will not be advertised as available offline.

**Can I scan text live with a phone camera?** This is a planned feature: permissioned frame capture, local OCR, optional translation/AI, and **separate consent** to save images. Read [Live Camera OCR & Permissions](LIVE_OCR_AND_PERMISSIONS.md).

**Why might the camera not open?** Browser/OS camera permissions and a trustworthy HTTPS origin may be required. An alternative user-initiated photo/file upload should remain available.

**Can Tihulu replace an official emergency-warning receiver?** No. It may display alerts from genuinely configured and reachable sources, but must never replace official channels or emergency services. Offline state, antenna/signal limitations and source age must be shown clearly.

## Further reading

- [Installation & First Configuration](INSTALLATION.md)
- [Network Access, Wi-Fi and Direct Ethernet](NETWORK_ACCESS.md)
- [Live Camera OCR and Device Permissions](LIVE_OCR_AND_PERMISSIONS.md)
- [Features & System Architecture](FEATURES_AND_ARCHITECTURE.md)
- [Main README](../README.md)
- [Turkish version of this guide](tr/START_HERE.md)
