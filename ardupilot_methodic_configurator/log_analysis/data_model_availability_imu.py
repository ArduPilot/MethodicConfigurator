"""
Data model for IMU availability check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    AvailabilityIssue,
    BaseLogAnalysisModel,
    BaseLogAvailabilityModel,
    LogAvailabilityResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_instances import (
    has_nonzero_parameter,
    imu_device_id_param,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_param_metadata import tcal_enabled_codes
from ardupilot_methodic_configurator.log_analysis.utils import find_matching_param_values

# This must be at least 10 degrees above TMIN for calibration
_TCAL_MIN_REQUIRED_SPREAD = 10.0
_TCAL_RECOMMENDED_SPREAD = 25.0

# Below this, TMIN is unlikely to reflect a real freezer.
_TCAL_TMIN_WARM_THRESHOLD = 0.0
_TCAL_TMIN_RECOMMENDED = -10.0
_INVALID_CALTEMP = -300.0


class ImuLogAvailabilityModel(BaseLogAvailabilityModel):
    """Checks IMU telemetry availability (error counts, sensor health, raw signal presence)."""

    def check(self) -> LogAvailabilityResult:
        records = self.log_data.get_message_columns("IMU")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[AvailabilityIssue] = []
        for check in (self.check_gyro_error, self.check_accel_error, self.check_health, self.check_signal_present):
            issues += check()

        step, name = self.resolve_message_step("IMU", "IMU")
        return self.build_result(issues, name, related_step=step)

    def _diagnose_absence(self) -> LogAvailabilityResult:
        """Diagnose why IMU data is absent using LOG_BITMASK."""
        step, name = self.resolve_message_step("IMU", "IMU")
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "IMU", "IMU", "IMU", not_logged_hint=_("check firmware build supports IMU logging")
        )
        return LogAvailabilityResult(
            available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name, related_step=step
        )

    def check_gyro_error(self) -> list[AvailabilityIssue]:
        """Validate gyroscope error count across all IMU instances."""
        eg, issues = self.field_values_or_issue(
            "IMU",
            "EG",
            missing_field_message=_("EG field not present in this firmware's IMU schema"),
            missing_values_message=_("Gyroscope error count missing from IMU records"),
        )
        if eg is not None and eg.max() > 0:
            issues.append(AvailabilityIssue(_("Gyroscope error count detected on at least one IMU instance")))
        return issues

    def check_accel_error(self) -> list[AvailabilityIssue]:
        """Validate accelerometer error count across all IMU instances."""
        ea, issues = self.field_values_or_issue(
            "IMU",
            "EA",
            missing_field_message=_("EA field not present in this firmware's IMU schema"),
            missing_values_message=_("Accelerometer error count missing from IMU records"),
        )
        if ea is not None and ea.max() > 0:
            issues.append(AvailabilityIssue(_("Accelerometer error count detected on at least one IMU instance")))
        return issues

    def check_health(self) -> list[AvailabilityIssue]:
        """Validate gyroscope/accelerometer health flags across all IMU instances."""
        issues: list[AvailabilityIssue] = []

        gh, gh_issues = self.field_values_or_issue(
            "IMU",
            "GH",
            missing_field_message=_("GH field not present in this firmware's IMU schema"),
            missing_values_message=_("Gyroscope health missing from IMU records"),
        )
        issues += gh_issues
        if gh is not None and (gh == 0).any():
            issues.append(AvailabilityIssue(_("Gyroscope reported unhealthy at some point during the flight")))

        ah, ah_issues = self.field_values_or_issue(
            "IMU",
            "AH",
            missing_field_message=_("AH field not present in this firmware's IMU schema"),
            missing_values_message=_("Accelerometer health missing from IMU records"),
        )
        issues += ah_issues
        if ah is not None and (ah == 0).any():
            issues.append(AvailabilityIssue(_("Accelerometer reported unhealthy at some point during the flight")))

        return issues

    def check_signal_present(self) -> list[AvailabilityIssue]:
        """Validate that raw gyro/accel signals are not flat-zero throughout (sensor not reading)."""
        issues: list[AvailabilityIssue] = []

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
                    AvailabilityIssue(_("{field} is zero throughout, gyroscope may not be reading").format(field=axis_field))
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
                    AvailabilityIssue(
                        _("{field} is zero throughout, accelerometer may not be reading").format(field=axis_field)
                    )
                )

        return issues


class ImuLogAnalysis(BaseLogAnalysisModel):
    """
    IMU analysis on the data from the log.

    Runs after IMU availability model passes with the required data for analysis.
    """

    def analyse(self) -> LogAnalysisResult:
        outcomes: list[LogAnalysis] = []
        outcomes += self.check_temperature_calibration()
        outcomes += self.check_notch_filter_telemetry_dependency()
        outcomes += self.check_harmonic_notch_filter()

        step, _name = self.resolve_message_step("IMU", "IMU")
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("IMU Analysis"),
            reason=_("IMU analysis complete"),
            related_step=step,
        )

    def check_temperature_calibration(self) -> list[LogAnalysis]:
        """Check IMU temperature calibration state and, if calibrated, the achieved per IMU instance."""
        outcomes: list[LogAnalysis] = []

        for instance in (1, 2, 3):
            if not has_nonzero_parameter(self.parameters, imu_device_id_param(instance)):
                continue  # no physical IMU detected

            enable_param = f"INS_TCAL{instance}_ENABLE"
            enable = self.parameters.get(enable_param)
            if enable is None:
                continue  # this IMU instance is not present on the board

            if enable == 0:
                step_filename = self.step_for_parameter(enable_param)
                suggested, _source = (
                    self.expected_parameter_value(step_filename, enable_param) if step_filename else (None, "")
                )
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "IMU {n} temperature calibration is not enabled. "
                            "Consider running it for better accuracy across temperature changes."
                        ).format(n=instance),
                        timestamp_us=None,
                        value=0.0,
                        param_name=enable_param,
                        suggested_value=suggested,
                        related_step=step_filename or None,
                    )
                )
                continue

            if enable == 2:
                outcomes.append(
                    LogAnalysis(
                        message=_("IMU {n} temperature calibration is in progress (not yet complete).").format(n=instance),
                        timestamp_us=None,
                        value=2.0,
                        param_name=enable_param,
                    )
                )
                continue

            enabled_codes = tcal_enabled_codes(self.apm_doc, instance)
            if not enabled_codes:
                enabled_codes = {"1"}
            if str(int(enable)) not in enabled_codes:
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "IMU {n} has an unexpected {param} value of {value}, "
                            "neither disabled, learning, nor a recognized enabled state."
                        ).format(n=instance, param=enable_param, value=enable),
                        timestamp_us=None,
                        value=float(enable),
                        param_name=enable_param,
                    )
                )
                continue

            accel_caltemp = self.parameters.get(f"INS_ACC{instance}_CALTEMP")
            gyro_caltemp = self.parameters.get(f"INS_GYR{instance}_CALTEMP")
            if _INVALID_CALTEMP in (accel_caltemp, gyro_caltemp):
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "IMU {n} is marked as temperature-calibrated, but accelerometer/gyroscope "
                            "calibration (CALTEMP) was never performed. This calibration data may be "
                            "unreliable; run a 6-axis accel calibration and re-run temperature calibration."
                        ).format(n=instance),
                        timestamp_us=None,
                        value=None,
                        param_name=enable_param,
                    )
                )
                continue

            tmin = self.parameters.get(f"INS_TCAL{instance}_TMIN")
            tmax = self.parameters.get(f"INS_TCAL{instance}_TMAX")
            if tmin is None or tmax is None:
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "IMU {n} temperature calibration is enabled but TMIN/TMAX data is missing, an inconsistent state."
                        ).format(n=instance),
                        timestamp_us=None,
                        value=None,
                        param_name=enable_param,
                    )
                )
                continue

            if tmin > _TCAL_TMIN_WARM_THRESHOLD:
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "IMU {n} temperature calibration's coldest recorded point was {tmin:.1f}C, "
                            "above freezing. For best results, cool the flight controller down to "
                            "around {rec:.0f}C or lower before starting calibration."
                        ).format(n=instance, tmin=tmin, rec=_TCAL_TMIN_RECOMMENDED),
                        timestamp_us=None,
                        value=tmin,
                        param_name=f"INS_TCAL{instance}_TMIN",
                    )
                )

            outcomes.append(self._temp_difference(instance, tmin, tmax))

        return outcomes

    def _param_range(self, param_name: str) -> tuple[float, float] | None:
        """Parse the documented (min, max) Range bounds for a parameter from apm_doc."""
        if self.apm_doc is None:
            return None
        range_str = self.apm_doc.get(param_name, {}).get("fields", {}).get("Range")
        if not isinstance(range_str, str):
            return None
        try:
            low_str, high_str = range_str.split()
            low, high = float(low_str), float(high_str)
        except ValueError:
            return None
        return (low, high) if math.isfinite(low) and math.isfinite(high) else None

    def check_harmonic_notch_filter(self) -> list[LogAnalysis]:
        """Check that the primary harmonic notch filter is enabled, uses a valid mode, and has parameters in range."""
        hntch_enable = self.parameters.get("INS_HNTCH_ENABLE")
        if hntch_enable is None or not math.isfinite(hntch_enable):
            return []

        enabled_codes = find_matching_param_values(self.apm_doc, "INS_HNTCH_ENABLE", "Enabled") if self.apm_doc else set()
        if not enabled_codes:
            return []
        if str(int(hntch_enable)) not in enabled_codes:
            suggested = float(min(int(code) for code in enabled_codes))
            return [
                self.build_parameter_outcome(
                    "INS_HNTCH_ENABLE",
                    hntch_enable,
                    _("Harmonic notch filter is not enabled (INS_HNTCH_ENABLE is {val:.0f}, expected {exp:.0f}).").format(
                        val=hntch_enable, exp=suggested
                    ),
                    suggested_value=suggested,
                )
            ]

        hntch_mode = self.parameters.get("INS_HNTCH_MODE")
        valid_modes = self.apm_doc.get("INS_HNTCH_MODE", {}).get("values", {}) if self.apm_doc else None
        if hntch_mode is None or not math.isfinite(hntch_mode) or not isinstance(valid_modes, dict) or not valid_modes:
            return []

        mode_code = str(int(hntch_mode))
        if mode_code not in valid_modes:
            return [
                self.build_parameter_outcome(
                    "INS_HNTCH_MODE",
                    hntch_mode,
                    _("INS_HNTCH_MODE has an unrecognized value ({val:.0f}).").format(val=hntch_mode),
                )
            ]

        return self._check_notch_sub_parameters(str(valid_modes[mode_code]))

    def _validated_suggestion(self, param_name: str, low: float, high: float, *, strict_low: bool = False) -> float | None:
        """Return the template suggestion for param_name only when it lies inside the valid bounds."""
        step_filename = self.step_for_parameter(param_name)
        suggested, _source = self.expected_parameter_value(step_filename, param_name) if step_filename else (None, "")
        if suggested is None or not math.isfinite(suggested):
            return None
        above_low = suggested > low if strict_low else suggested >= low
        return suggested if above_low and suggested <= high else None

    def _check_notch_sub_parameters(self, mode_label: str) -> list[LogAnalysis]:
        """Validate harmonic notch sub-parameters against apm.pdef.xml ranges and mode requirements."""
        outcomes: list[LogAnalysis] = []

        for param_name in ("INS_HNTCH_FREQ", "INS_HNTCH_BW", "INS_HNTCH_ATT"):
            val = self.parameters.get(param_name)
            bounds = self._param_range(param_name)
            if val is None or not math.isfinite(val) or bounds is None or bounds[0] <= val <= bounds[1]:
                continue
            raw_units = self.apm_doc.get(param_name, {}).get("fields", {}).get("Units") if self.apm_doc else None
            unit_suffix = f" {raw_units}" if isinstance(raw_units, str) and raw_units else ""
            outcomes.append(
                self.build_parameter_outcome(
                    param_name,
                    val,
                    _("{param} is {val:g}{unit}, outside the documented range of {low:g} to {high:g}{unit}.").format(
                        param=param_name, val=val, low=bounds[0], high=bounds[1], unit=unit_suffix
                    ),
                    suggested_value=self._validated_suggestion(param_name, bounds[0], bounds[1]),
                    lookup_expected=False,
                )
            )

        hmncs = self.parameters.get("INS_HNTCH_HMNCS")
        if hmncs is not None and math.isfinite(hmncs) and int(hmncs) == 0:
            outcomes.append(
                self.build_parameter_outcome(
                    "INS_HNTCH_HMNCS",
                    hmncs,
                    _("INS_HNTCH_HMNCS is 0, which disables the harmonic notch filter on all harmonics."),
                )
            )

        if "fixed" not in mode_label.lower():
            ref = self.parameters.get("INS_HNTCH_REF")
            ref_bounds = self._param_range("INS_HNTCH_REF")
            if ref is not None and math.isfinite(ref) and ref_bounds is not None:
                min_ref, max_ref = ref_bounds
                suggested_ref = self._validated_suggestion("INS_HNTCH_REF", min_ref, max_ref, strict_low=True)
                if ref <= min_ref:
                    outcomes.append(
                        self.build_parameter_outcome(
                            "INS_HNTCH_REF",
                            ref,
                            _(
                                "INS_HNTCH_REF is {val:g} with harmonic notch mode {mode}, which disables "
                                "dynamic frequency updates (expected a positive value up to {high:g})."
                            ).format(val=ref, mode=mode_label, high=max_ref),
                            suggested_value=suggested_ref,
                            lookup_expected=False,
                        )
                    )
                elif ref > max_ref:
                    outcomes.append(
                        self.build_parameter_outcome(
                            "INS_HNTCH_REF",
                            ref,
                            _("INS_HNTCH_REF is {val:g}, outside the documented range of {low:g} to {high:g}.").format(
                                val=ref, low=min_ref, high=max_ref
                            ),
                            suggested_value=suggested_ref,
                            lookup_expected=False,
                        )
                    )

        return outcomes

    def check_notch_filter_telemetry_dependency(self) -> list[LogAnalysis]:
        """Warn when a notch filter is configured to track ESC telemetry RPM, but no ESC telemetry was present."""
        esc_columns = self.log_data.get_message_columns("ESC")
        esc_present = esc_columns is not None and len(esc_columns) > 0
        if esc_present:
            return []

        outcomes: list[LogAnalysis] = []
        for mode_param in ("INS_HNTCH_MODE", "INS_HNTC2_MODE"):
            mode = self.parameters.get(mode_param)
            if mode is None or self.apm_doc is None:
                continue

            esc_telemetry_codes = find_matching_param_values(self.apm_doc, mode_param, "ESC Telemetry")
            if str(int(mode)) in esc_telemetry_codes:
                outcomes.append(
                    LogAnalysis(
                        message=_(
                            "{param} is set to ESC Telemetry tracking mode, but no ESC telemetry was present "
                            "in this log. The notch filter could not track motor RPM, and did not "
                            "remove motor noise. Motor vibration noise reached the PID controller inputs."
                        ).format(param=mode_param),
                        timestamp_us=None,
                        value=float(mode),
                        param_name=mode_param,
                        related_step=self.step_for_parameter(mode_param),
                    )
                )
        return outcomes

    def _temp_difference(self, instance: int, tmin: float, tmax: float) -> LogAnalysis:
        """Build the LogAnalysis finding for one IMU instance's achieved calibration spread."""
        spread = tmax - tmin

        if spread < _TCAL_MIN_REQUIRED_SPREAD:
            message = _(
                "IMU {n} temperature calibration spread is only {spread:.1f}C ({tmin:.1f}C to {tmax:.1f}C), "
                "below ArduPilot's required minimum of {min_req:.0f}C. Recalibration needed."
            ).format(n=instance, spread=spread, tmin=tmin, tmax=tmax, min_req=_TCAL_MIN_REQUIRED_SPREAD)
        elif spread < _TCAL_RECOMMENDED_SPREAD:
            message = _(
                "IMU {n} temperature calibration spread is {spread:.1f}C ({tmin:.1f}C to {tmax:.1f}C), "
                "meets the minimum but below the recommended {rec:.0f}C for best coverage."
            ).format(n=instance, spread=spread, tmin=tmin, tmax=tmax, rec=_TCAL_RECOMMENDED_SPREAD)
        else:
            message = _(
                "IMU {n} temperature calibration spread is {spread:.1f}C ({tmin:.1f}C to {tmax:.1f}C), good coverage."
            ).format(n=instance, spread=spread, tmin=tmin, tmax=tmax)

        return LogAnalysis(message=message, timestamp_us=None, value=spread)
