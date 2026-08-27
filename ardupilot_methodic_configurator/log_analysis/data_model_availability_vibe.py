"""
Data model for VIBE availability check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    AvailabilityIssue,
    BaseLogAnalysisModel,
    BaseLogAvailabilityModel,
    LogAvailabilityResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState

_VIBE_WARNING_THRESHOLD = 30.0
_VIBE_SEVERE_THRESHOLD = 60.0

_VIBE_AXES = ("VibeX", "VibeY", "VibeZ")


class VibeLogAvailabilityModel(BaseLogAvailabilityModel):
    """
    Checks VIBE data presence and availability for analysis.

    This model only reports whether vibration data exists and is readable.
    Threshold-based judgment (e.g. the ArduPilot wiki's 30/60 m/s/s vibration
    guidance, or clip-count nuance) is deferred to a future analysis layer.
    """

    def check(self) -> LogAvailabilityResult:
        records = self.log_data.get_message_columns("VIBE")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[AvailabilityIssue] = []
        for check in (self.check_vibe_levels, self.check_clipping):
            issues += check()

        step, name = self.resolve_message_step("VIBE", "VIBE")
        return self.build_result(issues, name, related_step=step)

    def _diagnose_absence(self) -> LogAvailabilityResult:
        """
        Diagnose why VIBE data is absent.

        VIBE has no dedicated LOG_BITMASK bit (it rides along with base IMU
        logging), so diagnose_bitmask_absence falls through to its generic
        "not logged" branch here rather than a bitmask-specific one.
        """
        step, name = self.resolve_message_step("VIBE", "VIBE")
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "VIBE",
            "VIBE",
            "VIBE",
            not_logged_hint=_("check that IMU data is being logged, since VIBE is derived from it"),
        )
        return LogAvailabilityResult(
            available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name, related_step=step
        )

    def check_vibe_levels(self) -> list[AvailabilityIssue]:
        """Check that VibeX/Y/Z fields are present and have readable data."""
        return self.check_fields_present("VIBE", ("VibeX", "VibeY", "VibeZ"))

    def check_clipping(self) -> list[AvailabilityIssue]:
        """Check that the Clip field is present and has readable data."""
        _clip, issues = self.field_values_or_issue(
            "VIBE",
            "Clip",
            missing_field_message=_("Clip field not present in this firmware's VIBE schema"),
            missing_values_message=_("Clip values missing from VIBE records"),
        )
        return issues


class VibeLogAnalysis(BaseLogAnalysisModel):
    """
    VIBE analysis on the data from the log.

    Runs after VIBE availability model passes with the required data.
    """

    def analyse(self) -> LogAnalysisResult:
        records = self.log_data.get_message_columns("VIBE")
        if records is None or len(records) == 0:
            return LogAnalysisResult(
                available=False,
                outcomes=[],
                name=_("Vibration Analysis"),
                reason=_("No VIBE data available for analysis"),
            )

        outcomes: list[LogAnalysis] = []
        for check in (self.check_vibration_levels, self.check_clipping):
            outcomes += check()

        step, _name = self.resolve_message_step("VIBE", "VIBE")
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Vibration Analysis"),
            reason=_("Vibration analysis complete"),
            related_step=step,
        )

    def _time_seconds(self) -> Any | None:  # noqa: ANN401
        """Return canonical TimeUS values in seconds, or None if unavailable."""
        time_seconds, _issues = self.field_values_or_issue(
            "VIBE",
            "TimeUS",
            missing_field_message=_("TimeUS field not present in this firmware's VIBE schema"),
            missing_values_message=_("TimeUS missing from VIBE records"),
        )
        return time_seconds

    def check_vibration_levels(self) -> list[LogAnalysis]:
        """Check peak vibration per axis against the ArduPilot wiki's 30/60 m/s/s guidance."""
        outcomes: list[LogAnalysis] = []

        time_seconds = self._time_seconds()
        if time_seconds is None:
            return outcomes

        for axis_field in _VIBE_AXES:
            values, _issues = self.field_values_or_issue(
                "VIBE",
                axis_field,
                missing_field_message=_("{field} field not present in this firmware's VIBE schema").format(field=axis_field),
                missing_values_message=_("{field} values missing from VIBE records").format(field=axis_field),
            )
            if values is None or len(values) == 0:
                continue

            peak_idx = values.argmax()
            peak_value = float(values[peak_idx])
            peak_timestamp_us = float(time_seconds[peak_idx] * 1e6)

            if peak_value >= _VIBE_SEVERE_THRESHOLD:
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "{axis} peaked at {peak:.1f} m/s/s, above the {severe:.0f} m/s/s level at which "
                            "position/altitude hold problems are nearly always present."
                        ).format(axis=axis_field, peak=peak_value, severe=_VIBE_SEVERE_THRESHOLD),
                        timestamp_us=peak_timestamp_us,
                        value=peak_value,
                    )
                )
            elif peak_value >= _VIBE_WARNING_THRESHOLD:
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "{axis} peaked at {peak:.1f} m/s/s, above the {warn:.0f} m/s/s level that may cause "
                            "position/altitude hold problems."
                        ).format(axis=axis_field, peak=peak_value, warn=_VIBE_WARNING_THRESHOLD),
                        timestamp_us=peak_timestamp_us,
                        value=peak_value,
                    )
                )

        return outcomes

    def check_clipping(self) -> list[LogAnalysis]:
        """Report total accelerometer clipping events, if any."""
        outcomes: list[LogAnalysis] = []

        time_seconds = self._time_seconds()
        clip_values, _issues = self.field_values_or_issue(
            "VIBE",
            "Clip",
            missing_field_message=_("Clip field not present in this firmware's VIBE schema"),
            missing_values_message=_("Clip values missing from VIBE records"),
        )
        if clip_values is None or time_seconds is None or len(clip_values) == 0:
            return outcomes

        total_clips = float(clip_values.max())
        if total_clips > 0:
            worst_idx = clip_values.argmax()
            outcomes.append(
                LogAnalysis(
                    message=_(
                        "Accelerometer reported {count:.0f} clipping event(s) during the flight, "
                        "meaning the sensor physically saturated at some point."
                    ).format(count=total_clips),
                    timestamp_us=float(time_seconds[worst_idx] * 1e6),
                    value=total_clips,
                )
            )

        return outcomes
