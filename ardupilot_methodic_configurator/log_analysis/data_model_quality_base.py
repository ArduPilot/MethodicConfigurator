"""
Base Quality model for all base classes and combined results.

Defines the common result data model and the base class used by all subsystem quality analysis models.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData
from ardupilot_methodic_configurator.log_analysis.backend_log_quality_check import (
    find_step_for_message,
    find_step_for_parameter,
)


@dataclass
class QualityIssue:
    """One detected issue, paired with the configuration step that would fix it."""

    message: str
    config_step: str = ""


@dataclass
class LogQualityResult:
    """Result produced by a subsystem quality model (battery, GPS, etc.)."""

    available: bool
    state: str
    reason: str
    issues: list[QualityIssue]
    name: str


class BaseLogQualityAnalysisModel:
    """Base class for log analysis models."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        log_data: LogData,
        parameters: dict[str, float],
        configuration_steps: dict[str, Any],
        apm_doc: str | None,
        vehicle_components: dict[str, Any] | None = None,
    ) -> None:
        self.log_data = log_data
        self.parameters = parameters or {}
        self.vehicle_components = vehicle_components or {}
        self.configuration_steps = configuration_steps
        self.apm_doc = apm_doc

    def step_for_parameter(self, param_name: str) -> str:
        return find_step_for_parameter(self.configuration_steps, param_name) or ""

    def build_result(self, issues: list[QualityIssue], name: str) -> LogQualityResult:
        return LogQualityResult(
            available=True,
            state="info" if not issues else "warning",
            reason=_("{name} data present and good for analysis").format(name=name)
            if not issues
            else _("{name} data has quality issues").format(name=name),
            issues=issues,
            name=name,
        )

    def resolve_message_step(self, message_name: str, fallback_name: str) -> tuple[str, str]:
        """
        Resolve the configuration step and display name for a message this model checks.

        Returns: config_step, name.
        """
        resolved = find_step_for_message(self.configuration_steps, message_name)
        if resolved is None:
            return "", fallback_name
        step, related = resolved
        return step, related.get(message_name, {}).get("name", fallback_name)

    def field_available(self, message_name: str, field_name: str) -> bool:
        """Check whether a field exists in this log's schema for a message type, before reading it."""
        columns = self.log_data.get_message_columns(message_name)
        return columns is not None and field_name in (columns.dtype.names or ())
