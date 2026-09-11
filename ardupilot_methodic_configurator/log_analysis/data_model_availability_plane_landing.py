"""
Availability and objective analysis for ArduPlane landing attempts.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.formatting import format_elapsed_time
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    BaseLogAnalysisModel,
    BaseLogAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import (
    AvailabilityIssue,
    LogAvailabilityResult,
    LogAvailabilityState,
)
from ardupilot_methodic_configurator.log_analysis.data_model_plane_flight_segment import PlaneFlightSegmentDetector
from ardupilot_methodic_configurator.log_analysis.data_model_plane_landing import (
    PlaneLandingAttempt,
    PlaneLandingAttemptDetector,
    PlaneLandingEndReason,
    PlaneLandingEvidenceExtractor,
    PlaneLandingFirmwareEvidence,
    PlaneLandingFirmwareFlareEvidence,
    PlaneLandingFirmwareGlideSlopeEvidence,
    PlaneLandingFirmwareMessageExtractor,
    PlaneLandingMissionTargetExtractor,
    PlaneLandingRangefinderEvidence,
    PlaneLandingStage,
    PlaneLandingStageEvidence,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
    from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterHistory

_REQUIRED_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("GPS", ("TimeUS", "Spd")),
    ("BARO", ("TimeUS", "Alt")),
    ("LAND", ("TimeUS", "stage")),
    ("MODE", ("TimeUS", "ModeNum")),
)

_RFND_STATUS_NAMES: dict[int, str] = {
    0: "NotConnected",
    1: "NoData",
    2: "OutOfRangeLow",
    3: "OutOfRangeHigh",
    4: "Good",
}


class PlaneLandingAvailabilityModel(BaseLogAvailabilityModel):
    """Limit landing analysis to ArduPlane 4.7.x logs with required evidence."""

    def check(self) -> LogAvailabilityResult:
        """Validate identity, firmware, required fields, and operational-flight scope."""
        if self.log_data.vehicle_type != "ArduPlane":
            return self._unavailable(
                _("Plane landing analysis is available only for ArduPlane logs"),
                _("Log vehicle type is not ArduPlane"),
            )

        firmware_version = self.log_data.firmware_version
        if firmware_version is None or firmware_version[:2] != (4, 7):
            return self._unavailable(
                _("Plane landing analysis currently supports ArduPlane 4.7.x only"),
                _("Log firmware is not ArduPlane 4.7.x"),
            )

        issues = self._required_evidence_issues()
        if issues:
            return LogAvailabilityResult(
                available=False,
                state=LogAvailabilityState.WARNING,
                reason=_("Required Plane landing-attempt evidence is unavailable"),
                issues=issues,
                name=_("Plane Landing"),
            )

        segmentation = PlaneFlightSegmentDetector.detect(self.log_data, self.parameters)
        if not segmentation.available:
            return self._unavailable(
                _("Operational Plane flight segmentation is unavailable: {reason}").format(reason=segmentation.reason),
                _("No usable operational Plane flight scope"),
            )
        if not segmentation.segments:
            return self._unavailable(
                _("No operational Plane flight segments were detected"),
                _("No operational Plane flight scope contains landing evidence"),
            )

        return LogAvailabilityResult(
            available=True,
            state=LogAvailabilityState.INFO,
            reason=_("Plane landing-attempt data present and good for analysis"),
            issues=[],
            name=_("Plane Landing"),
        )

    def _required_evidence_issues(self) -> list[AvailabilityIssue]:
        issues: list[AvailabilityIssue] = []
        for message_name, field_names in _REQUIRED_FIELDS:
            records = self.log_data.get_message_columns(message_name)
            if records is None or len(records) == 0:
                issues.append(AvailabilityIssue(_("No {message} messages found").format(message=message_name)))
                continue
            issues.extend(self.check_fields_present(message_name, field_names))
        return issues

    @staticmethod
    def _unavailable(reason: str, issue: str) -> LogAvailabilityResult:
        return LogAvailabilityResult(
            available=False,
            state=LogAvailabilityState.WARNING,
            reason=reason,
            issues=[AvailabilityIssue(issue)],
            name=_("Plane Landing"),
        )


class PlaneLandingAnalysis(BaseLogAnalysisModel):
    """Report objective landing-attempt boundaries and time-scoped parameters."""

    def __init__(self, log_data: LogData, context: LogAnalysisContext) -> None:
        super().__init__(log_data, context)
        self.parameter_history: ParameterHistory = context.parameter_history

    def analyse(self) -> LogAnalysisResult:
        """Detect attempts within every operational flight and flatten them into AMC results."""
        segmentation = PlaneFlightSegmentDetector.detect(self.log_data, self.parameters)
        if not segmentation.available:
            return LogAnalysisResult(
                available=False,
                outcomes=[],
                name=_("Plane Landing Analysis"),
                reason=_("Operational Plane flight segmentation is unavailable"),
            )

        attempts = tuple(
            attempt
            for flight_segment in segmentation.segments
            for attempt in PlaneLandingAttemptDetector.detect(self.log_data, flight_segment)
        )
        evidence_by_attempt = PlaneLandingEvidenceExtractor.extract_attempts(
            self.log_data,
            attempts,
            self.parameter_history,
        )
        outcomes: list[LogAnalysis] = []
        for attempt_number, (attempt, attempt_evidence) in enumerate(
            zip(attempts, evidence_by_attempt, strict=True),
            start=1,
        ):
            stage_evidence_items, rangefinder_evidence = attempt_evidence
            firmware_evidence_items = PlaneLandingFirmwareMessageExtractor.extract(self.log_data, attempt)
            outcomes.append(self._attempt_outcome(attempt_number, attempt))
            outcomes.append(self._start_of_final_altitude_outcome(attempt_number, attempt))
            for firmware_evidence in firmware_evidence_items:
                if isinstance(firmware_evidence, PlaneLandingFirmwareGlideSlopeEvidence):
                    outcomes.extend(self._firmware_message_outcomes(attempt_number, firmware_evidence))
            for stage_evidence in stage_evidence_items:
                outcomes.extend(self._stage_outcomes(attempt_number, stage_evidence))
            for firmware_evidence in firmware_evidence_items:
                if not isinstance(firmware_evidence, PlaneLandingFirmwareGlideSlopeEvidence):
                    outcomes.extend(self._firmware_message_outcomes(attempt_number, firmware_evidence))
            if rangefinder_evidence is not None:
                outcomes.extend(self._rangefinder_outcomes(attempt_number, rangefinder_evidence))
            target_distance = PlaneLandingMissionTargetExtractor.distance_at_gps_stop(self.log_data, attempt)
            if target_distance is not None:
                outcomes.append(
                    self._measurement_outcome(
                        round(target_distance.time_s * 1_000_000),
                        (_("Computed distance to mission LAND target"), target_distance.distance_m, _("m")),
                        group=self._group_label(attempt_number, _("Mission-target evidence")),
                    )
                )
        reason = (
            _("Detected {count} Plane landing attempt(s)").format(count=len(attempts))
            if attempts
            else _("No Plane landing attempts detected")
        )
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Plane Landing Analysis"),
            reason=reason,
        )

    def _attempt_outcome(self, attempt_number: int, attempt: PlaneLandingAttempt) -> LogAnalysis:
        flare_altitude_m = self._finite_parameter_value(self.parameter_history.value_at("LAND_FLARE_ALT", attempt.start_s))
        mode_name = self._mode_name(attempt.mode_number)
        parameter_evidence = (
            _("LAND_FLARE_ALT at start: {value:.1f} m").format(value=flare_altitude_m)
            if flare_altitude_m is not None
            else _("LAND_FLARE_ALT at start: unavailable")
        )
        return LogAnalysis(
            message=_("{mode_name} landing: {start} → {end}\nTermination: {end_reason}\n{parameter_evidence}").format(
                mode_name=mode_name,
                start=format_elapsed_time(attempt.start_s),
                end=format_elapsed_time(attempt.end_s),
                end_reason=self._end_reason_text(attempt.end_reason),
                parameter_evidence=parameter_evidence,
            ),
            timestamp_us=round(attempt.start_s * 1_000_000),
            value=flare_altitude_m,
            group=self._group_label(attempt_number, _("Summary")),
        )

    def _start_of_final_altitude_outcome(self, attempt_number: int, attempt: PlaneLandingAttempt) -> LogAnalysis:
        altitude_m = PlaneLandingEvidenceExtractor.start_of_final_altitude_m(self.log_data, attempt)
        group = self._group_label(attempt_number, _("Summary"))
        timestamp_us = round(attempt.start_s * 1_000_000)
        if altitude_m is not None:
            return self._measurement_outcome(
                timestamp_us,
                (_("Start-of-final altitude"), altitude_m, _("m")),
                group=group,
            )
        return LogAnalysis(
            message=_("Start-of-final altitude: unavailable"),
            timestamp_us=timestamp_us,
            group=group,
        )

    def _stage_outcomes(self, attempt_number: int, evidence: PlaneLandingStageEvidence) -> list[LogAnalysis]:
        group_name = _("Preflare") if evidence.stage is PlaneLandingStage.PREFLARE else _("Flare")
        group = self._group_label(attempt_number, group_name)
        timestamp_us = round(evidence.time_s * 1_000_000)
        outcomes = [
            LogAnalysis(
                message=_("LAND stage {stage} entered").format(stage=int(evidence.stage)),
                timestamp_us=timestamp_us,
                value=float(evidence.stage),
                group=group,
            )
        ]
        measurements = (
            (evidence.flight_height_m, _("LAND flight height"), _("m")),
            (evidence.airspeed_m_s, _("ARSP airspeed"), _("m/s")),
            (evidence.gps_ground_speed_m_s, _("GPS groundspeed"), _("m/s")),
            (evidence.barometric_altitude_m, _("BARO altitude"), _("m")),
            (evidence.barometric_sink_rate_m_s, _("BARO sink rate"), _("m/s")),
            (evidence.rangefinder_distance_m, _("RFND distance"), _("m")),
            (evidence.flare_to_gps_stop_s, _("Flare to GPS stop"), _("s")),
        )
        for value, measurement_name, unit in measurements:
            if value is not None:
                outcomes.append(
                    self._measurement_outcome(
                        timestamp_us,
                        (measurement_name, value, unit),
                        group=group,
                    )
                )
        if evidence.rangefinder_status is not None and not (
            evidence.rangefinder_status == 4 and evidence.rangefinder_distance_m is not None
        ):
            outcomes.append(
                self._rangefinder_status_outcome(
                    timestamp_us,
                    evidence.rangefinder_status,
                    group,
                )
            )
        for parameter_name, value in evidence.parameter_values.items():
            if value is not None:
                outcomes.append(
                    LogAnalysis(
                        message=_("{parameter} effective value: {value:g}").format(
                            parameter=parameter_name,
                            value=value,
                        ),
                        timestamp_us=timestamp_us,
                        value=value,
                        group=group,
                    )
                )
        return outcomes

    @staticmethod
    def _rangefinder_status_outcome(
        timestamp_us: int,
        status: int,
        group: str,
    ) -> LogAnalysis:
        """Report selected RFND firmware status without conflating it with lifecycle evidence."""
        status_name = _RFND_STATUS_NAMES.get(status)
        if status_name is None:
            status_evidence = _("RFND status {status}").format(status=status)
        elif status == 4:
            status_evidence = _("RFND status {status_name} ({status}) — distance unavailable").format(
                status_name=status_name,
                status=status,
            )
        elif status in {2, 3}:
            status_evidence = _("RFND status {status_name} ({status}) — not usable as Plane landing-height evidence").format(
                status_name=status_name, status=status
            )
        else:
            status_evidence = _("RFND status {status_name} ({status}) — no current range measurement").format(
                status_name=status_name,
                status=status,
            )
        return LogAnalysis(
            message=status_evidence,
            timestamp_us=timestamp_us,
            value=float(status),
            group=group,
        )

    @staticmethod
    def _finite_parameter_value(value: float | None) -> float | None:
        """Treat non-finite event-time parameter values as unavailable evidence."""
        return value if value is not None and math.isfinite(value) else None

    def _firmware_message_outcomes(
        self,
        attempt_number: int,
        evidence: PlaneLandingFirmwareEvidence,
    ) -> list[LogAnalysis]:
        timestamp_us = round(evidence.time_s * 1_000_000)
        if isinstance(evidence, PlaneLandingFirmwareFlareEvidence):
            group = self._group_label(attempt_number, _("Firmware evidence"))
            measurements = (
                (_("Flare altitude"), evidence.altitude_m, _("m")),
                (_("Flare sink rate"), evidence.sink_rate_m_s, _("m/s")),
                (_("Flare groundspeed"), evidence.groundspeed_m_s, _("m/s")),
                (_("Flare distance to target"), evidence.distance_to_target_m, _("m")),
            )
            return [
                self._measurement_outcome(
                    timestamp_us,
                    measurement,
                    group=group,
                )
                for measurement in measurements
            ]
        return [
            self._measurement_outcome(
                timestamp_us,
                (_("Glide slope"), evidence.glide_slope_degrees, _("degrees")),
                group=self._group_label(attempt_number, _("Summary")),
            )
        ]

    def _rangefinder_outcomes(
        self,
        attempt_number: int,
        evidence: PlaneLandingRangefinderEvidence,
    ) -> list[LogAnalysis]:
        """Flatten optional RFND lifecycle evidence into objective findings."""
        outcomes: list[LogAnalysis] = []
        group = self._group_label(attempt_number, _("Rangefinder evidence"))
        timed_measurements = (
            (
                evidence.first_nonzero_time_s,
                evidence.first_nonzero_distance_m,
                _("First non-zero distance"),
                _("m"),
            ),
            (
                evidence.first_in_range_time_s,
                evidence.first_in_range_distance_m,
                _("First in-range distance"),
                _("m"),
            ),
            (
                evidence.continuous_time_s,
                evidence.continuous_samples,
                _("Continuous acquisition sample count"),
                _("samples"),
            ),
            (
                evidence.last_disengagement_time_s,
                evidence.last_disengagement_distance_m,
                _("Last disengagement distance"),
                _("m"),
            ),
        )
        for timestamp_s, value, measurement_name, unit in timed_measurements:
            if timestamp_s is not None and value is not None:
                outcomes.append(
                    self._measurement_outcome(
                        round(timestamp_s * 1_000_000),
                        (measurement_name, float(value), unit),
                        group=group,
                    )
                )
        if (
            evidence.last_disengagement_time_s is not None
            and evidence.last_disengagement_distance_m is None
            and evidence.last_disengagement_status is not None
        ):
            outcomes.append(
                LogAnalysis(
                    message=_("Last disengagement status: {status_name} ({status}); distance unavailable").format(
                        status_name=_RFND_STATUS_NAMES.get(
                            evidence.last_disengagement_status,
                            _("Unknown"),
                        ),
                        status=evidence.last_disengagement_status,
                    ),
                    timestamp_us=round(evidence.last_disengagement_time_s * 1_000_000),
                    value=float(evidence.last_disengagement_status),
                    group=group,
                )
            )
        outcomes.append(
            self._measurement_outcome(
                round(evidence.attempt.end_s * 1_000_000),
                (_("Disengagement count"), float(evidence.disengagement_count), _("events")),
                group=group,
            )
        )
        return outcomes

    @staticmethod
    def _group_label(attempt_number: int, category: str) -> str:
        """Return a one-level presentation group for an attempt's existing evidence."""
        return _("Attempt {number} — {category}").format(number=attempt_number, category=category)

    @staticmethod
    def _measurement_outcome(
        timestamp_us: int,
        measurement: tuple[str, float, str],
        *,
        group: str | None = None,
    ) -> LogAnalysis:
        measurement_name, value, unit = measurement
        if unit == _("degrees"):
            measurement_text = _("{measurement}: {value:.1f}°").format(measurement=measurement_name, value=value)
        elif unit in {_("samples"), _("events")}:
            measurement_text = _("{measurement}: {value:.0f}").format(measurement=measurement_name, value=value)
        else:
            measurement_text = _("{measurement}: {value:.1f} {unit}").format(
                measurement=measurement_name,
                value=value,
                unit=unit,
            )
        return LogAnalysis(
            message=measurement_text,
            timestamp_us=timestamp_us,
            value=value,
            group=group,
        )

    @staticmethod
    def _end_reason_text(end_reason: PlaneLandingEndReason) -> str:
        return {
            PlaneLandingEndReason.ABORT: _("landing abort message"),
            PlaneLandingEndReason.DISARM: _("throttle disarm message"),
            PlaneLandingEndReason.MODE_EXIT: _("transition away from landing mode"),
            PlaneLandingEndReason.GPS_STOP: _("sustained GPS low-speed rollout completion"),
            PlaneLandingEndReason.STAGE_RESTART: _("new LAND active-stage transition"),
            PlaneLandingEndReason.FLIGHT_SEGMENT_END: _("operational flight-segment boundary"),
        }[end_reason]

    @staticmethod
    def _mode_name(mode_number: int) -> str:
        return {
            PlaneLandingAttemptDetector.AUTO_MODE_NUMBER: "AUTO",
            PlaneLandingAttemptDetector.AUTOLAND_MODE_NUMBER: "AUTOLAND",
        }[mode_number]
