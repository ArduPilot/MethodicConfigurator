"""
Data model for VIBE quality check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogModel,
    LogQualityResult,
    QualityIssue,
)

_VIBE_WARNING_THRESHOLD = 30.0
_VIBE_SEVERE_THRESHOLD = 60.0

_VIBE_AXES = ("VibeX", "VibeY", "VibeZ")


class VibeLogQualityModel(BaseLogModel):
    """
    Checks VIBE data presence and availability for analysis.

    This model only reports whether vibration data exists and is readable.
    Threshold-based judgment (e.g. the ArduPilot wiki's 30/60 m/s/s vibration
    guidance, or clip-count nuance) is deferred to a future analysis layer.
    """

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("VIBE")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_vibe_levels, self.check_clipping):
            issues += check()

        _, name = self.resolve_message_step("VIBE", "VIBE")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        """
        Diagnose why VIBE data is absent.

        VIBE has no dedicated LOG_BITMASK bit (it rides along with base IMU
        logging), so diagnose_bitmask_absence falls through to its generic
        "not logged" branch here rather than a bitmask-specific one.
        """
        name = self.resolve_message_step("VIBE", "VIBE")[1]
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "VIBE",
            "VIBE",
            "VIBE",
            not_logged_hint=_("check that IMU data is being logged, since VIBE is derived from it"),
        )
        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_vibe_levels(self) -> list[QualityIssue]:
        """Check that VibeX/Y/Z fields are present and have readable data."""
        return self.check_fields_present("VIBE", ("VibeX", "VibeY", "VibeZ"))

    def check_clipping(self) -> list[QualityIssue]:
        """Check that the Clip field is present and has readable data."""
        _clip, issues = self.field_values_or_issue(
            "VIBE",
            "Clip",
            missing_field_message=_("Clip field not present in this firmware's VIBE schema"),
            missing_values_message=_("Clip values missing from VIBE records"),
        )
        return issues


class VibeLogAnalysis(BaseLogModel):
    """
    VIBE analysis on the data from the log.

    Runs after VIBE quality model passes with the required data.
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

    def _time_us(self) -> Any | None:  # noqa: ANN401
        """Return the raw TimeUS array for the VIBE message, or None if unavailable."""
        time_us, _issues = self.field_values_or_issue(
            "VIBE",
            "TimeUS",
            scaled=False,
            missing_field_message=_("TimeUS field not present in this firmware's VIBE schema"),
            missing_values_message=_("TimeUS missing from VIBE records"),
        )
        return time_us

    def check_vibration_levels(self) -> list[LogAnalysis]:
        """Check peak vibration per axis against the ArduPilot wiki's 30/60 m/s/s guidance."""
        outcomes: list[LogAnalysis] = []

        time_us = self._time_us()
        if time_us is None:
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
            peak_timestamp = float(time_us[peak_idx])

            if peak_value >= _VIBE_SEVERE_THRESHOLD:
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "{axis} peaked at {peak:.1f} m/s/s, above the {severe:.0f} m/s/s level at which "
                            "position/altitude hold problems are nearly always present."
                        ).format(axis=axis_field, peak=peak_value, severe=_VIBE_SEVERE_THRESHOLD),
                        timestamp_us=peak_timestamp,
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
                        timestamp_us=peak_timestamp,
                        value=peak_value,
                    )
                )

        return outcomes

    def check_clipping(self) -> list[LogAnalysis]:
        """Report total accelerometer clipping events, if any."""
        outcomes: list[LogAnalysis] = []

        time_us = self._time_us()
        clip_values, _issues = self.field_values_or_issue(
            "VIBE",
            "Clip",
            scaled=False,
            missing_field_message=_("Clip field not present in this firmware's VIBE schema"),
            missing_values_message=_("Clip values missing from VIBE records"),
        )
        if clip_values is None or time_us is None or len(clip_values) == 0:
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
                    timestamp_us=float(time_us[worst_idx]),
                    value=total_clips,
                )
            )

        return outcomes
