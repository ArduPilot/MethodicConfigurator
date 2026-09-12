"""
AMC-native ArduPlane landing-attempt detection within operational flights.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=too-many-lines

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ardupilot_methodic_configurator.log_analysis.data_model_flight_segment import FlightSegment
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
    from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterHistory


def _active_gps_fields(log_data: LogData, *field_names: str) -> tuple[np.ndarray, ...] | None:
    """Return scaled GPS fields, restricted to the active receiver when ``U`` is available."""
    gps = log_data.get_message_columns("GPS")
    if gps is None:
        return None
    names = gps.dtype.names or ()
    if not set(field_names).issubset(names):
        return None

    values = tuple(log_data.get_field("GPS", field_name) for field_name in field_names)
    if "U" not in names:
        return values

    active_receiver_samples = log_data.get_field("GPS", "U") == 1
    return tuple(field_values[active_receiver_samples] for field_values in values)


def _instance_zero_fields(
    log_data: LogData,
    message_name: str,
    instance_field: str,
    *field_names: str,
) -> tuple[np.ndarray, ...] | None:
    """Return message fields restricted to instance zero when the selector exists."""
    records = log_data.get_message_columns(message_name)
    if records is None:
        return None
    names = records.dtype.names or ()
    if not set(field_names).issubset(names):
        return None

    values = tuple(log_data.get_field(message_name, field_name) for field_name in field_names)
    if instance_field not in names:
        return values

    instance_zero_samples = log_data.get_field(message_name, instance_field) == 0
    return tuple(field_values[instance_zero_samples] for field_values in values)


def _owns_attempt_observation(attempt: PlaneLandingAttempt, timestamp_s: float) -> bool:
    """Return whether an observational record belongs to ``attempt``."""
    if attempt.end_reason is PlaneLandingEndReason.STAGE_RESTART:
        return attempt.start_s <= timestamp_s < attempt.end_s
    return attempt.start_s <= timestamp_s <= attempt.end_s


_FIRMWARE_FLARE_PREFIX = "Flare "


def _finite_float(value: object) -> float | None:
    """Return a finite float, or ``None`` when conversion is unsafe."""
    try:
        converted = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return converted if math.isfinite(converted) else None


def _prefixed_value(text: str, prefix: str, suffix: str) -> float | None:
    """Parse a finite value between a required prefix and suffix."""
    if not text.startswith(prefix):
        return None
    value_text = text[len(prefix) :]
    suffix_index = value_text.find(suffix)
    if suffix_index < 0:
        return None
    return _finite_float(value_text[:suffix_index].strip())


def _named_value(text: str, name: str) -> float | None:
    """Parse a finite whitespace-delimited named value."""
    name_index = text.find(name)
    if name_index < 0:
        return None
    value_parts = text[name_index + len(name) :].split()
    return _finite_float(value_parts[0]) if value_parts else None


def _firmware_flare_values(message: str) -> tuple[float, float, float, float] | None:
    """Return all values from a complete finite firmware Flare message."""
    altitude_m = _prefixed_value(message, _FIRMWARE_FLARE_PREFIX, "m")
    sink_rate_m_s = _named_value(message, "sink=")
    groundspeed_m_s = _named_value(message, "speed=")
    distance_to_target_m = _named_value(message, "dist=")
    if altitude_m is None or sink_rate_m_s is None or groundspeed_m_s is None or distance_to_target_m is None:
        return None
    return altitude_m, sink_rate_m_s, groundspeed_m_s, distance_to_target_m


class PlaneLandingEndReason(str, Enum):
    """Objective evidence that bounded a detected Plane landing attempt."""

    ABORT = "abort"
    DISARM = "disarm"
    MODE_EXIT = "mode"
    GPS_STOP = "gps"
    STAGE_RESTART = "stage_restart"
    FLIGHT_SEGMENT_END = "flight_segment_end"


@dataclass(frozen=True, slots=True)
class PlaneLandingAttempt:
    """One landing attempt contained by an operational Plane flight."""

    flight_segment: FlightSegment
    start_s: float
    end_s: float
    end_reason: PlaneLandingEndReason
    mode_number: int
    start_stage: int = 1
    previous_attempt_end_s: float | None = None

    def __post_init__(self) -> None:
        """Require a non-empty attempt fully contained by its parent flight."""
        if self.start_s >= self.end_s:
            msg = "Plane landing attempt start_s must be before end_s"
            raise ValueError(msg)
        if not self.flight_segment.contains(self.start_s, self.end_s):
            msg = "Plane landing attempt must be contained by its flight segment"
            raise ValueError(msg)
        if self.start_stage not in {1, 2, 3}:
            msg = "Plane landing attempt start_stage must be an active LAND stage"
            raise ValueError(msg)

    @property
    def duration_s(self) -> float:
        """Return the attempt duration in seconds."""
        return self.end_s - self.start_s


@dataclass(frozen=True, slots=True)
class _PlaneLandingAttemptNeighbors:
    """Attempt boundaries immediately adjacent to one landing start."""

    next_start_s: float | None
    previous_end_s: float | None


class PlaneLandingAttemptDetector:  # pylint: disable=too-few-public-methods
    """Detect APT-compatible landing-attempt boundaries in one flight."""

    AUTO_MODE_NUMBER: ClassVar[int] = 10
    AUTOLAND_MODE_NUMBER: ClassVar[int] = 26
    LANDING_MODE_NUMBERS: ClassVar[frozenset[int]] = frozenset({AUTO_MODE_NUMBER, AUTOLAND_MODE_NUMBER})
    GPS_STOP_SPEED_M_S: ClassVar[float] = 3.0
    GPS_STOP_PERSISTENCE_S: ClassVar[float] = 2.0

    @classmethod
    def detect(cls, log_data: LogData, flight_segment: FlightSegment) -> tuple[PlaneLandingAttempt, ...]:
        """Return all landing-mode-gated active LAND sequences within ``flight_segment``."""
        land = log_data.get_message_columns("LAND")
        mode = log_data.get_message_columns("MODE")
        if (
            land is None
            or mode is None
            or not {"TimeUS", "stage"}.issubset(land.dtype.names or ())
            or not {"TimeUS", "ModeNum"}.issubset(mode.dtype.names or ())
        ):
            return ()

        starts = cls._landing_starts(log_data, flight_segment)
        attempts: list[PlaneLandingAttempt] = []
        for index, start in enumerate(starts):
            next_start_s = starts[index + 1][0] if index + 1 < len(starts) else None
            previous_attempt_end_s = attempts[-1].end_s if attempts else None
            attempt = cls._attempt_for_start(
                log_data,
                flight_segment,
                start,
                _PlaneLandingAttemptNeighbors(next_start_s, previous_attempt_end_s),
            )
            if attempt is not None:
                attempts.append(attempt)
        return tuple(attempts)

    @classmethod
    def _landing_starts(  # pylint: disable=too-many-locals
        cls, log_data: LogData, flight_segment: FlightSegment
    ) -> list[tuple[float, int, int]]:
        """Find the first active stage of each LAND sequence in a supported mode."""
        land_time_s = log_data.get_field("LAND", "TimeUS")
        land_stage = log_data.get_field("LAND", "stage")
        mode_time_s = log_data.get_field("MODE", "TimeUS")
        mode_number = log_data.get_field("MODE", "ModeNum")

        starts: list[tuple[float, int, int]] = []
        previous_stage: int | None = None
        for timestamp, stage_value in zip(land_time_s, land_stage, strict=True):
            stage = int(stage_value)
            timestamp_s = float(timestamp)
            if not flight_segment.start_s <= timestamp_s <= flight_segment.end_s:
                continue

            entered_active_sequence = stage in {1, 2, 3} and previous_stage in {None, 0}
            restarted_active_sequence = stage == 1 and previous_stage in {2, 3}
            previous_stage = stage
            if not entered_active_sequence and not restarted_active_sequence:
                continue
            landing_mode = cls._landing_mode_at(mode_time_s, mode_number, timestamp_s)
            if landing_mode is not None:
                starts.append((timestamp_s, landing_mode, stage))
        return starts

    @classmethod
    def _attempt_for_start(  # pylint: disable=too-many-locals
        cls,
        log_data: LogData,
        flight_segment: FlightSegment,
        start: tuple[float, int, int],
        neighbors: _PlaneLandingAttemptNeighbors,
    ) -> PlaneLandingAttempt | None:
        start_s, mode_number, start_stage = start
        candidates = cls._message_termination_events(log_data, flight_segment, start_s)
        mode_exit = cls._first_mode_exit(log_data, flight_segment, start_s, mode_number)
        if mode_exit is not None:
            candidates.append(mode_exit)
        if neighbors.next_start_s is not None:
            candidates.append((neighbors.next_start_s, PlaneLandingEndReason.STAGE_RESTART))

        if candidates:
            provisional_end_s, provisional_end_reason = min(
                candidates,
                key=lambda item: (item[0], item[1] is not PlaneLandingEndReason.STAGE_RESTART),
            )
        else:
            provisional_end_s = flight_segment.end_s
            provisional_end_reason = PlaneLandingEndReason.FLIGHT_SEGMENT_END

        if provisional_end_s <= start_s:
            return None
        provisional_attempt = PlaneLandingAttempt(
            flight_segment=flight_segment,
            start_s=start_s,
            end_s=provisional_end_s,
            end_reason=provisional_end_reason,
            mode_number=mode_number,
            start_stage=start_stage,
            previous_attempt_end_s=neighbors.previous_end_s,
        )
        corroboration_s = cls._first_final_evidence(log_data, provisional_attempt)
        if corroboration_s is not None:
            gps_stop_s = cls._first_gps_stop(log_data, provisional_attempt, max(start_s, corroboration_s))
            if gps_stop_s is not None:
                candidates.append((gps_stop_s, PlaneLandingEndReason.GPS_STOP))

        if candidates:
            end_s, end_reason = min(
                candidates,
                key=lambda item: (item[0], item[1] is not PlaneLandingEndReason.STAGE_RESTART),
            )
        else:
            end_s, end_reason = provisional_end_s, provisional_end_reason
        if end_s <= start_s:
            # The earliest supported termination leaves no positive-duration attempt; do not substitute a later one.
            return None
        return PlaneLandingAttempt(
            flight_segment=flight_segment,
            start_s=start_s,
            end_s=end_s,
            end_reason=end_reason,
            mode_number=mode_number,
            start_stage=start_stage,
            previous_attempt_end_s=neighbors.previous_end_s,
        )

    @classmethod
    def _first_final_evidence(cls, log_data: LogData, attempt: PlaneLandingAttempt) -> float | None:
        """Return earliest valid LAND-stage-3 or associated firmware Flare evidence."""
        candidates: list[float] = []
        for timestamp, stage_value in zip(
            log_data.get_field("LAND", "TimeUS"),
            log_data.get_field("LAND", "stage"),
            strict=True,
        ):
            timestamp_s = _finite_float(timestamp)
            if timestamp_s is not None and int(stage_value) == 3 and _owns_attempt_observation(attempt, timestamp_s):
                candidates.append(timestamp_s)
        candidates.extend(
            evidence.time_s
            for evidence in PlaneLandingFirmwareMessageExtractor.extract(log_data, attempt)
            if isinstance(evidence, PlaneLandingFirmwareFlareEvidence)
        )
        return min(candidates) if candidates else None

    @classmethod
    def _landing_mode_at(cls, time_s: np.ndarray, mode_number: np.ndarray, timestamp_s: float) -> int | None:
        current_mode: int | None = None
        for mode_timestamp, number in zip(time_s, mode_number, strict=True):
            if float(mode_timestamp) > timestamp_s:
                break
            current_mode = int(number)
        return current_mode if current_mode in cls.LANDING_MODE_NUMBERS else None

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
        start_mode_number: int,
    ) -> tuple[float, PlaneLandingEndReason] | None:
        for timestamp, new_mode_number in zip(
            log_data.get_field("MODE", "TimeUS"),
            log_data.get_field("MODE", "ModeNum"),
            strict=True,
        ):
            timestamp_s = float(timestamp)
            if start_s < timestamp_s <= flight_segment.end_s and int(new_mode_number) != start_mode_number:
                return timestamp_s, PlaneLandingEndReason.MODE_EXIT
        return None

    @classmethod
    def _first_gps_stop(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        evaluation_start_s: float,
    ) -> float | None:
        gps_fields = _active_gps_fields(log_data, "TimeUS", "Spd")
        if gps_fields is None:
            return None
        time_s, speed_m_s = gps_fields

        below_since_s: float | None = None
        for timestamp, speed in zip(time_s, speed_m_s, strict=True):
            timestamp_s = float(timestamp)
            if timestamp_s < evaluation_start_s:
                continue
            if not _owns_attempt_observation(attempt, timestamp_s):
                break
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
    gps_ground_speed_m_s: float | None = None
    barometric_altitude_m: float | None = None
    barometric_sink_rate_m_s: float | None = None
    rangefinder_distance_m: float | None = None
    rangefinder_status: int | None = None
    flare_to_gps_stop_s: float | None = None
    parameter_values: Mapping[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Require the event to lie inside its attempt and freeze parameter evidence."""
        if not _owns_attempt_observation(self.attempt, self.time_s):
            msg = "Plane landing stage evidence must be contained by its landing attempt"
            raise ValueError(msg)
        object.__setattr__(self, "parameter_values", MappingProxyType(dict(self.parameter_values)))


