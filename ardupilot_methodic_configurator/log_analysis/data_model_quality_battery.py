"""
Data model for battery quality check.

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


class BatteryLogQualityModel(BaseLogQualityAnalysisModel):
    """Checks battery telemetry and configuration quality."""

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("BAT")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_voltage, self.check_curr_total, self.check_current, self.check_efficiency):
            issues += check()
        issues += self.check_parameters()

        _, name = self.resolve_message_step("BAT", "Battery")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        name = self.resolve_message_step("BAT", "Battery")[1]
        reason, issues, bitmask_disabled = self.diagnose_bitmask_absence(
            "BAT", "Battery Monitor", "Battery", not_logged_hint=_("check the battery monitor physical connection")
        )
        if not bitmask_disabled:
            step, name = self.resolve_message_step("BAT", "Battery")
            if self.parameters.get("BATT_MONITOR") == 0:
                reason = _("Battery logging enabled but BATT_MONITOR is 0 (monitor disabled)")
                issues = [
                    QualityIssue(_("Set BATT_MONITOR to enable the battery monitor"), self.step_for_parameter("BATT_MONITOR"))
                ]
            else:
                reason = _("Battery logging enabled but no data, monitor may not be configured properly")
                issues = [QualityIssue(_("No BAT messages found"), step)]

        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_voltage(self) -> list[QualityIssue]:
        volts, issues = self.field_values_or_issue(
            "BAT",
            "Volt",
            missing_field_message=_("Volt field not present in this firmware's BAT schema"),
            missing_values_message=_("Voltage values missing from BAT records"),
        )
        if volts is None:
            return issues

        if volts.max() == 0:
            issues.append(QualityIssue(_("Voltage is zero throughout, sensor may not be reading")))

        v_max = self.parameters.get("MOT_BAT_VOLT_MAX")
        v_min = self.parameters.get("MOT_BAT_VOLT_MIN")
        if v_max is not None and v_max > 0 and volts.max() >= 1.2 * v_max:
            issues.append(
                QualityIssue(
                    _("Voltage spike, or MOT_BAT_VOLT_MAX misconfigured"), self.step_for_parameter("MOT_BAT_VOLT_MAX")
                )
            )
        if v_min is not None and v_min > 0 and volts.min() <= 0.8 * v_min:
            issues.append(
                QualityIssue(_("Voltage sag, or MOT_BAT_VOLT_MIN misconfigured"), self.step_for_parameter("MOT_BAT_VOLT_MIN"))
            )

        return issues

    def check_current(self) -> list[QualityIssue]:
        _current, issues = self.field_values_or_issue(
            "BAT",
            "Curr",
            missing_field_message=_("Curr field not present in this firmware's BAT schema"),
            missing_values_message=_("Current values missing from BAT records"),
        )
        return issues

    def check_curr_total(self) -> list[QualityIssue]:
        _cur_tot, issues = self.field_values_or_issue(
            "BAT",
            "CurrTot",
            missing_field_message=_("CurrTot field not present in this firmware's BAT schema"),
            missing_values_message=_("CurrTot missing from BAT records"),
        )
        return issues

    def check_parameters(self) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        monitor = self.parameters.get("BATT_MONITOR")
        if monitor is None:
            return issues

        if self.parameters.get("BATT_LOW_VOLT") == 0:
            issues.append(
                QualityIssue(_("Battery low-voltage failsafe threshold disabled"), self.step_for_parameter("BATT_LOW_VOLT"))
            )
        if self.parameters.get("BATT_CRT_VOLT") == 0:
            issues.append(
                QualityIssue(
                    _("Battery critical-voltage failsafe threshold disabled"), self.step_for_parameter("BATT_CRT_VOLT")
                )
            )

        return issues

    def check_efficiency(self) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        frame = self.vehicle_components.get("Frame", {})
        specs = frame.get("Specifications", {})
        tow = specs.get("TOW max Kg", None)
        if tow is None or tow <= 0:
            return issues

        volts, _volts_issues = self.field_values_or_issue(
            "BAT",
            "Volt",
            missing_field_message=_("Volt field not present in this firmware's BAT schema"),
            missing_values_message=_("Voltage values missing from BAT records"),
        )
        curr, _curr_issues = self.field_values_or_issue(
            "BAT",
            "Curr",
            missing_field_message=_("Curr field not present in this firmware's BAT schema"),
            missing_values_message=_("Current values missing from BAT records"),
        )
        if volts is None or curr is None:
            return issues

        efficiency = (volts.mean() * curr.mean()) / tow
        if efficiency < 200:
            issues.append(
                QualityIssue(
                    _(
                        "Power efficiency < 200W/Kg. Current is miscalibrated or take "
                        "off weight is incorrect or the efficiency is really good."
                    )
                )
            )
        elif efficiency > 500:
            issues.append(
                QualityIssue(
                    _(
                        "Power efficiency > 500W/Kg. Current is miscalibrated or take off "
                        "weight is incorrect or the efficiency is really bad."
                    )
                )
            )
        return issues
