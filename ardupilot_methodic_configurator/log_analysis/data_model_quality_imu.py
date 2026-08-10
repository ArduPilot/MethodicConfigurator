"""
Data model for IMU quality check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogQualityAnalysisModel,
    LogQualityResult,
    QualityIssue,
)


class ImuLogQualityModel(BaseLogQualityAnalysisModel):
    """Checks IMU telemetry quality (error counts, sensor health, raw signal presence)."""

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("IMU")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_gyro_error, self.check_accel_error, self.check_health, self.check_signal_present):
            issues += check()

        _, name = self.resolve_message_step("IMU", "IMU")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        """Diagnose why IMU data is absent using LOG_BITMASK."""
        name = self.resolve_message_step("IMU", "IMU")[1]
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "IMU", "IMU", "IMU", not_logged_hint=_("check firmware build supports IMU logging")
        )
        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_gyro_error(self) -> list[QualityIssue]:
        """Validate gyroscope error count across all IMU instances."""
        eg, issues = self.field_values_or_issue(
            "IMU",
            "EG",
            missing_field_message=_("EG field not present in this firmware's IMU schema"),
            missing_values_message=_("Gyroscope error count missing from IMU records"),
        )
        if eg is not None and eg.max() > 0:
            issues.append(QualityIssue(_("Gyroscope error count detected on at least one IMU instance")))
        return issues

    def check_accel_error(self) -> list[QualityIssue]:
        """Validate accelerometer error count across all IMU instances."""
        ea, issues = self.field_values_or_issue(
            "IMU",
            "EA",
            missing_field_message=_("EA field not present in this firmware's IMU schema"),
            missing_values_message=_("Accelerometer error count missing from IMU records"),
        )
        if ea is not None and ea.max() > 0:
            issues.append(QualityIssue(_("Accelerometer error count detected on at least one IMU instance")))
        return issues

    def check_health(self) -> list[QualityIssue]:
        """Validate gyroscope/accelerometer health flags across all IMU instances."""
        issues: list[QualityIssue] = []

        gh, gh_issues = self.field_values_or_issue(
            "IMU",
            "GH",
            missing_field_message=_("GH field not present in this firmware's IMU schema"),
            missing_values_message=_("Gyroscope health missing from IMU records"),
        )
        issues += gh_issues
        if gh is not None and (gh == 0).any():
            issues.append(QualityIssue(_("Gyroscope reported unhealthy at some point during the flight")))

        ah, ah_issues = self.field_values_or_issue(
            "IMU",
            "AH",
            missing_field_message=_("AH field not present in this firmware's IMU schema"),
            missing_values_message=_("Accelerometer health missing from IMU records"),
        )
        issues += ah_issues
        if ah is not None and (ah == 0).any():
            issues.append(QualityIssue(_("Accelerometer reported unhealthy at some point during the flight")))

        return issues

    def check_signal_present(self) -> list[QualityIssue]:
        """Validate that raw gyro/accel signals are not flat-zero throughout (sensor not reading)."""
        issues: list[QualityIssue] = []

        for axis_field in ("GyrX", "GyrY", "GyrZ"):
            values, field_issues = self.field_values_or_issue(
                "IMU",
                axis_field,
                missing_field_message=_("{field} field not present in this firmware's IMU schema").format(field=axis_field),
                missing_values_message=_("{field} values missing from IMU records").format(field=axis_field),
            )
            issues += field_issues
            if values is not None and values.max() == 0 and values.min() == 0:
                issues.append(
                    QualityIssue(_("{field} is zero throughout, gyroscope may not be reading").format(field=axis_field))
                )

        for axis_field in ("AccX", "AccY", "AccZ"):
            values, field_issues = self.field_values_or_issue(
                "IMU",
                axis_field,
                missing_field_message=_("{field} field not present in this firmware's IMU schema").format(field=axis_field),
                missing_values_message=_("{field} values missing from IMU records").format(field=axis_field),
            )
            issues += field_issues
            if values is not None and values.max() == 0 and values.min() == 0:
                issues.append(
                    QualityIssue(_("{field} is zero throughout, accelerometer may not be reading").format(field=axis_field))
                )

        return issues
