"""
Data model for GPS/GNSS quality check.

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


class GPSLogQualityModel(BaseLogQualityAnalysisModel):
    """Checks GPS/GNSS telemetry and configuration quality."""

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("GPS")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_status,):
            issues += check()
        issues += self.check_parameters()

        _, name = self.resolve_message_step("GPS", "GPS")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        """Diagnose why GPS data is absent using LOG_BITMASK."""
        bitmask = self.parameters.get("LOG_BITMASK")
        bitmask_field = get_log_bitmask(self.apm_doc) if self.apm_doc else None
        log_bit = find_log_bit_in_apm_file(bitmask_field, "GPS") if bitmask_field else None

        step, name = self.resolve_message_step("GPS", "GPS")

        if log_bit is not None and bitmask is not None and (int(bitmask) & (1 << log_bit)) == 0:
            reason = _("GPS logging is disabled in LOG_BITMASK")
            issues = [QualityIssue(_("Enable GPS logging (LOG_BITMASK bit) to record GPS data"), step)]
        else:
            reason = _("GPS/GNSS telemetry not logged but logging enabled; check the GPS physical connection")
            issues = [QualityIssue(_("No GPS messages found"), step)]

        return LogQualityResult(available=False, state="warning", reason=reason, issues=issues, name=name)

    def check_status(self) -> list[QualityIssue]:
        """Validate GPS fix status."""
        issues: list[QualityIssue] = []

        if not self.field_available("GPS", "Status"):
            issues.append(QualityIssue(_("Status field not present in this firmware's GPS schema")))
            return issues

        status = self.log_data.get_field("GPS", "Status")
        if len(status) == 0:
            issues.append(QualityIssue(_("GPS fix status missing from GPS records")))
        elif max(status) < 3:
            issues.append(QualityIssue(_("GPS never achieved a 3D fix")))
        return issues

    def check_parameters(self) -> list[QualityIssue]:
        """Validate GPS-related parameter configuration."""
        issues: list[QualityIssue] = []
        gps_type = self.parameters.get("GPS_TYPE", self.parameters.get("GPS1_TYPE"))
        if gps_type == 0:
            issues.append(QualityIssue(_("GPS type not configured (set to None)"), self.step_for_parameter("GPS_TYPE")))
        return issues
