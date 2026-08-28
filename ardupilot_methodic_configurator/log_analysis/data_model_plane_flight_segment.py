"""
ArduPlane operational-flight segmentation over AMC-native scaled log data.

The thresholds are inherited reference heuristics from ArduPilotTools. They
are not universal ArduPlane flight semantics.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math
from typing import ClassVar

import numpy as np

from ardupilot_methodic_configurator.log_analysis.data_model_flight_segment import (
    FlightSegment,
    FlightSegmentationResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData


class PlaneFlightSegmentDetector:  # pylint: disable=too-few-public-methods
    """
    Detect Plane flights from persistent GPS groundspeed evidence.

    When the GPS schema provides the ``U`` flag, only samples from the active
    receiver are used. Older schemas without that flag use all GPS records.
    """

    MINIMUM_SPEED_M_S: ClassVar[float] = 5.0
    STALL_SPEED_MULTIPLIER: ClassVar[float] = 0.5
    START_PERSISTENCE_S: ClassVar[float] = 2.0
    GROUND_PERSISTENCE_S: ClassVar[float] = 30.0

    @classmethod
    def detect(cls, log_data: LogData, parameters: dict[str, float]) -> FlightSegmentationResult:
        """Return operational Plane segments, using scaled GPS times in seconds."""
        gps = log_data.get_message_columns("GPS")
        if gps is None or len(gps) == 0:
            return FlightSegmentationResult(available=False, reason="GPS messages are unavailable")

        field_names = gps.dtype.names or ()
        missing_fields = [field_name for field_name in ("TimeUS", "Spd") if field_name not in field_names]
        if missing_fields:
            return FlightSegmentationResult(
                available=False,
                reason=f"GPS fields are unavailable: {', '.join(missing_fields)}",
            )

        time_s = log_data.get_field("GPS", "TimeUS")
        speed_m_s = log_data.get_field("GPS", "Spd")
        if "U" in field_names:
            active_receiver_samples = log_data.get_field("GPS", "U") == 1
            time_s = time_s[active_receiver_samples]
            speed_m_s = speed_m_s[active_receiver_samples]
        if not cls._usable_gps_values(time_s, speed_m_s):
            return FlightSegmentationResult(available=False, reason="GPS time or groundspeed values are unusable")

        threshold_m_s = cls._effective_speed_threshold(parameters)
        segments = cls._detect_segments(time_s, speed_m_s, threshold_m_s)
        return FlightSegmentationResult(available=True, segments=tuple(segments))

    @staticmethod
    def _usable_gps_values(time_s: np.ndarray, speed_m_s: np.ndarray) -> bool:
        """Check required GPS evidence without inventing replacements for invalid samples."""
        return (
            len(time_s) == len(speed_m_s)
            and len(time_s) > 0
            and np.issubdtype(time_s.dtype, np.number)
            and np.issubdtype(speed_m_s.dtype, np.number)
            and bool(np.isfinite(time_s).all())
            and bool(np.isfinite(speed_m_s).all())
        )

    @classmethod
    def _effective_speed_threshold(cls, parameters: dict[str, float]) -> float:
        """Return the minimum threshold, raised by half stall speed when usable."""
        stall_speed = parameters.get("AIRSPEED_STALL")
        if stall_speed is None or not math.isfinite(stall_speed):
            return cls.MINIMUM_SPEED_M_S
        return max(cls.MINIMUM_SPEED_M_S, cls.STALL_SPEED_MULTIPLIER * stall_speed)

    @classmethod
    def _detect_segments(
        cls,
        time_s: np.ndarray,
        speed_m_s: np.ndarray,
        threshold_m_s: float,
    ) -> list[FlightSegment]:
        """Apply the reference Plane persistence state machine."""
        segments: list[FlightSegment] = []
        flight_start_index: int | None = None
        start_candidate_index: int | None = None
        ground_candidate_index: int | None = None

        for index, (timestamp_s, speed) in enumerate(zip(time_s, speed_m_s, strict=True)):
            above_threshold = speed > threshold_m_s

            if flight_start_index is None:
                if above_threshold:
                    if start_candidate_index is None:
                        start_candidate_index = index
                    if timestamp_s - time_s[start_candidate_index] >= cls.START_PERSISTENCE_S:
                        flight_start_index = start_candidate_index
                        start_candidate_index = None
                        ground_candidate_index = None
                else:
                    start_candidate_index = None
                continue

            if above_threshold:
                ground_candidate_index = None
                continue

            if ground_candidate_index is None:
                ground_candidate_index = index

            if timestamp_s - time_s[ground_candidate_index] >= cls.GROUND_PERSISTENCE_S:
                segments.append(
                    FlightSegment(
                        start_s=float(time_s[flight_start_index]),
                        end_s=float(time_s[ground_candidate_index - 1]),
                        is_complete=True,
                    )
                )
                flight_start_index = None
                start_candidate_index = None
                ground_candidate_index = None

        if flight_start_index is not None:
            segments.append(
                FlightSegment(
                    start_s=float(time_s[flight_start_index]),
                    end_s=float(time_s[-1]),
                    is_complete=False,
                )
            )

        return segments
