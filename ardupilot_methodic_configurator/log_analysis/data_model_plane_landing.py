"""
AMC-native ArduPlane landing-attempt detection within operational flights.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Mapping

    import numpy as np

    from ardupilot_methodic_configurator.log_analysis.data_model_flight_segment import FlightSegment
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
    from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterHistory


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


class PlaneLandingStage(IntEnum):
    """ArduPlane LAND controller stages used by the first evidence slice."""

    PREFLARE = 2
    FLARE = 3


@dataclass(frozen=True, slots=True)
class PlaneLandingStageEvidence:  # pylint: disable=too-many-instance-attributes
    """Objective measurements associated with one LAND stage transition."""

    attempt: PlaneLandingAttempt
    stage: PlaneLandingStage
    time_s: float
    flight_height_m: float | None = None
    airspeed_m_s: float | None = None
    barometric_altitude_m: float | None = None
    rangefinder_distance_m: float | None = None
    parameter_values: Mapping[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Require the event to lie inside its attempt and freeze parameter evidence."""
        if not self.attempt.start_s <= self.time_s <= self.attempt.end_s:
            msg = "Plane landing stage evidence must be contained by its landing attempt"
            raise ValueError(msg)
        object.__setattr__(self, "parameter_values", MappingProxyType(dict(self.parameter_values)))


class PlaneLandingEvidenceExtractor:  # pylint: disable=too-few-public-methods
    """Collect APT-compatible stage and nearest-telemetry evidence for one attempt."""

    _PARAMETERS_BY_STAGE: ClassVar[dict[PlaneLandingStage, tuple[str, ...]]] = {
        PlaneLandingStage.PREFLARE: ("LAND_PF_ALT", "LAND_PF_SEC"),
        PlaneLandingStage.FLARE: ("LAND_FLARE_ALT", "LAND_FLARE_SEC", "LAND_PITCH_DEG"),
    }

    @classmethod
    def extract(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
    ) -> tuple[PlaneLandingStageEvidence, ...]:
        """Return the first preflare and flare transitions found inside ``attempt``."""
        return tuple(
            cls._build_stage_evidence(log_data, attempt, parameter_history, transition)
            for transition in cls._stage_transitions(log_data, attempt)
        )

    @classmethod
    def _stage_transitions(
        cls, log_data: LogData, attempt: PlaneLandingAttempt
    ) -> list[tuple[PlaneLandingStage, float, float | None]]:
        """Return the first scoped transition into each supported LAND stage."""
        land = log_data.get_message_columns("LAND")
        if land is None or not {"TimeUS", "stage"}.issubset(land.dtype.names or ()):
            return []

        flight_heights = log_data.get_field("LAND", "fh") if "fh" in (land.dtype.names or ()) else None
        transitions: list[tuple[PlaneLandingStage, float, float | None]] = []
        seen_stages: set[PlaneLandingStage] = set()
        previous_stage: int | None = None

        for index, (timestamp, stage_value) in enumerate(
            zip(log_data.get_field("LAND", "TimeUS"), log_data.get_field("LAND", "stage"), strict=True)
        ):
            timestamp_s = float(timestamp)
            if not attempt.start_s <= timestamp_s <= attempt.end_s:
                continue
            stage_number = int(stage_value)
            changed_stage = stage_number != previous_stage
            previous_stage = stage_number
            try:
                stage = PlaneLandingStage(stage_number)
            except ValueError:
                continue
            if not changed_stage or stage in seen_stages:
                continue
            seen_stages.add(stage)
            transitions.append(
                (
                    stage,
                    timestamp_s,
                    cls._finite_float(flight_heights[index]) if flight_heights is not None else None,
                )
            )
        return transitions

    @classmethod
    def _build_stage_evidence(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
        transition: tuple[PlaneLandingStage, float, float | None],
    ) -> PlaneLandingStageEvidence:
        stage, time_s, flight_height_m = transition
        return PlaneLandingStageEvidence(
            attempt=attempt,
            stage=stage,
            time_s=time_s,
            flight_height_m=flight_height_m,
            airspeed_m_s=cls._nearest_value(log_data, attempt, ("ARSP", "Airspeed"), time_s),
            barometric_altitude_m=cls._nearest_value(log_data, attempt, ("BARO", "Alt"), time_s),
            rangefinder_distance_m=cls._nearest_value(log_data, attempt, ("RFND", "Dist"), time_s),
            parameter_values={
                parameter_name: parameter_history.value_at(parameter_name, time_s)
                for parameter_name in cls._PARAMETERS_BY_STAGE[stage]
            },
        )

    @classmethod
    def _nearest_value(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        telemetry_field: tuple[str, str],
        target_time_s: float,
    ) -> float | None:
        message_name, field_name = telemetry_field
        records = log_data.get_message_columns(message_name)
        if records is None or not {"TimeUS", field_name}.issubset(records.dtype.names or ()):
            return None

        nearest_value: float | None = None
        nearest_offset: float | None = None
        for timestamp, value in zip(
            log_data.get_field(message_name, "TimeUS"),
            log_data.get_field(message_name, field_name),
            strict=True,
        ):
            timestamp_s = cls._finite_float(timestamp)
            measured_value = cls._finite_float(value)
            if timestamp_s is None or measured_value is None or not attempt.start_s <= timestamp_s <= attempt.end_s:
                continue
            offset = abs(timestamp_s - target_time_s)
            if nearest_offset is None or offset < nearest_offset:
                nearest_offset = offset
                nearest_value = measured_value
        return nearest_value

    @staticmethod
    def _finite_float(value: object) -> float | None:
        try:
            converted = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return converted if math.isfinite(converted) else None
