"""Non-destructive disk migration tests: no actual SSD needed."""
import tempfile
import unittest
from pathlib import Path
from tihulu_runtime.ai_model_storage import ModelStorageRegistry, StorageError, digest


class StorageTests(unittest.TestCase):
    def test_register_move_reload_checksum_and_source_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            internal, external = root/'internal', root/'external'
            internal.mkdir()
            external.mkdir()
            source = internal/'model.gguf'
            source.write_bytes(b'GGUF example model bytes')
            db = root/'model-registry.json'
            registry = ModelStorageRegistry(db)
            with self.assertRaises(PermissionError):
                registry.register('qwen', source)
            first = registry.register('qwen', source, owner_verified=True,
                                      sha256=digest(source))
            self.assertEqual(registry.availability('qwen'), 'present_not_reverified')
            with self.assertRaises(PermissionError):
                registry.move_model('qwen', external)
            moved = registry.move_model('qwen', external, owner_verified=True)
            self.assertTrue(source.exists())
            self.assertEqual(moved.sha256, first.sha256)
            self.assertEqual(ModelStorageRegistry(db).verified_path('qwen'),
                             external/'model.gguf')

    def test_missing_disk_never_recreated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_dir = root/'source'
            source_dir.mkdir()
            model = source_dir/'m.gguf'
            model.write_bytes(b'model')
            registry = ModelStorageRegistry(root/'registry.json')
            registry.register('m', model, owner_verified=True)
            with self.assertRaises(StorageError):
                registry.move_model('m', root/'unplugged', owner_verified=True)
            self.assertFalse((root/'unplugged').exists())
            self.assertEqual(registry.verified_path('m'), model)
            model.unlink()
            self.assertEqual(registry.availability('m'), 'storage_unavailable')

    def test_bad_hash_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src_dir, dest = root/'a', root/'b'
            src_dir.mkdir()
            dest.mkdir()
            source = src_dir/'m.gguf'
            source.write_bytes(b'a')
            registry = ModelStorageRegistry(root/'reg.json')
            with self.assertRaises(StorageError):
                registry.register('m', source, owner_verified=True,
                                  sha256='0'*64)
            registry.register('m', source, owner_verified=True)
            (dest/'m.gguf').write_bytes(b'keep me')
            with self.assertRaises(StorageError):
                registry.move_model('m', dest, owner_verified=True)
            self.assertEqual((dest/'m.gguf').read_bytes(), b'keep me')
            source.write_bytes(b'corrupt')
            with self.assertRaises(StorageError):
                registry.verified_path('m')

    def test_symlink_is_not_a_model(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root/'x.gguf'
            real.write_bytes(b'hello')
            link = root/'y.gguf'
            link.symlink_to(real)
            with self.assertRaises(StorageError):
                ModelStorageRegistry(root/'reg.json').register(
                    'x', link, owner_verified=True)


if __name__ == '__main__':
    unittest.main()
