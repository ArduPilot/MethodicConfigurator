"""
Extracts firmware version information from an ArduPilot .bin log file.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import re
from collections.abc import Iterable
from typing import Any

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import close_log, open_log

# Matches lines like "ArduCopter V4.5.5 (142aece2)", and as a fallback when, no VER message present in the log (old firmware).
_MSG_VERSION_PATTERN = re.compile(
    r"^(ArduCopter|ArduPlane|ArduRover|ArduSub|AntennaTracker|Blimp) "
    r"V(\d+)\.(\d+)(?:\.(\d+))?(?: \(([0-9a-fA-F]+)\))?$"
)


def parse_ver_fields(fws: str, maj: Any, mini: Any, pat: Any) -> tuple[str, int, int, int] | None:  # noqa: ANN401
    """
    Parse a VER message's core fields into (vehicle_type, major, minor, patch).

    fws is the raw FWS string (e.g. "ArduCopter V4.6.3"); maj/mini/pat are the
    raw Maj/Min/Pat field values or None.
    """
    fws = fws.strip()
    if not fws:
        return None
    parts = fws.split(maxsplit=1)
    vehicle_type = parts[0] if parts else ""
    if not vehicle_type:
        return None

    if maj is None or mini is None or pat is None:
        return None

    with contextlib.suppress(TypeError, ValueError):
        return vehicle_type, int(maj), int(mini), int(pat)
    return None


def _process_ver(msg: Any) -> tuple[str, int, int, int] | None:  # noqa: ANN401
    """
    Extract firmware version from a VER DataFlash log entry.

    Returns (vehicle_type, major, minor, patch) or None if any field is missing.
    """
    fws = getattr(msg, "FWS", None)
    if isinstance(fws, bytes):
        fws = fws.decode("utf-8", errors="replace")
    elif not isinstance(fws, str):
        return None

    return parse_ver_fields(fws, getattr(msg, "Maj", None), getattr(msg, "Min", None), getattr(msg, "Pat", None))


def parse_msg_ver_string(message: str) -> tuple[str, int, int, int, str | None] | None:
    """
    Parse a firmware version line from MSG text, e.g. "ArduCopter V4.5.5 (142aece2)".

    Also accepts a version with no patch number, e.g. "ArduCopter V4.6 (hash)", defaulting patch to 0.

    Returns (vehicle_type, major, minor, patch, firmware_hash) or None.
    """
    matched = _MSG_VERSION_PATTERN.match(message.strip())
    if matched is None:
        return None

    vehicle_type, major, minor, patch, firm_hash = matched.groups()
    patch_val = int(patch) if patch is not None else 0
    return vehicle_type, int(major), int(minor), patch_val, firm_hash


def parse_first_msg_version(messages: Iterable[str]) -> tuple[str, int, int, int, str | None] | None:
    """Return the first parseable firmware version tuple found in MSG message text."""
    for message in messages:
        parsed = parse_msg_ver_string(message)
        if parsed is not None:
            return parsed
    return None


def _parse_msg_version(msg: Any) -> tuple[str, int, int, int] | None:  # noqa: ANN401
    """
    Parse firmware version from a MSG DataFlash log entry.

    Returns (vehicle_type, major, minor, patch) or None if the entry is not parseable.
    The caller is responsible for not calling this once a result has already been found.
    """
    message = getattr(msg, "Message", "")
    if isinstance(message, bytes):
        message = message.decode("utf-8", errors="replace")
    elif not isinstance(message, str):
        return None
    parsed = parse_first_msg_version([message])
    if parsed is None:
        return None
    vehicle_type, major, minor, patch, _firm_hash = parsed
    return vehicle_type, major, minor, patch


def extract_firmware_version_and_vehicle_type(logfile: str) -> tuple[str, int, int, int]:
    """
    Extract vehicle type and firmware version from an ArduPilot .bin log file.

    Prefers the structured VER message (fields Maj, Min, Pat, FWS) and falls back to
    scanning MSG messages until one with a parseable "Vx.y" version is found
    (e.g. "ArduCopter V4.6.3 (hash)").

    Args:
        logfile: The path to the ArduPilot .bin log file.

    Returns:
        A tuple of (vehicle_type, major, minor, patch), e.g. ("ArduCopter", 4, 6, 3).

    """
    mlog = open_log(logfile)
    try:
        msg_fallback_result: tuple[str, int, int, int] | None = None
        while True:
            m = mlog.recv_match(type=["VER", "MSG"])
            if m is None:
                break
            if m.get_type() == "VER":
                result = _process_ver(m)
                if result is not None:
                    return result
            elif m.get_type() == "MSG" and msg_fallback_result is None:
                msg_fallback_result = _parse_msg_version(m)

        if msg_fallback_result is not None:
            return msg_fallback_result

        msg = f"No firmware version information found in {logfile}"
        raise SystemExit(msg)
    finally:
        close_log(mlog)
