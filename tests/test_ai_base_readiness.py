"""Mock-only current-boot Base assessment tests; never physical Pi approval."""
import unittest
from tihulu_runtime.ai_base_readiness import BaseEvidence, assess_base_readiness
from tihulu_runtime.ai_boot_topology import BootTopology


def topology(kind='sd_card'):
    return BootTopology('Pi 5','/dev/mmcblk0p2','/dev/mmcblk0p2','/dev/mmcblk0p2',
                        kind,'root_mount_source')


def evidence(**kwargs):
    data=dict(model_id='base-gguf', storage_status='hash_verified',
              gguf_header_checked=True, checksum_verified=True,
              cpu_runtime_detected=True, cpu_inference_passed=True,
              tested_model_id='base-gguf')
    data.update(kwargs)
    return BaseEvidence(**data)


class BaseReadinessTests(unittest.TestCase):
    def test_strong_single_boot_still_not_dual_verified(self):
        out=assess_base_readiness(topology(), evidence())
        self.assertEqual(out.state,'current_boot_candidate')
        self.assertTrue(out.current_boot_candidate)
        self.assertFalse(out.two_physical_layouts_verified)
        self.assertFalse(out.hardware_swap_approved)
        self.assertIn('second_physical_boot_not_verified',out.missing_checks)

    def test_unconfigured_base(self):
        out=assess_base_readiness(topology(),BaseEvidence())
        self.assertEqual(out.state,'base_not_configured')
        self.assertFalse(out.current_boot_candidate)

    def test_unplugged_external_model(self):
        out=assess_base_readiness(topology(),evidence(storage_status='storage_unavailable'))
        self.assertEqual(out.state,'base_storage_unavailable')

    def test_missing_model_bytes(self):
        out=assess_base_readiness(topology(),evidence(storage_status='integrity_unknown'))
        self.assertEqual(out.state,'base_storage_unavailable')

    def test_format_proof_needed(self):
        out=assess_base_readiness(topology(),evidence(gguf_header_checked=False))
        self.assertEqual(out.state,'base_format_unverified')

    def test_hash_verification_needed(self):
        out=assess_base_readiness(topology(),evidence(checksum_verified=False,
            storage_status='present_not_reverified'))
        self.assertEqual(out.state,'base_checksum_unverified')

    def test_cpu_runtime_required(self):
        out=assess_base_readiness(topology(),evidence(cpu_runtime_detected=False))
        self.assertEqual(out.state,'cpu_runtime_unavailable')

    def test_cpu_actual_smoke_required(self):
        out=assess_base_readiness(topology(),evidence(cpu_inference_passed=False,
            tested_model_id=None))
        self.assertEqual(out.state,'cpu_inference_unverified')

    def test_unmatched_smoke_proof_rejected(self):
        with self.assertRaises(ValueError):
            evidence(tested_model_id='different')

    def test_spurious_smoke_without_model_rejected(self):
        with self.assertRaises(ValueError):
            BaseEvidence(cpu_inference_passed=True, tested_model_id='base')

    def test_pcie_nvme_conflict_even_when_current_cpu_working(self):
        out=assess_base_readiness(topology('pcie_nvme'),evidence())
        self.assertEqual(out.boot_risk,'pcie_root_conflict')
        self.assertFalse(out.hardware_swap_approved)
        self.assertIn('pcie_root_conflict',out.missing_checks)

    def test_unknown_root_not_approved(self):
        out=assess_base_readiness(topology('unknown'),evidence())
        self.assertIn('boot_root_unverified',out.missing_checks)
        self.assertFalse(out.hardware_swap_approved)

    def test_sd_root_only_candidate(self):
        out=assess_base_readiness(topology(),evidence())
        self.assertEqual(out.boot_risk,'sd_boot_candidate')
        self.assertFalse(out.two_physical_layouts_verified)

    def test_usb_sd_candidate_is_not_proven_usb_boot(self):
        out=assess_base_readiness(topology('usb_or_scsi_candidate'),evidence())
        self.assertIn('root_transport_unverified',out.missing_checks)
        self.assertFalse(out.hardware_swap_approved)

    def test_invalid_evidence_rejected(self):
        with self.assertRaises(ValueError):
            evidence(storage_status='guaranteed')

    def test_serialized_output_is_json_compatible(self):
        data=assess_base_readiness(topology(),evidence()).as_dict()
        self.assertIsInstance(data['missing_checks'],tuple)
        self.assertFalse(data['hardware_swap_approved'])

if __name__=='__main__':unittest.main()
