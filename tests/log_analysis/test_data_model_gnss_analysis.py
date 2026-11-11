#!/usr/bin/env python3
"""
Behavior tests for receiver interference and GPS/inertial consistency analysis.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from dataclasses import asdict
from pathlib import Path

import jsonschema
import numpy as np
import pytest

# pytest fixtures intentionally share their names with test arguments.
# pylint: disable=redefined-outer-name,too-many-lines
from ardupilot_methodic_configurator.log_analysis.data_model_availability_gnss import GPSLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_consistency import (
    GnssConsistencyChecks,
    _body_to_ned,
    _gps_fix,
    _InertialTrack,
    _interpolate,
    _prediction_residual,
)
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_interference import GPSLogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_samples import SensorSeries, event_intervals
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import analyze_log
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterChange, ParameterHistory


def _add(log: LogData, message: str, **fields: np.ndarray | list[float]) -> None:
    """Populate real canonical numeric log columns without mocking the analysis."""
    columns = np.empty(len(next(iter(fields.values()))), dtype=[(name, "f8") for name in fields])
    for name, values in fields.items():
        columns[name] = values
    log.add_message_columns(message, columns)


def _context() -> LogAnalysisContext:
    return LogAnalysisContext(parameters={}, configuration_steps={}, vehicle_components={})


def _columns(log: LogData, message: str) -> np.ndarray:
    """Require the canonical numeric columns supplied by the test fixture."""
    columns = log.get_message_columns(message)
    assert columns is not None
    return columns


def _evidence(outcome: LogAnalysis) -> dict[str, float]:
    """Require measurement evidence before asserting its contents."""
    assert outcome.evidence is not None
    return outcome.evidence


def _warnings(outcomes: list[LogAnalysis], source: str) -> list[LogAnalysis]:
    return [outcome for outcome in outcomes if outcome.source == source and outcome.severity in ("warning", "critical")]


@pytest.fixture
def motion_log() -> LogData:
    """Ten seconds of stationary healthy level vehicle, with GPS at 2 Hz and IMU at 20 Hz."""
    log = LogData()
    times = np.arange(0, 10.05, 0.05)
    zeros, ones = np.zeros(len(times)), np.ones(len(times))
    _add(
        log,
        "IMU",
        TimeUS=times,
        I=zeros,
        AccX=zeros,
        AccY=zeros,
        AccZ=ones * -9.80665,
        GyrX=zeros,
        GyrY=zeros,
        GyrZ=zeros,
        AH=ones,
        GH=ones,
        EA=zeros,
        EG=zeros,
    )
    _add(log, "ATT", TimeUS=times, Roll=zeros, Pitch=zeros, Yaw=zeros)
    gps_times = np.arange(0, 10.5, 0.5)
    zeros, ones = np.zeros(len(gps_times)), np.ones(len(gps_times))
    _add(
        log,
        "GPS",
        TimeUS=gps_times,
        I=zeros,
        Status=ones * 3,
        Lat=ones * 48,
        Lng=ones * 11,
        Spd=zeros,
        GCrs=zeros,
        VZ=zeros,
        U=ones,
        GWk=ones * 2400,
        GMS=gps_times + 1000,
    )
    _add(log, "GPA", TimeUS=gps_times, I=zeros, HAcc=ones, SAcc=ones * 0.1, VV=ones, SMS=gps_times)
    return log


@pytest.mark.parametrize(
    ("message", "field", "expected"),
    [("AERG", "Jam", "critical"), ("AERG", "Spf", "critical"), ("ILB5", "GSS", "warning"), ("ILB5", "GJS", "critical")],
)
def test_receiver_events_work_without_gps_or_the_other_indicator(message: str, field: str, expected: str) -> None:
    """GIVEN one explicit field only WHEN analyzed THEN the warning survives missing GPS/IMU and sibling fields."""
    log = LogData()
    _add(log, message, TimeUS=[1, 2, 3, 4], **{field: [1, 3, 3, 1]})
    availability = GPSLogAvailabilityModel(log, _context()).check()
    outcomes = GPSLogAnalysis(log, _context()).analyse().outcomes
    events = _warnings(outcomes, f"{message}.{field}")
    assert availability.available
    assert f"{message}.{field}" in availability.reason
    assert len(events) == 1
    assert events[0].severity == expected
    assert events[0].timestamp_us == 2e6
    assert events[0].end_timestamp_us == 3e6
    assert events[0].instance is None
    assert events[0].evidence == {"status": 3.0}


def test_unknown_status_is_not_reported_as_healthy_or_as_a_confirmed_attack() -> None:
    """GIVEN unknown ILB5 status WHEN analyzed THEN its raw value and inability to assess are retained."""
    log = LogData()
    _add(log, "ILB5", TimeUS=[1, 2], GJS=[0, 2])
    outcomes = GPSLogAnalysis(log, _context()).analyse().outcomes
    events = [item for item in outcomes if item.timestamp_us is not None]
    assert len(events) == 2
    assert all(item.severity == "informational" and "Unknown" in item.message for item in events)
    assert [item.evidence for item in events] == [{"status": 0.0}, {"status": 2.0}]


def test_severity_changes_and_gaps_break_receiver_event_intervals() -> None:
    """GIVEN changing status and a missing-data gap WHEN analyzed THEN distinct observed intervals are preserved."""
    log = LogData()
    _add(log, "AERG", TimeUS=[1, 2, 3, 4, 5, 20, 21], Jam=[2, 2, 3, np.nan, 3, 3, 1])
    events = _warnings(GPSLogAnalysis(log, _context()).analyse().outcomes, "AERG.Jam")
    assert [(item.timestamp_us, item.end_timestamp_us, item.severity) for item in events] == [
        (1e6, 2e6, "warning"),
        (3e6, 3e6, "critical"),
        (5e6, 5e6, "critical"),
        (20e6, 20e6, "critical"),
    ]
    issues = GPSLogAvailabilityModel(log, _context()).check().issues
    assert any("coverage is incomplete" in item.message for item in issues)
    assert any("timestamp discontinuities" in item.message for item in issues)


@pytest.mark.parametrize("times", [[1, 1, 2], [2, 1, 2]])
def test_duplicate_or_reversed_timestamps_do_not_extend_event_intervals(times: list[float]) -> None:
    """GIVEN a boot-clock discontinuity WHEN analyzed THEN intervals restart at the discontinuity."""
    log = LogData()
    _add(log, "AERG", TimeUS=times, Jam=[2, 2, 2])
    events = _warnings(GPSLogAnalysis(log, _context()).analyse().outcomes, "AERG.Jam")
    assert len(events) == 2
    assert all(
        item.end_timestamp_us is not None and item.timestamp_us is not None and item.end_timestamp_us >= item.timestamp_us
        for item in events
    )


def test_availability_rejects_non_numeric_or_unusable_explicit_fields() -> None:
    """GIVEN invalid timestamps and values WHEN checking availability THEN no usable indicator is claimed."""
    log = LogData()
    _add(log, "AERG", TimeUS=[np.nan, -1], Jam=[2, 3])
    _add(log, "UBX1", TimeUS=[1, 2], Instance=[-1, np.nan], jamInd=[20, 50])
    log.add_message_columns("ILB5", np.array([(1.0, "bad")], dtype=[("TimeUS", "f8"), ("GSS", "U3")]))
    result = GPSLogAvailabilityModel(log, _context()).check()
    assert not result.available
    assert not _warnings(GPSLogAnalysis(log, _context()).analyse().outcomes, "AERG.Jam")


def test_present_gps_availability_reports_fix_and_configuration_issues() -> None:
    """GIVEN GPS data without a 3D fix and a disabled receiver WHEN availability is checked THEN both issues are explained."""
    log = LogData()
    _add(log, "GPS", TimeUS=[1, 2], Status=[1, 2])
    context = _context()
    context.parameters["GPS1_TYPE"] = 0
    result = GPSLogAvailabilityModel(log, context).check()
    assert result.available
    assert any(item.message == "GPS never achieved a 3D fix" for item in result.issues)
    assert any("not configured" in item.message for item in result.issues)
    assert "explicit jamming/spoofing assessment unavailable" in result.reason


def test_no_timestamped_capability_is_not_reported_as_completed_analysis() -> None:
    """GIVEN GPS records without timestamps WHEN analyzed THEN the assessment is unavailable."""
    log = LogData()
    _add(log, "GPS", Status=[3, 3])
    result = GPSLogAnalysis(log, _context()).analyse()
    assert not result.available
    assert "No supported timestamped GNSS checks" in result.reason


def test_ublox_rise_is_receiver_specific_and_constant_levels_are_not_an_attack() -> None:
    """GIVEN interleaved receivers WHEN one indicator rises THEN only that receiver gets an RF finding."""
    log = LogData()
    times = np.repeat(np.arange(12), 2)
    values = np.array([10, 200] * 12)
    values[14::2] = 100
    _add(log, "UBX1", TimeUS=times, Instance=[0, 1] * 12, jamInd=values)
    events = _warnings(GPSLogAnalysis(log, _context()).analyse().outcomes, "UBX1.jamInd")
    assert len(events) == 1
    assert events[0].instance == 0
    assert events[0].timestamp_us == 7e6
    assert "possible RF interference" in events[0].message
    assert events[0].evidence == {"peak_jamInd": 100.0}


def test_correlations_require_overlapping_events_from_the_same_identified_receiver() -> None:
    """GIVEN different receivers and times WHEN correlated THEN unrelated evidence is never combined."""
    first = LogAnalysis("RF", timestamp_us=1e6, end_timestamp_us=3e6, source="UBX1.jamInd", instance=0)
    other_receiver = LogAnalysis("fix lost", timestamp_us=2e6, source="GPS.Status", instance=1)
    other_time = LogAnalysis("fix lost", timestamp_us=4e6, source="GPS.Status", instance=0)
    matching = LogAnalysis("fix lost", timestamp_us=2e6, end_timestamp_us=4e6, source="GPS.Status", instance=0)
    events = GPSLogAnalysis.correlate_findings([first, other_receiver, other_time, matching])
    assert len(events) == 1
    assert "Suspected jamming" in events[0].message
    assert events[0].timestamp_us == 2e6
    assert events[0].end_timestamp_us == 3e6


def test_default_registry_runs_receiver_analysis_and_event_schema_preserves_evidence() -> None:
    """GIVEN an explicit receiver event WHEN the default analysis runs THEN pairing and report serialization preserve it."""
    log = LogData()
    _add(log, "AERG", TimeUS=[1, 2], Spf=[3, 3])
    summary = analyze_log(log, _context())
    pair = next(pair for pair in summary.paired_availability_and_analysis_results() if pair[0].subsystem_key == "gps")
    assert pair[1] is not None
    event = _warnings(pair[1].outcomes, "AERG.Spf")[0]
    exported = asdict(event) | {"step_info": None, "param_info": None}
    schema_path = Path(__file__).parents[2] / "ardupilot_methodic_configurator/log_analysis/log_analysis_report_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator({"$ref": "#/$defs/analysis_outcome", "$defs": schema["$defs"]}).validate(exported)
    assert json.loads(json.dumps(exported))["evidence"] == {"status": 3.0}


def test_stationary_healthy_motion_produces_no_consistency_warnings(motion_log: LogData) -> None:
    """GIVEN healthy stationary GPS and gravity-only IMU WHEN checked THEN evaluated coverage and no warning are reported."""
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    assert not [item for item in outcomes if item.severity == "warning"]
    coverage = next(item for item in outcomes if item.source == "GPS.IMU")
    assert coverage.evidence == {"evaluated": 20.0, "total": 20.0}


def test_northward_acceleration_matches_gps_velocity_changes(motion_log: LogData) -> None:
    """GIVEN real northward acceleration WHEN compared in NED THEN normal changing speed passes."""
    imu = _columns(motion_log, "IMU")
    gps = _columns(motion_log, "GPS")
    imu["AccX"] = 2.0
    gps["Spd"] = 2.0 * gps["TimeUS"]
    gps["Lat"] += np.rad2deg(gps["TimeUS"] ** 2 / 6371000.0)
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    assert not _warnings(outcomes, "GPS.IMU")
    assert not _warnings(outcomes, "GPS.PositionVelocity")


def test_body_axes_are_rotated_by_attitude_before_comparing_motion(motion_log: LogData) -> None:
    """GIVEN forward acceleration while facing east WHEN compared THEN body X maps to east velocity."""
    _columns(motion_log, "IMU")["AccX"] = 2.0
    _columns(motion_log, "ATT")["Yaw"] = 90.0
    gps = _columns(motion_log, "GPS")
    gps["Spd"] = 2.0 * gps["TimeUS"]
    gps["GCrs"] = 90.0
    assert not _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")


def test_sustained_fabricated_gps_acceleration_conflicts_with_stationary_imu(motion_log: LogData) -> None:
    """GIVEN fabricated GPS acceleration WHEN checked THEN a measured inertial discrepancy is reported."""
    gps = _columns(motion_log, "GPS")
    gps["Spd"] = 20.0 * gps["TimeUS"]
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    events = _warnings(outcomes, "GPS.IMU")
    assert len(events) == 1
    assert events[0].instance == 0
    assert _evidence(events[0])["residual_m_s"] == pytest.approx(10.0)
    assert _evidence(events[0])["tolerance_m_s"] == pytest.approx(3.6)
    assert _warnings(outcomes, "GNSS.Correlation") == []
    assert GPSLogAnalysis.correlate_findings(outcomes)


@pytest.mark.parametrize("field", ["AH", "GH", "EA", "EG", "GyrZ"])
def test_unhealthy_or_fast_rotating_imu_is_excluded_from_motion_checks(motion_log: LogData, field: str) -> None:
    """GIVEN unhealthy sensors or significant lever-arm motion WHEN checked THEN inertial coverage is unavailable."""
    imu = _columns(motion_log, "IMU")
    imu[field] = 0 if field in ("AH", "GH") else 1
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    coverage = next(item for item in outcomes if item.source == "GPS.IMU")
    assert _evidence(coverage)["evaluated"] == 0
    assert not _warnings(outcomes, "GPS.IMU")


def test_imu_and_attitude_gaps_are_not_interpolated_across(motion_log: LogData) -> None:
    """GIVEN missing attitude and IMU samples WHEN checked THEN affected GPS intervals reduce coverage."""
    _columns(motion_log, "IMU")["AccX"][80:100] = np.nan
    _columns(motion_log, "ATT")["Yaw"][120:140] = np.nan
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    coverage = next(item for item in outcomes if item.source == "GPS.IMU")
    assert 0 < _evidence(coverage)["evaluated"] < 20
    assert not _warnings(outcomes, "GPS.IMU")


def test_single_discrepant_velocity_sample_is_not_a_sustained_inertial_event(motion_log: LogData) -> None:
    """GIVEN one terminal speed spike WHEN checked THEN it does not become a sustained inertial warning."""
    _columns(motion_log, "GPS")["Spd"][-1] = 100
    assert not _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")


def test_speed_uncertainty_raises_the_motion_tolerance(motion_log: LogData) -> None:
    """GIVEN poor reported velocity accuracy WHEN comparing motion THEN uncertainty prevents overconfident warnings."""
    gps = _columns(motion_log, "GPS")
    gps["Spd"] = 20.0 * gps["TimeUS"]
    _columns(motion_log, "GPA")["SAcc"] = 10
    assert not _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")


def test_inertial_coverage_states_its_documented_limits_verbatim(motion_log: LogData) -> None:
    """GIVEN a healthy stationary log WHEN checked THEN the GPS.IMU coverage reports every documented limit."""
    checks = GnssConsistencyChecks(motion_log, {})
    checks.check_inertial_motion()
    assert checks.coverage[0].message == (
        "GPS.IMU: evaluated 20/20 samples or intervals. "
        "Short windows, healthy IMUs, low rotation and continuous attitude required. "
        "Automatic receiver latency is tested over 0-0.5 s; attitude may itself be GPS-aided. "
        "GPS series with reversed boot timestamps are excluded."
    )


def test_speed_change_equal_to_the_motion_tolerance_is_not_a_discrepancy(motion_log: LogData) -> None:
    """GIVEN a sustained 3 m/s per sample speed change with no speed uncertainty WHEN checked THEN it is within tolerance."""
    _columns(motion_log, "GPA")["SAcc"] = 0.0
    gps = _columns(motion_log, "GPS")
    gps["Spd"] = 6.0 * gps["TimeUS"]
    checks = GnssConsistencyChecks(motion_log, {})
    outcomes = checks.check_inertial_motion()
    assert _evidence(checks.coverage[0])["evaluated"] == 20.0
    assert not _warnings(outcomes, "GPS.IMU")


def test_one_second_speed_discrepancy_is_still_reported_as_an_event(motion_log: LogData) -> None:
    """GIVEN a speed discrepancy lasting one second WHEN checked THEN it is reported with its measured span."""
    gps = _columns(motion_log, "GPS")
    gps["Spd"][8:] = 30.0
    gps["Spd"][8:11] = [10.0, 20.0, 30.0]
    events = _warnings(GnssConsistencyChecks(motion_log, {}).check_inertial_motion(), "GPS.IMU")
    assert len(events) == 1
    assert events[0].timestamp_us == 4.0e6
    assert events[0].end_timestamp_us == 5.0e6


def test_gps_samples_across_a_long_receiver_gap_are_not_bridged(motion_log: LogData) -> None:
    """GIVEN a 2.5 s GPS receiver gap with aligned GPA records WHEN checked THEN intervals spanning it are not evaluated."""
    _columns(motion_log, "GPS")["TimeUS"][6:] += 2.0
    gpa = _columns(motion_log, "GPA")
    gpa["TimeUS"][6:] += 2.0
    gpa["SMS"][6:] += 2.0
    checks = GnssConsistencyChecks(motion_log, {})
    checks.check_inertial_motion()
    assert _evidence(checks.coverage[0])["evaluated"] == 16.0


def test_single_gps_epoch_contributes_no_evaluable_intervals(motion_log: LogData) -> None:
    """GIVEN a GPS series with one epoch WHEN checked THEN no interval is counted as available for evaluation."""
    _add(motion_log, "GPS", TimeUS=[0.0], I=[0.0], Status=[3.0], Spd=[0.0], GCrs=[0.0], VZ=[0.0])
    checks = GnssConsistencyChecks(motion_log, {})
    checks.check_inertial_motion()
    assert _evidence(checks.coverage[0]) == {"evaluated": 0.0, "total": 0.0}


def test_negative_corrupt_gps_timestamp_does_not_mark_the_series_as_rebooted(motion_log: LogData) -> None:
    """GIVEN one corrupt negative GPS timestamp WHEN checked THEN the rest of the GPS series is still evaluated."""
    _columns(motion_log, "GPS")["TimeUS"][10] = -1.0
    checks = GnssConsistencyChecks(motion_log, {})
    checks.check_inertial_motion()
    assert _evidence(checks.coverage[0])["evaluated"] == 18.0


@pytest.mark.parametrize("glitch_time_s", [0.0, 0.25])
def test_gps_timestamp_stepping_back_to_near_zero_is_treated_as_a_reboot(motion_log: LogData, glitch_time_s: float) -> None:
    """GIVEN a GPS timestamp stepping back to a near-zero value WHEN checked THEN the ambiguous series is skipped."""
    _columns(motion_log, "GPS")["TimeUS"][2] = glitch_time_s
    checks = GnssConsistencyChecks(motion_log, {})
    checks.check_inertial_motion()
    assert _evidence(checks.coverage[0])["evaluated"] == 0.0


def test_repeated_gps_timestamp_splits_the_series_without_skipping_it(motion_log: LogData) -> None:
    """GIVEN a duplicated GPS timestamp WHEN checked THEN only intervals touching it are lost, not the whole series."""
    gps = _columns(motion_log, "GPS")
    gps["TimeUS"][10] = gps["TimeUS"][9]
    checks = GnssConsistencyChecks(motion_log, {})
    checks.check_inertial_motion()
    assert _evidence(checks.coverage[0])["evaluated"] == 19.0


def test_vertical_velocity_requires_receiver_availability_flag(motion_log: LogData) -> None:
    """GIVEN unavailable receiver vertical velocity WHEN checked THEN only horizontal motion is compared."""
    gps = _columns(motion_log, "GPS")
    gps["VZ"] = 20 * gps["TimeUS"]
    assert _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")
    _columns(motion_log, "GPA")["VV"] = 0
    assert not _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")


def test_gps_position_jump_is_reported_with_metric_residual(motion_log: LogData) -> None:
    """GIVEN a position jump with zero velocity WHEN checked THEN the discrepancy carries metres and threshold."""
    _columns(motion_log, "GPS")["Lat"][10:] += 0.001
    events = _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.PositionVelocity")
    assert len(events) == 1
    assert events[0].timestamp_us == 5e6
    assert _evidence(events[0])["residual_m"] == pytest.approx(111.1949266)
    assert _evidence(events[0])["tolerance_m"] == 10.0


def test_infinite_horizontal_accuracy_does_not_disable_the_position_jump_check(motion_log: LogData) -> None:
    """
    A non-finite horizontal accuracy is not a usable uncertainty and must not disable the position check.

    GIVEN: A 111 m position jump with zero velocity and infinite horizontal accuracy
    WHEN: GPS position and velocity are checked
    THEN: The jump is still reported with the default 10 m tolerance
    """
    _columns(motion_log, "GPS")["Lat"][10:] += 0.001
    _columns(motion_log, "GPA")["HAcc"] = np.inf
    events = _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.PositionVelocity")
    assert len(events) == 1
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(10.0)


def test_gps_week_rollover_and_longitude_wrap_are_consistent() -> None:
    """GIVEN valid week and longitude boundaries WHEN checked THEN wrapping is not classified as spoofing."""
    log = LogData()
    _add(
        log,
        "GPS",
        TimeUS=[1, 2],
        I=[0, 0],
        Status=[3, 3],
        GWk=[2400, 2401],
        GMS=[604799, 0],
        Lat=[0, 0],
        Lng=[179.99999, -179.99999],
        Spd=[2.2238985, 2.2238985],
        GCrs=[90, 90],
    )
    outcomes = GnssConsistencyChecks(log, {}).analyse()
    assert not _warnings(outcomes, "GPS.Clock")
    assert not _warnings(outcomes, "GPS.PositionVelocity")


def test_gps_clock_jump_uses_boot_time_for_the_event(motion_log: LogData) -> None:
    """GIVEN a receiver-clock jump WHEN checked THEN event time remains anchored to the boot clock."""
    _columns(motion_log, "GPS")["GMS"][10:] += 100
    events = _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.Clock")
    assert len(events) == 1
    assert events[0].timestamp_us == 5e6
    assert events[0].evidence == {"clock_residual_s": 100.0}


def _healthy_gps_track() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Ten seconds of 2 Hz 3D-fix receiver rows whose GPS clock advances exactly with the boot clock."""
    times = np.arange(0.0, 10.5, 0.5)
    ones = np.ones_like(times)
    return times, ones * 2400, 1000 + times, ones * 3


def _run_gps_clock_check(
    times: np.ndarray, weeks: np.ndarray, tows: np.ndarray, statuses: np.ndarray
) -> tuple[list[LogAnalysis], GnssConsistencyChecks]:
    """Run only the GPS clock check on the supplied receiver rows and return its outcomes and coverage."""
    log = LogData()
    _add(log, "GPS", TimeUS=times, GWk=weeks, GMS=tows, Status=statuses)
    checks = GnssConsistencyChecks(log, {})
    return checks.check_gps_clock(), checks


