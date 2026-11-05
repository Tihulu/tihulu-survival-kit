"""CPU inference smoke: mock executor and fake local CLI only, never a real model."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from tihulu_runtime.ai_cpu_smoke import MARKER, cpu_smoke_test


class FakeRegistry:
    def __init__(self, model_file):
        self.path = model_file
        self.models = {'base': SimpleNamespace(sha256=hashlib.sha256(model_file.read_bytes()).hexdigest())}
        self.calls = 0

    def verified_path(self, model_id):
        self.calls += 1
        if model_id != 'base':
            raise KeyError(model_id)
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != self.models[model_id].sha256:
            raise ValueError('Hash mismatch')
        return self.path


class CpuSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / 'base.gguf'
        self.model.write_bytes(b'GGUF' + b'placeholder')
        self.registry = FakeRegistry(self.model)
        self.runner = self.root / 'llama-cli'
        self.runner.write_bytes(b'#!/bin/sh\nexit 0\n')
        self.runner.chmod(0o700)

    def kwargs(self):
        return dict(explicit_owner_consent=True, service_allowed=True,
                    resource_budget_allowed=True, runner=self.runner)

    def mock_subprocess(self, generated=MARKER, returncode=0):
        return patch('tihulu_runtime.ai_cpu_smoke.subprocess.run',
                     side_effect=[SimpleNamespace(returncode=0, stdout='llama.cpp build 1', stderr=''),
                                  SimpleNamespace(returncode=returncode, stdout=generated, stderr='')])

    def test_default_no_consent_does_not_open_file_or_launch(self):
        with patch('tihulu_runtime.ai_cpu_smoke.subprocess.run') as mock:
            out = cpu_smoke_test(self.registry, 'base')
        self.assertEqual(out.status, 'owner_consent_required')
        self.assertEqual(self.registry.calls, 0)
        mock.assert_not_called()

    def test_service_hard_off(self):
        out = cpu_smoke_test(self.registry, 'base', explicit_owner_consent=True)
        self.assertEqual(out.status, 'service_disabled')
        self.assertEqual(self.registry.calls, 0)

    def test_resource_budget_explicit_gate(self):
        out = cpu_smoke_test(self.registry, 'base', explicit_owner_consent=True, service_allowed=True)
        self.assertEqual(out.status, 'resource_budget_not_approved')

    def test_limit_guard(self):
        for vals in ({'timeout_seconds':999}, {'threads':9}, {'predict_tokens':0},
                     {'threads':True}, {'timeout_seconds':0}):
            out = cpu_smoke_test(self.registry,'base',**self.kwargs(),**vals)
            self.assertEqual(out.status,'unsafe_limits')

    def test_missing_model_denied(self):
        out = cpu_smoke_test(self.registry,'fake',**self.kwargs())
        self.assertEqual(out.status,'unregistered_model')

    def test_invalid_digest_denied(self):
        self.registry.models['base'].sha256 = 'not-a-digest'
        out = cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'untrusted_model_digest')

    def test_changed_model_bytes_fail_sha(self):
        self.model.write_bytes(b'GGUFtampered')
        out = cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'model_unavailable')

    def test_non_gguf_fail_closed(self):
        self.model.write_bytes(b'ABCDnotgguf')
        self.registry = FakeRegistry(self.model)
        out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'not_gguf')

    def test_no_runner(self):
        out=cpu_smoke_test(self.registry,'base',**dict(self.kwargs(),runner='/tmp/untrusted.sh'))
        self.assertEqual(out.status,'cpu_runner_unavailable')

    def test_missing_version_fail_closed(self):
        with patch('tihulu_runtime.ai_cpu_smoke.subprocess.run',
                   return_value=SimpleNamespace(returncode=1,stdout='',stderr='error')):
            out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'runner_version_unavailable')

    def test_smoke_pass_records_only_marker_flag_and_no_text(self):
        with self.mock_subprocess() as run:
            out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'marker_observed')
        self.assertTrue(out.passed)
        self.assertTrue(out.marker_observed)
        self.assertFalse(out.cloud_used)
        self.assertFalse(out.output_saved)
        self.assertFalse(out.physical_swap_approved)
        self.assertTrue(out.current_boot_only)
        self.assertEqual(out.model_sha256,self.registry.models['base'].sha256)
        self.assertEqual(len(run.call_args_list),2)
        argv=run.call_args_list[1].args[0]
        self.assertIn('--n-gpu-layers',argv)
        self.assertEqual(argv[argv.index('--n-gpu-layers')+1],'0')
        self.assertIn('--no-kv-offload',argv)
        self.assertIn('--no-op-offload',argv)
        self.assertNotIn('--model-url',argv)
        self.assertNotIn('--hf-repo',argv)
        self.assertEqual(run.call_args_list[1].kwargs['env'].get('HF_TOKEN'),None)
        self.assertFalse(run.call_args_list[1].kwargs.get('shell',False))
        self.assertNotIn('stdout',out.as_dict())

    def test_runner_generates_empty_output(self):
        with self.mock_subprocess(generated=''):
            out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'generation_unverified')
        self.assertFalse(out.passed)

    def test_runner_generates_other_text_not_auto_pass(self):
        with self.mock_subprocess(generated='This is only a banner'):
            out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'generation_unverified')

    def test_nonzero_exit_fails_even_with_marker(self):
        with self.mock_subprocess(returncode=1):
            out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'runner_failed')

    def test_inference_timeout(self):
        with patch('tihulu_runtime.ai_cpu_smoke.subprocess.run',
                   side_effect=[SimpleNamespace(returncode=0,stdout='v1',stderr=''),
                                subprocess.TimeoutExpired(['llama-cli'],1)]):
            out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'timed_out')

    def test_real_fake_executable_subprocess_path_no_model_load(self):
        # Harmless local stand-in, NOT a llama.cpp model.
        self.runner.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo fake-build; else echo TIHULU_CPU_OK; fi\n')
        self.runner.chmod(0o700)
        out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertTrue(out.passed)
        self.assertEqual(out.runner_version,'fake-build')
        self.assertFalse(out.physical_swap_approved)

    def test_version_timeout(self):
        with patch('tihulu_runtime.ai_cpu_smoke.subprocess.run',
                   side_effect=subprocess.TimeoutExpired(['llama-cli','--version'],1)):
            out=cpu_smoke_test(self.registry,'base',**self.kwargs())
        self.assertEqual(out.status,'runner_version_unavailable')


if __name__ == '__main__':
    unittest.main()
