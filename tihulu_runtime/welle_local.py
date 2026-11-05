# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded read-only access to an EXISTING localhost welle-cli receiver.

This adapter does not launch the decoder or configure its TCP listener.
The trusted runtime must isolate welle-cli from the LAN before using it.
No writable /channel endpoint, automatic scan, or live RF claim.
"""
from __future__ import annotations

import http.client
import json
import math
import re
import struct
from typing import Callable

MAX_RESPONSE = 262_144
TECH_PATHS = frozenset({"/spectrum", "/constellation", "/impulseresponse"})


class WelleLocalError(RuntimeError):
    """The local decoder is unavailable or returned untrusted data."""


class WelleLocalReader:
    """Loopback-only telemetry reader; NO arbitrary remote URL or server start."""

    def __init__(self, *, port: int = 7979, timeout: float = 2.0,
                 connection_factory: Callable = http.client.HTTPConnection):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Nonprivileged local welle-cli port required")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 5:
            raise ValueError("Timeout must be 0..5 seconds")
        self.port = port
        self.timeout = float(timeout)
        self.connection_factory = connection_factory

    def _get(self, path: str) -> bytes:
        if path not in TECH_PATHS | {"/mux.json", "/channel"}:
            raise PermissionError("Only explicit read-only diagnostic paths allowed")
        connection = self.connection_factory(
            "127.0.0.1", self.port, timeout=self.timeout)
        try:
            connection.request("GET", path,
                               headers={"Accept": "application/json, application/octet-stream, text/plain"})
            response = connection.getresponse()
            if response.status != 200:
                raise WelleLocalError("Decoder did not return a successful local response")
            header = response.getheader("Content-Length")
            if header is not None:
                try:
                    if int(header) > MAX_RESPONSE or int(header) < 0:
                        raise WelleLocalError("Decoder response exceeds configured size limit")
                except ValueError as exc:
                    raise WelleLocalError("Invalid response length") from exc
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise WelleLocalError("Decoder response exceeds configured size limit")
            return data
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            raise WelleLocalError("Local DAB decoder unavailable") from exc
        finally:
            connection.close()

    def channel(self) -> str:
        """Channel label only; it does not independently prove RF lock."""
        raw = self._get("/channel")
        try:
            channel = raw.decode("ascii").strip().upper()
        except UnicodeDecodeError as exc:
            raise WelleLocalError("Invalid DAB channel label") from exc
        if not re.fullmatch(r"(?:[5-9]|1[0-3])[A-F]", channel):
            raise WelleLocalError("Unexpected DAB channel label")
        return channel

    def mux(self) -> dict:
        """Return only decoder-reported metadata, not validated live stations."""
        try:
            info = json.loads(self._get("/mux.json").decode("utf-8"),
                              parse_constant=lambda value: (_ for _ in ()).throw(
                                  ValueError("Invalid JSON numeric constant")))
        except (ValueError, UnicodeError) as exc:
            raise WelleLocalError("Malformed decoder metadata") from exc
        if not isinstance(info, dict):
            raise WelleLocalError("Decoder metadata must be a JSON object")
        return {
            "decoder_reported": True,
            "physical_rf_validated_by_tihulu": False,
            "ensemble_data": info,
        }

    def samples(self, path: str) -> tuple[float, ...]:
        """Bounded native-little-endian float32 diagnostic series.

        Current welle-cli desktop/Pi targets are little endian. Validate
        binary framing and finiteness; callers render only if source is live.
        """
        if path not in TECH_PATHS:
            raise PermissionError("No access to arbitrary welle-cli endpoint")
        raw = self._get(path)
        if not raw or len(raw) % 4 or len(raw) > 65_536:
            raise WelleLocalError("Unexpected FFT/constellation sample framing")
        readings = struct.unpack("<" + str(len(raw) // 4) + "f", raw)
        if not all(math.isfinite(value) for value in readings):
            raise WelleLocalError("Invalid nonfinite RF diagnostic sample")
        return readings

    def expert_snapshot(self) -> dict:
        """Read-only pull. No background loop; caller chooses refresh rate."""
        return {
            "channel": self.channel(),
            "mux": self.mux(),
            "rf_spectrum": self.samples("/spectrum"),
            "constellation": self.samples("/constellation"),
            "impulse_response": self.samples("/impulseresponse"),
            "status": "decoder_reported_not_independently_rf_verified",
        }
