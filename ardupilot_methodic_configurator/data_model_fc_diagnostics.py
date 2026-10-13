"""
Normalize flight-controller diagnostics and derive device-table rows.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
from time import monotonic

from ardupilot_methodic_configurator.decode_devid import DeviceCategory, decode_device_id, get_device_type_name


def status_text_bytes(message: object) -> bytes:
    """Use the wire bytes, since PyMAVLink's text attribute decodes as ASCII."""
    raw_text = getattr(message, "_text_raw", None)
    if not isinstance(raw_text, bytes):
        raw_text = getattr(message, "text", "")
    return raw_text if isinstance(raw_text, bytes) else str(raw_text).encode("utf-8")


def decode_status_text(message: object) -> str:
    """Decode a standalone STATUSTEXT payload without its null padding."""
    return status_text_bytes(message).split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


def message_source(message: object) -> tuple[int, int] | None:
    """Return a packet's source when available, including for test transports."""
    system = getattr(message, "get_srcSystem", lambda: None)()
    component = getattr(message, "get_srcComponent", lambda: None)()
    return (system, component) if isinstance(system, int) and isinstance(component, int) else None


class StatusTextAssembler:
    """Assemble ordered MAVLink 2 chunks; discard incomplete or expired sequences."""

    CHUNK_TIMEOUT = 5.0
    MAX_PENDING = 100

    def __init__(self) -> None:
        self._pending: dict[tuple[int, int, int], tuple[int, bytes, float]] = {}

    def clear(self) -> None:
        """Discard unfinished messages when the connection changes."""
        self._pending.clear()

    def assemble(self, message: object) -> str | None:
        """Return a complete message, preserving spaces and UTF-8 across chunks."""
        now = monotonic()
        self._pending = {key: value for key, value in self._pending.items() if now - value[2] < self.CHUNK_TIMEOUT}
        message_id = getattr(message, "id", 0)
        if not isinstance(message_id, int) or message_id == 0:
            return decode_status_text(message)
        sequence = getattr(message, "chunk_seq", 0)
        if not isinstance(sequence, int) or not 0 <= sequence <= 255:
            return None
        source = message_source(message) or (0, 0)
        key = (source[0], source[1], message_id)
        raw_text = status_text_bytes(message)
        complete = b"\x00" in raw_text or len(raw_text) < 50
        chunk = raw_text.split(b"\x00", 1)[0]
        if sequence == 0:
            previous = b""
            if key not in self._pending and len(self._pending) >= self.MAX_PENDING:
                del self._pending[next(iter(self._pending))]
        else:
            pending = self._pending.get(key)
            if pending is None or sequence == pending[0] - 1:
                # Ignore a retransmitted chunk without losing the sequence.
                return None
            expected, previous, _timestamp = pending
            if sequence != expected:
                self._pending.pop(key, None)
                return None
        text = previous + chunk
        if complete:
            self._pending.pop(key, None)
            return text.decode("utf-8", errors="replace").strip()
        self._pending[key] = (sequence + 1, text, now)
        return None


def _device_category(parameter_name: str) -> DeviceCategory | None:
    if parameter_name.startswith("COMPASS_"):
        return "compass"
    if parameter_name.startswith("BARO"):
        return "baro"
    if parameter_name.startswith("INS") and ("_ACC" in parameter_name or "_GYR" in parameter_name):
        return "imu"
    if parameter_name.startswith(("ARSPD", "AIRSPEED")):
        return "airspeed"
    return None


def _compass_priorities(fc_parameters: dict[str, float]) -> dict[int, int]:
    """Map compass device IDs to their configured one-based priority, not their instance number."""
    priorities: dict[int, int] = {}
    for parameter_name, raw_device_id in fc_parameters.items():
        match = re.fullmatch(r"COMPASS_PRIO([1-9]\d*)_ID", parameter_name)
        if match is None:
            continue
        try:
            device_id = int(raw_device_id)
        except (TypeError, ValueError, OverflowError):
            continue
        if raw_device_id != device_id or not 0 < device_id <= 0x00FFFFFF:
            continue
        priority = int(match[1])
        priorities[device_id] = min(priority, priorities.get(device_id, priority))
    return priorities


def device_rows(fc_parameters: dict[str, float]) -> list[tuple[str, str, int, int, str, int | None, str]]:
    """Derive present devices, decoded IDs, compass priorities and source labels without GUI I/O."""
    rows: list[tuple[str, str, int, int, str, int | None, str]] = []
    compass_priorities = _compass_priorities(fc_parameters)
    for parameter_name, raw_device_id in fc_parameters.items():
        category = _device_category(parameter_name)
        if category is None or not (
            parameter_name.endswith("_DEVID")
            or "_DEV_ID" in parameter_name
            or (category == "imu" and parameter_name.endswith("_ID"))
        ):
            continue
        try:
            device_id = int(raw_device_id)
        except (TypeError, ValueError, OverflowError):
            continue
        if device_id <= 0:
            continue
        decoded, error = decode_device_id(device_id)
        if error is not None or decoded is None:
            continue
        name = (
            parameter_name.removesuffix("_DEVID")
            if parameter_name.endswith("_DEVID")
            else re.sub(r"_ID(\d*)$", r"\1", parameter_name)
        )
        compass_instance = re.fullmatch(r"COMPASS_DEV_ID(\d*)", parameter_name)
        if compass_instance is not None:
            name = f"COMPASS{compass_instance[1] or '1'}"
        priority = compass_priorities.get(device_id) if category == "compass" else None
        devtype = "DRONECAN" if decoded["is_dronecan"] else get_device_type_name(decoded["devtype"], category)
        devtype = re.sub(r"^(?:(?:DEVTYPE_?|INS_|BARO_|ACC_|GYR_))+", "", devtype, flags=re.IGNORECASE)
        rows.append(
            (
                name,
                decoded["bus_type_name"],
                decoded["bus"],
                decoded["address"],
                devtype,
                priority,
                f"{parameter_name}: {device_id}",
            )
        )
    return sorted(rows, key=lambda row: row[0])