def _clock_evaluation(checks: GnssConsistencyChecks) -> dict[str, float]:
    """Return the GPS.Clock coverage counters: residuals evaluated and residuals that could have been evaluated."""
    coverage = [item for item in checks.coverage if item.source == "GPS.Clock"]
    assert len(coverage) == 1
    return _evidence(coverage[0])


def test_single_gps_fix_reports_no_clock_intervals_to_evaluate() -> None:
    """GIVEN a log with a single GPS fix WHEN the clock is checked THEN no interval is counted as possible."""
    _outcomes, checks = _run_gps_clock_check(np.array([0.0]), np.array([2400.0]), np.array([1000.0]), np.array([3.0]))
    assert _clock_evaluation(checks) == {"evaluated": 0.0, "total": 0.0}


def test_gps_clock_ignores_receiver_rows_without_a_3d_fix() -> None:
    """GIVEN a 2D-fix row between healthy 3D fixes WHEN the clock is checked THEN that row breaks the comparison."""
    times, weeks, tows, statuses = _healthy_gps_track()
    statuses[10] = 2
    _outcomes, checks = _run_gps_clock_check(times, weeks, tows, statuses)
    assert _clock_evaluation(checks) == {"evaluated": 18.0, "total": 20.0}


def test_gps_clock_ignores_rows_with_invalid_zero_gps_week() -> None:
    """GIVEN a row with GPS week zero between healthy rows WHEN the clock is checked THEN it is not evaluated."""
    times, weeks, tows, statuses = _healthy_gps_track()
    weeks[10] = 0
    _outcomes, checks = _run_gps_clock_check(times, weeks, tows, statuses)
    assert _clock_evaluation(checks) == {"evaluated": 18.0, "total": 20.0}


def test_gps_clock_accepts_week_one_as_a_valid_gps_week() -> None:
    """GIVEN every row in GPS week one WHEN the clock is checked THEN all comparisons are evaluated."""
    times, weeks, tows, statuses = _healthy_gps_track()
    weeks[:] = 1
    _outcomes, checks = _run_gps_clock_check(times, weeks, tows, statuses)
    assert _clock_evaluation(checks) == {"evaluated": 20.0, "total": 20.0}


def test_gps_clock_accepts_time_of_week_exactly_at_zero() -> None:
    """GIVEN a row at the start of the GPS week (time of week zero) WHEN the clock is checked THEN it is evaluated."""
    times, weeks, _tows, statuses = _healthy_gps_track()
    _outcomes, checks = _run_gps_clock_check(times, weeks, times.copy(), statuses)
    assert _clock_evaluation(checks) == {"evaluated": 20.0, "total": 20.0}


def test_gps_clock_excludes_time_of_week_at_exactly_one_week() -> None:
    """GIVEN a row whose time of week is exactly 604800 s WHEN the clock is checked THEN it is not evaluated."""
    times, weeks, _tows, statuses = _healthy_gps_track()
    _outcomes, checks = _run_gps_clock_check(times, weeks, 604790.0 + times, statuses)
    assert _clock_evaluation(checks) == {"evaluated": 19.0, "total": 20.0}


def test_gps_clock_does_not_bridge_receiver_gaps_longer_than_two_seconds() -> None:
    """GIVEN a 2.5 s gap in GPS rows WHEN the clock is checked THEN no residual is computed across the gap."""
    times = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 4.5, 5.0, 5.5])
    weeks, tows, statuses = np.full(times.shape, 2400.0), 1000 + times, np.full(times.shape, 3.0)
    _outcomes, checks = _run_gps_clock_check(times, weeks, tows, statuses)
    assert _clock_evaluation(checks) == {"evaluated": 6.0, "total": 7.0}


def test_gps_clock_drift_residual_is_measured_over_a_five_second_window() -> None:
    """GIVEN a GPS clock running 30% fast WHEN checked THEN the residual reflects the 5 s comparison window."""
    times, weeks, _tows, statuses = _healthy_gps_track()
    outcomes, _checks = _run_gps_clock_check(times, weeks, 1000 + 1.3 * times, statuses)
    events = _warnings(outcomes, "GPS.Clock")
    assert len(events) == 1
    assert events[0].timestamp_us == pytest.approx(3.5e6)
    assert _evidence(events[0])["clock_residual_s"] == pytest.approx(1.5)


def test_gps_clock_week_rollover_reports_the_true_clock_error() -> None:
    """GIVEN a 1.5 s clock step across a GPS week rollover WHEN checked THEN the event reports 1.5 s, not a week error."""
    times = np.arange(0.0, 10.5, 0.5)
    raw_tow = 604795.0 + times
    wrapped = raw_tow >= 604800.0
    weeks = np.where(wrapped, 2401.0, 2400.0)
    tows = np.where(wrapped, raw_tow - 604800.0 + 1.5, raw_tow)
    outcomes, _checks = _run_gps_clock_check(times, weeks, tows, np.full(times.shape, 3.0))
    events = _warnings(outcomes, "GPS.Clock")
    assert len(events) == 1
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (5e6, 9.5e6)
    assert _evidence(events[0])["clock_residual_s"] == pytest.approx(1.5)


def test_scaled_log_schema_converts_microseconds_and_milliseconds_before_analysis() -> None:
    """GIVEN raw stored timestamp units WHEN analyzed THEN FMT multipliers produce canonical event times."""
    log = LogData()
    _add(log, "GPS", TimeUS=[1000000, 2000000, 3000000], GWk=[2400, 2400, 2400], GMS=[1000, 2000, 103000], Status=[3, 3, 3])
    fields = ["TimeUS", "GWk", "GMS", "Status"]
    log.schemas["GPS"] = MessageSchema(
        "GPS", 1, 1, "", fields, ["us", "", "ms", ""], ["s", "", "s", ""], [1e-6, 1, 1e-3, 1], [False] * 4
    )
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Clock")
    assert len(events) == 1
    assert events[0].timestamp_us == 3e6


def test_fix_acquisition_is_not_jamming_and_loss_after_acquisition_is_reported() -> None:
    """GIVEN startup acquisition followed by loss WHEN checked THEN only the later loss is a diagnostic event."""
    log = LogData()
    _add(log, "GPS", TimeUS=[0, 1, 2, 3, 4, 5], I=[0] * 6, Status=[1, 2, 3, 3, 1, 3])
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Status")
    assert len(events) == 1
    assert events[0].timestamp_us == 4e6


def test_ekf_checks_follow_primary_core_and_timestamped_gps_source_selection() -> None:
    """GIVEN an inactive unhealthy core and a later non-GPS source WHEN checked THEN only active GPS intervals warn."""
    log = LogData()
    times = np.repeat(np.arange(6), 2)
    _add(log, "XKF4", TimeUS=times, C=[0, 1] * 6, PI=[0] * 12, SV=[2, 50] * 6, SP=[0] * 12)
    _add(log, "XKFS", TimeUS=list(range(6)), C=[0] * 6, SS=[0] * 6)
    history = ParameterHistory(initial_values={"EK3_SRC1_VELXY": 3}, changes={"EK3_SRC1_VELXY": (ParameterChange(3.0, 6.0),)})
    events = [item for item in _warnings(GnssConsistencyChecks(log, {}, history).analyse(), "XKF4.SV") if item.instance == 0]
    assert len(events) == 1
    assert events[0].instance == 0
    assert events[0].timestamp_us == 0
    assert events[0].end_timestamp_us == 2e6
    assert events[0].evidence == {"test_ratio": 2.0, "active_primary": 1.0}


def test_ekf_missing_source_metadata_is_reported_as_missing_coverage() -> None:
    """GIVEN an unknown EKF navigation source WHEN checked THEN ratios are not attributed to GPS."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[1, 2], C=[0, 0], PI=[0, 0], SV=[5, 5], SP=[5, 5])
    outcomes = GnssConsistencyChecks(log, {}).analyse()
    assert not _warnings(outcomes, "XKF4.SV")
    assert _evidence(next(item for item in outcomes if item.source == "XKF4.SV/SP"))["evaluated"] == 0


def test_primary_ekf_position_reset_is_reported_once_when_offset_changes() -> None:
    """GIVEN a repeated last-reset offset WHEN checked THEN only the actual offset transition is reported."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[1, 2, 3, 4], C=[0] * 4, PI=[0] * 4, SV=[0] * 4, SP=[0] * 4, OFN=[0, 5, 5, 5])
    _add(log, "XKFS", TimeUS=[1, 2, 3, 4], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")
    assert len(events) == 1
    assert events[0].timestamp_us == 2e6


def test_multiple_receivers_and_primary_receiver_switch_do_not_mix_motion(motion_log: LogData) -> None:
    """GIVEN two separated GPS tracks and a primary switch WHEN checked THEN position derivatives stay within each receiver."""
    original = _columns(motion_log, "GPS")
    second = original.copy()
    second["I"] = 1
    second["Lat"] = 49
    second["U"] = second["TimeUS"] >= 5
    original["U"] = original["TimeUS"] < 5
    interleaved = np.stack((original, second), axis=1).flatten()
    motion_log.add_message_columns("GPS", interleaved)
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    assert not _warnings(outcomes, "GPS.PositionVelocity")
    assert not _warnings(outcomes, "GPS.IMU")
    assert next(item for item in outcomes if item.source == "GPS.IMU").evidence == {"evaluated": 40.0, "total": 40.0}


def test_fault_on_secondary_receiver_is_retained_without_borrowing_primary_accuracy(motion_log: LogData) -> None:
    """GIVEN a faulty secondary GPS WHEN compared THEN the primary receiver's uncertainty is not borrowed."""
    original = _columns(motion_log, "GPS")
    second = original.copy()
    second["I"] = 1
    second["Spd"] = second["TimeUS"] * 20
    second["U"] = 0
    motion_log.add_message_columns("GPS", np.stack((original, second), axis=1).flatten())
    _columns(motion_log, "GPA")["SAcc"] = 100
    events = _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")
    assert len(events) == 1
    assert events[0].instance == 1
    assert _evidence(events[0])["tolerance_m_s"] == 3


def test_multiple_ekf_lanes_are_reported_with_primary_switch_and_selected_receivers() -> None:
    """GIVEN two GPS lanes switching primary roles WHEN checked THEN lane activity and receiver selection are retained."""
    log = LogData()
    times = np.repeat(np.arange(6), 2)
    _add(log, "XKF4", TimeUS=times, C=[0, 1] * 6, PI=[0] * 6 + [1] * 6, SV=[2] * 12, SP=[0] * 12)
    _add(log, "XKFS", TimeUS=times, C=[0, 1] * 6, SS=[0] * 12, GI=[0, 1] * 6)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_VELXY": 3}).analyse(), "XKF4.SV")
    assert len(events) == 4
    for lane in (0, 1):
        lane_events = [item for item in events if item.instance == lane]
        assert [(item.timestamp_us, item.end_timestamp_us) for item in lane_events] == [(0, 2e6), (3e6, 5e6)]
        assert [_evidence(item)["active_primary"] for item in lane_events] == ([1, 0] if lane == 0 else [0, 1])
        assert all(_evidence(item)["gps_receiver"] == lane for item in lane_events)


def test_receiver_change_within_an_ekf_lane_splits_its_event() -> None:
    """GIVEN an EKF lane changing receivers WHEN checked THEN its event intervals are split."""
    log = LogData()
    _add(log, "XKF4", TimeUS=list(range(6)), C=[0] * 6, PI=[0] * 6, SV=[2] * 6)
    _add(log, "XKFS", TimeUS=list(range(6)), C=[0] * 6, SS=[0] * 6, GI=[0] * 3 + [1] * 3)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_VELXY": 3}).analyse(), "XKF4.SV")
    assert len(events) == 2
    assert [_evidence(item)["gps_receiver"] for item in events] == [0, 1]


def test_non_gps_source_on_one_lane_does_not_block_other_gps_lanes() -> None:
    """GIVEN GPS and external-navigation lanes WHEN checked THEN GPS attribution follows each lane's source set."""
    log = LogData()
    times = np.repeat(np.arange(6), 2)
    _add(log, "XKF4", TimeUS=times, C=[0, 1] * 6, PI=[0] * 12, SV=[2] * 12)
    _add(log, "XKFS", TimeUS=times, C=[0, 1] * 6, SS=[0, 1] * 6)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_VELXY": 3, "EK3_SRC2_VELXY": 6}).analyse(), "XKF4.SV")
    assert len(events) == 1
    assert events[0].instance == 0


def test_ekf2_gps_disabled_does_not_create_a_gps_innovation_warning() -> None:
    """GIVEN an EKF2 non-GPS configuration WHEN checked THEN its innovations are not attributed to GPS."""
    log = LogData()
    _add(log, "NKF4", TimeUS=[1, 2, 3], C=[0] * 3, PI=[0] * 3, SV=[2] * 3, SP=[2] * 3)
    assert not _warnings(GnssConsistencyChecks(log, {"EK2_GPS_TYPE": 3}).analyse(), "NKF4.SV")
    assert len(_warnings(GnssConsistencyChecks(log, {"EK2_GPS_TYPE": 0}).analyse(), "NKF4.SV")) == 1
    position_only = GnssConsistencyChecks(log, {"EK2_GPS_TYPE": 2}).analyse()
    assert not _warnings(position_only, "NKF4.SV")
    assert _warnings(position_only, "NKF4.SP")


def test_banked_stationary_vehicle_has_gravity_removed_in_the_correct_frame(motion_log: LogData) -> None:
    """GIVEN a stationary tilted vehicle WHEN compared THEN its gravity projection is not treated as GPS acceleration."""
    imu = _columns(motion_log, "IMU")
    roll, pitch = np.deg2rad(20), np.deg2rad(60)
    imu["AccX"] = 9.80665 * np.sin(pitch)
    imu["AccY"] = -9.80665 * np.sin(roll) * np.cos(pitch)
    imu["AccZ"] = -9.80665 * np.cos(roll) * np.cos(pitch)
    _columns(motion_log, "ATT")["Roll"] = 20
    _columns(motion_log, "ATT")["Pitch"] = 60
    assert not _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")


def test_normal_turn_and_heading_wrap_match_inertial_motion(motion_log: LogData) -> None:
    """GIVEN a constant-speed turn through north WHEN checked THEN changing course and angular wrap stay consistent."""
    imu = _columns(motion_log, "IMU")
    imu["AccY"] = 1
    imu["GyrZ"] = 0.1
    attitude = _columns(motion_log, "ATT")
    attitude["Yaw"] = (350 + np.rad2deg(attitude["TimeUS"] * 0.1)) % 360
    gps = _columns(motion_log, "GPS")
    gps["Spd"] = 10
    gps["GCrs"] = (350 + np.rad2deg(gps["TimeUS"] * 0.1)) % 360
    assert not _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")


def test_recorded_receiver_delay_aligns_nonconstant_acceleration(motion_log: LogData) -> None:
    """GIVEN delayed GPS velocity during an acceleration pulse WHEN aligned THEN motion is consistent."""
    imu = _columns(motion_log, "IMU")
    times = imu["TimeUS"]
    imu["AccX"] = np.where((times >= 3) & (times <= 4), 30.0, 0.0)
    integrated = np.r_[0, np.cumsum((imu["AccX"][1:] + imu["AccX"][:-1]) * np.diff(times) / 2)]
    gps = _columns(motion_log, "GPS")
    gps["Spd"] = np.interp(gps["TimeUS"] - 0.25, times, integrated)
    assert not _warnings(GnssConsistencyChecks(motion_log, {"GPS1_DELAY_MS": 250}).analyse(), "GPS.IMU")


def test_fractional_fix_status_is_excluded_from_kinematic_checks(motion_log: LogData) -> None:
    """GIVEN an invalid fix code WHEN checking motion THEN the data is not treated as a healthy 3D fix."""
    _columns(motion_log, "GPS")["Status"] = 3.5
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    assert _evidence(next(item for item in outcomes if item.source == "GPS.IMU"))["evaluated"] == 0


def test_receiver_recovery_is_reported_only_with_contiguous_status_evidence() -> None:
    """GIVEN a warning followed by healthy status WHEN contiguous THEN report recovery, while a gap remains unknown."""
    log = LogData()
    _add(log, "AERG", TimeUS=[1, 2, 3, 20], Jam=[2, 1, 3, 1])
    recoveries = [item for item in GPSLogAnalysis(log, _context()).analyse().outcomes if "after the warning" in item.message]
    assert len(recoveries) == 1
    assert recoveries[0].timestamp_us == 2e6


@pytest.mark.parametrize("cadence", [5, 5.02, 6, 10])
def test_slow_ublox_diagnostics_have_a_cadence_appropriate_baseline(cadence: float) -> None:
    """GIVEN five-second receiver diagnostics WHEN indicator rises THEN useful RF evidence remains available."""
    log = LogData()
    _add(log, "UBX1", TimeUS=np.arange(12) * cadence, Instance=[0] * 12, jamInd=[10] * 7 + [100] * 5)
    events = _warnings(GPSLogAnalysis(log, _context()).analyse().outcomes, "UBX1.jamInd")
    assert len(events) == 1
    assert events[0].timestamp_us == pytest.approx(7 * cadence * 1e6)
    assert not any("discontinuities" in item.message for item in GPSLogAvailabilityModel(log, _context()).check().issues)


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
def test_ekf_startup_is_excluded_but_later_faults_and_resets_warn(message: str) -> None:
    """Pre-aiding faults and the initial reset are context; later events remain visible."""
    log = LogData()
    _add(
        log,
        message,
        TimeUS=list(range(8)),
        C=[0] * 8,
        PI=[0] * 8,
        SS=[0, 0, 16, 16, 16, 16, 0, 0],
        TS=[3, 3, 0, 0, 0, 0, 3, 3],
        FS=[128, 128, 0, 0, 0, 0, 1, 1],
        GPS=[1, 1, 0, 0, 0, 0, 1, 1],
        OFN=[0, 0, 5, 5, 5, 5, 10, 10],
    )
    _add(log, "XKFS", TimeUS=list(range(8)), C=[0] * 8, SS=[0] * 8)
    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3, "EK2_GPS_TYPE": 0}).analyse()
    for field in ("TS", "FS", "GPS", "OFN"):
        events = _warnings(outcomes, f"{message}.{field}")
        assert len(events) == 1
        assert events[0].timestamp_us == 6e6


def test_ekf_only_log_is_available() -> None:
    """Configured GPS fusion permits EKF analysis when GPS and receiver records are absent."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[1, 2], C=[0, 0], PI=[0, 0], FS=[0, 1])
    _add(log, "XKFS", TimeUS=[1, 2], C=[0, 0], SS=[0, 0], GI=[0, 0])
    context = _context()
    context.parameters["EK3_SRC1_POSXY"] = 3
    assert GPSLogAvailabilityModel(log, context).check().available
    assert _warnings(GPSLogAnalysis(log, context).analyse().outcomes, "XKF4.FS")


def test_gps_fusion_evidence_is_analyzed_without_receiver_records() -> None:
    """XKF4/XKFS GPS innovation evidence remains usable without GPS or RF diagnostics."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[1, 2, 3], C=[0] * 3, PI=[0] * 3, SV=[2] * 3)
    _add(log, "XKFS", TimeUS=[1, 2, 3], C=[0] * 3, SS=[0] * 3, GI=[0] * 3)
    context = _context()
    context.parameters["EK3_SRC1_VELXY"] = 3
    assert GPSLogAvailabilityModel(log, context).check().available
    result = GPSLogAnalysis(log, context).analyse()
    assert result.available
    assert _warnings(result.outcomes, "XKF4.SV")


def test_ublox_baseline_keeps_five_samples_when_timing_jitters() -> None:
    """A rise after five slightly irregular diagnostic samples remains detectable."""
    log = LogData()
    _add(log, "UBX1", TimeUS=[0, 10, 20, 30, 40, 50.1, 60.1, 70.1], Instance=[0] * 8, jamInd=[10] * 5 + [100] * 3)
    events = _warnings(GPSLogAnalysis(log, _context()).analyse().outcomes, "UBX1.jamInd")
    assert events[0].timestamp_us == pytest.approx(50.1e6)


def test_real_ekf_fault_before_aiding_remains_a_warning() -> None:
    """A bad-quaternion fault alongside NOT_INITIALISED is not hidden by startup gating."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, SS=[0, 0, 16], FS=[129, 129, 0])
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3, GI=[0] * 3)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.FS")
    assert len(events) == 1
    assert events[0].timestamp_us == 0
    assert _evidence(events[0])["FS"] == 129


@pytest.mark.parametrize("status", [0, 65536 | 128])
def test_log_starting_during_existing_ekf_outage_keeps_fault_warnings(status: int) -> None:
    """Missing aiding at the start of a partial log does not establish initialization."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[500, 501, 502], C=[0] * 3, PI=[0] * 3, SS=[status] * 3, FS=[1] * 3, TS=[3] * 3, GPS=[1] * 3)
    _add(log, "XKFS", TimeUS=[500, 501, 502], C=[0] * 3, SS=[0] * 3)
    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3}).analyse()
    for field in ("FS", "TS", "GPS"):
        assert _warnings(outcomes, f"XKF4.{field}")[0].timestamp_us == 500e6


