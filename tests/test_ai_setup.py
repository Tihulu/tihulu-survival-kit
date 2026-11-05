"""Safe read-only Hailo firmware probe tests; no actual hardware."""
import unittest
import io
import json
from types import SimpleNamespace
from contextlib import redirect_stdout
from tihulu_runtime.ai_boot_topology import BootTopology
from tihulu_runtime.ai_hardware import HardwareSnapshot
from tihulu_runtime.ai_setup import main
from unittest.mock import patch
from tihulu_runtime.ai_setup import verify_hailo10h


class SetupTests(unittest.TestCase):
    @patch('tihulu_runtime.ai_setup.shutil.which', return_value=None)
    def test_without_hailortcli_never_marks_ready(self, which):
        self.assertFalse(verify_hailo10h())

    @patch('tihulu_runtime.ai_setup.shutil.which', return_value='/usr/bin/hailortcli')
    @patch('tihulu_runtime.ai_setup.subprocess.run')
    def test_verified_model_identity(self, run, which):
        run.return_value.returncode = 0
        run.return_value.stdout = 'Device Architecture: HAILO10H'
        run.return_value.stderr = ''
        self.assertTrue(verify_hailo10h())
        run.assert_called_once()
        self.assertEqual(run.call_args[0][0],
                         ['hailortcli', 'fw-control', 'identify'])
        run.return_value.stdout = 'Device Architecture: HAILO8'
        self.assertFalse(verify_hailo10h())


    @patch("tihulu_runtime.ai_setup.inspect_hardware")
    @patch("tihulu_runtime.ai_setup.inspect_boot_topology")
    def test_boot_topology_detects_pcie_root_without_writing(self, boot, hardware):
        hardware.return_value = HardwareSnapshot(
            "aarch64", "Pi 5", 8 << 30, ("0000:01:00.0",), True, True, (),
            hailo_initialized=True)
        boot.return_value = BootTopology(
            "Pi 5", "PARTUUID=abc", "/dev/root", "/dev/nvme0n1p2",
            "pcie_nvme", "resolved_kernel_root")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--boot-topology"]), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result["wizard_proposal"]["pcie_conflict_warning"])
        self.assertEqual(result["hat_change_advisory"]["state"], "pcie_root_conflict")
        self.assertFalse(result["hat_change_advisory"]["physical_swap_approved"])
        self.assertFalse(result["hat_change_advisory"]["installer_or_disk_action_performed"])

    @patch("tihulu_runtime.ai_setup.inspect_hardware")
    @patch("tihulu_runtime.ai_setup.inspect_boot_topology")
    def test_unknown_root_never_approved_for_hat_swap(self, boot, hardware):
        hardware.return_value = HardwareSnapshot(
            "aarch64", "Pi 5", 8 << 30, (), False, False, ())
        boot.return_value = BootTopology(
            "Pi 5", "PARTUUID=missing", "/dev/root", "",
            "unknown", "root_transport_unverified")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--boot-topology"]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["hat_change_advisory"]["state"], "boot_root_unverified")
        self.assertFalse(result["hat_change_advisory"]["both_layouts_boot_verified"])
        self.assertFalse(result["wizard_proposal"]["installation_performed"])


    @patch("tihulu_runtime.ai_setup.ModelStorageRegistry")
    @patch("tihulu_runtime.ai_setup.inspect_hardware")
    @patch("tihulu_runtime.ai_setup.inspect_boot_topology")
    def test_base_readiness_hash_and_magic_still_require_real_inference(self, boot, hardware, registry):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        hardware.return_value = HardwareSnapshot(
            "aarch64", "Pi 5", 8 << 30, (), True, False, ())
        boot.return_value = BootTopology(
            "Pi 5", "/dev/mmcblk0p2", "/dev/mmcblk0p2", "/dev/mmcblk0p2",
            "sd_card", "root_mount_source")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "small.gguf"
            path.write_bytes(b"GGUFexample-content")
            registry.return_value.models = {"base": SimpleNamespace(path="/models/base.gguf", sha256="hash", device_uuid=None)}
            registry.return_value.availability.return_value = "present_not_reverified"
            registry.return_value.verified_path.return_value = path
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--base-readiness", "--model-registry", "dummy.json",
                                       "--base-model-id", "base", "--verify-base-hash"]), 0)
            data = json.loads(output.getvalue())
            self.assertEqual(data["base_readiness"]["state"], "cpu_inference_unverified")
            self.assertFalse(data["base_readiness"]["hardware_swap_approved"])
            self.assertFalse(data["base_readiness"]["actual_inference_test_executed"])
            self.assertFalse(data["base_readiness"]["two_physical_layouts_verified"])
            registry.return_value.verified_path.assert_called_once_with("base")

    @patch("tihulu_runtime.ai_setup.ModelStorageRegistry")
    @patch("tihulu_runtime.ai_setup.inspect_hardware")
    @patch("tihulu_runtime.ai_setup.inspect_boot_topology")
    def test_base_unregistered_model_stays_unavailable(self, boot, hardware, registry):
        hardware.return_value = HardwareSnapshot(
            "aarch64", "Pi 5", 8 << 30, (), True, False, ())
        boot.return_value = BootTopology("Pi 5", "", "/dev/root", "",
                                          "unknown", "root_transport_unverified")
        registry.return_value.models = {}
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--base-readiness", "--model-registry",
                                   "dummy.json", "--base-model-id", "missing"]), 0)
        self.assertEqual(json.loads(output.getvalue())["base_readiness"]["state"],
                         "base_not_configured")
        registry.return_value.verified_path.assert_not_called()

    @patch("tihulu_runtime.ai_setup.ModelStorageRegistry")
    @patch("tihulu_runtime.ai_setup.inspect_hardware")
    @patch("tihulu_runtime.ai_setup.inspect_boot_topology")
    def test_mismatched_or_unreachable_model_never_approved(self, boot, hardware, registry):
        hardware.return_value = HardwareSnapshot(
            "aarch64", "Pi 5", 8 << 30, (), True, False, ())
        boot.return_value = BootTopology(
            "Pi 5", "/dev/nvme0n1p2", "/dev/nvme0n1p2", "/dev/nvme0n1p2",
            "pcie_nvme", "root_mount_source")
        registry.return_value.models = {"base": SimpleNamespace(path="/models/base.gguf", sha256="hash", device_uuid=None)}
        registry.return_value.availability.return_value = "storage_unavailable"
        registry.return_value.verified_path.side_effect = RuntimeError("offline SSD")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--base-readiness", "--model-registry", "dummy.json",
                                   "--base-model-id", "base", "--verify-base-hash"]), 0)
        data = json.loads(output.getvalue())["base_readiness"]
        self.assertEqual(data["state"], "base_storage_unavailable")
        self.assertIn("pcie_root_conflict", data["missing_checks"])
        self.assertFalse(data["hardware_swap_approved"])


    @patch("tihulu_runtime.ai_setup.cpu_smoke_test")
    @patch("tihulu_runtime.ai_setup.ModelStorageRegistry")
    @patch("tihulu_runtime.ai_setup.inspect_hardware")
    @patch("tihulu_runtime.ai_setup.inspect_boot_topology")
    def test_cpu_smoke_explicit_cli_marker_not_physical_boot_proof(self, boot, hw, registry, smoke):
        from tihulu_runtime.ai_cpu_smoke import CpuSmokeResult
        hw.return_value = HardwareSnapshot("aarch64", "Pi 5", 8 << 30, (), False, False, ())
        boot.return_value = BootTopology(
            "Pi5", "/dev/mmcblk0p2", "/dev/mmcblk0p2", "/dev/mmcblk0p2",
            "sd_card", "root_mount_source")
        registry.return_value.models = {"base": SimpleNamespace(
            path="/approved/base.gguf", sha256="a"*64, device_uuid=None)}
        registry.return_value.availability.return_value = "present_not_reverified"
        smoke.return_value = CpuSmokeResult(
            "base", "a"*64, "llama.cpp verified runner", "marker_observed",
            elapsed_seconds=0.32, marker_observed=True)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([
                "--base-readiness", "--model-registry", "existing.json",
                "--base-model-id", "base", "--run-base-cpu-smoke",
                "--smoke-service-allowed", "--smoke-resource-budget-ok"]), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["cpu_smoke"]["status"], "marker_observed")
        self.assertEqual(data["base_readiness"]["state"], "current_boot_candidate")
        self.assertTrue(data["base_readiness"]["actual_inference_test_executed"])
        self.assertFalse(data["base_readiness"]["hardware_swap_approved"])
        self.assertFalse(data["base_readiness"]["two_physical_layouts_verified"])
        smoke.assert_called_once()
        self.assertTrue(smoke.call_args.kwargs["explicit_owner_consent"])
        self.assertTrue(smoke.call_args.kwargs["service_allowed"])
        self.assertTrue(smoke.call_args.kwargs["resource_budget_allowed"])

    @patch("tihulu_runtime.ai_setup.cpu_smoke_test")
    @patch("tihulu_runtime.ai_setup.ModelStorageRegistry")
    @patch("tihulu_runtime.ai_setup.inspect_hardware")
    @patch("tihulu_runtime.ai_setup.inspect_boot_topology")
    def test_cpu_smoke_denied_by_policy_keeps_inference_unverified(self, boot, hw, registry, smoke):
        from tihulu_runtime.ai_cpu_smoke import CpuSmokeResult
        hw.return_value = HardwareSnapshot("aarch64", "Pi 5", 8 << 30, (), False, False, ())
        boot.return_value = BootTopology("Pi5", "", "/dev/root", "", "unknown", "root_transport_unverified")
        registry.return_value.models = {"base": SimpleNamespace(
            path="/approved/base.gguf", sha256="b"*64, device_uuid=None)}
        registry.return_value.availability.return_value = "present_not_reverified"
        smoke.return_value = CpuSmokeResult("base", None, None, "service_disabled")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--base-readiness", "--model-registry", "existing.json",
                                   "--base-model-id", "base", "--run-base-cpu-smoke"]), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["cpu_smoke"]["status"], "service_disabled")
        self.assertFalse(data["base_readiness"]["actual_inference_test_executed"])
        self.assertIn("cpu_inference_unverified", data["base_readiness"]["missing_checks"])
        self.assertFalse(smoke.call_args.kwargs["service_allowed"])
        self.assertFalse(smoke.call_args.kwargs["resource_budget_allowed"])

    def test_cpu_smoke_requires_all_explicit_scope_flags(self):
        for args in [
            ["--run-base-cpu-smoke"],
            ["--base-readiness", "--run-base-cpu-smoke"],
            ["--base-readiness", "--smoke-service-allowed"],
        ]:
            with self.assertRaises(SystemExit) as err:
                main(args)
            self.assertEqual(err.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
