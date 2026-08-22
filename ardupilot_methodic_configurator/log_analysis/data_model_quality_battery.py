"""
Data model for battery quality check and battery analysis.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_par_dict import is_within_tolerance
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogModel,
    LogQualityResult,
    QualityIssue,
)
from ardupilot_methodic_configurator.log_analysis.utils import find_log_bit_in_apm_file


class BatteryLogQualityModel(BaseLogModel):
    """Checks battery telemetry and configuration quality."""

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("BAT")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_voltage, self.check_curr_total, self.check_current):
            issues += check()
        issues += self.check_parameters()

        step, name = self.resolve_message_step("BAT", "Battery")
        return self.build_result(issues, name, related_step=step)

    def _diagnose_absence(self) -> LogQualityResult:
        step, name = self.resolve_message_step("BAT", "Battery")
        reason, issues, bitmask_disabled = self.diagnose_bitmask_absence(
            "BAT", "Battery Monitor", "Battery", not_logged_hint=_("check the battery monitor physical connection")
        )
        if not bitmask_disabled:
            if self.parameters.get("BATT_MONITOR") == 0:
                reason = _("Battery logging enabled but BATT_MONITOR is 0 (monitor disabled)")
                issues = [
                    QualityIssue(_("Set BATT_MONITOR to enable the battery monitor"), self.step_for_parameter("BATT_MONITOR"))
                ]
            else:
                reason = _("Battery logging enabled but no data, monitor may not be configured properly")
                issues = [QualityIssue(_("No BAT messages found"), step)]

        return LogQualityResult(
            available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name, related_step=step
        )

    def check_voltage(self) -> list[QualityIssue]:
        """Voltage presence check."""
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
            scaled=False,
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


# Analysis class for battery.
# Hardware and parameter analysis.


class BatteryLogAnalysis(BaseLogModel):
    """
    Battery analysis on the data from the log.

    Runs after battery quality model passes with the required data.
    """

    def analyse(self) -> LogAnalysisResult:
        records = self.log_data.get_message_columns("BAT")
        if records is None or len(records) == 0:
            return LogAnalysisResult(
                available=False,
                outcomes=[],
                name=_("Battery Analysis"),
                reason=_("No BAT data available for analysis"),
            )

        outcomes: list[LogAnalysis] = []
        for check in (
            self.check_battery_capacity_retention,
            self.check_voltage_extrema,
            self.check_efficiency,
            self.check_failsafe_ordering,
            self.check_battery_parameter_derivation,
        ):
            outcomes += check()

        step, _name = self.resolve_message_step("BAT", "Battery")
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Battery Analysis"),
            reason=_("Battery analysis complete"),
            related_step=step,
        )

    def _last_timestamp_us(self) -> float | None:
        """Return the TimeUS value for this message, in microseconds."""
        time_us, _issues = self.field_values_or_issue(
            "BAT",
            "TimeUS",
            scaled=False,
            missing_field_message=_("TimeUS field not present in this firmware's BAT schema"),
            missing_values_message=_("TimeUS missing from BAT records"),
        )
        if time_us is None or len(time_us) == 0:
            return None
        return float(time_us[-1])

    def check_battery_capacity_retention(self) -> list[LogAnalysis]:
        """Check what percentage of rated BATT_CAPACITY was consumed during the flight."""
        outcomes: list[LogAnalysis] = []

        bat_capacity = self.parameters.get("BATT_CAPACITY")
        if bat_capacity is None or bat_capacity <= 0:
            return outcomes

        curr_tot, _issues = self.field_values_or_issue(
            "BAT",
            "CurrTot",
            # 3 test logs were tested where scaled values were physically implausible (<1 mAh total consumed) To be tested
            # on more logs later until then scaled should be False.
            scaled=False,
            missing_field_message=_("CurrTot field not present in this firmware's BAT schema"),
            missing_values_message=_("CurrTot missing from BAT records"),
        )
        if curr_tot is None:
            return outcomes

        used_percentage = float(curr_tot.max() / bat_capacity * 100)
        timestamp_us = self._last_timestamp_us()

        if used_percentage > 100:
            outcomes.append(
                LogAnalysis(
                    message=_(
                        "Consumed {used:.1f}% of rated battery capacity ({capacity:.0f} mAh). "
                        "This exceeds 100%, check BATT_CAPACITY is correct for your battery, "
                        "or BATT_AMP_PERVLT."
                    ).format(used=used_percentage, capacity=bat_capacity),
                    timestamp_us=timestamp_us,
                    value=used_percentage,
                    param_name="BATT_CAPACITY",
                )
            )
        else:
            outcomes.append(
                LogAnalysis(
                    message=_("Used {used:.1f}% of rated battery capacity ({capacity:.0f} mAh)").format(
                        used=used_percentage, capacity=bat_capacity
                    ),
                    timestamp_us=timestamp_us,
                    value=used_percentage,
                )
            )

        return outcomes

    def check_voltage_extrema(self) -> list[LogAnalysis]:
        """Report voltage sag relative to MOT_BAT_VOLT_MAX/MIN."""
        outcomes: list[LogAnalysis] = []

        volts, _issues = self.field_values_or_issue(
            "BAT",
            "Volt",
            missing_field_message=_("Volt field not present in this firmware's BAT schema"),
            missing_values_message=_("Voltage values missing from BAT records"),
        )
        if volts is None:
            return outcomes

        timestamp_us = self._last_timestamp_us()

        v_max = self.parameters.get("MOT_BAT_VOLT_MAX")
        v_min = self.parameters.get("MOT_BAT_VOLT_MIN")
        if v_max is not None and v_max > 0 and volts.max() >= 1.2 * v_max:
            outcomes.append(
                LogAnalysis(
                    message=_("Voltage spike to {v:.2f}V, or MOT_BAT_VOLT_MAX misconfigured").format(v=float(volts.max())),
                    timestamp_us=timestamp_us,
                    value=float(volts.max()),
                    param_name="MOT_BAT_VOLT_MAX",
                )
            )
        if v_min is not None and v_min > 0 and volts.min() <= 0.8 * v_min:
            outcomes.append(
                LogAnalysis(
                    message=_("Voltage sag to {v:.2f}V, or MOT_BAT_VOLT_MIN misconfigured").format(v=float(volts.min())),
                    timestamp_us=timestamp_us,
                    value=float(volts.min()),
                    param_name="MOT_BAT_VOLT_MIN",
                )
            )

        return outcomes

    def check_efficiency(self) -> list[LogAnalysis]:
        """Report power to weight efficiency (W/Kg)."""
        outcomes: list[LogAnalysis] = []

        frame = self.vehicle_components.get("Frame", {})
        specs = frame.get("Specifications", {})
        tow = specs.get("TOW max Kg", None)
        if tow is None or tow <= 0:
            return outcomes

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
            return outcomes

        efficiency = float((volts.mean() * curr.mean()) / tow)
        timestamp_us = self._last_timestamp_us()

        outcomes.append(
            LogAnalysis(
                message=_("Power efficiency: {eff:.0f} W/Kg").format(eff=efficiency),
                timestamp_us=timestamp_us,
                value=efficiency,
            )
        )

        return outcomes

    def check_failsafe_ordering(self) -> list[LogAnalysis]:
        """
        Check BATT_CRT_VOLT < BATT_LOW_VOLT, sourced from AP_BattMonitor_Backend::arming_checks(fs_voltage_inversion).

        This is a static parameter check.
        ARMING_CHECK or ARMING_SKIPCHK can bypass that protection, so a flight does not guarantee this was actually checked.
        """
        outcomes: list[LogAnalysis] = []

        crt_volt = self.parameters.get("BATT_CRT_VOLT")
        low_volt = self.parameters.get("BATT_LOW_VOLT")

        if crt_volt is None or low_volt is None or crt_volt <= 0 or low_volt <= 0:
            return outcomes

        if crt_volt >= low_volt:
            bypass_note = self._arming_check_bypass_battery()

            outcomes.append(
                LogAnalysis(
                    message=_(
                        "BATT_CRT_VOLT ({crt:.1f}V) is not lower than BATT_LOW_VOLT ({low:.1f}V). "
                        "ArduPilot's own arming check requires critical voltage to be below low voltage.{note}"
                    ).format(crt=crt_volt, low=low_volt, note=bypass_note),
                    timestamp_us=None,
                    value=crt_volt - low_volt,
                )
            )

        return outcomes

    def _arming_check_bypass_battery(self) -> str:
        """Check whether ARMING_CHECK includes the battery-level check, from apm.pdef.xml's bitmask."""
        arming_check = self.parameters.get("ARMING_CHECK")
        if arming_check is None or self.apm_doc is None:
            return ""

        bitmask_field = self.apm_doc.get("ARMING_CHECK", {}).get("fields", {}).get("Bitmask")
        if not isinstance(bitmask_field, str):
            return ""

        battery_bit = find_log_bit_in_apm_file(bitmask_field, "Battery Level")
        all_bit = find_log_bit_in_apm_file(bitmask_field, "All")

        bits_to_check = [b for b in (battery_bit, all_bit) if b is not None]
        if not bits_to_check:
            return ""

        battery_check_active = any(int(arming_check) & (1 << b) for b in bits_to_check)
        if not battery_check_active:
            return _(
                " ARMING_CHECK does not include 'All' or 'Battery Level', "
                "so this misconfiguration would not have blocked arming."
            )
        return ""

    def check_battery_parameter_derivation(self) -> list[LogAnalysis]:
        """Compare actual FC parameter values against derived or forced parameters."""
        outcomes: list[LogAnalysis] = []

        for param_name, step_filename in self.derived_and_forced_parameters_matching(r"^(BATT_|MOT_BAT_)").items():
            expected, source = self.expected_parameter_value(step_filename, param_name)
            if expected is None:
                continue

            actual = self.parameters.get(param_name)
            if actual is None:
                continue

            if not is_within_tolerance(actual, expected):
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "{param} is {actual:.2f} but should be {expected:.2f} as per {source} parameter "
                            "in {step}, based on your vehicle_components specifications."
                        ).format(param=param_name, actual=actual, expected=expected, source=source, step=step_filename),
                        timestamp_us=None,
                        value=actual,
                        param_name=param_name,
                        suggested_value=expected,
                        related_step=step_filename,
                    )
                )
        return outcomes
