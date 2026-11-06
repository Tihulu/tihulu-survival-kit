# SPDX-License-Identifier: AGPL-3.0-only
"""Linux cross-process receiver reservations for cooperating Tihulu services.

flock is an advisory *cross-process* exclusion primitive, NOT a USB hardware
firewall: non-cooperating Gqrx/readsb/welle.io/etc may ignore it. Fail closed
unless a privileged external-use audit is supplied. Every trusted tuner-owning
Kit service must adopt the SAME lock directory and exact physical-device ID.
Never retune, kill, suspend or open a tuner in this module.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

from .sdr_resource_broker import ReceiverBusy

_RECEIVER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")


class SDRGuardUnavailable(RuntimeError):
    """Cross-process RF ownership cannot be confirmed; deny tuning."""


class LinuxProcUSBUseAudit:
    """Conservative read-only /proc/fd check of *known* USB receiver nodes.

    This is only a secondary safety check. It cannot close the race with
    external programs opening a USB device after the scan. Deploy the guard
    in a privileged, single RF supervisor and require other Kit RF services
    to honor the same advisory device lock. If /proc permission or the mapping
    is uncertain, block RF rather than assuming the tuner is free.
    """

    def __init__(self, device_nodes: dict[str, str],
                 *, proc_root: str | Path = "/proc"):
        if not isinstance(device_nodes, dict) or not device_nodes:
            raise ValueError("Verified USB device-node mapping required")
        self.device_nodes = dict(device_nodes)
        self.proc_root = Path(proc_root)

    def __call__(self, receiver_id: str) -> None:
        if receiver_id not in self.device_nodes:
            raise SDRGuardUnavailable("Receiver has no verified USB device mapping")
        node = Path(self.device_nodes[receiver_id])
        try:
            # Canonical USB bus node, NOT /dev/dvb, a symlink to another device
            # or a user-supplied arbitrary path.
            if not str(node).startswith("/dev/bus/usb/"):
                raise SDRGuardUnavailable("Only verified USB bus nodes are supported")
            real = node.resolve(strict=True)
            if not str(real).startswith("/dev/bus/usb/"):
                raise SDRGuardUnavailable("USB node resolves outside bus devices")
            info = real.stat()
            if not stat.S_ISCHR(info.st_mode):
                raise SDRGuardUnavailable("Receiver USB node is not a character device")
            for proc in self.proc_root.iterdir():
                if not proc.name.isdecimal():
                    continue
                try:
                    fd_dir = proc / "fd"
                    for fd in fd_dir.iterdir():
                        try:
                            link = os.readlink(fd)
                        except (FileNotFoundError, ProcessLookupError):
                            continue
                        except (PermissionError, OSError) as exc:
                            raise SDRGuardUnavailable(
                                "Cannot verify external USB device users") from exc
                        # Deleted device nodes and other paths are conservatively
                        # handled by the privileged operator during recovery.
                        if link == str(real) or link == str(real) + " (deleted)":
                            raise ReceiverBusy(receiver_id, "external USB process")
                except (FileNotFoundError, ProcessLookupError):
                    continue
                except PermissionError as exc:
                    raise SDRGuardUnavailable(
                        "Cannot examine all receiver processes; use privileged broker") from exc
            return True
        except (PermissionError, FileNotFoundError, OSError) as exc:
            raise SDRGuardUnavailable("Cannot inspect USB device or process state") from exc


class ReceiverReservation:
    """Keep lock FD open until decoder confirms STOP. Release is idempotent."""

    def __init__(self, fd: int):
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class LinuxFlockSDRGuard:
    """Real Linux inter-process lock requiring trusted receiver-busy audit.

    The deployment service must create the shared lock directory on persistent
    /run/lock or /run with private, consistent ownership. The same exact
    receiver ID must be used by all its cooperating decoder processes.
    An audit is mandatory: advisory flock alone is not sufficient to call
    a non-cooperating third-party USB tuner free.
    """

    def __init__(self, lock_dir: str | Path, *, external_use_audit=None):
        if sys.platform != "linux":
            raise SDRGuardUnavailable("Linux-only RF lock backend")
        if not callable(external_use_audit):
            raise SDRGuardUnavailable(
                "Verified external USB process audit is mandatory")
        self.lock_dir = Path(lock_dir)
        if not self.lock_dir.is_absolute():
            raise ValueError("Shared lock directory must be an absolute path")
        self.external_use_audit = external_use_audit

    def reserve(self, receiver_id: str, purpose: str) -> ReceiverReservation:
        if (not isinstance(receiver_id, str)
                or not _RECEIVER_ID.fullmatch(receiver_id)):
            raise ValueError("Use a stable trusted physical receiver ID")
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("Nonempty RF purpose required")
        try:
            self.lock_dir.mkdir(mode=0o700, parents=False, exist_ok=True)
            root_stat = self.lock_dir.lstat()
            if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_mode & 0o077:
                raise SDRGuardUnavailable(
                    "Shared lock directory must be private, not a symlink")
            # Stable mapping, not arbitrary filename supplied from a browser.
            digest = hashlib.sha256(receiver_id.encode("ascii")).hexdigest()
            filename = self.lock_dir / (digest + ".lock")
            flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
            if not hasattr(os, "O_NOFOLLOW"):
                raise SDRGuardUnavailable("Symlink-safe open is unavailable")
            fd = os.open(filename, flags | os.O_NOFOLLOW, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise SDRGuardUnavailable("Unsafe receiver-lock file")
                if info.st_mode & 0o077:
                    raise SDRGuardUnavailable("Receiver-lock permissions too open")
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ReceiverBusy(receiver_id, "another receiver process") from exc
                # Race-aware audit while the cooperating process lock is held.
                # Errors always block, never treat an uncertain USB as free.
                if self.external_use_audit(receiver_id) is not True:
                    raise SDRGuardUnavailable("External USB usage audit did not certify idle")
                return ReceiverReservation(fd)
            except BaseException:
                os.close(fd)
                raise
        except (PermissionError, FileNotFoundError) as exc:
            raise SDRGuardUnavailable(
                "Receiver lock directory is inaccessible") from exc
