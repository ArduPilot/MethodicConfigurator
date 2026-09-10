#!/usr/bin/env python3

"""
Tests for the locally generated MAVLink PARAM_ERROR compatibility decoder.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_mavlink_param_error import (
    PARAM_ERROR_MESSAGE_ID,
    install_param_error_message,
)


def test_param_error_wire_definition_decodes_a_mavlink2_frame() -> None:
    """
    Decode a PARAM_ERROR frame produced from the MAVLink wire definition.

    GIVEN: A MAVLink-2 PARAM_ERROR frame with a known payload and CRC
    WHEN: The compatibility decoder parses the frame
    THEN: The parameter error fields are decoded with their wire values
    """
    install_param_error_message()
    mavlink = mavutil.mavlink
    assert mavlink.WIRE_PROTOCOL_VERSION == "2.0"

    # This frame has payload ``<hBB16sB``:
    # param_index=-1, target_system=1, target_component=1,
    # param_id="BATT_MONITOR", error=5, CRC extra=209.
    frame = bytes.fromhex("fd 15 00 00 00 01 01 59 01 00 ff ff 01 01 42 41 54 54 5f 4d 4f 4e 49 54 4f 52 00 00 00 00 05 20 2d")

    receiver = mavlink.MAVLink(None)
    decoded = None
    for byte in frame:
        decoded = receiver.parse_char(bytes((byte,))) or decoded

    assert decoded is not None
    assert decoded.get_type() == "PARAM_ERROR"
    assert decoded.get_msgId() == PARAM_ERROR_MESSAGE_ID
    assert decoded.param_id == "BATT_MONITOR"
    assert decoded.param_index == -1
    assert decoded.error == 5
