"""
Extracts firmware version information from an ArduPilot .bin log file.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import (
    close_log,
    open_log,
    process_msg_identity,
    process_ver_identity,
)


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
                result = process_ver_identity(m)
                if result is not None:
                    return result
            elif m.get_type() == "MSG" and msg_fallback_result is None:
                msg_fallback_result = process_msg_identity(m)

        if msg_fallback_result is not None:
            return msg_fallback_result

        msg = f"No firmware version information found in {logfile}"
        raise ValueError(msg)
    finally:
        close_log(mlog)
