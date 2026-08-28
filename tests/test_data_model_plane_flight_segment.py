#!/usr/bin/env python3

"""Tests for reusable flight segments and ArduPlane flight segmentation."""

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_flight_segment import FlightSegment, FlightSegmentationResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.data_model_plane_flight_segment import PlaneFlightSegmentDetector


def _gps_log(samples: list[tuple[float, float]], *, scaled_from_microseconds: bool = False) -> LogData:
    log_data = LogData()
    if scaled_from_microseconds:
        columns = np.array(samples, dtype=[("TimeUS", "u8"), ("Spd", "f8")])
        schema = MessageSchema(
            name="GPS",
            msg_type=1,
            length=0,
            format="Qf",
            fields=["TimeUS", "Spd"],
            stored_units=["µs", "m/s"],
            scaled_units=["s", "m/s"],
            multipliers=[1e-6, 1.0],
            multipliers_applied_at_ingest=[False, False],
            records=len(samples),
        )
    else:
        columns = np.array(samples, dtype=[("TimeUS", "f8"), ("Spd", "f8")])
        schema = None
    log_data.add_message_columns("GPS", columns, schema)
    return log_data


def _detect(samples: list[tuple[float, float]], parameters: dict[str, float] | None = None) -> FlightSegmentationResult:
    return PlaneFlightSegmentDetector.detect(_gps_log(samples), parameters or {})


def test_flight_segment_accepts_valid_bounds_and_derives_duration() -> None:
    segment = FlightSegment(start_s=10.0, end_s=15.5, is_complete=True)

    assert segment.duration_s == 5.5


def test_flight_segment_rejects_reversed_bounds() -> None:
    with pytest.raises(ValueError, match="start_s must not be after end_s"):
        FlightSegment(start_s=2.0, end_s=1.0, is_complete=True)


def test_flight_segment_containment_is_inclusive() -> None:
    segment = FlightSegment(start_s=10.0, end_s=20.0, is_complete=True)

    assert segment.contains(10.0, 20.0)
    assert segment.contains(12.0, 18.0)
    assert not segment.contains(9.0, 18.0)
    assert not segment.contains(12.0, 21.0)
    assert not segment.contains(18.0, 12.0)


@pytest.mark.parametrize(
    "result",
    [
        FlightSegmentationResult(available=True),
        FlightSegmentationResult(
            available=True,
            segments=(FlightSegment(start_s=1.0, end_s=2.0, is_complete=True),),
        ),
        FlightSegmentationResult(available=False, reason="GPS messages are unavailable"),
    ],
)
def test_flight_segmentation_result_accepts_consistent_states(result: FlightSegmentationResult) -> None:
    assert isinstance(result, FlightSegmentationResult)