@dataclass(frozen=True, slots=True)
class PlaneLandingFirmwareFlareEvidence:
    """Objective values reported by one complete attempt-scoped firmware Flare message."""

    attempt: PlaneLandingAttempt
    time_s: float
    altitude_m: float
    sink_rate_m_s: float
    groundspeed_m_s: float
    distance_to_target_m: float
    associated_before_attempt_start: bool = False

    def __post_init__(self) -> None:
        """Require the firmware message to lie inside its landing attempt."""
        ordinary_evidence = not self.associated_before_attempt_start and _owns_attempt_observation(self.attempt, self.time_s)
        left_truncated_evidence = (
            self.associated_before_attempt_start
            and self.attempt.start_stage == 3
            and self.attempt.flight_segment.start_s <= self.time_s < self.attempt.start_s
        )
        if not ordinary_evidence and not left_truncated_evidence:
            msg = "Plane firmware flare evidence must be contained by its landing attempt"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PlaneLandingFirmwareGlideSlopeEvidence:
    """Objective glide-slope value reported by one attempt-scoped firmware message."""

    attempt: PlaneLandingAttempt
    time_s: float
    glide_slope_degrees: float

    def __post_init__(self) -> None:
        """Require the firmware message to lie inside its landing attempt."""
        if not _owns_attempt_observation(self.attempt, self.time_s):
            msg = "Plane firmware glide-slope evidence must be contained by its landing attempt"
            raise ValueError(msg)


