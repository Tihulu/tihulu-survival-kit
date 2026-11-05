# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental receive-only RTL-SDR inventory, tuning policy and FM stream.

This is a trusted INTERNAL Python library, not an authenticated HTTP API or a
deployed Raspberry Pi service. USB identity does not prove an installed
decoder, usable antenna, live signal, device index, or NESDR model revision.
No background polling, scan, recording, or network listener is started.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Callable
import re
import shutil
import subprocess

from .channel_explorer import Receiver, TunePoint

RTL_USB_IDS = frozenset({("0bda", "2838")})
FM_MIN_HZ, FM_MAX_HZ = 87_500_000, 108_000_000


class SdrBusy(RuntimeError):
    """An incompatible frequency, mode or protected task owns the tuner."""


@dataclass(frozen=True)
class UsbSdr:
    usb_path: str
    vendor_id: str
    product_id: str
    manufacturer: str
    product: str
    # USB VID/PID identifies a compatible RTL chipset, NOT the Nooelec brand.
    identity_confidence: str = "rtl2832u_compatible_usb_id_only"


def discover_usb_sdr(root: str | Path = "/sys/bus/usb/devices") -> tuple[UsbSdr, ...]:
    """Read sysfs metadata only; never open SDR, run rtl_test or claim reception."""
    root = Path(root)
    found: list[UsbSdr] = []
    if not root.is_dir():
        return ()
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir():
            continue
        try:
            vid = (candidate / "idVendor").read_text(encoding="ascii").strip().lower()
            pid = (candidate / "idProduct").read_text(encoding="ascii").strip().lower()
        except (OSError, UnicodeError):
            continue
        if (vid, pid) not in RTL_USB_IDS:
            continue

        def safe_text(name: str) -> str:
            try:
                value = (candidate / name).read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                return ""
            # Do not output arbitrary unbounded USB descriptor strings.
            return "".join(c for c in value[:120] if c.isprintable())

        found.append(UsbSdr(candidate.name, vid, pid,
                            safe_text("manufacturer"), safe_text("product")))
    return tuple(found)


def setup_inventory(root: str | Path = "/sys/bus/usb/devices",
                    which: Callable[[str], str | None] = shutil.which) -> dict:
    """Setup Wizard read-only inventory; never implies an on-Pi reception test."""
    devices = discover_usb_sdr(root)
    backend = {"fm_rtl_fm": bool(which("rtl_fm")),
               "dab_welle_cli": bool(which("welle-cli"))}
    return {
        "schema_version": 1,
        "receiver_type": "radio_sdr",
        "usb_devices": [vars(device) for device in devices],
        "usb_present": bool(devices),
        "backend_executables": backend,
        "background_scanning": False,
        "auto_open_receiver": False,
        "reported_status": "usb_detected_not_rf_validated" if devices else "not_detected",
        "model_confirmation_required": True,
        "pi_rf_reception_verified": False,
        "dvb_t2_hd_supported_by_this_receiver": False,
        "separate_tv_tuner_required": True,
    }


def receiver_candidate(device: UsbSdr, *, verified_modes: frozenset[str],
                       verified_min_hz: int = 25_000_000,
                       verified_max_hz: int = 1_750_000_000) -> Receiver:
    """Convert ONLY trusted adapter-verified capabilities to shared API shape.

    USB VID/PID alone never authorizes 'fm', 'dab', or HF direct sampling.
    Backend/version/host-specific verification is the caller's responsibility.
    """
    if not verified_modes or not verified_modes.issubset({
        "fm", "dab", "am", "nfm", "hf", "usb", "lsb"
    }):
        raise ValueError("Modes must be explicitly verified by trusted adapter")
    if not (100_000 <= verified_min_hz < verified_max_hz <= 1_750_000_000):
        raise ValueError("Invalid verified RF range")
    return Receiver("usb-sdr:" + device.usb_path, "radio_sdr",
                    verified_modes, verified_min_hz, verified_max_hz,
                    connected=True, fine_tune_supported=True)


@dataclass
class _Capture:
    receiver_id: str
    owner_id: str
    job_id: str
    point: TunePoint
    recording: bool = False
    share_ready: bool = False
    listeners: dict[str, str] = field(default_factory=dict)