def test_position_reset_after_aiding_is_not_hidden_by_a_grace_period() -> None:
    """A first reset after initialization is still a discrepancy requiring review."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3, 4], C=[0] * 5, PI=[0] * 5, SS=[128, 128, 16, 16, 16], OFN=[0, 0, 0, 5, 5])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3, 4], C=[0] * 5, SS=[0] * 5, GI=[0] * 5)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")
    assert len(events) == 1
    assert events[0].timestamp_us == 3e6


@pytest.mark.parametrize("instances", [[0, 0, 0, 0], [0, 0, 1, 1]])
def test_reversed_boot_timestamps_disable_correlations(instances: list[int]) -> None:
    """Overlapping timestamps from different boots do not establish correlated evidence."""
    log = LogData()
    _add(log, "UBX1", TimeUS=[0, 1, 0, 1], Instance=instances, jamInd=[10] * 4)
    first = LogAnalysis("rf", timestamp_us=1e6, source="UBX1.jamInd", instance=0)
    second = LogAnalysis("fix", timestamp_us=1e6, source="GPS.Status", instance=0)
    assert not GPSLogAnalysis.correlate_findings([first, second], log)


@pytest.mark.parametrize("instance", [0, 1])
@pytest.mark.parametrize("legacy", [False, True])
def test_vibe_clipping_excludes_only_matching_imu_intervals(motion_log: LogData, instance: int, legacy: bool) -> None:
    """Modern and legacy counters reduce motion coverage only for the affected IMU."""
    baseline = GnssConsistencyChecks(motion_log, {}).analyse()
    before = _evidence(next(item for item in baseline if item.source == "GPS.IMU"))["evaluated"]
    fields = {f"Clip{instance}": [0, 1, 1]} if legacy else {"IMU": [instance] * 3, "Clip": [0, 1, 1]}
    _add(motion_log, "VIBE", TimeUS=[1, 2, 3], **fields)
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    after = _evidence(next(item for item in outcomes if item.source == "GPS.IMU"))["evaluated"]
    assert (after < before) if instance == 0 else (after == before)


def _unclipped_imu_samples(log: LogData, imu_times: list[float], instance: int | None = None) -> np.ndarray:
    """Apply the VIBE clip mask to one IMU stream without running the whole consistency pipeline."""
    imu = SensorSeries(instance, {"TimeUS": np.asarray(imu_times, dtype=np.float64)})
    return GnssConsistencyChecks(log, {})._unclipped_samples(imu)  # pylint: disable=protected-access


def test_clip_interval_excludes_inclusive_span_and_restores_validity_after_it() -> None:
    """GIVEN one counter increment from 1 s to 3 s WHEN masking IMU samples THEN both ends are excluded."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[1.0, 3.0], Clip=[0.0, 1.0])
    valid = _unclipped_imu_samples(log, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    assert valid.tolist() == [True, False, False, False, True, True]


def test_clip_starting_at_time_zero_excludes_the_first_samples() -> None:
    """GIVEN a counter increment starting at time zero WHEN masking IMU samples THEN the sample at zero is excluded."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[0.0, 2.0], Clip=[0.0, 1.0])
    valid = _unclipped_imu_samples(log, [0.0, 0.5, 1.0, 1.5, 2.0, 3.0])
    assert valid.tolist() == [False, False, False, False, False, True]


def test_clip_starting_before_boot_time_is_ignored() -> None:
    """GIVEN a counter increment whose start precedes boot time WHEN masking IMU samples THEN no IMU sample is excluded."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[-1.0, 2.0], Clip=[0.0, 1.0])
    valid = _unclipped_imu_samples(log, [0.0, 1.0, 2.0, 3.0])
    assert valid.tolist() == [True, True, True, True]


def test_counter_plateaus_and_decreases_do_not_clip_imu_samples() -> None:
    """GIVEN counter intervals with no change or a decrease WHEN masking IMU samples THEN only the increment clips."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[1.0, 2.0, 3.0, 4.0], Clip=[5.0, 5.0, 3.0, 4.0])
    valid = _unclipped_imu_samples(log, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    assert valid.tolist() == [True, True, True, False, False, True]


def test_repeated_vibe_timestamps_are_not_out_of_order_and_do_not_clip_by_themselves() -> None:
    """GIVEN repeated VIBE timestamps WHEN masking IMU samples THEN the zero-length interval excludes nothing."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[1.0, 1.0, 3.0, 4.0], Clip=[0.0, 1.0, 1.0, 2.0])
    valid = _unclipped_imu_samples(log, [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    assert valid.tolist() == [True, True, True, False, False, True]


def test_half_second_vibe_cadence_is_monotonic_and_clips_the_counted_span() -> None:
    """GIVEN VIBE samples every half second WHEN masking IMU samples THEN the increment still clips its span."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[1.0, 1.5, 2.0, 2.5], Clip=[0.0, 0.0, 1.0, 1.0])
    valid = _unclipped_imu_samples(log, [1.0, 1.5, 1.75, 2.0, 2.5])
    assert valid.tolist() == [True, False, False, False, True]


@pytest.mark.parametrize(
    ("vibe_times", "imu_times"),
    [
        ([1.0, 0.0, 2.0], [0.0, 1.0, 2.0, 3.0]),
        ([2.0, 0.5, 3.0], [0.0, 1.0, 2.0, 3.0, 4.0]),
        ([2.0, 1.0, 3.0], [0.0, 1.0, 2.0, 3.0, 4.0]),
    ],
)
def test_out_of_order_vibe_timestamps_exclude_every_imu_sample(vibe_times: list[float], imu_times: list[float]) -> None:
    """GIVEN VIBE timestamps running backwards WHEN masking IMU samples THEN no IMU sample is usable."""
    log = LogData()
    _add(log, "VIBE", TimeUS=vibe_times, Clip=[0.0, 1.0, 2.0])
    valid = _unclipped_imu_samples(log, imu_times)
    assert valid.dtype == np.bool_
    assert valid.tolist() == [False] * len(imu_times)


def test_negative_vibe_timestamps_are_not_part_of_the_order_check() -> None:
    """GIVEN a pre-boot VIBE timestamp between valid ones WHEN masking IMU samples THEN only the valid span clips."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[2.0, 3.0, -1.0, 4.0], Clip=[0.0, 1.0, 2.0, 3.0])
    valid = _unclipped_imu_samples(log, [0.0, 1.0, 2.0, 3.0, 4.0])
    assert valid.tolist() == [True, True, False, False, True]


def test_clip_counters_from_several_sources_accumulate_exclusions() -> None:
    """GIVEN generic and instance counters for one IMU WHEN masking IMU samples THEN a clean counter keeps exclusions."""
    log = LogData()
    _add(log, "VIBE", TimeUS=[1.0, 2.0, 3.0, 4.0], IMU=[0.0] * 4, Clip=[0.0, 1.0, 1.0, 1.0], Clip0=[0.0] * 4)
    valid = _unclipped_imu_samples(log, [0.0, 1.0, 2.0, 3.0, 4.0], instance=0)
    assert valid.tolist() == [True, False, False, True, True]


def test_missing_imu_health_fields_reduce_inertial_coverage(motion_log: LogData) -> None:
    """GIVEN missing IMU health flags WHEN checking motion THEN inertial coverage is unavailable."""
    columns = _columns(motion_log, "IMU")
    assert columns.dtype.names is not None
    motion_log.add_message_columns("IMU", columns[[name for name in columns.dtype.names if name not in ("AH", "GH")]])
    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()
    assert _evidence(next(item for item in outcomes if item.source == "GPS.IMU"))["evaluated"] == 0


def test_frozen_gps_clock_is_detected_over_a_short_window(motion_log: LogData) -> None:
    """GIVEN a frozen receiver clock WHEN boot time continues THEN accumulated time disagreement is reported."""
    _columns(motion_log, "GPS")["GMS"] = 1000
    events = _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.Clock")
    assert len(events) == 1
    assert events[0].timestamp_us == 1.5e6


def test_relative_altitude_and_downwards_velocity_use_consistent_signs(motion_log: LogData) -> None:
    """GIVEN a climb with down-negative GPS velocity WHEN checked THEN altitude and velocity agree regardless of datum."""
    gps = _columns(motion_log, "GPS")
    assert gps.dtype.names is not None
    _add(motion_log, "GPS", **{name: gps[name] for name in gps.dtype.names}, Alt=300 + 10 * gps["TimeUS"])
    gps = _columns(motion_log, "GPS")
    gps["VZ"] = -10
    assert not _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.AltitudeVelocity")
    gps["VZ"] = 50
    assert _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.AltitudeVelocity")


def test_altitude_tolerance_is_three_times_the_summed_vertical_accuracy_of_each_interval() -> None:
    """
    Vertical accuracy scales the altitude tolerance by three, not four, times the summed interval accuracy.

    GIVEN: Flat GPS altitude with a 70 m/s descent over half-second intervals and 5 m vertical accuracy
    WHEN: GPS altitude and vertical velocity are checked
    THEN: The 35 m disagreement exceeds the 30 m tolerance and is reported with that tolerance
    """
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, VZ=np.full(len(times), 70.0))
    _add_gps_auxiliary(log, times, VAcc=np.full(len(times), 5.0))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")
    assert events
    assert _evidence(events[0])["residual_m"] == pytest.approx(35.0)
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(30.0)


@pytest.mark.parametrize("times", [[-2, -1], [-1, 0], [np.nan, 1], [1, np.nan], [np.inf, 2], [1, np.inf]])
def test_receiver_recovery_requires_two_valid_boot_timestamps(times: list[float]) -> None:
    """
    Invalid timestamp pairs cannot establish receiver recovery.

    GIVEN: A warning and healthy status with an invalid boot timestamp
    WHEN: Receiver indications are analyzed
    THEN: No recovery is inferred from the invalid pair
    """
    log = LogData()
    _add(log, "AERG", TimeUS=times, Jam=[2, 1])

    result = GPSLogAnalysis(log, _context()).analyse()

    assert not any("after the warning" in item.message for item in result.outcomes)
    if not np.any(np.isfinite(times) & (np.asarray(times) >= 0)):
        assert not result.available


@pytest.mark.parametrize(("ekf2_gps_type", "expect_warning"), [(0, True), (1, True), (2, True), (3, False)])
def test_ekf2_position_reset_is_attributed_to_gps_only_when_position_fusion_is_enabled(
    ekf2_gps_type: int, expect_warning: bool
) -> None:
    """
    An EKF2 lane position reset is GNSS evidence only when the configured GPS type fuses position.

    GIVEN: An NKF4 lane position reset with the parametrised EK2_GPS_TYPE, where type 3 disables GPS fusion
    WHEN: GNSS consistency is checked
    THEN: The reset is reported only when GPS position fusion is enabled
    """
    log = LogData()
    times = [0, 1, 2, 3]
    _add(log, "NKF4", TimeUS=times, C=[0] * 4, PI=[0] * 4, SV=[0] * 4, SP=[0] * 4, OFN=[0, 0, 5, 5])
    _add(log, "NKFS", TimeUS=times, C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    outcomes = GnssConsistencyChecks(log, {"EK2_GPS_TYPE": ekf2_gps_type}).analyse()
    assert bool(_warnings(outcomes, "NKF4.OFN")) == expect_warning


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
@pytest.mark.parametrize("timeout", [0, 4, 8, 16, 32, 48, 128])
def test_non_gps_ekf_timeouts_do_not_warn_about_gnss(message: str, timeout: int) -> None:
    """
    Other measurement timeouts do not become GNSS warnings.

    GIVEN: GPS navigation with only non-GPS timeout bits set
    WHEN: GNSS consistency is checked
    THEN: No GPS timeout warning is produced
    """
    log = LogData()
    _add(log, message, TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[timeout] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)
    parameters = {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3, "EK2_GPS_TYPE": 0}

    outcomes = GnssConsistencyChecks(log, parameters).analyse()

    assert not _warnings(outcomes, f"{message}.TS")


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
@pytest.mark.parametrize("timeout", [1, 2, 3, 49])
def test_gps_ekf_timeouts_retain_relevant_bits_and_raw_evidence(message: str, timeout: int) -> None:
    """
    GPS timeouts remain visible alongside unrelated timeout bits.

    GIVEN: GPS navigation with position or velocity timeout bits set
    WHEN: GNSS consistency is checked
    THEN: The warning retains the raw mask and the GPS-relevant bits
    """
    log = LogData()
    _add(log, message, TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[timeout] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)
    parameters = {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3, "EK2_GPS_TYPE": 0}

    events = _warnings(GnssConsistencyChecks(log, parameters).analyse(), f"{message}.TS")

    assert len(events) == 1
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (0, 2e6)
    assert events[0].evidence == {"TS": float(timeout), "gps_timeout_mask": float(timeout & 3), "active_primary": 1.0}


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
@pytest.mark.parametrize(("timeouts", "expected_mask"), [([5, 3], 7), ([9, 5], 13)])
def test_raw_timeout_evidence_retains_all_bits_within_an_interval(
    message: str, timeouts: list[int], expected_mask: int
) -> None:
    """GIVEN a constant GPS timeout WHEN other timeout bits change THEN the evidence retains every observed bit."""
    log = LogData()
    _add(log, message, TimeUS=[0, 1], C=[0, 0], PI=[0, 0], TS=timeouts)
    _add(log, "XKFS", TimeUS=[0, 1], C=[0, 0], SS=[0, 0])
    parameters = {"EK3_SRC1_POSXY": 3, "EK2_GPS_TYPE": 2}

    events = _warnings(GnssConsistencyChecks(log, parameters).analyse(), f"{message}.TS")

    assert len(events) == 1
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (0, 1e6)
    assert _evidence(events[0])["TS"] == expected_mask
    assert _evidence(events[0])["gps_timeout_mask"] == 1


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
def test_timeout_values_beyond_the_byte_range_are_not_counted_as_gps_evidence(message: str) -> None:
    """
    Out-of-range timeout values are unusable samples, not zero-timeout samples.

    GIVEN: A GPS navigation source and a timeout value beyond the 8-bit mask range
    WHEN: GNSS consistency is checked
    THEN: The sample is excluded from the TS coverage count
    """
    log = LogData()
    _add(log, message, TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[256] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)
    parameters = {"EK3_SRC1_POSXY": 3, "EK2_GPS_TYPE": 0}

    outcomes = GnssConsistencyChecks(log, parameters).analyse()

    assert not _warnings(outcomes, f"{message}.TS")
    coverage = next(item for item in outcomes if item.source == f"{message}.TS.coverage")
    assert _evidence(coverage)["evaluated"] == 0.0


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
def test_ekf_timeouts_without_gps_source_evidence_are_not_attributed_to_gps(message: str) -> None:
    """
    Unknown navigation sources cannot establish GPS timeouts.

    GIVEN: Position and velocity timeout bits without source metadata
    WHEN: GNSS consistency is checked
    THEN: No GPS timeout warning is inferred
    """
    log = LogData()
    _add(log, message, TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[3] * 3)

    outcomes = GnssConsistencyChecks(log, {}).analyse()

    assert not _warnings(outcomes, f"{message}.TS")


def test_gps_velocity_timeout_stops_when_the_lane_switches_to_external_navigation() -> None:
    """
    GPS timeout attribution follows the source active at each timestamp.

    GIVEN: A lane switching from GPS to external velocity navigation
    WHEN: A velocity timeout persists across the switch
    THEN: Only the GPS interval is reported
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=list(range(6)), C=[0] * 6, PI=[0] * 6, TS=[2] * 6)
    _add(log, "XKFS", TimeUS=list(range(6)), C=[0] * 6, SS=[0] * 6)
    history = ParameterHistory(initial_values={"EK3_SRC1_VELXY": 3}, changes={"EK3_SRC1_VELXY": (ParameterChange(3, 6),)})

    events = _warnings(GnssConsistencyChecks(log, {}, history).analyse(), "XKF4.TS")

    assert len(events) == 1
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (0, 2e6)


def test_position_and_velocity_timeout_transitions_preserve_separate_masks() -> None:
    """
    Changes in GPS timeout bits retain their own event evidence.

    GIVEN: A position timeout followed by a velocity timeout on the same lane
    WHEN: GNSS consistency is assessed
    THEN: Each observed interval retains its distinct mask
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, TS=[1, 1, 2, 2])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3}).analyse(), "XKF4.TS")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(0, 1e6), (2e6, 3e6)]
    assert [_evidence(item)["gps_timeout_mask"] for item in events] == [1, 2]


@pytest.mark.parametrize("timeout", [-1, 1.5, np.nan, np.inf, 256])
def test_invalid_ekf_timeout_masks_do_not_establish_gps_faults(timeout: float) -> None:
    """
    Malformed timeout masks are excluded from GPS assessment.

    GIVEN: GPS navigation with invalid timeout masks
    WHEN: GNSS consistency is checked
    THEN: No GPS timeout is inferred
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[timeout] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3}).analyse()

    assert not _warnings(outcomes, "XKF4.TS")


@pytest.mark.parametrize(
    ("options", "expected"),
    [(0, False), (1, True), (3, True), (8, False), (-1, False), (1.5, False), (np.nan, False), (np.inf, False)],
)
def test_fuse_all_velocities_includes_gps_from_another_source_set(options: float, expected: bool) -> None:
    """
    GPS velocity evidence follows the FuseAllVelocities option.

    GIVEN: GPS velocity in an inactive source set
    WHEN: An innovation gate is exceeded on the selected lane
    THEN: GPS velocity is assessed only when fusion across source sets is enabled
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, SV=[2] * 3, SP=[2] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[1] * 3, GI=[0] * 3)
    parameters = {
        "EK3_SRC_OPTIONS": options,
        "EK3_SRC1_VELXY": 3,
        "EK3_SRC2_VELXY": 0,
        "EK3_SRC1_POSXY": 3,
        "EK3_SRC2_POSXY": 0,
    }

    outcomes = GnssConsistencyChecks(log, parameters).analyse()

    assert bool(_warnings(outcomes, "XKF4.SV")) == expected
    assert not _warnings(outcomes, "XKF4.SP")
    coverage = next(item for item in outcomes if item.source == "XKF4.SV/SP")
    assert coverage.evidence == {"evaluated": 3.0 if expected else 0.0, "total": 6.0}


def test_fuse_all_velocity_warning_follows_timestamped_options_and_acknowledges_mixed_sources() -> None:
    """
    Mixed-source velocity evidence is assessed when fusion becomes enabled.

    GIVEN: External velocity selected and GPS velocity in another source set
    WHEN: FuseAllVelocities is enabled during a sustained innovation discrepancy
    THEN: The later interval warns without assigning the discrepancy solely to GPS
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=list(range(6)), C=[0] * 6, PI=[0] * 6, SV=[2] * 6)
    _add(log, "XKFS", TimeUS=list(range(6)), C=[0] * 6, SS=[1] * 6, GI=[0] * 6)
    history = ParameterHistory(
        initial_values={"EK3_SRC_OPTIONS": 0, "EK3_SRC1_VELXY": 3, "EK3_SRC2_VELXY": 6},
        changes={"EK3_SRC_OPTIONS": (ParameterChange(3, 1),)},
    )

    events = _warnings(GnssConsistencyChecks(log, {}, history).analyse(), "XKF4.SV")

    assert len(events) == 1
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (3e6, 5e6)
    assert "other velocity sources may contribute" in events[0].message
    assert _evidence(events[0])["gps_receiver"] == 0


@pytest.mark.parametrize("selected_source", [1, None])
def test_fuse_all_velocities_preserves_gps_timeout_evidence_without_an_active_gps_source(
    selected_source: int | None,
) -> None:
    """
    Known GPS velocity fusion does not depend on the active source set being GPS.

    GIVEN: GPS velocity fusion enabled across all source sets
    WHEN: Velocity times out with a different or unavailable active source set
    THEN: The lane's GPS velocity timeout and innovation remain assessable
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, SV=[2] * 3, TS=[2] * 3)
    if selected_source is not None:
        _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[selected_source] * 3)
    parameters = {"EK3_SRC_OPTIONS": 1, "EK3_SRC1_VELXY": 3, "EK3_SRC2_VELXY": 0}

    outcomes = GnssConsistencyChecks(log, parameters).analyse()

    assert len(_warnings(outcomes, "XKF4.SV")) == 1
    assert len(_warnings(outcomes, "XKF4.TS")) == 1


def test_healthy_secondary_imu_prevents_a_motion_warning_from_one_faulty_imu(motion_log: LogData) -> None:
    """
    Independent healthy IMUs retain their own motion predictions.

    GIVEN: A faulty primary accelerometer and a consistent secondary IMU
    WHEN: GPS motion is compared with all healthy IMUs
    THEN: The consistent sensor prevents a warning until it becomes unhealthy
    """
    primary = _columns(motion_log, "IMU")
    secondary = primary.copy()
    secondary["I"] = 1
    primary["AccX"] = 20
    motion_log.add_message_columns("IMU", np.stack((primary, secondary), axis=1).flatten())

    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()

    assert not _warnings(outcomes, "GPS.IMU")
    columns = _columns(motion_log, "IMU")
    columns["AH"][columns["I"] == 1] = 0
    assert _warnings(GnssConsistencyChecks(motion_log, {}).analyse(), "GPS.IMU")


@pytest.mark.parametrize("invalid_boundary", [False, True])
def test_reversed_imu_boot_epochs_cannot_establish_motion_consistency(
    motion_log: LogData,
    invalid_boundary: bool,
) -> None:
    """
    Repeated IMU boot epochs cannot be matched to GPS unambiguously.

    GIVEN: An IMU boot clock restarting, optionally across an invalid sample
    WHEN: GPS motion is assessed
    THEN: The ambiguous IMU contributes no evaluated intervals or warnings
    """
    imu = _columns(motion_log, "IMU")
    imu["TimeUS"][100:] -= 5
    if invalid_boundary:
        imu["TimeUS"][99] = np.nan

    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()

    assert not _warnings(outcomes, "GPS.IMU")
    assert _evidence(next(item for item in outcomes if item.source == "GPS.IMU"))["evaluated"] == 0


@pytest.mark.parametrize("invalid_boundary", [False, True])
def test_reversed_gps_boot_epochs_are_not_compared_with_first_epoch_imu(motion_log: LogData, invalid_boundary: bool) -> None:
    """An ambiguous GPS receiver is skipped without losing coverage for another receiver."""
    first = _columns(motion_log, "GPS").copy()
    second = first.copy()
    second["Spd"] = second["TimeUS"] * 20
    other_receiver = first.copy()
    other_receiver["I"] = 1
    if invalid_boundary:
        first["TimeUS"][-1] = np.nan
    motion_log.add_message_columns("GPS", np.concatenate((first, second, other_receiver)))

    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()

    assert not _warnings(outcomes, "GPS.IMU")
    coverage = next(item for item in outcomes if item.source == "GPS.IMU" and item.severity == "informational")
    assert _evidence(coverage) == {"evaluated": 20.0, "total": 61.0}
    assert "reversed" in coverage.message.lower()


