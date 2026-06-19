#!/usr/bin/env python3

"""
Integration tests for ardupilot_methodic_configurator/log_analysis/backend_log_extraction.py.

These tests exercise real pymavlink parsing against a truncated ArduPilot .bin fixture.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

import pytest

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import extract_log, parse_log

pytestmark = pytest.mark.integration

FIXTURE_LOG = Path(__file__).resolve().parent / "fixtures" / "backend_log_80k.bin"


def test_extract_log_reads_real_pymavlink_data() -> None:
    """
    Parse a real .bin log file and assert schemas are populated.

    GIVEN a real ArduPilot log fixture,
    WHEN it is fully extracted,
    THEN the FMT-derived schemas and record counts are populated.
    """
    log_data = extract_log(str(FIXTURE_LOG))

    assert log_data.msg_count["VER"] == 1
    assert log_data.msg_count["FMT"] > 0
    assert log_data.msg_count["FMTU"] > 0
    assert log_data.schemas["VER"].records == 1
    assert log_data.schemas["FMT"].records == log_data.msg_count["FMT"]
    assert log_data.schemas["FMTU"].records == log_data.msg_count["FMTU"]
    assert "GPS" in log_data.schemas
    assert "PARM" in log_data.msg_count


def test_parse_log_yields_real_messages() -> None:
    """
    Iterate a real .bin log file and assert DataFlash messages are yielded.

    GIVEN a real ArduPilot log fixture,
    WHEN it is iterated via parse_log,
    THEN the resulting stream contains real DataFlash message types.
    """
    messages = list(parse_log(str(FIXTURE_LOG)))
    message_types = {msg.get_type() for msg in messages}

    assert len(messages) > 0
    assert {"FMT", "FMTU", "VER"}.issubset(message_types)