PlaneLandingFirmwareEvidence = PlaneLandingFirmwareFlareEvidence | PlaneLandingFirmwareGlideSlopeEvidence


class PlaneLandingFirmwareMessageExtractor:  # pylint: disable=too-few-public-methods
    """Parse the first complete APT-recognized firmware messages inside one attempt."""

    _FLARE_PREFIX: ClassVar[str] = _FIRMWARE_FLARE_PREFIX
    _GLIDE_SLOPE_PREFIX: ClassVar[str] = "Landing glide slope "

    @classmethod
    def extract(cls, log_data: LogData, attempt: PlaneLandingAttempt) -> tuple[PlaneLandingFirmwareEvidence, ...]:
        """Return chronological, complete firmware flare and glide-slope evidence."""
        messages = log_data.get_message_columns("MSG")
        if messages is None or not {"TimeUS", "Message"}.issubset(messages.dtype.names or ()):
            return ()

        candidates: list[tuple[float, str]] = []
        for timestamp, message in zip(
            log_data.get_field("MSG", "TimeUS"),
            log_data.get_field("MSG", "Message"),
            strict=True,
        ):
            timestamp_s = _finite_float(timestamp)
            if timestamp_s is not None and _owns_attempt_observation(attempt, timestamp_s):
                candidates.append((timestamp_s, str(message)))

        evidence: list[PlaneLandingFirmwareEvidence] = []
        flare_found = False
        glide_slope_found = False
        for timestamp_s, message in sorted(candidates, key=lambda item: item[0]):
            if not flare_found and message.startswith(cls._FLARE_PREFIX):
                flare = cls._parse_flare(attempt, timestamp_s, message)
                if flare is not None:
                    evidence.append(flare)
                    flare_found = True
            elif not glide_slope_found and message.startswith(cls._GLIDE_SLOPE_PREFIX):
                glide_slope = cls._parse_glide_slope(attempt, timestamp_s, message)
                if glide_slope is not None:
                    evidence.append(glide_slope)
                    glide_slope_found = True
        if not flare_found:
            left_truncated_flare = cls._left_truncated_flare(log_data, attempt)
            if left_truncated_flare is not None:
                evidence.append(left_truncated_flare)
        return tuple(sorted(evidence, key=lambda item: item.time_s))

    @classmethod
    def _parse_flare(
        cls,
        attempt: PlaneLandingAttempt,
        timestamp_s: float,
        message: str,
    ) -> PlaneLandingFirmwareFlareEvidence | None:
        values = _firmware_flare_values(message)
        if values is None:
            return None
        altitude_m, sink_rate_m_s, groundspeed_m_s, distance_to_target_m = values
        return PlaneLandingFirmwareFlareEvidence(
            attempt=attempt,
            time_s=timestamp_s,
            altitude_m=altitude_m,
            sink_rate_m_s=sink_rate_m_s,
            groundspeed_m_s=groundspeed_m_s,
            distance_to_target_m=distance_to_target_m,
        )

    @classmethod
    def _left_truncated_flare(  # noqa: PLR0911  # pylint: disable=too-many-locals,too-many-return-statements
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
    ) -> PlaneLandingFirmwareFlareEvidence | None:
        """Return the narrowly associated pre-start Flare for a stage-3-opened attempt."""
        if attempt.start_stage != 3:
            return None
        messages = log_data.get_message_columns("MSG")
        land = log_data.get_message_columns("LAND")
        if messages is None or land is None:
            return None

        complete_candidates: list[tuple[float, str]] = []
        for timestamp, message in zip(
            log_data.get_field("MSG", "TimeUS"),
            log_data.get_field("MSG", "Message"),
            strict=True,
        ):
            timestamp_s = _finite_float(timestamp)
            text = str(message)
            if (
                timestamp_s is not None
                and attempt.flight_segment.start_s <= timestamp_s < attempt.start_s
                and _firmware_flare_values(text) is not None
            ):
                complete_candidates.append((timestamp_s, text))
        if not complete_candidates:
            return None
        timestamp_s, message = max(complete_candidates, key=lambda item: item[0])

        if attempt.previous_attempt_end_s is not None and timestamp_s <= attempt.previous_attempt_end_s:
            return None

        preceding_land_times = [
            land_time_s
            for timestamp in log_data.get_field("LAND", "TimeUS")
            if (land_time_s := _finite_float(timestamp)) is not None and land_time_s < attempt.start_s
        ]
        if not preceding_land_times or timestamp_s <= max(preceding_land_times):
            return None
        if cls._association_is_invalidated(log_data, attempt, timestamp_s):
            return None

        values = _firmware_flare_values(message)
        if values is None:  # pragma: no cover - guarded while collecting candidates
            return None
        altitude_m, sink_rate_m_s, groundspeed_m_s, distance_to_target_m = values
        return PlaneLandingFirmwareFlareEvidence(
            attempt=attempt,
            time_s=timestamp_s,
            altitude_m=altitude_m,
            sink_rate_m_s=sink_rate_m_s,
            groundspeed_m_s=groundspeed_m_s,
            distance_to_target_m=distance_to_target_m,
            associated_before_attempt_start=True,
        )

    @classmethod
    def _association_is_invalidated(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        flare_time_s: float,
    ) -> bool:
        """Return whether termination or mode evidence breaks a pre-start association."""
        flare_mode = PlaneLandingAttemptDetector._landing_mode_at(  # noqa: SLF001  # pylint: disable=protected-access
            log_data.get_field("MODE", "TimeUS"),
            log_data.get_field("MODE", "ModeNum"),
            flare_time_s,
        )
        if flare_mode is not None and flare_mode != attempt.mode_number:
            return True
        for timestamp, message in zip(
            log_data.get_field("MSG", "TimeUS"),
            log_data.get_field("MSG", "Message"),
            strict=True,
        ):
            timestamp_s = _finite_float(timestamp)
            if timestamp_s is None or not flare_time_s < timestamp_s < attempt.start_s:
                continue
            text = str(message).lower()
            if "landing aborted" in text or "throttle disarmed" in text:
                return True
        for timestamp, mode_number in zip(
            log_data.get_field("MODE", "TimeUS"),
            log_data.get_field("MODE", "ModeNum"),
            strict=True,
        ):
            timestamp_s = _finite_float(timestamp)
            if (
                timestamp_s is not None
                and flare_time_s < timestamp_s < attempt.start_s
                and int(mode_number) != attempt.mode_number
            ):
                return True
        return False

    @classmethod
    def _parse_glide_slope(
        cls,
        attempt: PlaneLandingAttempt,
        timestamp_s: float,
        message: str,
    ) -> PlaneLandingFirmwareGlideSlopeEvidence | None:
        glide_slope_degrees = _prefixed_value(message, cls._GLIDE_SLOPE_PREFIX, " degrees")
        if glide_slope_degrees is None:
            return None
        return PlaneLandingFirmwareGlideSlopeEvidence(
            attempt=attempt,
            time_s=timestamp_s,
            glide_slope_degrees=glide_slope_degrees,
        )


