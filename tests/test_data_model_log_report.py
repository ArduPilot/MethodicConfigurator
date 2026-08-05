#!/usr/bin/env python3

"""
Tests for pure log-report presentation helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

from ardupilot_methodic_configurator.log_analysis.data_model_log_report import (
    build_report_status,
    clean_devtype,
    firmware_release_link,
    format_duration,
    format_optional_value,
    step_display_name,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import VehicleInfo


def test_report_status_counts_quality_issues_and_failed_steps() -> None:
    """Report status is calculated without building Tk widgets."""
    summary = MagicMock()
    summary.quality_results = [MagicMock(issues=[object(), object()]), MagicMock(issues=[])]
    summary.step_results = [MagicMock(valid=True), MagicMock(valid=False)]

    status = build_report_status(summary)

    assert status.problem_count == 3
    assert status.color == "darkorange"
    assert "3 potential issue" in status.text


def test_report_status_is_healthy_when_no_issues() -> None:
    summary = MagicMock()
    summary.quality_results = [MagicMock(issues=[])]
    summary.step_results = [MagicMock(valid=True)]

    status = build_report_status(summary)

    assert status.problem_count == 0
    assert status.color == "darkgreen"


def test_firmware_release_link_formats_ardupilot_tag() -> None:
    vehicle = VehicleInfo(
        vehicle_type="ArduCopter",
        major=4,
        minor=6,
        patch=3,
        firmware_hash=None,
        board_id=None,
        flight_controller=None,
        oper_sys=None,
    )

    release = firmware_release_link(vehicle)

    assert release is not None
    assert release.base_text == "ArduCopter 4.6.3"
    assert release.version_tag == "Copter-4.6.3"
    assert release.url.endswith("/Copter-4.6.3")


def test_report_format_helpers_are_pure() -> None:
    assert format_duration(None) == "-"
    assert format_duration(125.9) == "2m 5s"
    assert step_display_name("05_battery_setup.param") == "05 battery setup"
    assert clean_devtype("DEVTYPE_INS_ICM42688") == "ICM42688"
    assert format_optional_value("Unknown") == "-"
