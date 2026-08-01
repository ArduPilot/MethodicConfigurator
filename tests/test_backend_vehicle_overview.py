#!/usr/bin/env python3

"""
Tests for vehicle overview extraction robustness.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.backend_vehicle_overview import (
    build_baro_info,
    build_imu_info,
    extract_vehicle_info,
)


def test_extract_vehicle_info_falls_back_to_msg_when_ver_fields_are_invalid() -> None:
    """When VER fields are invalid, MSG version parsing is used as fallback."""
    ver_data = np.array(
        [("ArduCopter V4.6.3 (3fc7011a)", "bad", 6, 3)],
        dtype=[("FWS", "U64"), ("Maj", "U16"), ("Min", "i4"), ("Pat", "i4")],
    )
    msg_data = np.array(
        [("ArduCopter V4.6.3 (3fc7011a)",)],
        dtype=[("Message", "U64")],
    )

    log_data = LogData(
        _raw_messages={"VER": ver_data, "MSG": msg_data},
        msg_count={"VER": 1, "MSG": 1},
    )

    info = extract_vehicle_info(log_data)

    assert info.vehicle_type == "ArduCopter"
    assert info.major == 4
    assert info.minor == 6
    assert info.patch == 3


def test_build_imu_info_handles_missing_health_fields_without_crashing() -> None:
    """IMU schemas missing AH/GH should leave health fields as unknown."""
    imu_data = np.array(
        [(0,)],
        dtype=[("I", "i4")],
    )

    log_data = LogData(
        _raw_messages={"IMU": imu_data},
        msg_count={"IMU": 1},
    )

    info = build_imu_info(
        apm_doc=None,
        log_data=log_data,
        params={"INS_ACC_ID": 1.0, "INS_GYR_ID": 1.0},
        instance=1,
    )

    assert info.accel_healthy is None
    assert info.gyro_healthy is None


def test_build_baro_info_handles_missing_instance_field_without_crashing() -> None:
    """BARO schemas missing instance field I should leave health as unknown."""
    baro_data = np.array(
        [(1,)],
        dtype=[("Health", "i4")],
    )
    baro_schema = MessageSchema(
        name="BARO",
        msg_type=1,
        length=1,
        format="B",
        fields=["Health"],
        units=[],
        multipliers=[None],
        records=1,
    )

    log_data = LogData(
        schemas={"BARO": baro_schema},
        _raw_messages={"BARO": baro_data},
        msg_count={"BARO": 1},
    )

    info = build_baro_info(
        apm_doc=None,
        log_data=log_data,
        params={"BARO1_DEVID": 1.0, "BARO_WCF_ENABLE": 1.0},
        instance=1,
    )

    assert info.healthy is None
