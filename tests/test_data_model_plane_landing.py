#!/usr/bin/env python3

"""
Focused tests for AMC-native ArduPlane landing-attempt analysis.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=too-many-lines

from collections.abc import Sequence

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis import data_model_log_analysis, data_model_plane_landing
from ardupilot_methodic_configurator.log_analysis.data_model_availability_plane_landing import (
    PlaneLandingAnalysis,
    PlaneLandingAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_flight_segment import FlightSegment
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterChange, ParameterHistory
from ardupilot_methodic_configurator.log_analysis.data_model_plane_flight_segment import PlaneFlightSegmentDetector
from ardupilot_methodic_configurator.log_analysis.data_model_plane_landing import (
    PlaneLandingAttempt,
    PlaneLandingAttemptDetector,
    PlaneLandingEndReason,
    PlaneLandingEvidenceExtractor,
    PlaneLandingFirmwareFlareEvidence,
    PlaneLandingFirmwareGlideSlopeEvidence,
    PlaneLandingFirmwareMessageExtractor,
    PlaneLandingMissionTarget,
    PlaneLandingMissionTargetExtractor,
    PlaneLandingRangefinderEvidence,
    PlaneLandingRangefinderEvidenceExtractor,
    PlaneLandingStage,
    PlaneLandingStageEvidence,
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
    land: Sequence[tuple[object, ...]] | None = None,
    mode: Sequence[tuple[float, int]] | None = None,
    messages: Sequence[tuple[float, str]] | None = None,
    include_land: bool = True,
    include_baro: bool = True,
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
        land_records = land if land is not None else ((5.0, 0), (10.0, 1), (11.0, 2))
        land_dtype = [("TimeUS", "f8"), ("stage", "i4")]
        if land_records and len(land_records[0]) == 3:
            land_dtype.append(("fh", "f8"))
        _add_columns(
            log_data,
            "LAND",
            land_records,
            land_dtype,
        )
    _add_columns(
        log_data,
        "MODE",
        mode if mode is not None else ((0.0, 10),),
        [("TimeUS", "f8"), ("ModeNum", "i4")],
    )
    if include_baro:
        _add_columns(
            log_data,
            "BARO",
            ((15.0, 100.0), (20.0, 99.0), (35.0, 98.0), (38.0, 97.0)),
            [("TimeUS", "f8"), ("Alt", "f8")],
        )
    if messages is not None:
        _add_columns(log_data, "MSG", messages, [("TimeUS", "f8"), ("Message", "U64")])
    return log_data


def _gps_stop_log(
    cmd: Sequence[tuple[object, ...]] | None,
    *,
    messages: Sequence[tuple[float, str]] | None = None,
) -> LogData:
    """Return a synthetic GPS-ended landing with optional CMD snapshot records."""
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (15.0, 5.0), (20.0, 2.0), (22.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (12.0, 2), (14.0, 3)),
        messages=messages,
    )
    _add_columns(
        log_data,
        "GPS",
        (
            (0.0, 6.0, 0.0, 1.0),
            (2.0, 6.0, 0.0, 1.0),
            (15.0, 5.0, 0.0, 1.0),
            (20.0, 2.0, 0.0, 1.001),
            (22.0, 2.0, 0.0, 1.001),
            (30.0, 6.0, 0.0, 1.001),
        ),
        [("TimeUS", "f8"), ("Spd", "f8"), ("Lat", "f8"), ("Lng", "f8")],
    )
    if cmd is not None:
        _add_columns(
            log_data,
            "CMD",
            cmd,
            [("TimeUS", "f8"), ("CTot", "f8"), ("CNum", "f8"), ("CId", "f8"), ("Lat", "f8"), ("Lng", "f8")],
        )
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


def _rangefinder_evidence(
    records: Sequence[tuple[object, object]],
    parameter_history: ParameterHistory | None = None,
    *,
    dtype: list[tuple[str, str]] | None = None,
) -> tuple[LogData, PlaneLandingAttempt, PlaneLandingRangefinderEvidence | None]:
    """Return one synthetic attempt and its optional RFND lifecycle evidence."""
    log_data = _plane_log(messages=((40.0, "Throttle disarmed"),))
    _add_columns(log_data, "RFND", records, dtype or [("TimeUS", "f8"), ("Dist", "f8")])
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]
    evidence = PlaneLandingRangefinderEvidenceExtractor.extract(
        log_data,
        attempt,
        parameter_history or ParameterHistory(),
    )
    return log_data, attempt, evidence


def _oriented_rangefinder_evidence(
    records: Sequence[tuple[object, ...]],
    parameter_history: ParameterHistory,
    *,
    dtype: list[tuple[str, str]] | None = None,
    attempt_bounds: tuple[float, float, PlaneLandingEndReason] | None = None,
) -> tuple[tuple[PlaneLandingStageEvidence, ...], PlaneLandingRangefinderEvidence | None]:
    """Return stage and lifecycle evidence for full-schema RFND records."""
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "RFND",
        records,
        dtype or [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1"), ("Orient", "u1"), ("Stat", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]
    if attempt_bounds is not None:
        start_s, end_s, end_reason = attempt_bounds
        land_stages = {
            float(timestamp): int(stage)
            for timestamp, stage in zip(log_data.get_field("LAND", "TimeUS"), log_data.get_field("LAND", "stage"), strict=True)
        }
        attempt = PlaneLandingAttempt(
            flight_segment=segment,
            start_s=start_s,
            end_s=end_s,
            end_reason=end_reason,
            mode_number=attempt.mode_number,
            start_stage=land_stages[start_s],
        )
    return (
        PlaneLandingEvidenceExtractor.extract(log_data, attempt, parameter_history),
        PlaneLandingRangefinderEvidenceExtractor.extract(log_data, attempt, parameter_history),
    )


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


def test_missing_baro_is_unavailable() -> None:
    result = _availability(_plane_log(include_baro=False))

    assert result.available is False
    assert [issue.message for issue in result.issues] == ["No BARO messages found"]


@pytest.mark.parametrize(
    ("records", "dtype", "expected_issue"),
    [
        (((100.0,),), [("Alt", "f8")], "TimeUS field not present in this firmware's BARO schema"),
        (((0.0,),), [("TimeUS", "f8")], "Alt field not present in this firmware's BARO schema"),
    ],
)
def test_missing_required_baro_field_is_unavailable(
    records: Sequence[tuple[object, ...]],
    dtype: list[tuple[str, str]],
    expected_issue: str,
) -> None:
    log_data = _plane_log(include_baro=False)
    _add_columns(log_data, "BARO", records, dtype)

    result = _availability(log_data)

    assert result.available is False
    assert [issue.message for issue in result.issues] == [expected_issue]


def test_valid_baro_allows_plane_landing_availability() -> None:
    result = _availability(_plane_log())

    assert result.available is True
    assert not result.issues


def test_optional_sensor_and_message_evidence_is_not_required() -> None:
    log_data = _plane_log(messages=None)

    result = _availability(log_data)
    analysis = PlaneLandingAnalysis(log_data, _context()).analyse()
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert result.available is True
    assert analysis.available is True
    assert not PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
    assert not any("firmware" in outcome.message.lower() for outcome in analysis.outcomes)
    assert not any("glide slope" in outcome.message.lower() for outcome in analysis.outcomes)
    for optional_message in ("ARSP", "RFND", "CMD", "MSG"):
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
            mode_number=PlaneLandingAttemptDetector.AUTO_MODE_NUMBER,
        ),
    )


@pytest.mark.parametrize("first_active_stage", [1, 2, 3])
def test_first_observed_active_land_stage_opens_one_attempt(first_active_stage: int) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, first_active_stage), (15.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in attempts] == [
        (10.0, 40.0, PlaneLandingEndReason.DISARM)
    ]


def test_repeated_final_stage_does_not_open_duplicate_attempts() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 3), (11.0, 3), (12.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s) for attempt in attempts] == [(10.0, 40.0)]


@pytest.mark.parametrize("first_active_stage", [2, 3])
def test_flight_observation_beginning_in_active_stage_opens_left_truncated_attempt(
    first_active_stage: int,
) -> None:
    log_data = _plane_log(
        land=((5.0, 1), (10.0, first_active_stage), (15.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    segment = FlightSegment(start_s=10.0, end_s=60.0, is_complete=False)

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s) for attempt in attempts] == [(10.0, 40.0)]


def test_autoland_only_attempt_preserves_mode_and_flat_result_label() -> None:
    log_data = _plane_log(mode=((0.0, 26),), messages=((40.0, "Throttle disarmed"),))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    assert len(attempts) == 1
    assert attempts[0].mode_number == PlaneLandingAttemptDetector.AUTOLAND_MODE_NUMBER
    assert any(outcome.message.startswith("AUTOLAND landing:") for outcome in result.outcomes)


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


def test_auto_to_autoland_terminates_old_attempt_and_allows_new_stage_one_attempt() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (11.0, 2), (29.0, 0), (30.0, 1), (31.0, 2)),
        mode=((0.0, 10), (25.0, 26)),
        messages=((50.0, "Throttle disarmed"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason, attempt.mode_number) for attempt in attempts] == [
        (10.0, 25.0, PlaneLandingEndReason.MODE_EXIT, 10),
        (30.0, 50.0, PlaneLandingEndReason.DISARM, 26),
    ]


def test_autoland_to_auto_terminates_attempt() -> None:
    log_data = _plane_log(mode=((0.0, 26), (25.0, 10)))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason, attempt.mode_number) for attempt in attempts] == [
        (10.0, 25.0, PlaneLandingEndReason.MODE_EXIT, 26)
    ]


def test_mode_exit_and_reentry_does_not_reopen_stale_active_stage() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (30.0, 2), (40.0, 2)),
        mode=((0.0, 10), (20.0, 5), (35.0, 10)),
        messages=((50.0, "Throttle disarmed"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in attempts] == [
        (10.0, 20.0, PlaneLandingEndReason.MODE_EXIT)
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


def test_abort_reset_and_new_active_stage_create_separate_attempts() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 3), (22.0, 0), (30.0, 2), (35.0, 3)),
        messages=((20.0, "Landing aborted by pilot"), (50.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in attempts] == [
        (10.0, 20.0, PlaneLandingEndReason.ABORT),
        (30.0, 50.0, PlaneLandingEndReason.DISARM),
    ]


def test_stage_one_restart_closes_previous_attempt_without_explicit_termination() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (15.0, 6.0), (30.0, 6.0), (60.0, 6.0), (61.0, 6.0), (91.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (11.0, 3), (30.0, 1), (31.0, 2)),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in attempts] == [
        (10.0, 30.0, PlaneLandingEndReason.STAGE_RESTART),
        (30.0, 91.0, PlaneLandingEndReason.FLIGHT_SEGMENT_END),
    ]


def test_restart_boundary_observations_belong_only_to_new_attempt() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (20.0, 8.0), (30.0, 3.0), (50.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (29.0, 2), (29.5, 0), (30.0, 2), (35.0, 3)),
        messages=((30.0, "Landing glide slope 4.7 degrees"), (50.0, "Throttle disarmed")),
        include_baro=False,
    )
    _add_columns(log_data, "BARO", ((20.0, 100.0), (30.0, 90.0)), [("TimeUS", "f8"), ("Alt", "f8")])
    _add_columns(log_data, "ARSP", ((20.0, 12.0), (30.0, 7.0)), [("TimeUS", "f8"), ("Airspeed", "f8")])
    _add_columns(
        log_data,
        "RFND",
        ((20.0, 8.0, 0, 25, 4), (30.0, 3.0, 0, 25, 4)),
        [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1"), ("Orient", "u1"), ("Stat", "u1")],
    )
    _add_columns(
        log_data,
        "CMD",
        ((30.0, 1, 0, 21, -35.0, 174.0),),
        [("TimeUS", "f8"), ("CTot", "i4"), ("CNum", "i4"), ("CId", "i4"), ("Lat", "f8"), ("Lng", "f8")],
    )
    history = ParameterHistory(
        {"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "LAND_PF_ALT": 5.0},
        {"LAND_PF_ALT": (ParameterChange(time_s=30.0, value=7.0),)},
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    first_stages = PlaneLandingEvidenceExtractor.extract(log_data, attempts[0], history)
    second_stages = PlaneLandingEvidenceExtractor.extract(log_data, attempts[1], history)
    first_messages = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempts[0])
    second_messages = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempts[1])
    second_target = PlaneLandingMissionTargetExtractor.target_for_attempt(log_data, attempts[1])

    assert attempts[0].end_reason is PlaneLandingEndReason.STAGE_RESTART
    assert [item.time_s for item in first_stages] == [29.0]
    assert [item.time_s for item in second_stages] == [30.0, 35.0]
    assert (
        first_stages[0].gps_ground_speed_m_s,
        first_stages[0].barometric_altitude_m,
        first_stages[0].airspeed_m_s,
        first_stages[0].rangefinder_distance_m,
    ) == (8.0, 100.0, 12.0, 8.0)
    assert (
        second_stages[0].gps_ground_speed_m_s,
        second_stages[0].barometric_altitude_m,
        second_stages[0].airspeed_m_s,
        second_stages[0].rangefinder_distance_m,
    ) == (3.0, 90.0, 7.0, 3.0)
    assert not first_messages
    assert [item.time_s for item in second_messages] == [30.0]
    assert first_stages[0].parameter_values["LAND_PF_ALT"] == 5.0
    assert second_stages[0].parameter_values["LAND_PF_ALT"] == 7.0
    assert second_target is not None
    assert second_target.snapshot_completed_s == 30.0


def test_restart_wins_equal_time_termination_tie() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (20.0, 6.0), (40.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (29.0, 0), (30.0, 2)),
        messages=((30.0, "Landing aborted"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert (attempts[0].end_s, attempts[0].end_reason) == (30.0, PlaneLandingEndReason.STAGE_RESTART)
    assert attempts[1].start_s == 30.0


@pytest.mark.parametrize(
    ("land_records", "land_dtype", "mode_records", "mode_dtype"),
    [
        (((1,),), [("stage", "i4")], ((0.0, 10),), [("TimeUS", "f8"), ("ModeNum", "i4")]),
        (((10.0,),), [("TimeUS", "f8")], ((0.0, 10),), [("TimeUS", "f8"), ("ModeNum", "i4")]),
        (((10.0, 1),), [("TimeUS", "f8"), ("stage", "i4")], ((10,),), [("ModeNum", "i4")]),
        (((10.0, 1),), [("TimeUS", "f8"), ("stage", "i4")], ((0.0,),), [("TimeUS", "f8")]),
    ],
)
def test_partial_land_or_mode_schema_returns_no_attempts(
    land_records: Sequence[tuple[object, ...]],
    land_dtype: list[tuple[str, str]],
    mode_records: Sequence[tuple[object, ...]],
    mode_dtype: list[tuple[str, str]],
) -> None:
    log_data = LogData(vehicle_type="ArduPlane", firmware_version=(4, 7, 0))
    _add_columns(log_data, "LAND", land_records, land_dtype)
    _add_columns(log_data, "MODE", mode_records, mode_dtype)

    assert not PlaneLandingAttemptDetector.detect(
        log_data,
        FlightSegment(start_s=0.0, end_s=20.0, is_complete=False),
    )


def test_go_around_does_not_split_parent_flight_segment() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (15.0, 2.0), (17.0, 2.0), (20.0, 6.0), (60.0, 6.0), (61.0, 0.0), (91.0, 0.0)),
        land=((5.0, 0), (10.0, 1), (11.0, 2), (12.0, 3), (30.0, 1)),
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
        ((5_000_000, 0), (10_000_000, 1), (15_000_000, 2)),
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
    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempts[0], ParameterHistory())

    assert attempts[0].start_s == 10.0
    assert attempts[0].end_s == 20.0
    assert attempts[0].duration_s == 10.0
    assert evidence[0].time_s == 15.0


def test_inactive_gps_receiver_cannot_create_false_stop() -> None:
    log_data = _plane_log(messages=((40.0, "Throttle disarmed"),))
    _add_columns(
        log_data,
        "GPS",
        (
            (0.0, 6.0, 0, 1),
            (2.0, 6.0, 0, 1),
            (11.0, 1.0, 1, 0),
            (13.0, 1.0, 1, 0),
            (20.0, 6.0, 0, 1),
            (40.0, 6.0, 0, 1),
        ),
        [("TimeUS", "f8"), ("Spd", "f8"), ("I", "u1"), ("U", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.start_s, attempt.end_s, attempt.end_reason) == (10.0, 40.0, PlaneLandingEndReason.DISARM)


def test_inactive_gps_receiver_cannot_supply_stage_speed() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "GPS",
        (
            (0.0, 6.0, 0, 1),
            (2.0, 6.0, 0, 1),
            (14.0, 7.0, 0, 1),
            (15.0, 1.0, 1, 0),
            (16.0, 8.0, 0, 1),
            (40.0, 6.0, 0, 1),
        ),
        [("TimeUS", "f8"), ("Spd", "f8"), ("I", "u1"), ("U", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    assert evidence[0].gps_ground_speed_m_s == 7.0


def test_inactive_gps_receiver_cannot_supply_target_distance_position() -> None:
    log_data = _gps_stop_log(((1.0, 1, 0, 21, 0.0, 1.0),))
    _add_columns(
        log_data,
        "GPS",
        (
            (20.0, 2.0, 10.0, 10.0, 1, 0),
            (20.0, 2.0, 0.0, 1.001, 0, 1),
        ),
        [("TimeUS", "f8"), ("Spd", "f8"), ("Lat", "f8"), ("Lng", "f8"), ("I", "u1"), ("U", "u1")],
    )
    segment = FlightSegment(start_s=0.0, end_s=30.0, is_complete=True)
    attempt = PlaneLandingAttempt(
        flight_segment=segment,
        start_s=10.0,
        end_s=20.0,
        end_reason=PlaneLandingEndReason.GPS_STOP,
        mode_number=PlaneLandingAttemptDetector.AUTO_MODE_NUMBER,
    )

    distance = PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt)

    assert distance is not None
    assert (distance.aircraft_latitude_deg, distance.aircraft_longitude_deg) == (0.0, 1.001)
    assert distance.distance_m == pytest.approx(111.1949266)


def test_gps_without_use_flag_retains_existing_stop_behavior() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (20.0, 2.0), (22.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (11.0, 2), (14.0, 3)),
    )
    gps = log_data.get_message_columns("GPS")
    assert gps is not None
    assert "U" not in (gps.dtype.names or ())
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (20.0, PlaneLandingEndReason.GPS_STOP)


def test_preflare_headwind_low_groundspeed_does_not_truncate_before_final() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (11.0, 2.0), (13.0, 2.0), (20.0, 5.0), (25.0, 2.0), (27.0, 2.0)),
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.start_s, attempt.end_s, attempt.end_reason) == (10.0, 25.0, PlaneLandingEndReason.GPS_STOP)


def test_pre_final_low_speed_run_is_reset_at_corroboration() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (18.0, 2.0), (20.0, 2.0), (22.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (20.0, PlaneLandingEndReason.GPS_STOP)


@pytest.mark.parametrize(
    ("mode", "land", "messages", "expected_reason"),
    [
        (((0.0, 10),), ((5.0, 0), (10.0, 1), (12.0, 3)), ((45.0, "Throttle disarmed"),), PlaneLandingEndReason.DISARM),
        (((0.0, 10),), ((5.0, 0), (10.0, 1), (12.0, 3)), ((45.0, "Landing aborted"),), PlaneLandingEndReason.ABORT),
        (((0.0, 10), (45.0, 5)), ((5.0, 0), (10.0, 1), (12.0, 3)), None, PlaneLandingEndReason.MODE_EXIT),
        (((0.0, 10),), ((5.0, 0), (10.0, 1), (12.0, 3), (45.0, 1)), None, PlaneLandingEndReason.STAGE_RESTART),
    ],
)
def test_gps_persistence_cannot_be_confirmed_after_competing_termination(
    mode: Sequence[tuple[float, int]],
    land: Sequence[tuple[object, ...]],
    messages: Sequence[tuple[float, str]] | None,
    expected_reason: PlaneLandingEndReason,
) -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (44.0, 2.0), (46.0, 2.0), (60.0, 6.0)),
        land=land,
        mode=mode,
        messages=messages,
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (45.0, expected_reason)


def test_gps_persistence_confirmed_before_disarm_backdates_to_first_low_sample() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (42.0, 2.0), (44.0, 2.0), (60.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (12.0, 3)),
        messages=((45.0, "Throttle disarmed"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (42.0, PlaneLandingEndReason.GPS_STOP)


def test_zero_length_gps_stop_attempt_is_omitted_without_crashing_analysis() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (10.0, 2.0), (12.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 3)),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    assert not attempts
    assert result.available is True
    assert not result.outcomes
    assert result.reason == "No Plane landing attempts detected"


def test_short_positive_duration_gps_stop_attempt_remains_valid() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (10.001, 2.0), (12.001, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 3)),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.start_s, attempt.end_s, attempt.end_reason) == (
        10.0,
        10.001,
        PlaneLandingEndReason.GPS_STOP,
    )


def test_later_disarm_does_not_replace_zero_length_gps_stop() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (10.0, 2.0), (12.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 3)),
        messages=((20.0, "Throttle disarmed"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert not attempts


def test_stage_three_alone_corroborates_gps_stop() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (14.0, 4.0), (16.0, 2.0), (18.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (12.0, 2), (14.0, 3)),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (16.0, PlaneLandingEndReason.GPS_STOP)


def test_complete_firmware_flare_corroborates_gps_stop_without_stage_three() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (12.0, 2.0), (14.0, 2.0), (16.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (11.0, 2)),
        messages=((13.0, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (14.0, PlaneLandingEndReason.GPS_STOP)


@pytest.mark.parametrize(
    "message",
    [
        "Flare malformed",
        "Flare 2.0m sink=1.0 speed=10.0",
        "Flare nanm sink=1.0 speed=10.0 dist=20.0",
        "Flare 2.0m sink=inf speed=10.0 dist=20.0",
    ],
)
def test_unusable_firmware_flare_does_not_corroborate_gps_stop(message: str) -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (12.0, 2.0), (14.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (11.0, 2)),
        messages=((11.5, message), (25.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (25.0, PlaneLandingEndReason.DISARM)


def test_stage_evidence_uses_land_and_nearest_optional_telemetry() -> None:
    log_data = _plane_log(
        gps=(
            (0.0, 6.0),
            (2.0, 6.0),
            (14.9, 8.0),
            (15.0, 7.0),
            (15.1, 9.0),
            (19.9, 6.0),
            (20.0, 5.0),
            (20.1, 7.0),
            (60.0, 6.0),
            (61.0, 0.0),
            (91.0, 0.0),
        ),
        land=((5.0, 0, 0.0), (10.0, 1, 20.0), (15.0, 2, 5.5), (20.0, 3, 1.2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(log_data, "ARSP", ((14.8, 12.0), (15.1, 12.154), (19.8, 9.0)), [("TimeUS", "f8"), ("Airspeed", "f8")])
    _add_columns(
        log_data,
        "BARO",
        ((14.5, 101.0), (14.9, 100.0), (15.5, 99.0), (19.5, 92.0), (20.1, 90.0), (20.5, 89.0)),
        [("TimeUS", "f8"), ("Alt", "f8")],
    )
    _add_columns(log_data, "RFND", ((14.7, 6.0), (20.2, 1.5)), [("TimeUS", "f8"), ("Dist", "f8")])
    history = ParameterHistory(
        {
            "LAND_PF_ALT": 6.0,
            "LAND_PF_SEC": 2.0,
            "LAND_FLARE_ALT": 3.0,
            "LAND_FLARE_SEC": 1.5,
            "LAND_PITCH_DEG": 4.0,
        }
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, history)
    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    assert [item.stage for item in evidence] == [PlaneLandingStage.PREFLARE, PlaneLandingStage.FLARE]
    preflare, flare = evidence
    assert (preflare.time_s, preflare.flight_height_m) == (15.0, 5.5)
    assert (preflare.airspeed_m_s, preflare.barometric_altitude_m, preflare.rangefinder_distance_m) == (
        12.154,
        100.0,
        6.0,
    )
    assert preflare.rangefinder_status is None
    assert preflare.gps_ground_speed_m_s == 7.0
    assert preflare.barometric_sink_rate_m_s == 2.0
    assert preflare.flare_to_gps_stop_s is None
    assert preflare.parameter_values == {"LAND_PF_ALT": 6.0, "LAND_PF_SEC": 2.0}
    assert (flare.time_s, flare.flight_height_m) == (20.0, 1.2)
    assert (flare.airspeed_m_s, flare.barometric_altitude_m, flare.rangefinder_distance_m) == (9.0, 90.0, 1.5)
    assert flare.rangefinder_status is None
    assert flare.gps_ground_speed_m_s == 5.0
    assert flare.barometric_sink_rate_m_s is None
    assert flare.flare_to_gps_stop_s is None
    assert flare.parameter_values == {
        "LAND_FLARE_ALT": 3.0,
        "LAND_FLARE_SEC": 1.5,
        "LAND_PITCH_DEG": 4.0,
    }
    outcome_messages = [outcome.message for outcome in result.outcomes]
    for expected_measurement in (
        "LAND stage 2 entered",
        "LAND stage 3 entered",
        "LAND flight height",
        "ARSP airspeed",
        "GPS groundspeed",
        "BARO altitude",
        "BARO sink rate",
        "RFND distance",
        "LAND_PF_ALT effective value",
        "LAND_FLARE_ALT effective value",
        "LAND_PITCH_DEG effective value",
    ):
        assert any(expected_measurement in message for message in outcome_messages)
    assert all(outcome.param_name is None for outcome in result.outcomes)
    assert all(outcome.suggested_value is None for outcome in result.outcomes)
    assert all(isinstance(outcome, LogAnalysis) for outcome in result.outcomes)
    assert result.outcomes[0].group == "Attempt 1 — Summary"
    assert result.outcomes[0].message.startswith("AUTO landing: 0:10.0 → 0:40.0\nTermination:")
    assert any(outcome.message == "ARSP airspeed: 12.2 m/s" and outcome.value == 12.154 for outcome in result.outcomes)
    assert all(not outcome.message.startswith("Attempt 1") for outcome in result.outcomes)
    assert any(outcome.group == "Attempt 1 — Preflare" for outcome in result.outcomes)
    assert any(outcome.group == "Attempt 1 — Flare" for outcome in result.outcomes)
    assert not any(
        label in outcome.message.lower() for outcome in result.outcomes for label in ("good", "poor", "safe", "unsafe")
    )


def test_start_of_final_altitude_uses_nearest_attempt_scoped_primary_baro_observation() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
        include_baro=False,
    )
    _add_columns(
        log_data,
        "BARO",
        ((9.99, 20.0, 0), (10.05, 999.0, 1), (10.2, 18.8, 0)),
        [("TimeUS", "f8"), ("Alt", "f8"), ("I", "u1")],
    )

    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    altitude_outcome = next(outcome for outcome in result.outcomes if "start-of-final altitude" in outcome.message.lower())
    assert (attempt.start_s, attempt.end_s, attempt.end_reason) == (10.0, 40.0, PlaneLandingEndReason.DISARM)
    assert (altitude_outcome.timestamp_us, altitude_outcome.value) == (10_000_000, 18.8)
    assert altitude_outcome.group == "Attempt 1 — Summary"


@pytest.mark.parametrize("baro_records", [None, ((10.1, np.nan),)])
def test_missing_or_invalid_start_of_final_altitude_is_reported_unavailable(
    baro_records: tuple[tuple[float, float], ...] | None,
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
        include_baro=False,
    )
    if baro_records is not None:
        _add_columns(log_data, "BARO", baro_records, [("TimeUS", "f8"), ("Alt", "f8")])

    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    altitude_outcome = next(outcome for outcome in result.outcomes if "start-of-final altitude" in outcome.message.lower())
    assert (attempt.start_s, attempt.end_s, attempt.end_reason) == (10.0, 40.0, PlaneLandingEndReason.DISARM)
    assert altitude_outcome.timestamp_us == 10_000_000
    assert altitude_outcome.value is None
    assert "unavailable" in altitude_outcome.message
    assert altitude_outcome.group == "Attempt 1 — Summary"


@pytest.mark.parametrize(("nonprimary_used", "nonprimary_healthy"), [(1, 1), (0, 1), (1, 0)])
def test_arsp_nearest_value_uses_healthy_primary_sensor_regardless_of_row_order(
    nonprimary_used: int,
    nonprimary_healthy: int,
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "ARSP",
        (
            (15.0, 5.0, 0, nonprimary_used, nonprimary_healthy, 1),
            (15.0, 22.0, 1, 1, 1, 1),
        ),
        [("TimeUS", "f8"), ("Airspeed", "f8"), ("I", "u1"), ("U", "u1"), ("H", "u1"), ("Pri", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    assert evidence[0].airspeed_m_s == 22.0


@pytest.mark.parametrize("primary_used", [0, 1])
def test_arsp_observational_evidence_does_not_require_primary_use(primary_used: int) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "ARSP",
        (
            (15.0, 5.0, 0, 1, 1, 1),
            (15.0, 22.0, 1, primary_used, 1, 1),
        ),
        [("TimeUS", "f8"), ("Airspeed", "f8"), ("I", "u1"), ("U", "u1"), ("H", "u1"), ("Pri", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    assert evidence[0].airspeed_m_s == 22.0


def test_arsp_selector_schema_without_use_field_remains_sufficient() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "ARSP",
        ((15.0, 22.0, 1, 1, 1),),
        [("TimeUS", "f8"), ("Airspeed", "f8"), ("I", "u1"), ("H", "u1"), ("Pri", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    assert evidence[0].airspeed_m_s == 22.0


@pytest.mark.parametrize(
    "arsp_records",
    [
        ((15.0, 5.0, 0, 1, 1, 1), (15.0, 22.0, 1, 1, 0, 1)),
        ((15.0, 5.0, 0, 1, 1, 1), (15.0, float("nan"), 1, 1, 1, 1)),
        ((15.0, 5.0, 0, 1, 1, 0), (15.0, 22.0, 1, 1, 1, 1)),
        ((15.0, 5.0, float("nan"), 1, 1, 1), (15.0, 22.0, 1, 1, 1, 1)),
        ((15.0, 5.0, 0, 1, 1, float("inf")), (15.0, 22.0, 1, 1, 1, 1)),
        ((15.0, 5.0, 0, 1, 1, 1), (15.0, 22.0, 1, 1, float("inf"), 1)),
        ((15.0, 21.0, 1, 1, 1, 1), (15.0, 22.0, 1, 1, 1, 1)),
    ],
)
def test_arsp_unusable_or_ambiguous_primary_is_unavailable(
    arsp_records: Sequence[tuple[object, ...]],
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "ARSP",
        arsp_records,
        [("TimeUS", "f8"), ("Airspeed", "f8"), ("I", "f8"), ("U", "f8"), ("H", "f8"), ("Pri", "f8")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    assert evidence[0].airspeed_m_s is None


def test_arsp_partial_selector_schema_is_unavailable() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "ARSP",
        ((15.0, 22.0, 1),),
        [("TimeUS", "f8"), ("Airspeed", "f8"), ("I", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    assert evidence[0].airspeed_m_s is None


@pytest.mark.parametrize(
    ("event_airspeed", "event_healthy"),
    [(22.0, 0.0), (float("nan"), 1.0)],
    ids=("unhealthy", "non-finite"),
)
def test_arsp_nearest_primary_frame_does_not_fall_back_to_farther_healthy_value(
    event_airspeed: float,
    event_healthy: float,
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "ARSP",
        (
            (10.0, 21.0, 1, 0, 1, 1),
            (20.0, 30.0, 0, 1, 1, 1),
            (20.0, event_airspeed, 1, 1, event_healthy, 1),
            (30.0, 23.0, 1, 1, 1, 1),
        ),
        [("TimeUS", "f8"), ("Airspeed", "f8"), ("I", "u1"), ("U", "u1"), ("H", "f8"), ("Pri", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    flare = next(item for item in evidence if item.stage is PlaneLandingStage.FLARE)
    assert flare.airspeed_m_s is None
    assert not any("ARSP airspeed" in outcome.message for outcome in result.outcomes)


def test_arsp_ambiguous_nearest_primary_frame_does_not_fall_back_to_farther_healthy_value() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "ARSP",
        (
            (10.0, 21.0, 1, 1, 1),
            (20.0, 30.0, 0, 1, 0),
            (20.0, 22.0, 1, 1, 1),
            (30.0, 23.0, 1, 1, 1),
        ),
        [("TimeUS", "f8"), ("Airspeed", "f8"), ("I", "u1"), ("H", "u1"), ("Pri", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    flare = next(item for item in evidence if item.stage is PlaneLandingStage.FLARE)
    assert flare.airspeed_m_s is None


@pytest.mark.parametrize(
    "records",
    [
        ((20.0, float("nan")), (30.0, 23.0)),
        ((10.0, 21.0), (20.0, float("nan")), (30.0, 23.0)),
    ],
    ids=("finite-later", "finite-older-and-newer"),
)
def test_legacy_arsp_nearest_non_finite_observation_does_not_fall_back(
    records: Sequence[tuple[float, float]],
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(log_data, "ARSP", records, [("TimeUS", "f8"), ("Airspeed", "f8")])
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    flare = next(item for item in evidence if item.stage is PlaneLandingStage.FLARE)
    assert flare.airspeed_m_s is None


@pytest.mark.parametrize(
    ("records", "expected_airspeed_m_s"),
    [
        (((20.0, 22.0), (30.0, 23.0)), 22.0),
        (((19.0, 21.0), (21.0, 23.0)), 21.0),
    ],
    ids=("nearest-finite", "equidistant-first-wins"),
)
def test_legacy_arsp_nearest_finite_observation_preserves_existing_tie_behavior(
    records: Sequence[tuple[float, float]],
    expected_airspeed_m_s: float,
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(log_data, "ARSP", records, [("TimeUS", "f8"), ("Airspeed", "f8")])
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    flare = next(item for item in evidence if item.stage is PlaneLandingStage.FLARE)
    assert flare.airspeed_m_s == expected_airspeed_m_s


def test_flare_to_gps_stop_uses_the_authoritative_attempt_end() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (12.0, 5.0), (14.0, 4.0), (20.0, 2.0), (22.0, 2.0), (30.0, 6.0)),
        land=((5.0, 0), (10.0, 1), (12.0, 2), (14.0, 3)),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    assert (attempt.start_s, attempt.end_s, attempt.end_reason) == (10.0, 20.0, PlaneLandingEndReason.GPS_STOP)
    flare = next(item for item in evidence if item.stage is PlaneLandingStage.FLARE)
    assert flare.flare_to_gps_stop_s == 6.0
    outcomes = [outcome for outcome in result.outcomes if "Flare to GPS stop" in outcome.message]
    assert [(outcome.timestamp_us, outcome.value) for outcome in outcomes] == [(14_000_000, 6.0)]


def test_sparse_and_non_finite_baro_omits_preflare_sink_rate() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
        include_baro=False,
    )
    _add_columns(
        log_data,
        "BARO",
        ((float("nan"), 95.0), (14.5, float("nan")), (15.0, 100.0), (15.5, float("inf"))),
        [("TimeUS", "f8"), ("Alt", "f8")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    preflare = next(item for item in evidence if item.stage is PlaneLandingStage.PREFLARE)
    assert preflare.barometric_altitude_m == 100.0
    assert preflare.barometric_sink_rate_m_s is None


def test_duplicate_timestamp_baro_omits_preflare_sink_rate() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
        include_baro=False,
    )
    _add_columns(
        log_data,
        "BARO",
        ((15.0, 100.0), (15.0, 99.0)),
        [("TimeUS", "f8"), ("Alt", "f8")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    preflare = next(item for item in evidence if item.stage is PlaneLandingStage.PREFLARE)
    assert preflare.barometric_altitude_m == 100.0
    assert preflare.barometric_sink_rate_m_s is None


@pytest.mark.parametrize(("message_name", "field_name"), [("BARO", "Alt"), ("GPS", "Spd")])
@pytest.mark.parametrize(
    ("records", "expected_value"),
    [
        (((20.0, float("nan")), (30.0, 23.0)), None),
        (((10.0, 21.0), (20.0, float("nan")), (30.0, 23.0)), None),
        (((20.0, 22.0), (30.0, 23.0)), 22.0),
        (((20.0, 0.0), (30.0, 23.0)), 0.0),
        (((19.0, 21.0), (21.0, 23.0)), 21.0),
    ],
    ids=("non-finite-with-later", "non-finite-with-older-and-newer", "finite", "zero", "tie-first-wins"),
)
def test_stage_nearest_value_applies_finiteness_after_selection(
    message_name: str,
    field_name: str,
    records: Sequence[tuple[float, float]],
    expected_value: float | None,
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
        include_baro=False,
    )
    _add_columns(log_data, message_name, records, [("TimeUS", "f8"), (field_name, "f8")])
    attempt = PlaneLandingAttempt(
        flight_segment=FlightSegment(start_s=0.0, end_s=40.0, is_complete=False),
        start_s=10.0,
        end_s=40.0,
        end_reason=PlaneLandingEndReason.DISARM,
        mode_number=PlaneLandingAttemptDetector.AUTO_MODE_NUMBER,
    )

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    flare = next(item for item in evidence if item.stage is PlaneLandingStage.FLARE)
    actual_value = flare.barometric_altitude_m if message_name == "BARO" else flare.gps_ground_speed_m_s
    assert actual_value == expected_value


def test_baro_stage_altitude_and_sink_rate_use_only_instance_zero() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
        include_baro=False,
    )
    _add_columns(
        log_data,
        "BARO",
        (
            (14.5, 200.0, 1),
            (14.5, 100.0, 0),
            (15.0, 199.5, 1),
            (15.0, 99.5, 0),
            (15.5, 199.0, 1),
            (15.5, 99.0, 0),
        ),
        [("TimeUS", "f8"), ("Alt", "f8"), ("I", "u1")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())

    preflare = next(item for item in evidence if item.stage is PlaneLandingStage.PREFLARE)
    assert preflare.barometric_altitude_m == 99.5
    assert preflare.barometric_sink_rate_m_s == pytest.approx(1.0)


def test_firmware_flare_and_glide_slope_messages_are_separate_from_land_stage() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=(
            (10.1, "Landing glide slope 4.7 degrees"),
            (19.9999, "Flare -160.1m sink=1.13 speed=13.5 dist=32.6"),
            (40.0, "Throttle disarmed"),
        ),
    )
    _add_columns(log_data, "ARSP", ((20.0, 17.0),), [("TimeUS", "f8"), ("Airspeed", "f8")])
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    stage_evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())
    firmware_evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    stage_flare = next(item for item in stage_evidence if item.stage is PlaneLandingStage.FLARE)
    glide_slope = next(item for item in firmware_evidence if isinstance(item, PlaneLandingFirmwareGlideSlopeEvidence))
    firmware_flare = next(item for item in firmware_evidence if isinstance(item, PlaneLandingFirmwareFlareEvidence))
    assert (glide_slope.time_s, glide_slope.glide_slope_degrees) == (10.1, 4.7)
    assert firmware_flare == PlaneLandingFirmwareFlareEvidence(
        attempt=attempt,
        time_s=19.9999,
        altitude_m=-160.1,
        sink_rate_m_s=1.13,
        groundspeed_m_s=13.5,
        distance_to_target_m=32.6,
    )
    assert stage_flare.time_s == 20.0
    assert stage_flare.airspeed_m_s == 17.0
    assert firmware_flare.groundspeed_m_s == 13.5
    assert firmware_flare.time_s != stage_flare.time_s
    glide_slope_outcomes = [outcome for outcome in result.outcomes if outcome.message.startswith("Glide slope:")]
    firmware_outcomes = [outcome for outcome in result.outcomes if outcome.group == "Attempt 1 — Firmware evidence"]
    start_altitude_index = next(
        index for index, outcome in enumerate(result.outcomes) if "start-of-final altitude" in outcome.message.lower()
    )
    glide_slope_indices = [
        index for index, outcome in enumerate(result.outcomes) if outcome.message.startswith("Glide slope:")
    ]
    preflare_index = next(index for index, outcome in enumerate(result.outcomes) if "LAND stage 2" in outcome.message)
    assert len(glide_slope_indices) == 1
    assert start_altitude_index < glide_slope_indices[0] < preflare_index
    assert [(outcome.timestamp_us, outcome.value) for outcome in glide_slope_outcomes] == [(10_100_000, 4.7)]
    assert [outcome.timestamp_us for outcome in firmware_outcomes] == [19_999_900] * 4
    assert [outcome.value for outcome in firmware_outcomes] == [-160.1, 1.13, 13.5, 32.6]
    assert glide_slope_outcomes[0].message == "Glide slope: 4.7°"
    assert any(outcome.message == "Flare groundspeed: 13.5 m/s" for outcome in firmware_outcomes)
    assert all(isinstance(outcome, LogAnalysis) for outcome in glide_slope_outcomes + firmware_outcomes)
    assert all(outcome.param_name is None and outcome.suggested_value is None for outcome in firmware_outcomes)
    assert glide_slope_outcomes[0].group == "Attempt 1 — Summary"
    assert not any(
        label in outcome.message.lower() for outcome in firmware_outcomes for label in ("good", "poor", "safe", "unsafe")
    )


@pytest.mark.parametrize(
    "message",
    [
        "Flare malformed",
        "Flare 1.2m sink=bad speed=10.0 dist=20.0",
        "Flare 1.2m sink=0.5 speed=10.0",
        "Flare 1.2m sink=nan speed=10.0 dist=20.0",
    ],
)
def test_malformed_or_partial_firmware_flare_message_is_omitted(message: str) -> None:
    log_data = _plane_log(messages=((15.0, message), (40.0, "Throttle disarmed")))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert not any(isinstance(item, PlaneLandingFirmwareFlareEvidence) for item in evidence)


@pytest.mark.parametrize(
    "message",
    [
        "Landing glide slope malformed",
        "Landing glide slope nan degrees",
        "Landing glide slope 4.7",
    ],
)
def test_malformed_firmware_glide_slope_message_is_omitted(message: str) -> None:
    log_data = _plane_log(messages=((15.0, message), (40.0, "Throttle disarmed")))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert not any(isinstance(item, PlaneLandingFirmwareGlideSlopeEvidence) for item in evidence)


def test_firmware_messages_outside_attempt_are_ignored() -> None:
    log_data = _plane_log(
        messages=(
            (9.9, "Landing approach start at 20.0m"),
            (9.95, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"),
            (20.0, "Landing aborted"),
            (20.1, "Landing glide slope 4.7 degrees"),
        )
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert (attempt.start_s, attempt.end_s) == (10.0, 20.0)
    assert not evidence


def test_stage_three_opened_attempt_associates_immediately_preceding_flare() -> None:
    log_data = _plane_log(
        land=((9.998, 0), (10.0, 3)),
        messages=((9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    flare = next(item for item in evidence if isinstance(item, PlaneLandingFirmwareFlareEvidence))
    assert (attempt.start_s, attempt.start_stage) == (10.0, 3)
    assert flare.time_s == 9.999
    assert flare.associated_before_attempt_start is True


@pytest.mark.parametrize(("flare_mode", "attempt_mode"), [(26, 10), (10, 26)])
def test_prestart_flare_known_mode_mismatch_is_rejected(flare_mode: int, attempt_mode: int) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (9.998, 0), (10.0, 3)),
        mode=((0.0, flare_mode), (10.0, attempt_mode)),
        messages=((9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert not any(isinstance(item, PlaneLandingFirmwareFlareEvidence) for item in evidence)


def test_prestart_flare_known_same_mode_remains_associated() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (9.998, 0), (10.0, 3)),
        mode=((0.0, 10),),
        messages=((9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    flare = next(
        item
        for item in PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
        if isinstance(item, PlaneLandingFirmwareFlareEvidence)
    )

    assert (flare.time_s, flare.associated_before_attempt_start) == (9.999, True)


def test_prestart_flare_unknown_mode_is_not_treated_as_contradictory() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (9.998, 0), (10.0, 3)),
        mode=((10.0, 10),),
        messages=((9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    flare = next(
        item
        for item in PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
        if isinstance(item, PlaneLandingFirmwareFlareEvidence)
    )

    assert (flare.time_s, flare.associated_before_attempt_start) == (9.999, True)


@pytest.mark.parametrize(("earlier_mode", "later_mode"), [(26, 10), (10, 26)])
def test_mode_transition_flare_is_owned_only_by_earlier_attempt(earlier_mode: int, later_mode: int) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (20.0, 3), (29.998, 0), (30.0, 3)),
        mode=((0.0, earlier_mode), (29.9995, later_mode)),
        messages=((29.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    flare_evidence = [
        (attempt_number, evidence)
        for attempt_number, attempt in enumerate(attempts, start=1)
        for evidence in PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
        if isinstance(evidence, PlaneLandingFirmwareFlareEvidence)
    ]

    assert len(attempts) == 2
    assert [(number, evidence.time_s, evidence.associated_before_attempt_start) for number, evidence in flare_evidence] == [
        (1, 29.999, False)
    ]


def test_same_mode_restart_flare_is_owned_only_by_earlier_attempt() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (20.0, 3), (29.998, 0), (30.0, 3)),
        messages=((29.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    flare_evidence = [
        (attempt_number, evidence)
        for attempt_number, attempt in enumerate(attempts, start=1)
        for evidence in PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
        if isinstance(evidence, PlaneLandingFirmwareFlareEvidence)
    ]

    assert len(attempts) == 2
    assert [(number, evidence.time_s, evidence.associated_before_attempt_start) for number, evidence in flare_evidence] == [
        (1, 29.999, False)
    ]


def test_stage_two_opened_attempt_cannot_associate_preceding_flare() -> None:
    log_data = _plane_log(
        land=((9.998, 0), (10.0, 2)),
        messages=((9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert attempt.start_stage == 2
    assert not any(isinstance(item, PlaneLandingFirmwareFlareEvidence) for item in evidence)


@pytest.mark.parametrize(
    ("land", "messages", "mode"),
    [
        (
            ((9.998, 0), (9.9995, 0), (10.0, 3)),
            ((9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
            ((0.0, 10),),
        ),
        (
            ((9.998, 0), (10.0, 3)),
            (
                (9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"),
                (9.9995, "Landing aborted"),
                (40.0, "Throttle disarmed"),
            ),
            ((0.0, 10),),
        ),
        (
            ((9.998, 0), (10.0, 3)),
            (
                (9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"),
                (9.9995, "Throttle disarmed"),
                (40.0, "Throttle disarmed"),
            ),
            ((0.0, 10),),
        ),
        (
            ((9.998, 0), (10.0, 3)),
            ((9.999, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
            ((0.0, 10), (9.9995, 5), (10.0, 10)),
        ),
    ],
)
def test_intervening_reset_termination_or_mode_exit_blocks_left_truncated_flare(
    land: Sequence[tuple[float, int]],
    messages: Sequence[tuple[float, str]],
    mode: Sequence[tuple[float, int]],
) -> None:
    log_data = _plane_log(land=land, messages=messages, mode=mode)
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert not any(isinstance(item, PlaneLandingFirmwareFlareEvidence) for item in evidence)


@pytest.mark.parametrize(
    "message",
    ["Flare malformed", "Flare 2.0m sink=nan speed=10.0 dist=20.0"],
)
def test_unusable_preceding_flare_is_not_associated(message: str) -> None:
    log_data = _plane_log(
        land=((9.998, 0), (10.0, 3)),
        messages=((9.999, message), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert not any(
        isinstance(item, PlaneLandingFirmwareFlareEvidence)
        for item in PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
    )


def test_old_or_outside_parent_flare_is_not_associated() -> None:
    log_data = _plane_log(
        land=((9.5, 0), (10.0, 3)),
        messages=((9.0, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"),),
    )
    attempt = PlaneLandingAttempt(
        flight_segment=FlightSegment(start_s=9.25, end_s=20.0, is_complete=False),
        start_s=10.0,
        end_s=20.0,
        end_reason=PlaneLandingEndReason.FLIGHT_SEGMENT_END,
        mode_number=10,
        start_stage=3,
    )

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert not any(isinstance(item, PlaneLandingFirmwareFlareEvidence) for item in evidence)


def test_old_flare_before_preceding_land_record_is_not_associated() -> None:
    log_data = _plane_log(
        land=((9.5, 0), (10.0, 3)),
        messages=((9.0, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"), (40.0, "Throttle disarmed")),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)

    assert not any(isinstance(item, PlaneLandingFirmwareFlareEvidence) for item in evidence)


def test_multiple_attempts_do_not_cross_associate_firmware_messages() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (11.0, 3), (25.0, 0), (30.0, 1), (31.0, 3)),
        messages=(
            (10.1, "Landing glide slope 4.0 degrees"),
            (15.0, "Flare 2.0m sink=1.0 speed=10.0 dist=20.0"),
            (20.0, "Landing aborted"),
            (30.1, "Landing glide slope 5.0 degrees"),
            (35.0, "Flare 3.0m sink=2.0 speed=11.0 dist=30.0"),
            (50.0, "Throttle disarmed"),
        ),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    first = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempts[0])
    second = PlaneLandingFirmwareMessageExtractor.extract(log_data, attempts[1])

    first_flare = next(item for item in first if isinstance(item, PlaneLandingFirmwareFlareEvidence))
    second_flare = next(item for item in second if isinstance(item, PlaneLandingFirmwareFlareEvidence))
    first_glide = next(item for item in first if isinstance(item, PlaneLandingFirmwareGlideSlopeEvidence))
    second_glide = next(item for item in second if isinstance(item, PlaneLandingFirmwareGlideSlopeEvidence))
    assert (first_flare.time_s, first_flare.altitude_m, first_glide.glide_slope_degrees) == (15.0, 2.0, 4.0)
    assert (second_flare.time_s, second_flare.altitude_m, second_glide.glide_slope_degrees) == (35.0, 3.0, 5.0)
    assert first_flare.attempt is attempts[0]
    assert second_flare.attempt is attempts[1]


def test_complete_cmd_snapshot_produces_independent_mission_target_distance() -> None:
    log_data = _gps_stop_log(
        (
            (1.0, 3, 0, 16, 0.0, 0.0),
            (2.0, 3, 1, 21, 0.0, 1.0),
            (3.0, 3, 2, 20, 0.0, 0.0),
        ),
        messages=((13.9999, "Flare 2.0m sink=1.0 speed=10.0 dist=32.6"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    target = PlaneLandingMissionTargetExtractor.target_for_attempt(log_data, attempt)
    distance = PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt)
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    assert target == PlaneLandingMissionTarget(
        attempt=attempt,
        snapshot_completed_s=3.0,
        latitude_deg=0.0,
        longitude_deg=1.0,
    )
    assert distance is not None
    assert (distance.time_s, distance.aircraft_position_time_s) == (20.0, 20.0)
    assert (distance.aircraft_latitude_deg, distance.aircraft_longitude_deg) == (0.0, 1.001)
    assert distance.distance_m == pytest.approx(111.1949266)
    firmware_distance = [outcome for outcome in result.outcomes if outcome.message.startswith("Flare distance to target:")]
    computed_distance = [
        outcome for outcome in result.outcomes if "computed distance to mission land target" in outcome.message.lower()
    ]
    assert [(outcome.timestamp_us, outcome.value) for outcome in firmware_distance] == [(13_999_900, 32.6)]
    assert {outcome.group for outcome in firmware_distance} == {"Attempt 1 — Firmware evidence"}
    assert len(computed_distance) == 1
    assert (computed_distance[0].timestamp_us, computed_distance[0].value) == pytest.approx((20_000_000, 111.1949266))
    assert computed_distance[0].group == "Attempt 1 — Mission-target evidence"
    assert all(isinstance(outcome, LogAnalysis) for outcome in result.outcomes)
    assert all(outcome.param_name is None and outcome.suggested_value is None for outcome in result.outcomes)
    assert not any(
        label in outcome.message.lower() for outcome in result.outcomes for label in ("good", "poor", "safe", "unsafe")
    )
    assert not any("touchdown" in outcome.message.lower() for outcome in result.outcomes)


def test_missing_cmd_keeps_analysis_available_and_omits_target_evidence() -> None:
    log_data = _gps_stop_log(None)
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    availability = _availability(log_data)
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    assert availability.available is True
    assert PlaneLandingMissionTargetExtractor.target_for_attempt(log_data, attempt) is None
    assert PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt) is None
    assert not any("computed distance to mission land target" in outcome.message.lower() for outcome in result.outcomes)


@pytest.mark.parametrize(
    "cmd",
    [
        ((1.0, 3, 0, 16, 0.0, 0.0), (2.0, 3, 2, 21, 0.0, 1.0)),
        ((1.0, 2, 0, 21, 0.0, 1.0), (2.0, 2, 1, 21, 0.0, 2.0)),
        ((1.0, 2, 0, 16, 0.0, 0.0), (2.0, 2, 1, 20, 0.0, 1.0)),
    ],
    ids=("incomplete", "ambiguous-land", "no-land"),
)
def test_unusable_cmd_snapshot_omits_target_evidence(cmd: Sequence[tuple[object, ...]]) -> None:
    log_data = _gps_stop_log(cmd)
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert PlaneLandingMissionTargetExtractor.target_for_attempt(log_data, attempt) is None
    assert PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt) is None


@pytest.mark.parametrize(("latitude", "longitude"), [(0.0, 0.0), (float("nan"), 1.0), (0.0, float("inf"))])
def test_malformed_mission_target_coordinates_are_rejected(latitude: float, longitude: float) -> None:
    log_data = _gps_stop_log(((1.0, 1, 0, 21, latitude, longitude),))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert PlaneLandingMissionTargetExtractor.target_for_attempt(log_data, attempt) is None
    assert PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt) is None


def test_latest_complete_snapshot_before_each_attempt_selects_the_correct_target() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (11.0, 3), (25.0, 0), (30.0, 1), (31.0, 3)),
        messages=((20.0, "Landing aborted"), (50.0, "Throttle disarmed")),
    )
    _add_columns(
        log_data,
        "CMD",
        (
            (1.0, 2, 0, 16, 0.0, 0.0),
            (2.0, 2, 1, 21, -35.0, 174.0),
            (22.0, 2, 0, 16, 0.0, 0.0),
            (23.0, 2, 1, 21, -36.0, 175.0),
        ),
        [("TimeUS", "f8"), ("CTot", "f8"), ("CNum", "f8"), ("CId", "f8"), ("Lat", "f8"), ("Lng", "f8")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempts = PlaneLandingAttemptDetector.detect(log_data, segment)

    first = PlaneLandingMissionTargetExtractor.target_for_attempt(log_data, attempts[0])
    second = PlaneLandingMissionTargetExtractor.target_for_attempt(log_data, attempts[1])

    assert first is not None
    assert second is not None
    assert (first.snapshot_completed_s, first.latitude_deg, first.longitude_deg) == (2.0, -35.0, 174.0)
    assert (second.snapshot_completed_s, second.latitude_deg, second.longitude_deg) == (23.0, -36.0, 175.0)
    assert first.attempt is attempts[0]
    assert second.attempt is attempts[1]


def test_target_distance_does_not_use_gps_position_outside_attempt() -> None:
    log_data = _gps_stop_log(((1.0, 1, 0, 21, 0.0, 1.0),))
    gps = log_data.get_message_columns("GPS")
    assert gps is not None
    gps["Lat"][3] = float("nan")
    gps["Lng"][3] = float("nan")
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    distance = PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt)

    assert (attempt.end_s, attempt.end_reason) == (20.0, PlaneLandingEndReason.GPS_STOP)
    assert distance is None


def test_target_distance_scopes_gps_positions_before_nearest_selection() -> None:
    log_data = _gps_stop_log(((1.0, 1, 0, 21, 0.0, 1.0),))
    _add_columns(
        log_data,
        "GPS",
        ((19.0, 2.0, 0.0, 1.001), (20.5, 2.0, 0.0, 1.002)),
        [("TimeUS", "f8"), ("Spd", "f8"), ("Lat", "f8"), ("Lng", "f8")],
    )
    attempt = PlaneLandingAttempt(
        flight_segment=FlightSegment(start_s=0.0, end_s=30.0, is_complete=False),
        start_s=10.0,
        end_s=20.0,
        end_reason=PlaneLandingEndReason.GPS_STOP,
        mode_number=PlaneLandingAttemptDetector.AUTO_MODE_NUMBER,
    )

    distance = PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt)

    assert distance is not None
    assert (distance.aircraft_position_time_s, distance.aircraft_longitude_deg) == (19.0, 1.001)


def test_target_distance_without_in_scope_gps_position_remains_unavailable() -> None:
    log_data = _gps_stop_log(((1.0, 1, 0, 21, 0.0, 1.0),))
    _add_columns(
        log_data,
        "GPS",
        ((20.5, 2.0, 0.0, 1.002),),
        [("TimeUS", "f8"), ("Spd", "f8"), ("Lat", "f8"), ("Lng", "f8")],
    )
    attempt = PlaneLandingAttempt(
        flight_segment=FlightSegment(start_s=0.0, end_s=30.0, is_complete=False),
        start_s=10.0,
        end_s=20.0,
        end_reason=PlaneLandingEndReason.GPS_STOP,
        mode_number=PlaneLandingAttemptDetector.AUTO_MODE_NUMBER,
    )

    assert PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt) is None


@pytest.mark.parametrize(
    ("end_reason", "target_time_s", "expected_time_s"),
    [
        (PlaneLandingEndReason.GPS_STOP, 20.0, 20.0),
        (PlaneLandingEndReason.STAGE_RESTART, 20.0, 19.0),
        (PlaneLandingEndReason.GPS_STOP, 18.0, 17.0),
    ],
    ids=("inclusive-endpoint", "stage-restart-exclusive-endpoint", "tie-first-wins"),
)
def test_nearest_gps_position_preserves_attempt_endpoint_and_tie_semantics(
    end_reason: PlaneLandingEndReason,
    target_time_s: float,
    expected_time_s: float,
) -> None:
    log_data = _plane_log()
    _add_columns(
        log_data,
        "GPS",
        ((17.0, 2.0, 0.0, 1.001), (19.0, 2.0, 0.0, 1.002), (20.0, 2.0, 0.0, 1.003)),
        [("TimeUS", "f8"), ("Spd", "f8"), ("Lat", "f8"), ("Lng", "f8")],
    )
    attempt = PlaneLandingAttempt(
        flight_segment=FlightSegment(start_s=0.0, end_s=30.0, is_complete=False),
        start_s=10.0,
        end_s=20.0,
        end_reason=end_reason,
        mode_number=PlaneLandingAttemptDetector.AUTO_MODE_NUMBER,
    )

    position = PlaneLandingMissionTargetExtractor._nearest_gps_position(  # pylint: disable=protected-access
        log_data,
        attempt,
        target_time_s,
    )

    assert position is not None
    assert position[0] == expected_time_s


def test_missing_optional_arsp_and_rfnd_omits_only_their_measurements() -> None:
    log_data = _plane_log(
        land=((5.0, 0, 0.0), (10.0, 1, 20.0), (15.0, 2, 5.5), (20.0, 3, 1.2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, ParameterHistory())
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    assert _availability(log_data).available is True
    assert len(evidence) == 2
    assert all(item.airspeed_m_s is None for item in evidence)
    assert all(item.barometric_altitude_m is not None for item in evidence)
    assert all(item.rangefinder_distance_m is None for item in evidence)
    assert not any("ARSP airspeed" in outcome.message for outcome in result.outcomes)
    assert any("BARO altitude" in outcome.message for outcome in result.outcomes)
    assert not any("RFND distance" in outcome.message for outcome in result.outcomes)


def test_missing_rfnd_omits_lifecycle_evidence_without_affecting_availability() -> None:
    log_data = _plane_log(messages=((40.0, "Throttle disarmed"),))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingRangefinderEvidenceExtractor.extract(log_data, attempt, ParameterHistory())
    result = PlaneLandingAnalysis(log_data, _context()).analyse()

    assert _availability(log_data).available is True
    assert evidence is None
    assert not any(outcome.group == "Attempt 1 — Rangefinder evidence" for outcome in result.outcomes)


def test_rfnd_uses_configured_landing_orientation_instead_of_instance_zero() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 40.0, 0, 0, 4),
            (14.0, 12.0, 1, 25, 4),
            (15.0, 40.0, 0, 0, 4),
            (15.0, 7.0, 1, 25, 4),
            (20.0, 40.0, 0, 0, 4),
            (20.0, 2.0, 1, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND2_MAX": 15.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [7.0, 2.0]
    assert lifecycle is not None
    assert (lifecycle.first_nonzero_time_s, lifecycle.first_nonzero_distance_m) == (14.0, 12.0)
    assert (lifecycle.first_in_range_time_s, lifecycle.first_in_range_distance_m) == (14.0, 12.0)


def test_rfnd_only_nonzero_configured_instance_remains_available() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 12.0, 1, 25, 4), (15.0, 7.0, 1, 25, 4), (20.0, 2.0, 1, 25, 4)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND2_MAX": 15.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [7.0, 2.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 12.0


def test_rfnd_selection_follows_nondefault_configured_orientation() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 4),
            (14.0, 8.0, 1, 0, 4),
            (15.0, 7.0, 0, 25, 4),
            (15.0, 4.0, 1, 0, 4),
            (20.0, 2.0, 0, 25, 4),
            (20.0, 1.0, 1, 0, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 0.0, "RNGFND2_MAX": 10.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [4.0, 1.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 8.0


def test_rfnd_selection_uses_landing_orientation_at_each_sample_time() -> None:
    history = ParameterHistory(
        {"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0},
        {"RNGFND_LND_ORNT": (ParameterChange(time_s=20.0, value=0.0),)},
    )
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 0, 4),
            (14.0, 8.0, 1, 25, 4),
            (15.0, 6.0, 0, 0, 4),
            (15.0, 4.0, 1, 25, 4),
            (20.0, 2.0, 0, 0, 4),
            (20.0, 1.0, 1, 25, 4),
        ),
        history,
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [4.0, 2.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 8.0


def test_rfnd_orient_schema_without_historical_landing_orientation_is_unavailable() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 8.0, 0, 25, 4), (15.0, 4.0, 0, 25, 4), (20.0, 1.0, 0, 25, 4)),
        ParameterHistory({"RNGFND1_MAX": 10.0}),
    )

    assert all(item.rangefinder_distance_m is None for item in stage_evidence)
    assert lifecycle is None


def test_rfnd_multiple_matching_instances_emulate_firmware_good_preference() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 3),
            (14.0, 8.0, 1, 25, 4),
            (15.0, 7.0, 0, 25, 3),
            (15.0, 4.0, 1, 25, 4),
            (20.0, 2.0, 0, 25, 4),
            (20.0, 1.0, 1, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [4.0, 2.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 8.0


def test_rfnd_logical_frame_allows_distinct_instance_timestamps() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 3),
            (14.000001, 8.0, 1, 25, 4),
            (15.0, 7.0, 0, 25, 3),
            (15.000001, 4.0, 1, 25, 4),
            (20.0, 2.0, 0, 25, 3),
            (20.000001, 1.0, 1, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [4.0, 1.0]
    assert lifecycle is not None
    assert (lifecycle.first_nonzero_time_s, lifecycle.first_nonzero_distance_m) == (14.000001, 8.0)


def test_rfnd_prestart_orientation_state_prevents_leading_partial_frame_selection() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.999999, 12.0, 0, 25, 4),
            (15.000001, 3.0, 1, 25, 4),
            (16.0, 8.0, 0, 25, 4),
            (16.000001, 4.0, 1, 25, 3),
            (17.0, 8.0, 0, 25, 4),
            (17.000001, 4.0, 1, 25, 3),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
        attempt_bounds=(15.0, 40.0, PlaneLandingEndReason.DISARM),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [8.0, 8.0]
    assert lifecycle is not None
    assert (lifecycle.first_nonzero_time_s, lifecycle.first_nonzero_distance_m) == (16.0, 8.0)


def test_rfnd_prestart_state_never_becomes_attempt_observation() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 4),
            (14.999999, 11.0, 0, 25, 4),
            (15.000001, 3.0, 1, 25, 4),
            (16.0, 8.0, 0, 25, 4),
            (16.000001, 4.0, 1, 25, 3),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
        attempt_bounds=(15.0, 40.0, PlaneLandingEndReason.DISARM),
    )

    assert lifecycle is not None
    assert (lifecycle.first_nonzero_time_s, lifecycle.first_nonzero_distance_m) == (16.0, 8.0)


def test_rfnd_removing_latest_prestart_row_still_degrades_leading_partial_frame() -> None:
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0})
    records = (
        (14.0, 12.0, 0, 25, 4),
        (14.999999, 11.0, 0, 25, 4),
        (15.000001, 3.0, 1, 25, 4),
        (16.0, 8.0, 0, 25, 4),
        (16.000001, 4.0, 1, 25, 3),
    )
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        records[:1] + records[2:],
        history,
        attempt_bounds=(15.0, 40.0, PlaneLandingEndReason.DISARM),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [8.0, 8.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_time_s == 16.0


def test_rfnd_multiple_matching_instances_use_lowest_instance_when_none_is_good() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 3),
            (14.0, 8.0, 1, 25, 2),
            (15.0, 7.0, 0, 25, 3),
            (15.0, 4.0, 1, 25, 2),
            (20.0, 2.0, 0, 25, 3),
            (20.0, 1.0, 1, 25, 2),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 15.0, "RNGFND2_MAX": 15.0}),
    )

    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 12.0
    assert lifecycle.first_in_range_time_s is None


def test_rfnd_incomplete_middle_frame_does_not_erase_valid_frames() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 4),
            (14.0, 8.0, 1, 25, 4),
            (15.0, 7.0, 0, 25, 4),
            (20.0, 2.0, 0, 25, 4),
            (20.0, 1.0, 1, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [12.0, 2.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 12.0


def test_rfnd_nonmatching_middle_frame_degrades_locally() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 8.0, 0, 25, 4),
            (15.0, 40.0, 0, 0, 4),
            (20.0, 2.0, 0, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [8.0, 2.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_time_s == 14.0


def test_rfnd_unusable_middle_frame_breaks_continuity_without_disengagement() -> None:
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0})
    records = (
        (10.0, 5.0, 0, 25, 4),
        (10.25, 5.0, 0, 25, 4),
        (10.5, 40.0, 0, 0, 4),
        (10.75, 5.0, 0, 25, 4),
        (11.0, 5.0, 0, 25, 4),
    )
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(records, history)
    stage_without_break, lifecycle_without_break = _oriented_rangefinder_evidence(
        records[:2] + records[3:],
        history,
    )

    assert stage_evidence == stage_without_break
    assert lifecycle is not None
    assert lifecycle.continuous_time_s is None
    assert lifecycle.continuous_samples is None
    assert lifecycle.disengagement_count == 0
    assert lifecycle.last_disengagement_time_s is None
    assert lifecycle_without_break is not None
    assert (lifecycle_without_break.continuous_time_s, lifecycle_without_break.continuous_samples) == (10.0, 4)


def test_rfnd_break_markers_do_not_reduce_observation_sample_rate_requirement() -> None:
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0})
    selected_records = (
        (10.0, 5.0, 0, 25, 4),
        (10.125, 5.0, 0, 25, 4),
        (10.25, 5.0, 0, 25, 4),
    )
    records_with_breaks = (
        *selected_records,
        (11.25, 40.0, 0, 0, 4),
        (12.25, 40.0, 0, 0, 4),
        (13.25, 40.0, 0, 0, 4),
    )

    _stages, lifecycle = _oriented_rangefinder_evidence(records_with_breaks, history)
    _stages_without_breaks, lifecycle_without_breaks = _oriented_rangefinder_evidence(selected_records, history)

    assert lifecycle is not None
    assert lifecycle_without_breaks is not None
    assert (lifecycle.continuous_time_s, lifecycle.continuous_samples) == (None, None)
    assert (lifecycle_without_breaks.continuous_time_s, lifecycle_without_breaks.continuous_samples) == (None, None)
    assert (
        PlaneLandingRangefinderEvidenceExtractor._required_continuous_samples(  # pylint: disable=protected-access
            tuple(record[0] for record in selected_records)
        )
        == 8
    )


def test_rfnd_incomplete_middle_frame_breaks_acquisition_continuity() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (10.0, 5.0, 0, 25, 4),
            (10.000001, 4.0, 1, 25, 3),
            (10.25, 5.0, 0, 25, 4),
            (10.250001, 4.0, 1, 25, 3),
            (10.5, 5.0, 0, 25, 4),
            (10.75, 5.0, 0, 25, 4),
            (10.750001, 4.0, 1, 25, 3),
            (11.0, 5.0, 0, 25, 4),
            (11.000001, 4.0, 1, 25, 3),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
    )

    assert lifecycle is not None
    assert lifecycle.continuous_time_s is None
    assert lifecycle.continuous_samples is None
    assert lifecycle.disengagement_count == 0


def test_rfnd_future_matching_instance_does_not_invalidate_earlier_attempt() -> None:
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0})
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((20.0, 2.0, 0, 25, 4), (41.0, 1.0, 1, 25, 4)),
        history,
    )
    stage_without_future, lifecycle_without_future = _oriented_rangefinder_evidence(
        ((20.0, 2.0, 0, 25, 4),),
        history,
    )

    assert [(item.rangefinder_distance_m, item.rangefinder_status) for item in stage_evidence] == [
        (2.0, 4),
        (2.0, 4),
    ]
    assert stage_evidence == stage_without_future
    assert lifecycle is not None
    assert lifecycle == lifecycle_without_future


def test_rfnd_frame_straddling_attempt_end_uses_only_owned_prefix() -> None:
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0})
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((39.999999, 2.0, 0, 25, 3), (40.000001, 1.0, 1, 25, 4)),
        history,
    )

    assert [(item.rangefinder_distance_m, item.rangefinder_status) for item in stage_evidence] == [
        (2.0, 3),
        (2.0, 3),
    ]
    assert lifecycle is not None
    assert (lifecycle.first_nonzero_time_s, lifecycle.first_nonzero_distance_m) == (39.999999, 2.0)


def test_rfnd_stage_restart_endpoint_is_exclusive_before_frame_selection() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((19.999999, 5.0, 0, 25, 3), (20.0, 1.0, 1, 25, 4)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
        attempt_bounds=(10.0, 20.0, PlaneLandingEndReason.STAGE_RESTART),
    )

    assert [(item.rangefinder_distance_m, item.rangefinder_status) for item in stage_evidence] == [(5.0, 3)]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 5.0


def test_rfnd_incomplete_owned_frame_prefix_degrades_only_that_frame() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 8.0, 0, 25, 4),
            (14.000001, 7.0, 1, 25, 3),
            (19.999999, 2.0, 0, 25, 4),
            (20.000001, 1.0, 1, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
        attempt_bounds=(10.0, 20.0, PlaneLandingEndReason.DISARM),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [8.0, 8.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_distance_m == 8.0


def test_rfnd_logical_frame_has_no_invented_numeric_time_bound() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((20.0, 2.0, 0, 25, 3), (21.0, 1.0, 1, 25, 4)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [1.0, 1.0]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_time_s == 21.0


def test_rfnd_repeated_instance_starts_new_logical_frame() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 4),
            (14.000001, 8.0, 1, 25, 4),
            (15.0, 7.0, 0, 25, 4),
            (15.0, 6.0, 0, 25, 4),
            (15.000001, 4.0, 1, 25, 4),
            (20.0, 2.0, 0, 25, 4),
            (20.000001, 1.0, 1, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [6.0, 2.0]
    assert lifecycle is not None


def test_rfnd_duplicate_middle_frame_breaks_acquisition_continuity() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (10.0, 5.0, 0, 25, 4),
            (10.000001, 4.0, 1, 25, 3),
            (10.25, 5.0, 0, 25, 4),
            (10.250001, 4.0, 1, 25, 3),
            (10.5, 5.0, 0, 25, 4),
            (10.5, 4.5, 0, 25, 4),
            (10.500001, 4.0, 1, 25, 3),
            (10.75, 5.0, 0, 25, 4),
            (10.750001, 4.0, 1, 25, 3),
            (11.0, 5.0, 0, 25, 4),
            (11.000001, 4.0, 1, 25, 3),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
    )

    assert lifecycle is not None
    assert lifecycle.continuous_time_s is None
    assert lifecycle.continuous_samples is None
    assert lifecycle.disengagement_count == 0


def test_rfnd_malformed_middle_frame_degrades_locally() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (14.0, 12.0, 0, 25, 4),
            (14.000001, 8.0, 1, 25, 4),
            (15.0, 7.0, 0, 25, 4),
            (15.000001, 4.0, 1, 25, "bad"),
            (20.0, 2.0, 0, 25, 4),
            (20.000001, 1.0, 1, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0, "RNGFND2_MAX": 10.0}),
        dtype=[("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "O"), ("Orient", "O"), ("Stat", "O")],
    )

    assert [item.rangefinder_distance_m for item in stage_evidence] == [12.0, 2.0]
    assert lifecycle is not None


def test_analysis_prepares_rfnd_once_and_reuses_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 3), (20.0, 0), (30.0, 1), (35.0, 3)),
        messages=((18.0, "Landing aborted"), (45.0, "Throttle disarmed")),
    )
    _add_columns(
        log_data,
        "RFND",
        ((14.0, 5.0, 0, 25, 4), (34.0, 3.0, 0, 25, 4)),
        [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1"), ("Orient", "u1"), ("Stat", "u1")],
    )
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0})
    selector = data_model_plane_landing._PlaneLandingRangefinderSelector  # pylint: disable=protected-access
    original_prepare = selector.prepare
    prepare_calls = 0

    def counted_prepare(cls: type[object], prepared_log: LogData) -> object:
        nonlocal prepare_calls
        prepare_calls += 1
        del cls
        return original_prepare(prepared_log)

    monkeypatch.setattr(selector, "prepare", classmethod(counted_prepare))

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    assert result.available is True
    assert prepare_calls == 1


@pytest.mark.parametrize(
    ("status", "has_current_observation", "has_acquisition", "has_in_range"),
    [
        (0, False, False, False),
        (1, False, False, False),
        (2, True, True, False),
        (3, True, True, False),
        (4, True, True, True),
    ],
)
def test_rfnd_status_separates_current_observation_and_usable_range(
    status: int,
    has_current_observation: bool,
    has_acquisition: bool,
    has_in_range: bool,
) -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 5.0, 0, 25, status), (15.0, 4.0, 0, 25, status), (20.0, 2.0, 0, 25, status)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0}),
    )

    assert lifecycle is not None
    assert (lifecycle.first_nonzero_time_s is not None) is has_acquisition
    assert (lifecycle.first_in_range_time_s is not None) is has_in_range
    assert [item.rangefinder_distance_m is not None for item in stage_evidence] == [
        has_current_observation,
        has_current_observation,
    ]
    assert [item.rangefinder_status for item in stage_evidence] == [status, status]


def test_rfnd_out_of_range_low_zero_is_current_observation_not_acquisition() -> None:
    stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 0.0, 0, 25, 2), (15.0, 0.0, 0, 25, 2), (20.0, 0.0, 0, 25, 2)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0}),
    )

    assert [(item.rangefinder_distance_m, item.rangefinder_status) for item in stage_evidence] == [(0.0, 2), (0.0, 2)]
    assert lifecycle is not None
    assert lifecycle.first_nonzero_time_s is None
    assert lifecycle.first_in_range_time_s is None


@pytest.mark.parametrize(
    ("status", "status_name", "distance_is_present", "usability_text"),
    [
        (0, "NotConnected", False, "no current range measurement"),
        (1, "NoData", False, "no current range measurement"),
        (2, "OutOfRangeLow", True, "not usable as Plane landing-height evidence"),
        (3, "OutOfRangeHigh", True, "not usable as Plane landing-height evidence"),
        (4, "Good", True, None),
    ],
)
def test_rfnd_stage_flat_output_reports_observation_status_and_usability(
    status: int,
    status_name: str,
    distance_is_present: bool,
    usability_text: str | None,
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "RFND",
        ((14.0, 5.0, 0, 25, status), (15.0, 4.0, 0, 25, status), (20.0, 2.0, 0, 25, status)),
        [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1"), ("Orient", "u1"), ("Stat", "u1")],
    )
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0})

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    stage_messages = [outcome.message for outcome in result.outcomes if outcome.group == "Attempt 1 — Preflare"]
    assert any(f"RFND status {status_name} ({status})" in message for message in stage_messages) is (status != 4)
    if usability_text is not None:
        assert any(usability_text in message for message in stage_messages)
    assert any("RFND distance" in message for message in stage_messages) is distance_is_present


def test_unknown_rfnd_status_is_reported_numerically_without_current_distance() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "RFND",
        ((15.0, 4.0, 0, 25, 5),),
        [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1"), ("Orient", "u1"), ("Stat", "u1")],
    )
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0})

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    stage_messages = [outcome.message for outcome in result.outcomes if outcome.group == "Attempt 1 — Preflare"]
    assert "RFND status 5" in stage_messages
    assert not any("RFND distance" in message for message in stage_messages)


def test_rfnd_good_nodata_good_breaks_acquisition_without_using_retained_distance() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 5.0, 0, 25, 4), (15.0, 5.0, 0, 25, 1), (20.0, 2.0, 0, 25, 4)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0}),
    )

    assert lifecycle is not None
    assert lifecycle.disengagement_count == 1
    assert lifecycle.last_disengagement_time_s == 15.0
    assert lifecycle.last_disengagement_distance_m is None
    assert lifecycle.last_disengagement_status == 1
    assert lifecycle.continuous_time_s is None
    assert lifecycle.continuous_samples is None


def test_rfnd_nodata_resets_multi_sample_continuous_acquisition() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        (
            (10.0, 5.0, 0, 25, 4),
            (10.25, 5.0, 0, 25, 4),
            (10.5, 5.0, 0, 25, 4),
            (10.75, 5.0, 0, 25, 1),
            (11.0, 5.0, 0, 25, 4),
            (11.25, 5.0, 0, 25, 4),
            (11.5, 5.0, 0, 25, 4),
        ),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0}),
    )

    assert lifecycle is not None
    assert lifecycle.continuous_time_s is None
    assert lifecycle.continuous_samples is None
    assert lifecycle.last_disengagement_status == 1


@pytest.mark.parametrize(("status", "status_name"), [(0, "NotConnected"), (1, "NoData")])
def test_rfnd_no_current_data_disengagement_flat_output_preserves_status_without_distance(
    status: int,
    status_name: str,
) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "RFND",
        ((14.0, 5.0, 0, 25, 4), (16.0, 5.0, 0, 25, status), (20.0, 2.0, 0, 25, 4)),
        [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1"), ("Orient", "u1"), ("Stat", "u1")],
    )
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0})

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()
    lifecycle_messages = [outcome for outcome in result.outcomes if outcome.group == "Attempt 1 — Rangefinder evidence"]

    status_outcome = next(outcome for outcome in lifecycle_messages if "disengagement status" in outcome.message.lower())
    assert status_name in status_outcome.message
    assert "distance unavailable" in status_outcome.message
    assert (status_outcome.timestamp_us, status_outcome.value) == (16_000_000, float(status))
    assert not any("disengagement distance" in outcome.message.lower() for outcome in lifecycle_messages)


def test_rfnd_good_status_is_reported_when_distance_is_unavailable() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "RFND",
        ((15.0, float("nan"), 0, 25, 4),),
        [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1"), ("Orient", "u1"), ("Stat", "u1")],
    )
    history = ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0})

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    assert any("RFND status Good (4) — distance unavailable" in outcome.message for outcome in result.outcomes)
    assert not any("RFND distance" in outcome.message for outcome in result.outcomes)


def test_rfnd_nodata_retained_distance_is_not_stage_point_evidence() -> None:
    stage_evidence, _lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 7.5, 0, 25, 1), (15.0, 7.5, 0, 25, 1), (20.0, 7.5, 0, 25, 1)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 10.0}),
    )

    assert all(item.rangefinder_distance_m is None for item in stage_evidence)
    assert [item.rangefinder_status for item in stage_evidence] == [1, 1]


def test_rfnd_instance_nine_uses_rngfnda_max() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 8.0, 9, 25, 4), (15.0, 6.0, 9, 25, 4), (20.0, 2.0, 9, 25, 4)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFNDA_MAX": 7.0}),
    )

    assert lifecycle is not None
    assert (lifecycle.first_in_range_time_s, lifecycle.first_in_range_distance_m) == (15.0, 6.0)


def test_rfnd_selected_nonzero_instance_does_not_use_rngfnd1_max() -> None:
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 8.0, 1, 25, 4), (15.0, 6.0, 1, 25, 4), (20.0, 2.0, 1, 25, 4)),
        ParameterHistory({"RNGFND_LND_ORNT": 25.0, "RNGFND1_MAX": 100.0, "RNGFND2_MAX": 5.0}),
    )

    assert lifecycle is not None
    assert (lifecycle.first_in_range_time_s, lifecycle.first_in_range_distance_m) == (20.0, 2.0)


def test_rfnd_selected_instance_uses_event_time_max_change() -> None:
    history = ParameterHistory(
        {"RNGFND_LND_ORNT": 25.0, "RNGFND2_MAX": 5.0},
        {"RNGFND2_MAX": (ParameterChange(time_s=15.0, value=7.0),)},
    )
    _stage_evidence, lifecycle = _oriented_rangefinder_evidence(
        ((14.0, 8.0, 1, 25, 4), (15.0, 6.0, 1, 25, 4), (20.0, 2.0, 1, 25, 4)),
        history,
    )

    assert lifecycle is not None
    assert (lifecycle.first_in_range_time_s, lifecycle.first_in_range_distance_m) == (15.0, 6.0)


def test_rfnd_active_threshold_and_first_active_sample() -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(((10.0, 0.05), (11.0, 0.051), (12.0, 0.0)))

    assert evidence is not None
    assert (evidence.first_nonzero_time_s, evidence.first_nonzero_distance_m) == (11.0, 0.05)
    assert evidence.continuous_time_s is None
    assert evidence.continuous_samples is None
    assert evidence.disengagement_count == 1
    assert (evidence.last_disengagement_time_s, evidence.last_disengagement_distance_m) == (12.0, 0.0)


def test_rfnd_first_in_range_uses_parameter_value_at_each_sample_time() -> None:
    history = ParameterHistory(
        {"RNGFND1_MAX": 5.0},
        {"RNGFND1_MAX": (ParameterChange(time_s=12.0, value=7.0),)},
    )
    _log_data, _attempt, evidence = _rangefinder_evidence(
        ((10.0, 8.0), (11.0, 6.0), (12.0, 6.0)),
        history,
    )

    assert evidence is not None
    assert (evidence.first_nonzero_time_s, evidence.first_nonzero_distance_m) == (10.0, 8.0)
    assert (evidence.first_in_range_time_s, evidence.first_in_range_distance_m) == (12.0, 6.0)


def test_rfnd_median_sample_rate_and_exact_continuous_threshold() -> None:
    assert (
        PlaneLandingRangefinderEvidenceExtractor._required_continuous_samples(  # pylint: disable=protected-access
            (10.0, 10.2, 10.4, 11.4)
        )
        == 5
    )
    _log_data, _attempt, evidence = _rangefinder_evidence(((10.0, 1.0), (10.2, 1.0), (10.4, 1.0), (10.6, 1.0), (10.8, 1.0)))

    assert evidence is not None
    assert (evidence.continuous_time_s, evidence.continuous_samples) == (10.0, 5)


@pytest.mark.parametrize(
    "records",
    [
        ((10.0, 1.0),),
        ((10.0, 1.0), (10.0, 1.0)),
        ((10.0, 1.0), (30.0, 1.0)),
    ],
    ids=("one-sample", "duplicate-timestamps", "twenty-second-gap"),
)
def test_rfnd_sparse_or_unusable_cadence_does_not_establish_continuity(
    records: Sequence[tuple[float, float]],
) -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(records)

    assert evidence is not None
    assert evidence.continuous_time_s is None
    assert evidence.continuous_samples is None


@pytest.mark.parametrize(
    ("records", "expected_samples"),
    [
        (tuple((10.0 + index * 0.25, 1.0) for index in range(4)), 4),
        (tuple((10.0 + index * 0.02, 1.0) for index in range(50)), 50),
    ],
    ids=("four-hertz", "fifty-hertz"),
)
def test_rfnd_normal_cadence_still_establishes_continuity(
    records: Sequence[tuple[float, float]],
    expected_samples: int,
) -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(records)

    assert evidence is not None
    assert (evidence.continuous_time_s, evidence.continuous_samples) == (10.0, expected_samples)


@pytest.mark.parametrize(
    "records",
    [
        (*tuple((10.0 + index * 0.25, 1.0) for index in range(8)), (11.75, 1.0)),
        (*tuple((10.0 + index * 0.25, 1.0) for index in range(8)), (30.0, 1.0), (30.0, 1.0)),
    ],
    ids=("isolated-duplicate", "later-duplicate-pair"),
)
def test_rfnd_duplicate_timestamp_does_not_erase_valid_cadence(
    records: Sequence[tuple[float, float]],
) -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(records)

    assert evidence is not None
    assert (evidence.continuous_time_s, evidence.continuous_samples) == (10.0, 4)


@pytest.mark.parametrize(
    "timestamps_s",
    [
        (10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.25),
        (10.0, 10.0, 10.0, 10.25),
        (10.0, 12.0, 14.0, 16.0, 16.0),
    ],
    ids=("seven-duplicates", "three-duplicates", "sparse-trailing-duplicate"),
)
def test_rfnd_duplicate_timestamps_do_not_count_as_distinct_continuity_samples(
    timestamps_s: Sequence[float],
) -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(tuple((timestamp_s, 1.0) for timestamp_s in timestamps_s))

    assert evidence is not None
    assert evidence.continuous_time_s is None
    assert evidence.continuous_samples is None


def test_rfnd_sparse_old_observation_does_not_block_later_dense_qualifying_run() -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(((10.0, 1.0), (20.0, 1.0), (20.25, 1.0), (20.5, 1.0), (20.75, 1.0)))

    assert evidence is not None
    assert (evidence.continuous_time_s, evidence.continuous_samples) == (20.0, 4)


def test_rfnd_interrupted_run_resets_continuity_and_tracks_multiple_disengagements() -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(
        (
            (10.0, 1.0),
            (10.25, 1.0),
            (10.5, 0.0),
            (10.75, 2.0),
            (11.0, 2.0),
            (11.25, 2.0),
            (11.5, 2.0),
            (11.75, 0.04),
        )
    )

    assert evidence is not None
    assert (evidence.continuous_time_s, evidence.continuous_samples) == (10.75, 4)
    assert evidence.disengagement_count == 2
    assert (evidence.last_disengagement_time_s, evidence.last_disengagement_distance_m) == (11.75, 0.04)


def test_rfnd_active_run_without_inactive_sample_has_no_disengagement() -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(((10.0, 1.0), (11.0, 1.0)))

    assert evidence is not None
    assert evidence.disengagement_count == 0
    assert evidence.last_disengagement_time_s is None
    assert evidence.last_disengagement_distance_m is None


def test_rfnd_lifecycle_is_restricted_to_attempt_and_does_not_change_boundaries() -> None:
    log_data = _plane_log(messages=((40.0, "Throttle disarmed"),))
    _add_columns(
        log_data,
        "RFND",
        ((9.0, 9.0), (10.0, 1.0), (39.0, 1.0), (41.0, 0.0)),
        [("TimeUS", "f8"), ("Dist", "f8")],
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    boundaries_before = PlaneLandingAttemptDetector.detect(log_data, segment)

    evidence = PlaneLandingRangefinderEvidenceExtractor.extract(log_data, boundaries_before[0], ParameterHistory())
    boundaries_after = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert evidence is not None
    assert (evidence.first_nonzero_time_s, evidence.first_nonzero_distance_m) == (10.0, 1.0)
    assert evidence.disengagement_count == 0
    assert boundaries_after == boundaries_before


def test_non_finite_and_malformed_rfnd_values_are_conservatively_invalid() -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(
        ((10.0, "bad"), ("bad", 9.0), (11.0, 1.0), (12.0, float("nan")), (float("inf"), 0.0)),
        dtype=[("TimeUS", "O"), ("Dist", "O")],
    )

    assert evidence is not None
    assert (evidence.first_nonzero_time_s, evidence.first_nonzero_distance_m) == (11.0, 1.0)
    assert evidence.disengagement_count == 1
    assert evidence.last_disengagement_time_s == 12.0
    assert evidence.last_disengagement_distance_m is None


def test_rfnd_lifecycle_flat_outcomes_leave_stage_point_measurement_unchanged() -> None:
    log_data = _plane_log(
        land=((5.0, 0, 0.0), (10.0, 1, 20.0), (15.0, 2, 5.5), (20.0, 3, 1.2)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "RFND",
        ((14.7, 6.0), (15.0, 5.5), (20.2, 1.5), (21.0, 0.0)),
        [("TimeUS", "f8"), ("Dist", "f8")],
    )
    history = ParameterHistory({"RNGFND1_MAX": 5.5})
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    stage_evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, history)
    lifecycle_evidence = PlaneLandingRangefinderEvidenceExtractor.extract(log_data, attempt, history)
    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    preflare, flare = stage_evidence
    assert (preflare.rangefinder_distance_m, flare.rangefinder_distance_m) == (5.5, 1.5)
    assert lifecycle_evidence is not None
    assert (lifecycle_evidence.first_nonzero_time_s, lifecycle_evidence.first_nonzero_distance_m) == (14.7, 6.0)
    assert (lifecycle_evidence.first_in_range_time_s, lifecycle_evidence.first_in_range_distance_m) == (15.0, 5.5)
    lifecycle_outcomes = [outcome for outcome in result.outcomes if outcome.group == "Attempt 1 — Rangefinder evidence"]
    assert {outcome.group for outcome in lifecycle_outcomes} == {"Attempt 1 — Rangefinder evidence"}
    assert [(outcome.timestamp_us, outcome.value) for outcome in lifecycle_outcomes] == [
        (14_700_000, 6.0),
        (15_000_000, 5.5),
        (14_700_000, 2.0),
        (21_000_000, 0.0),
        (40_000_000, 1.0),
    ]
    assert any(outcome.message == "Continuous acquisition sample count: 2" for outcome in lifecycle_outcomes)
    assert lifecycle_outcomes[-1].message == "Disengagement count: 1"


def test_rfnd_lifecycle_and_stage_distance_use_only_instance_zero() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    _add_columns(
        log_data,
        "RFND",
        (
            (14.7, 0.0, 1),
            (14.7, 6.0, 0),
            (15.0, 0.0, 1),
            (15.0, 5.5, 0),
            (20.2, 0.0, 1),
            (20.2, 1.5, 0),
            (21.0, 0.0, 1),
            (21.0, 1.0, 0),
        ),
        [("TimeUS", "f8"), ("Dist", "f8"), ("Instance", "u1")],
    )
    history = ParameterHistory({"RNGFND1_MAX": 10.0})
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    stage_evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, history)
    lifecycle_evidence = PlaneLandingRangefinderEvidenceExtractor.extract(log_data, attempt, history)

    assert [item.rangefinder_distance_m for item in stage_evidence] == [5.5, 1.5]
    assert lifecycle_evidence is not None
    assert (lifecycle_evidence.first_nonzero_time_s, lifecycle_evidence.first_nonzero_distance_m) == (14.7, 6.0)
    assert lifecycle_evidence.disengagement_count == 0
    assert lifecycle_evidence.last_disengagement_time_s is None


@pytest.mark.parametrize("non_finite_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_event_time_landing_parameters_are_unavailable(non_finite_value: float) -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    parameter_names = ("LAND_PF_ALT", "LAND_PF_SEC", "LAND_FLARE_ALT", "LAND_FLARE_SEC", "LAND_PITCH_DEG")
    history = ParameterHistory(dict.fromkeys(parameter_names, non_finite_value))
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    evidence = PlaneLandingEvidenceExtractor.extract(log_data, attempt, history)
    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    assert all(value is None for item in evidence for value in item.parameter_values.values())
    attempt_outcome = next(outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing:"))
    assert attempt_outcome.value is None
    assert "LAND_FLARE_ALT at start: unavailable" in attempt_outcome.message
    assert not any(
        parameter_name in outcome.message and "effective value" in outcome.message
        for parameter_name in parameter_names
        for outcome in result.outcomes
    )


def test_finite_event_time_landing_parameters_are_emitted() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    parameter_values = {
        "LAND_PF_ALT": 6.0,
        "LAND_PF_SEC": 2.0,
        "LAND_FLARE_ALT": 3.0,
        "LAND_FLARE_SEC": 1.5,
        "LAND_PITCH_DEG": 4.0,
    }

    result = PlaneLandingAnalysis(log_data, _context(ParameterHistory(parameter_values))).analyse()

    attempt_outcome = next(outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing:"))
    assert attempt_outcome.value == 3.0
    parameter_outcomes = [outcome for outcome in result.outcomes if "effective value" in outcome.message]
    emitted_parameter_names = {
        parameter_name
        for parameter_name in parameter_values
        if any(parameter_name in item.message for item in parameter_outcomes)
    }
    assert emitted_parameter_names == set(parameter_values)


def test_finite_parameter_change_at_event_time_remains_effective() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=((40.0, "Throttle disarmed"),),
    )
    history = ParameterHistory(
        {"LAND_PF_ALT": 5.0, "LAND_FLARE_ALT": 3.0},
        {
            "LAND_PF_ALT": (ParameterChange(time_s=15.0, value=6.0),),
            "LAND_FLARE_ALT": (ParameterChange(time_s=20.0, value=4.0),),
        },
    )

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()

    attempt_outcome = next(outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing:"))
    assert attempt_outcome.value == 3.0
    parameter_outcomes = [outcome for outcome in result.outcomes if "effective value" in outcome.message]
    assert [(outcome.timestamp_us, outcome.value) for outcome in parameter_outcomes] == [
        (15_000_000, 6.0),
        (20_000_000, 4.0),
    ]


def test_event_time_parameters_change_between_attempts_without_changing_boundaries() -> None:
    log_data = _plane_log(
        land=(
            (5.0, 0, 0.0),
            (10.0, 1, 20.0),
            (15.0, 2, 5.0),
            (18.0, 3, 2.0),
            (21.0, 0, 0.0),
            (30.0, 1, 20.0),
            (35.0, 2, 6.0),
            (38.0, 3, 2.5),
        ),
        messages=((20.0, "Landing aborted"), (50.0, "Throttle disarmed")),
    )
    history = ParameterHistory(
        {"LAND_FLARE_ALT": 2.0},
        {"LAND_FLARE_ALT": (ParameterChange(time_s=38.0, value=4.0),)},
    )
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]
    boundaries_before = PlaneLandingAttemptDetector.detect(log_data, segment)

    result = PlaneLandingAnalysis(log_data, _context(history)).analyse()
    boundaries_after = PlaneLandingAttemptDetector.detect(log_data, segment)

    assert boundaries_after == boundaries_before
    assert [(attempt.start_s, attempt.end_s, attempt.end_reason) for attempt in boundaries_after] == [
        (10.0, 20.0, PlaneLandingEndReason.ABORT),
        (30.0, 50.0, PlaneLandingEndReason.DISARM),
    ]
    flare_parameter_outcomes = [outcome for outcome in result.outcomes if "LAND_FLARE_ALT effective value" in outcome.message]
    assert [outcome.timestamp_us for outcome in flare_parameter_outcomes] == [18_000_000, 38_000_000]
    assert [outcome.value for outcome in flare_parameter_outcomes] == [2.0, 4.0]
    assert all(outcome.suggested_value is None for outcome in result.outcomes)


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
    assert result.reason == "Detected 2 Plane landing attempt(s)"
    attempt_outcomes = [outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing:")]
    assert [outcome.timestamp_us for outcome in attempt_outcomes] == [10_000_000, 30_000_000]
    assert [outcome.value for outcome in attempt_outcomes] == [2.0, 4.0]
    assert all(outcome.param_name is None for outcome in attempt_outcomes)
    assert all(outcome.suggested_value is None for outcome in result.outcomes)
    assert "landing abort message" in attempt_outcomes[0].message
    assert "throttle disarm message" in attempt_outcomes[1].message


def test_plane_landing_models_are_registered_as_one_subsystem_pair() -> None:
    spec = next(spec for spec in data_model_log_analysis.LOG_ANALYSIS_SUBSYSTEMS if spec.key == "plane_landing")

    assert spec.availability_model is PlaneLandingAvailabilityModel
    assert spec.analysis_model is PlaneLandingAnalysis