def test_motion_assessment_does_not_copy_full_imu_history_for_each_gps_interval(
    motion_log: LogData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Motion assessment bounds interpolation copy volume while preserving results.

    GIVEN: High-rate inertial history and lower-rate GPS observations
    WHEN: Motion is assessed using real NumPy interpolation
    THEN: Full inertial histories are not recopied for each interval or latency
    """
    original_interp = np.interp
    copied_bytes = 0

    def record_interpolation(x: np.ndarray, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
        nonlocal copied_bytes
        copied_bytes += sum(values.nbytes for values in (xp, fp) if not values.flags.c_contiguous)
        return np.asarray(original_interp(x, xp, fp))

    monkeypatch.setattr(np, "interp", record_interpolation)

    outcomes = GnssConsistencyChecks(motion_log, {}).analyse()

    assert not _warnings(outcomes, "GPS.IMU")
    assert _evidence(next(item for item in outcomes if item.source == "GPS.IMU"))["evaluated"] == 20
    assert copied_bytes < 20 * _columns(motion_log, "IMU")["TimeUS"].nbytes


def _evaluated_motion_intervals(log: LogData) -> float:
    """Return how many GPS velocity intervals the inertial comparison actually evaluated."""
    outcomes = GnssConsistencyChecks(log, {}).analyse()
    return _evidence(next(item for item in outcomes if item.source == "GPS.IMU"))["evaluated"]


def _ten_hertz_gps(log: LogData) -> None:
    """Replace 2 Hz GPS with 10 Hz so that a 0.1 s inertial fragment can bound one receiver interval."""
    times = np.arange(0, 10.05, 0.1)
    gps = np.zeros(len(times), dtype=_columns(log, "GPS").dtype)
    gps["TimeUS"], gps["Status"], gps["Lat"], gps["Lng"] = times, 3, 48, 11
    gps["U"], gps["GWk"], gps["GMS"] = 1, 2400, times + 1000
    log.add_message_columns("GPS", gps)
    gpa = np.zeros(len(times), dtype=_columns(log, "GPA").dtype)
    gpa["TimeUS"], gpa["HAcc"], gpa["SAcc"], gpa["VV"], gpa["SMS"] = times, 1, 0.1, 1, times
    log.add_message_columns("GPA", gpa)


def test_rotation_exactly_at_the_lever_arm_limit_excludes_the_imu(motion_log: LogData) -> None:
    """GIVEN a steady 0.5 rad/s rotation WHEN checked THEN the strict limit excludes every IMU sample."""
    _columns(motion_log, "IMU")["GyrX"] = 0.5
    assert _evaluated_motion_intervals(motion_log) == 0


def test_one_fast_rotating_sample_excludes_only_its_own_interval(motion_log: LogData) -> None:
    """GIVEN one fast-rotating IMU sample WHEN checked THEN only the intervals it touches lose coverage."""
    _columns(motion_log, "IMU")["GyrZ"][100] = 1.0
    assert _evaluated_motion_intervals(motion_log) == 19


@pytest.mark.parametrize("field", ["AH", "GH"])
def test_imu_missing_one_mandatory_health_flag_has_no_motion_coverage(motion_log: LogData, field: str) -> None:
    """GIVEN an IMU lacking only one of its health flags WHEN checked THEN inertial coverage is unavailable."""
    columns = _columns(motion_log, "IMU")
    assert columns.dtype.names is not None
    motion_log.add_message_columns("IMU", columns[[name for name in columns.dtype.names if name != field]])
    assert _evaluated_motion_intervals(motion_log) == 0


def test_health_flag_older_than_two_tenths_of_a_second_does_not_confirm_imu_health(motion_log: LogData) -> None:
    """GIVEN health flags logged once per second WHEN checked THEN stale flags do not confirm the IMU."""
    imu = _columns(motion_log, "IMU")
    stale = np.arange(len(imu)) % 20 != 0
    imu["AH"][stale] = np.nan
    imu["GH"][stale] = np.nan
    assert _evaluated_motion_intervals(motion_log) == 0


@pytest.mark.parametrize("gap", ["nan", "time"])
def test_attitude_gap_is_neither_bridged_nor_used_to_integrate_motion(motion_log: LogData, gap: str) -> None:
    """
    Attitude is only interpolated across genuinely continuous records.

    GIVEN: Attitude missing as unusable samples, or as an absent one-second time span
    WHEN: GPS motion is assessed
    THEN: The affected IMU samples are not integrated and the evaluated coverage is exact
    """
    if gap == "nan":
        _columns(motion_log, "ATT")["Yaw"][120:140] = np.nan
    else:
        attitude = _columns(motion_log, "ATT")
        motion_log.add_message_columns("ATT", np.delete(attitude, slice(120, 140)))
    assert _evaluated_motion_intervals(motion_log) == 18


def test_imu_time_gap_longer_than_a_fifth_second_is_not_bridged(motion_log: LogData) -> None:
    """
    An absent IMU time span is not integrated into one continuous motion segment.

    GIVEN: One second of IMU records absent from the middle of the log
    WHEN: GPS motion is assessed
    THEN: Only the intervals supported by continuous IMU records are evaluated
    """
    motion_log.add_message_columns("IMU", np.delete(_columns(motion_log, "IMU"), slice(80, 100)))
    assert _evaluated_motion_intervals(motion_log) == 18


def test_short_imu_fragments_do_not_hide_later_motion_coverage(motion_log: LogData) -> None:
    """
    Fragments below the minimum length are skipped without ending the scan.

    GIVEN: IMU runs of two, three and many samples separated by unusable samples, with 10 Hz GPS
    WHEN: GPS motion is assessed
    THEN: The three-sample run and the long run still supply their evaluated intervals
    """
    _ten_hertz_gps(motion_log)
    imu = _columns(motion_log, "IMU")
    usable = np.zeros(len(imu), dtype=bool)
    usable[0:2] = usable[30:33] = usable[60:] = True
    imu["AccX"][~usable] = np.nan
    assert _evaluated_motion_intervals(motion_log) == 32


def test_repeated_boot_epoch_on_one_imu_does_not_hide_a_healthy_second_imu(motion_log: LogData) -> None:
    """
    An ambiguous IMU is skipped while another healthy IMU is still evaluated.

    GIVEN: IMU instance 0 with a restarted boot clock and a healthy instance 1
    WHEN: GPS motion is assessed
    THEN: Instance 1 supplies the full coverage
    """
    primary = _columns(motion_log, "IMU").copy()
    primary["TimeUS"][100:] -= 5
    secondary = _columns(motion_log, "IMU").copy()
    secondary["I"] = 1
    motion_log.add_message_columns("IMU", np.stack((primary, secondary), axis=1).flatten())
    assert _evaluated_motion_intervals(motion_log) == 20


@pytest.mark.parametrize(("restart_s", "expected"), [(0.0, 0), (0.5, 0), (-0.02, 19)])
def test_restarted_imu_clock_after_an_unusable_timestamp_is_classified_by_its_sign(
    motion_log: LogData, restart_s: float, expected: int
) -> None:
    """
    A reversal to a boot time is ambiguous, while a pre-boot sample only drops its own interval.

    GIVEN: An unusable IMU timestamp followed by a sample stamped at 0.0 s, 0.5 s or -0.02 s
    WHEN: GPS motion is assessed
    THEN: Reversals to 0.0 s or 0.5 s stop the IMU evaluation, and the pre-boot sample leaves 19 intervals evaluated
    """
    imu = _columns(motion_log, "IMU")
    imu["TimeUS"][100] = np.nan
    imu["TimeUS"][101] = restart_s
    assert _evaluated_motion_intervals(motion_log) == expected


def test_identical_consecutive_imu_timestamp_keeps_motion_evaluation(motion_log: LogData) -> None:
    """
    An identical timestamp is not a boot-clock reversal.

    GIVEN: An IMU sample repeating the previous timestamp at 4.95 s
    WHEN: GPS motion is assessed
    THEN: All 20 GPS velocity intervals remain evaluated
    """
    _columns(motion_log, "IMU")["TimeUS"][100] = 4.95
    assert _evaluated_motion_intervals(motion_log) == 20


@pytest.mark.parametrize("value", [0.0, 255.0])
def test_receiver_indicator_accepts_boundary_values_at_boot(value: float) -> None:
    """GIVEN a boundary indicator at boot WHEN checked THEN it is available with complete coverage."""
    log = LogData()
    _add(log, "UBX1", TimeUS=[0.0], Instance=[0], jamInd=[value])

    result = GPSLogAvailabilityModel(log, _context()).check()

    assert result.available
    assert "UBX1.jamInd" in result.reason
    assert not any("UBX1.jamInd contains invalid samples" in issue.message for issue in result.issues)


@pytest.mark.parametrize(
    ("time", "value", "instance"),
    [(np.nan, 1.0, 0.0), (-1.0, 1.0, 0.0), (2.0, -1.0, 0.0), (2.0, 256.0, 0.0), (2.0, 1.5, 0.0), (2.0, 1.0, -1.0)],
)
def test_receiver_indicator_reports_partial_coverage_for_invalid_samples(time: float, value: float, instance: float) -> None:
    """GIVEN a usable sample and an invalid one WHEN checked THEN incomplete coverage is disclosed."""
    log = LogData()
    _add(log, "UBX1", TimeUS=[1.0, time], Instance=[0.0, instance], jamInd=[1.0, value])

    result = GPSLogAvailabilityModel(log, _context()).check()

    assert result.available
    assert "UBX1.jamInd" in result.reason
    assert any(issue.message == "UBX1.jamInd contains invalid samples; coverage is incomplete" for issue in result.issues)


def test_event_intervals_do_not_bridge_a_gap_longer_than_two_seconds() -> None:
    """GIVEN equal warnings separated by a gap WHEN grouped THEN two intervals are reported."""
    intervals = list(event_intervals(np.array([0.0, 2.5]), np.array([1.0, 1.0])))
    assert intervals == [(0, 0, 1), (1, 1, 1)]


def test_missing_receiver_sources_identify_the_unavailable_field() -> None:
    """GIVEN no receiver records WHEN checked THEN the missing capability is named in the issue."""
    result = GPSLogAvailabilityModel(LogData(), _context()).check()
    assert any(issue.message == "AERG.Jam unavailable: no numeric timestamped samples in this log" for issue in result.issues)


def test_unusable_receiver_samples_report_each_invalid_sibling_field() -> None:
    """GIVEN unusable receiver samples WHEN checked THEN each indicator is reported separately."""
    log = LogData()
    _add(log, "AERG", TimeUS=[1.0, -1.0], I=[-1.0, 0.0], Jam=[1.0, 1.0], Spf=[1.0, 1.0])
    # The valid timestamp belongs to an invalid receiver ID; both fields are unusable.
    result = GPSLogAvailabilityModel(log, _context()).check()
    assert not result.available
    assert any(
        issue.message == "AERG.Jam unavailable: timestamps, sensor identifiers or values are invalid"
        for issue in result.issues
    )
    assert any(
        issue.message == "AERG.Spf unavailable: timestamps, sensor identifiers or values are invalid"
        for issue in result.issues
    )


@pytest.mark.parametrize(
    ("times", "discontinuous"), [([1.0, 1.0], True), ([1.0, 2.0], False), ([1.0, 3.0], False), ([1.0, 3.5], True)]
)
def test_receiver_availability_reports_timestamp_gap_boundaries(times: list[float], discontinuous: bool) -> None:
    """GIVEN receiver timestamps WHEN checked THEN only duplicate or too-distant samples are flagged."""
    log = LogData()
    _add(log, "AERG", TimeUS=times, Jam=[2.0, 2.0])
    result = GPSLogAvailabilityModel(log, _context()).check()
    message = "AERG.Jam has timestamp discontinuities; event intervals stop at gaps"
    assert any(issue.message == message for issue in result.issues) is discontinuous


def test_gps_status_reports_missing_schema_and_empty_values() -> None:
    """GIVEN absent or empty fix status WHEN checked THEN the reason identifies the missing data."""
    missing = LogData()
    _add(missing, "GPS", TimeUS=[1.0])
    issues = GPSLogAvailabilityModel(missing, _context()).check_status()
    assert [issue.message for issue in issues] == ["Status field not present in this firmware's GPS schema"]

    empty = LogData()
    empty.add_message_columns("GPS", np.empty(0, dtype=[("TimeUS", "f8"), ("Status", "f8")]))
    issues = GPSLogAvailabilityModel(empty, _context()).check_status()
    assert [issue.message for issue in issues] == ["GPS fix status missing from GPS records"]


def test_three_dimensional_fix_is_not_reported_as_missing() -> None:
    """GIVEN a GPS receiver with a 3D fix WHEN checked THEN no missing-fix issue is reported."""
    log = LogData()
    _add(log, "GPS", TimeUS=[1.0], Status=[3.0])
    result = GPSLogAvailabilityModel(log, _context()).check()
    assert not any(issue.message == "GPS never achieved a 3D fix" for issue in result.issues)


@pytest.mark.parametrize(("message", "position_source", "velocity_source"), [("XKF4", 6, 6), ("XKF4", 0, 5), ("NKF4", 0, 0)])
def test_non_gps_ekf_faults_do_not_make_gnss_analysis_available(
    message: str, position_source: int, velocity_source: int
) -> None:
    """GIVEN non-GPS navigation with a logged receiver index WHEN assessed THEN unrelated faults remain excluded."""
    log = LogData()
    _add(
        log,
        message,
        TimeUS=[1, 2, 3],
        C=[0] * 3,
        PI=[0] * 3,
        FS=[0, 2, 2],
        OFN=[0, 5, 5],
        OFE=[0, 3, 3],
        SV=[2] * 3,
        SP=[2] * 3,
        TS=[3] * 3,
        GPS=[1] * 3,
    )
    if message == "XKF4":
        # Firmware logs GI even when the selected navigation sources do not use GPS.
        _add(log, "XKFS", TimeUS=[1, 2, 3], C=[0] * 3, SS=[0] * 3, GI=[0] * 3)
    context = _context()
    context.parameters.update(
        {
            "EK3_SRC1_POSXY": position_source,
            "EK3_SRC1_VELXY": velocity_source,
            "EK3_SRC2_POSXY": 3,
            "EK3_SRC2_VELXY": 3,
            "EK3_SRC_OPTIONS": 0,
            "EK2_GPS_TYPE": 3,
            "GPS1_TYPE": 0,
        }
    )

    availability = GPSLogAvailabilityModel(log, context).check()
    analysis = GPSLogAnalysis(log, context).analyse()

    assert not availability.available
    assert any("No GPS messages" in issue.message for issue in availability.issues)
    assert not analysis.available
    assert not [item for item in analysis.outcomes if item.severity == "warning"]


def test_receiver_index_without_gps_source_metadata_does_not_establish_gnss_evidence() -> None:
    """GIVEN an EKF receiver index without source configuration WHEN assessed THEN GNSS coverage is unavailable."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[1, 2, 3], C=[0] * 3, PI=[0] * 3, FS=[2] * 3, SV=[2] * 3)
    _add(log, "XKFS", TimeUS=[1, 2, 3], C=[0] * 3, SS=[0] * 3, GI=[0] * 3)

    assert not GPSLogAvailabilityModel(log, _context()).check().available
    analysis = GPSLogAnalysis(log, _context()).analyse()
    assert not analysis.available
    assert not [item for item in analysis.outcomes if item.severity == "warning"]


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
@pytest.mark.parametrize("gps_at_start", [False, True])
def test_ekf_only_availability_follows_timestamped_gps_configuration(message: str, gps_at_start: bool) -> None:
    """GIVEN GPS fusion changes with GI still logged WHEN assessed THEN only eligible rows produce warnings."""
    log = LogData()
    _add(log, message, TimeUS=[1, 2, 3, 4], C=[0] * 4, PI=[0] * 4, FS=[1] * 4)
    if message == "XKF4":
        _add(log, "XKFS", TimeUS=[1, 2, 3, 4], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    name, disabled, enabled = ("EK3_SRC1_POSXY", 6.0, 3.0) if message == "XKF4" else ("EK2_GPS_TYPE", 3.0, 0.0)
    initial, changed = (enabled, disabled) if gps_at_start else (disabled, enabled)
    log.parameter_history = ParameterHistory(initial_values={name: initial}, changes={name: (ParameterChange(3, changed),)})
    context = _context()

    assert GPSLogAvailabilityModel(log, context).check().available
    events = _warnings(GPSLogAnalysis(log, context).analyse().outcomes, f"{message}.FS")
    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == ([(1e6, 2e6)] if gps_at_start else [(3e6, 4e6)])


@pytest.mark.parametrize("field_name", ["TS", "GPS"])
def test_ekf_gps_events_split_on_receiver_and_source_set_changes(field_name: str) -> None:
    """GIVEN a persistent GPS event WHEN selection changes THEN each interval retains its receiver."""
    log = LogData()
    _add(log, "XKF4", TimeUS=list(range(6)), C=[0] * 6, PI=[0] * 6, **{field_name: [1] * 6})
    _add(log, "XKFS", TimeUS=list(range(6)), C=[0] * 6, SS=[0, 0, 0, 0, 1, 1], GI=[0, 0, 1, 1, 1, 1])
    checks = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC2_POSXY": 3})

    events = _warnings(checks.analyse(), f"XKF4.{field_name}")

    assert [(event.timestamp_us, event.end_timestamp_us) for event in events] == [(0, 1e6), (2e6, 3e6), (4e6, 5e6)]
    assert [_evidence(event)["gps_receiver"] for event in events] == [0, 1, 1]


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
@pytest.mark.parametrize("field_name", ["FS", "GPS"])
def test_ekf_events_combine_observed_fault_masks(message: str, field_name: str) -> None:
    """Changing masks retain all observed bits in one continuous interval."""
    log = LogData()
    _add(log, message, TimeUS=list(range(6)), C=[0] * 6, PI=[0] * 6, **{field_name: [1, 1, 2, 1, 2, 2]})
    if message == "XKF4":
        _add(log, "XKFS", TimeUS=list(range(6)), C=[0] * 6, SS=[0] * 6, GI=[0] * 6)
    checks = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK2_GPS_TYPE": 0})

    events = _warnings(checks.analyse(), f"{message}.{field_name}")

    assert [(event.timestamp_us, event.end_timestamp_us) for event in events] == [(0, 5e6)]
    assert _evidence(events[0])[field_name] == 3


def test_nkf4_gps_events_do_not_take_receiver_identity_from_xkfs() -> None:
    """GIVEN an NKF4 GPS fault and an XKFS receiver selection WHEN analyzed THEN no receiver is attributed to the event."""
    log = LogData()
    _add(log, "NKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, GPS=[1] * 4)
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[1] * 4)

    events = _warnings(GnssConsistencyChecks(log, {"EK2_GPS_TYPE": 0}).analyse(), "NKF4.GPS")

    assert len(events) == 1
    assert "gps_receiver" not in _evidence(events[0])


def test_gps_fault_without_source_set_is_not_merged_with_source_set_zero() -> None:
    """GIVEN a GPS fault before any source-set sample and after source set 0 WHEN analyzed THEN two events are reported."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, GPS=[1] * 4)
    _add(log, "XKFS", TimeUS=[2, 3], C=[0] * 2, SS=[0] * 2, GI=[np.nan] * 2)
    checks = GnssConsistencyChecks(log, {"EK3_SRC_OPTIONS": 1, "EK3_SRC1_VELXY": 3})

    events = _warnings(checks.analyse(), "XKF4.GPS")

    assert [(event.timestamp_us, event.end_timestamp_us) for event in events] == [(0, 1e6), (2e6, 3e6)]


@pytest.mark.parametrize("invalid_mask", [-1, 1.5, 65536, np.nan, np.inf])
def test_invalid_gps_check_masks_are_excluded_from_events_and_coverage(invalid_mask: float) -> None:
    """Invalid bitmasks cannot establish GPS-check failures or evaluated coverage."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, GPS=[invalid_mask] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()

    assert not _warnings(outcomes, "XKF4.GPS")
    coverage = next(item for item in outcomes if item.source == "XKF4.GPS.coverage")
    assert _evidence(coverage) == {"evaluated": 0.0, "total": 3.0}


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
def test_ekf_ratio_and_gps_field_coverage_have_distinct_sources(message: str) -> None:
    """Ratio coverage and GPS-check coverage retain distinct counts and do not share the warning source."""
    log = LogData()
    _add(log, message, TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, SV=[0] * 4, SP=[0] * 4, GPS=[1] * 4)
    if message == "XKF4":
        _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3, "EK2_GPS_TYPE": 0}).analyse()

    ratio_coverage = next(item for item in outcomes if item.source == f"{message}.SV/SP")
    gps_coverage = next(item for item in outcomes if item.source == f"{message}.GPS.coverage")
    assert _evidence(ratio_coverage) == {"evaluated": 8.0, "total": 8.0}
    assert _evidence(gps_coverage) == {"evaluated": 4.0, "total": 4.0}
    assert len(_warnings(outcomes, f"{message}.GPS")) == 1
    assert all(item.severity != "informational" for item in outcomes if item.source == f"{message}.GPS")


@pytest.mark.parametrize("field_name", ["FS", "GPS", "OFN", "OFE", "TS"])
def test_ekf_discontinuity_coverage_explains_missing_source_selection(field_name: str) -> None:
    """Logged EKF fields cannot be assessed without an identifiable GPS source."""
    log = LogData()
    _add(log, "GPS", TimeUS=[0, 1, 2], I=[0] * 3, Status=[3] * 3)
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, **{field_name: [1] * 3})
    context = _context()
    context.parameters.update({"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3, "EK3_SRC_OPTIONS": 0})

    outcomes = GPSLogAnalysis(log, context).analyse().outcomes

    assert not _warnings(outcomes, f"XKF4.{field_name}")
    coverage = next(item for item in outcomes if item.source == f"XKF4.{field_name}.coverage")
    assert _evidence(coverage) == {"evaluated": 0.0, "total": 3.0}
    assert "XKFS.SS" in coverage.message
    assert "skipped" in coverage.message


def test_ekf_discontinuity_coverage_counts_only_eligible_samples() -> None:
    """Coverage distinguishes eligible GPS rows from stale source selection."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3, 4], C=[0] * 5, PI=[0] * 5, GPS=[1] * 5)
    _add(log, "XKFS", TimeUS=[0, 1], C=[0] * 2, SS=[0] * 2, GI=[1] * 2)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()

    coverage = next(item for item in outcomes if item.source == "XKF4.GPS.coverage")
    assert _evidence(coverage) == {"evaluated": 4.0, "total": 5.0}
    assert len(_warnings(outcomes, "XKF4.GPS")) == 1


def test_ekf_discontinuity_coverage_respects_fuse_all_velocities_without_source_selection() -> None:
    """A missing XKFS selection does not suppress configured cross-source GPS velocity fusion."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[2] * 3)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC_OPTIONS": 1, "EK3_SRC1_VELXY": 3}).analyse()

    coverage = next(item for item in outcomes if item.source == "XKF4.TS.coverage")
    assert _evidence(coverage) == {"evaluated": 3.0, "total": 3.0}
    assert len(_warnings(outcomes, "XKF4.TS")) == 1


