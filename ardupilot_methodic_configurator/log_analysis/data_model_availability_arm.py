"""
Data model for ARM (arming status change) availability check.

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
