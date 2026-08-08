"""
Vehicle identity extraction helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib

from ardupilot_methodic_configurator.data_model_fc_ids import APJ_BOARD_ID_NAME_DICT
from ardupilot_methodic_configurator.log_analysis.data_model_firmware_version import parse_first_msg_version, parse_ver_fields
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import StartupInfo, VehicleInfo

_STARTUP_ANCHOR_LINE = "Param space used:"


def extract_startup_info(log_data: LogData) -> StartupInfo:
    """Extract the OS and flight-controller strings logged at startup."""
    columns = log_data.get_message_columns("MSG")
    if columns is None or columns.size == 0:
        return StartupInfo(os_string=None, flight_controller=None)

    messages = log_data.get_field("MSG", "Message")

    for i, message in enumerate(messages):
        if i < 2:
            continue
        if message.startswith(_STARTUP_ANCHOR_LINE):
            return StartupInfo(os_string=messages[i - 2], flight_controller=messages[i - 1])

    return StartupInfo(os_string=None, flight_controller=None)


def _vehicle_info_from_ver(log_data: LogData) -> VehicleInfo | None:
    """Read vehicle type, version, hash, and board id from the VER message, if present."""
    ver_columns = log_data.get_message_columns("VER")
    if ver_columns is None or ver_columns.size == 0:
        return None

    names = ver_columns.dtype.names or ()
    required = {"FWS", "Maj", "Min", "Pat"}
    if not required.issubset(names):
        return None

    fws = log_data.get_field("VER", "FWS")[0]
    result = parse_ver_fields(
        fws, log_data.get_field("VER", "Maj")[0], log_data.get_field("VER", "Min")[0], log_data.get_field("VER", "Pat")[0]
    )
    if result is None:
        return None

    vehicle_type, major, minor, patch = result

    firmware_hash = None
    if "GH" in names:
        with contextlib.suppress(TypeError, ValueError):
            gh = int(log_data.get_field("VER", "GH")[0])
            if gh != 0:
                firmware_hash = f"{gh:08x}"

    board_id = None
    if "APJ" in names:
        with contextlib.suppress(TypeError, ValueError):
            apj = int(log_data.get_field("VER", "APJ")[0])
            if apj != 0:
                board_id = apj

    return VehicleInfo(
        vehicle_type=vehicle_type,
        major=major,
        minor=minor,
        patch=patch,
        firmware_hash=firmware_hash,
        board_id=board_id,
        flight_controller=None,
        oper_sys=None,
    )


def _vehicle_info_from_msg_fallback(log_data: LogData) -> VehicleInfo | None:
    """Read vehicle type, version, and hash from a MSG line, for firmware with no VER message."""
    columns = log_data.get_message_columns("MSG")
    if columns is None or columns.size == 0:
        return None

    parsed = parse_first_msg_version(log_data.get_field("MSG", "Message"))
    if parsed is not None:
        vehicle_type, major, minor, patch, firmware_hash = parsed
        return VehicleInfo(
            vehicle_type=vehicle_type,
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            firmware_hash=firmware_hash,
            board_id=None,
            flight_controller=None,
            oper_sys=None,
        )

    return None


def extract_vehicle_info(log_data: LogData) -> VehicleInfo:
    """Extract vehicle identity and FC identity from a parsed log."""
    info = _vehicle_info_from_ver(log_data)
    if info is None:
        info = _vehicle_info_from_msg_fallback(log_data)
    if info is None:
        info = VehicleInfo(
            vehicle_type=None,
            major=None,
            minor=None,
            patch=None,
            firmware_hash=None,
            board_id=None,
            flight_controller=None,
            oper_sys=None,
        )

    startup_info = extract_startup_info(log_data)
    info.flight_controller = startup_info.flight_controller
    info.oper_sys = startup_info.os_string

    return info


def resolve_board_name(board_id: int | None) -> str | None:
    """Resolve a numeric APJ board ID to its board name, using AMC's bundled fc_id data."""
    if board_id is None:
        return None
    names = APJ_BOARD_ID_NAME_DICT.get(board_id)
    return names[0] if names else None