def test_ekf_gps_source_selection_must_belong_to_the_same_lane_and_be_current() -> None:
    """GIVEN a stale or different-lane source selection WHEN EKF is assessed THEN it cannot establish GPS evidence."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[10, 11], C=[0, 0], PI=[0, 0], FS=[1, 1])
    _add(log, "XKFS", TimeUS=[1, 10, 11], C=[0, 1, 1], SS=[0, 0, 0], GI=[0, 1, 1])
    context = _context()
    context.parameters["EK3_SRC1_POSXY"] = 3

    assert not GPSLogAvailabilityModel(log, context).check().available
    assert not _warnings(GPSLogAnalysis(log, context).analyse().outcomes, "XKF4.FS")


_DEG_PER_M = 180.0 / (np.pi * 6371000.0)
_LANE_MESSAGE_SV = (
    "EKF lane velocity innovation gate exceeded while GPS velocity fusion is configured; "
    "other velocity sources may contribute; active_primary identifies lane activity"
)


def _message_text(outcome: LogAnalysis) -> str:
    """Return the user-facing description after the source and sensor identity prefix."""
    return outcome.message.split(": ", 1)[1]


def _gps_log(times: list[float] | np.ndarray, **overrides: list[float] | np.ndarray) -> LogData:
    """GPS-only log with a healthy 3D fix, consistent boot clock and stationary receiver unless overridden."""
    t = np.asarray(times, dtype=float)
    ones = np.ones(len(t))
    fields: dict[str, list[float] | np.ndarray] = {
        "TimeUS": t,
        "Status": ones * 3,
        "Lat": ones * 48,
        "Lng": ones * 11,
        "Spd": np.zeros(len(t)),
        "GCrs": np.zeros(len(t)),
        "Alt": np.zeros(len(t)),
        "VZ": np.zeros(len(t)),
        "GWk": ones * 2400,
        "GMS": t + 1000,
    }
    fields.update(overrides)
    log = LogData()
    _add(log, "GPS", **fields)
    return log


def _add_gps_auxiliary(log: LogData, times: list[float] | np.ndarray, **overrides: list[float] | np.ndarray) -> None:
    """Receiver accuracy and velocity-availability reports aligned with the GPS samples."""
    t = np.asarray(times, dtype=float)
    ones = np.ones(len(t))
    fields: dict[str, list[float] | np.ndarray] = {
        "TimeUS": t,
        "HAcc": ones,
        "SAcc": ones * 0.1,
        "VV": ones,
        "VAcc": np.zeros(len(t)),
        "SMS": t,
    }
    fields.update(overrides)
    _add(log, "GPA", **fields)


def _motion_log(body_x_acceleration: float, gps_acceleration: float, course_deg: float, yaw_deg: float) -> LogData:
    """Level vehicle with constant body-x specific force and a GPS speed ramp along the given ground course."""
    gps_times = np.arange(0, 10.5, 0.5)
    log = _gps_log(
        gps_times,
        Spd=gps_acceleration * gps_times,
        GCrs=np.full(len(gps_times), course_deg),
    )
    _add_gps_auxiliary(log, gps_times)
    imu_times = np.arange(0, 10.05, 0.05)
    zeros = np.zeros(len(imu_times))
    _add(
        log,
        "IMU",
        TimeUS=imu_times,
        AccX=zeros + body_x_acceleration,
        AccY=zeros,
        AccZ=zeros - 9.80665,
        GyrX=zeros,
        GyrY=zeros,
        GyrZ=zeros,
        AH=zeros + 1,
        GH=zeros + 1,
        EA=zeros,
        EG=zeros,
    )
    _add(log, "ATT", TimeUS=imu_times, Roll=zeros, Pitch=zeros, Yaw=zeros + yaw_deg)
    return log


@pytest.mark.parametrize(
    ("status", "expect_loss"),
    [(0, True), (2.5, False), (7, False), (6, False)],
)
def test_gps_fix_loss_ignores_unknown_or_fractional_status_codes(status: float, expect_loss: bool) -> None:
    """
    Only a documented no-fix code after a 3D fix is a loss of fix.

    GIVEN: A 3D fix followed by a status code outside the no-fix vocabulary
    WHEN: GPS quality is checked
    THEN: Only the documented no-fix code is reported
    """
    log = _gps_log([0, 1, 2, 3], Status=[3, 3, status, 3])
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Status")
    assert bool(events) == expect_loss


def test_gps_fix_loss_warning_reports_exact_interval_and_message() -> None:
    """
    A lost 3D fix is reported over the interval it persists.

    GIVEN: A 3D fix that degrades to 2D for two samples and then recovers
    WHEN: GPS quality is checked
    THEN: One warning covers exactly the degraded interval with the user-facing message
    """
    log = _gps_log([0, 1, 2, 3, 4], Status=[3, 3, 1, 2, 3])
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Status")
    assert len(events) == 1
    assert events[0].message == "GPS.Status, sensor unknown: GPS lost its 3D fix after acquiring a fix"
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (2e6, 3e6)
    assert events[0].group == "GNSS consistency"
    assert events[0].evidence == {}


def test_gps_status_coverage_counts_only_evaluable_samples_and_explains_exclusions() -> None:
    """GIVEN one invalid status sample WHEN coverage is reported THEN it counts evaluated samples and explains exclusions."""
    outcomes = GnssConsistencyChecks(_gps_log([0, 1, 2, 3], Status=[3, 3, 7, 1]), {}).analyse()
    coverage = next(item for item in outcomes if item.source == "GPS.Status")
    assert coverage.message == (
        "GPS.Status: evaluated 3/4 samples or intervals. "
        "Startup acquisition and recovery after long gaps are excluded from fix-loss warnings."
    )
    assert coverage.severity == "informational"
    assert coverage.group == "Coverage"
    assert _evidence(coverage) == {"evaluated": 3.0, "total": 4.0}


def test_status_change_after_a_long_gap_starts_a_new_unevaluated_interval() -> None:
    """GIVEN a status drop after a nine-second data gap WHEN analyzed THEN it is not reported as fix loss."""
    log = _gps_log([0, 1, 10, 11], Status=[3, 3, 1, 1])
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Status")


@pytest.mark.parametrize(
    ("field", "baseline", "degraded", "expected"),
    [
        ("NSats", 12.0, 5.9, True),
        ("NSats", 12.0, 6.0, False),
        ("NSats", 7.0, 1.0, False),
        ("NSats", 8.0, 3.9, True),
        ("HDop", 0.5, 3.1, True),
        ("HDop", 0.5, 3.0, False),
        ("HDop", 1.0, 3.5, False),
        ("HDop", 1.0, 4.5, True),
    ],
)
def test_sustained_quality_deterioration_uses_documented_relative_thresholds(
    field: str, baseline: float, degraded: float, expected: bool
) -> None:
    """
    Quality warnings need a sustained drop below half the satellite baseline or a rise above the HDop limit.

    GIVEN: A stable baseline followed by two degraded samples
    WHEN: GPS quality is checked
    THEN: A warning is raised only when the documented threshold is crossed
    """
    times = np.arange(0, 7.0, 0.5)
    log = _gps_log(times, **{field: np.where(times < 6.0, baseline, degraded)})
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), f"GPS.{field}")
    assert bool(events) == expected


def test_quality_deterioration_warning_reports_message_interval_and_measurement() -> None:
    """GIVEN a sustained satellite-count drop WHEN analyzed THEN the warning names the degraded measurement."""
    times = np.arange(0, 7.0, 0.5)
    log = _gps_log(times, NSats=np.where(times < 6.0, 12.0, 4.0))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.NSats")
    assert len(events) == 1
    assert events[0].message == "GPS.NSats, sensor unknown: GPS quality deteriorated relative to preceding samples"
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (6e6, 6.5e6)
    assert _evidence(events[0]) == {"NSats": 4.0}


def test_gps_clock_drift_is_reported_only_beyond_one_second_over_the_window() -> None:
    """
    Clock disagreement uses a five-second reference and a one-second tolerance.

    GIVEN: A receiver clock that runs 15% or 25% fast relative to boot time
    WHEN: GPS clock progression is checked
    THEN: Only the 25% drift exceeds the one-second residual tolerance
    """
    times = np.arange(0, 10.5, 0.5)
    for drift, expected in ((0.15, False), (0.25, True)):
        log = _gps_log(times, GMS=1000 + times * (1 + drift))
        events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Clock")
        assert bool(events) == expected


def test_gps_clock_warning_reports_message_and_clock_residual() -> None:
    """GIVEN a drifting receiver clock WHEN analyzed THEN the warning reports the residual in seconds."""
    times = np.arange(0, 10.5, 0.5)
    log = _gps_log(times, GMS=1000 + times * 1.25)
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Clock")
    assert events
    assert events[0].message == "GPS.Clock, sensor unknown: GPS clock progression disagrees with the boot clock"
    assert _evidence(events[0])["clock_residual_s"] > 1.0


def test_gps_clock_coverage_counts_evaluated_intervals() -> None:
    """GIVEN four healthy GPS samples WHEN coverage is reported THEN three clock intervals are evaluated."""
    outcomes = GnssConsistencyChecks(_gps_log([0, 0.5, 1.0, 1.5]), {}).analyse()
    coverage = next(item for item in outcomes if item.source == "GPS.Clock")
    assert coverage.message == (
        "GPS.Clock: evaluated 3/3 samples or intervals. GPS week rollover is included; boot timestamps determine event time."
    )
    assert _evidence(coverage) == {"evaluated": 3.0, "total": 3.0}


def test_gps_week_rollover_keeps_clock_residual_continuous() -> None:
    """GIVEN time-of-week wrapping into the next GPS week WHEN analyzed THEN the clock is still consistent."""
    log = _gps_log(
        [0, 0.5, 1.0, 1.5],
        GWk=[2400, 2400, 2401, 2401],
        GMS=[604799.0, 604799.5, 0.0, 0.5],
    )
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Clock")


def test_gps_clock_coverage_counts_intervals_of_each_receiver_separately() -> None:
    """
    Clock intervals are evaluated and counted per receiver instead of only for the last receiver.

    GIVEN: Two receivers with interleaved healthy samples, three samples for one and two for the other
    WHEN: GPS clock coverage is reported
    THEN: All three intervals across both receivers are counted as evaluated
    """
    times = np.arange(0, 2.5, 0.5)
    log = _gps_log(times, I=[0, 0, 1, 0, 1])
    outcomes = GnssConsistencyChecks(log, {}).analyse()
    coverage = next(item for item in outcomes if item.source == "GPS.Clock")
    assert _evidence(coverage) == {"evaluated": 3.0, "total": 3.0}


@pytest.mark.parametrize(
    ("reported_speed", "accuracy", "expected"),
    [(10.0, 1.0, False), (60.0, 1.0, True), (60.0, 10.0, False)],
)
def test_position_change_is_compared_with_reported_speed_and_horizontal_accuracy(
    reported_speed: float, accuracy: float, expected: bool
) -> None:
    """
    Position change must agree with reported velocity within the reported horizontal uncertainty.

    GIVEN: Ten metres per second of true northward motion with a reported speed and accuracy
    WHEN: GPS position and velocity are checked
    THEN: Only a speed disagreement beyond the accuracy-scaled tolerance is reported
    """
    times = np.arange(0, 5.0, 0.5)
    log = _gps_log(
        times,
        Lat=48 + 10.0 * times * _DEG_PER_M,
        Spd=np.full(len(times), reported_speed),
    )
    _add_gps_auxiliary(log, times, HAcc=np.full(len(times), accuracy))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")
    assert bool(events) == expected


def test_position_velocity_warning_reports_message_residual_and_tolerance() -> None:
    """GIVEN a 60 m/s report for 10 m/s of motion WHEN analyzed THEN residual and minimum tolerance are explained."""
    times = np.arange(0, 5.0, 0.5)
    log = _gps_log(times, Lat=48 + 10.0 * times * _DEG_PER_M, Spd=np.full(len(times), 60.0))
    _add_gps_auxiliary(log, times)
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")
    assert events
    assert events[0].message == "GPS.PositionVelocity, sensor unknown: GPS position change disagrees with reported velocity"
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(10.0)
    assert _evidence(events[0])["residual_m"] == pytest.approx(25.0, rel=1e-6)


def test_position_velocity_coverage_counts_each_evaluated_interval() -> None:
    """GIVEN five healthy GPS samples WHEN coverage is reported THEN four displacement intervals are evaluated."""
    times = np.arange(0, 2.5, 0.5)
    outcomes = GnssConsistencyChecks(_gps_log(times, Lat=48 + 0 * times), {}).analyse()
    coverage = next(item for item in outcomes if item.source == "GPS.PositionVelocity")
    assert coverage.message == (
        "GPS.PositionVelocity: evaluated 4/4 samples or intervals. "
        "Longitude wrap and reported position uncertainty are accounted for."
    )


def test_eastward_motion_across_the_antimeridian_at_high_latitude_agrees_with_velocity() -> None:
    """
    Eastward motion that crosses longitude 180 degrees must not be mistaken for a disagreement.

    GIVEN: 60 metres per second of eastward motion at 60 degrees latitude that crosses the antimeridian
    WHEN: GPS position and velocity are checked
    THEN: No position-velocity disagreement is reported
    """
    times = np.arange(0, 5.0, 0.5)
    deg_per_m_east = 180.0 / (np.pi * 6371000.0 * np.cos(np.deg2rad(60.0)))
    longitude = 179.9999 + 60.0 * times * deg_per_m_east
    wrapped = (longitude + 180.0) % 360.0 - 180.0
    assert np.any(wrapped < 0)
    log = _gps_log(
        times,
        Lat=np.full(len(times), 60.0),
        Lng=wrapped,
        Spd=np.full(len(times), 60.0),
        GCrs=np.full(len(times), 90.0),
    )
    _add_gps_auxiliary(log, times)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")


@pytest.mark.parametrize(
    ("vertical_accuracy", "expected"),
    [(0.0, True), (5.0, False)],
)
def test_altitude_change_tolerance_scales_with_reported_vertical_accuracy(vertical_accuracy: float, expected: bool) -> None:
    """
    Flat altitude with a 30 m/s vertical velocity is a disagreement unless the reported vertical accuracy covers it.

    GIVEN: Flat GPS altitude and a descent of 30 m/s over half-second intervals
    WHEN: GPS altitude and vertical velocity are checked
    THEN: The disagreement is reported only when the vertical accuracy does not explain it
    """
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, VZ=np.full(len(times), 30.0))
    _add_gps_auxiliary(log, times, VAcc=np.full(len(times), vertical_accuracy))
    assert bool(_warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")) == expected


def test_altitude_warning_reports_message_residual_and_tolerance() -> None:
    """GIVEN an unexplained altitude disagreement WHEN analyzed THEN the warning reports residual and tolerance in metres."""
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, VZ=np.full(len(times), 30.0))
    _add_gps_auxiliary(log, times)
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")
    assert events
    assert (
        events[0].message
        == "GPS.AltitudeVelocity, sensor unknown: GPS altitude change disagrees with reported vertical velocity"
    )
    assert _evidence(events[0])["residual_m"] == pytest.approx(15.0)
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(10.0)


def test_altitude_check_requires_receiver_vertical_velocity_availability() -> None:
    """GIVEN a receiver that does not report vertical velocity WHEN analyzed THEN no altitude disagreement is claimed."""
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, VZ=np.full(len(times), 30.0))
    _add_gps_auxiliary(log, times, VV=np.zeros(len(times)))
    outcomes = GnssConsistencyChecks(log, {}).analyse()
    assert not _warnings(outcomes, "GPS.AltitudeVelocity")
    coverage = next(item for item in outcomes if item.source == "GPS.AltitudeVelocity")
    assert coverage.message == (
        "GPS.AltitudeVelocity: evaluated 0/3 samples or intervals. Requires receiver vertical velocity availability."
    )


def test_climb_at_forty_metres_per_second_agrees_with_down_negative_velocity() -> None:
    """
    A climb is consistent with negative down-positive velocity at a speed large enough to exceed the tolerance.

    GIVEN: GPS altitude rising 40 m/s and vertical velocity of -40 m/s
    WHEN: GPS altitude and vertical velocity are checked
    THEN: No altitude disagreement is reported
    """
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, Alt=40 * times, VZ=np.full(len(times), -40.0))
    _add_gps_auxiliary(log, times)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")


def test_altitude_check_follows_velocity_changes_sample_by_sample() -> None:
    """
    A trajectory whose vertical velocity changes between samples must be integrated with each sample's own velocity.

    GIVEN: GPS altitude integrated from a varying down-positive vertical velocity profile
    WHEN: GPS altitude and vertical velocity are checked
    THEN: The altitude and velocity agree and no disagreement is reported
    """
    times = np.arange(0, 2.5, 0.5)
    velocity = np.array([-30.0, -90.0, -150.0, -60.0, 0.0])
    altitude = np.concatenate(([0.0], -np.cumsum((velocity[1:] + velocity[:-1]) * 0.5 / 2)))
    log = _gps_log(times, Alt=altitude, VZ=velocity)
    _add_gps_auxiliary(log, times)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")


def test_altitude_tolerance_uses_each_interval_own_vertical_accuracy() -> None:
    """
    Each interval's tolerance is set by the accuracy of its own two samples, not by the first sample's accuracy.

    GIVEN: Flat GPS altitude, a 70 m/s descent and vertical accuracy that is only large near the second sample
    WHEN: GPS altitude and vertical velocity are checked
    THEN: Only the interval whose own accuracy is small is reported
    """
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, VZ=np.full(len(times), 70.0))
    _add_gps_auxiliary(log, times, VAcc=np.array([0.0, 12.0, 0.0, 0.0]))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")
    assert len(events) == 1
    assert events[0].timestamp_us == pytest.approx(1.5e6)


def test_infinite_vertical_accuracy_does_not_widen_altitude_tolerance() -> None:
    """
    A non-finite vertical accuracy is not a usable uncertainty and must not disable the altitude check.

    GIVEN: Flat GPS altitude, a 30 m/s descent and infinite vertical accuracy
    WHEN: GPS altitude and vertical velocity are checked
    THEN: The disagreement is still reported with the default 10 m tolerance
    """
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, VZ=np.full(len(times), 30.0))
    _add_gps_auxiliary(log, times, VAcc=np.full(len(times), np.inf))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")
    assert events
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(10.0)


def test_altitude_residual_equal_to_tolerance_is_not_a_disagreement() -> None:
    """
    The altitude check only reports residuals strictly greater than the tolerance.

    GIVEN: Flat GPS altitude and a 20 m/s descent that produces a 10 m residual, exactly the default tolerance
    WHEN: GPS altitude and vertical velocity are checked
    THEN: No altitude disagreement is reported
    """
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times, VZ=np.full(len(times), 20.0))
    _add_gps_auxiliary(log, times)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")


def test_altitude_check_does_not_bridge_gaps_longer_than_two_seconds() -> None:
    """
    An altitude jump across a 2.5 s data gap is not evidence of a velocity disagreement.

    GIVEN: GPS altitude that is flat within two sample groups separated by a 2.5 s gap and jumps across the gap
    WHEN: GPS altitude and vertical velocity are checked
    THEN: No altitude disagreement is reported across the gap
    """
    times = np.array([0.0, 0.5, 1.0, 3.5, 4.0, 4.5])
    log = _gps_log(times, Alt=np.array([0.0, 0.0, 0.0, 100.0, 100.0, 100.0]))
    _add_gps_auxiliary(log, times)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.AltitudeVelocity")


def test_altitude_coverage_counts_all_evaluated_intervals_of_one_receiver() -> None:
    """
    Coverage reports every evaluated interval of a receiver as evaluated, out of the intervals available.

    GIVEN: One receiver with four valid, consistent samples
    WHEN: GPS altitude and vertical velocity are checked
    THEN: The coverage reports three of three intervals evaluated
    """
    times = np.arange(0, 2.0, 0.5)
    log = _gps_log(times)
    _add_gps_auxiliary(log, times)
    coverage = next(item for item in GnssConsistencyChecks(log, {}).analyse() if item.source == "GPS.AltitudeVelocity")
    assert _evidence(coverage) == {"evaluated": 3.0, "total": 3.0}


def test_altitude_coverage_accumulates_across_receivers() -> None:
    """
    Coverage adds the intervals of every receiver instead of keeping only the last receiver's counts.

    GIVEN: Two receivers, each with four valid, consistent samples
    WHEN: GPS altitude and vertical velocity are checked
    THEN: The coverage reports six of six intervals evaluated
    """
    times = np.arange(0, 4.0, 0.5)
    instances = np.array([0.0] * 4 + [1.0] * 4)
    log = _gps_log(times, I=instances)
    _add_gps_auxiliary(log, times, I=instances)
    coverage = next(item for item in GnssConsistencyChecks(log, {}).analyse() if item.source == "GPS.AltitudeVelocity")
    assert _evidence(coverage) == {"evaluated": 6.0, "total": 6.0}


def test_altitude_coverage_has_no_intervals_for_a_single_sample() -> None:
    """
    A receiver with a single sample has no intervals to evaluate.

    GIVEN: One receiver reporting a single valid sample
    WHEN: GPS altitude and vertical velocity are checked
    THEN: The coverage reports zero intervals in total
    """
    log = _gps_log(np.array([0.0]))
    _add_gps_auxiliary(log, np.array([0.0]))
    coverage = next(item for item in GnssConsistencyChecks(log, {}).analyse() if item.source == "GPS.AltitudeVelocity")
    assert _evidence(coverage)["total"] == 0.0


@pytest.mark.parametrize(
    ("body_x", "gps_acceleration", "course", "yaw", "expect_warning"),
    [
        (10.0, 10.0, 0.0, 0.0, False),
        (10.0, 10.0, 90.0, 90.0, False),
        (10.0, 0.0, 0.0, 0.0, True),
        (10.0, 10.0, 90.0, 0.0, True),
    ],
)
def test_gps_velocity_change_is_compared_with_rotated_gravity_corrected_imu(
    body_x: float, gps_acceleration: float, course: float, yaw: float, expect_warning: bool
) -> None:
    """
    Specific force must be rotated by yaw and compared with GPS velocity along the ground course.

    GIVEN: Constant forward specific force on a level vehicle with a given heading and GPS velocity
    WHEN: GPS and inertial motion are checked
    THEN: Only physically inconsistent GPS velocity changes are reported
    """
    events = _warnings(GnssConsistencyChecks(_motion_log(body_x, gps_acceleration, course, yaw), {}).analyse(), "GPS.IMU")
    assert bool(events) == expect_warning


def test_inertial_disagreement_warning_reports_message_residual_and_gps_uncertainty_tolerance() -> None:
    """GIVEN stationary GPS during forward acceleration WHEN analyzed THEN the warning explains the disagreement."""
    events = _warnings(GnssConsistencyChecks(_motion_log(10.0, 0.0, 0.0, 0.0), {}).analyse(), "GPS.IMU")
    assert events
    assert events[0].message == "GPS.IMU, sensor unknown: GPS velocity change disagrees with gravity-corrected IMU motion"
    assert _evidence(events[0])["tolerance_m_s"] == pytest.approx(3.6)
    assert _evidence(events[0])["residual_m_s"] > 3.6


_PULSE_TIMES = np.arange(0, 10.05, 0.05)
_PULSE_ACCELERATION = np.where((_PULSE_TIMES >= 3) & (_PULSE_TIMES <= 4), 30.0, 0.0)
_PULSE_VELOCITY = np.concatenate(
    ([0.0], np.cumsum((_PULSE_ACCELERATION[1:] + _PULSE_ACCELERATION[:-1]) * np.diff(_PULSE_TIMES) / 2))
)


def _arrival_pulse_log(sms_lag_s: float, velocity_lag_s: float) -> LogData:
    """Forward acceleration pulse with GPS speed sampled at the stated velocity lag and receiver arrival lag."""
    gps_times = np.arange(0, 10.5, 0.5)
    speed = np.interp(gps_times - velocity_lag_s - 0.25, _PULSE_TIMES, _PULSE_VELOCITY)
    log = _gps_log(gps_times, Spd=speed)
    _add_gps_auxiliary(log, gps_times, SMS=gps_times - sms_lag_s)
    zeros = np.zeros(len(_PULSE_TIMES))
    _add(
        log,
        "IMU",
        TimeUS=_PULSE_TIMES,
        AccX=_PULSE_ACCELERATION,
        AccY=zeros,
        AccZ=zeros - 9.80665,
        GyrX=zeros,
        GyrY=zeros,
        GyrZ=zeros,
        AH=zeros + 1,
        GH=zeros + 1,
        EA=zeros,
        EG=zeros,
    )
    _add(log, "ATT", TimeUS=_PULSE_TIMES, Roll=zeros, Pitch=zeros, Yaw=zeros)
    return log


@pytest.mark.parametrize(
    ("sms_lag_s", "velocity_lag_s", "params"),
    [
        (0.2, 0.2, {}),
        (0.2, 0.2, {"GPS_DELAY_MS": 250}),
        (0.5, 0.5, {"GPS_DELAY_MS": 250}),
        (-0.2, 0.0, {"GPS_DELAY_MS": 250}),
        (1.0, 0.0, {"GPS_DELAY_MS": 250}),
    ],
)
def test_receiver_arrival_time_is_used_only_when_it_lags_at_most_half_a_second(
    sms_lag_s: float, velocity_lag_s: float, params: dict[str, float]
) -> None:
    """
    GPS velocity must be matched to the receiver arrival time only inside the 0 to 0.5 s lag window.

    GIVEN: A consistent acceleration pulse where GPS speed matches the stated arrival lag,
           or the GPS time when the lag is outside the window
    WHEN: GPS and inertial motion are checked, with or without a configured GPS delay
    THEN: No GPS.IMU inconsistency is reported
    """
    events = _warnings(GnssConsistencyChecks(_arrival_pulse_log(sms_lag_s, velocity_lag_s), params).analyse(), "GPS.IMU")
    assert not events


def _sharp_pulse_log(acceleration: float, speed_lag_s: float, sms_lag_s: float, instance: int | None = None) -> LogData:
    """Sinusoidal forward acceleration with GPS speed sampled at the given true latency and receiver arrival lag."""
    t = _PULSE_TIMES
    accel = acceleration * np.sin(2 * np.pi * t / 4)
    velocity = np.concatenate(([0.0], np.cumsum((accel[1:] + accel[:-1]) * np.diff(t) / 2)))
    gps_times = np.arange(0, 10.5, 0.5)
    speed = np.interp(gps_times - speed_lag_s, t, velocity)
    overrides: dict[str, np.ndarray] = {}
    if instance is not None:
        overrides["I"] = np.full(len(gps_times), float(instance))
    log = _gps_log(gps_times, Spd=speed, **overrides)
    _add_gps_auxiliary(log, gps_times, SMS=gps_times - sms_lag_s, **overrides)
    zeros = np.zeros(len(t))
    _add(
        log,
        "IMU",
        TimeUS=t,
        AccX=accel,
        AccY=zeros,
        AccZ=zeros - 9.80665,
        GyrX=zeros,
        GyrY=zeros,
        GyrZ=zeros,
        AH=zeros + 1,
        GH=zeros + 1,
        EA=zeros,
        EG=zeros,
    )
    _add(log, "ATT", TimeUS=t, Roll=zeros, Pitch=zeros, Yaw=zeros)
    return log


def test_configured_receiver_delay_is_used_exactly_rather_than_a_coarse_latency_grid() -> None:
    """
    A configured GPS delay must be applied exactly, not approximated by the nearest latency grid point.

    GIVEN: A sharp acceleration pulse whose GPS speed lags the IMU by exactly 0.25 s, with an unusable receiver arrival time
    WHEN: GPS and inertial motion are checked with GPS_DELAY_MS set to 250
    THEN: No GPS.IMU inconsistency is reported, because a 0.05 s grid error would be a 5 m/s residual
    """
    log = _sharp_pulse_log(acceleration=300.0, speed_lag_s=0.25, sms_lag_s=1.0)
    assert not _warnings(GnssConsistencyChecks(log, {"GPS_DELAY_MS": 250}).analyse(), "GPS.IMU")


def test_zero_configured_receiver_delay_falls_back_to_latency_search_instead_of_zero_lag() -> None:
    """
    A zero configured delay means no delay is known, so the latency search must still be used.

    GIVEN: A sharp acceleration pulse whose GPS speed lags the IMU by 0.2 s, with an unusable receiver arrival time
    WHEN: GPS and inertial motion are checked with GPS_DELAY_MS set to 0
    THEN: No GPS.IMU inconsistency is reported, because the 0.2 s latency is found by the search
    """
    log = _sharp_pulse_log(acceleration=100.0, speed_lag_s=0.2, sms_lag_s=1.0)
    assert not _warnings(GnssConsistencyChecks(log, {"GPS_DELAY_MS": 0}).analyse(), "GPS.IMU")


def test_wrong_configured_receiver_delay_still_reports_inconsistency() -> None:
    """
    A configured GPS delay that disagrees with the data must not hide the inconsistency.

    GIVEN: A sharp acceleration pulse whose GPS speed has no lag, with an unusable receiver arrival time
    WHEN: GPS and inertial motion are checked with GPS_DELAY_MS set to 400
    THEN: The GPS.IMU inconsistency is reported
    """
    log = _sharp_pulse_log(acceleration=300.0, speed_lag_s=0.0, sms_lag_s=1.0)
    assert _warnings(GnssConsistencyChecks(log, {"GPS_DELAY_MS": 400}).analyse(), "GPS.IMU")


def test_receiver_arrival_time_later_than_the_gps_time_is_ignored() -> None:
    """
    A receiver arrival time later than the GPS time is outside the valid window and must not be used.

    GIVEN: A sharp acceleration pulse whose GPS speed lags by 0.25 s, with receiver arrival 0.2 s after the GPS time
    WHEN: GPS and inertial motion are checked with GPS_DELAY_MS set to 250
    THEN: No GPS.IMU inconsistency is reported
    """
    log = _sharp_pulse_log(acceleration=300.0, speed_lag_s=0.25, sms_lag_s=-0.2)
    assert not _warnings(GnssConsistencyChecks(log, {"GPS_DELAY_MS": 250}).analyse(), "GPS.IMU")


def test_latency_search_finds_a_quarter_second_receiver_lag_without_configured_delay() -> None:
    """
    The latency search must find a true lag that lies on its grid without any configured delay.

    GIVEN: A sharp acceleration pulse whose GPS speed lags the IMU by 0.2 s, with an unusable receiver arrival time
    WHEN: GPS and inertial motion are checked with no GPS delay parameter
    THEN: No GPS.IMU inconsistency is reported
    """
    log = _sharp_pulse_log(acceleration=200.0, speed_lag_s=0.2, sms_lag_s=1.0)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.IMU")


def test_per_receiver_delay_parameter_takes_precedence_over_the_shared_delay_parameter() -> None:
    """
    A receiver's own delay parameter must be used in preference to the shared GPS delay parameter.

    GIVEN: A sharp acceleration pulse from receiver 1 lagging by 0.25 s, with an unusable receiver arrival time
    WHEN: GPS and inertial motion are checked with GPS1_DELAY_MS 250 and a wrong shared GPS_DELAY_MS 400
    THEN: No GPS.IMU inconsistency is reported
    """
    log = _sharp_pulse_log(acceleration=100.0, speed_lag_s=0.25, sms_lag_s=1.0, instance=0)
    assert not _warnings(GnssConsistencyChecks(log, {"GPS1_DELAY_MS": 250, "GPS_DELAY_MS": 400}).analyse(), "GPS.IMU")


def test_receiver_delay_from_parameter_history_is_resolved_at_the_gps_time() -> None:
    """
    Parameter history must supply the receiver's own delay at the GPS sample time.

    GIVEN: A sharp acceleration pulse from receiver 1 lagging by 0.25 s, with the delay logged in the parameter history
    WHEN: GPS and inertial motion are checked
    THEN: No GPS.IMU inconsistency is reported
    """
    log = _sharp_pulse_log(acceleration=300.0, speed_lag_s=0.25, sms_lag_s=1.0, instance=0)
    history = ParameterHistory(initial_values={"GPS1_DELAY_MS": 250})
    assert not _warnings(GnssConsistencyChecks(log, {}, parameter_history=history).analyse(), "GPS.IMU")


def test_shared_receiver_delay_from_parameter_history_is_resolved_at_the_gps_time() -> None:
    """
    Parameter history must supply the shared GPS delay at the GPS sample time when no receiver delay exists.

    GIVEN: A sharp acceleration pulse lagging by 0.25 s, with the shared delay logged in the parameter history
    WHEN: GPS and inertial motion are checked
    THEN: No GPS.IMU inconsistency is reported
    """
    log = _sharp_pulse_log(acceleration=300.0, speed_lag_s=0.25, sms_lag_s=1.0)
    history = ParameterHistory(initial_values={"GPS_DELAY_MS": 250})
    assert not _warnings(GnssConsistencyChecks(log, {}, parameter_history=history).analyse(), "GPS.IMU")


def _stationary_speed_log(
    times: list[float] | np.ndarray, speed: list[float] | np.ndarray, speed_accuracy: list[float] | np.ndarray
) -> LogData:
    """Stationary level vehicle with the given GPS speed and speed accuracy, so any GPS speed change is inconsistent."""
    t = np.asarray(times, dtype=float)
    log = _gps_log(t, Spd=np.asarray(speed, dtype=float))
    _add_gps_auxiliary(log, t, SAcc=np.asarray(speed_accuracy, dtype=float))
    imu_times = np.arange(-1.0, 10.05, 0.05)
    zeros = np.zeros(len(imu_times))
    _add(
        log,
        "IMU",
        TimeUS=imu_times,
        AccX=zeros,
        AccY=zeros,
        AccZ=zeros - 9.80665,
        GyrX=zeros,
        GyrY=zeros,
        GyrZ=zeros,
        AH=zeros + 1,
        GH=zeros + 1,
        EA=zeros,
        EG=zeros,
    )
    _add(log, "ATT", TimeUS=imu_times, Roll=zeros, Pitch=zeros, Yaw=zeros)
    return log


def test_gps_velocity_change_across_a_sub_tenth_second_interval_is_not_compared_with_inertial_motion() -> None:
    """
    Intervals shorter than a tenth of a second are too short to compare with inertial motion.

    GIVEN: A stationary vehicle whose GPS speed jumps by 10 m/s across a 0.05 s interval,
           followed by a further inconsistent change
    WHEN: GPS and inertial motion are checked
    THEN: The short interval is skipped, so no GPS.IMU inconsistency is reported
    """
    times = [0.5, 1.0, 1.05, 1.55, 2.05]
    log = _stationary_speed_log(times, speed=[0.0, 0.0, 10.0, 15.0, 15.0], speed_accuracy=np.full(len(times), 0.1))
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.IMU")


def test_gps_velocity_change_across_exactly_a_tenth_second_interval_is_compared_with_inertial_motion() -> None:
    """
    An interval of exactly a tenth of a second is long enough to compare with inertial motion.

    GIVEN: A stationary vehicle whose GPS speed keeps changing inconsistently, including across an interval of exactly 0.1 s
    WHEN: GPS and inertial motion are checked
    THEN: The inconsistent speed changes are reported
    """
    times = [0.1, 0.2, 0.7, 0.9]
    log = _stationary_speed_log(times, speed=[0.0, 10.0, 15.0, 25.0], speed_accuracy=np.full(len(times), 0.1))
    assert _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.IMU")


def test_zero_reported_speed_accuracy_adds_no_tolerance_margin_to_gps_velocity_comparison() -> None:
    """
    A zero speed accuracy in an interval must not inflate the inertial comparison tolerance.

    GIVEN: A stationary vehicle whose GPS speed rises by 3.15 m/s per 0.5 s, with alternating zero and 0.1 m/s speed accuracy
    WHEN: GPS and inertial motion are checked
    THEN: The 3.15 m/s residuals exceed the unchanged 3.0 m/s tolerance and are reported
    """
    times = np.arange(0, 5.0, 0.5)
    speed_accuracy = np.where(np.arange(len(times)) % 2 == 0, 0.0, 0.1)
    log = _stationary_speed_log(times, speed=6.3 * times, speed_accuracy=speed_accuracy)
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.IMU")
    assert events
    assert _evidence(events[0])["tolerance_m_s"] == pytest.approx(3.0)


def test_speed_accuracy_of_the_following_sample_does_not_widen_the_interval_tolerance() -> None:
    """
    The inertial tolerance of a GPS interval must depend only on the speed accuracy of its two samples.

    GIVEN: A stationary vehicle whose GPS speed rises by 3.15 m/s per 0.5 s,
    with a very poor speed accuracy on one middle sample
    WHEN: GPS and inertial motion are checked
    THEN: The intervals that do not involve that sample are still reported with the 3.06 m/s tolerance
    from their own two samples
    """
    times = np.arange(0, 3.01, 0.5)
    speed_accuracy = np.full(len(times), 0.01)
    speed_accuracy[3] = 1.0
    log = _stationary_speed_log(times, speed=6.3 * times, speed_accuracy=speed_accuracy)
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.IMU")
    assert events
    assert _evidence(events[0])["tolerance_m_s"] == pytest.approx(3.06)


@pytest.mark.parametrize(("delay_ms", "expect_warning"), [(1, True), (500, True), (501, False)])
def test_recorded_receiver_delay_is_applied_only_within_the_zero_to_half_second_window(
    delay_ms: float, expect_warning: bool
) -> None:
    """
    A recorded receiver delay is used as the only lag only when it is strictly positive and at most half a second.

    GIVEN: A sharp acceleration pulse whose GPS speed lags by 0.3 s, with the receiver delay set to the parametrised value
    WHEN: GPS and inertial motion are checked
    THEN: A GPS.IMU inconsistency is reported only when the recorded delay is outside the window, or misaligned with the pulse
    """
    log = _sharp_pulse_log(acceleration=300.0, speed_lag_s=0.3, sms_lag_s=1.0)
    events = _warnings(GnssConsistencyChecks(log, {"GPS_DELAY_MS": delay_ms}).analyse(), "GPS.IMU")
    assert bool(events) == expect_warning


@pytest.mark.parametrize(
    ("ratio", "value", "expected"),
    [("SV", 1.0, False), ("SV", 1.01, True), ("SP", 1.0, False), ("SP", 1.01, True)],
)
def test_lane_innovation_gate_warns_only_when_test_ratio_exceeds_one(ratio: str, value: float, expected: bool) -> None:
    """GIVEN a GPS-aided lane whose test ratio equals or exceeds the gate WHEN analyzed THEN only excess is warned."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0, 0, 0], PI=[0, 0, 0], **{ratio: [value] * 3})
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0, 0, 0], SS=[0, 0, 0], GI=[0, 0, 0])
    checks = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3})
    assert bool(_warnings(checks.analyse(), f"XKF4.{ratio}")) == expected


