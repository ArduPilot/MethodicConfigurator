"""
Data model for battery quality check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.backend_log_quality_check import find_log_bit_in_apm_file, get_log_bitmask
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
        bitmask = self.parameters.get("LOG_BITMASK")
        monitor = self.parameters.get("BATT_MONITOR")
        bitmask_field = get_log_bitmask(self.apm_doc) if self.apm_doc else None
        log_bit = find_log_bit_in_apm_file(bitmask_field, "Battery Monitor") if bitmask_field else None

        step, name = self.resolve_message_step("BAT", "Battery")

        if log_bit is not None and bitmask is not None and (int(bitmask) & (1 << log_bit)) == 0:
            reason = _("Battery logging is disabled in LOG_BITMASK")
            issues = [QualityIssue(_("Enable battery logging (LOG_BITMASK bit) to record BAT data"), step)]
        elif monitor == 0:
            reason = _("Battery logging enabled but BATT_MONITOR is 0 (monitor disabled)")
            issues = [
                QualityIssue(_("Set BATT_MONITOR to enable the battery monitor"), self.step_for_parameter("BATT_MONITOR"))
            ]
        else:
            reason = _("Battery logging enabled but no data, monitor may not be configured properly")
            issues = [QualityIssue(_("No BAT messages found"), step)]

        return LogQualityResult(available=False, state="warning", reason=reason, issues=issues, name=name)

    def check_voltage(self) -> list[QualityIssue]:
        issues: list[QualityIssue] = []

        if not self.field_available("BAT", "Volt"):
            issues.append(QualityIssue(_("Volt field not present in this firmware's BAT schema")))
            return issues

        volts = self.log_data.get_field("BAT", "Volt")

        if len(volts) == 0:
            issues.append(QualityIssue(_("Voltage values missing from BAT records")))
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
        issues: list[QualityIssue] = []

        if not self.field_available("BAT", "Curr"):
            issues.append(QualityIssue(_("Curr field not present in this firmware's BAT schema")))
            return issues

        current = self.log_data.get_field("BAT", "Curr")
        if len(current) == 0:
            issues.append(QualityIssue(_("Current values missing from BAT records")))
        return issues

    def check_curr_total(self) -> list[QualityIssue]:
        issues: list[QualityIssue] = []

        if not self.field_available("BAT", "CurrTot"):
            issues.append(QualityIssue(_("CurrTot field not present in this firmware's BAT schema")))
            return issues

        cur_tot = self.log_data.get_field("BAT", "CurrTot")
        if len(cur_tot) == 0:
            issues.append(QualityIssue(_("CurrTot missing from BAT records")))
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

        volts = self.log_data.get_field("BAT", "Volt")
        curr = self.log_data.get_field("BAT", "Curr")
        if len(volts) == 0 or len(curr) == 0:
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