class SdrTunerBroker:
    """In-process reservation for ONE RF center/mode at a time.

    A reservation is not a physical USB lock. The authenticated service and
    process supervisor must connect this to exclusive OS device ownership.
    """
    def __init__(self):
        self._mutex = RLock()
        self._captures: dict[str, _Capture] = {}

    def reserve(self, receiver: Receiver, point: TunePoint, *,
                owner_id: str, job_id: str) -> None:
        if not owner_id or not job_id:
            raise PermissionError("Trusted owner and server job IDs required")
        if receiver.kind != "radio_sdr" or not receiver.supports(
                point.mode, point.tuned_hz):
            raise ValueError("Unavailable or incompatible radio SDR")
        if point.mode not in {"fm", "dab", "am", "hf", "nfm", "usb", "lsb"}:
            raise ValueError("DVB tuner modes cannot reserve SDR")
        with self._mutex:
            if receiver.receiver_id in self._captures:
                raise SdrBusy("Tuner reserved; join an existing authorized stream")
            self._captures[receiver.receiver_id] = _Capture(
                receiver.receiver_id, owner_id, job_id, point)

    def mark_recording(self, receiver_id: str, *, owner_id: str,
                       job_id: str, active: bool) -> None:
        with self._mutex:
            cap = self._owned(receiver_id, owner_id, job_id)
            cap.recording = bool(active)

    def mark_shared_stream_ready(self, receiver_id: str, *, owner_id: str,
                                 job_id: str, ready: bool) -> None:
        """Only trusted, actually-running media fanout may set ready=True."""
        with self._mutex:
            cap = self._owned(receiver_id, owner_id, job_id)
            cap.share_ready = bool(ready)

    def join(self, receiver_id: str, point: TunePoint, *,
             listener_id: str, owner_id: str) -> None:
        if not owner_id or not listener_id:
            raise PermissionError("Authenticated listener required")
        with self._mutex:
            cap = self._captures.get(receiver_id)
            if not cap or not cap.share_ready or cap.point != point:
                raise SdrBusy("No verified shared stream at exact tuned point")
            if listener_id in cap.listeners:
                raise SdrBusy("Duplicate listener session")
            cap.listeners[listener_id] = owner_id

    def leave(self, receiver_id: str, *, listener_id: str, owner_id: str) -> None:
        with self._mutex:
            cap = self._captures[receiver_id]
            if cap.listeners.get(listener_id) != owner_id:
                raise PermissionError("Not listener owner")
            del cap.listeners[listener_id]

    def release_after(self, receiver_id: str, *, owner_id: str, job_id: str,
                      stop_worker: Callable[[], None],
                      recording_stop_confirmed: bool = False) -> None:
        """Keep the reservation locked through worker termination.

        An acknowledged recorder flush is the trusted caller's prerequisite
        for recording_stop_confirmed=True. Never kill worker before the gate.
        """
        with self._mutex:
            cap = self._owned(receiver_id, owner_id, job_id)
            if cap.recording and not recording_stop_confirmed:
                raise SdrBusy("Protected recording: explicit safe stop required")
            if cap.listeners:
                raise SdrBusy("Shared listeners still attached")
            stop_worker()
            del self._captures[receiver_id]

    def release(self, receiver_id: str, *, owner_id: str, job_id: str,
                recording_stop_confirmed: bool = False) -> None:
        self.release_after(receiver_id, owner_id=owner_id, job_id=job_id,
                           stop_worker=lambda: None,
                           recording_stop_confirmed=recording_stop_confirmed)

    def snapshot(self, receiver_id: str) -> dict:
        with self._mutex:
            cap = self._captures.get(receiver_id)
            if cap is None:
                return {"state": "idle", "listeners": 0}
            return {"state": "reserved_not_signal_verified",
                    "mode": cap.point.mode, "frequency_hz": cap.point.tuned_hz,
                    "recording": cap.recording, "listeners": len(cap.listeners)}

    def _owned(self, receiver_id: str, owner_id: str, job_id: str) -> _Capture:
        cap = self._captures[receiver_id]
        if (cap.owner_id, cap.job_id) != (owner_id, job_id):
            raise PermissionError("Only the capture owner/job may change tuner")
        return cap