@pytest.mark.parametrize(
    ("available", "segments", "reason", "error"),
    [
        (True, (), "unexpected reason", "must not have an unavailable reason"),
        (
            False,
            (FlightSegment(start_s=1.0, end_s=2.0, is_complete=True),),
            "GPS messages are unavailable",
            "must not contain segments",
        ),
        (False, (), None, "requires a non-empty reason"),
        (False, (), "", "requires a non-empty reason"),
    ],
)
def test_flight_segmentation_result_rejects_contradictory_states(
    available: bool,
    segments: tuple[FlightSegment, ...],
    reason: str | None,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        FlightSegmentationResult(available=available, segments=segments, reason=reason)


def test_one_clear_flight_uses_first_motion_sample_and_last_sample_before_ground_run() -> None:
    result = _detect([(0.0, 0.0), (5.0, 6.0), (7.0, 6.0), (9.0, 6.0), (10.0, 0.0), (40.0, 0.0)])

    assert result.available is True
    assert result.reason is None
    assert result.segments == (FlightSegment(start_s=5.0, end_s=9.0, is_complete=True),)


def test_two_flights_are_detected_after_persistent_ground_separation() -> None:
    result = _detect(
        [
            (0.0, 6.0),
            (2.0, 6.0),
            (3.0, 0.0),
            (33.0, 0.0),
            (40.0, 6.0),
            (42.0, 6.0),
            (43.0, 0.0),
            (73.0, 0.0),
        ]
    )

    assert result.segments == (
        FlightSegment(start_s=0.0, end_s=2.0, is_complete=True),
        FlightSegment(start_s=40.0, end_s=42.0, is_complete=True),
    )


def test_short_low_speed_interval_does_not_split_flight() -> None:
    result = _detect([(0.0, 6.0), (2.0, 6.0), (3.0, 0.0), (20.0, 6.0), (21.0, 0.0), (51.0, 0.0)])

    assert result.segments == (FlightSegment(start_s=0.0, end_s=20.0, is_complete=True),)


def test_motion_run_shorter_than_start_persistence_does_not_create_flight() -> None:
    result = _detect([(0.0, 6.0), (1.9, 6.0), (2.0, 0.0), (40.0, 0.0)])

    assert result.available is True
    assert not result.segments


def test_interrupted_start_candidate_resets_to_next_motion_run() -> None:
    result = _detect([(0.0, 6.0), (1.0, 0.0), (5.0, 6.0), (7.0, 6.0), (8.0, 0.0), (38.0, 0.0)])

    assert result.segments == (FlightSegment(start_s=5.0, end_s=7.0, is_complete=True),)


def test_final_open_flight_is_explicitly_incomplete() -> None:
    result = _detect([(0.0, 6.0), (2.0, 6.0), (3.0, 0.0), (10.0, 0.0)])

    assert result.segments == (FlightSegment(start_s=0.0, end_s=10.0, is_complete=False),)


@pytest.mark.parametrize(
    ("log_data", "reason"),
    [
        (LogData(), "GPS messages are unavailable"),
        (LogData(_raw_messages={"GPS": np.array([(1.0,)], dtype=[("Spd", "f8")])}), "GPS fields are unavailable: TimeUS"),
        (
            LogData(_raw_messages={"GPS": np.array([(1.0,)], dtype=[("TimeUS", "f8")])}),
            "GPS fields are unavailable: Spd",
        ),
    ],
)
def test_missing_required_gps_evidence_makes_segmentation_unavailable(log_data: LogData, reason: str) -> None:
    result = PlaneFlightSegmentDetector.detect(log_data, {})

    assert result.available is False
    assert not result.segments
    assert result.reason == reason


def test_non_finite_required_gps_evidence_makes_segmentation_unavailable() -> None:
    result = _detect([(0.0, 6.0), (2.0, np.nan)])

    assert result.available is False
    assert result.reason == "GPS time or groundspeed values are unusable"


def test_missing_stall_speed_uses_five_metre_per_second_threshold() -> None:
    result = _detect([(0.0, 6.0), (2.0, 6.0)])

    assert result.segments == (FlightSegment(start_s=0.0, end_s=2.0, is_complete=False),)


def test_stall_speed_raises_effective_threshold() -> None:
    result = _detect([(0.0, 6.0), (2.0, 6.0), (3.0, 11.0), (5.0, 11.0)], {"AIRSPEED_STALL": 20.0})

    assert result.segments == (FlightSegment(start_s=3.0, end_s=5.0, is_complete=False),)


def test_speed_exactly_at_threshold_does_not_qualify() -> None:
    result = _detect([(0.0, 5.0), (2.0, 5.0)])

    assert not result.segments


def test_exact_start_and_ground_persistence_boundaries_qualify() -> None:
    result = _detect([(0.0, 6.0), (2.0, 6.0), (3.0, 5.0), (33.0, 5.0)])

    assert result.segments == (FlightSegment(start_s=0.0, end_s=2.0, is_complete=True),)


def test_elapsed_timestamp_gaps_count_toward_persistence() -> None:
    result = _detect([(0.0, 6.0), (10.0, 6.0), (11.0, 0.0), (50.0, 0.0)])

    assert result.segments == (FlightSegment(start_s=0.0, end_s=10.0, is_complete=True),)


def test_detector_uses_log_data_scaled_seconds() -> None:
    log_data = _gps_log(
        [(0, 6.0), (2_000_000, 6.0), (3_000_000, 0.0), (33_000_000, 0.0)],
        scaled_from_microseconds=True,
    )

    result = PlaneFlightSegmentDetector.detect(log_data, {})

    assert result.segments == (FlightSegment(start_s=0.0, end_s=2.0, is_complete=True),)
