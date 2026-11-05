"""Owner-authorized model file registry and non-destructive SSD migration.

No formatting, downloads, remounts or implicit source-file deletion.
Use only behind a trusted authenticated owner API with mount/UUID checks.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelLocation:
    model_id: str
    path: str
    sha256: str
    size_bytes: int
    device_uuid: str | None
    state: str = "registered"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


class ModelStorageRegistry:
    """Atomic metadata registry, separated from the model weights themselves."""

    def __init__(self, registry_file: Path | str):
        self.path = Path(registry_file)
        self.models: dict[str, ModelLocation] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf8"))
            if data.get("schema") != 1:
                raise StorageError("Unsupported model registry version")
            self.models = {name: ModelLocation(**row)
                           for name, row in data.get("models", {}).items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".model-registry-")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf8") as stream:
                json.dump({"schema": 1, "models": {key: asdict(value)
                           for key, value in self.models.items()}}, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def register(self, model_id: str, filename: Path | str, *,
                 owner_verified: bool = False, sha256: str | None = None,
                 device_uuid: str | None = None) -> ModelLocation:
        if not owner_verified:
            raise PermissionError("Owner confirmation required")
        if not model_id or model_id in self.models:
            raise StorageError("Missing or already registered model ID")
        path = Path(filename)
        if not regular_file(path):
            raise StorageError("Model must exist as a regular non-symlink file")
        checksum = digest(path)
        if sha256 is not None and checksum.lower() != sha256.lower():
            raise StorageError("Model hash mismatch")
        entry = ModelLocation(model_id, str(path.resolve()), checksum, path.stat().st_size,
                              device_uuid)
        self.models[model_id] = entry
        try:
            self._save()
        except Exception:
            del self.models[model_id]
            raise
        return entry

    def availability(self, model_id: str) -> str:
        entry = self.models[model_id]
        path = Path(entry.path)
        if not regular_file(path):
            return "storage_unavailable"
        if path.stat().st_size != entry.size_bytes:
            return "integrity_unknown"
        return "present_not_reverified"  # Hash must be rechecked before load.

    def verified_path(self, model_id: str) -> Path:
        entry = self.models[model_id]
        path = Path(entry.path)
        if not regular_file(path) or digest(path) != entry.sha256:
            raise StorageError("Model unavailable or checksum failed")
        return path

    def move_model(self, model_id: str, destination_dir: Path | str, *,
                   owner_verified: bool = False) -> ModelLocation:
        """Copy -> fsync -> SHA256 -> register. Original is ALWAYS preserved.

        Target directory must already exist. A future system-level storage
        adapter must also validate UUID and mount-point identity; do not expose
        this method to untrusted browser users or automatically run it on an
        arbitrary path that happens to exist after an SSD is unplugged.
        """
        if not owner_verified:
            raise PermissionError("Owner confirmation required")
        source = self.verified_path(model_id)
        destination_dir = Path(destination_dir)
        if not destination_dir.is_dir() or destination_dir.is_symlink():
            raise StorageError("Target storage not mounted/available")
        destination = destination_dir / source.name
        if destination.exists() or destination.is_symlink():
            raise StorageError("Destination exists: refusing overwrite")
        if destination_dir.resolve() == source.parent.resolve():
            raise StorageError("Same model directory")
        size = source.stat().st_size
        if shutil.disk_usage(destination_dir).free < size + max(16 * 1024 * 1024, size // 100):
            raise StorageError("Insufficient destination space")
        fd, temporary = tempfile.mkstemp(prefix=".model-transfer-", dir=destination_dir)
        original = self.models[model_id]
        try:
            with os.fdopen(fd, "wb") as output, source.open("rb") as input_stream:
                shutil.copyfileobj(input_stream, output, 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            if digest(Path(temporary)) != original.sha256:
                raise StorageError("Migration integrity check failed")
            os.replace(temporary, destination)
            entry = ModelLocation(model_id, str(destination.resolve()), original.sha256,
                                  size, None)
            self.models[model_id] = entry
            try:
                self._save()
            except Exception:
                self.models[model_id] = original
                destination.unlink(missing_ok=True)
                raise
            return entry
        finally:
            Path(temporary).unlink(missing_ok=True)
