"""
AMC-native ArduPlane landing-attempt detection within operational flights.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

import numpy as np

from ardupilot_methodic_configurator.log_analysis.data_model_flight_segment import FlightSegment
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData


class PlaneLandingEndReason(str, Enum):
    """Objective evidence that bounded a detected AUTO landing attempt."""

    ABORT = "abort"
    DISARM = "disarm"
    MODE_EXIT = "mode"
    GPS_STOP = "gps"
    FLIGHT_SEGMENT_END = "flight_segment_end"


@dataclass(frozen=True, slots=True)
class PlaneLandingAttempt:
    """One AUTO landing attempt contained by an operational Plane flight."""

    flight_segment: FlightSegment
    start_s: float
    end_s: float
    end_reason: PlaneLandingEndReason

    def __post_init__(self) -> None:
        """Require a non-empty attempt fully contained by its parent flight."""
        if self.start_s >= self.end_s:
            msg = "Plane landing attempt start_s must be before end_s"
            raise ValueError(msg)
        if not self.flight_segment.contains(self.start_s, self.end_s):
            msg = "Plane landing attempt must be contained by its flight segment"
            raise ValueError(msg)

    @property
    def duration_s(self) -> float:
        """Return the attempt duration in seconds."""
        return self.end_s - self.start_s


class PlaneLandingAttemptDetector:  # pylint: disable=too-few-public-methods
    """Detect APT-compatible AUTO landing-attempt boundaries in one flight."""

    AUTO_MODE_NUMBER: ClassVar[int] = 10
    GPS_STOP_SPEED_M_S: ClassVar[float] = 3.0
    GPS_STOP_PERSISTENCE_S: ClassVar[float] = 2.0

    @classmethod
    def detect(cls, log_data: LogData, flight_segment: FlightSegment) -> tuple[PlaneLandingAttempt, ...]:
        """Return all AUTO-gated LAND stage-one attempts within ``flight_segment``."""
        land = log_data.get_message_columns("LAND")
        mode = log_data.get_message_columns("MODE")
        if land is None or mode is None:
            return ()

        starts = cls._landing_starts(log_data, flight_segment)
        attempts: list[PlaneLandingAttempt] = []
        for start_s in starts:
            attempt = cls._attempt_for_start(log_data, flight_segment, start_s)
            if attempt is not None:
                attempts.append(attempt)
        return tuple(attempts)

    @classmethod
    def _landing_starts(cls, log_data: LogData, flight_segment: FlightSegment) -> list[float]:
        """Find LAND stage-one transitions whose current Plane mode is AUTO."""
        land_time_s = log_data.get_field("LAND", "TimeUS")
        land_stage = log_data.get_field("LAND", "stage")
        mode_time_s = log_data.get_field("MODE", "TimeUS")
        mode_number = log_data.get_field("MODE", "ModeNum")

        starts: list[float] = []
        previous_stage: int | None = None
        for timestamp, stage_value in zip(land_time_s, land_stage, strict=True):
            stage = int(stage_value)
            timestamp_s = float(timestamp)
            entered_landing_stage = stage == 1 and previous_stage != 1
            previous_stage = stage
            if (
                entered_landing_stage
                and flight_segment.start_s <= timestamp_s <= flight_segment.end_s
                and cls._mode_is_auto(mode_time_s, mode_number, timestamp_s)
            ):
                starts.append(timestamp_s)
        return starts

    @classmethod
    def _attempt_for_start(
        cls,
        log_data: LogData,
        flight_segment: FlightSegment,
        start_s: float,
    ) -> PlaneLandingAttempt | None:
        candidates = cls._message_termination_events(log_data, flight_segment, start_s)
        mode_exit = cls._first_mode_exit(log_data, flight_segment, start_s)
        if mode_exit is not None:
            candidates.append(mode_exit)
        gps_stop_s = cls._first_gps_stop(log_data, flight_segment, start_s)
        if gps_stop_s is not None:
            candidates.append((gps_stop_s, PlaneLandingEndReason.GPS_STOP))

        if candidates:
            end_s, end_reason = min(candidates, key=lambda item: item[0])
        else:
            end_s, end_reason = flight_segment.end_s, PlaneLandingEndReason.FLIGHT_SEGMENT_END

        if end_s <= start_s:
            return None
        return PlaneLandingAttempt(
            flight_segment=flight_segment,
            start_s=start_s,
            end_s=end_s,
            end_reason=end_reason,
        )

    @classmethod
    def _mode_is_auto(cls, time_s: np.ndarray, mode_number: np.ndarray, timestamp_s: float) -> bool:
        current_mode: int | None = None
        for mode_timestamp, number in zip(time_s, mode_number, strict=True):
            if float(mode_timestamp) > timestamp_s:
                break
            current_mode = int(number)
        return current_mode == cls.AUTO_MODE_NUMBER

    @classmethod
    def _message_termination_events(
        cls,
        log_data: LogData,
        flight_segment: FlightSegment,
        start_s: float,
    ) -> list[tuple[float, PlaneLandingEndReason]]:
        messages = log_data.get_message_columns("MSG")
        if messages is None or not {"TimeUS", "Message"}.issubset(messages.dtype.names or ()):
            return []

        events: list[tuple[float, PlaneLandingEndReason]] = []
        for timestamp, message in zip(
            log_data.get_field("MSG", "TimeUS"),
            log_data.get_field("MSG", "Message"),
            strict=True,
        ):
            timestamp_s = float(timestamp)
            if not start_s < timestamp_s <= flight_segment.end_s:
                continue
            text = str(message).lower()
            if "landing aborted" in text:
                events.append((timestamp_s, PlaneLandingEndReason.ABORT))
            elif "throttle disarmed" in text:
                events.append((timestamp_s, PlaneLandingEndReason.DISARM))
        return events

    @classmethod
    def _first_mode_exit(
        cls,
        log_data: LogData,
        flight_segment: FlightSegment,
        start_s: float,
    ) -> tuple[float, PlaneLandingEndReason] | None:
        for timestamp, mode_number in zip(
            log_data.get_field("MODE", "TimeUS"),
            log_data.get_field("MODE", "ModeNum"),
            strict=True,
        ):
            timestamp_s = float(timestamp)
            if start_s < timestamp_s <= flight_segment.end_s and int(mode_number) != cls.AUTO_MODE_NUMBER:
                return timestamp_s, PlaneLandingEndReason.MODE_EXIT
        return None

    @classmethod
    def _first_gps_stop(cls, log_data: LogData, flight_segment: FlightSegment, start_s: float) -> float | None:
        gps = log_data.get_message_columns("GPS")
        if gps is None or not {"TimeUS", "Spd"}.issubset(gps.dtype.names or ()):
            return None

        below_since_s: float | None = None
        for timestamp, speed in zip(
            log_data.get_field("GPS", "TimeUS"),
            log_data.get_field("GPS", "Spd"),
            strict=True,
        ):
            timestamp_s = float(timestamp)
            if not start_s <= timestamp_s <= flight_segment.end_s:
                continue
            if float(speed) < cls.GPS_STOP_SPEED_M_S:
                if below_since_s is None:
                    below_since_s = timestamp_s
                elif timestamp_s - below_since_s >= cls.GPS_STOP_PERSISTENCE_S:
                    return below_since_s
            else:
                below_since_s = None
        return None
