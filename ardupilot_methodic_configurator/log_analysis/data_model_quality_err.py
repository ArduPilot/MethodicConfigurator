"""
Data model for ERR message quality check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogQualityAnalysisModel,
    LogQualityResult,
    QualityIssue,
)


class ErrLogQualityModel(BaseLogQualityAnalysisModel):
    """
    Checks presence and readability of subsystem error/recovery events.

    An empty ERR message is NOT a data-quality problem, it means no
    errors occurred during the flight, which is the good outcome.

    """

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("ERR")

        if records is None or len(records) == 0:
            return LogQualityResult(
                available=True,
                state=LogQualityState.INFO,
                reason=_("No errors logged during this flight"),
                issues=[],
                name="ERR",
            )

        issues: list[QualityIssue] = self.check_err_fields()
        return self.build_result(issues, "ERR")

    def check_err_fields(self) -> list[QualityIssue]:
        """Check that Subsys/ECode fields are present and have readable data."""
        return self.check_fields_present("ERR", ("Subsys", "ECode"), scaled=False)
