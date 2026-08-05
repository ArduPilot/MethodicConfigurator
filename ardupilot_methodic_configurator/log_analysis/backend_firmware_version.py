"""
Extracts firmware version information from an ArduPilot .bin log file.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import close_log, open_log
from ardupilot_methodic_configurator.log_analysis.data_model_firmware_version import (
    parse_first_msg_version,
    parse_ver_fields,
)


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
    try:
        mlog = open_log(logfile)
    except OSError as error:
        msg = f"Error opening the {logfile} logfile: {error!s}"
        raise OSError(msg) from error

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
        raise ValueError(msg)
    finally:
        close_log(mlog)
