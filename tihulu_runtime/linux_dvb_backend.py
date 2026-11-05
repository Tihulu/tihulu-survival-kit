# SPDX-License-Identifier: AGPL-3.0-only
"""Optional experimental Linux DVB-T/T2 scan backend, using dvbv5-scan.

It is not auto-started and has not been tested with the purchased Hauppauge
tuner on Raspberry Pi 5. No raw user command, shell string or internet fetch.
Requires trusted server owner permission and a physical tuner lease externally.
"""
from __future__ import annotations

from configparser import ConfigParser, Error as ConfigParserError
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

from .channel_explorer import DetectedService, ProbeReading, Receiver, TunePoint


class LinuxDvbV5Backend:
    """One DVB transport frequency per bounded process.

    Device open and app-wide tuner ownership are the responsibility of the
    authenticated service broker, not this standalone adapter. The scanner
    uses -F to avoid following NIT into frequencies the user did not select.
    """

    def __init__(self, adapter_index: int = 0, frontend_index: int = 0,
                 *, binary: str = "dvbv5-scan"):
        if (type(adapter_index) is not int or type(frontend_index) is not int
                or not 0 <= adapter_index <= 15 or not 0 <= frontend_index <= 15):
            raise ValueError("DVB adapter/frontend index must be within 0-15")
        if binary != "dvbv5-scan":
            raise ValueError("Only the allowlisted dvbv5-scan command is supported")
        self.adapter_index = adapter_index
        self.frontend_index = frontend_index
        self.binary = binary

    @staticmethod
    def scan_input(point: TunePoint) -> str:
        modes = {"dvb_t": "DVBT", "dvb_t2": "DVBT2"}
        if point.mode not in modes:
            raise NotImplementedError(
                "Experimental adapter supports DVB-T/T2 only; DVB-C needs "
                "validated frequency, symbol rate and cable frontend parameters")
        bandwidth = point.bandwidth_hz or 8_000_000
        if bandwidth not in (6_000_000, 7_000_000, 8_000_000):
            raise ValueError("Unsupported DVB terrestrial bandwidth")
        if not isinstance(point.tuned_hz, int) or not (
                40_000_000 <= point.tuned_hz <= 900_000_000):
            raise ValueError("DVB terrestrial tuning frequency out of range")
        return ("[Selected Frequency]\n"
                f"DELIVERY_SYSTEM = {modes[point.mode]}\n"
                f"FREQUENCY = {point.tuned_hz}\n"
                f"BANDWIDTH_HZ = {bandwidth}\n"
                "INVERSION = AUTO\n")

    @staticmethod
    def parse_channel_config(config_text: str, *, frequency_hz: int
                             ) -> tuple[DetectedService, ...]:
        if len(config_text) > 2_000_000:
            raise ValueError("Channel config unexpectedly large")
        p = ConfigParser(interpolation=None, strict=False)
        p.optionxform = str.upper
        try:
            p.read_string(config_text)
        except ConfigParserError as e:
            raise ValueError("Could not decode DVB scanner output") from e
        services: list[DetectedService] = []
        for section in p.sections():
            values = p[section]
            try:
                freq = int(values.get("FREQUENCY","0"))
            except (TypeError, ValueError):
                continue
            # Service must derive from the frequency actually chosen by owner.
            if freq != frequency_hz or "SERVICE_ID" not in values:
                continue
            service_id = values.get("SERVICE_ID","").strip()
            if (not service_id.isdecimal() or len(service_id)>10
                    or len(section)>160):
                continue
            video = values.get("VIDEO_PID", "").strip()
            audio = values.get("AUDIO_PID", "").strip()
            kind = "tv" if video and video!="0" else (
                "radio" if audio and audio!="0" else "data")
            services.append(DetectedService(service_id, section, kind))
            if len(services) > 256:
                raise ValueError("Too many services on one mux")
        return tuple(services)

    def probe(self, receiver: Receiver, point: TunePoint) -> ProbeReading:
        # dvbv5-scan takes control of the frontend: it is not a shared-mux
        # service reader and must never run against an active recording.
        if receiver.recording_active:
            raise RuntimeError("Refusing dvbv5-scan while a recording is active")
        if receiver.kind != "dvb_tuner" or point.mode not in ("dvb_t","dvb_t2"):
            raise ValueError("DVB backend cannot scan general radio/SDR modes")
        if not receiver.supports(point.mode, point.tuned_hz):
            raise RuntimeError("Receiver unavailable or outside supported mode/band")
        scan_file_content = self.scan_input(point)
        frontend = Path(
            f"/dev/dvb/adapter{self.adapter_index}/frontend{self.frontend_index}")
        if not frontend.is_char_device():
            raise RuntimeError("DVB frontend is not a connected character device")
        binary = shutil.which(self.binary)
        if not binary:
            raise RuntimeError("dvbv5-scan is not installed")
        with tempfile.TemporaryDirectory(prefix="tihulu-dvb-") as tmp:
            scan_file = Path(tmp) / "requested-frequency.conf"
            output_file = Path(tmp) / "services.conf"
            scan_file.write_text(scan_file_content, encoding="ascii")
            command = [
                binary, "-a", str(self.adapter_index),
                "-f", str(self.frontend_index),
                "-F", "-o", str(output_file), str(scan_file),
            ]
            result = subprocess.run(command, shell=False, check=False,
                                    capture_output=True, text=True, timeout=40,
                                    env={**os.environ,"LC_ALL":"C"})
            log = (result.stdout or "")[:200_000]
            raw = output_file.read_text(encoding="utf-8",errors="replace") if (
                output_file.exists() and output_file.stat().st_size<=2_000_000) else ""
            services = self.parse_channel_config(raw, frequency_hz=point.tuned_hz) if raw else ()
            if services:
                return ProbeReading("service_decoded", services=services,
                                    technical_details="DVB service table decoded")
            if result.returncode != 0:
                raise RuntimeError("dvbv5-scan failed or frontend could not lock")
            if "Lock   " in log or "Lock (" in log:
                return ProbeReading("signal_locked", technical_details="DVB lock reported")
            return ProbeReading("no_signal", technical_details="No DVB lock or service")
