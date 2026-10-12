#!/usr/bin/env python3

"""
Behavior tests for complete flight-controller diagnostics.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

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


def test_device_rows_show_only_present_devices_with_formatted_names_and_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Present device rows omit ID suffixes and type prefixes, and skip absent IDs."""

    def get_device_type_name(_devtype: int, category: str) -> str:
        type_names = {
            "baro": "DEVTYPE_BARO_DPS310",
            "compass": "COMPASS_HMC5883",
            "imu": "INS_ICM42688",
        }
        return type_names[category]

    monkeypatch.setattr(diagnostics, "get_device_type_name", get_device_type_name)

    rows = diagnostics.device_rows(
        {
            "BARO1_DEVID": 423425.0,
            "BARO2_DEVID": 0,
            "COMPASS_DEV_ID2": 423425,
            "COMPASS_PRIO1_ID": 423425,
            "INS_ACC2_ID": 423425,
            "INS_GYR3_ID": 0,
            "BATT_MONITOR": 423425,
        }
    )

    assert [row[0] for row in rows] == ["BARO1", "COMPASS_DEV2", "COMPASS_PRIO1", "INS_ACC2"]
    assert [row[4] for row in rows] == ["DPS310", "COMPASS_HMC5883", "COMPASS_HMC5883", "ICM42688"]
    assert [row[5] for row in rows] == [
        "BARO1_DEVID: 423425",
        "COMPASS_DEV_ID2: 423425",
        "COMPASS_PRIO1_ID: 423425",
        "INS_ACC2_ID: 423425",
    ]


@pytest.mark.parametrize("parameter_name", ["INS4_ACC_ID", "INS4_GYR_ID", "INS5_ACC_ID", "INS5_GYR_ID"])
def test_device_rows_include_fourth_and_fifth_imu(parameter_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """GIVEN an extra IMU ID, WHEN diagnostics opens, THEN its device and IMU type are displayed."""
    monkeypatch.setattr(
        diagnostics, "get_device_type_name", lambda _devtype, category: "INS_ICM42688" if category == "imu" else "unknown"
    )

    rows = diagnostics.device_rows({parameter_name: 423425})

    assert len(rows) == 1
    assert rows[0][0] == parameter_name.removesuffix("_ID")
    assert rows[0][4] == "ICM42688"
    assert rows[0][5] == f"{parameter_name}: 423425"