@dataclass(frozen=True, slots=True)
class _PlaneLandingRangefinderSample:
    """One firmware-selected landing rangefinder sample."""

    time_s: float
    distance_m: float | None
    instance: int
    status: int | None


@dataclass(frozen=True, slots=True)
class _PlaneLandingRangefinderBreak:
    """One logged RFND frame unusable for deterministic landing selection."""

    time_s: float


_RangefinderSelectionEvent = _PlaneLandingRangefinderSample | _PlaneLandingRangefinderBreak


@dataclass(frozen=True, slots=True)
class _PlaneLandingRangefinderSelection:
    """Ordered selected observations and explicit acquisition-continuity breaks."""

    events: tuple[_RangefinderSelectionEvent, ...]

    @property
    def samples(self) -> tuple[_PlaneLandingRangefinderSample, ...]:
        """Return only valid observations for stage-point evidence."""
        return tuple(event for event in self.events if isinstance(event, _PlaneLandingRangefinderSample))


_RangefinderRow = tuple[float, float | None, int, int | None, int]
_RangefinderFrame = tuple[_RangefinderRow, ...]


@dataclass(frozen=True, slots=True)
class _PlaneLandingRangefinderData:
    """Immutable RFND representation prepared once for one analysis request."""

    frames: tuple[_RangefinderFrame, ...] | None = None
    legacy_samples: tuple[_PlaneLandingRangefinderSample, ...] | None = None


class _PlaneLandingRangefinderSelector:  # pylint: disable=too-many-locals
    """Select Plane's configured landing rangefinder from RFND update frames."""

    LANDING_ORIENTATION_PARAMETER: ClassVar[str] = "RNGFND_LND_ORNT"
    GOOD_STATUS: ClassVar[int] = 4
    CURRENT_DATA_STATUSES: ClassVar[frozenset[int]] = frozenset({2, 3, 4})
    MAX_RANGE_PARAMETERS: ClassVar[tuple[str, ...]] = (
        "RNGFND1_MAX",
        "RNGFND2_MAX",
        "RNGFND3_MAX",
        "RNGFND4_MAX",
        "RNGFND5_MAX",
        "RNGFND6_MAX",
        "RNGFND7_MAX",
        "RNGFND8_MAX",
        "RNGFND9_MAX",
        "RNGFNDA_MAX",
    )

    @classmethod
    def select(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
    ) -> _PlaneLandingRangefinderSelection | None:
        """Return selected attempt-scoped samples from request-local prepared RFND data."""
        prepared = cls.prepare(log_data)
        return cls.select_prepared(prepared, attempt, parameter_history) if prepared is not None else None

    @classmethod
    def prepare(cls, log_data: LogData) -> _PlaneLandingRangefinderData | None:
        """Build immutable logical frames or legacy samples once for the complete log."""
        records = log_data.get_message_columns("RFND")
        if records is None or not {"TimeUS", "Dist"}.issubset(records.dtype.names or ()):
            return None
        names = records.dtype.names or ()
        if "Orient" not in names:
            return _PlaneLandingRangefinderData(legacy_samples=cls._legacy_samples(log_data))
        if "Instance" not in names:
            return None

        rows = cls._rows(log_data)
        if not rows:
            return None
        return _PlaneLandingRangefinderData(frames=cls._frames(rows))

    @classmethod
    def select_prepared(
        cls,
        prepared: _PlaneLandingRangefinderData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
    ) -> _PlaneLandingRangefinderSelection | None:
        """Select causally configured samples, degrading ambiguous frames locally."""
        if prepared.legacy_samples is not None:
            return _PlaneLandingRangefinderSelection(
                tuple(sample for sample in prepared.legacy_samples if _owns_attempt_observation(attempt, sample.time_s))
            )
        if prepared.frames is None:
            return None

        orientation_by_instance = {row[2]: row[4] for frame in prepared.frames for row in frame if row[0] < attempt.start_s}
        events: list[_RangefinderSelectionEvent] = []
        for frame in prepared.frames:
            scoped_rows = [row for row in frame if _owns_attempt_observation(attempt, row[0])]
            if not scoped_rows:
                continue
            for row in scoped_rows:
                orientation_by_instance[row[2]] = row[4]
            frame_time_s = scoped_rows[0][0]
            required_orientation = cls._integer(parameter_history.value_at(cls.LANDING_ORIENTATION_PARAMETER, frame_time_s))
            if required_orientation is None:
                events.append(_PlaneLandingRangefinderBreak(frame_time_s))
                continue

            configured_instances = {
                instance for instance, orientation in orientation_by_instance.items() if orientation == required_orientation
            }
            matching_rows = [row for row in scoped_rows if row[4] == required_orientation]
            matching_instances = {row[2] for row in matching_rows}
            if not matching_rows or matching_instances != configured_instances:
                events.append(_PlaneLandingRangefinderBreak(frame_time_s))
                continue
            if len(matching_rows) != len(matching_instances):
                events.append(_PlaneLandingRangefinderBreak(frame_time_s))
                continue

            if len(matching_rows) > 1:
                if any(row[3] is None for row in matching_rows):
                    events.append(_PlaneLandingRangefinderBreak(frame_time_s))
                    continue
                good_rows = [row for row in matching_rows if row[3] == cls.GOOD_STATUS]
                selected_row = min(good_rows or matching_rows, key=lambda row: row[2])
            else:
                selected_row = matching_rows[0]
            events.append(
                _PlaneLandingRangefinderSample(
                    time_s=selected_row[0],
                    distance_m=selected_row[1],
                    instance=selected_row[2],
                    status=selected_row[3],
                )
            )
        return _PlaneLandingRangefinderSelection(tuple(events))

    @classmethod
    def maximum_range_parameter(cls, instance: int) -> str | None:
        """Return the bounded ArduPlane 4.7 MAX parameter for ``instance``."""
        return cls.MAX_RANGE_PARAMETERS[instance] if 0 <= instance < len(cls.MAX_RANGE_PARAMETERS) else None

    @classmethod
    def _legacy_samples(
        cls,
        log_data: LogData,
    ) -> tuple[_PlaneLandingRangefinderSample, ...]:
        """Preserve instance-zero or single-stream behavior when Orient is absent."""
        records = log_data.get_message_columns("RFND")
        if records is None:
            return ()
        names = records.dtype.names or ()
        samples: list[_PlaneLandingRangefinderSample] = []
        for index, (timestamp, distance) in enumerate(
            zip(log_data.get_field("RFND", "TimeUS"), log_data.get_field("RFND", "Dist"), strict=True)
        ):
            instance = cls._integer(records["Instance"][index]) if "Instance" in names else 0
            if instance != 0:
                continue
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is None:
                continue
            status = cls._integer(records["Stat"][index]) if "Stat" in names else None
            samples.append(
                _PlaneLandingRangefinderSample(
                    time_s=timestamp_s,
                    distance_m=cls._finite_float(distance),
                    instance=0,
                    status=status,
                )
            )
        return tuple(samples)

    @classmethod
    def _rows(cls, log_data: LogData) -> list[_RangefinderRow]:
        """Return finite-timestamp RFND rows in logged order."""
        records = log_data.get_message_columns("RFND")
        if records is None:
            return []
        names = records.dtype.names or ()
        rows: list[_RangefinderRow] = []
        for index, (timestamp, distance) in enumerate(
            zip(log_data.get_field("RFND", "TimeUS"), log_data.get_field("RFND", "Dist"), strict=True)
        ):
            timestamp_s = cls._finite_float(timestamp)
            instance = cls._integer(records["Instance"][index])
            orientation = cls._integer(records["Orient"][index])
            status = cls._integer(records["Stat"][index]) if "Stat" in names else None
            if timestamp_s is None or instance is None or orientation is None:
                continue
            rows.append((timestamp_s, cls._finite_float(distance), instance, status, orientation))
        return rows

    @staticmethod
    def _frames(rows: list[_RangefinderRow]) -> tuple[_RangefinderFrame, ...]:
        """Group sequential instance-ordered RFND rows emitted by one firmware update."""
        frames: list[_RangefinderFrame] = []
        current: list[_RangefinderRow] = []
        for row in rows:
            if current and row[2] <= current[-1][2]:
                frames.append(tuple(current))
                current = []
            current.append(row)
        if current:
            frames.append(tuple(current))
        return tuple(frames)

    @staticmethod
    def _finite_float(value: object) -> float | None:
        try:
            converted = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            return None
        return converted if math.isfinite(converted) else None

    @classmethod
    def _integer(cls, value: object) -> int | None:
        converted = cls._finite_float(value)
        return int(converted) if converted is not None and converted.is_integer() else None


