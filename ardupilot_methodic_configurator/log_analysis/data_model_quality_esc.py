"""
Data model for ESC quality check.

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
from ardupilot_methodic_configurator.log_analysis.utils import find_matching_param_values


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

        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_rpm(self) -> list[QualityIssue]:
        """Validate logged ESC RPM values."""
        _rpm, issues = self.field_values_or_issue(
            "ESC",
            "RPM",
            missing_field_message=_("RPM field not present in this firmware's ESC schema"),
            missing_values_message=_("RPM values missing from ESC records"),
        )
        return issues

    def check_current(self) -> list[QualityIssue]:
        """Validate logged ESC current values."""
        _current, issues = self.field_values_or_issue(
            "ESC",
            "Curr",
            missing_field_message=_("Curr field not present in this firmware's ESC schema"),
            missing_values_message=_("Current values missing from ESC records"),
        )
        return issues

    def check_error_rate(self) -> list[QualityIssue]:
        """Validate ESC error rate."""
        err, issues = self.field_values_or_issue(
            "ESC",
            "Err",
            missing_field_message=_("Err field not present in this firmware's ESC schema"),
            missing_values_message=_("ESC error values missing from ESC records"),
        )
        if err is not None and err.max() > 0:
            step, _name = self.resolve_message_step("ESC", "ESC")
            issues.append(QualityIssue(_("ESC error rate detected on at least one ESC instance"), step))
        return issues
