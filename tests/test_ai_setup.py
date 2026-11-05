"""Safe read-only Hailo firmware probe tests; no actual hardware."""
import unittest
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


if __name__ == '__main__':
    unittest.main()
