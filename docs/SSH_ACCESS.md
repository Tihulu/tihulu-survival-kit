# SSH & Terminal Access — Tihulu Survival Kit

> **Project status (November 6, 2026):** This is the **planned offline Guide / Setup Wizard content**, not proof of a released Tihulu image or a working on-device Guide. A regular Raspberry Pi OS Lite image does not automatically configure this project-specific SSH account.

## Planned SSH login

| Setting | Intended behavior |
|---|---|
| Linux / SSH user | `tihulu-kit` **when the Tihulu image builder/setup has actually created it** |
| Initial SSH password | **Owner-selected and provisioned privately for the individual Pi**; never embedded in public GitHub, a shared image or this Guide |
| SSH enablement | Owner-controlled; do not assume port 22 or SSH is active until the service is enabled and verified |
| Web owner login | Separate identity and authentication policy from SSH |
| Wi-Fi passphrase | Separate owner-provisioned secret for the `Tihulu Kit` hotspot |

The project owner may choose a specific initial SSH password **locally** during their own image build or initial setup. It must be applied through protected provisioning, with an OS password hash and no plaintext copy in release metadata, logs or downloadable artifacts. Prefer a strong unique password or an SSH public key, and change any temporary password before enabling wider LAN access. Linux generally does **not** store a recoverable plaintext password, so a Guide cannot safely display or recover the existing one.

## Which SSH command should I use?

After the corresponding network and SSH service have **actually been configured**:

```sh
# While your computer is joined to the Pi's "Tihulu Kit" hotspot:
ssh tihulu-kit@tihulu.lan
# Alternative on the Pi hotspot ONLY:
ssh tihulu-kit@10.10.10.10

# On a compatible home LAN with working mDNS/Avahi:
ssh tihulu-kit@tihulu.local

# On a home router or direct-PC Ethernet link:
ssh tihulu-kit@<actual-pi-ip-address>
```

Replace the angle-bracket placeholder with the real Pi IP shown by the router, the device status screen, or a trusted local diagnostic. The Pi's hotspot IP is **not** the router/direct-PC Ethernet IP. `tihulu.lan` is not automatically resolvable on arbitrary routers.

The SSH client prompts for the locally provisioned **Linux account password** (not Wi-Fi or web owner password), or uses the owner's configured SSH key. Do not type a password as part of the command, URL or GitHub file. Verify the expected SSH host key/fingerprint through an independent trusted channel before accepting it, especially after a reimage or hardware recovery.

## Enable, disable or change credentials

**Proposed on-device owner UI:** `Guide > Network & SSH` and `Settings > Security > SSH / Remote Access`.

- Show actual SSH **Enabled / Disabled / Unavailable** service status and currently valid LAN/AP addresses; do not invent a working address.
- Allow the authorized owner to **Enable SSH**, **Disable SSH**, **Set/Change password**, add/revoke **authorized SSH public keys**, and restrict SSH to trusted LAN/hotspot interfaces. Never expose the SSH listener by default on the public Internet.
- Account `tihulu-kit` must have been securely created before presenting login as ready. A shared/reusable Tihulu image must **not** contain any publicly known working password.
- When logged in as that account, use `passwd` to change its **own** password interactively. For recovery, use a separately authorized administrator or verified local recovery procedure; do not expose/reset secrets from an unauthenticated Guide.
- Changing the SSH password must **not** silently modify the web owner credential or Wi-Fi hotspot password. No blind secret reset during OS updates.

**No SSH needed for regular Tihulu:** after a real phone-ready Core exists, Home, apps and Setup Wizard should be usable directly from the authenticated browser, even without SSH.

## Troubleshooting

1. **Name does not resolve:** check you are on the correct hotspot/home LAN; use the actual interface IP and confirm Pi DNS/mDNS was installed.
2. **Connection refused:** SSH is not enabled/running or the firewall blocks that interface; check authorized Settings or on-device recovery.
3. **Permission denied:** confirm Linux account `tihulu-kit` was provisioned and enter its own password/authorized key; web owner login and hotspot PSK are not SSH passwords.
4. **Host key changed:** do **not** blindly remove host-key warnings. Confirm expected reimaging/rekeying or investigate unexpected device changes.
5. **No boot after AI HAT upgrade:** this is not an SSH issue; restore a physically validated PCIe/NVMe boot layout with power safely removed. See [Post-install AI HAT upgrades](AI_HARDWARE_UPGRADES.md).

See also [Network Access](NETWORK_ACCESS.md), [First Things to Know](START_HERE.md), [Installation](INSTALLATION.md).

## Official Raspberry Pi OS SSH defaults

The [official Raspberry Pi remote-access guide](https://www.raspberrypi.com/documentation/computers/remote-access.html) documents SSH as **disabled by default** on a standard Raspberry Pi OS installation. The supported [Raspberry Pi Imager setup](https://www.raspberrypi.com/documentation/computers/getting-started.html) includes **Remote Access → Enable SSH** and allows a personally configured password account or public SSH key. Tihulu's future personalized image must explicitly create `tihulu-kit` and configure the authorized login; simply documenting the name cannot enable SSH.