@dataclass(frozen=True, slots=True)
class PlaneLandingRangefinderEvidence:  # pylint: disable=too-many-instance-attributes
    """APT-compatible RFND lifecycle evidence scoped to one landing attempt."""

    attempt: PlaneLandingAttempt
    first_nonzero_time_s: float | None
    first_nonzero_distance_m: float | None
    first_in_range_time_s: float | None
    first_in_range_distance_m: float | None
    continuous_time_s: float | None
    continuous_samples: int | None
    disengagement_count: int
    last_disengagement_time_s: float | None
    last_disengagement_distance_m: float | None
    last_disengagement_status: int | None = None


class PlaneLandingRangefinderEvidenceExtractor:  # pylint: disable=too-few-public-methods,too-many-boolean-expressions,too-many-locals
    """Extract the optional attempt-scoped RFND lifecycle used by APT."""

    ZERO_THRESHOLD_M: ClassVar[float] = 0.05
    CONTINUOUS_SECONDS: ClassVar[float] = 1.0

    @classmethod
    def extract(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
    ) -> PlaneLandingRangefinderEvidence | None:
        """Return RFND lifecycle evidence, or ``None`` when scoped RFND is unusable."""
        selection = _PlaneLandingRangefinderSelector.select(log_data, attempt, parameter_history)
        return cls._extract_selected(attempt, parameter_history, selection)

    @classmethod
    def _extract_selected(  # noqa: PLR0915  # pylint: disable=too-many-statements
        cls,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
        selection: _PlaneLandingRangefinderSelection | None,
    ) -> PlaneLandingRangefinderEvidence | None:
        """Build lifecycle evidence from the same selected sequence used by stage evidence."""
        if selection is None:
            return None
        selected_samples = selection.samples
        if not selected_samples or not any(sample.distance_m is not None for sample in selected_samples):
            return None

        events = tuple(sorted(selection.events, key=lambda event: event.time_s))
        required_samples = cls._required_continuous_samples(tuple(sample.time_s for sample in selected_samples))
        first_nonzero_time_s: float | None = None
        first_nonzero_distance_m: float | None = None
        first_in_range_time_s: float | None = None
        first_in_range_distance_m: float | None = None
        continuous_time_s: float | None = None
        continuous_samples: int | None = None
        disengagement_count = 0
        last_disengagement_time_s: float | None = None
        last_disengagement_distance_m: float | None = None
        last_disengagement_status: int | None = None
        run_timestamps_s: list[float] = []
        rangefinder_active = False

        for event in events:
            if isinstance(event, _PlaneLandingRangefinderBreak):
                rangefinder_active = False
                run_timestamps_s.clear()
                continue
            sample = event
            timestamp_s = sample.time_s
            distance_m = sample.distance_m
            has_current_data = sample.status is None or sample.status in _PlaneLandingRangefinderSelector.CURRENT_DATA_STATUSES
            if not has_current_data or distance_m is None or distance_m <= cls.ZERO_THRESHOLD_M:
                if rangefinder_active:
                    disengagement_count += 1
                    last_disengagement_time_s = timestamp_s
                    last_disengagement_distance_m = None if sample.status in {0, 1} else cls._apt_distance(distance_m)
                    last_disengagement_status = sample.status
                    rangefinder_active = False
                run_timestamps_s.clear()
                continue

            rangefinder_active = True
            if first_nonzero_time_s is None:
                first_nonzero_time_s = timestamp_s
                first_nonzero_distance_m = cls._apt_distance(distance_m)

            maximum_range_parameter = _PlaneLandingRangefinderSelector.maximum_range_parameter(sample.instance)
            maximum_range_m = (
                parameter_history.value_at(maximum_range_parameter, timestamp_s)
                if maximum_range_parameter is not None
                else None
            )
            if (
                first_in_range_time_s is None
                and (sample.status is None or sample.status == _PlaneLandingRangefinderSelector.GOOD_STATUS)
                and maximum_range_m is not None
                and math.isfinite(maximum_range_m)
                and distance_m <= maximum_range_m
            ):
                first_in_range_time_s = timestamp_s
                first_in_range_distance_m = cls._apt_distance(distance_m)

            if not run_timestamps_s or timestamp_s > run_timestamps_s[-1]:
                run_timestamps_s.append(timestamp_s)
            if continuous_time_s is not None or required_samples is None or len(run_timestamps_s) < required_samples:
                continue
            qualifying_timestamps_s = run_timestamps_s[-required_samples:]
            if qualifying_timestamps_s[-1] - qualifying_timestamps_s[0] <= cls.CONTINUOUS_SECONDS:
                continuous_time_s = qualifying_timestamps_s[0]
                continuous_samples = required_samples

        return PlaneLandingRangefinderEvidence(
            attempt=attempt,
            first_nonzero_time_s=first_nonzero_time_s,
            first_nonzero_distance_m=first_nonzero_distance_m,
            first_in_range_time_s=first_in_range_time_s,
            first_in_range_distance_m=first_in_range_distance_m,
            continuous_time_s=continuous_time_s,
            continuous_samples=continuous_samples,
            disengagement_count=disengagement_count,
            last_disengagement_time_s=last_disengagement_time_s,
            last_disengagement_distance_m=last_disengagement_distance_m,
            last_disengagement_status=last_disengagement_status,
        )

    @classmethod
    def _required_continuous_samples(cls, timestamps_s: tuple[float, ...]) -> int | None:
        """Return a cadence-derived count that requires multiple observations."""
        if len(timestamps_s) < 2:
            return None
        timestamp_deltas_s = np.diff(np.asarray(timestamps_s))
        usable_deltas_s = timestamp_deltas_s[np.isfinite(timestamp_deltas_s) & (timestamp_deltas_s > 0.0)]
        if usable_deltas_s.size == 0:
            return None
        median_delta_s = float(np.median(usable_deltas_s))
        sample_rate_hz = 1.0 / median_delta_s
        return max(2, round(sample_rate_hz * cls.CONTINUOUS_SECONDS))

    @staticmethod
    def _apt_distance(distance_m: float | None) -> float | None:
        """Preserve APT's two-decimal event-detail round trip for distances."""
        return None if distance_m is None else float(f"{distance_m:.2f}")

    @staticmethod
    def _finite_float(value: object) -> float | None:
        try:
            converted = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            return None
        return converted if math.isfinite(converted) else None


