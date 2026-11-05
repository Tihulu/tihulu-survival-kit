# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only Raspberry Pi 5 root-drive survey for removable AI HAT+ 2 planning.

No bootloader, EEPROM, partition, filesystem or driver is changed. A one-boot
snapshot NEVER proves that the machine can boot in both HAT configurations.
Use only as a conservative diagnostic, not an authorization to remove a HAT.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

ROOT_CLASSES = frozenset({"pcie_nvme", "sd_card", "usb_or_scsi_candidate", "unknown"})


@dataclass(frozen=True)
class BootTopology:
    board: str
    root_spec: str
    root_mount_source: str
    resolved_root_device: str
    root_class: str
    evidence: str

    def __post_init__(self) -> None:
        if self.root_class not in ROOT_CLASSES:
            raise ValueError("Unknown root transport class")

    def as_dict(self) -> dict:
        return asdict(self)


def _read(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", errors="replace").strip("\x00\r\n ")
    except (OSError, ValueError):
        return ""


def _root_arg(cmdline: str) -> str:
    for arg in cmdline.split():
        if arg.startswith("root="):
            return arg[5:]
    return ""


def _root_mount_source(mountinfo: str) -> str:
    """Return only the source of / itself, never a nested mount."""
    for line in mountinfo.splitlines():
        if " - " not in line:
            continue
        before, after = line.split(" - ", 1)
        left, right = before.split(), after.split()
        if len(left) >= 5 and len(right) >= 2 and left[4] == "/":
            return right[1]
    return ""


def _device_kind(name: str) -> str:
    if re.fullmatch(r"/dev/nvme\d+n\d+p\d+", name):
        return "pcie_nvme"
    if re.fullmatch(r"/dev/mmcblk\d+p\d+", name):
        return "sd_card"
    # /dev/sdX does not prove USB attachment: SATA/SCSI also have sdX names.
    if re.fullmatch(r"/dev/sd[a-z]+\d+", name):
        return "usb_or_scsi_candidate"
    return "unknown"


def _resolve_root_spec(root_spec: str, root: Path) -> str:
    """Read-only resolution of known Linux /dev/disk/by-* links.

    Do not trust a root=PARTUUID token as proof of the physical transport until
    a real symlink resolves to a recognized partition device.
    """
    if root_spec.startswith("/dev/"):
        # A direct /dev path is evidence only for recognized partition schemes.
        return root_spec
    for prefix, folder in (("PARTUUID=", "by-partuuid"), ("UUID=", "by-uuid")):
        if not root_spec.startswith(prefix):
            continue
        key = root_spec[len(prefix):]
        if not re.fullmatch(r"[\w.:-]{1,128}", key, re.ASCII):
            return ""
        link = root / "dev/disk" / folder / key
        if not link.is_symlink():
            return ""
        try:
            resolved = link.resolve(strict=True)
        except (OSError, RuntimeError):
            return ""
        # Path may be a /dev name on live hardware, or inside a fixture root.
        # Only allow the relevant fixture /dev prefix to be mapped to /dev/...
        try:
            relative = resolved.relative_to((root / "dev").resolve())
        except ValueError:
            return ""
        if len(relative.parts) == 1:
            return "/dev/" + relative.name
    return ""


def inspect_boot_topology(*, root: str | Path = "/") -> BootTopology:
    """Collect one read-only snapshot. Supports synthetic fixtures via root."""
    root = Path(root)
    board = _read(root / "proc/device-tree/model") or "unknown"
    spec = _root_arg(_read(root / "proc/cmdline"))
    mounted = _root_mount_source(_read(root / "proc/self/mountinfo"))
    direct_kind = _device_kind(mounted)
    resolved = _resolve_root_spec(spec, root)
    spec_kind = _device_kind(resolved)
    if direct_kind != "unknown" and spec_kind != "unknown" and direct_kind != spec_kind:
        # Conflicting evidence must not be interpreted as a safe boot layout.
        return BootTopology(board, spec, mounted, resolved, "unknown", "conflicting_root_evidence")
    if direct_kind != "unknown":
        return BootTopology(board, spec, mounted, resolved, direct_kind,
                            "root_mount_source")
    if spec_kind != "unknown":
        return BootTopology(board, spec, mounted, resolved, spec_kind,
                            "resolved_kernel_root")
    return BootTopology(board, spec, mounted, resolved, "unknown",
                        "root_transport_unverified")


def hat_change_advisory(snapshot: BootTopology) -> dict[str, object]:
    """Conservative safety assessment. It NEVER approves a physical swap."""
    if snapshot.root_class == "pcie_nvme":
        state = "pcie_root_conflict"
        reason = ("Running OS root is on PCIe NVMe. Removing its NVMe HAT to fit "
                  "AI HAT+ 2 may prevent boot until a separate boot layout is tested.")
    elif snapshot.root_class == "unknown":
        state = "boot_root_unverified"
        reason = "Could not prove root storage transport; do not assume HAT swap will boot."
    elif snapshot.root_class == "usb_or_scsi_candidate":
        state = "usb_transport_unverified"
        reason = "A /dev/sd* root does not prove USB boot or power compatibility."
    else:
        state = "sd_boot_candidate"
        reason = "SD root observed in this boot; other HAT layout still needs real boot testing."
    return {
        "state": state,
        "explanation": reason,
        "root_class": snapshot.root_class,
        "power_off_before_pcie_change": True,
        "physical_swap_approved": False,
        "both_layouts_boot_verified": False,
        "base_model_verified_in_both_layouts": False,
        "eeprom_boot_order_verified": False,
        "installer_or_disk_action_performed": False,
    }
