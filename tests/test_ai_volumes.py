"""Read-only mocked mount/UUID tests; no physical SSD."""
import tempfile
import unittest
from pathlib import Path
from tihulu_runtime.ai_volumes import (
    MountedVolume, enumerate_volumes, require_volume, volume_containing)


class VolumeTests(unittest.TestCase):
    def test_fixture_mountinfo_parse_without_fake_uuid(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            disk = root/'media/AI Drive'
            disk.mkdir(parents=True)
            mountinfo = root/'mountinfo'
            encoded = str(disk).replace(' ', '\\040')
            mountinfo.write_text(
                '31 1 0:31 / / rw - overlay overlay rw\n'
                + f'32 31 8:1 / {encoded} rw - ext4 /tmp/fake-dev rw\n')
            found = enumerate_volumes(mountinfo, root/'uuid')
            self.assertEqual(volume_containing(disk/'models', found).filesystem, 'ext4')
            self.assertIsNone(volume_containing(disk/'models', found).uuid)

    def test_disconnected_ssd_does_not_match_root_mount(self):
        root = MountedVolume('/', '/dev/sda2', 'ext4', 'ROOT', True, 500, 1000)
        external = MountedVolume('/media/ai', '/dev/sdb1', 'ext4',
                                 'SSD-123', True, 700, 1000)
        self.assertEqual(require_volume('/media/ai/models', 'SSD-123',
                                        volumes=(root, external)), external)
        with self.assertRaises(ValueError):
            require_volume('/media/ai/models', 'SSD-123', volumes=(root,))
        with self.assertRaises(ValueError):
            require_volume('/media/ai/models', 'WRONG',
                           volumes=(root, external))


if __name__ == '__main__':
    unittest.main()
