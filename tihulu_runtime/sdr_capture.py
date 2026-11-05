# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 8 SDR cooperating-process lock + Stage 4 foreground FM lease.

Internal trusted-library prototype, not an authenticated API or Pi daemon.
flock coordinates ONLY processes using this same lock directory and exact
receiver key. It does NOT prevent unrelated Gqrx/welle.io/rtl_test processes
from opening the USB device. No automatic/background capture is started.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
import fcntl
import hashlib
import os
import re
import stat

from .channel_explorer import Receiver
from .sdr_radio import RtlFmStream, SdrBusy, fm_command
from .service_manager import ServiceManager


def default_lock_root() -> Path:
    """Use the authenticated service account's runtime directory, fail closed."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "tihulu-sdr"
    return Path("/run/user") / str(os.getuid()) / "tihulu-sdr"


class SdrCooperativeLock:
    """Per-receiver non-blocking Linux advisory lock for Tihulu workers.

    No unlinks: deleting live flock files can split ownership across inodes.
    Private directory and no-follow opens reject lock-file symlink attacks.
    Keep this object alive until the trusted receiver worker fully stops.
    """

    def __init__(self, receiver_id: str, *, root: str | Path | None = None):
        if not isinstance(receiver_id, str) or not re.fullmatch(
                r"[A-Za-z0-9:._-]{1,128}", receiver_id, flags=re.ASCII):
            raise ValueError("Canonical receiver ID required; no paths or serial secrets")
        self.receiver_id = receiver_id
        self.root = Path(root) if root is not None else default_lock_root()
        self._fd: int | None = None
        self._gate = RLock()

    @property
    def lock_name(self) -> str:
        # Stable across processes, opaque in shared operational diagnostics.
        return hashlib.sha256(self.receiver_id.encode("ascii")).hexdigest() + ".lock"

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> None:
        with self._gate:
            if self._fd is not None:
                raise SdrBusy("This coordinator already holds the receiver lock")
            try:
                self.root.mkdir(mode=0o700)
            except FileExistsError:
                pass
            # O_DIRECTORY | O_NOFOLLOW verifies the final directory component.
            directory_fd = os.open(
                self.root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            fd = None
            try:
                directory = os.fstat(directory_fd)
                if (not stat.S_ISDIR(directory.st_mode)
                        or directory.st_uid != os.geteuid()
                        or stat.S_IMODE(directory.st_mode) != 0o700):
                    raise PermissionError("SDR lock directory must be private and owned")
                fd = os.open(
                    self.lock_name,
                    os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=directory_fd)
                metadata = os.fstat(fd)
                if (not stat.S_ISREG(metadata.st_mode)
                        or metadata.st_uid != os.geteuid()
                        or metadata.st_nlink != 1
                        or stat.S_IMODE(metadata.st_mode) != 0o600):
                    raise PermissionError("SDR lock file owner/type/mode invalid")
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise SdrBusy("Receiver already owned by a cooperating process") from exc
                self._fd = fd
                fd = None
            finally:
                if fd is not None:
                    os.close(fd)
                os.close(directory_fd)

    def release(self) -> None:
        with self._gate:
            fd = self._fd
            if fd is None:
                return
            self._fd = None
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def __enter__(self) -> "SdrCooperativeLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@dataclass(frozen=True)
class _Active:
    owner_id: str
    job_id: str
    receiver_id: str


class ManagedFmCapture:
    """Connect Stage4 foreground lease, cooperative OS lock, and FM worker.

    Owner authentication and device-index->USB identity are enforced by the
    future trusted gateway. This object MUST NOT accept arbitrary LAN inputs.
    The service adapter may start a module policy unit, not a public server.
    """

    def __init__(self, services: ServiceManager, stream: RtlFmStream, *,
                 lock_root: str | Path | None = None, service_id: str = "radio"):
        if service_id != "radio":
            raise ValueError("Only known Stage4 radio service is supported")
        self.services = services
        self.stream = stream
        self.lock_root = lock_root
        self.service_id = service_id
        self._gate = RLock()
        self._active: _Active | None = None
        self._device_lock: SdrCooperativeLock | None = None

    def start(self, receiver: Receiver, *, frequency_hz: int,
              owner_id: str, job_id: str, device_index: int,
              ppm: int = 0, gain_db: float | None = None,
              grant_token: str | None = None) -> None:
        """Always explicit foreground. No background/Startup auto wake."""
        if not owner_id or not job_id:
            raise PermissionError("Authenticated owner and server job required")
        if receiver.kind != "radio_sdr" or not receiver.receiver_id:
            raise ValueError("A verified SDR receiver is required")
        # Validate the requested tune BEFORE consuming an optional lease.
        fm_command(frequency_hz=frequency_hz, device_index=device_index,
                   ppm=ppm, gain_db=gain_db)
        with self._gate:
            if self._active is not None:
                raise SdrBusy("This managed worker already owns a capture")
            # Stage4 enforces installed/hard/background/startup policy and
            # any one-time owner grant; this is never a background request.
            self.services.acquire(self.service_id, task_id=job_id,
                                  owner_id=owner_id, mode="foreground",
                                  grant_token=grant_token)
            device_lock = SdrCooperativeLock(receiver.receiver_id,
                                             root=self.lock_root)
            try:
                device_lock.acquire()
                self.stream.start(receiver, frequency_hz=frequency_hz,
                                  owner_id=owner_id, job_id=job_id,
                                  device_index=device_index,
                                  ppm=ppm, gain_db=gain_db)
            except BaseException:
                device_lock.release()
                self.services.release(job_id, owner_id=owner_id)
                self.services.sweep_idle()
                raise
            self._device_lock = device_lock
            self._active = _Active(owner_id, job_id, receiver.receiver_id)

    def stop(self, *, owner_id: str, job_id: str,
             recording_stop_confirmed: bool = False) -> None:
        with self._gate:
            active = self._active
            if active is None:
                return
            if (owner_id, job_id) != (active.owner_id, active.job_id):
                raise PermissionError("Only the original trusted owner/job may stop capture")
            # Streaming worker enforces recorder ACK and listener gates
            # BEFORE terminating process; on denial retain BOTH leases.
            self.stream.stop(recording_stop_confirmed=recording_stop_confirmed)
            self.services.release(job_id, owner_id=owner_id)
            self._device_lock.release()
            self._active = None
            self._device_lock = None
            self.services.sweep_idle()

    def read_pcm(self, max_bytes: int = 8192) -> bytes:
        with self._gate:
            if self._active is None:
                raise RuntimeError("No managed FM stream")
            return self.stream.read_pcm(max_bytes)

    def snapshot(self) -> dict:
        with self._gate:
            return {
                "state": "active_not_rf_verified" if self._active else "idle",
                "cooperative_device_lock_held": bool(self._device_lock
                                                     and self._device_lock.held),
                "service_id": self.service_id,
                "background_scan_enabled": False,
                "actual_usb_hardware_exclusivity_verified": False,
            }
