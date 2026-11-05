"""Read-only Linux mount/UUID inventory for external AI model SSDs.

No mounts, unmounts or formatting. Stable UUIDs are distinct from /dev/sda order.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class MountedVolume:
    mountpoint: str
    source: str
    filesystem: str
    uuid: str | None
    read_write: bool
    free_bytes: int
    total_bytes: int


def _unescape(value: str) -> str:
    for escaped, plain in ((r'\040', ' '), (r'\011', '\t'),
                           (r'\012', '\n'), (r'\134', '\\')):
        value = value.replace(escaped, plain)
    return value


def enumerate_volumes(mountinfo: str | Path = '/proc/self/mountinfo',
                      uuid_dir: str | Path = '/dev/disk/by-uuid') -> tuple[MountedVolume, ...]:
    uuids = {}
    directory = Path(uuid_dir)
    if directory.is_dir():
        for link in directory.iterdir():
            if link.is_symlink():
                uuids[os.path.realpath(link)] = link.name
    result = []
    try:
        lines = Path(mountinfo).read_text(encoding='utf8').splitlines()
    except OSError:
        return ()
    for line in lines:
        if ' - ' not in line:
            continue
        left, right = line.split(' - ', 1)
        before, after = left.split(), right.split()
        if len(before) < 6 or len(after) < 2:
            continue
        mountpoint, source, filesystem = (
            _unescape(before[4]), _unescape(after[1]), after[0])
        path = Path(mountpoint)
        if not path.is_dir():
            continue
        try:
            st = os.statvfs(path)
        except OSError:
            continue
        uuid = uuids.get(os.path.realpath(source)) if source.startswith('/dev/') else None
        result.append(MountedVolume(
            mountpoint, source, filesystem, uuid, 'rw' in before[5].split(','),
            st.f_bavail * st.f_frsize, st.f_blocks * st.f_frsize))
    return tuple(result)


def volume_containing(path: Path | str,
                      volumes: tuple[MountedVolume, ...] | None = None) -> MountedVolume | None:
    """Longest mount-point match; a stale unmounted path falls back to root."""
    absolute = Path(path).resolve()
    best = None
    for volume in volumes if volumes is not None else enumerate_volumes():
        if absolute.is_relative_to(Path(volume.mountpoint).resolve()) and (
                best is None or len(volume.mountpoint) > len(best.mountpoint)):
            best = volume
    return best


def require_volume(path: Path | str, uuid: str, *,
                   volumes: tuple[MountedVolume, ...] | None = None,
                   writable: bool = True) -> MountedVolume:
    volume = volume_containing(path, volumes)
    if not uuid or volume is None or volume.uuid != uuid or (writable and not volume.read_write):
        raise ValueError('Expected writable UUID-mounted SSD unavailable or changed')
    return volume
