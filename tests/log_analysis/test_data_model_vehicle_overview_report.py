#!/usr/bin/env python3

"""
Tests for vehicle overview extraction robustness.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_report import (
    _instance_health_from_message_field,
    build_airspeed_info,
    build_baro_info,
    build_imu_info,
    extract_hardware_report,
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

    log_data = LogData()
    log_data.add_message_columns("VER", ver_data)
    log_data.add_message_columns("MSG", msg_data)

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

    log_data = LogData()
    log_data.add_message_columns("IMU", imu_data)

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
        stored_units=[""],
        scaled_units=[""],
        multipliers=[None],
        multipliers_applied_at_ingest=[False],
        records=1,
    )

    log_data = LogData()
    log_data.add_message_columns("BARO", baro_data, baro_schema)

    info = build_baro_info(
        apm_doc=None,
        log_data=log_data,
        params={"BARO1_DEVID": 1.0, "BARO_WCF_ENABLE": 1.0},
        instance=1,
    )

    assert info.healthy is None


def test_extract_hardware_report_ignores_zero_placeholder_hardware_ids() -> None:
    """Zero-valued placeholder parameters must not create phantom hardware entries."""
    report = extract_hardware_report(
        log_data=LogData(),
        params={
            "INS_ACC_ID": 123.0,
            "INS_GYR_ID": 456.0,
            "INS_ACC2_ID": 0.0,
            "COMPASS_DEV_ID": 789.0,
            "COMPASS_DEV_ID2": 0.0,
            "BARO1_DEVID": 321.0,
            "BARO2_DEVID": 0.0,
            "ARSPD_TYPE": 1.0,
            "ARSPD2_TYPE": 0.0,
        },
        apm_doc=None,
    )

    assert [imu.instance for imu in report.imus] == [1]
    assert [compass.instance for compass in report.compasses] == [1]
    assert [baro.instance for baro in report.baros] == [1]
    assert [airspeed.instance for airspeed in report.airspeed_sensors] == [1]


def test_build_airspeed_info_uses_instance_specific_parameter_metadata() -> None:
    """Second airspeed sensor metadata should come from ARSPD2_* definitions, not ARSPD_* ones."""
    info = build_airspeed_info(
        apm_doc={
            "ARSPD_TYPE": {"values": {"1": "Primary"}},
            "ARSPD2_TYPE": {"values": {"2": "Secondary"}},
            "ARSPD_USE": {"values": {"0": "DoNotUse"}},
            "ARSPD2_USE": {"values": {"2": "UseWhenZeroThrottle"}},
        },
        log_data=LogData(),
        params={"ARSPD2_TYPE": 2.0, "ARSPD2_USE": 2.0},
        instance=2,
    )

    assert info.sensor_type == "Secondary"
    assert info.use is True


@pytest.mark.parametrize(
    ("message_name", "rows", "dtype", "instance", "health_field", "expected"),
    [
        ("IMU", [(1,)], [("AH", "i4")], 1, "AH", None),
        ("ARSP", [(0, 1), (0, 1)], [("I", "i4"), ("H", "i4")], 2, "H", None),
        ("MAG", [(0, 1), (0, 0), (1, 1)], [("I", "i4"), ("Health", "i4")], 1, "Health", False),
        ("BARO", [(1, 1), (1, 2), (0, 0)], [("I", "i4"), ("H", "i4")], 2, "H", True),
    ],
)
def test_instance_health_helper_behaviour(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    message_name: str,
    rows: list[tuple[int, ...]],
    dtype: list[tuple[str, str]],
    instance: int,
    health_field: str,
    expected: bool | None,
) -> None:
    """Helper should return expected health state across representative edge cases."""
    data = np.array(rows, dtype=dtype)
    log_data = LogData()
    log_data.add_message_columns(message_name, data)

    result = _instance_health_from_message_field(
        log_data,
        message_name,
        instance=instance,
        health_field=health_field,
    )

    assert result is expected
