"""
Availability and objective analysis for ArduPlane AUTO landing attempts.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
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
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
    from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterHistory

_REQUIRED_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("GPS", ("TimeUS", "Spd")),
    ("LAND", ("TimeUS", "stage")),
    ("MODE", ("TimeUS", "ModeNum")),
)


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
    """Report objective AUTO landing-attempt boundaries and time-scoped parameters."""

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
        outcomes = [self._attempt_outcome(index, attempt) for index, attempt in enumerate(attempts, start=1)]
        reason = (
            _("Detected {count} AUTO landing attempt(s)").format(count=len(attempts))
            if attempts
            else _("No AUTO landing attempts detected")
        )
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Plane Landing Analysis"),
            reason=reason,
        )

    def _attempt_outcome(self, attempt_number: int, attempt: PlaneLandingAttempt) -> LogAnalysis:
        flare_altitude_m = self.parameter_history.value_at("LAND_FLARE_ALT", attempt.start_s)
        parameter_evidence = (
            _("LAND_FLARE_ALT at attempt start: {value:.2f} m").format(value=flare_altitude_m)
            if flare_altitude_m is not None
            else _("LAND_FLARE_ALT was unavailable at attempt start")
        )
        return LogAnalysis(
            message=_(
                "AUTO landing attempt {number}: {start:.3f} s to {end:.3f} s; "
                "termination evidence: {end_reason}; {parameter_evidence}"
            ).format(
                number=attempt_number,
                start=attempt.start_s,
                end=attempt.end_s,
                end_reason=self._end_reason_text(attempt.end_reason),
                parameter_evidence=parameter_evidence,
            ),
            timestamp_us=round(attempt.start_s * 1_000_000),
            value=flare_altitude_m,
        )

    @staticmethod
    def _end_reason_text(end_reason: PlaneLandingEndReason) -> str:
        return {
            PlaneLandingEndReason.ABORT: _("landing abort message"),
            PlaneLandingEndReason.DISARM: _("throttle disarm message"),
            PlaneLandingEndReason.MODE_EXIT: _("transition away from AUTO"),
            PlaneLandingEndReason.GPS_STOP: _("sustained GPS low-speed rollout completion"),
            PlaneLandingEndReason.FLIGHT_SEGMENT_END: _("operational flight-segment boundary"),
        }[end_reason]
