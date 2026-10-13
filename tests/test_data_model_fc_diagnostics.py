#!/usr/bin/env python3

"""
Behavior tests for complete flight-controller diagnostics.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from itertools import permutations

import pytest
from pymavlink.dialects.v20.ardupilotmega import MAVLink_statustext_message

from ardupilot_methodic_configurator import data_model_fc_diagnostics as diagnostics


def test_long_status_text_preserves_utf8_and_spaces_across_chunks() -> None:
    """GIVEN split UTF-8 text, WHEN all chunks arrive, THEN one intact diagnostic is returned."""
    assembler = diagnostics.StatusTextAssembler()
    text = "A" * 49 + "é useful details"
    payload = text.encode("utf-8")
    assert assembler.assemble(MAVLink_statustext_message(4, payload[:50], id=42, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, payload[50:], id=42, chunk_seq=1)) == text
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 49 + b" ", id=43, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"tail", id=43, chunk_seq=1)) == "A" * 49 + " tail"


def test_missing_chunk_does_not_display_a_misleading_partial_diagnostic() -> None:
    """GIVEN a missing middle chunk, WHEN the ending arrives, THEN no partial message is emitted."""
    assembler = diagnostics.StatusTextAssembler()
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"ending", id=42, chunk_seq=2)) is None


def test_retransmitted_chunk_does_not_interrupt_a_long_diagnostic() -> None:
    """GIVEN a repeated middle chunk, WHEN the ending arrives, THEN the text contains each chunk once."""
    assembler = diagnostics.StatusTextAssembler()
    for sequence in (0, 1, 1):
        assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=sequence)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"ending", id=42, chunk_seq=2)) == "A" * 100 + "ending"


def test_expired_chunks_cannot_be_combined_with_a_later_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """GIVEN an unfinished old message, WHEN its continuation arrives late, THEN it is discarded."""
    now = [0.0]
    monkeypatch.setattr(diagnostics, "monotonic", lambda: now[0])
    assembler = diagnostics.StatusTextAssembler()
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=0)) is None
    now[0] = 6.0
    assert assembler.assemble(MAVLink_statustext_message(4, b"old ending", id=42, chunk_seq=1)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"new message", id=42, chunk_seq=0)) == "new message"


def test_identical_chunk_ids_from_different_vehicles_are_assembled_separately() -> None:
    """GIVEN two senders using one ID, WHEN chunks interleave, THEN their messages stay separate."""
    assembler = diagnostics.StatusTextAssembler()
    for system, text, sequence, expected in (
        (1, b"A" * 50, 0, None),
        (2, b"B" * 50, 0, None),
        (1, b"first ending", 1, "A" * 50 + "first ending"),
        (2, b"second ending", 1, "B" * 50 + "second ending"),
    ):
        message = MAVLink_statustext_message(4, text, id=42, chunk_seq=sequence)
        message._header.srcSystem = system  # pylint: disable=protected-access
        assert assembler.assemble(message) == expected


def test_empty_final_chunk_completes_an_exact_multiple_of_fifty_bytes() -> None:
    """GIVEN fifty text bytes, WHEN the null ending arrives, THEN the complete diagnostic is emitted."""
    assembler = diagnostics.StatusTextAssembler()
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"\x00", id=42, chunk_seq=1)) == "A" * 50


def test_device_rows_show_only_present_devices_with_formatted_names_and_types() -> None:
    """
    Decoded device details and compass priorities are preserved in complete rows.

    GIVEN: Real barometer, compass and IMU IDs on different buses and absent devices
    WHEN: Diagnostics derives the table using the real device-type lookup
    THEN: Every displayed field and original parameter label matches the detected device
    """
    baro_id = (6 << 16) | (118 << 8) | (1 << 3) | 1
    compass_id = (7 << 16) | (30 << 8) | (2 << 3) | 1
    imu_id = (52 << 16) | (1 << 8) | (3 << 3) | 2
    rows = diagnostics.device_rows(
        {
            "BARO1_DEVID": float(baro_id),
            "BARO2_DEVID": 0,
            "COMPASS_DEV_ID2": compass_id,
            "COMPASS_PRIO1_ID": compass_id,
            "INS_ACC2_ID": imu_id,
            "INS_GYR3_ID": 0,
            "BATT_MONITOR": compass_id,
        }
    )

    assert rows == [
        ("BARO1", "I2C", 1, 118, "DPS310", None, f"BARO1_DEVID: {baro_id}"),
        ("COMPASS2", "I2C", 2, 30, "HMC5883", 1, f"COMPASS_DEV_ID2: {compass_id}"),
        ("INS_ACC2", "SPI", 3, 1, "ICM42688", None, f"INS_ACC2_ID: {imu_id}"),
    ]


@pytest.mark.parametrize("parameter_name", ["INS4_ACC_ID", "INS4_GYR_ID", "INS5_ACC_ID", "INS5_GYR_ID"])
def test_device_rows_include_fourth_and_fifth_imu(parameter_name: str) -> None:
    """GIVEN an extra IMU ID, WHEN diagnostics opens, THEN its device and IMU type are displayed."""
    device_id = (52 << 16) | (1 << 8) | (3 << 3) | 2

    rows = diagnostics.device_rows({parameter_name: device_id})

    assert rows == [(parameter_name.removesuffix("_ID"), "SPI", 3, 1, "ICM42688", None, f"{parameter_name}: {device_id}")]


@pytest.mark.parametrize(
    ("parameter_name", "device_type", "expected_type"),
    [
        ("INS_ACC_ID", 19, "MPU6000"),
        ("INS_GYR_ID", 33, "MPU6000"),
        ("INS_ACC2_ID", 24, "LSM9DS1"),
        ("INS_GYR2_ID", 38, "LSM9DS1"),
    ],
)
def test_device_types_omit_accelerometer_and_gyroscope_prefixes(
    parameter_name: str, device_type: int, expected_type: str
) -> None:
    """
    Accelerometer and gyroscope type names show the sensor model without category prefixes.

    GIVEN: Real device IDs whose enum names contain DEVTYPE_ACC_ or DEVTYPE_GYR_
    WHEN: Diagnostics derives the detected-device rows
    THEN: Only the type prefix is removed and all other device fields remain intact
    """
    device_id = (device_type << 16) | (1 << 8) | (2 << 3) | 2

    rows = diagnostics.device_rows({parameter_name: device_id})

    assert rows == [(parameter_name.removesuffix("_ID"), "SPI", 2, 1, expected_type, None, f"{parameter_name}: {device_id}")]


def test_user_sees_compass_priorities_matched_by_device_id_not_instance_number() -> None:
    """
    Each compass displays its configured priority rather than a duplicate priority-device row.

    GIVEN: Three compass devices with a priority order different from their instance order
    WHEN: Diagnostics derives the detected-device rows
    THEN: Priorities follow matching device IDs and other device categories have no priority
    """
    parameters = {
        "COMPASS_PRIO3_ID": 423681,
        "COMPASS_DEV_ID": 423425,
        "COMPASS_DEV_ID2": 423681,
        "COMPASS_DEV_ID3": 423937,
        "COMPASS_PRIO1_ID": 423937,
        "COMPASS_PRIO2_ID": 423425,
        "BARO1_DEVID": 423937,
    }

    rows = diagnostics.device_rows(parameters)

    assert [(row[0], row[5]) for row in rows] == [
        ("BARO1", None),
        ("COMPASS1", 2),
        ("COMPASS2", 3),
        ("COMPASS3", 1),
    ]
    assert rows[1][6] == "COMPASS_DEV_ID: 423425"
    assert diagnostics.device_rows(dict(reversed(list(parameters.items())))) == rows


@pytest.mark.parametrize("instance", range(1, 9))
def test_compass_names_use_instance_numbers_instead_of_dev_suffixes(instance: int) -> None:
    """
    All detected compasses have consistent instance names.

    GIVEN: A compass device-ID parameter, including additional detected compasses
    WHEN: Its row is derived
    THEN: The device name is COMPASS followed by its one-based instance number
    """
    parameter_name = f"COMPASS_DEV_ID{instance if instance > 1 else ''}"

    rows = diagnostics.device_rows({parameter_name: 423425})

    assert len(rows) == 1
    assert rows[0][0] == f"COMPASS{instance}"
    assert rows[0][5] is None
    assert rows[0][6] == f"{parameter_name}: 423425"


@pytest.mark.parametrize("priority_id", [0, -1, 423681, 423425.5, float("nan"), float("inf")])
def test_missing_or_invalid_compass_priority_does_not_assign_a_rank(priority_id: float) -> None:
    """
    A compass without a matching valid priority remains visible without an invented rank.

    GIVEN: A detected compass and an unset, nonmatching, or malformed priority ID
    WHEN: Diagnostics derives the device table
    THEN: Only the compass device is shown and its priority is None
    """
    rows = diagnostics.device_rows({"COMPASS_DEV_ID": 423425, "COMPASS_PRIO1_ID": priority_id})

    assert [(row[0], row[5]) for row in rows] == [("COMPASS1", None)]


def test_priority_parameters_without_detected_compasses_do_not_create_device_rows() -> None:
    """
    Priority parameters describe ordering, not additional devices.

    GIVEN: Stored compass priorities without any detected compass device-ID parameters
    WHEN: Diagnostics derives the table
    THEN: No priority-only device rows are created
    """
    assert diagnostics.device_rows({"COMPASS_PRIO1_ID": 423425, "COMPASS_PRIO2_ID": 423681}) == []


@pytest.mark.parametrize("priority_order", list(permutations((1, 2, 3))))
def test_duplicate_compass_priority_ids_use_the_highest_priority(priority_order: tuple[int, ...]) -> None:
    """
    Duplicate priority references do not make the displayed rank depend on parameter order.

    GIVEN: Multiple priority slots referencing the same detected compass
    WHEN: Diagnostics derives the table
    THEN: The lowest priority number is displayed once on the compass row
    """
    parameters = {"COMPASS_DEV_ID": 423425}
    parameters.update({f"COMPASS_PRIO{priority}_ID": 423425 for priority in priority_order})

    rows = diagnostics.device_rows(parameters)

    assert rows == [("COMPASS1", "I2C", 0, 118, "LSM9DS1", 1, "COMPASS_DEV_ID: 423425")]