@dataclass(frozen=True, slots=True)
class PlaneLandingMissionTarget:
    """One unambiguous mission LAND target applicable to a landing attempt."""

    attempt: PlaneLandingAttempt
    snapshot_completed_s: float
    latitude_deg: float
    longitude_deg: float

    def __post_init__(self) -> None:
        """Require the mission snapshot to have completed before the attempt began."""
        if self.snapshot_completed_s > self.attempt.start_s:
            msg = "Plane mission target snapshot must complete at or before the landing attempt"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PlaneLandingTargetDistanceEvidence:
    """Distance from the scoped GPS-stop position to the applicable mission LAND target."""

    attempt: PlaneLandingAttempt
    time_s: float
    aircraft_position_time_s: float
    aircraft_latitude_deg: float
    aircraft_longitude_deg: float
    target: PlaneLandingMissionTarget
    distance_m: float

    def __post_init__(self) -> None:
        """Require GPS-stop and position evidence to remain inside the associated attempt."""
        if self.attempt.end_reason is not PlaneLandingEndReason.GPS_STOP or self.time_s != self.attempt.end_s:
            msg = "Plane target-distance evidence requires the authoritative GPS-stop attempt end"
            raise ValueError(msg)
        if not self.attempt.start_s <= self.aircraft_position_time_s <= self.attempt.end_s:
            msg = "Plane target-distance position must be contained by its landing attempt"
            raise ValueError(msg)
        if self.target.attempt is not self.attempt:
            msg = "Plane mission target must be associated with the same landing attempt"
            raise ValueError(msg)


_MissionCommandRecord = tuple[float, object, object, object, object, object]


class PlaneLandingMissionTargetExtractor:
    """Reconstruct APT-compatible mission targets and GPS-stop distance evidence."""

    MAV_CMD_NAV_LAND: ClassVar[int] = 21
    EARTH_RADIUS_M: ClassVar[float] = 6_371_000.0
    _CMD_FIELDS: ClassVar[set[str]] = {"TimeUS", "CTot", "CNum", "CId", "Lat", "Lng"}

    @classmethod
    def target_for_attempt(cls, log_data: LogData, attempt: PlaneLandingAttempt) -> PlaneLandingMissionTarget | None:
        """Return the single LAND target from the latest complete applicable CMD snapshot."""
        snapshots = cls._complete_cmd_snapshots(log_data)
        applicable = [snapshot for snapshot in snapshots if snapshot[-1][0] <= attempt.start_s]
        if not applicable:
            return None

        snapshot = applicable[-1]
        land_rows: list[_MissionCommandRecord] = []
        for row in snapshot:
            command_id = cls._integer(row[3])
            if command_id is None:
                return None
            if command_id == cls.MAV_CMD_NAV_LAND:
                land_rows.append(row)
        if len(land_rows) != 1:
            return None

        latitude_deg = cls._finite_float(land_rows[0][4])
        longitude_deg = cls._finite_float(land_rows[0][5])
        if latitude_deg is None or longitude_deg is None or (latitude_deg == 0.0 and longitude_deg == 0.0):
            return None
        return PlaneLandingMissionTarget(
            attempt=attempt,
            snapshot_completed_s=snapshot[-1][0],
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
        )

    @classmethod
    def distance_at_gps_stop(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
    ) -> PlaneLandingTargetDistanceEvidence | None:
        """Return target distance when mission and attempt-scoped GPS-stop position are available."""
        if attempt.end_reason is not PlaneLandingEndReason.GPS_STOP:
            return None
        target = cls.target_for_attempt(log_data, attempt)
        if target is None:
            return None

        nearest_position = cls._nearest_gps_position(log_data, attempt, attempt.end_s)
        if nearest_position is None:
            return None

        position_time_s, aircraft_latitude_deg, aircraft_longitude_deg = nearest_position
        return PlaneLandingTargetDistanceEvidence(
            attempt=attempt,
            time_s=attempt.end_s,
            aircraft_position_time_s=position_time_s,
            aircraft_latitude_deg=aircraft_latitude_deg,
            aircraft_longitude_deg=aircraft_longitude_deg,
            target=target,
            distance_m=cls._horizontal_distance(
                target.latitude_deg,
                target.longitude_deg,
                aircraft_latitude_deg,
                aircraft_longitude_deg,
            ),
        )

    @classmethod
    def _complete_cmd_snapshots(cls, log_data: LogData) -> tuple[tuple[_MissionCommandRecord, ...], ...]:
        """Return complete consecutive CMD snapshots in timestamp order."""
        snapshots: list[tuple[_MissionCommandRecord, ...]] = []
        current: list[_MissionCommandRecord] = []
        expected_total: int | None = None
        expected_number = 0
        for row in sorted(cls._cmd_records(log_data), key=lambda record: record[0]):
            total = cls._integer(row[1])
            number = cls._integer(row[2])
            if total is None or number is None:
                current = []
                expected_total = None
                expected_number = 0
                continue

            if total <= 0 or number < 0 or number >= total:
                current = []
                expected_total = None
                expected_number = 0
                continue
            if number == 0:
                current = [row]
                expected_total = total
                expected_number = 1
            elif not current or total != expected_total or number != expected_number:
                current = []
                expected_total = None
                expected_number = 0
                continue
            else:
                current.append(row)
                expected_number += 1
            if expected_number == expected_total:
                snapshots.append(tuple(current))
                current = []
                expected_total = None
                expected_number = 0
        return tuple(snapshots)

    @classmethod
    def _cmd_records(cls, log_data: LogData) -> list[_MissionCommandRecord]:
        """Return finite-timestamp CMD fields in their scaled representation."""
        cmd = log_data.get_message_columns("CMD")
        if cmd is None or not cls._CMD_FIELDS.issubset(cmd.dtype.names or ()):
            return []

        records: list[_MissionCommandRecord] = []
        for timestamp, total, number, command_id, latitude, longitude in zip(
            log_data.get_field("CMD", "TimeUS"),
            log_data.get_field("CMD", "CTot"),
            log_data.get_field("CMD", "CNum"),
            log_data.get_field("CMD", "CId"),
            log_data.get_field("CMD", "Lat"),
            log_data.get_field("CMD", "Lng"),
            strict=True,
        ):
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is not None:
                records.append((timestamp_s, total, number, command_id, latitude, longitude))
        return records

    @classmethod
    def _nearest_gps_position(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        target_time_s: float,
    ) -> tuple[float, float, float] | None:
        """Return the nearest usable attempt-scoped GPS position."""
        gps_fields = _active_gps_fields(log_data, "TimeUS", "Lat", "Lng")
        if gps_fields is None:
            return None

        nearest_position: tuple[float, object, object] | None = None
        nearest_offset: float | None = None
        for timestamp, latitude, longitude in zip(*gps_fields, strict=True):
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is None or not _owns_attempt_observation(attempt, timestamp_s):
                continue
            offset = abs(timestamp_s - target_time_s)
            if nearest_offset is None or offset < nearest_offset:
                nearest_offset = offset
                nearest_position = (timestamp_s, latitude, longitude)
        if nearest_position is None:
            return None
        timestamp_s, latitude, longitude = nearest_position
        latitude_deg = cls._finite_float(latitude)
        longitude_deg = cls._finite_float(longitude)
        if latitude_deg is None or longitude_deg is None:
            return None
        return timestamp_s, latitude_deg, longitude_deg

    @classmethod
    def _horizontal_distance(
        cls,
        latitude_one_deg: float,
        longitude_one_deg: float,
        latitude_two_deg: float,
        longitude_two_deg: float,
    ) -> float:
        """Return the APT great-circle horizontal distance in metres."""
        latitude_one_rad = math.radians(latitude_one_deg)
        latitude_two_rad = math.radians(latitude_two_deg)
        delta_latitude = math.radians(latitude_two_deg - latitude_one_deg)
        delta_longitude = math.radians(longitude_two_deg - longitude_one_deg)
        haversine = (
            math.sin(delta_latitude / 2.0) ** 2
            + math.cos(latitude_one_rad) * math.cos(latitude_two_rad) * math.sin(delta_longitude / 2.0) ** 2
        )
        central_angle = 2.0 * math.atan2(math.sqrt(haversine), math.sqrt(1.0 - haversine))
        return cls.EARTH_RADIUS_M * central_angle

    @staticmethod
    def _finite_float(value: object) -> float | None:
        try:
            converted = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            return None
        return converted if math.isfinite(converted) else None

    @staticmethod
    def _integer(value: object) -> int | None:
        try:
            converted: int = int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError, OverflowError):
            return None
        return converted


