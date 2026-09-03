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

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping

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
    gps_ground_speed_m_s: float | None = None
    barometric_altitude_m: float | None = None
    barometric_sink_rate_m_s: float | None = None
    rangefinder_distance_m: float | None = None
    flare_to_gps_stop_s: float | None = None
    parameter_values: Mapping[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Require the event to lie inside its attempt and freeze parameter evidence."""
        if not self.attempt.start_s <= self.time_s <= self.attempt.end_s:
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
    airspeed_m_s: float
    distance_to_target_m: float

    def __post_init__(self) -> None:
        """Require the firmware message to lie inside its landing attempt."""
        if not self.attempt.start_s <= self.time_s <= self.attempt.end_s:
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
        if not self.attempt.start_s <= self.time_s <= self.attempt.end_s:
            msg = "Plane firmware glide-slope evidence must be contained by its landing attempt"
            raise ValueError(msg)


PlaneLandingFirmwareEvidence = PlaneLandingFirmwareFlareEvidence | PlaneLandingFirmwareGlideSlopeEvidence


class PlaneLandingFirmwareMessageExtractor:  # pylint: disable=too-few-public-methods
    """Parse the first complete APT-recognized firmware messages inside one attempt."""

    _FLARE_PREFIX: ClassVar[str] = "Flare "
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
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is not None and attempt.start_s <= timestamp_s <= attempt.end_s:
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
        return tuple(sorted(evidence, key=lambda item: item.time_s))

    @classmethod
    def _parse_flare(
        cls,
        attempt: PlaneLandingAttempt,
        timestamp_s: float,
        message: str,
    ) -> PlaneLandingFirmwareFlareEvidence | None:
        altitude_m = cls._prefixed_value(message, cls._FLARE_PREFIX, "m")
        sink_rate_m_s = cls._named_value(message, "sink=")
        airspeed_m_s = cls._named_value(message, "speed=")
        distance_to_target_m = cls._named_value(message, "dist=")
        if altitude_m is None or sink_rate_m_s is None or airspeed_m_s is None or distance_to_target_m is None:
            return None
        return PlaneLandingFirmwareFlareEvidence(
            attempt=attempt,
            time_s=timestamp_s,
            altitude_m=altitude_m,
            sink_rate_m_s=sink_rate_m_s,
            airspeed_m_s=airspeed_m_s,
            distance_to_target_m=distance_to_target_m,
        )

    @classmethod
    def _parse_glide_slope(
        cls,
        attempt: PlaneLandingAttempt,
        timestamp_s: float,
        message: str,
    ) -> PlaneLandingFirmwareGlideSlopeEvidence | None:
        glide_slope_degrees = cls._prefixed_value(message, cls._GLIDE_SLOPE_PREFIX, " degrees")
        if glide_slope_degrees is None:
            return None
        return PlaneLandingFirmwareGlideSlopeEvidence(
            attempt=attempt,
            time_s=timestamp_s,
            glide_slope_degrees=glide_slope_degrees,
        )

    @classmethod
    def _prefixed_value(cls, text: str, prefix: str, suffix: str) -> float | None:
        if not text.startswith(prefix):
            return None
        value_text = text[len(prefix) :]
        suffix_index = value_text.find(suffix)
        if suffix_index < 0:
            return None
        return cls._finite_float(value_text[:suffix_index].strip())

    @classmethod
    def _named_value(cls, text: str, name: str) -> float | None:
        name_index = text.find(name)
        if name_index < 0:
            return None
        value_parts = text[name_index + len(name) :].split()
        return cls._finite_float(value_parts[0]) if value_parts else None

    @staticmethod
    def _finite_float(value: object) -> float | None:
        try:
            converted = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return converted if math.isfinite(converted) else None


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


class PlaneLandingRangefinderEvidenceExtractor:  # pylint: disable=too-few-public-methods,too-many-locals
    """Extract the optional attempt-scoped RFND lifecycle used by APT."""

    ZERO_THRESHOLD_M: ClassVar[float] = 0.05
    CONTINUOUS_SECONDS: ClassVar[float] = 1.0
    MAX_RANGE_PARAMETER: ClassVar[str] = "RNGFND1_MAX"

    @classmethod
    def extract(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        parameter_history: ParameterHistory,
    ) -> PlaneLandingRangefinderEvidence | None:
        """Return RFND lifecycle evidence, or ``None`` when scoped RFND is unusable."""
        records = log_data.get_message_columns("RFND")
        if records is None or not {"TimeUS", "Dist"}.issubset(records.dtype.names or ()):
            return None

        samples: list[tuple[float, float | None]] = []
        for timestamp, distance in zip(
            log_data.get_field("RFND", "TimeUS"),
            log_data.get_field("RFND", "Dist"),
            strict=True,
        ):
            timestamp_s = cls._finite_float(timestamp)
            if timestamp_s is None or not attempt.start_s <= timestamp_s <= attempt.end_s:
                continue
            samples.append((timestamp_s, cls._finite_float(distance)))

        if not samples or not any(distance_m is not None for _, distance_m in samples):
            return None

        required_samples = cls._required_continuous_samples(tuple(timestamp_s for timestamp_s, _ in samples))
        first_nonzero_time_s: float | None = None
        first_nonzero_distance_m: float | None = None
        first_in_range_time_s: float | None = None
        first_in_range_distance_m: float | None = None
        continuous_time_s: float | None = None
        continuous_samples: int | None = None
        disengagement_count = 0
        last_disengagement_time_s: float | None = None
        last_disengagement_distance_m: float | None = None
        run_start_time_s: float | None = None
        run_samples = 0
        rangefinder_active = False

        for timestamp_s, distance_m in samples:
            if distance_m is None or distance_m <= cls.ZERO_THRESHOLD_M:
                if rangefinder_active:
                    disengagement_count += 1
                    last_disengagement_time_s = timestamp_s
                    last_disengagement_distance_m = cls._apt_distance(distance_m)
                    rangefinder_active = False
                run_start_time_s = None
                run_samples = 0
                continue

            rangefinder_active = True
            if first_nonzero_time_s is None:
                first_nonzero_time_s = timestamp_s
                first_nonzero_distance_m = cls._apt_distance(distance_m)

            maximum_range_m = parameter_history.value_at(cls.MAX_RANGE_PARAMETER, timestamp_s)
            if (
                first_in_range_time_s is None
                and maximum_range_m is not None
                and math.isfinite(maximum_range_m)
                and distance_m <= maximum_range_m
            ):
                first_in_range_time_s = timestamp_s
                first_in_range_distance_m = cls._apt_distance(distance_m)

            if run_samples == 0:
                run_start_time_s = timestamp_s
                run_samples = 1
            else:
                run_samples += 1

            if continuous_time_s is None and run_samples >= required_samples:
                continuous_time_s = run_start_time_s
                continuous_samples = run_samples

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
        )

    @classmethod
    def _required_continuous_samples(cls, timestamps_s: tuple[float, ...]) -> int:
        """Apply APT's median-delta sample-rate estimate and rounded count."""
        if len(timestamps_s) < 2:
            return 1
        median_delta_s = float(np.median(np.diff(np.asarray(timestamps_s))))
        if not math.isfinite(median_delta_s) or median_delta_s <= 0.0:
            return 1
        sample_rate_hz = 1.0 / median_delta_s
        return max(1, round(sample_rate_hz * cls.CONTINUOUS_SECONDS))

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

        nearest_position = cls._nearest_gps_position(log_data, attempt.end_s)
        if nearest_position is None:
            return None

        position_time_s, aircraft_latitude_deg, aircraft_longitude_deg = nearest_position
        if not attempt.start_s <= position_time_s <= attempt.end_s:
            return None
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
    def _nearest_gps_position(cls, log_data: LogData, target_time_s: float) -> tuple[float, float, float] | None:
        """Return the nearest finite GPS position to the supplied time."""
        gps = log_data.get_message_columns("GPS")
        if gps is None or not {"TimeUS", "Lat", "Lng"}.issubset(gps.dtype.names or ()):
            return None

        nearest_position: tuple[float, float, float] | None = None
        nearest_offset: float | None = None
        for timestamp, latitude, longitude in zip(
            log_data.get_field("GPS", "TimeUS"),
            log_data.get_field("GPS", "Lat"),
            log_data.get_field("GPS", "Lng"),
            strict=True,
        ):
            timestamp_s = cls._finite_float(timestamp)
            latitude_deg = cls._finite_float(latitude)
            longitude_deg = cls._finite_float(longitude)
            if timestamp_s is None or latitude_deg is None or longitude_deg is None:
                continue
            offset = abs(timestamp_s - target_time_s)
            if nearest_offset is None or offset < nearest_offset:
                nearest_offset = offset
                nearest_position = (timestamp_s, latitude_deg, longitude_deg)
        return nearest_position

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


class PlaneLandingEvidenceExtractor:  # pylint: disable=too-few-public-methods
    """Collect APT-compatible stage and nearest-telemetry evidence for one attempt."""

    BARO_RATE_HALF_WINDOW_S: ClassVar[float] = 0.5

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
            gps_ground_speed_m_s=cls._nearest_value(log_data, attempt, ("GPS", "Spd"), time_s),
            barometric_altitude_m=cls._nearest_value(log_data, attempt, ("BARO", "Alt"), time_s),
            barometric_sink_rate_m_s=(
                cls._barometric_sink_rate(log_data, attempt, time_s) if stage is PlaneLandingStage.PREFLARE else None
            ),
            rangefinder_distance_m=cls._nearest_value(log_data, attempt, ("RFND", "Dist"), time_s),
            flare_to_gps_stop_s=(
                attempt.end_s - time_s
                if stage is PlaneLandingStage.FLARE
                and attempt.end_reason is PlaneLandingEndReason.GPS_STOP
                and time_s <= attempt.end_s
                else None
            ),
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

    @classmethod
    def _barometric_sink_rate(
        cls,
        log_data: LogData,
        attempt: PlaneLandingAttempt,
        target_time_s: float,
    ) -> float | None:
        """Return the APT-compatible local preflare sink rate, positive while descending."""
        records = log_data.get_message_columns("BARO")
        if records is None or not {"TimeUS", "Alt"}.issubset(records.dtype.names or ()):
            return None

        start_s = max(attempt.start_s, target_time_s - cls.BARO_RATE_HALF_WINDOW_S)
        end_s = min(attempt.end_s, target_time_s + cls.BARO_RATE_HALF_WINDOW_S)
        scoped_samples: list[tuple[float, float]] = []
        for timestamp, altitude in zip(
            log_data.get_field("BARO", "TimeUS"),
            log_data.get_field("BARO", "Alt"),
            strict=True,
        ):
            timestamp_s = cls._finite_float(timestamp)
            altitude_m = cls._finite_float(altitude)
            if timestamp_s is None or altitude_m is None or not start_s <= timestamp_s <= end_s:
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
