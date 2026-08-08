"""
Pure firmware version parsing helpers for ArduPilot log analysis.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import re
from collections.abc import Iterable
from typing import Any

# Matches lines like "ArduCopter V4.5.5 (142aece2)", and as a fallback when no VER message is
# present in the log (old firmware).
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
