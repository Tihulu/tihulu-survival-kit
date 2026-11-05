"""Fixture-only root/PCIe boot preflight tests: no Raspberry Pi touched."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tihulu_runtime.ai_boot_topology import (
    _device_kind, _root_arg, _root_mount_source, _resolve_root_spec,
    inspect_boot_topology, hat_change_advisory,
)


def fixture(root: Path, *, bootroot="/dev/nvme0n1p2", mount="/dev/root"):
    (root / "proc/self").mkdir(parents=True, exist_ok=True)
    (root / "proc/device-tree").mkdir(parents=True, exist_ok=True)
    (root / "proc/device-tree/model").write_text("Raspberry Pi 5 Model B\x00")
    (root / "proc/cmdline").write_text("console=tty1 root=" + bootroot + " rw quiet\n")
    (root / "proc/self/mountinfo").write_text(
        "22 1 259:2 / / rw,relatime - ext4 " + mount + " rw\n"
        "23 22 8:1 / /media/usb rw,relatime - ext4 /dev/sda1 rw\n"
    )


class BootTopologyTests(unittest.TestCase):
    def test_mount_parser_finds_exact_root_not_nested(self):
        self.assertEqual(_root_mount_source(
            "12 3 8:2 / / rw - ext4 /dev/sda2 rw\n"
            "13 12 8:1 / /media/usb rw - ext4 /dev/nvme0n1p1 rw"), "/dev/sda2")

    def test_kernel_root_option_parser(self):
        self.assertEqual(_root_arg("console=ttyS0 root=PARTUUID=abc-123 quiet"),
                         "PARTUUID=abc-123")
        self.assertEqual(_root_arg("console=ttyS0"), "")

    def test_direct_pcie_nvme_is_conflict(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            snap = inspect_boot_topology(root=root)
            self.assertEqual(snap.root_class, "pcie_nvme")
            self.assertEqual(hat_change_advisory(snap)["state"], "pcie_root_conflict")
            self.assertFalse(hat_change_advisory(snap)["physical_swap_approved"])

    def test_resolved_partuuid_is_recognized_without_mount_device(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, bootroot="PARTUUID=abc-123")
            dev = root / "dev"
            dev.mkdir(parents=True)
            (dev / "nvme0n1p2").touch()
            lookup = dev / "disk/by-partuuid"
            lookup.mkdir(parents=True)
            (lookup / "abc-123").symlink_to("../../nvme0n1p2")
            snap = inspect_boot_topology(root=root)
            self.assertEqual(snap.root_class, "pcie_nvme")
            self.assertEqual(snap.evidence, "resolved_kernel_root")

    def test_partuuid_without_proven_symlink_is_unknown(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, bootroot="PARTUUID=unknown")
            snap = inspect_boot_topology(root=root)
            self.assertEqual(snap.root_class, "unknown")
            self.assertEqual(hat_change_advisory(snap)["state"], "boot_root_unverified")

    def test_sd_candidate_is_not_verified_dual_boot(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, bootroot="/dev/mmcblk0p2")
            advice = hat_change_advisory(inspect_boot_topology(root=root))
            self.assertEqual(advice["state"], "sd_boot_candidate")
            self.assertFalse(advice["both_layouts_boot_verified"])
            self.assertFalse(advice["base_model_verified_in_both_layouts"])

    def test_sd_mounted_root_while_kernel_root_unknown(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, bootroot="PARTUUID=missing", mount="/dev/mmcblk0p2")
            self.assertEqual(inspect_boot_topology(root=root).root_class, "sd_card")

    def test_dev_sd_is_not_assumed_proven_usb(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, bootroot="/dev/sda2", mount="/dev/sda2")
            advice = hat_change_advisory(inspect_boot_topology(root=root))
            self.assertEqual(advice["state"], "usb_transport_unverified")
            self.assertFalse(advice["physical_swap_approved"])

    def test_mount_kernel_conflict_must_fail_closed(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, bootroot="/dev/mmcblk0p2", mount="/dev/nvme0n1p2")
            snap = inspect_boot_topology(root=root)
            self.assertEqual(snap.root_class, "unknown")
            self.assertEqual(snap.evidence, "conflicting_root_evidence")

    def test_missing_proc_files_must_fail_closed(self):
        with TemporaryDirectory() as d:
            snap = inspect_boot_topology(root=d)
            self.assertEqual(snap.root_class, "unknown")
            self.assertFalse(hat_change_advisory(snap)["physical_swap_approved"])

    def test_invalid_partuuid_rejected(self):
        with TemporaryDirectory() as d:
            self.assertEqual(_resolve_root_spec("PARTUUID=../escape", Path(d)), "")
            self.assertEqual(_resolve_root_spec("UUID=../../etc/passwd", Path(d)), "")

    def test_root_kind_unrecognized_device(self):
        self.assertEqual(_device_kind("/dev/mapper/cryptroot"), "unknown")
        self.assertEqual(_device_kind("overlay"), "unknown")

    def test_advisory_is_no_write_and_never_green_lights_swap(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root, bootroot="/dev/mmcblk0p2")
            before = sorted(str(x.relative_to(root)) for x in root.rglob("*"))
            result = hat_change_advisory(inspect_boot_topology(root=root))
            after = sorted(str(x.relative_to(root)) for x in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertTrue(result["power_off_before_pcie_change"])
            self.assertFalse(result["installer_or_disk_action_performed"])
            self.assertFalse(result["eeprom_boot_order_verified"])


if __name__ == "__main__":
    unittest.main()
