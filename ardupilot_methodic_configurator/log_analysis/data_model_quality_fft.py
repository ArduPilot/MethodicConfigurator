"""
Data model for FFT / raw IMU batch logging quality check (ISBH and ISBD).

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogModel,
    LogQualityResult,
    QualityIssue,
)


class FftLogQualityModel(BaseLogModel):
    """Checks presence of raw IMU batch logging data (ISBH and ISBD samples)."""

    def check(self) -> LogQualityResult:
        header_records = self.log_data.get_message_columns("ISBH")
        if header_records is None or len(header_records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_header_fields, self.check_batch_data_present):
            issues += check()

        _, name = self.resolve_message_step("ISBH", "FFT")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        """Diagnose why ISBH/ISBD data is absent using INS_LOG_BAT_MASK."""
        step, name = self.resolve_message_step("ISBH", "FFT")

        bat_mask = self.parameters.get("INS_LOG_BAT_MASK")

        if bat_mask is not None and int(bat_mask) == 0:
            reason = _("Raw IMU batch logging is disabled (INS_LOG_BAT_MASK is 0)")
            issues = [
                QualityIssue(
                    _("Set INS_LOG_BAT_MASK to enable raw IMU batch logging for FFT analysis"),
                    self.step_for_parameter("INS_LOG_BAT_MASK"),
                )
            ]
        else:
            reason = _("Raw IMU batch logging enabled but no data, check firmware build supports batch logging")
            issues = [QualityIssue(_("No ISBH messages found"), step)]

        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_header_fields(self) -> list[QualityIssue]:
        """Check that ISBH's key fields are present and have readable data."""
        return self.check_fields_present("ISBH", ("type", "instance", "smp_cnt", "smp_rate"))

    def check_batch_data_present(self) -> list[QualityIssue]:
        """Check that ISBD and ISBH header."""
        records = self.log_data.get_message_columns("ISBD")
        if records is None or len(records) == 0:
            return [QualityIssue(_("ISBH header present but ISBD batch samples are missing"))]

        issues: list[QualityIssue] = []
        for axis_field in ("x", "y", "z"):
            _values, field_issues = self.field_values_or_issue(
                "ISBD",
                axis_field,
                missing_field_message=_("{field} field not present in this firmware's ISBD schema").format(field=axis_field),
                missing_values_message=_("{field} values missing from ISBD records").format(field=axis_field),
            )
            issues += field_issues

        return issues
