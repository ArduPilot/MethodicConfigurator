"""
Data model for ARM (arming status change) availability check.

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
from ardupilot_methodic_configurator.log_analysis.utils import find_log_bit_in_apm_file, find_matching_param_values

_NAME = "ARM"


class ArmLogAvailabilityModel(BaseLogAvailabilityModel):
    """
    Checks presence of arming/disarming event data.

    ARM is an unconditional logging. Absence is treated as an anomaly.
    """

    def check(self) -> LogAvailabilityResult:
        records = self.log_data.get_message_columns("ARM")

        if records is None or len(records) == 0:
            reason = _("ARM messages not found, that is unexpected since arm/disarm events are always logged")
            issues = [AvailabilityIssue(_("No ARM messages found"))]
            return LogAvailabilityResult(
                available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=_NAME
            )

        issues = self.check_arm_fields()
        return self.build_result(issues, _NAME)

    def check_arm_fields(self) -> list[AvailabilityIssue]:
        """Check that ArmState/ArmChecks/Forced/Method fields are present and have readable data."""
        return self.check_fields_present("ARM", ("ArmState", "ArmChecks", "Forced", "Method"))


class ArmLogAnalysis(BaseLogAnalysisModel):
    """Pre flight safety and frame setup checks paired with ARM availability."""

    def analyse(self) -> LogAnalysisResult:
        outcomes: list[LogAnalysis] = []
        for check in (
            self.check_frame_class,
            self.check_arming_check,
            self.check_fence_enabled,
            self.check_slew_limit_parameters,
        ):
            outcomes += check()

        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Arming & Safety Analysis"),
            reason=_("Arming and safety configuration analysis complete"),
        )

    def check_frame_class(self) -> list[LogAnalysis]:
        """Check that FRAME_CLASS (and Q_FRAME_CLASS when QuadPlane is enabled) is configured."""
        param_names = ["FRAME_CLASS"]
        q_enable = self.parameters.get("Q_ENABLE")
        if q_enable is not None and math.isfinite(q_enable) and q_enable != 0:
            param_names.append("Q_FRAME_CLASS")

        outcomes: list[LogAnalysis] = []
        for param_name in param_names:
            frame_class = self.parameters.get(param_name)
            if frame_class is None or not math.isfinite(frame_class):
                continue

            doc_param = param_name if (self.apm_doc and param_name in self.apm_doc) else "FRAME_CLASS"
            undefined_codes = find_matching_param_values(self.apm_doc, doc_param, "Undefined") if self.apm_doc else set()
            if undefined_codes and str(int(frame_class)) in undefined_codes:
                outcomes.append(
                    self.build_parameter_outcome(
                        param_name,
                        frame_class,
                        _("{param} is {val:.0f} (Undefined). Configure the frame class for your vehicle.").format(
                            param=param_name, val=frame_class
                        ),
                    )
                )
                continue

            valid_values = self.apm_doc.get(doc_param, {}).get("values", {}) if self.apm_doc else None
            if isinstance(valid_values, dict) and valid_values and str(int(frame_class)) not in valid_values:
                outcomes.append(
                    self.build_parameter_outcome(
                        param_name,
                        frame_class,
                        _("{param} has an unrecognized value ({val:.0f}).").format(param=param_name, val=frame_class),
                    )
                )
        return outcomes

    def check_arming_check(self) -> list[LogAnalysis]:
        """Check ARMING_CHECK (pre-4.7) and ARMING_SKIPCHK (4.7+) so pre-arm safety checks are active."""
        outcomes: list[LogAnalysis] = []

        arming_check = self.parameters.get("ARMING_CHECK")
        if arming_check is not None and math.isfinite(arming_check):
            bitmask_field = self.apm_doc.get("ARMING_CHECK", {}).get("fields", {}).get("Bitmask") if self.apm_doc else None
            all_bit = find_log_bit_in_apm_file(bitmask_field, "All") if isinstance(bitmask_field, str) else None
            if all_bit is not None:
                all_mask = 1 << all_bit
                actual = int(arming_check)
                if (actual & all_mask) == 0:
                    if actual == 0:
                        message = _(
                            "ARMING_CHECK is 0 (all pre-arm safety checks are disabled). "
                            "Set it to {all_mask} to enable all checks."
                        )
                    else:
                        message = _(
                            "ARMING_CHECK is {actual} (does not include 'All' pre-arm safety checks). "
                            "Set it to {all_mask} to enable all checks."
                        )
                    outcomes.append(
                        self.build_parameter_outcome(
                            "ARMING_CHECK",
                            arming_check,
                            message.format(actual=actual, all_mask=all_mask),
                            suggested_value=float(all_mask),
                        )
                    )

        skip_chk = self.parameters.get("ARMING_SKIPCHK")
        if skip_chk is not None and math.isfinite(skip_chk) and int(skip_chk) != 0:
            outcomes.append(
                self.build_parameter_outcome(
                    "ARMING_SKIPCHK",
                    skip_chk,
                    _(
                        "ARMING_SKIPCHK is {actual} (pre-arm safety checks are skipped). Set it to 0 to enable all checks."
                    ).format(actual=int(skip_chk)),
                    suggested_value=0.0,
                )
            )

        return outcomes

    def check_fence_enabled(self) -> list[LogAnalysis]:
        """Warn when the geofence (FENCE_ENABLE) is disabled, without offering a blind auto-fix."""
        fence_enable = self.parameters.get("FENCE_ENABLE")
        if fence_enable is None or not math.isfinite(fence_enable):
            return []

        autoenable = self.parameters.get("FENCE_AUTOENABLE")
        if autoenable is not None and math.isfinite(autoenable) and autoenable != 0:
            return []

        enabled_codes = find_matching_param_values(self.apm_doc, "FENCE_ENABLE", "Enabled") if self.apm_doc else set()
        if not enabled_codes or str(int(fence_enable)) in enabled_codes:
            return []

        return [
            self.build_parameter_outcome(
                "FENCE_ENABLE",
                fence_enable,
                _(
                    "FENCE_ENABLE is {val:.0f} (geofence disabled). Configure fence limits and enable "
                    "the geofence to protect the vehicle from flying out of bounds."
                ).format(val=fence_enable),
                lookup_expected=False,
            )
        ]

    def check_slew_limit_parameters(self) -> list[LogAnalysis]:
        """Check that rate-controller slew-rate limiters (ATC_RAT_*_SMAX) are not disabled (0)."""
        outcomes: list[LogAnalysis] = []
        for param_name in ("ATC_RAT_RLL_SMAX", "ATC_RAT_PIT_SMAX", "ATC_RAT_YAW_SMAX"):
            smax = self.parameters.get(param_name)
            if smax is None or not math.isfinite(smax) or smax != 0:
                continue
            outcomes.append(
                self.build_parameter_outcome(
                    param_name,
                    smax,
                    _(
                        "{param} is 0 (rate-controller slew-rate limiter disabled). "
                        "Set a non-zero value to protect against high-frequency control oscillations."
                    ).format(param=param_name),
                )
            )
        return outcomes
