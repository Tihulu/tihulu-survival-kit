"""Mock-only benchmark evidence and hardware upgrade invalidation tests."""
import tempfile
import unittest
from pathlib import Path
from tihulu_runtime.ai_benchmarks import (
    BenchmarkLedger, BenchmarkEvidence, hardware_key)
from tihulu_runtime.ai_hardware import HardwareSnapshot


class BenchmarkTests(unittest.TestCase):
    def test_upgrade_invalidates_cached_model_rankings(self):
        old = HardwareSnapshot('aarch64', 'Pi5', 8 << 30, (), True, False, ())
        new = HardwareSnapshot('aarch64', 'Pi5', 8 << 30,
                               ('0000:01:00.0',), True, True, (), True, 8 << 30)
        self.assertNotEqual(hardware_key(old), hardware_key(new))
        with tempfile.TemporaryDirectory() as folder:
            ledger_file = Path(folder)/'benchmark.json'
            ledger = BenchmarkLedger(ledger_file)
            evidence = BenchmarkEvidence(
                'qwen', 'revision-1', 'cpu_local', hardware_key(old),
                '2026-11-05T14:00:00Z', 'local_benchmark',
                {'tokens_per_second': 4.3})
            with self.assertRaises(PermissionError):
                ledger.record(evidence)
            ledger.record(evidence, owner_verified=True)
            reloaded = BenchmarkLedger(ledger_file)
            self.assertIn('cpu_local|qwen', reloaded.evidence_for(
                hardware_key=hardware_key(old),
                model_revisions={'qwen': 'revision-1'}))
            self.assertEqual(reloaded.evidence_for(
                hardware_key=hardware_key(new),
                model_revisions={'qwen': 'revision-1'}), {})
            self.assertEqual(reloaded.evidence_for(
                hardware_key=hardware_key(old),
                model_revisions={'qwen': 'revision-2'}), {})

    def test_invalid_and_imported_metrics_not_silently_used(self):
        key = '0'*64
        with self.assertRaises(ValueError):
            BenchmarkEvidence('m', 'rev', 'cpu_local', key, 'date', 'imported',
                              {'tokens_per_second': float('nan')})
        with self.assertRaises(ValueError):
            BenchmarkEvidence('m', 'rev', 'cpu_local', key, 'date', 'imported',
                              {'turkish_score': 11})
        with tempfile.TemporaryDirectory() as folder:
            ledger = BenchmarkLedger(Path(folder)/'ledger.json')
            row = BenchmarkEvidence('m', 'rev', 'cpu_local', key, 'date',
                                    'imported', {'tokens_per_second': 1.2})
            ledger.record(row, owner_verified=True)
            self.assertEqual(ledger.evidence_for(
                hardware_key=key, model_revisions={'m': 'rev'}), {})
            self.assertEqual(ledger.evidence_for(
                hardware_key=key, model_revisions={'m': 'rev'},
                include_imported=True),
                {'cpu_local|m': {'tokens_per_second': 1.2}})


if __name__ == '__main__':
    unittest.main()
