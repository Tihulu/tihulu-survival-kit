# Network Access — Tihulu Kit, tihulu.lan, tihulu.local and Ethernet

> **Status:** This is a proposed networking guide. Tihulu Core and its portal have **not** been released. Names and addresses work only when the relevant DNS, networking and application services have really been installed and configured. No personal passwords or actual assigned IP addresses are included here.

## Quick reference

| Topic | Planned behavior |
|---|---|
| Raspberry Pi hotspot SSID | **`Tihulu Kit`** |
| Hotspot password | **Unique per device**, provisioned by owner during setup; **not published on GitHub** |
| Admin password | Separate strong credentials, **not identical to the hotspot password** |
| Hotspot DNS name | **`tihulu.lan`** |
| Hotspot fallback IP | **`10.10.10.10`** |
| Home-router access | **`tihulu.local` if mDNS works**, otherwise the Pi's real assigned LAN IP |
| `tihulu.lan` on the home router | Only with the router's own local DNS alias/host record |
| Direct PC Ethernet | Actual Pi link IP or supported mDNS; hotspot IP is **not** an Ethernet fallback |
| Public internet exposure | **Off/unsupported by default**; do not confuse local-LAN access with public WAN access |

## Four connection methods

### A — Pi's built-in hotspot

- The Pi's built-in Wi-Fi operates as the **Tihulu Kit** access point, joined by a phone, tablet or PC.
- Planned hotspot DHCP/DNS should resolve `tihulu.lan` to `10.10.10.10`.
- If Tihulu Core and relevant content are installed, Home, Guide, Kiwix/Wikipedia, Kolibri, offline maps and local file apps can function **without WAN internet**.
- The hotspot should remain independent of a secondary USB Wi-Fi uplink or Ethernet.
- The future **Settings → Network → Tihulu Hotspot** interface should allow authorized SSID/password changes. Clients may need to reconnect after a change.

### B — Pi Ethernet to a home router

- Plug Pi Ethernet into the router's LAN port.
- Phones and computers on that router's local network should access the **same authenticated Tihulu Home** without joining the Pi hotspot.
- The router may assign a private address such as `192.168.x.y`; this is an **example pattern, not a promised address**.
- With working Pi Avahi/mDNS, client support and multicast transport, `tihulu.local` may resolve.
- Your router will not automatically resolve `tihulu.lan`; an explicit local DNS record may be required.
- Local offline applications can still operate if the home router loses WAN connectivity.

### C — Second USB Wi-Fi to a home router

- The built-in Pi Wi-Fi remains the **Tihulu Kit** AP while a **separate USB Wi-Fi adapter** joins the router as a Wi-Fi client.
- Phones/computers on the router LAN use the same authenticated Home and installed services, as in method B.
- If no second adapter is installed, this uplink method is unavailable; Ethernet and the Pi hotspot remain alternatives.
- The future Network Manager should identify each actual interface, SSID, assigned DHCP address, gateway, trusted LAN and internet status.
- Do **not** assume an arbitrary single Wi-Fi chip can operate reliably as AP and client simultaneously.

### D — Pi Ethernet directly to a computer (no router)

- Connect the Pi Ethernet port to a computer's Ethernet port or USB-to-Ethernet adapter.
- Both ends need mutually reachable, correctly configured IP addresses:
  1. If the computer runs Internet Sharing/ICS with DHCP, Pi Ethernet may obtain a DHCP address.
  2. Without DHCP, IPv4 link-local and mDNS may work **if both devices support and permit them**.
  3. Otherwise use an intentionally chosen isolated static IPv4 network, with **different addresses** on each side.
- Try `tihulu.local` if mDNS works or enter the Pi's **actual Ethernet IP**. The hotspot-only `10.10.10.10` is not automatically correct.
- Direct Ethernet **does not automatically share the computer's internet**. The owner must enable sharing separately.
- Never enable a rogue DHCP/DNS server on the home-router Ethernet interface; direct-link DHCP and router-client configurations must be isolated.

## Optional: share a computer's internet connection with the Pi

Prerequisite: The computer has a working internet connection on another interface, is directly connected to Pi Ethernet, and the owner explicitly enables sharing.

