# AI HAT+ 2 / NVMe boot preflight — safe, read-only developer diagnostic

**Status (2026-11-05):** This is a root-device *survey*, not a tested hot-plug or automated dual-boot mechanism. No actual Pi 5, AI HAT+ 2, SSD, EEPROM, battery, or model was modified. The new synthetic-fixture unit tests passed in the isolated development environment (13/13); GitHub Actions and real-device boot verification remain outstanding.

## Why this exists

A Raspberry Pi 5 exposes a PCIe connector. A PCIe-connected NVMe HAT for the system boot disk and Raspberry Pi AI HAT+ 2 cannot be assumed to work together without an explicitly verified topology. If an owner removes the NVMe HAT to install the AI HAT+ 2, the system may no longer have its boot drive. Choosing a smaller CPU model is not sufficient unless the **OS, CPU runtime, Base model files, source data and required application state** are still accessible.

The Raspberry Pi foundation's official AI HAT+ 2 documentation states that it connects through PCIe, includes 8 GB of dedicated Hailo-10H memory, and needs matching runtime/drivers and supported Hailo models. The OS bootloader and storage layout must be verified separately. On the Pi 5, USB boot capability and adequate power supply are also physical prerequisites; do not infer them from a Linux root device name.

Official sources:
- https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html
- https://www.raspberrypi.com/documentation/computers/ai.html
- https://www.raspberrypi.com/documentation/computers/raspberry-pi.html
- https://www.raspberrypi.com/documentation/accessories/m2-hat-plus.html

## Diagnostic command (developer checkout, on the Pi when available)

```bash
python3 -m tihulu_runtime.ai_setup --boot-topology
# Optionally, only if the correct Hailo CLI is installed:
python3 -m tihulu_runtime.ai_setup --boot-topology --probe-npu
```

`--boot-topology` only reads `/proc/cmdline`, `/proc/self/mountinfo`, `/proc/device-tree/model` and, where available, Linux `/dev/disk/by-partuuid` or `by-uuid` symlinks. It **does not** run package installation, modify EEPROM `BOOT_ORDER`, edit `config.txt`, mount/unmount/formats disks or probe PCIe destructively. The optional `--probe-npu` uses an existing bounded read-only `hailortcli fw-control identify` probe and does not install a driver.

The output contains:
- `boot_topology`: original root specification, root mounted source, resolved device when possible, `pcie_nvme`, `sd_card`, `usb_or_scsi_candidate` or `unknown`, and the evidence used.
- `hat_change_advisory`: `pcie_root_conflict`, `boot_root_unverified`, `usb_transport_unverified` or `sd_boot_candidate`, **always** `physical_swap_approved: false`, `both_layouts_boot_verified: false` and `eeprom_boot_order_verified: false`. One boot can never prove both layouts.
- `wizard_proposal.pcie_conflict_warning`: automatically reflects a directly detected PCIe NVMe root, independently of the existing manually supplied `--pcie-nvme-boot` override.

**Interpretation:** `sd_boot_candidate` is not clearance to disconnect or attach a PCIe board. `/dev/sdX` might be USB, SATA or SCSI; it is intentionally never reported as proven USB. `root=PARTUUID=...` with no resolvable device remains **unknown** rather than assumed SD. Conflicting root evidence is reported as **unknown**. Root volume and partition identifiers may be private device metadata; do not post raw unredacted reports publicly.

## Both-configuration acceptance protocol (future owner/operator + actual Pi)

Only on actual tested hardware, with a verified backup and safe recovery media:

1. Inventory present root/boot disk and Base CPU GGUF model location. Confirm the OS boots and Base CPU inference works in the **HAT-absent** hardware configuration, with Kiwix and core services operational.
2. Plan a *separately supported* root disk (microSD or tested USB 3 SSD, if necessary) for the **HAT-present** configuration, plus adequate power for Pi 5, Hailo board, storage, cooling and attached RF devices. First test this alternate boot path **before** making physical HAT changes. Keep originals and model weights; do not silently clone/format a selected drive.
3. Shut down completely, remove all power, then attach the AI HAT+ 2 according to official instructions. Reconnect power and boot. Verify exact Hailo-10H firmware ID, Hailo runtime/model allowlist, installed Advanced inference, system disk and Base CPU fallback still accessible.
4. Save *separate authenticated test evidence* for both boots: root transport, model/OS UUID/revision (not public), actual CPU inference result, preserved books/wiki indexes and services, power readings and owner-confirmed physical setup.
5. Shut down and disconnect power again before removing the HAT. Reboot and verify the same Base CPU inference and original apps/data are available. Repeat after reattaching; never claim dynamic HAT hot-removal.
6. Measure idle watts and joules for comparable inference workloads under both power profiles. **Base is a resource/feature profile, not a measured promise of less total energy.**

The current diagnostic verifies **none** of steps 1–6 on actual hardware. It also cannot verify full EEPROM boot order, cryptsetup/LVM root transport, real USB bus topology, SSD power headroom, PCIe switches or compatible Hailo model inference. For these cases return an unknown/candidate result and require explicit further measurements.

## Code and tests

- [Read-only collector](../../tihulu_runtime/ai_boot_topology.py)
- [CLI integration](../../tihulu_runtime/ai_setup.py)
- [13 fixture-based unit tests](../../tests/test_ai_boot_topology.py)
- [2 additional mocked CLI tests](../../tests/test_ai_setup.py)
- [Existing profile fallback policy](../../tihulu_runtime/ai_profiles.py)
- [Interactive UI mock](../../prototype/ai_mode_profiles.html), now with a *simulated* boot-drive status; not wired to real hardware.

Run in a development checkout:

```bash
python3 -m unittest tests.test_ai_boot_topology tests.test_ai_setup -v
python3 -m unittest discover -s tests -v
```

The new **13** topology-fixture tests were executed and passed in an isolated development container; the **2** newly added CLI-integration test cases have not been observed running yet. Real Pi testing, public CI status and Pi startup service integration remain future gates. Keep this draft-only until validated.
