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
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_consistency import GnssConsistencyChecks
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_interference import GPSLogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_samples import event_intervals
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
    schema_path = Path(__file__).parents[1] / "ardupilot_methodic_configurator/log_analysis/log_analysis_report_schema.json"
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
    assert _evidence(next(item for item in outcomes if item.source == "XKF4.GPS"))["evaluated"] == 0


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
    coverage = next(item for item in outcomes if item.source == "XKF4.GPS")
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


def test_ekf_timeout_splits_on_receiver_and_source_set_changes() -> None:
    """GIVEN a persistent GPS timeout WHEN source selection changes THEN each interval retains its receiver."""
    log = LogData()
    _add(log, "XKF4", TimeUS=list(range(6)), C=[0] * 6, PI=[0] * 6, TS=[1] * 6)
    _add(log, "XKFS", TimeUS=list(range(6)), C=[0] * 6, SS=[0, 0, 0, 0, 1, 1], GI=[0, 0, 1, 1, 1, 1])
    checks = GnssConsistencyChecks(log, {"EK3_SRC1_POSXY": 3, "EK3_SRC2_POSXY": 3})

    events = _warnings(checks.analyse(), "XKF4.TS")

    assert [(event.timestamp_us, event.end_timestamp_us) for event in events] == [(0, 1e6), (2e6, 3e6), (4e6, 5e6)]
    assert [_evidence(event)["gps_receiver"] for event in events] == [0, 1, 1]


def test_ekf_gps_source_selection_must_belong_to_the_same_lane_and_be_current() -> None:
    """GIVEN a stale or different-lane source selection WHEN EKF is assessed THEN it cannot establish GPS evidence."""
    log = LogData()
    _add(log, "XKF4", TimeUS=[10, 11], C=[0, 0], PI=[0, 0], FS=[1, 1])
    _add(log, "XKFS", TimeUS=[1, 10, 11], C=[0, 1, 1], SS=[0, 0, 0], GI=[0, 1, 1])
    context = _context()
    context.parameters["EK3_SRC1_POSXY"] = 3

    assert not GPSLogAvailabilityModel(log, context).check().available
    assert not _warnings(GPSLogAnalysis(log, context).analyse().outcomes, "XKF4.FS")