class PlaneLandingEvidenceExtractor:  # pylint: disable=too-many-locals
    """Collect APT-compatible stage and nearest-telemetry evidence for one attempt."""

    BARO_RATE_HALF_WINDOW_S: ClassVar[float] = 0.5

    _PARAMETERS_BY_STAGE: ClassVar[dict[PlaneLandingStage, tuple[str, ...]]] = {
        PlaneLandingStage.PREFLARE: ("LAND_PF_ALT", "LAND_PF_SEC"),
        PlaneLandingStage.FLARE: ("LAND_FLARE_ALT", "LAND_FLARE_SEC", "LAND_PITCH_DEG"),
    }

    @classmethod
    def start_of_final_altitude_m(cls, log_data: LogData, attempt: PlaneLandingAttempt) -> float | None:
        """Return nearest attempt-scoped BARO altitude at the start of final approach."""
        return cls._nearest_value(log_data, attempt, ("BARO", "Alt"), attempt.start_s)

    @classmethod
    def extract(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
    ) -> tuple[PlaneLandingStageEvidence, ...]:
        """Return the first preflare and flare transitions found inside ``attempt``."""
        rangefinder_selection = _PlaneLandingRangefinderSelector.select(log_data, attempt, parameter_history)
        return cls._extract_selected(log_data, attempt, parameter_history, rangefinder_selection)

    @classmethod
    def extract_attempts(
        cls,
        log_data: LogData,
        attempts: tuple[PlaneLandingAttempt, ...],
        parameter_history: ParameterHistory,
    ) -> tuple[tuple[tuple[PlaneLandingStageEvidence, ...], PlaneLandingRangefinderEvidence | None], ...]:
        """Prepare RFND once and reuse one selected sequence per attempt."""
        prepared = _PlaneLandingRangefinderSelector.prepare(log_data)
        evidence: list[tuple[tuple[PlaneLandingStageEvidence, ...], PlaneLandingRangefinderEvidence | None]] = []
        for attempt in attempts:
            selection = (
                _PlaneLandingRangefinderSelector.select_prepared(prepared, attempt, parameter_history)
                if prepared is not None
                else None
            )
            evidence.append(
                (
                    cls._extract_selected(log_data, attempt, parameter_history, selection),
                    PlaneLandingRangefinderEvidenceExtractor._extract_selected(  # noqa: SLF001  # pylint: disable=protected-access
                        attempt,
                        parameter_history,
                        selection,
                    ),
                )
            )
        return tuple(evidence)

    @classmethod
    def _extract_selected(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
        rangefinder_selection: _PlaneLandingRangefinderSelection | None,
    ) -> tuple[PlaneLandingStageEvidence, ...]:
        """Build stage evidence from a preselected attempt-scoped RFND sequence."""
        return tuple(
            cls._build_stage_evidence(log_data, attempt, parameter_history, rangefinder_selection, transition)
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
            if not _owns_attempt_observation(attempt, timestamp_s):
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
    def _build_stage_evidence(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
        rangefinder_selection: _PlaneLandingRangefinderSelection | None,
        transition: tuple[PlaneLandingStage, float, float | None],
    ) -> PlaneLandingStageEvidence:
        stage, time_s, flight_height_m = transition
        rangefinder_distance_m, rangefinder_status = cls._nearest_rangefinder_observation(
            rangefinder_selection.samples if rangefinder_selection is not None else None,
            time_s,
        )
        return PlaneLandingStageEvidence(
            attempt=attempt,
            stage=stage,
            time_s=time_s,
            flight_height_m=flight_height_m,
            airspeed_m_s=cls._nearest_value(log_data, attempt, ("ARSP", "Airspeed"), time_s),
            gps_ground_speed_m_s=cls._nearest_value(log_data, attempt, ("GPS", "Spd"), time_s),
            barometric_altitude_m=cls._nearest_value(log_data, attempt, ("BARO", "Alt"), time_s),
            barometric_sink_rate_m_s=(
                cls._barometric_sink_rate(log_data, attempt, time_s) if stage is PlaneLandingStage.PREFLARE else None
            ),
            rangefinder_distance_m=rangefinder_distance_m,
            rangefinder_status=rangefinder_status,
            flare_to_gps_stop_s=(
                attempt.end_s - time_s
                if stage is PlaneLandingStage.FLARE
                and attempt.end_reason is PlaneLandingEndReason.GPS_STOP
                and time_s <= attempt.end_s
                else None
            ),
            parameter_values={
                parameter_name: cls._finite_float(parameter_history.value_at(parameter_name, time_s))
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
        message_name = telemetry_field[0]
        records = log_data.get_message_columns(message_name)
        if records is None or not {"TimeUS", telemetry_field[1]}.issubset(records.dtype.names or ()):
            return None

        if message_name == "ARSP":
            return cls._nearest_primary_arsp_value(log_data, attempt, telemetry_field[1], target_time_s)
        if message_name == "GPS":
            telemetry_fields = _active_gps_fields(log_data, "TimeUS", telemetry_field[1])
        elif message_name == "BARO":
            telemetry_fields = _instance_zero_fields(log_data, "BARO", "I", "TimeUS", telemetry_field[1])
        else:
            telemetry_fields = (
                log_data.get_field(message_name, "TimeUS"),
                log_data.get_field(message_name, telemetry_field[1]),
            )
        if telemetry_fields is None:
            return None

        nearest_value: object | None = None
        nearest_offset: float | None = None
        for timestamp, value in zip(*telemetry_fields, strict=True):
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is None or not _owns_attempt_observation(attempt, timestamp_s):
                continue
            offset = abs(timestamp_s - target_time_s)
            if nearest_offset is None or offset < nearest_offset:
                nearest_offset = offset
                nearest_value = value
        return cls._finite_float(nearest_value)

    @classmethod
    def _nearest_rangefinder_observation(
        cls,
        selected_samples: tuple[_PlaneLandingRangefinderSample, ...] | None,
        target_time_s: float,
    ) -> tuple[float | None, int | None]:
        """Return the nearest firmware-selected RFND observation and status."""
        if not selected_samples:
            return None, None
        nearest_sample = min(selected_samples, key=lambda sample: abs(sample.time_s - target_time_s))
        if (
            nearest_sample.status is not None
            and nearest_sample.status not in _PlaneLandingRangefinderSelector.CURRENT_DATA_STATUSES
        ):
            return None, nearest_sample.status
        return nearest_sample.distance_m, nearest_sample.status

    @classmethod
    def _nearest_primary_arsp_value(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        field_name: str,
        target_time_s: float,
    ) -> float | None:
        """Return nearest usable primary ARSP value without falling back to another sensor."""
        records = log_data.get_message_columns("ARSP")
        if records is None:
            return None
        names = records.dtype.names or ()
        selector_fields = {"I", "H", "Pri"}
        present_selectors = selector_fields.intersection(names)
        if not present_selectors:
            return cls._nearest_unselected_arsp_value(log_data, attempt, field_name, target_time_s)
        if not selector_fields.issubset(names):
            return None

        grouped_rows: dict[float, list[tuple[object, object, object, object]]] = {}
        for timestamp, value, instance, healthy, primary in zip(
            log_data.get_field("ARSP", "TimeUS"),
            log_data.get_field("ARSP", field_name),
            log_data.get_field("ARSP", "I"),
            log_data.get_field("ARSP", "H"),
            log_data.get_field("ARSP", "Pri"),
            strict=True,
        ):
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is not None and _owns_attempt_observation(attempt, timestamp_s):
                grouped_rows.setdefault(timestamp_s, []).append((value, instance, healthy, primary))

        if not grouped_rows:
            return None
        _timestamp_s, rows = min(grouped_rows.items(), key=lambda frame: abs(frame[0] - target_time_s))
        return cls._primary_arsp_frame_value(rows)

    @classmethod
    def _primary_arsp_frame_value(cls, rows: list[tuple[object, object, object, object]]) -> float | None:
        """Return the usable primary value from one already-selected ARSP frame."""
        instances = tuple(cls._selector_integer(row[1]) for row in rows)
        if any(instance is None for instance in instances):
            return None
        primary_instances = {cls._selector_integer(row[3]) for row in rows}
        if None in primary_instances or len(primary_instances) != 1:
            return None
        primary_instance = next(iter(primary_instances))
        primary_rows = [row for row, instance in zip(rows, instances, strict=True) if instance == primary_instance]
        if len(primary_rows) != 1:
            return None
        value, _instance, healthy, _primary = primary_rows[0]
        healthy_value = cls._finite_float(healthy)
        if healthy_value is None or healthy_value == 0.0:
            return None
        return cls._finite_float(value)

    @classmethod
    def _nearest_unselected_arsp_value(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        field_name: str,
        target_time_s: float,
    ) -> float | None:
        candidates: list[tuple[float, object]] = []
        for timestamp, value in zip(
            log_data.get_field("ARSP", "TimeUS"),
            log_data.get_field("ARSP", field_name),
            strict=True,
        ):
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is not None and _owns_attempt_observation(attempt, timestamp_s):
                candidates.append((timestamp_s, value))
        return cls._nearest_candidate_value(candidates, target_time_s)

    @classmethod
    def _nearest_candidate_value(cls, candidates: list[tuple[float, object]], target_time_s: float) -> float | None:
        if not candidates:
            return None
        return cls._finite_float(min(candidates, key=lambda sample: abs(sample[0] - target_time_s))[1])

    @classmethod
    def _selector_integer(cls, value: object) -> int | None:
        converted = cls._finite_float(value)
        return int(converted) if converted is not None and converted.is_integer() else None

    @classmethod
    def _barometric_sink_rate(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        target_time_s: float,
    ) -> float | None:
        """Return the APT-compatible local preflare sink rate, positive while descending."""
        baro_fields = _instance_zero_fields(log_data, "BARO", "I", "TimeUS", "Alt")
        if baro_fields is None:
            return None
        timestamps, altitudes = baro_fields

        start_s = max(attempt.start_s, target_time_s - cls.BARO_RATE_HALF_WINDOW_S)
        end_s = min(attempt.end_s, target_time_s + cls.BARO_RATE_HALF_WINDOW_S)
        scoped_samples: list[tuple[float, float]] = []
        for timestamp, altitude in zip(timestamps, altitudes, strict=True):
            timestamp_s = cls._finite_float(timestamp)
            altitude_m = cls._finite_float(altitude)
            if (
                timestamp_s is None
                or altitude_m is None
                or not start_s <= timestamp_s <= end_s
                or not _owns_attempt_observation(attempt, timestamp_s)
            ):
                continue
            scoped_samples.append((timestamp_s, altitude_m))

        if len(scoped_samples) < 2:
            return None
        first_sample = scoped_samples[0]
        last_sample = scoped_samples[-1]
        elapsed_s = last_sample[0] - first_sample[0]
        if elapsed_s <= 0:
            return None
        return -(last_sample[1] - first_sample[1]) / elapsed_s

    @staticmethod
    def _finite_float(value: object) -> float | None:
        try:
            converted = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return converted if math.isfinite(converted) else None
