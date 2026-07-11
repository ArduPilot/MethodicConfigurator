"""
Data model for ESC quality check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.backend_log_quality_check import find_matching_param_values
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogQualityAnalysisModel,
    LogQualityResult,
    QualityIssue,
)


class EscLogQualityModel(BaseLogQualityAnalysisModel):
    """Checks ESC telemetry and configuration quality."""

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("ESC")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_rpm, self.check_current, self.check_error_rate):
            issues += check()

        _, name = self.resolve_message_step("ESC", "ESC")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        """Diagnose why ESC data is absent."""
        step, name = self.resolve_message_step("ESC", "ESC")

        dshot_values = find_matching_param_values(self.apm_doc, "MOT_PWM_TYPE", "DShot") if self.apm_doc else set()
        pwm_type = self.parameters.get("MOT_PWM_TYPE")
        scr_enabled = self.parameters.get("SCR_ENABLE")

        if pwm_type is not None and str(int(pwm_type)) not in dshot_values:
            reason = _("ESC telemetry not logged")
            issues = [
                QualityIssue(
                    _("Set MOT_PWM_TYPE to a DShot variant for ESC telemetry support"),
                    self.step_for_parameter("MOT_PWM_TYPE"),
                )
            ]
        elif scr_enabled == 0:
            reason = _("ESC telemetry not logged, scripting is disabled")
            issues = [
                QualityIssue(
                    _("Enable SCR_ENABLE if using scripted ESC telemetry"),
                    self.step_for_parameter("SCR_ENABLE"),
                )
            ]
        else:
            reason = _("ESC telemetry not logged, check ESC hardware supports telemetry and is wired correctly")
            issues = [QualityIssue(_("No ESC messages found"), step)]

        return LogQualityResult(available=False, state="warning", reason=reason, issues=issues, name=name)

    def check_rpm(self) -> list[QualityIssue]:
        """Validate logged ESC RPM values."""
        issues: list[QualityIssue] = []
        if not self.field_available("ESC", "RPM"):
            issues.append(QualityIssue(_("RPM field not present in this firmware's ESC schema")))
            return issues

        rpm = self.log_data.get_field("ESC", "RPM")
        if len(rpm) == 0:
            issues.append(QualityIssue(_("RPM values missing from ESC records")))
        return issues

    def check_current(self) -> list[QualityIssue]:
        """Validate logged ESC current values."""
        issues: list[QualityIssue] = []
        if not self.field_available("ESC", "Curr"):
            issues.append(QualityIssue(_("Curr field not present in this firmware's ESC schema")))
            return issues

        current = self.log_data.get_field("ESC", "Curr")
        if len(current) == 0:
            issues.append(QualityIssue(_("Current values missing from ESC records")))
        return issues

    def check_error_rate(self) -> list[QualityIssue]:
        """Validate ESC error rate."""
        issues: list[QualityIssue] = []
        if not self.field_available("ESC", "Err"):
            issues.append(QualityIssue(_("Err field not present in this firmware's ESC schema")))
            return issues

        err = self.log_data.get_field("ESC", "Err")
        if len(err) > 0 and err.max() > 0:
            issues.append(QualityIssue(_("ESC error rate detected on at least one ESC instance")))
        return issues