def fm_command(*, frequency_hz: int, device_index: int = 0,
               ppm: int = 0, gain_db: float | None = None,
               binary: str = "rtl_fm") -> list[str]:
    """Safe argv for mono 32kHz signed 16-bit PCM from broadcast WBFM.

    RDS is NOT decoded by rtl_fm and is NOT claimed by this adapter.
    """
    if not (type(frequency_hz) is int and FM_MIN_HZ <= frequency_hz <= FM_MAX_HZ):
        raise ValueError("Out-of-band FM frequency")
    if type(device_index) is not int or not 0 <= device_index <= 15:
        raise ValueError("Invalid device index; it must be explicitly selected")
    if type(ppm) is not int or not -1000 <= ppm <= 1000:
        raise ValueError("Invalid PPM correction")
    if gain_db is not None and not (
            isinstance(gain_db, (float, int)) and
            not isinstance(gain_db, bool) and 0 <= gain_db <= 49.6):
        raise ValueError("Gain must be within a conservative 0..49.6 dB range")
    if binary != "rtl_fm":
        raise ValueError("Only allowlisted rtl_fm executable supported")
    cmd = [binary, "-d", str(device_index), "-f", str(frequency_hz),
           "-M", "wbfm", "-s", "170k", "-o", "4", "-A", "fast",
           "-r", "32k", "-l", "0", "-E", "deemp", "-p", str(ppm)]
    if gain_db is not None:
        cmd += ["-g", str(gain_db)]
    return cmd + ["-"]


class RtlFmStream:
    """Actual optional process adapter; returns RAW PCM, not web audio.

    Requires a caller-managed trusted service lease, authorized player/recorder,
    and verified rtl-sdr device-index mapping. Does not auto-start or scan.
    No real reception is claimed until the consumer verifies the output.
    """
    def __init__(self, broker: SdrTunerBroker, *,
                 which: Callable[[str], str | None] = shutil.which,
                 popen: Callable = subprocess.Popen):
        self.broker = broker
        self.which = which
        self.popen = popen
        self._process = None
        self._binding: tuple[str, str, str] | None = None

    def start(self, receiver: Receiver, *, frequency_hz: int,
              owner_id: str, job_id: str, device_index: int = 0,
              ppm: int = 0, gain_db: float | None = None) -> None:
        if self._process is not None:
            raise SdrBusy("Stream already started")
        cmd = fm_command(frequency_hz=frequency_hz, device_index=device_index,
                         ppm=ppm, gain_db=gain_db)
        exe = self.which("rtl_fm")
        if not exe:
            raise FileNotFoundError("rtl_fm is not installed")
        point = TunePoint("fm", frequency_hz)
        self.broker.reserve(receiver, point, owner_id=owner_id, job_id=job_id)
        try:
            self._process = self.popen(
                [exe, *cmd[1:]], shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                close_fds=True)
            if self._process.stdout is None:
                raise RuntimeError("Missing PCM pipe")
            self._binding = receiver.receiver_id, owner_id, job_id
        except BaseException:
            if self._process is not None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=2)
                except Exception:
                    pass
                self._process = None
            self.broker.release(receiver.receiver_id,
                                owner_id=owner_id, job_id=job_id)
            raise

    def read_pcm(self, max_bytes: int = 8192) -> bytes:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("FM stream not started")
        if not 1 <= max_bytes <= 65536:
            raise ValueError("Invalid bounded PCM read")
        data = self._process.stdout.read(max_bytes)
        if not data and self._process.poll() is not None:
            raise RuntimeError("rtl_fm exited; SDR may be busy or unavailable")
        return data

    def stop(self, *, recording_stop_confirmed: bool = False) -> None:
        """Stop only after recording and listener gates pass atomically.

        The recorder must flush and acknowledge its original master BEFORE
        a trusted caller supplies recording_stop_confirmed=True. This class
        cannot itself validate a filesystem/durable recording ACK.
        """
        if self._process is None:
            return
        process, binding = self._process, self._binding
        if binding is None:
            raise RuntimeError("Missing trusted stream-to-reservation binding")

        def stop_worker() -> None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            if process.stdout is not None:
                process.stdout.close()

        rid, owner, job = binding
        # Broker checks recording/listener protection while holding its lock
        # before invoking stop_worker. No process termination on denied stop.
        self.broker.release_after(
            rid, owner_id=owner, job_id=job, stop_worker=stop_worker,
            recording_stop_confirmed=recording_stop_confirmed)
        self._process = None
        self._binding = None


if __name__ == "__main__":
    import json
    print(json.dumps(setup_inventory(), ensure_ascii=False, indent=2))