| Computer | User-controlled sharing path |
|---|---|
| Windows 10/11 | **Internet Connection Sharing (ICS)**: share the connected internet interface with the Ethernet interface attached to the Pi; follow Windows DHCP/NAT behavior |
| macOS | **System Settings → General → Sharing → Internet Sharing**, from the actual upstream connection to Ethernet |
| Linux (NetworkManager / Ubuntu / Pop!_OS) | Set Ethernet IPv4 method to **Shared to other computers**; NetworkManager may provide local DHCP/NAT while Pi uses DHCP |

These changes happen in the **computer OS**, not by granting a browser page silent control of firewall/network sharing. Verify actual interfaces, subnet, gateway and firewall behavior for your OS version. If the computer sleeps, powers down or loses connectivity, Pi internet access can stop while the independent Tihulu hotspot may continue.

Internet access is **not** required to load local Tihulu apps across properly configured direct Ethernet, assuming the future Core server exists.

References: [Apple Internet Sharing](https://support.apple.com/guide/mac-help/share-internet-connection-mac-network-users-mchlp1540/mac), [NetworkManager IPv4 shared mode](https://networkmanager.dev/docs/api/latest/settings-ipv4.html), [Microsoft Windows Support](https://support.microsoft.com/windows).

## Which address should I use?

### `tihulu.lan` — hotspot DNS name

The Pi controls this hostname only for clients using its **own local hotspot DNS**. On a separate home router, you need a supported DNS host entry/alias or equivalent routing configuration. Joining a router does **not** silently reconfigure that router's DNS.

### `tihulu.local` — mDNS / Avahi

When the Pi uses the hostname `tihulu` and runs Avahi/mDNS, clients on a compatible local link may discover it as `tihulu.local`. Guest isolation, blocked multicast, different VLANs and missing mDNS support can prevent resolution. Use the actual Pi IP for the corresponding interface instead.

### IP addresses per interface

- Proposed hotspot: **`10.10.10.10`**.
- Router Ethernet or second USB Wi-Fi: actual **DHCP-assigned Pi IP**, not a fixed example.
- Direct Pi-to-PC Ethernet: actual address from the chosen PC-sharing, link-local or static profile.
- The future **Settings → Network** panel and local Pi/router utilities should show interface-specific real addresses and offer a copy action.

## Browser security and HTTPS

- Basic Home/offline content access depends on real local reachability and the configured HTTP/HTTPS web service.
- **Camera, microphone, geolocation and live OCR** are particularly sensitive to browser **secure-context / trusted HTTPS** requirements. A self-signed certificate is **not automatically trusted** on iOS, Android or desktop devices.
- `tihulu.lan`, `tihulu.local`, the hotspot IP, the router-assigned Pi IP and a direct PC Ethernet IP may each have **different hostname/certificate validation outcomes**. A future Guide must provide a genuinely tested trust procedure; live camera support cannot be assumed before then.
- Cloud AI, internet-facing remote control, UPnP and router port forwarding remain **disabled by default**. Local LAN reachability never removes owner authentication.

Technical references: [Raspberry Pi local discovery](https://www.raspberrypi.com/documentation/computers/remote-access.html), [RFC 6762 (mDNS)](https://www.rfc-editor.org/rfc/rfc6762), [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia), [MDN Geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API).

## Troubleshooting

| Symptom | What to check first |
|---|---|
| `Tihulu Kit` Wi-Fi is missing | Has an actual Tihulu Core AP ever been installed? Pi boot, NVMe, power, cooling, AP service |
| `tihulu.lan` fails on home Wi-Fi | Router may lack the DNS alias; try `tihulu.local` or Pi router IP |
| `tihulu.local` cannot resolve | Avahi/mDNS, client support, multicast, VLAN, guest isolation; use real IP |
| `10.10.10.10` fails from home router | It is a **hotspot-only** address; use Pi router IP instead |
| Direct PC Ethernet does not open portal | Ethernet link, PC/Pi addresses, firewall, DHCP/IPv4LL or selected static network |
| Pi cannot use PC internet | Explicit ICS/Internet Sharing on PC, real internet source, correct Pi gateway/DNS |
| Portal opens but live camera fails | Trusted HTTPS, camera permissions, browser support, installed OCR package |
| Pi hotspot disappeared | Check AP and second USB Wi-Fi roles, recovery settings and actual installed Core |

## Next steps

- [Getting Started](START_HERE.md)
- [Installation](INSTALLATION.md)
- [Live OCR & Device Permissions](LIVE_OCR_AND_PERMISSIONS.md)
- [Main README](../README.md)
- [Turkish translation](tr/NETWORK_ACCESS.md)
