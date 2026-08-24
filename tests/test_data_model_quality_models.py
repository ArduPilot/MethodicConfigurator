#!/usr/bin/env python3

"""
Tests for log-analysis quality domain models.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np

from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_battery import BatteryLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_esc import EscLogAnalysis, EscLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_gnss import GPSLogQualityModel


def _context(
    parameters: dict[str, float],
    *,
    apm_doc: dict | None = None,
    vehicle_components: dict | None = None,
) -> LogAnalysisContext:
    return LogAnalysisContext(
        parameters=parameters,
        configuration_steps={
            "05_battery.param": {
                "related_bin_messages": {"BAT": {"name": "Battery"}},
                "derived_parameters": {"BATT_MONITOR": 4.0},
            },
            "06_gnss.param": {
                "related_bin_messages": {"GPS": {"name": "GNSS"}},
                "derived_parameters": {"GPS_TYPE": 1.0},
            },
            "07_esc.param": {
                "related_bin_messages": {"ESC": {"name": "ESC"}},
                "derived_parameters": {"MOT_PWM_TYPE": 6.0},
            },
        },
        vehicle_components=vehicle_components or {},
        apm_doc=apm_doc,
    )


def test_battery_model_uses_apm_doc_to_diagnose_disabled_logging() -> None:
    """Missing BAT data should point to LOG_BITMASK when the bit is disabled."""
    result = BatteryLogQualityModel(
        LogData(),
        _context(
            {"LOG_BITMASK": 0.0, "BATT_MONITOR": 4.0},
            apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "9:Battery Monitor"}}},
        ),
    ).check()

    assert result.available is False
    assert result.state == LogQualityState.WARNING
    assert result.issues[0].config_step == "05_battery.param"
    assert "LOG_BITMASK" in result.issues[0].message


def test_gps_model_uses_apm_doc_to_diagnose_disabled_logging() -> None:
    """Missing GPS data should point to LOG_BITMASK when the GPS bit is disabled."""
    result = GPSLogQualityModel(
        LogData(),
        _context(
            {"LOG_BITMASK": 0.0, "GPS_TYPE": 1.0},
            apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "3:GPS"}}},
        ),
    ).check()

    assert result.available is False
    assert result.state == LogQualityState.WARNING
    assert result.issues[0].config_step == "06_gnss.param"
    assert "GPS logging" in result.reason


def test_esc_model_uses_apm_doc_to_detect_non_dshot_configuration() -> None:
    """Missing ESC data should recommend DShot when MOT_PWM_TYPE is not one of the documented DShot values."""
    result = EscLogQualityModel(
        LogData(),
        _context(
            {"MOT_PWM_TYPE": 3.0, "SCR_ENABLE": 1.0},
            apm_doc={"MOT_PWM_TYPE": {"values": {"3": "PWM", "6": "DShot150"}}},
        ),
    ).check()

    assert result.available is False
    assert result.state == LogQualityState.WARNING
    assert result.issues[0].config_step == "07_esc.param"
    assert "DShot" in result.issues[0].message


def test_battery_model_checks_present_log_data_without_datasource_access() -> None:
    """Present BAT data should be analyzed from in-memory LogData and context values only."""
    log_data = LogData()
    log_data.add_message_columns(
        "BAT",
        np.array(
            [(0.0, 1.0, 1.0)],
            dtype=[("Volt", "f8"), ("Curr", "f8"), ("CurrTot", "f8")],
        ),
    )

    result = BatteryLogQualityModel(log_data, _context({"BATT_MONITOR": 4.0})).check()

    assert result.available is True
    assert result.state == LogQualityState.WARNING
    assert any("Voltage is zero" in issue.message for issue in result.issues)


def test_esc_analysis_does_not_report_zero_error_rates_as_findings() -> None:
    """A healthy ESC log should have no error-rate findings."""
    log_data = LogData()
    log_data.add_message_columns(
        "ESC",
        np.array(
            [(0.0, 0.0, 1_000_000.0), (1.0, 0.0, 2_000_000.0)],
            dtype=[("Instance", "f8"), ("Err", "f8"), ("TimeUS", "f8")],
        ),
    )

    outcomes = EscLogAnalysis(log_data, _context({})).check_per_instance_errors()

    assert outcomes == []


def test_esc_analysis_ignores_a_single_zero_rpm_sample() -> None:
    """A sparse zero-RPM sample must not be described as a full armed-period failure."""
    log_data = LogData()
    log_data.add_message_columns(
        "ARM",
        np.array([(1.0, 0.0), (0.0, 2_000_000.0)], dtype=[("ArmState", "f8"), ("TimeUS", "f8")]),
    )
    log_data.add_message_columns(
        "ESC",
        np.array([(0.0, 0.0, 1_000_000.0)], dtype=[("Instance", "f8"), ("RPM", "f8"), ("TimeUS", "f8")]),
    )

    outcomes = EscLogAnalysis(log_data, _context({})).check_rpm_while_armed()

    assert outcomes == []
