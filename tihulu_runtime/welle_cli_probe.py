# SPDX-License-Identifier: AGPL-3.0-only
"""Receive-only, NO-HTTP welle-cli DAB scan probe for trusted Linux workers.

Uses the upstream welle-cli documented -c/-F/-p/-T flags. Unlike -w, this
does NOT open a web port (upstream -w binds INADDR_ANY). One invocation per
channel, bounded by time and bounded captured logs. Stdin supplies '.' to
quit after the service list; a deliberately impossible programme selector
forces welle-cli to print metadata WITHOUT playing or recording audio.

This is an internal adapter, not a published network endpoint. A host
hardware gate must verify that upstream's "first working rtl_sdr" is the
exact intended USB receiver before the process is started. No gate = OFF.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
import os
import re
import selectors
import shutil
import signal
import subprocess
import time

from .channel_explorer import (
    DetectedService, FrequencyLibrary, ProbeReading, Receiver, TunePoint,
)

MAX_CAPTURE_BYTES = 131_072
MAX_LABEL_LENGTH = 96
# The DAB programme name cannot contain this long, fixed selector, so it
# cannot trigger unintended ALSA playback when listing real services.
UNPLAYABLE_SERVICE_NAME = "TIHULU_SCAN_DO_NOT_PLAY_ANY_RADIO_SERVICE_0123456789"
SERVICE_LINE = re.compile(
    r"^\s*\[0x([0-9a-fA-F]{1,8})\]\s+(.+?)(?:\s+\[component\b|$)")
DAB_SERVICE_ID = re.compile(r"^0x[0-9a-fA-F]{1,8}$")


class WelleCliProbeError(RuntimeError):
    """No supported local welle-cli, verified device or bounded decoder run."""


def dab_channel_map(library: FrequencyLibrary) -> dict[int, str]:
    """Only published discrete Band III channel centers, no inferred sweep."""
    core = library.channel_group_points("dab_band_iii")
    extension = library.channel_group_points("dab_band_iii_ext_13")
    if len(core) != 32 or len(extension) != 6:
        raise ValueError("Expected exact 32+6 DAB Band III block centers")
    channels = [f"{i}{letter}" for i in range(5, 13) for letter in "ABCD"]
    channels.extend(f"13{letter}" for letter in "ABCDEF")
    points = (*core, *extension)
    if any(p.mode != "dab" for p in points):
        raise ValueError("DAB raster contains wrong mode")
    freqs = [p.frequency_hz for p in points]
    if (len(set(freqs)) != len(freqs) or
            any(not 174_000_000 <= f <= 240_000_000 for f in freqs) or
            freqs != sorted(freqs)):
        raise ValueError("Invalid or non-monotonic DAB raster")
    return dict(zip(freqs, channels))


def interpret_welle_cli_log(log: bytes, *, timed_out: bool,
                            returncode: int | None) -> ProbeReading:
    """Promote to service_decoded ONLY when welle-cli printed labelled IDs.

    'New Service: 0x...' on its own does not prove the service label or
    playable audio. No RF measurements are invented; signal_quality=None.
    """
    text = log.decode("utf-8", errors="replace")
    if any(marker in text for marker in (
        "Could not start device", "Opening rtl-sdr failed",
        "No devices found", "Could not start device", "Could not initialise",
    )):
        raise WelleCliProbeError("RTL-SDR backend unavailable or USB busy")
    if returncode not in (0, None):
        raise WelleCliProbeError("welle-cli exited with a decoder/device error")

    # welle-cli writes the human-readable Service list to stderr in its
    # non-web ALSA-enabled code path. Never infer service names from the
    # published frequencies, arbitrary log lines or 'New Service' alone.
    services = []
    seen = set()
    listed = False
    for line in text.splitlines():
        if line.strip() == "Service list":
            listed = True
            continue
        if listed:
            match = SERVICE_LINE.fullmatch(line.strip())
            if match:
                service_id = "0x" + match.group(1).upper()
                label = match.group(2).strip()
                # upstream includes extra '[subch ...]' after '[component]'.
                if (not label or len(label) > MAX_LABEL_LENGTH or
                        not all(c.isprintable() for c in label)):
                    continue
                if service_id not in seen and len(services) < 128:
                    seen.add(service_id)
                    services.append(DetectedService(service_id, label, "radio"))
            elif line.strip() and not line.startswith(" "):
                listed = False
    if services:
        return ProbeReading(
            "service_decoded", services=tuple(services),
            technical_details="welle-cli stdout/stderr DAB service list; audio not tested")

    if "New Service: 0x" in text or "Ensemble label:" in text:
        return ProbeReading(
            "signal_locked",
            technical_details="FIC service/ensemble identified but labelled list unavailable")
    if timed_out:
        return ProbeReading(
            "no_signal",
            technical_details="No confirmed DAB services before per-block deadline; RF silence not proven")
    return ProbeReading(
        "no_signal",
        technical_details="No DAB services decoded during bounded single-block attempt")


class WelleCliDabProbe:
    """Trusted ReceiverBackend for one DAB block per managed SDR lock.

    A caller-controlled URL, RF frequency or arbitrary binary path is NEVER
    passed from client input. The injected identity validator is the critical
    host trust boundary: it must verify exactly ONE accessible RTL-SDR and
    that upstream's first working device maps to receiver.receiver_id.
    """

    def __init__(self, library: FrequencyLibrary, *,
                 verified_single_device: Callable[[str], bool] | None = None,
                 executable: str | Path | None = None,
                 dwell_seconds: float = 12.0,
                 clock: Callable[[], float] = time.monotonic):
        self.channels = dab_channel_map(library)
        self.verified_single_device = verified_single_device
        if executable is None:
            executable = shutil.which("welle-cli")
        if executable is None:
            self.executable = None
        else:
            path = Path(executable)
            if not path.is_absolute():
                raise ValueError("welle-cli binary must be an absolute trusted path")
            self.executable = path
        if type(dwell_seconds) not in (int, float) or not (4 <= dwell_seconds <= 40):
            raise ValueError("Bounded 4..40 seconds DAB per-channel dwell required")
        self.dwell_seconds = float(dwell_seconds)
        self.clock = clock

    def command(self, point: TunePoint) -> tuple[str, ...]:
        if point.mode != "dab" or point.offset_hz or point.bandwidth_hz not in (None, 0):
            raise ValueError("DAB scan may only tune exact published Band III centers")
        channel = self.channels.get(point.frequency_hz)
        if channel is None:
            raise ValueError("Unknown or unapproved DAB block")
        if self.executable is None:
            raise WelleCliProbeError("welle-cli is not installed")
        # Upstream source: -F rtl_sdr chooses the *first working* device.
        # Never enable -w: upstream Socket::bind uses INADDR_ANY.
        return (str(self.executable), "-c", channel,
                "-F", "rtl_sdr", "-T", "-p", UNPLAYABLE_SERVICE_NAME)

    def probe(self, receiver: Receiver, point: TunePoint) -> ProbeReading:
        command = self.command(point)
        if (not receiver.connected or receiver.kind != "radio_sdr"
                or not receiver.receiver_id.startswith("usb-sdr:")
                or not receiver.supports("dab", point.frequency_hz)):
            raise WelleCliProbeError("Verified compatible radio receiver required")
        if (self.verified_single_device is None
                or self.verified_single_device(receiver.receiver_id) is not True):
            raise WelleCliProbeError(
                "No trusted USB-to-welle-cli first-working RTL tuner mapping")
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise WelleCliProbeError("welle-cli binary missing or not executable")

        # stdout/stderr are drained with selectors, never communicate() into
        # an unbounded in-memory buffer. No shell, network port or file dump.
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True,
            close_fds=True, cwd="/",
        )
        if proc.stdin is None or proc.stdout is None:
            self._stop_process(proc)
            raise WelleCliProbeError("Cannot attach bounded CLI pipes")

        captured = bytearray()
        deadline = self.clock() + self.dwell_seconds
        timed_out = False
        try:
            try:
                proc.stdin.write(b".\n")
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                proc.stdin.close()

            with selectors.DefaultSelector() as watcher:
                watcher.register(proc.stdout, selectors.EVENT_READ)
                while watcher.get_map():
                    remaining = deadline - self.clock()
                    if remaining <= 0:
                        timed_out = True
                        break
                    events = watcher.select(timeout=min(0.2, remaining))
                    for key, _mask in events:
                        data = os.read(key.fileobj.fileno(), 8192)
                        if not data:
                            watcher.unregister(key.fileobj)
                            break
                        if len(captured) + len(data) > MAX_CAPTURE_BYTES:
                            raise WelleCliProbeError("welle-cli log exceeded bounded budget")
                        captured.extend(data)
                    # A child can exit but the PIPE may still contain data:
                    # drain until EOF or deadline, not until first poll().
            returncode = proc.poll()
            return interpret_welle_cli_log(bytes(captured), timed_out=timed_out,
                                           returncode=returncode)
        finally:
            self._stop_process(proc)
            proc.stdout.close()

    @staticmethod
    def _stop_process(proc: subprocess.Popen) -> None:
        """Terminate entire child session on every stop/cancel/error path."""
        if proc.poll() is not None:
            proc.wait()
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=1.5)
