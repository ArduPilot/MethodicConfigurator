"""
Data model for MODE message availability check.

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


class ModeLogAvailabilityModel(BaseLogAvailabilityModel):
    """Checks presence of flight mode change data."""

    def check(self) -> LogAvailabilityResult:
        records = self.log_data.get_message_columns("MODE")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[AvailabilityIssue] = []
        for check in (self.check_mode_fields,):
            issues += check()

        step, name = self.resolve_message_step("MODE", "MODE")
        return self.build_result(issues, name, related_step=step)

    def _diagnose_absence(self) -> LogAvailabilityResult:
        """
        Diagnose why MODE data is absent.

        MODE has no LOG_BITMASK bit - it should always be present. Absence is
        unexpected rather than a configuration choice.
        """
        step, name = self.resolve_message_step("MODE", "MODE")
        reason = _("MODE messages not found, this is unexpected since mode changes are always logged")
        issues = [AvailabilityIssue(_("No MODE messages found"), step)]
        return LogAvailabilityResult(
            available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name, related_step=step
        )

    def check_mode_fields(self) -> list[AvailabilityIssue]:
        """Check that Mode/ModeNum/Rsn fields are present and have readable data."""
        return self.check_fields_present("MODE", ("Mode", "ModeNum", "Rsn"))
