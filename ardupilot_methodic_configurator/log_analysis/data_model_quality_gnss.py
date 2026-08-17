"""
Data model for GPS/GNSS quality check.

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


class GPSLogQualityModel(BaseLogModel):
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
        name = self.resolve_message_step("GPS", "GPS")[1]
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "GPS", "GPS", "GPS", not_logged_hint=_("check the GPS physical connection")
        )
        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_status(self) -> list[QualityIssue]:
        """Validate GPS fix status."""
        status, issues = self.field_values_or_issue(
            "GPS",
            "Status",
            missing_field_message=_("Status field not present in this firmware's GPS schema"),
            missing_values_message=_("GPS fix status missing from GPS records"),
        )
        if status is not None and max(status) < 3:
            issues.append(QualityIssue(_("GPS never achieved a 3D fix")))
        return issues

    def check_parameters(self) -> list[QualityIssue]:
        """Validate GPS-related parameter configuration."""
        issues: list[QualityIssue] = []
        gps_type = self.parameters.get("GPS_TYPE", self.parameters.get("GPS1_TYPE"))
        if gps_type == 0:
            issues.append(QualityIssue(_("GPS type not configured (set to None)"), self.step_for_parameter("GPS_TYPE")))
        return issues