def test_velocity_gate_warning_reports_configuration_lane_activity_and_innovation_norm() -> None:
    """
    The velocity gate warning explains its GPS configuration and carries the velocity innovation evidence.

    GIVEN: A GPS-aided primary lane with an exceeded velocity test ratio and a 3-4 innovation
    WHEN: EKF evidence is analyzed
    THEN: The message states the GPS velocity configuration and the evidence contains the innovation norm
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0, 0, 0], PI=[0, 0, 0], SV=[2.0, 2.0, 2.0])
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0, 0, 0], SS=[0, 0, 0], GI=[0, 0, 0])
    _add(log, "XKF3", TimeUS=[0, 1, 2], C=[0, 0, 0], IVN=[3.0, 3.0, 3.0], IVE=[4.0, 4.0, 4.0])
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_VELXY": 3}).analyse(), "XKF4.SV")
    assert len(events) == 1
    assert _message_text(events[0]) == _LANE_MESSAGE_SV
    assert _evidence(events[0]) == {"test_ratio": 2.0, "active_primary": 1.0, "gps_receiver": 0.0, "innovation_norm": 5.0}


def test_position_gate_warning_uses_position_message_without_velocity_wording() -> None:
    """GIVEN an exceeded GPS position gate WHEN analyzed THEN the position-specific message is used."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0, 0, 0], PI=[0, 0, 0], SP=[2.0, 2.0, 2.0])
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0, 0, 0], SS=[0, 0, 0], GI=[0, 0, 0])
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.SP")
    assert len(events) == 1
    assert _message_text(events[0]) == (
        "EKF lane GPS position innovation gate exceeded; active_primary identifies lane activity"
    )


def test_lane_gate_coverage_counts_samples_and_states_gps_aided_evidence() -> None:
    """GIVEN three GPS-aided lane samples WHEN coverage is reported THEN all three are evaluated."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0, 0, 0], PI=[0, 0, 0], SV=[1.0, 1.0, 1.0])
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0, 0, 0], SS=[0, 0, 0], GI=[0, 0, 0])
    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_VELXY": 3}).analyse()
    coverage = next(item for item in outcomes if item.source == "XKF4.SV/SP")
    assert coverage.message == (
        "XKF4.SV/SP: evaluated 3/3 samples or intervals. "
        "Every logged lane is checked independently; GPS source selection is required. EKF evidence is GPS-aided."
    )
    assert _evidence(coverage) == {"evaluated": 3.0, "total": 3.0}


def test_gps_fault_mask_warning_uses_fault_message_and_raw_bitmask_evidence() -> None:
    """GIVEN a GPS-aided lane reporting a fault mask WHEN analyzed THEN the fault wording and raw mask are retained."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, FS=[0, 4, 4, 0])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.FS")
    assert len(events) == 1
    assert _message_text(events[0]) == "EKF lane reports a fault or GPS quality check failure"
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (1e6, 2e6)
    assert _evidence(events[0]) == {"FS": 4.0, "active_primary": 1.0}


def test_gps_fault_coverage_states_source_selection_requirements() -> None:
    """GIVEN four GPS-aided fault samples WHEN coverage is reported THEN every sample is evaluated with its requirements."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, FS=[0, 4, 4, 0])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()
    coverage = next(item for item in outcomes if item.source == "XKF4.FS.coverage")
    assert coverage.message.startswith(
        "XKF4.FS.coverage: evaluated 4/4 samples or intervals. "
        "Samples without a usable GPS navigation source are skipped; startup exclusions may also apply."
    )
    assert coverage.message.endswith(
        " XKFS.SS identifies the active source set; FuseAllVelocities can enable GPS velocity fusion."
    )


@pytest.mark.parametrize(
    ("step", "expected"),
    [(0.005, False), (0.02, True)],
)
def test_position_reset_warning_requires_a_change_above_one_centimetre(step: float, expected: bool) -> None:
    """GIVEN a north offset reset of 5 mm or 2 cm WHEN analyzed THEN only the larger jump is reported."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, OFN=[0, 0, step, step])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    checks = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3})
    assert bool(_warnings(checks.analyse(), "XKF4.OFN")) == expected


def test_position_reset_warning_reports_message_time_and_changed_offset() -> None:
    """GIVEN a 2 cm north offset reset WHEN analyzed THEN the warning identifies the reset instant and magnitude."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, OFN=[0, 0, 0.02, 0.02])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")
    assert len(events) == 1
    assert _message_text(events[0]) == "EKF lane position reset changed"
    assert events[0].timestamp_us == 2e6
    assert _evidence(events[0])["OFN"] == pytest.approx(0.02)


def test_gps_timeout_warning_uses_timeout_message_and_raw_timeout_mask() -> None:
    """GIVEN a GPS position timeout bit on a GPS-aided lane WHEN analyzed THEN the timeout wording and mask are kept."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, TS=[0, 1, 1, 0])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.TS")
    assert len(events) == 1
    assert _message_text(events[0]) == "EKF lane GPS position or velocity measurement timed out"
    assert _evidence(events[0])["gps_timeout_mask"] == 1.0


def _series(times: list[float], **fields: list[float]) -> SensorSeries:
    values = {"TimeUS": np.asarray(times, dtype=float)}
    values.update({name: np.asarray(column, dtype=float) for name, column in fields.items()})
    return SensorSeries(instance=0, fields=values)


def _rotation_body_to_ned(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    roll, pitch, yaw = np.deg2rad([roll_deg, pitch_deg, yaw_deg])
    rot_x = np.array([[1.0, 0.0, 0.0], [0.0, np.cos(roll), -np.sin(roll)], [0.0, np.sin(roll), np.cos(roll)]])
    rot_y = np.array([[np.cos(pitch), 0.0, np.sin(pitch)], [0.0, 1.0, 0.0], [-np.sin(pitch), 0.0, np.cos(pitch)]])
    rot_z = np.array([[np.cos(yaw), -np.sin(yaw), 0.0], [np.sin(yaw), np.cos(yaw), 0.0], [0.0, 0.0, 1.0]])
    return rot_z @ rot_y @ rot_x


def test_gps_fix_accepts_rtk_fixed_status_six_and_rejects_status_seven() -> None:
    """GIVEN GPS fix codes 2, 6 and 7 WHEN screened THEN only the 3D-to-RTK-fixed range 3..6 is accepted."""
    series = _series([0.0, 1.0, 2.0], Status=[2.0, 6.0, 7.0])
    assert _gps_fix(series).tolist() == [False, True, False]


def test_gps_fix_rejects_non_integer_status_codes() -> None:
    """GIVEN a fractional fix code between valid codes WHEN screened THEN it is rejected."""
    series = _series([0.0, 1.0, 2.0], Status=[3.0, 3.5, 4.0])
    assert _gps_fix(series).tolist() == [True, False, True]


@pytest.mark.parametrize(("roll", "pitch", "yaw"), [(30.0, 20.0, 40.0), (-15.0, 35.0, -120.0)])
def test_body_to_ned_rotates_specific_force_and_adds_downward_gravity(roll: float, pitch: float, yaw: float) -> None:
    """GIVEN a body-axis specific force and a non-trivial attitude WHEN rotated THEN it matches ZYX rotation plus gravity."""
    acceleration = np.array([[1.0, 2.0, 3.0]])
    attitude = np.array([[roll, pitch, yaw]])
    expected = _rotation_body_to_ned(roll, pitch, yaw) @ acceleration[0] + np.array([0.0, 0.0, 9.80665])
    assert np.allclose(_body_to_ned(acceleration, attitude)[0], expected, atol=1e-9)


def test_interpolation_returns_nan_when_sample_times_run_backwards() -> None:
    """GIVEN samples whose timestamps decrease WHEN interpolated THEN no value is produced."""
    series = _series([0.0, 2.0, 1.0, 3.0], Spd=[0.0, 20.0, 10.0, 30.0])
    result = _interpolate(series, np.array([0.5]), ("Spd",), 5.0)
    assert np.isnan(result).all()


def test_interpolation_uses_segments_with_duplicate_timestamps_split_out() -> None:
    """GIVEN a repeated timestamp that splits the record WHEN interpolated THEN the later stretch still yields values."""
    series = _series([0.0, 1.0, 1.0, 2.0, 3.0], Spd=[0.0, 10.0, 10.0, 20.0, 30.0])
    result = _interpolate(series, np.array([2.5]), ("Spd",), 5.0)
    assert result[0, 0] == pytest.approx(25.0)


def test_interpolation_accepts_two_sample_segments() -> None:
    """GIVEN a continuous segment of exactly two samples WHEN interpolated THEN its midpoint is returned."""
    series = _series([0.0, 1.0], Spd=[0.0, 10.0])
    result = _interpolate(series, np.array([0.5]), ("Spd",), 5.0)
    assert result[0, 0] == pytest.approx(5.0)


def test_interpolation_skips_single_sample_segment_without_dropping_later_segments() -> None:
    """GIVEN an isolated single valid sample followed by a valid segment WHEN interpolated THEN the later segment is used."""
    series = _series([0.0, 1.0, 2.0, 3.0, 4.0], Spd=[0.0, np.nan, 20.0, 30.0, 40.0])
    result = _interpolate(series, np.array([2.5]), ("Spd",), 5.0)
    assert result[0, 0] == pytest.approx(25.0)


def test_interpolation_never_extrapolates_beyond_segment_ends() -> None:
    """GIVEN query times before and after a segment WHEN interpolated THEN they remain undefined."""
    series = _series([0.0, 1.0, 2.0], Spd=[0.0, 10.0, 20.0])
    result = _interpolate(series, np.array([-0.5, 1.5, 2.5]), ("Spd",), 5.0)
    assert np.isnan(result[0, 0])
    assert result[1, 0] == pytest.approx(15.0)
    assert np.isnan(result[2, 0])


def test_interpolation_includes_query_at_last_segment_sample() -> None:
    """GIVEN a query exactly at the final sample of a segment WHEN interpolated THEN the final value is returned."""
    series = _series([0.0, 1.0, 2.0], Spd=[0.0, 10.0, 20.0])
    result = _interpolate(series, np.array([2.0]), ("Spd",), 5.0)
    assert result[0, 0] == pytest.approx(20.0)


@pytest.mark.parametrize("attitude_name", ["Roll", "Pitch", "Yaw"])
def test_interpolation_unwraps_attitude_angles_across_the_180_degree_seam(attitude_name: str) -> None:
    """GIVEN attitude samples either side of the 180 degree seam WHEN interpolated THEN the short path through 180 is used."""
    series = _series([0.0, 1.0], **{attitude_name: [170.0, -170.0]})
    result = _interpolate(series, np.array([0.5]), (attitude_name,), 5.0)
    assert abs(result[0, 0]) == pytest.approx(180.0)


def test_interpolation_does_not_unwrap_non_attitude_channels() -> None:
    """GIVEN a non-attitude channel that jumps across 180 WHEN interpolated THEN the raw linear midpoint is returned."""
    series = _series([0.0, 1.0], Spd=[170.0, -170.0])
    result = _interpolate(series, np.array([0.5]), ("Spd",), 5.0)
    assert result[0, 0] == pytest.approx(0.0)


def _inertial_track(*segments: tuple[list[float], list[float]]) -> _InertialTrack:
    """Build one IMU track from (times, north velocity) segments with zero east and down velocity."""
    series = tuple(_series(times, VN=velocity, VE=[0.0] * len(times), VD=[0.0] * len(times)) for times, velocity in segments)
    return _InertialTrack(np.array([segment.times[0] for segment in series]), series)


@pytest.mark.parametrize("times", [[1.0, 1.0], [2.0, 1.0]])
def test_prediction_residual_is_undefined_for_an_interval_that_does_not_advance(times: list[float]) -> None:
    """
    Non-advancing receiver intervals cannot be predicted.

    GIVEN: A healthy IMU track covering the requested time
    WHEN: The receiver interval is equal or reversed
    THEN: No residual is produced
    """
    track = _inertial_track(([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0]))
    assert np.isnan(_prediction_residual([track], np.array(times), np.zeros(3)))


def test_prediction_residual_is_undefined_without_a_track_covering_the_interval() -> None:
    """
    No residual is invented when no healthy IMU is available.

    GIVEN: No IMU tracks
    WHEN: A residual is requested for a valid interval
    THEN: The residual is undefined
    """
    assert np.isnan(_prediction_residual([], np.array([1.0, 2.0]), np.zeros(3)))


def test_prediction_residual_uses_the_segment_containing_the_interval_start() -> None:
    """
    The prediction segment is selected by the interval start.

    GIVEN: An IMU whose first segment ends before the interval end and a later segment covers that end
    WHEN: The residual is requested for an interval starting in the first segment
    THEN: The residual is undefined because the start segment cannot predict the interval
    """
    track = _inertial_track(([0.0, 1.0], [0.0, 1.0]), ([1.5, 3.0], [1.5, 3.0]))
    assert np.isnan(_prediction_residual([track], np.array([1.0, 2.0]), np.zeros(3)))


def test_prediction_residual_accepts_an_interval_ending_exactly_at_segment_end() -> None:
    """
    A receiver interval ending on the last IMU sample is predictable.

    GIVEN: An IMU segment with constant northward acceleration
    WHEN: The interval ends exactly at the segment's final sample
    THEN: The residual matches the prediction
    """
    track = _inertial_track(([0.0, 1.0, 2.0], [0.0, 1.0, 2.0]))
    residual = _prediction_residual([track], np.array([0.5, 2.0]), np.array([1.5, 0.0, 0.0]))
    assert residual == pytest.approx(0.0)


def test_prediction_residual_accepts_an_interval_ending_after_the_penultimate_sample() -> None:
    """
    A receiver interval ending between the last two IMU samples is predictable.

    GIVEN: An IMU segment with constant northward acceleration
    WHEN: The interval ends between the last two samples of the segment
    THEN: The residual matches the prediction
    """
    track = _inertial_track(([0.0, 0.5, 1.0], [0.0, 0.5, 1.0]))
    residual = _prediction_residual([track], np.array([0.2, 0.9]), np.array([0.7, 0.0, 0.0]))
    assert residual == pytest.approx(0.0)


def test_prediction_residual_reports_the_healthy_imu_after_skipping_unusable_tracks() -> None:
    """
    Unusable IMU tracks do not hide a healthy one.

    GIVEN: One IMU starting after the interval, one ending before it, and one healthy IMU
    WHEN: The residual is requested
    THEN: The healthy IMU's discrepancy is reported
    """
    starts_late = _inertial_track(([2.0, 3.0], [2.0, 3.0]))
    ends_early = _inertial_track(([0.0, 0.4], [0.0, 0.4]))
    healthy = _inertial_track(([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0]))
    residual = _prediction_residual([starts_late, ends_early, healthy], np.array([0.5, 1.5]), np.zeros(3))
    assert residual == pytest.approx(1.0)


def test_gps_velocity_only_timeout_keeps_only_the_velocity_bit() -> None:
    """
    Position-only timeout bits are not GPS evidence when GPS supplies only velocity.

    GIVEN: GPS velocity fusion with non-GPS position fusion and both timeout bits set
    WHEN: GNSS consistency is checked
    THEN: Only the velocity timeout bit is retained as GPS evidence
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[3] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)
    parameters = {"EK3_SRC1_POSXY": 0, "EK3_SRC1_VELXY": 3, "EK2_GPS_TYPE": 0}

    events = _warnings(GnssConsistencyChecks(log, parameters).analyse(), "XKF4.TS")

    assert len(events) == 1
    assert _evidence(events[0])["gps_timeout_mask"] == 2.0


def test_gps_velocity_only_position_timeout_bit_is_not_reported() -> None:
    """
    A position-only timeout does not become a GPS velocity timeout.

    GIVEN: GPS velocity fusion with non-GPS position fusion and only the position timeout bit set
    WHEN: GNSS consistency is checked
    THEN: No GPS timeout warning is produced
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[1] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)
    parameters = {"EK3_SRC1_POSXY": 0, "EK3_SRC1_VELXY": 3, "EK2_GPS_TYPE": 0}

    assert not _warnings(GnssConsistencyChecks(log, parameters).analyse(), "XKF4.TS")


