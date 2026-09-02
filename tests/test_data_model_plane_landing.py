#!/usr/bin/env python3

"""Focused tests for AMC-native ArduPlane landing-attempt analysis."""

from collections.abc import Sequence

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis import data_model_log_analysis
from ardupilot_methodic_configurator.log_analysis.data_model_availability_plane_landing import (
    PlaneLandingAnalysis,
    PlaneLandingAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_flight_segment import FlightSegment
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterChange, ParameterHistory
from ardupilot_methodic_configurator.log_analysis.data_model_plane_flight_segment import PlaneFlightSegmentDetector
from ardupilot_methodic_configurator.log_analysis.data_model_plane_landing import (
    PlaneLandingAttempt,
    PlaneLandingAttemptDetector,
    PlaneLandingEndReason,
)


def _add_columns(
    log_data: LogData,
    message_name: str,
    records: Sequence[tuple[object, ...]],
    dtype: list[tuple[str, str]],
    *,
    microsecond_time: bool = False,
) -> None:
    columns = np.array(list(records), dtype=dtype)
    schema = None
    if microsecond_time:
        fields = [name for name, _field_type in dtype]
        schema = MessageSchema(
            name=message_name,
            msg_type=1,
            length=0,
            format="",
            fields=fields,
            stored_units=["µs" if name == "TimeUS" else "" for name in fields],
            scaled_units=["s" if name == "TimeUS" else "" for name in fields],
            multipliers=[1e-6 if name == "TimeUS" else 1.0 for name in fields],
            multipliers_applied_at_ingest=[False] * len(fields),
            records=len(records),
        )
    log_data.add_message_columns(message_name, columns, schema)


def _plane_log(  # pylint: disable=too-many-arguments
    *,
    vehicle_type: str = "ArduPlane",
    firmware_version: tuple[int, int, int] = (4, 7, 1),
    gps: Sequence[tuple[float, float]] | None = None,
    land: Sequence[tuple[float, int]] | None = None,
    mode: Sequence[tuple[float, int]] | None = None,
    messages: Sequence[tuple[float, str]] | None = None,
    include_land: bool = True,
) -> LogData:
    log_data = LogData(vehicle_type=vehicle_type, firmware_version=firmware_version)
    gps_records = (
        gps if gps is not None else ((0.0, 6.0), (2.0, 6.0), (15.0, 6.0), (30.0, 6.0), (60.0, 6.0), (61.0, 0.0), (91.0, 0.0))
    )
    _add_columns(
        log_data,
        "GPS",
        gps_records,
        [("TimeUS", "f8"), ("Spd", "f8")],
    )
    if include_land:
        _add_columns(
            log_data,
            "LAND",
            land if land is not None else ((5.0, 0), (10.0, 1), (11.0, 2)),
            [("TimeUS", "f8"), ("stage", "i4")],
        )
    _add_columns(
        log_data,
        "MODE",
        mode if mode is not None else ((0.0, 10),),
        [("TimeUS", "f8"), ("ModeNum", "i4")],
    )
    if messages is not None:
        _add_columns(log_data, "MSG", messages, [("TimeUS", "f8"), ("Message", "U64")])
    return log_data


def _context(parameter_history: ParameterHistory | None = None) -> LogAnalysisContext:
    history = parameter_history or ParameterHistory()
    return LogAnalysisContext(
        parameters=history.latest_values,
        configuration_steps={},
        parameter_history=history,
    )


def _availability(log_data: LogData) -> LogAvailabilityResult:
    return PlaneLandingAvailabilityModel(log_data, _context()).check()


def test_non_arduplane_log_is_unavailable() -> None:
    result = _availability(_plane_log(vehicle_type="ArduCopter"))

    assert result.available is False
    assert result.reason == "Plane landing analysis is available only for ArduPlane logs"


@pytest.mark.parametrize("firmware_version", [(4, 6, 3), (4, 8, 0)])
def test_only_arduplane_47_x_is_available(firmware_version: tuple[int, int, int]) -> None:
    result = _availability(_plane_log(firmware_version=firmware_version))

    assert result.available is False
    assert result.reason == "Plane landing analysis currently supports ArduPlane 4.7.x only"


def test_arduplane_47_x_with_required_evidence_is_available() -> None:
    result = _availability(_plane_log())

    assert result.available is True
    assert not result.issues


def test_missing_required_landing_evidence_is_unavailable() -> None:
    log_data = _plane_log(include_land=False)

    result = _availability(log_data)

    assert result.available is False
    assert [issue.message for issue in result.issues] == ["No LAND messages found"]


def test_optional_sensor_and_message_evidence_is_not_required() -> None:
    log_data = _plane_log(messages=None)

    result = _availability(log_data)

    assert result.available is True
    for optional_message in ("ARSP", "BARO", "RFND", "CMD", "MSG"):
        assert log_data.get_message_columns(optional_message) is None


def test_one_normal_attempt_uses_independent_disarm_termination() -> None:
    log_data = _plane_log(messages=((40.0, "Throttle disarmed"),))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert attempts == (
        PlaneLandingAttempt(
            flight_segment=segment,
            start_s=10.0,
            end_s=40.0,
            end_reason=PlaneLandingEndReason.DISARM,
        ),
    )


def test_stage_one_transition_is_ignored_when_current_mode_is_not_auto() -> None:
    log_data = _plane_log(mode=((0.0, 5),))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert not attempts


def test_first_transition_away_from_auto_terminates_attempt() -> None:
    log_data = _plane_log(mode=((0.0, 10), (25.0, 5)))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in attempts] == [
        (10.0, 25.0, PlaneLandingEndReason.MODE_EXIT)
    ]


