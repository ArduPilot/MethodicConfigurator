"""
Data model for GPS/GNSS availability check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    AvailabilityIssue,
    BaseLogAvailabilityModel,
    LogAvailabilityResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState


class GPSLogAvailabilityModel(BaseLogAvailabilityModel):
    """Checks GPS/GNSS telemetry and configuration availability."""

    def check(self) -> LogAvailabilityResult:
        records = self.log_data.get_message_columns("GPS")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[AvailabilityIssue] = []
        for check in (self.check_status,):
            issues += check()
        issues += self.check_parameters()

        step, name = self.resolve_message_step("GPS", "GPS")
        return self.build_result(issues, name, related_step=step)

    def _diagnose_absence(self) -> LogAvailabilityResult:
        """Diagnose why GPS data is absent using LOG_BITMASK."""
        step, name = self.resolve_message_step("GPS", "GPS")
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "GPS", "GPS", "GPS", not_logged_hint=_("check the GPS physical connection")
        )
        return LogAvailabilityResult(
            available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name, related_step=step
        )

    def check_status(self) -> list[AvailabilityIssue]:
        """Validate GPS fix status."""
        status, issues = self.field_values_or_issue(
            "GPS",
            "Status",
            missing_field_message=_("Status field not present in this firmware's GPS schema"),
            missing_values_message=_("GPS fix status missing from GPS records"),
        )
        if status is not None and max(status) < 3:
            issues.append(AvailabilityIssue(_("GPS never achieved a 3D fix")))
        return issues

    def check_parameters(self) -> list[AvailabilityIssue]:
        """Validate GPS-related parameter configuration."""
        issues: list[AvailabilityIssue] = []
        gps_type = self.parameters.get("GPS_TYPE", self.parameters.get("GPS1_TYPE"))
        if gps_type == 0:
            issues.append(AvailabilityIssue(_("GPS type not configured (set to None)"), self.step_for_parameter("GPS_TYPE")))
        return issues
