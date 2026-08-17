"""
Data model for PM quality check.

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


class PmLogQualityModel(BaseLogModel):
    """
    Checks presence and readability of system performance (PM) data.

    Gated by LOG_BITMASK bit 3,
    """

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("PM")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues = self.check_pm_fields()
        _, name = self.resolve_message_step("PM", "PM")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        """Diagnose why PM data is absent using LOG_BITMASK."""
        name = self.resolve_message_step("PM", "PM")[1]
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "PM",
            "System Performance",
            "PM",
            not_logged_hint=_("check firmware build supports performance monitor logging"),
        )
        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_pm_fields(self) -> list[QualityIssue]:
        """Check that key PM fields are present and have readable data."""
        return self.check_fields_present("PM", ("Load", "Mem", "NLon", "InE", "ErC"), scaled=False)
