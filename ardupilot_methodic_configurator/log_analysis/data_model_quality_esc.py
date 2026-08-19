"""
Data model for ESC quality check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import statistics

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_par_dict import is_within_tolerance
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogModel,
    LogQualityResult,
    QualityIssue,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_param_metadata import enum_value_name
from ardupilot_methodic_configurator.log_analysis.utils import find_matching_param_values

_MOT_SPIN_MIN_REQUIRED_MARGIN = 0.03


class EscLogQualityModel(BaseLogModel):
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


class EscLogAnalysis(BaseLogModel):
    """
    ESC analysis on the data from the log.

    Runs after ESC quality model passes with the required data.
    """

    def analyse(self) -> LogAnalysisResult:
        records = self.log_data.get_message_columns("ESC")
        if records is None or len(records) == 0:
            return LogAnalysisResult(available=False, outcomes=[], name=_("ESC Analysis"), reason=_("No ESC data available"))

        outcomes: list[LogAnalysis] = []
        outcomes += self.check_motor_spin_spread()
        outcomes += self.check_per_instance_errors()
        outcomes += self.check_rpm_while_armed()
        outcomes += self.check_current_imbalance()
        outcomes += self.check_dshot_output_rate()

        step, _name = self.resolve_message_step("ESC", "ESC")
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("ESC Analysis"),
            reason=_("ESC analysis complete"),
            related_step=step,
        )

    def _armed_time_windows(self) -> list[tuple[float, float]]:
        """Build (arm_time_us, disarm_time_us) pairs from ARM message transitions."""
        columns = self.log_data.get_message_columns("ARM")
        names = tuple(columns.dtype.names or ()) if columns is not None else ()
        if columns is None or "ArmState" not in names or "TimeUS" not in names:
            return []

        arm_state = self.log_data.get_field("ARM", "ArmState", scaled=False)
        time_us = self.log_data.get_field("ARM", "TimeUS", scaled=False)

        windows: list[tuple[float, float]] = []
        arm_time: float | None = None
        for state, ts in zip(arm_state, time_us, strict=True):
            if state and arm_time is None:
                arm_time = float(ts)
            elif not state and arm_time is not None:
                windows.append((arm_time, float(ts)))
                arm_time = None

        # Vehicle still armed at end of log (no matching disarm event)
        if arm_time is not None and len(time_us) > 0:
            windows.append((arm_time, float(time_us[-1])))

        return windows

    def check_rpm_while_armed(self) -> list[LogAnalysis]:
        """Report ESC outputs whose RPM was zero for a sustained period while the vehicle was armed."""
        windows = self._armed_time_windows()
        if not windows:
            return []

        columns = self.log_data.get_message_columns("ESC")
        names = tuple(columns.dtype.names or ()) if columns is not None else ()
        if "Instance" not in names or "RPM" not in names or "TimeUS" not in names:
            return []

        instance_numbers = self.log_data.get_field("ESC", "Instance", scaled=False)
        rpm_values = self.log_data.get_field("ESC", "RPM")
        time_us = self.log_data.get_field("ESC", "TimeUS", scaled=False)

        outcomes: list[LogAnalysis] = []
        for instance in sorted(set(instance_numbers.tolist())):
            mask = instance_numbers == instance
            inst_times = time_us[mask]
            inst_rpm = rpm_values[mask]

            for arm_time, disarm_time in windows:
                window_mask = (inst_times >= arm_time) & (inst_times <= disarm_time)
                if not window_mask.any():
                    continue
                windowed_rpm = inst_rpm[window_mask]
                if windowed_rpm.max() == 0:
                    outcomes.append(
                        LogAnalysis(
                            message=_(
                                "ESC output {instance} reported zero RPM throughout an armed period "
                                "({start:.1f}s to {end:.1f}s), the motor may not have responded."
                            ).format(instance=int(instance), start=arm_time / 1e6, end=disarm_time / 1e6),
                            timestamp_us=arm_time,
                            value=0.0,
                        )
                    )
        return outcomes

    def check_motor_spin_spread(self) -> list[LogAnalysis]:
        """Check MOT_SPIN_MIN >= MOT_SPIN_ARM + 0.03."""
        spin_arm = self.parameters.get("MOT_SPIN_ARM")
        spin_min = self.parameters.get("MOT_SPIN_MIN")
        if spin_arm is None or spin_min is None:
            return []

        required_min = spin_arm + _MOT_SPIN_MIN_REQUIRED_MARGIN
        if spin_min < required_min and not is_within_tolerance(spin_min, required_min):
            return [
                LogAnalysis(
                    message=_(
                        "MOT_SPIN_MIN ({spin_min:.3f}) is below MOT_SPIN_ARM + {required:.2f} ({required_min:.3f}). "
                        "AMC's tuning guide requires MOT_SPIN_MIN to be at least {required:.2f} above MOT_SPIN_ARM "
                        "({spin_arm:.3f}). Motors may not spin reliably once armed."
                    ).format(
                        spin_min=spin_min,
                        required=_MOT_SPIN_MIN_REQUIRED_MARGIN,
                        required_min=required_min,
                        spin_arm=spin_arm,
                    ),
                    timestamp_us=None,
                    value=spin_min - required_min,
                    param_name="MOT_SPIN_MIN",
                    suggested_value=required_min,
                    related_step=self.step_for_parameter("MOT_SPIN_MIN"),
                )
            ]
        return []

    def check_per_instance_errors(self) -> list[LogAnalysis]:
        """Report peak error rate per ESC output, as data - no threshold judgment."""
        columns = self.log_data.get_message_columns("ESC")
        names = tuple(columns.dtype.names or ()) if columns is not None else ()
        if "Instance" not in names or "Err" not in names or "TimeUS" not in names:
            return []

        instance_numbers = self.log_data.get_field("ESC", "Instance", scaled=False)
        err_values = self.log_data.get_field("ESC", "Err")
        time_us = self.log_data.get_field("ESC", "TimeUS", scaled=False)

        outcomes: list[LogAnalysis] = []
        for instance in sorted(set(instance_numbers.tolist())):
            mask = instance_numbers == instance
            instance_errs = err_values[mask]
            instance_times = time_us[mask]

            peak_err = float(instance_errs.max())
            peak_idx = instance_errs.argmax()
            outcomes.append(
                LogAnalysis(
                    message=_("ESC output {instance} peak error rate: {err:.1f}%").format(
                        instance=int(instance), err=peak_err
                    ),
                    timestamp_us=float(instance_times[peak_idx]),
                    value=peak_err,
                )
            )
        return outcomes

    def check_current_imbalance(self) -> list[LogAnalysis]:
        """
        Report ESC outputs, average current is separated from the rest.

        The largest gap between sorted per-instance current means exceeds the sum
        of all other gaps combined.
        """
        columns = self.log_data.get_message_columns("ESC")
        names = tuple(columns.dtype.names or ()) if columns is not None else ()
        if "Instance" not in names or "Curr" not in names or "TimeUS" not in names:
            return []

        instance_numbers = self.log_data.get_field("ESC", "Instance", scaled=False)
        curr_values = self.log_data.get_field("ESC", "Curr")
        time_us = self.log_data.get_field("ESC", "TimeUS", scaled=False)

        instances = sorted(set(instance_numbers.tolist()))
        if len(instances) < 3:
            return []

        means = {inst: float(curr_values[instance_numbers == inst].mean()) for inst in instances}
        sorted_items = sorted(means.items(), key=lambda kv: kv[1])
        values = [v for _, v in sorted_items]

        total_range = values[-1] - values[0]
        if total_range == 0:
            return []

        gaps = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        max_gap = max(gaps)
        max_gap_idx = gaps.index(max_gap)

        if max_gap <= (total_range - max_gap):
            return []

        lower_group = sorted_items[: max_gap_idx + 1]
        upper_group = sorted_items[max_gap_idx + 1 :]
        outlier_group = lower_group if len(lower_group) < len(upper_group) else None
        if outlier_group is None and len(upper_group) < len(lower_group):
            outlier_group = upper_group
        if outlier_group is None:
            return []

        median_curr = statistics.median(values)
        outcomes: list[LogAnalysis] = []
        for inst, inst_mean in outlier_group:
            mask = instance_numbers == inst
            inst_curr = curr_values[mask]
            inst_times = time_us[mask]
            furthest_idx = abs(inst_curr - median_curr).argmax()

            outcomes.append(
                LogAnalysis(
                    message=_(
                        "ESC output {instance} drew {mean:.2f}A on average,"
                        "current drawn by the other {n} ESC output(s) (median {median:.2f}A). If unexpected "
                        "for this vehicle's configuration, check for a mechanical or wiring issue."
                    ).format(instance=int(inst), mean=inst_mean, n=len(instances) - len(outlier_group), median=median_curr),
                    timestamp_us=float(inst_times[furthest_idx]),
                    value=inst_mean,
                )
            )
        return outcomes

    _DSHOT_OUTPUT_RATE_WARN_THRESHOLD = 1000.0  # Amilcar's stated threshold, Hz

    def check_dshot_output_rate(self) -> list[LogAnalysis]:
        """Check SCHED_LOOP_RATE * SERVO_DSHOT_RATE effective output rate against a minimum threshold."""
        loop_rate = self.parameters.get("SCHED_LOOP_RATE")
        dshot_rate_code = self.parameters.get("SERVO_DSHOT_RATE")
        if loop_rate is None or dshot_rate_code is None:
            return []

        label = enum_value_name(self.apm_doc, "SERVO_DSHOT_RATE", dshot_rate_code)
        if label is not None and label.lower() == "1khz":
            effective_rate = 1000.0
        else:
            multiplier = self._dshot_rate_multiplier(dshot_rate_code)
            if multiplier is None:
                return []  # unknown enum value, skip
            effective_rate = loop_rate * multiplier

        if effective_rate <= 1000.0:
            return [
                LogAnalysis(
                    message=_(
                        "Effective DShot output rate is {rate:.0f}Hz (SCHED_LOOP_RATE={loop:.0f}Hz, "
                        "SERVO_DSHOT_RATE={dshot!r}), at or below the {threshold:.0f}Hz level Amilcar flagged as "
                        "problematic. apm.pdef.xml also states SERVO_DSHOT_RATE should never be set below 500Hz."
                    ).format(rate=effective_rate, loop=loop_rate, dshot=label, threshold=1000.0),
                    timestamp_us=None,
                    value=effective_rate,
                    param_name="SERVO_DSHOT_RATE",
                    related_step=self.step_for_parameter("SERVO_DSHOT_RATE"),
                )
            ]
        return []

    def _dshot_rate_multiplier(self, dshot_rate_code: float) -> float | None:  # noqa: PLR0911
        """
        Resolve SERVO_DSHOT_RATE's effective multiplier from its apm.pdef.xml enum label.

        Returns None if the label can't be parsed (unexpected/unknown enum value).
        """
        label = enum_value_name(self.apm_doc, "SERVO_DSHOT_RATE", dshot_rate_code)
        if label is None:
            return None
        label = label.lower()
        if label == "1khz":
            return None  # fixed rate, not a multiple of loop rate - handled separately
        if label == "loop-rate":
            return 1.0
        if label == "double loop-rate":
            return 2.0
        if label == "triple loop-rate":
            return 3.0
        if label == "quadruple loop rate":
            return 4.0
        return None
