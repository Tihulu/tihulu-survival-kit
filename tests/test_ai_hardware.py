"""Mock-only Phase-5 hardware/routing policy tests. No Pi or NPU is used."""
import tempfile
import unittest
from pathlib import Path
from tihulu_runtime.ai_hardware import (HardwareSnapshot, InferenceTarget, ModelSpec,
                                        choose_backend, compatibility, inspect_hardware,
                                        proposal, recommendations)

CPU = ModelSpec('qwen-cpu', 'gguf', 1.7, 'Q4', 1200000, 2048,
                {'cpu_local': 1000, 'remote_server': 900},
                frozenset({'cpu_local', 'remote_server'}))
HAILO = ModelSpec('hailo-approved', 'hailo', 2, 'INT4', 400000, 2048,
                  {'npu_local': 1200}, frozenset({'npu_local'}))


class HardwareTests(unittest.TestCase):
    def test_cpu_only(self):
        cpu = InferenceTarget('cpu_local', True, 4000)
        self.assertEqual(compatibility(CPU, cpu)[0], 'compatible')
        self.assertEqual(choose_backend(CPU, (cpu,))['selected'], 'cpu_local')
        snapshot = HardwareSnapshot('aarch64', 'Pi 5', 8 << 30, (), False, False, ())
        self.assertFalse(proposal(snapshot)['npu_detected'])

    def test_detected_does_not_mean_initialized(self):
        snapshot = HardwareSnapshot('aarch64', 'Pi 5', 8 << 30,
                                    ('0000:01:00.0',), True, True, (), None)
        plan = proposal(snapshot, pcie_nvme_boot=True)
        self.assertTrue(plan['npu_detected'])
        self.assertFalse(plan['npu_usable'])
        self.assertTrue(plan['pcie_conflict_warning'])
        self.assertIn('USB', plan['storage_alternative'])
        self.assertFalse(plan['installation_performed'])

    def test_npu_verified_allowlist(self):
        target = InferenceTarget('npu_local', True, 8 << 30,
                                 frozenset({'hailo-approved'}))
        self.assertEqual(compatibility(HAILO, target)[0], 'compatible')
        self.assertEqual(compatibility(CPU, target)[0], 'incompatible')
        unchecked = InferenceTarget('npu_local', True, 8 << 30)
        self.assertEqual(compatibility(HAILO, unchecked)[0], 'not_verified')
        with self.assertRaises(ValueError):
            ModelSpec('bad', 'gguf', 3, 'Q4', 22, 4000,
                      {'npu_local': 55}, frozenset({'npu_local'}))

    def test_remote_down_fallback_and_force(self):
        cpu = InferenceTarget('cpu_local', True, 3000)
        remote = InferenceTarget('remote_server', False, 5000)
        route = choose_backend(CPU, (cpu, remote),
                               order=('remote_server', 'cpu_local'))
        self.assertEqual(route['selected'], 'cpu_local')
        self.assertTrue(route['fallback_used'])
        self.assertIsNone(choose_backend(CPU, (cpu, remote),
                                         force='remote_server')['selected'])

    def test_unknown_memory_and_evidence_only_ranking(self):
        unknown = InferenceTarget('cpu_local', True, None)
        self.assertEqual(compatibility(CPU, unknown)[0], 'not_tested')
        cpu = InferenceTarget('cpu_local', True, 3000)
        self.assertEqual(recommendations((CPU,), (cpu,))['fastest']['status'],
                         'Not Tested')
        evidence = {'cpu_local|qwen-cpu': {'tokens_per_second': 5.1}}
        self.assertEqual(recommendations((CPU,), (cpu,), evidence)['fastest']['measured'], 5.1)

    def test_mocked_sysfs_is_not_working_npu_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'proc/device-tree').mkdir(parents=True)
            (root/'proc/device-tree/model').write_text('Raspberry Pi 5')
            (root/'proc/meminfo').write_text('MemTotal: 8000000 kB\n')
            dev = root/'sys/bus/pci/devices/0000:01:00.0'
            dev.mkdir(parents=True)
            (dev/'vendor').write_text('0x1e60')
            snap = inspect_hardware(root=root)
            self.assertEqual(snap.system_ram_bytes, 8000000 * 1024)
            self.assertEqual(snap.hailo_pci_devices, ('0000:01:00.0',))
            self.assertIsNone(snap.hailo_initialized)


if __name__ == '__main__':
    unittest.main()