@pytest.mark.parametrize("message", ["XKF4", "NKF4"])
def test_gps_timeout_retains_the_largest_eight_bit_timeout_value(message: str) -> None:
    """
    The largest representable timeout bitmask is preserved.

    GIVEN: GPS position and velocity fusion with every timeout bit set
    WHEN: GNSS consistency is checked
    THEN: The warning retains the full raw mask and both GPS timeout bits
    """
    log = LogData()
    _add(log, message, TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[255] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)
    parameters = {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3, "EK2_GPS_TYPE": 0}

    events = _warnings(GnssConsistencyChecks(log, parameters).analyse(), f"{message}.TS")

    assert len(events) == 1
    assert _evidence(events[0])["TS"] == 255.0
    assert _evidence(events[0])["gps_timeout_mask"] == 3.0


def test_rtk_fixed_status_six_keeps_an_established_gps_fix() -> None:
    """
    RTK fixed status counts as a 3D fix, so a later non-fix status is a fix loss.

    GIVEN: A 3D fix, then RTK fixed, then no fix
    WHEN: GNSS consistency is checked
    THEN: The fix loss is reported at the no-fix sample
    """
    log = LogData()
    _add(log, "GPS", TimeUS=[0, 1, 2], I=[0] * 3, Status=[3, 6, 0])

    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Status")

    assert len(events) == 1
    assert events[0].timestamp_us == 2e6


def test_gps_fix_evaluation_restarts_after_a_gap_longer_than_two_seconds() -> None:
    """
    Recovery after a long gap is excluded from fix-loss evaluation.

    GIVEN: A 3D fix followed by a 2.5 second gap and then no fix
    WHEN: GNSS consistency is checked
    THEN: No fix-loss warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=[0, 1, 3.5], I=[0] * 3, Status=[3, 3, 0])

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.Status")


def test_gps_status_coverage_counts_every_receiver() -> None:
    """
    Coverage accounts for all receivers, not only the last one.

    GIVEN: Two GPS receivers with three healthy samples each
    WHEN: GNSS consistency is checked
    THEN: The GPS status coverage evaluates all six samples
    """
    log = LogData()
    _add(log, "GPS", TimeUS=[0, 1, 2, 0, 1, 2], I=[0, 0, 0, 1, 1, 1], Status=[3] * 6)

    coverage = next(item for item in GnssConsistencyChecks(log, {}).analyse() if item.source == "GPS.Status")

    assert _evidence(coverage) == {"evaluated": 6.0, "total": 6.0}


def test_satellite_count_samples_without_a_fix_are_not_judged() -> None:
    """
    Satellite count degradation is judged only on fixed GPS samples.

    GIVEN: A fixed GPS with a satellite count drop to 2 while the receiver reports no fix
    WHEN: GNSS consistency is checked
    THEN: No satellite count degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(7)), I=[0] * 7, Status=[3] * 6 + [0], NSats=[10] * 6 + [2])

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.NSats")


def test_satellite_count_zero_is_not_a_valid_quality_sample() -> None:
    """
    A zero satellite count is not a valid degradation sample.

    GIVEN: A fixed GPS whose satellite count drops to zero
    WHEN: GNSS consistency is checked
    THEN: No satellite count degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(9)), I=[0] * 9, Status=[3] * 9, NSats=[10] * 6 + [0] * 3)

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.NSats")


def test_satellite_count_drop_after_a_gap_of_two_and_a_half_seconds_is_not_judged() -> None:
    """
    A satellite count drop after a long gap starts a new evaluation window.

    GIVEN: Six fixed samples with ten satellites, then a 2.5 second gap and two samples with two satellites
    WHEN: GNSS consistency is checked
    THEN: No satellite count degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=[0, 1, 2, 3, 4, 5, 7.5, 8.5], I=[0] * 8, Status=[3] * 8, NSats=[10] * 6 + [2, 2])

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.NSats")


def test_samples_without_a_fix_do_not_extend_a_satellite_count_degradation() -> None:
    """
    Samples without a fix cannot form a satellite count degradation.

    GIVEN: A fixed GPS followed by three samples without a fix, each reporting two satellites
    WHEN: GNSS consistency is checked
    THEN: No satellite count degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(9)), I=[0] * 9, Status=[3] * 6 + [0] * 3, NSats=[10] * 6 + [2] * 3)

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.NSats")


def test_single_sample_satellite_count_drop_is_not_reported() -> None:
    """
    A satellite count drop lasting one sample is shorter than the warning duration.

    GIVEN: A fixed GPS whose satellite count drops for a single sample
    WHEN: GNSS consistency is checked
    THEN: No satellite count degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(7)), I=[0] * 7, Status=[3] * 7, NSats=[10] * 6 + [2])

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.NSats")


def test_satellite_count_baseline_uses_exactly_the_preceding_twenty_samples() -> None:
    """
    The satellite count baseline is the median of exactly the twenty preceding samples.

    GIVEN: A fixed GPS whose satellite count is one sample older than the twenty-sample window
           at the first drop to four, and whose median is eight within the window
    WHEN: GNSS consistency is checked
    THEN: The satellite count degradation is reported starting at the drop
    """
    log = LogData()
    nsats = [10] * 4 + [1] + [8] * 10 + [12] * 10 + [4] * 2 + [10] * 3
    _add(log, "GPS", TimeUS=list(range(len(nsats))), I=[0] * len(nsats), Status=[3] * len(nsats), NSats=nsats)

    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.NSats")

    assert len(events) == 1
    assert events[0].timestamp_us == 25e6


def test_hdop_spike_before_a_full_preceding_window_is_not_judged() -> None:
    """
    HDop spikes need the full preceding window before they are judged.

    GIVEN: A fixed GPS with a two-sample HDop spike at the start of the log
    WHEN: GNSS consistency is checked
    THEN: No HDop degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(8)), I=[0] * 8, Status=[3] * 8, HDop=[1.0, 1.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0])

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.HDop")


def test_hdop_spike_is_not_judged_against_a_window_that_is_not_its_own() -> None:
    """
    HDop degradation is judged against samples of the same continuous segment only.

    GIVEN: Eight samples with HDop one, a 2.5 second gap, then seven samples with HDop nine
    WHEN: GNSS consistency is checked
    THEN: No HDop degradation warning is produced
    """
    log = LogData()
    times = [*range(8), *(9.5 + index for index in range(7))]
    _add(log, "GPS", TimeUS=times, I=[0] * 15, Status=[3] * 15, HDop=[1.0] * 8 + [9.0] * 7)

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.HDop")


def test_hdop_spike_is_not_judged_before_the_window_of_its_segment_is_full() -> None:
    """
    Samples before the first full HDop window are not judged, even when they are spikes.

    GIVEN: A fixed GPS with HDop one, two samples of HDop nine, then HDop one again
    WHEN: GNSS consistency is checked
    THEN: No HDop degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(8)), I=[0] * 8, Status=[3] * 8, HDop=[1.0, 1.0, 1.0, 9.0, 9.0, 1.0, 1.0, 1.0])

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.HDop")


def test_hdop_samples_without_enough_history_are_not_judged() -> None:
    """
    HDop degradation needs a preceding window before it can be judged.

    GIVEN: A fixed GPS with a constant HDop of five and no earlier history
    WHEN: GNSS consistency is checked
    THEN: No HDop degradation warning is produced
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(6)), I=[0] * 6, Status=[3] * 6, HDop=[5.0] * 6)

    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.HDop")


def test_hdop_spike_is_judged_once_the_preceding_window_is_available() -> None:
    """
    The first HDop sample with a full preceding window is judged.

    GIVEN: A fixed GPS with HDop of one, then a sustained spike to five from the sixth sample
    WHEN: GNSS consistency is checked
    THEN: The HDop degradation is reported starting at the sixth sample
    """
    log = LogData()
    _add(log, "GPS", TimeUS=list(range(8)), I=[0] * 8, Status=[3] * 8, HDop=[1.0] * 5 + [5.0] * 3)

    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.HDop")

    assert len(events) == 1
    assert events[0].timestamp_us == 5e6


def _ekf_startup_log(
    status: list[float], fault_status: list[float] | None = None, offsets: list[float] | None = None
) -> LogData:
    """Build a single-lane XKF4 position-offset log with the given status, fault and offset samples."""
    log = LogData()
    times = list(range(4))
    _add(
        log,
        "XKF4",
        TimeUS=times,
        C=[0] * 4,
        PI=[0] * 4,
        SS=status,
        FS=fault_status or [0] * 4,
        OFN=offsets or [0, 5, 5, 5],
    )
    _add(log, "XKFS", TimeUS=times, C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    return log


def test_ekf_status_bit_zero_alone_is_not_startup_so_reset_warns() -> None:
    """
    Status bit zero alone does not mark EKF initialization.

    GIVEN an XKF4 lane whose status word is 1 (only bit 0 set) throughout, with a position offset reset
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN the position-offset reset is reported as a warning
    """
    events = _warnings(GnssConsistencyChecks(_ekf_startup_log([1] * 4), {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")
    assert len(events) == 1
    assert events[0].timestamp_us == 1e6


@pytest.mark.parametrize("status", [129, 128])
def test_ekf_startup_status_bit_seven_excludes_reset_during_initialization(status: int) -> None:
    """
    Initialization status suppresses position resets while uninitialized.

    GIVEN an XKF4 lane whose status word has the initialization bit set throughout, with a position offset reset
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN the position-offset reset during initialization is not reported
    """
    assert not _warnings(GnssConsistencyChecks(_ekf_startup_log([status] * 4), {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")


def test_ekf_startup_status_is_recognized_at_the_sample_where_initialization_clears() -> None:
    """
    Initialization ends when horizontal position aiding is established.

    GIVEN an XKF4 lane initializing until horizontal position aiding is established at its third sample,
    with position offset resets at the second and fourth samples
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN only the reset after aiding is established is reported, at the fourth sample
    """
    log = LogData()
    times = list(range(4))
    _add(log, "XKF4", TimeUS=times, C=[0] * 4, PI=[0] * 4, SS=[129, 129, 16, 16], OFN=[0, 5, 5, 10])
    _add(log, "XKFS", TimeUS=times, C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")
    assert len(events) == 1
    assert events[0].timestamp_us == 3e6


@pytest.mark.parametrize("invalid_status", [-1.0, float("nan")])
def test_invalid_ekf_status_words_do_not_mark_startup(invalid_status: float) -> None:
    """
    Invalid status words are ignored for initialization detection.

    GIVEN an XKF4 lane whose first status word is invalid, followed by initialization status, with a position offset reset
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN the invalid status word is ignored and the reset during initialization is not reported
    """
    status = [invalid_status, 128, 128, 128]
    assert not _warnings(GnssConsistencyChecks(_ekf_startup_log(status), {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")


def test_ekf_status_word_above_uint32_range_is_ignored() -> None:
    """
    Status words beyond the 32-bit range are ignored.

    GIVEN an XKF4 lane whose first status word exceeds the 32-bit range, followed by initialization status
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN the out-of-range status word is ignored and the position offset reset at the third sample is reported
    """
    status = [4294967295.0, 128, 128, 128]
    offsets = [0, 0, 5, 5]
    events = _warnings(
        GnssConsistencyChecks(_ekf_startup_log(status, offsets=offsets), {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN"
    )
    assert len(events) == 1
    assert events[0].timestamp_us == 2e6


@pytest.mark.parametrize("fault_value", [-1.0, 70128.0])
def test_invalid_fault_word_does_not_mark_ekf_initialization(fault_value: float) -> None:
    """
    Invalid fault words are ignored for initialization detection.

    GIVEN an XKF4 lane with a settled status word and an out-of-range fault word, with a position offset reset
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN the invalid fault word is ignored and the reset is reported as a warning
    """
    events = _warnings(
        GnssConsistencyChecks(_ekf_startup_log([0] * 4, fault_status=[fault_value] * 4), {"EK3_SRC1_POSXY": 3}).analyse(),
        "XKF4.OFN",
    )
    assert len(events) == 1
    assert events[0].timestamp_us == 1e6


def test_maximum_valid_fault_word_is_read_as_initialization() -> None:
    """
    The maximum valid fault word marks initialization.

    GIVEN an XKF4 lane with the maximum 16-bit fault word, which sets the initialization bit, and a settled status word
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN the reset during initialization is not reported
    """
    status = [0] * 4
    fault = [65535.0] * 4
    assert not _warnings(
        GnssConsistencyChecks(_ekf_startup_log(status, fault_status=fault), {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN"
    )


def test_nan_fault_word_does_not_hide_ekf_status_startup() -> None:
    """
    A NaN fault word does not hide startup detection.

    GIVEN an XKF4 lane with initialization status and a NaN fault word, with a position offset reset after aiding starts
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN the analysis completes and reports only the reset after aiding is established
    """
    status = [129, 129, 16, 16]
    fault = [float("nan")] * 4
    offsets = [0, 5, 5, 10]
    events = _warnings(
        GnssConsistencyChecks(_ekf_startup_log(status, fault_status=fault, offsets=offsets), {"EK3_SRC1_POSXY": 3}).analyse(),
        "XKF4.OFN",
    )
    assert len(events) == 1
    assert events[0].timestamp_us == 3e6


def test_startup_status_of_another_ekf_lane_does_not_hide_a_reset() -> None:
    """
    Initialization status is tracked per EKF lane.

    GIVEN two XKF4 lanes alternating samples, where only lane 1 reports initialization status
    WHEN the GNSS consistency analysis runs with the primary EKF using GPS for position
    THEN lane 0 reports its position offset reset, and lane 1 does not
    """
    log = LogData()
    times = list(range(4))
    _add(log, "XKF4", TimeUS=times, C=[0, 1, 0, 1], PI=[0] * 4, SS=[0, 128, 0, 128], OFN=[0, 0, 5, 5])
    _add(log, "XKFS", TimeUS=times, C=[0, 1, 0, 1], SS=[0] * 4, GI=[0] * 4)
    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()
    events = _warnings(outcomes, "XKF4.OFN")
    assert [item.instance for item in events] == [0]
    assert events[0].timestamp_us == 2e6


def test_nkf4_position_timeouts_with_gps_type_one_are_attributed_to_gps() -> None:
    """
    NKF4 position timeouts with GPS type 1 are attributed to GPS.

    GIVEN an NKF4 position timeout while EK2 uses GPS type 1
    WHEN the GNSS consistency analysis runs
    THEN the timeout is attributed to GPS position navigation
    """
    log = LogData()
    _add(log, "NKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[1] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)

    events = _warnings(GnssConsistencyChecks(log, {"EK2_GPS_TYPE": 1}).analyse(), "NKF4.TS")

    assert len(events) == 1
    assert _evidence(events[0])["gps_timeout_mask"] == 1


@pytest.mark.parametrize("receiver_index", [-1.0, 256.0, 300.0])
def test_gps_receiver_indices_outside_byte_range_are_not_reported(receiver_index: float) -> None:
    """
    Out-of-range GPS receiver indices are not attributed.

    GIVEN a GPS position timeout whose EKF GPS receiver index is outside the valid byte range
    WHEN the GNSS consistency analysis runs
    THEN the timeout is reported without attributing it to any receiver
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[1] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3, GI=[receiver_index] * 3)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.TS")

    assert len(events) == 1
    assert np.isnan(_evidence(events[0]).get("gps_receiver", np.nan))


def test_gps_receiver_index_255_is_kept_as_the_highest_valid_receiver() -> None:
    """
    GPS receiver index 255 is kept as a valid receiver.

    GIVEN a GPS position timeout whose EKF GPS receiver index is 255, the highest valid byte value
    WHEN the GNSS consistency analysis runs
    THEN the timeout is attributed to receiver 255
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[1] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3, GI=[255] * 3)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.TS")

    assert len(events) == 1
    assert _evidence(events[0])["gps_receiver"] == 255.0


@pytest.mark.parametrize(
    ("extra_parameters", "expect_warning"),
    [
        ({"EK3_SRC2_VELXY": 3}, True),
        ({"EK3_SRC3_VELXY": 3}, True),
        ({}, False),
    ],
)
def test_fuse_all_velocities_uses_any_velocity_source_selection(
    extra_parameters: dict[str, int], expect_warning: bool
) -> None:
    """
    FuseAllVelocities uses any velocity source selection.

    GIVEN a velocity timeout with FuseAllVelocities enabled and a GPS velocity source selected on source 2, 3 or none
    WHEN the GNSS consistency analysis runs
    THEN the timeout is attributed to GPS velocity only when a source selects GPS velocity
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[2] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)
    parameters = {"EK3_SRC_OPTIONS": 1, **extra_parameters}

    events = _warnings(GnssConsistencyChecks(log, parameters).analyse(), "XKF4.TS")

    assert bool(events) == expect_warning


def test_ekf3_position_source_two_selects_gps_when_source_set_is_two() -> None:
    """
    Source set 2 selects its position source for GPS.

    GIVEN a position timeout with source set 2 and EK3_SRC3_POSXY selecting GPS
    WHEN the GNSS consistency analysis runs
    THEN the timeout is attributed to GPS position navigation
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[1] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[2] * 3)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC3_POSXY": 3}).analyse(), "XKF4.TS")

    assert len(events) == 1
    assert _evidence(events[0])["gps_timeout_mask"] == 1


def test_event_message_names_the_ekf_lane_that_timed_out() -> None:
    """
    The warning message names the EKF lane that timed out.

    GIVEN a GPS position timeout on EKF lane 0
    WHEN the GNSS consistency analysis runs
    THEN the warning message identifies sensor 0
    """
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2], C=[0] * 3, PI=[0] * 3, TS=[1] * 3)
    _add(log, "XKFS", TimeUS=[0, 1, 2], C=[0] * 3, SS=[0] * 3)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.TS")

    assert len(events) == 1
    assert events[0].message.startswith("XKF4.TS, sensor 0: ")


def test_east_position_reset_reports_lane_reset_message() -> None:
    """GIVEN a 2 cm east offset reset on the primary lane WHEN analyzed THEN the lane reset warning names OFE."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, OFE=[0, 0, 0.02, 0.02])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFE")
    assert len(events) == 1
    assert _message_text(events[0]) == "EKF lane position reset changed"
    assert (events[0].timestamp_us, events[0].end_timestamp_us) == (2e6, 2e6)
    assert _evidence(events[0])["OFE"] == pytest.approx(0.02)


