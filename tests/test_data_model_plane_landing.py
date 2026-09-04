# ruff: noqa: INP001

"""
Focused tests for AMC-native ArduPlane landing-attempt analysis.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=too-many-lines

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
    )

    distance = PlaneLandingMissionTargetExtractor.distance_at_gps_stop(log_data, attempt)

    assert distance is not None
    assert (distance.aircraft_latitude_deg, distance.aircraft_longitude_deg) == (0.0, 1.001)
    assert distance.distance_m == pytest.approx(111.1949266)


def test_gps_without_use_flag_retains_existing_stop_behavior() -> None:
    log_data = _plane_log(
        gps=((0.0, 6.0), (2.0, 6.0), (20.0, 2.0), (22.0, 2.0), (30.0, 6.0)),
    )
    gps = log_data.get_message_columns("GPS")
    assert gps is not None
    assert "U" not in (gps.dtype.names or ())
    segment = PlaneFlightSegmentDetector.detect(log_data, {}).segments[0]

    attempt = PlaneLandingAttemptDetector.detect(log_data, segment)[0]

    assert (attempt.end_s, attempt.end_reason) == (20.0, PlaneLandingEndReason.GPS_STOP)


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
    _add_columns(log_data, "ARSP", ((14.8, 12.0), (15.1, 13.0), (19.8, 9.0)), [("TimeUS", "f8"), ("Airspeed", "f8")])
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
        13.0,
        100.0,
        6.0,
    )
    assert preflare.gps_ground_speed_m_s == 7.0
    assert preflare.barometric_sink_rate_m_s == 2.0
    assert preflare.flare_to_gps_stop_s is None
    assert preflare.parameter_values == {"LAND_PF_ALT": 6.0, "LAND_PF_SEC": 2.0}
    assert (flare.time_s, flare.flight_height_m) == (20.0, 1.2)
    assert (flare.airspeed_m_s, flare.barometric_altitude_m, flare.rangefinder_distance_m) == (9.0, 90.0, 1.5)
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
        "LAND stage 2 (preflare) entered",
        "LAND stage 3 (flare) entered",
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
    assert not any(
        label in outcome.message.lower() for outcome in result.outcomes for label in ("good", "poor", "safe", "unsafe")
    )


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


def test_firmware_flare_and_glide_slope_messages_are_separate_from_land_stage() -> None:
    log_data = _plane_log(
        land=((5.0, 0), (10.0, 1), (15.0, 2), (20.0, 3)),
        messages=(
            (10.1, "Landing glide slope 4.7 degrees"),
            (19.9999, "Flare -160.1m sink=1.13 speed=13.5 dist=32.6"),
            (40.0, "Throttle disarmed"),
        ),
    )
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
        airspeed_m_s=13.5,
        distance_to_target_m=32.6,
    )
    assert stage_flare.time_s == 20.0
    assert firmware_flare.time_s != stage_flare.time_s
    firmware_outcomes = [outcome for outcome in result.outcomes if "firmware" in outcome.message.lower()]
    assert [outcome.timestamp_us for outcome in firmware_outcomes] == [10_100_000] + [19_999_900] * 4
    assert [outcome.value for outcome in firmware_outcomes] == [4.7, -160.1, 1.13, 13.5, 32.6]
    assert all(isinstance(outcome, LogAnalysis) for outcome in firmware_outcomes)
    assert all(outcome.param_name is None and outcome.suggested_value is None for outcome in firmware_outcomes)
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
    firmware_distance = [outcome for outcome in result.outcomes if "firmware flare: distance to target" in outcome.message]
    computed_distance = [
        outcome for outcome in result.outcomes if "computed distance to mission LAND target" in outcome.message
    ]
    assert [(outcome.timestamp_us, outcome.value) for outcome in firmware_distance] == [(13_999_900, 32.6)]
    assert len(computed_distance) == 1
    assert (computed_distance[0].timestamp_us, computed_distance[0].value) == pytest.approx((20_000_000, 111.1949266))
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
    assert not any("computed distance to mission LAND target" in outcome.message for outcome in result.outcomes)


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
    assert not any("RFND lifecycle" in outcome.message for outcome in result.outcomes)


def test_rfnd_active_threshold_and_first_active_sample() -> None:
    _log_data, _attempt, evidence = _rangefinder_evidence(((10.0, 0.05), (11.0, 0.051), (12.0, 0.0)))

    assert evidence is not None
    assert (evidence.first_nonzero_time_s, evidence.first_nonzero_distance_m) == (11.0, 0.05)
    assert (evidence.continuous_time_s, evidence.continuous_samples) == (11.0, 1)
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
    lifecycle_outcomes = [outcome for outcome in result.outcomes if "RFND lifecycle" in outcome.message]
    assert [(outcome.timestamp_us, outcome.value) for outcome in lifecycle_outcomes] == [
        (14_700_000, 6.0),
        (15_000_000, 5.5),
        (14_700_000, 1.0),
        (21_000_000, 0.0),
        (40_000_000, 1.0),
    ]


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
    attempt_outcome = next(outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing attempt"))
    assert attempt_outcome.value is None
    assert "LAND_FLARE_ALT was unavailable" in attempt_outcome.message
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

    attempt_outcome = next(outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing attempt"))
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

    attempt_outcome = next(outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing attempt"))
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
    assert result.reason == "Detected 2 AUTO landing attempt(s)"
    attempt_outcomes = [outcome for outcome in result.outcomes if outcome.message.startswith("AUTO landing attempt")]
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
