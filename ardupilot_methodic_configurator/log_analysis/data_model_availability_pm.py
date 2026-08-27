"""
Data model for PM availability check.

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


class PmLogAvailabilityModel(BaseLogAvailabilityModel):
    """
    Checks presence and readability of system performance (PM) data.

    Gated by LOG_BITMASK bit 3,
    """

    def check(self) -> LogAvailabilityResult:
        records = self.log_data.get_message_columns("PM")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues = self.check_pm_fields()
        step, name = self.resolve_message_step("PM", "PM")
        return self.build_result(issues, name, related_step=step)

    def _diagnose_absence(self) -> LogAvailabilityResult:
        """Diagnose why PM data is absent using LOG_BITMASK."""
        step, name = self.resolve_message_step("PM", "PM")
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "PM",
            "System Performance",
            "PM",
            not_logged_hint=_("check firmware build supports performance monitor logging"),
        )
        return LogAvailabilityResult(
            available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name, related_step=step
        )

    def check_pm_fields(self) -> list[AvailabilityIssue]:
        """Validate whichever known PM fields are provided by this firmware's schema."""
        optional_fields = ("Load", "Mem", "NLon", "InE", "ErC")
        available_fields = tuple(field_name for field_name in optional_fields if self.field_available("PM", field_name))
        return self.check_fields_present("PM", available_fields)