def test_multiple_abort_and_restart_attempts_remain_distinguishable() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (11.0, 2), (30.0, 1)),
        messages=((20.0, "Landing aborted by pilot"), (50.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in attempts] == [
        (10.0, 20.0, PlaneLandingEndReason.ABORT),
        (30.0, 50.0, PlaneLandingEndReason.DISARM),
    ]
    assert all(attempt.flight_segment is segment for attempt in attempts)
    assert all(segment.contains(attempt.start_s, attempt.end_s) for attempt in attempts)


def test_go_around_does_not_split_parent_flight_segment() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (15.0, 2.0), (17.0, 2.0), (20.0, 6.0), (60.0, 6.0), (61.0, 0.0), (91.0, 0.0)),
        land=((5.0, 0), (10.0, 1), (11.0, 2), (30.0, 1)),
        messages=((50.0, "Throttle disarmed"),),
    )

    segmentation = PlaneFlightSegmentDetector.detect(log_data, {})
    attempts = PlaneLandingAttemptDetector.detect(log_data, segmentation.segments[0])

    assert len(segmentation.segments) == 1
    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in attempts] == [
        (10.0, 15.0, PlaneLandingEndReason.GPS_STOP),
        (30.0, 50.0, PlaneLandingEndReason.DISARM),
    ]
    assert attempts[0].end_reason is PlaneLandingEndReason.GPS_STOP


def test_attempt_times_use_scaled_seconds() -> None:
    log_data = LogData(vehicle_type="ArduPlane", firmware_version=(4, 7, 0))
    _add_columns(
        log_data,
        "GPS",
        ((0, 6.0), (2_000_000, 6.0), (20_000_000, 6.0)),
        [("TimeUS", "u8"), ("Spd", "f8")],
        microsecond_time=True,
    )
    _add_columns(
        log_data,
        "LAND",
        ((5_000_000, 0), (10_000_000, 1)),
        [("TimeUS", "u8"), ("stage", "i4")],
        microsecond_time=True,
    )
    _add_columns(
        log_data,
        "MODE",
        ((0, 10),),
        [("TimeUS", "u8"), ("ModeNum", "i4")],
        microsecond_time=True,
    )
    segment = FlightSegment(start_s=0.0, end_s=20.0, is_complete=False)

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert attempts[0].start_s == 10.0
    assert attempts[0].end_s == 20.0
    assert attempts[0].duration_s == 10.0


def test_analysis_resolves_landing_parameter_at_each_attempt_time() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (11.0, 2), (30.0, 1)),
        messages=((20.0, "Landing aborted"), (50.0, "Throttle disarmed")),
    )
    history = ParameterHistory(
        {"LAND_FLARE_ALT": 2.0},
        {"LAND_FLARE_ALT": (ParameterChange(time_s=25.0, value=4.0),)},
    )

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    assert result.available is True
    assert result.reason == "Detected 2 AUTO landing attempt(s)"
    assert [outcome.timestamp_us for outcome in result.outcomes] == [10_000_000, 30_000_000]
    assert [outcome.value for outcome in result.outcomes] == [2.0, 4.0]
    assert all(outcome.param_name is None for outcome in result.outcomes)
    assert all(outcome.suggested_value is None for outcome in result.outcomes)
    assert "landing abort message" in result.outcomes[0].message
    assert "throttle disarm message" in result.outcomes[1].message


def test_plane_landing_models_are_registered_as_one_subsystem_pair() -> None:
    spec = next(spec for spec in data_model_log_analysis.LOG_ANALYSIS_SUBSYSTEMS if spec.key == "plane_landing")

    assert spec.availability_model is PlaneLandingAvailabilityModel
    assert spec.analysis_model is PlaneLandingAnalysis