def test_fault_mask_at_maximum_uint16_value_is_reported() -> None:
    """GIVEN a primary-lane fault mask equal to 65535 WHEN analyzed THEN it is a valid mask and reports a fault."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0, 1, 2, 3], C=[0] * 4, PI=[0] * 4, FS=[0, 65535, 65535, 0])
    _add(log, "XKFS", TimeUS=[0, 1, 2, 3], C=[0] * 4, SS=[0] * 4, GI=[0] * 4)
    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.FS")
    assert len(events) == 1
    assert _message_text(events[0]) == "EKF lane reports a fault or GPS quality check failure"
    assert events[0].timestamp_us == 1e6
    assert _evidence(events[0])["FS"] == 65535


def test_short_event_is_skipped_without_hiding_a_later_long_event() -> None:
    """GIVEN a 1 s warning run followed by a 2 s run WHEN the minimum duration is 1.5 s THEN only the long run is reported."""
    series = _series([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    levels = np.array([1.0, 1.0, np.nan, 1.0, 1.0, 1.0])

    checks = GnssConsistencyChecks(LogData(), {})
    outcomes = checks._events(series, levels, "XKF4.FS", "msg", minimum_duration_s=1.5)  # pylint: disable=protected-access

    assert [(item.timestamp_us, item.end_timestamp_us) for item in outcomes] == [(3e6, 5e6)]


def test_bitmask_evidence_is_limited_to_samples_inside_the_event() -> None:
    """GIVEN a fault bit recorded after a warning run ends WHEN summarized THEN the bit is not attributed to the event."""
    series = _series([0.0, 1.0, 2.0, 3.0], FS=[1.0, 1.0, 8.0, 8.0])
    levels = np.array([1.0, 1.0, np.nan, np.nan])
    checks = GnssConsistencyChecks(LogData(), {})

    outcomes = checks._events(  # pylint: disable=protected-access
        series, levels, "XKF4.FS", "msg", {"FS": series.fields["FS"]}, bitmask_fields=("FS",)
    )

    assert len(outcomes) == 1
    assert _evidence(outcomes[0])["FS"] == 1.0


def test_measurement_without_finite_values_inside_the_event_is_not_reported() -> None:
    """GIVEN a measurement that is only finite after a warning run ends WHEN the event is summarized THEN it is omitted."""
    series = _series([0.0, 1.0, 2.0, 3.0], X=[np.nan, np.nan, 5.0, 5.0])
    levels = np.array([1.0, 1.0, np.nan, np.nan])

    checks = GnssConsistencyChecks(LogData(), {})
    outcomes = checks._events(series, levels, "XKF4.X", "msg", {"X": series.fields["X"]})  # pylint: disable=protected-access

    assert len(outcomes) == 1
    assert "X" not in _evidence(outcomes[0])


def test_stale_receiver_selection_starts_a_new_gps_timeout_event() -> None:
    """GIVEN a fresh source selection but a receiver selection 2.5 s old WHEN analyzed THEN the timeout is split there."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[0.0, 1.0, 2.0, 2.5], C=[0] * 4, PI=[0] * 4, TS=[3] * 4)
    _add(log, "XKFS", TimeUS=[0.0, 2.5], C=[0, 0], SS=[0, 0], GI=[1, np.nan])

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.TS")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(0.0, 2e6), (2.5e6, 2.5e6)]


def test_gps_position_gate_event_reports_norm_of_matching_position_innovation() -> None:
    """
    GPS position gate event reports the norm of matching position innovations.

    GIVEN a GPS position gate exceedance with matching XKF3 position innovations
    WHEN analyzed
    THEN the event reports their norm.
    """
    log = LogData()
    times = [0.0, 0.5, 1.0, 1.5, 2.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 5, PI=[0] * 5, SV=[0] * 5, SP=[2] * 5)
    _add(log, "XKFS", TimeUS=times, C=[0] * 5, SS=[0] * 5, GI=[0] * 5)
    _add(log, "XKF3", TimeUS=times, C=[0] * 5, IPN=[3.0] * 5, IPE=[4.0] * 5)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.SP")

    assert len(events) == 1
    assert _evidence(events[0]) == {"test_ratio": 2.0, "active_primary": 1.0, "gps_receiver": 0.0, "innovation_norm": 5.0}


def test_stale_position_innovation_is_not_attributed_to_a_later_gate_exceedance() -> None:
    """
    Stale position innovations are not attributed to a later gate exceedance.

    GIVEN a position innovation recorded 1 s before a GPS gate exceedance
    WHEN analyzed
    THEN the event has no innovation norm.
    """
    log = LogData()
    times = [1.0, 1.5, 2.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 3, PI=[0] * 3, SV=[0] * 3, SP=[2] * 3)
    _add(log, "XKFS", TimeUS=times, C=[0] * 3, SS=[0] * 3, GI=[0] * 3)
    _add(log, "XKF3", TimeUS=[0.0], C=[0], IPN=[3.0], IPE=[4.0])

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.SP")

    assert len(events) == 1
    assert _evidence(events[0]) == {"test_ratio": 2.0, "active_primary": 1.0, "gps_receiver": 0.0}


def test_ekf_lane_with_primary_index_above_byte_range_is_not_evaluated() -> None:
    """
    EKF lane with primary index above the byte range is not evaluated.

    GIVEN a GPS position gate exceedance whose primary-lane index is 256
    WHEN analyzed
    THEN no event or evaluated sample is reported.
    """
    log = LogData()
    times = [0.0, 0.5, 1.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 3, PI=[256] * 3, SV=[0] * 3, SP=[2] * 3)
    _add(log, "XKFS", TimeUS=times, C=[0] * 3, SS=[0] * 3, GI=[0] * 3)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()

    assert not _warnings(outcomes, "XKF4.SP")
    assert _evidence(next(item for item in outcomes if item.source == "XKF4.SV/SP"))["evaluated"] == 0


def test_ekf_lane_with_primary_index_at_byte_maximum_is_evaluated() -> None:
    """
    EKF lane with primary index at the byte maximum is evaluated.

    GIVEN a GPS position gate exceedance with primary-lane index 255
    WHEN analyzed
    THEN the event is reported for an inactive lane.
    """
    log = LogData()
    times = [0.0, 0.5, 1.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 3, PI=[255] * 3, SV=[0] * 3, SP=[2] * 3)
    _add(log, "XKFS", TimeUS=times, C=[0] * 3, SS=[0] * 3, GI=[0] * 3)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.SP")

    assert len(events) == 1
    assert _evidence(events[0]) == {"test_ratio": 2.0, "active_primary": 0.0, "gps_receiver": 0.0}


def test_gps_receiver_change_through_unknown_receiver_splits_position_gate_events() -> None:
    """GIVEN a lane whose GPS receiver goes from 0 to unknown to 1 WHEN analyzed THEN three separate events are reported."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 7, PI=[0] * 7, SV=[0] * 7, SP=[2] * 7)
    _add(log, "XKFS", TimeUS=times, C=[0] * 7, SS=[0] * 7, GI=[0, np.nan, np.nan, np.nan, np.nan, 1, 1])

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.SP")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(0.0, 2e6), (3e6, 4e6), (5e6, 6e6)]
    assert [_evidence(item).get("gps_receiver") for item in events] == [0.0, None, 1.0]


def test_sub_half_second_position_gate_blip_is_not_reported() -> None:
    """GIVEN a GPS position gate exceedance lasting 0.2 s WHEN analyzed THEN it is not reported as an event."""
    log = LogData()
    times = [0.0, 0.2]
    _add(log, "XKF4", TimeUS=times, C=[0] * 2, PI=[0] * 2, SV=[0] * 2, SP=[2] * 2)
    _add(log, "XKFS", TimeUS=times, C=[0] * 2, SS=[0] * 2, GI=[0] * 2)

    assert not _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.SP")


def test_one_second_position_gate_exceedance_is_reported() -> None:
    """GIVEN a GPS position gate exceedance lasting 1 s WHEN analyzed THEN it is reported as one event."""
    log = LogData()
    times = [0.0, 0.5, 1.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 3, PI=[0] * 3, SV=[0] * 3, SP=[2] * 3)
    _add(log, "XKFS", TimeUS=times, C=[0] * 3, SS=[0] * 3, GI=[0] * 3)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.SP")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(0.0, 1e6)]


def test_position_reset_of_exactly_one_centimetre_is_not_reported() -> None:
    """GIVEN an EKF3 lane position reset of exactly 0.01 m WHEN analyzed THEN it is not reported as a reset."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 5, PI=[0] * 5, SV=[0] * 5, SP=[0] * 5, OFN=[0, 0, 0.01, 0.01, 0.01])
    _add(log, "XKFS", TimeUS=times, C=[0] * 5, SS=[0] * 5, GI=[0] * 5)

    assert not _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")


def test_position_reset_visible_only_across_a_2_5_second_gap_is_not_reported() -> None:
    """GIVEN a position offset that changes only across a 2.5 s logging gap WHEN analyzed THEN no reset is reported."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 4.5, 5.5]
    _add(log, "XKF4", TimeUS=times, C=[0] * 5, PI=[0] * 5, SV=[0] * 5, SP=[0] * 5, OFN=[0, 0, 0, 5, 5])
    _add(log, "XKFS", TimeUS=times, C=[0] * 5, SS=[0] * 5, GI=[0] * 5)

    assert not _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.OFN")


def test_unknown_primary_core_sample_splits_position_reset_coverage_without_bridging() -> None:
    """GIVEN one EKF3 sample whose primary core index is unknown WHEN analyzed THEN it is not evaluated or bridged over."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 5, PI=[0, 0, np.nan, 0, 0], SV=[0] * 5, SP=[0] * 5, OFN=[0] * 5)
    _add(log, "XKFS", TimeUS=times, C=[0] * 5, SS=[0] * 5, GI=[0] * 5)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()
    coverage = _evidence(next(item for item in outcomes if item.source == "XKF4.OFN.coverage"))

    assert coverage["total"] == 5.0
    assert coverage["evaluated"] == 2.0


def test_steady_position_reset_coverage_evaluates_every_sample_after_the_first() -> None:
    """GIVEN a steady EKF3 lane position with no resets WHEN analyzed THEN each sample with a predecessor is evaluated."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 5, PI=[0] * 5, SV=[0] * 5, SP=[0] * 5, OFN=[0] * 5)
    _add(log, "XKFS", TimeUS=times, C=[0] * 5, SS=[0] * 5, GI=[0] * 5)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()
    coverage = _evidence(next(item for item in outcomes if item.source == "XKF4.OFN.coverage"))

    assert coverage["evaluated"] == 4.0
    assert coverage["total"] == 5.0


def test_non_primary_gps_timeout_is_reported_as_a_warning() -> None:
    """GIVEN a GPS timeout reported by a non-primary EKF3 core WHEN analyzed THEN the timeout is reported."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 4, PI=[1] * 4, SV=[0] * 4, SP=[0] * 4, TS=[0, 1, 1, 0])
    _add(log, "XKFS", TimeUS=times, C=[0] * 4, SS=[0] * 4, GI=[0] * 4)

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.TS")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(1e6, 2e6)]


def test_non_primary_gps_timeout_coverage_counts_samples_without_timeout() -> None:
    """GIVEN non-primary EKF3 samples with and without GPS timeouts WHEN analyzed THEN all samples are evaluated."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 4, PI=[1] * 4, SV=[0] * 4, SP=[0] * 4, TS=[0, 1, 1, 0])
    _add(log, "XKFS", TimeUS=times, C=[0] * 4, SS=[0] * 4, GI=[0] * 4)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()
    coverage = _evidence(next(item for item in outcomes if item.source == "XKF4.TS.coverage"))

    assert coverage["evaluated"] == 4.0
    assert coverage["total"] == 4.0


def test_coverage_totals_samples_from_every_ekf_core_not_only_the_last() -> None:
    """GIVEN two EKF3 cores with different sample counts WHEN analyzed THEN coverage totals the samples of every core."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0]
    _add(log, "XKF4", TimeUS=times, C=[0, 0, 0, 1], PI=[0, 0, 0, 1], SV=[0] * 4, SP=[0] * 4, OFN=[0] * 4)
    _add(log, "XKFS", TimeUS=times, C=[0, 0, 0, 1], SS=[0] * 4, GI=[0] * 4)

    outcomes = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse()
    coverage = _evidence(next(item for item in outcomes if item.source == "XKF4.OFN.coverage"))

    assert coverage["total"] == 4.0
    assert coverage["evaluated"] == 2.0


def test_unknown_gps_receiver_is_reported_separately_from_receiver_zero() -> None:
    """GIVEN a GPS timeout whose receiver is unknown, then 0 WHEN analyzed THEN two separate events are reported."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 4, PI=[0] * 4, SV=[0] * 4, SP=[0] * 4, TS=[1] * 4)
    _add(log, "XKFS", TimeUS=times, C=[0] * 4, SS=[0] * 4, GI=[np.nan, np.nan, 0, 0])

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.TS")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(0.0, 1e6), (2e6, 3e6)]
    assert [_evidence(item).get("gps_receiver") for item in events] == [None, 0.0]


def test_non_primary_gps_fault_is_split_by_gps_receiver() -> None:
    """GIVEN a non-primary EKF3 GPS fault while the GPS receiver changes WHEN analyzed THEN one event per receiver."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 4, PI=[1] * 4, SV=[0] * 4, SP=[0] * 4, GPS=[1] * 4)
    _add(log, "XKFS", TimeUS=times, C=[0] * 4, SS=[0] * 4, GI=[0, 0, 1, 1])

    events = _warnings(GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3}).analyse(), "XKF4.GPS")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(0.0, 1e6), (2e6, 3e6)]
    assert [_evidence(item).get("gps_receiver") for item in events] == [0.0, 1.0]


def test_unknown_source_set_before_first_report_is_a_separate_event() -> None:
    """GIVEN a GPS timeout whose source set is unknown, then 1 WHEN analyzed THEN the unknown set is its own event."""
    log = LogData()
    times = [0.0, 1.0, 2.0, 3.0]
    _add(log, "XKF4", TimeUS=times, C=[0] * 4, PI=[0] * 4, SV=[0] * 4, SP=[0] * 4, TS=[2] * 4)
    _add(log, "XKFS", TimeUS=times, C=[0] * 4, SS=[np.nan, 1, 1, 1], GI=[0] * 4)
    options = {"EK3_SRC1_POSXY": 3, "EK3_SRC1_VELXY": 3, "EK3_SRC_OPTIONS": 1}

    events = _warnings(GnssConsistencyChecks(log, options).analyse(), "XKF4.TS")

    assert [(item.timestamp_us, item.end_timestamp_us) for item in events] == [(0.0, 0.0), (1e6, 3e6)]


def test_stale_receiver_accuracy_does_not_widen_position_velocity_tolerance() -> None:
    """GIVEN a single receiver accuracy report at 0 s and a 60 m/s speed mismatch WHEN analyzed THEN 1.0 s is still checked."""
    times = np.arange(0, 5.0, 0.5)
    log = _gps_log(times, Lat=48 + 10.0 * times * _DEG_PER_M, Spd=np.full(len(times), 60.0))
    _add_gps_auxiliary(log, [0.0], HAcc=[100.0])
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")
    assert any(item.timestamp_us == pytest.approx(1e6) for item in events)


def _position_velocity_evaluated(log: LogData) -> tuple[float, float]:
    """Return the evaluated and total counts reported for GPS.PositionVelocity coverage."""
    outcomes = GnssConsistencyChecks(log, {}).analyse()
    coverage = next(item for item in outcomes if item.source == "GPS.PositionVelocity" and item.severity == "informational")
    evidence = _evidence(coverage)
    return evidence["evaluated"], evidence["total"]


@pytest.mark.parametrize(
    ("field", "value", "expected_evaluated"),
    [
        ("Status", 0.0, 0.0),
        ("Lat", 90.0, 9.0),
        ("Lat", 90.5, 0.0),
        ("Lat", 95.0, 0.0),
        ("Lng", 180.0, 9.0),
        ("Lng", 180.5, 0.0),
    ],
)
def test_gps_fix_and_coordinate_range_gate_position_velocity_evaluation(
    field: str, value: float, expected_evaluated: float
) -> None:
    """
    Only samples with a valid 3D fix and in-range coordinates take part in position-velocity checks.

    GIVEN: A stationary receiver whose every sample has one boundary or out-of-gate field value
    WHEN: GPS position and velocity are checked
    THEN: Boundary coordinates are evaluated, while invalid fixes and out-of-range coordinates are excluded
    """
    times = np.arange(0, 5.0, 0.5)
    log = _gps_log(times, **{field: np.full(len(times), value)})
    _add_gps_auxiliary(log, times)
    assert _position_velocity_evaluated(log) == (expected_evaluated, 9.0)


def test_position_velocity_evaluates_a_two_sample_continuous_section() -> None:
    """
    A two-sample track segment is the shortest one that still has a displacement interval.

    GIVEN: Two consecutive GPS samples whose reported speed contradicts their displacement
    WHEN: GPS position and velocity are checked
    THEN: The single interval is evaluated and reported
    """
    times = np.array([0.0, 0.5])
    log = _gps_log(times, Spd=np.full(len(times), 60.0))
    _add_gps_auxiliary(log, times)
    assert _position_velocity_evaluated(log) == (1.0, 1.0)
    assert _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")


def test_position_velocity_splits_sections_at_gaps_longer_than_two_seconds() -> None:
    """
    A gap longer than two seconds ends a continuous track section.

    GIVEN: A stationary receiver with a 2.5 s gap in its GPS samples
    WHEN: GPS position and velocity are checked
    THEN: The interval across the gap is not evaluated
    """
    times = np.array([0.0, 0.5, 1.0, 3.5, 4.0])
    log = _gps_log(times)
    _add_gps_auxiliary(log, times)
    assert _position_velocity_evaluated(log) == (3.0, 4.0)


def test_position_velocity_skips_single_sample_sections_without_ending_the_evaluation() -> None:
    """
    An isolated sample is skipped without stopping the evaluation of later sections.

    GIVEN: An isolated GPS sample followed by a later continuous track segment
    WHEN: GPS position and velocity are checked
    THEN: The isolated sample is skipped and the later segment is still evaluated
    """
    times = np.array([0.0, 3.5, 4.0, 4.5])
    log = _gps_log(times)
    _add_gps_auxiliary(log, times)
    assert _position_velocity_evaluated(log) == (2.0, 3.0)


def test_position_velocity_coverage_counts_every_gps_receiver() -> None:
    """
    Coverage includes the intervals of every GPS receiver instance.

    GIVEN: Two stationary receivers with four samples each
    WHEN: Coverage is reported
    THEN: The intervals of both receivers are counted
    """
    times = np.arange(0, 2.0, 0.5)
    ones = np.ones(2 * len(times))
    log = LogData()
    _add(
        log,
        "GPS",
        TimeUS=np.tile(times, 2),
        I=np.repeat([0.0, 1.0], len(times)),
        Status=ones * 3,
        Lat=ones * 48,
        Lng=ones * 11,
        Spd=np.zeros(2 * len(times)),
        GCrs=np.zeros(2 * len(times)),
    )
    assert _position_velocity_evaluated(log) == (6.0, 6.0)


def test_position_velocity_coverage_of_one_gps_sample_has_no_intervals() -> None:
    """
    A single GPS sample yields no position-velocity intervals.

    GIVEN: A log with a single GPS sample
    WHEN: Coverage is reported
    THEN: Zero intervals are reported as evaluated and as available
    """
    times = np.array([0.0])
    log = _gps_log(times)
    _add_gps_auxiliary(log, times)
    assert _position_velocity_evaluated(log) == (0.0, 0.0)


def test_position_velocity_tolerance_is_three_times_the_summed_horizontal_accuracy() -> None:
    """
    The position-velocity tolerance scales with the summed horizontal accuracy of each interval.

    GIVEN: 35 m of unreported northward motion per 0.5 s between two samples with 5 m horizontal accuracy
    WHEN: GPS position and velocity are checked
    THEN: The tolerance is 3 x (5 m + 5 m) = 30 m and the 35 m residual is reported
    """
    times = np.arange(0, 5.0, 0.5)
    log = _gps_log(times, Lat=48 + 70.0 * times * _DEG_PER_M)
    _add_gps_auxiliary(log, times, HAcc=np.full(len(times), 5.0))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")
    assert events
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(30.0)
    assert _evidence(events[0])["residual_m"] == pytest.approx(35.0, rel=1e-6)


def test_position_velocity_ignores_non_finite_accuracy_when_setting_tolerance() -> None:
    """
    A non-finite horizontal accuracy does not widen the position-velocity tolerance.

    GIVEN: 35 m of unreported northward motion per 0.5 s with infinite horizontal accuracy
    WHEN: GPS position and velocity are checked
    THEN: The default 10 m tolerance applies and the disagreement is reported
    """
    times = np.arange(0, 5.0, 0.5)
    log = _gps_log(times, Lat=48 + 70.0 * times * _DEG_PER_M)
    _add_gps_auxiliary(log, times, HAcc=np.full(len(times), np.inf))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")
    assert events
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(10.0)


def test_position_velocity_tolerance_uses_the_accuracy_of_both_samples_of_each_interval() -> None:
    """
    Each interval's tolerance uses only the accuracies of its own two samples.

    GIVEN: A 20 m position jump between two samples with 1 m accuracy, after a sample with 10 m accuracy
    WHEN: GPS position and velocity are checked
    THEN: The jump is judged with the 10 m tolerance from its own two samples and is reported
    """
    times = np.arange(0, 5.0, 0.5)
    lat = np.full(len(times), 48.0)
    lat[2:] += 20.0 * _DEG_PER_M
    log = _gps_log(times, Lat=lat)
    _add_gps_auxiliary(log, times, HAcc=np.array([10.0] + [1.0] * (len(times) - 1)))
    events = _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")
    assert events
    assert _evidence(events[0])["residual_m"] == pytest.approx(20.0, rel=1e-6)
    assert _evidence(events[0])["tolerance_m"] == pytest.approx(10.0)


def test_position_velocity_uses_each_intervals_velocity_when_speed_changes() -> None:
    """
    Each interval is compared with the velocity measured for that interval.

    GIVEN: A northward GPS speed ramp of 0, 10, 20, 30 and 40 m/s sampled every second, with position following the ramp
    WHEN: GPS position and velocity are checked
    THEN: Each interval is compared with its own velocity and nothing is reported
    """
    times = np.arange(0, 5.0)
    speed = np.array([0.0, 10.0, 20.0, 30.0, 40.0])
    north = np.concatenate(([0.0], np.cumsum((speed[1:] + speed[:-1]) / 2)))
    log = _gps_log(times, Lat=48 + north * _DEG_PER_M, Spd=speed)
    _add_gps_auxiliary(log, times)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")


def test_position_velocity_residual_equal_to_tolerance_is_not_reported() -> None:
    """
    A residual exactly equal to the tolerance is not a disagreement.

    GIVEN: A stationary receiver reporting 20 m/s northward, whose expected 10 m per 0.5 s equals the 10 m tolerance
    WHEN: GPS position and velocity are checked
    THEN: A residual exactly at the tolerance is not reported
    """
    times = np.arange(0, 5.0, 0.5)
    log = _gps_log(times, Spd=np.full(len(times), 20.0))
    _add_gps_auxiliary(log, times)
    assert not _warnings(GnssConsistencyChecks(log, {}).analyse(), "GPS.PositionVelocity")
