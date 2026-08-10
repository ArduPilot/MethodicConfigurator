"""
Data model for VIBE quality check.

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


class VibeLogQualityModel(BaseLogQualityAnalysisModel):
    """
    Checks VIBE data presence and availability for analysis.

    This model only reports whether vibration data exists and is readable.
    Threshold-based judgment (e.g. the ArduPilot wiki's 30/60 m/s/s vibration
    guidance, or clip-count nuance) is deferred to a future analysis layer.
    """

    def check(self) -> LogQualityResult:
        records = self.log_data.get_message_columns("VIBE")
        if records is None or len(records) == 0:
            return self._diagnose_absence()

        issues: list[QualityIssue] = []
        for check in (self.check_vibe_levels, self.check_clipping):
            issues += check()

        _, name = self.resolve_message_step("VIBE", "VIBE")
        return self.build_result(issues, name)

    def _diagnose_absence(self) -> LogQualityResult:
        """
        Diagnose why VIBE data is absent.

        VIBE has no dedicated LOG_BITMASK bit (it rides along with base IMU
        logging), so diagnose_bitmask_absence falls through to its generic
        "not logged" branch here rather than a bitmask-specific one.
        """
        name = self.resolve_message_step("VIBE", "VIBE")[1]
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "VIBE",
            "VIBE",
            "VIBE",
            not_logged_hint=_("check that IMU data is being logged, since VIBE is derived from it"),
        )
        return LogQualityResult(available=False, state=LogQualityState.WARNING, reason=reason, issues=issues, name=name)

    def check_vibe_levels(self) -> list[QualityIssue]:
        """Check that VibeX/Y/Z fields are present and have readable data."""
        return self.check_fields_present("VIBE", ("VibeX", "VibeY", "VibeZ"))

    def check_clipping(self) -> list[QualityIssue]:
        """Check that the Clip field is present and has readable data."""
        _clip, issues = self.field_values_or_issue(
            "VIBE",
            "Clip",
            missing_field_message=_("Clip field not present in this firmware's VIBE schema"),
            missing_values_message=_("Clip values missing from VIBE records"),
        )
        return issues
