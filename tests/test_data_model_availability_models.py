#!/usr/bin/env python3

"""
Tests for log-analysis availability domain models.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_availability_battery import (
    BatteryLogAnalysis,
    BatteryLogAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_availability_esc import EscLogAnalysis, EscLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_gnss import GPSLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_pm import PmLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData


def _esc_log(
    records: list[tuple[float, float, float, float, float]],
    arm_events: list[tuple[float, float]] | None = None,
) -> LogData:
    """Build real ESC columns in canonical seconds, RPM, amps and percent."""
    log = LogData()
    log.add_message_columns(
        "ESC",
        np.array(records, dtype=[("Instance", "f8"), ("TimeUS", "f8"), ("RPM", "f8"), ("Curr", "f8"), ("Err", "f8")]),
    )
    if arm_events is not None:
        log.add_message_columns("ARM", np.array(arm_events, dtype=[("ArmState", "f8"), ("TimeUS", "f8")]))
    return log


def _esc_context(parameters: dict[str, float]) -> LogAnalysisContext:
    """Resolve ESC findings against realistic parameter and configuration metadata."""
    context = _context(
        parameters,
        apm_doc={
            "MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot150", "9": "DShot600"}},
            "SERVO_DSHOT_RATE": {
                "values": {
                    "0": "1kHz",
                    "1": "loop-rate",
                    "2": "double loop-rate",
                    "3": "triple loop-rate",
                    "4": "quadruple loop rate",
                }
            },
        },
    )
    context.configuration_steps["07_esc.param"]["derived_parameters"].update(
        dict.fromkeys(("MOT_SPIN_ARM", "MOT_SPIN_MIN", "SERVO_DSHOT_RATE", "SCR_ENABLE"), 0.0)
    )
    return context


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
    result = BatteryLogAvailabilityModel(
        LogData(),
        _context(
            {"LOG_BITMASK": 0.0, "BATT_MONITOR": 4.0},
            apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "9:Battery Monitor"}}},
        ),
    ).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert result.issues[0].config_step == "05_battery.param"
    assert "LOG_BITMASK" in result.issues[0].message


def test_gps_model_uses_apm_doc_to_diagnose_disabled_logging() -> None:
    """Missing GPS data should point to LOG_BITMASK when the GPS bit is disabled."""
    result = GPSLogAvailabilityModel(
        LogData(),
        _context(
            {"LOG_BITMASK": 0.0, "GPS_TYPE": 1.0},
            apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "3:GPS"}}},
        ),
    ).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert result.issues[0].config_step == "06_gnss.param"
    assert "GPS logging" in result.reason


def test_esc_model_uses_apm_doc_to_detect_non_dshot_configuration() -> None:
    """Missing ESC data should recommend DShot when MOT_PWM_TYPE is not one of the documented DShot values."""
    result = EscLogAvailabilityModel(
        LogData(),
        _context(
            {"MOT_PWM_TYPE": 3.0, "SCR_ENABLE": 1.0},
            apm_doc={"MOT_PWM_TYPE": {"values": {"3": "PWM", "6": "DShot150"}}},
        ),
    ).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert result.issues[0].config_step == "07_esc.param"
    assert result.reason == "ESC telemetry not logged"
    assert result.issues[0].message == "Set MOT_PWM_TYPE to a DShot variant for ESC telemetry support"


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

    result = BatteryLogAvailabilityModel(log_data, _context({"BATT_MONITOR": 4.0})).check()

    assert result.available is True
    assert result.state == LogAvailabilityState.WARNING
    assert any("Voltage is zero" in issue.message for issue in result.issues)


def test_battery_model_rejects_non_finite_telemetry_values() -> None:
    """NaN telemetry must not be reported as healthy battery data."""
    log_data = LogData()
    log_data.add_message_columns(
        "BAT",
        np.array(
            [(np.nan, np.nan, np.nan)],
            dtype=[("Volt", "f8"), ("Curr", "f8"), ("CurrTot", "f8")],
        ),
    )

    result = BatteryLogAvailabilityModel(log_data, _context({"BATT_MONITOR": 4.0})).check()

    assert result.available is True
    assert result.state == LogAvailabilityState.WARNING
    assert len(result.issues) == 3
    assert all("non-finite telemetry values" in issue.message for issue in result.issues)


def test_battery_model_checks_failsafes_for_each_enabled_monitor() -> None:
    """An enabled secondary monitor must not bypass its own voltage failsafes."""
    log_data = LogData()
    log_data.add_message_columns(
        "BAT",
        np.array([(22.0, 1.0, 0.1)], dtype=[("Volt", "f8"), ("Curr", "f8"), ("CurrTot", "f8")]),
    )

    result = BatteryLogAvailabilityModel(
        log_data,
        _context({"BATT_MONITOR": 4.0, "BATT2_MONITOR": 4.0, "BATT2_LOW_VOLT": 0.0, "BATT2_CRT_VOLT": 0.0}),
    ).check()

    assert result.state == LogAvailabilityState.WARNING
    assert [issue.message for issue in result.issues] == [
        "Battery 2: low-voltage failsafe threshold disabled",
        "Battery 2: critical-voltage failsafe threshold disabled",
    ]


def test_pm_model_accepts_valid_legacy_schema_without_internal_error_fields() -> None:
    """Older PM schemas do not contain the current InE and ErC fields."""
    log_data = LogData()
    log_data.add_message_columns(
        "PM",
        np.array([(20.0, 10_000.0, 0.0)], dtype=[("Load", "f8"), ("Mem", "f8"), ("NLon", "f8")]),
    )

    result = PmLogAvailabilityModel(log_data, _context({})).check()

    assert result.state == LogAvailabilityState.INFO


def test_battery_capacity_uses_canonical_amp_hours() -> None:
    """A mAh capacity parameter must be converted before comparison with scaled CurrTot."""
    log_data = LogData()
    log_data.add_message_columns(
        "BAT",
        np.array([(0.5, 1.0)], dtype=[("CurrTot", "f8"), ("TimeUS", "f8")]),
    )

    outcomes = BatteryLogAnalysis(log_data, _context({"BATT_CAPACITY": 1000.0})).check_battery_capacity_retention()

    assert len(outcomes) == 1
    assert outcomes[0].value == 50.0
    assert outcomes[0].timestamp_us == 1_000_000.0


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

    assert not outcomes


def test_esc_analysis_ignores_a_single_zero_rpm_sample() -> None:
    """A sparse zero-RPM sample must not be described as a full armed-period failure."""
    log_data = LogData()
    log_data.add_message_columns(
        "ARM",
        np.array([(1.0, 0.0), (0.0, 2.0)], dtype=[("ArmState", "f8"), ("TimeUS", "f8")]),
    )
    log_data.add_message_columns(
        "ESC",
        np.array([(0.0, 0.0, 1.0)], dtype=[("Instance", "f8"), ("RPM", "f8"), ("TimeUS", "f8")]),
    )

    outcomes = EscLogAnalysis(log_data, _context({})).check_rpm_while_armed()

    assert not outcomes


def test_esc_analysis_skips_dshot_rate_for_pwm_output() -> None:
    """A SERVO_DSHOT_RATE parameter must not trigger findings when PWM outputs are active."""
    model = EscLogAnalysis(
        LogData(),
        _context(
            {"MOT_PWM_TYPE": 0.0, "SCHED_LOOP_RATE": 400.0, "SERVO_DSHOT_RATE": 1.0},
            apm_doc={
                "MOT_PWM_TYPE": {"values": {"0": "Normal", "4": "DShot150"}},
                "SERVO_DSHOT_RATE": {"values": {"1": "loop-rate"}},
            },
        ),
    )

    assert not model.check_dshot_output_rate()


@pytest.mark.parametrize("error", [0.0, 0.25, 2.5])
def test_esc_availability_checks_all_present_fields_and_reports_errors(error: float) -> None:
    """
    Distinguish usable ESC telemetry from logged ESC errors.

    GIVEN complete ESC records with a healthy first instance and a second instance's error rate,
    WHEN availability is checked,
    THEN data stays available and only a positive error rate produces a configuration-linked warning.
    """
    log = _esc_log([(2, 1, 1200, 3, 0), (9, 2, 1300, 4, error)])

    result = EscLogAvailabilityModel(log, _esc_context({})).check()

    assert result.available is True
    assert result.name == "ESC"
    assert result.state == (LogAvailabilityState.WARNING if error else LogAvailabilityState.INFO)
    if error:
        assert [(issue.message, issue.config_step) for issue in result.issues] == [
            ("ESC error rate detected on at least one ESC instance", "07_esc.param")
        ]
        assert result.reason == "ESC data has availability issues"
    else:
        assert not result.issues
        assert result.reason == "ESC data present and good for analysis"


@pytest.mark.parametrize("field", ["RPM", "Curr", "Err"])
def test_esc_availability_explains_legacy_missing_fields(field: str) -> None:
    """
    Identify the precise missing telemetry field in a legacy ESC schema.

    GIVEN an ESC record lacking one required field,
    WHEN availability is checked,
    THEN the report keeps the data available but explains that field's schema limitation.
    """
    log = _esc_log([(2, 1, 1200, 3, 0)])
    columns = log.get_message_columns("ESC")
    assert columns is not None
    names = columns.dtype.names
    assert names is not None
    log.add_message_columns("ESC", columns[[name for name in names if name != field]])

    result = EscLogAvailabilityModel(log, _esc_context({})).check()

    assert result.available is True
    assert result.state == LogAvailabilityState.WARNING
    assert [issue.message for issue in result.issues] == [f"{field} field not present in this firmware's ESC schema"]


@pytest.mark.parametrize("empty_records", [False, True])
@pytest.mark.parametrize(
    ("parameters", "reason", "message", "step"),
    [
        (
            {"MOT_PWM_TYPE": 6.0, "SCR_ENABLE": 0.0},
            "ESC telemetry not logged, scripting is disabled",
            "Enable SCR_ENABLE if using scripted ESC telemetry",
            "07_esc.param",
        ),
        (
            {"MOT_PWM_TYPE": 9.0, "SCR_ENABLE": 1.0},
            "ESC telemetry not logged, check ESC hardware supports telemetry and is wired correctly",
            "No ESC messages found",
            "07_esc.param",
        ),
        (
            {},
            "ESC telemetry not logged, check ESC hardware supports telemetry and is wired correctly",
            "No ESC messages found",
            "07_esc.param",
        ),
    ],
)
def test_missing_esc_data_reports_the_relevant_configuration_or_hardware_hint(
    empty_records: bool, parameters: dict[str, float], reason: str, message: str, step: str
) -> None:
    """
    Diagnose missing telemetry for both absent and empty ESC streams.

    GIVEN documented DShot outputs, disabled scripting, or unknown configuration,
    WHEN no ESC samples were logged,
    THEN availability reports the appropriate cause and its configuration step.
    """
    log = _esc_log([]) if empty_records else LogData()

    result = EscLogAvailabilityModel(log, _esc_context(parameters)).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert result.name == "ESC"
    assert result.reason == reason
    assert [(issue.message, issue.config_step) for issue in result.issues] == [(message, step)]


@pytest.mark.parametrize("empty_records", [False, True])
def test_esc_analysis_without_samples_has_no_findings(empty_records: bool) -> None:
    """
    Explain why detailed ESC analysis cannot proceed without samples.

    GIVEN an absent or empty ESC stream,
    WHEN detailed analysis runs,
    THEN the result is unavailable with an explicit reason and no speculative findings.
    """
    log = _esc_log([]) if empty_records else LogData()

    assert EscLogAnalysis(log, _esc_context({})).analyse() == LogAnalysisResult(
        available=False, outcomes=[], name="ESC Analysis", reason="No ESC data available"
    )


@pytest.mark.parametrize("spin_min", [0.12, 0.129, 0.129999999, 0.13, 0.14])
def test_motor_spin_margin_preserves_tolerance_and_suggests_the_required_minimum(spin_min: float) -> None:
    """
    Recommend a spin minimum only when the motor-spin margin is meaningfully too small.

    GIVEN MOT_SPIN_ARM of 0.1 and a spin minimum below, near, at, or above the required margin,
    WHEN motor-spin settings are checked,
    THEN only a real deficit produces an accurately valued fix in the ESC configuration step.
    """
    outcomes = EscLogAnalysis(
        LogData(), _esc_context({"MOT_SPIN_ARM": 0.1, "MOT_SPIN_MIN": spin_min})
    ).check_motor_spin_spread()

    if spin_min >= 0.129999999:
        assert not outcomes
    else:
        assert len(outcomes) == 1
        finding = outcomes[0]
        assert finding.param_name == "MOT_SPIN_MIN"
        assert finding.suggested_value == pytest.approx(0.13)
        assert finding.value == pytest.approx(-0.01 if spin_min == 0.12 else -0.001)
        assert finding.timestamp_us is None
        assert finding.related_step == "07_esc.param"
        assert finding.message == (
            f"MOT_SPIN_MIN ({spin_min:.3f}) is below MOT_SPIN_ARM + 0.03 (0.130). "
            "AMC's tuning guide requires MOT_SPIN_MIN to be at least 0.03 above MOT_SPIN_ARM "
            "(0.100). Motors may not spin reliably once armed."
        )


@pytest.mark.parametrize("parameters", [{}, {"MOT_SPIN_ARM": 0.1}, {"MOT_SPIN_MIN": 0.12}])
def test_motor_spin_margin_requires_both_settings(parameters: dict[str, float]) -> None:
    """
    Avoid inventing a motor-spin fix when a required setting is unknown.

    GIVEN one or both motor-spin settings are absent,
    WHEN the margin is checked,
    THEN no finding or suggested parameter change is produced.
    """
    assert not EscLogAnalysis(LogData(), _esc_context(parameters)).check_motor_spin_spread()


def test_esc_error_peaks_keep_instance_identity_time_and_first_tied_peak() -> None:
    """
    Attribute each positive error peak to the correct ESC and timestamp.

    GIVEN interleaved, unsorted instances with unequal peaks, tied peaks, and a healthy ESC,
    WHEN per-instance errors are checked,
    THEN findings are ordered by instance and report each peak's first actual occurrence.
    """
    log = _esc_log(
        [
            (9, 1.25, 1000, 2, 2),
            (2, 1.5, 1000, 2, 0.5),
            (7, 2, 1000, 2, 0),
            (9, 3.75, 1000, 2, 8),
            (2, 4.5, 1000, 2, 0.5),
        ]
    )

    assert EscLogAnalysis(log, _esc_context({})).check_per_instance_errors() == [
        LogAnalysis("ESC output 2 peak error rate: 0.5%", timestamp_us=1_500_000.0, value=0.5),
        LogAnalysis("ESC output 9 peak error rate: 8.0%", timestamp_us=3_750_000.0, value=8.0),
    ]


@pytest.mark.parametrize("field", ["Instance", "TimeUS", "RPM", "Curr", "Err"])
def test_esc_checks_skip_schemas_missing_their_required_fields(field: str) -> None:
    """
    Tolerate older schemas without accessing unavailable telemetry fields.

    GIVEN an ESC record missing one field needed by a detailed check,
    WHEN that check runs,
    THEN it returns no finding rather than failing or assuming a value.
    """
    log = _esc_log([(2, 3, 0, 1, 2)], [(1, 2), (0, 6)])
    columns = log.get_message_columns("ESC")
    assert columns is not None
    names = columns.dtype.names
    assert names is not None
    log.add_message_columns("ESC", columns[[name for name in names if name != field]])
    model = EscLogAnalysis(log, _esc_context({}))

    if field in {"Instance", "TimeUS", "RPM"}:
        assert not model.check_rpm_while_armed()
    if field in {"Instance", "TimeUS", "Curr"}:
        assert not model.check_current_imbalance()
    if field in {"Instance", "TimeUS", "Err"}:
        assert not model.check_per_instance_errors()


@pytest.mark.parametrize(
    ("code", "loop_rate", "expected_rate"),
    [
        (0, 2000, 1000),
        (1, 400, 400),
        (1, 1000, 1000),
        (1, 1001, None),
        (2, 500, 1000),
        (2, 501, None),
        (3, 300, 900),
        (3, 400, None),
        (4, 250, 1000),
        (4, 400, None),
    ],
)
def test_dshot_rate_uses_documented_multipliers_and_warns_at_the_exact_boundary(
    code: float, loop_rate: float, expected_rate: float | None
) -> None:
    """
    Compute DShot rates from metadata and include the exact warning boundary.

    GIVEN a fixed 1 kHz rate or a documented loop-rate multiplier,
    WHEN the effective DShot rate is checked,
    THEN rates at or below 1000 Hz produce an actionable finding with the calculated rate.
    """
    context = _esc_context({"MOT_PWM_TYPE": 6.0, "SCHED_LOOP_RATE": loop_rate, "SERVO_DSHOT_RATE": code})

    outcomes = EscLogAnalysis(LogData(), context).check_dshot_output_rate()

    if expected_rate is None:
        assert not outcomes
    else:
        assert len(outcomes) == 1
        finding = outcomes[0]
        assert finding.value == expected_rate
        assert finding.timestamp_us is None
        assert finding.param_name == "SERVO_DSHOT_RATE"
        assert finding.related_step == "07_esc.param"
        assert context.apm_doc is not None
        label = context.apm_doc["SERVO_DSHOT_RATE"]["values"][str(code)]
        assert finding.message == (
            f"Effective DShot output rate is {expected_rate:.0f}Hz (SCHED_LOOP_RATE={loop_rate:.0f}Hz, "
            f"SERVO_DSHOT_RATE={label!r}), at or below the 1000Hz level Amilcar flagged as "
            "problematic. apm.pdef.xml also states SERVO_DSHOT_RATE should never be set below 500Hz."
        )


@pytest.mark.parametrize("missing", ["MOT_PWM_TYPE", "SCHED_LOOP_RATE", "SERVO_DSHOT_RATE", "metadata"])
def test_dshot_rate_requires_complete_parameters_and_metadata(missing: str) -> None:
    """
    Avoid a DShot-rate warning based on incomplete configuration.

    GIVEN one required parameter or its documentation is missing,
    WHEN effective output rate is checked,
    THEN no unsupported calculation or finding is produced.
    """
    context = _esc_context({"MOT_PWM_TYPE": 6.0, "SCHED_LOOP_RATE": 400.0, "SERVO_DSHOT_RATE": 1.0})
    if missing == "metadata":
        context.apm_doc = None
    else:
        del context.parameters[missing]

    assert not EscLogAnalysis(LogData(), context).check_dshot_output_rate()


@pytest.mark.parametrize("label", [None, "unrecognized-rate", "DOUBLE LOOP-RATE"])
def test_dshot_metadata_handles_unknown_labels_and_case_insensitive_known_labels(label: str | None) -> None:
    """
    Resolve enum labels without guessing the meaning of unknown values.

    GIVEN a DShot rate with absent, unknown, or uppercase metadata,
    WHEN its output rate is checked,
    THEN unknown labels are skipped and a known uppercase label uses its documented multiplier.
    """
    context = _esc_context({"MOT_PWM_TYPE": 9.0, "SCHED_LOOP_RATE": 400.0, "SERVO_DSHOT_RATE": 8.0})
    assert context.apm_doc is not None
    context.apm_doc["SERVO_DSHOT_RATE"]["values"] = {} if label is None else {"8": label}

    outcomes = EscLogAnalysis(LogData(), context).check_dshot_output_rate()

    if label == "DOUBLE LOOP-RATE":
        assert len(outcomes) == 1
        assert outcomes[0].value == 800.0
        assert "'DOUBLE LOOP-RATE'" in outcomes[0].message
    else:
        assert not outcomes


@pytest.mark.parametrize(
    ("currents", "expected_instances", "expected_means", "expected_times", "median"),
    [
        ([10, 10, 10, 30], [4], [30], [5_000_000], 10),
        ([1, 10, 10, 10], [9], [1], [3_000_000], 10),
        ([10, 10, 11], [7], [11], [5_000_000], 10),
        ([1, 2, 10, 10, 11], [9, 2], [1, 2], [3_000_000, 3_000_000], 10),
    ],
)
def test_current_imbalance_identifies_the_smaller_group_and_its_most_extreme_armed_sample(
    currents: list[float], expected_instances: list[int], expected_means: list[float], expected_times: list[int], median: float
) -> None:
    """
    Separate high and low current outliers without mixing ESC identities or disarmed data.

    GIVEN interleaved ESCs with an outlying minority and extreme disarmed samples,
    WHEN current imbalance is analysed,
    THEN only the minority is reported with its armed mean and most extreme armed timestamp.
    """
    identities = [9, 2, 7, 4, 12]
    records = [
        (identity, time, 1000, current, 0)
        for time in (1, 3, 5, 7)
        for identity, mean in zip(identities, currents, strict=False)
        for current in [mean - 1 if time == 3 else mean + 1 if time == 5 else 9999]
    ]
    log = _esc_log(records, [(1, 2), (0, 6)])

    outcomes = EscLogAnalysis(log, _esc_context({})).check_current_imbalance()

    assert outcomes == [
        LogAnalysis(
            f"ESC output {instance} drew {mean:.2f}A on average, "
            f"current drawn by the other {len(currents) - len(expected_instances)} ESC output(s) (median {median:.2f}A). "
            "If unexpected for this vehicle's configuration, check for a mechanical or wiring issue.",
            timestamp_us=timestamp,
            value=mean,
        )
        for instance, mean, timestamp in zip(expected_instances, expected_means, expected_times, strict=True)
    ]


@pytest.mark.parametrize("currents", [[10, 10], [10, 10, 10], [0, 5, 10], [1, 1, 10, 10]])
def test_current_imbalance_requires_a_separated_minority_of_at_least_three_observed_escs(currents: list[float]) -> None:
    """
    Avoid speculative current-imbalance findings for balanced or ambiguous groups.

    GIVEN too few ESCs, equal currents, equal gaps, or two equally sized groups,
    WHEN current imbalance is checked,
    THEN no minority-outlier finding is produced.
    """
    log = _esc_log([(instance, 3, 1000, current, 0) for instance, current in enumerate(currents)], [(1, 2), (0, 6)])

    assert not EscLogAnalysis(log, _esc_context({})).check_current_imbalance()


@pytest.mark.parametrize("arm_events", [None, [(1, 2), (0, 6)]])
def test_current_imbalance_requires_armed_samples_from_every_instance(arm_events: list[tuple[float, float]] | None) -> None:
    """
    Reject an incomplete comparison of ESC current means.

    GIVEN no armed interval or an ESC observed only before arming,
    WHEN current imbalance is checked,
    THEN no finding compares a partial set of ESC outputs.
    """
    log = _esc_log([(2, 3, 1000, 10, 0), (7, 3, 1000, 10, 0), (9, 1, 1000, 1, 0)], arm_events)

    assert not EscLogAnalysis(log, _esc_context({})).check_current_imbalance()


def test_current_imbalance_combines_all_armed_windows_without_counting_disarmed_samples() -> None:
    """
    Include every armed interval in the ESC current comparison.

    GIVEN two flights separated by a disarmed interval with misleading current values,
    WHEN currents are compared,
    THEN both flights contribute to the means and the disarmed interval contributes nothing.
    """
    log = _esc_log(
        [
            (2, 2, 1000, 10, 0),
            (7, 2, 1000, 10, 0),
            (9, 2, 1000, 0, 0),
            (2, 4, 1000, 0, 0),
            (7, 4, 1000, 0, 0),
            (9, 4, 1000, 1000, 0),
            (2, 6, 1000, 10, 0),
            (7, 6, 1000, 10, 0),
            (9, 6, 1000, 20, 0),
        ],
        [(1, 1), (0, 3), (1, 5), (0, 7)],
    )

    assert not EscLogAnalysis(log, _esc_context({})).check_current_imbalance()


@pytest.mark.parametrize(
    ("sample_times", "armed_end", "warn"),
    [
        ([2.0, 3.0], 4.0, True),
        ([2.0, 3.0], 3.0, True),
        ([2.0, 2.999], 4.0, False),
        ([2.0, 3.0], 4.001, False),
        ([2.0, 4.0], 4.0, True),
        ([2.5], 4.0, False),
    ],
)
def test_zero_rpm_warning_requires_one_second_and_half_the_armed_interval(
    sample_times: list[float], armed_end: float, warn: bool
) -> None:
    """
    Require sustained zero RPM with adequate coverage of the armed interval.

    GIVEN zero samples spanning the exact observation and coverage boundaries,
    WHEN armed-period RPM is checked,
    THEN only sufficiently long, sufficiently complete observations trigger a warning.
    """
    log = _esc_log([(7, timestamp, 0, 1, 0) for timestamp in sample_times], [(1, 2), (0, armed_end)])

    outcomes = EscLogAnalysis(log, _esc_context({})).check_rpm_while_armed()

    if warn:
        assert outcomes == [
            LogAnalysis(
                f"ESC output 7 reported zero RPM throughout an armed period (2.0s to {armed_end:.1f}s), "
                "the motor may not have responded.",
                timestamp_us=2_000_000.0,
                value=0.0,
            )
        ]
    else:
        assert not outcomes


def test_zero_rpm_is_isolated_by_instance_and_armed_window() -> None:
    """
    Ignore disarmed zero RPM and moving motors while preserving stalled-motor findings.

    GIVEN interleaved ESC outputs before, during, and after arming,
    WHEN RPM is analysed,
    THEN only the ESC that remained stopped throughout the armed window is reported.
    """
    log = _esc_log(
        [
            (2, 1, 0, 1, 0),
            (2, 2, 0, 1, 0),
            (2, 4, 1000, 1, 0),
            (2, 5, 0, 1, 0),
            (7, 2, 0, 1, 0),
            (7, 4, 0, 1, 0),
            (9, 1, 0, 1, 0),
            (9, 5, 0, 1, 0),
        ],
        [(1, 2), (0, 4)],
    )

    assert EscLogAnalysis(log, _esc_context({})).check_rpm_while_armed() == [
        LogAnalysis(
            "ESC output 7 reported zero RPM throughout an armed period (2.0s to 4.0s), the motor may not have responded.",
            timestamp_us=2_000_000.0,
            value=0.0,
        )
    ]


@pytest.mark.parametrize("field", ["ArmState", "TimeUS"])
def test_armed_rpm_check_skips_an_incomplete_arm_schema(field: str) -> None:
    """
    Avoid assuming armed periods when transition metadata is incomplete.

    GIVEN ARM records missing a transition state or timestamp,
    WHEN zero-RPM analysis is requested,
    THEN no warning is produced from an invented armed window.
    """
    log = _esc_log([(7, 2, 0, 1, 0), (7, 4, 0, 1, 0)], [(1, 2), (0, 4)])
    columns = log.get_message_columns("ARM")
    assert columns is not None
    names = columns.dtype.names
    assert names is not None
    log.add_message_columns("ARM", columns[[name for name in names if name != field]])

    assert not EscLogAnalysis(log, _esc_context({})).check_rpm_while_armed()


def test_unclosed_armed_window_ends_at_the_last_arm_timestamp() -> None:
    """
    Retain an armed interval even when the log ends before disarming.

    GIVEN repeated armed messages without a matching disarm,
    WHEN zero RPM is analysed,
    THEN the original arm time and the final transition timestamp bound the warning.
    """
    log = _esc_log([(7, 2, 0, 1, 0), (7, 4, 0, 1, 0)], [(0, 1), (1, 2), (1, 4)])

    assert EscLogAnalysis(log, _esc_context({})).check_rpm_while_armed() == [
        LogAnalysis(
            "ESC output 7 reported zero RPM throughout an armed period (2.0s to 4.0s), the motor may not have responded.",
            timestamp_us=2_000_000.0,
            value=0.0,
        )
    ]


def test_complete_esc_analysis_combines_independent_findings_and_configuration_links() -> None:
    """
    Return a coherent detailed analysis with every applicable ESC check included.

    GIVEN present ESC data, zero armed RPM, positive errors, and deficient spin and output-rate settings,
    WHEN the complete analysis runs,
    THEN each independent issue appears once with the correct report identity and step.
    """
    log = _esc_log(
        [(7, 2, 0, 2, 3), (2, 2, 1000, 10, 0), (9, 2, 1000, 10, 0), (7, 4, 0, 2, 5), (2, 4, 1000, 10, 0), (9, 4, 1000, 10, 0)],
        [(1, 2), (0, 4)],
    )
    context = _esc_context(
        {"MOT_SPIN_ARM": 0.1, "MOT_SPIN_MIN": 0.12, "MOT_PWM_TYPE": 6.0, "SCHED_LOOP_RATE": 400.0, "SERVO_DSHOT_RATE": 1.0}
    )

    result = EscLogAnalysis(log, context).analyse()

    assert result.available is True
    assert result.name == "ESC Analysis"
    assert result.reason == "ESC analysis complete"
    assert result.related_step == "07_esc.param"
    assert len(result.outcomes) == 5
    assert [finding.param_name for finding in result.outcomes] == ["MOT_SPIN_MIN", None, None, None, "SERVO_DSHOT_RATE"]
    assert [finding.value for finding in result.outcomes] == pytest.approx([-0.01, 5, 0, 2, 400])
    assert [finding.timestamp_us for finding in result.outcomes] == [None, 4_000_000.0, 2_000_000.0, 2_000_000.0, None]


def test_fixed_dshot_rate_is_not_interpreted_as_a_loop_multiplier() -> None:
    """
    Keep the fixed 1 kHz output rate separate from loop-rate multipliers.

    GIVEN documentation identifying an enum value as a fixed 1 kHz rate,
    WHEN its loop multiplier is requested,
    THEN no multiplier is returned, allowing the fixed-rate calculation to apply.
    """
    model = EscLogAnalysis(LogData(), _esc_context({}))

    assert model._dshot_rate_multiplier(0.0) is None  # pylint: disable=protected-access


@pytest.mark.parametrize(
    ("method", "message"),
    [
        ("check_rpm", "RPM values missing from ESC records"),
        ("check_current", "Current values missing from ESC records"),
        ("check_error_rate", "ESC error values missing from ESC records"),
    ],
)
def test_individual_esc_field_checks_explain_a_schema_with_no_samples(method: str, message: str) -> None:
    """
    Distinguish an empty telemetry field from an unsupported firmware schema.

    GIVEN an ESC schema with all required fields but no records,
    WHEN a field-specific check is requested,
    THEN its issue explains that values are missing rather than the field itself.
    """
    model = EscLogAvailabilityModel(_esc_log([]), _esc_context({}))

    issues = getattr(model, method)()

    assert len(issues) == 1
    assert issues[0].message == message
    assert issues[0].config_step == ""


@pytest.mark.parametrize("metadata", [None, {}])
def test_absent_esc_metadata_still_produces_an_actionable_fallback_report(metadata: dict | None) -> None:
    """
    Keep ESC absence diagnostics readable without optional metadata.

    GIVEN no parameter documentation and no matching configuration step,
    WHEN an ESC stream is absent,
    THEN the fallback ESC name and hardware hint remain available.
    """
    context = _esc_context({})
    context.apm_doc = metadata
    context.configuration_steps = {}

    result = EscLogAvailabilityModel(LogData(), context).check()

    assert result.available is False
    assert result.name == "ESC"
    assert result.reason == "ESC telemetry not logged, check ESC hardware supports telemetry and is wired correctly"
    assert [(issue.message, issue.config_step) for issue in result.issues] == [("No ESC messages found", "")]


def test_current_imbalance_reports_a_mean_across_multiple_armed_intervals() -> None:
    """
    Combine samples from separate flights when calculating an ESC's mean current.

    GIVEN a low-current ESC with different means at the ends of two armed intervals,
    WHEN imbalance is analysed,
    THEN the reported mean uses both intervals and the timestamp identifies the most extreme sample.
    """
    log = _esc_log(
        [
            (2, 3, 1000, 10, 0),
            (7, 3, 1000, 10, 0),
            (9, 3, 1000, 0, 0),
            (2, 7, 1000, 14, 0),
            (7, 7, 1000, 14, 0),
            (9, 7, 1000, 2, 0),
        ],
        [(1, 1), (0, 3), (1, 5), (0, 7)],
    )

    assert EscLogAnalysis(log, _esc_context({})).check_current_imbalance() == [
        LogAnalysis(
            "ESC output 9 drew 1.00A on average, current drawn by the other 2 ESC output(s) (median 12.00A). "
            "If unexpected for this vehicle's configuration, check for a mechanical or wiring issue.",
            timestamp_us=3_000_000.0,
            value=1.0,
        )
    ]


@pytest.mark.parametrize("method", ["check_per_instance_errors", "check_current_imbalance", "check_rpm_while_armed"])
def test_individual_esc_analysis_checks_tolerate_an_absent_esc_stream(method: str) -> None:
    """
    Safely skip an individual detailed check when ESC data was never recorded.

    GIVEN valid ARM transitions but no ESC stream,
    WHEN an individual ESC check is requested,
    THEN it returns no findings instead of accessing a nonexistent schema.
    """
    log = LogData()
    log.add_message_columns("ARM", np.array([(1, 2), (0, 4)], dtype=[("ArmState", "f8"), ("TimeUS", "f8")]))

    assert not getattr(EscLogAnalysis(log, _esc_context({})), method)()


def test_zero_rpm_in_a_later_flight_is_reported_when_the_esc_was_not_observed_in_the_first() -> None:
    """
    Continue looking for stalled ESCs after an armed interval without samples.

    GIVEN no ESC observations in the first flight and sustained zero RPM in the second,
    WHEN armed RPM is checked,
    THEN the second flight still produces its correctly timed warning.
    """
    log = _esc_log([(7, 5, 0, 1, 0), (7, 7, 0, 1, 0)], [(1, 1), (0, 3), (1, 5), (0, 7)])

    assert EscLogAnalysis(log, _esc_context({})).check_rpm_while_armed() == [
        LogAnalysis(
            "ESC output 7 reported zero RPM throughout an armed period (5.0s to 7.0s), the motor may not have responded.",
            timestamp_us=5_000_000.0,
            value=0.0,
        )
    ]


@pytest.mark.parametrize(
    ("events", "windows"),
    [([], []), ([(0, 1)], []), ([(1, 0)], [(0.0, 0.0)]), ([(1, 0), (1, 1), (0, 2)], [(0.0, 2.0)])],
)
def test_arm_windows_preserve_initial_zero_timestamps_and_single_unclosed_transitions(
    events: list[tuple[float, float]], windows: list[tuple[float, float]]
) -> None:
    """
    Build armed windows without treating timestamp zero as a missing arm event.

    GIVEN empty, disarmed, singly armed, or repeated ARM transitions,
    WHEN canonical armed intervals are requested,
    THEN only armed periods are returned and zero-valued timestamps remain valid.
    """
    model = EscLogAnalysis(_esc_log([], events), _esc_context({}))

    assert model._armed_time_windows() == windows  # pylint: disable=protected-access


@pytest.mark.parametrize("registered_step", [False, True])
def test_present_esc_report_uses_the_configured_display_name_or_its_fallback(registered_step: bool) -> None:
    """
    Name a present ESC stream using its configuration metadata when available.

    GIVEN a custom ESC display name or no registered step,
    WHEN healthy telemetry availability is checked,
    THEN the report uses that configured name or the stable ESC fallback in both title and reason.
    """
    context = _esc_context({})
    if registered_step:
        context.configuration_steps["07_esc.param"]["related_bin_messages"]["ESC"]["name"] = "Motor telemetry"
    else:
        context.configuration_steps = {}
    expected_name = "Motor telemetry" if registered_step else "ESC"

    result = EscLogAvailabilityModel(_esc_log([(7, 1, 1000, 2, 0)]), context).check()

    assert result.available is True
    assert result.state == LogAvailabilityState.INFO
    assert result.name == expected_name
    assert result.reason == f"{expected_name} data present and good for analysis"
    assert not result.issues
