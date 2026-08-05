"""
Base Quality model for all base classes and combined results.

Defines the common result data model and the base class used by all subsystem quality analysis models.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import TYPE_CHECKING, Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import (
    LogQualityResult,
    LogQualityState,
    QualityIssue,
)
from ardupilot_methodic_configurator.log_analysis.utils import (
    find_configuration_step_for_message,
    find_configuration_step_for_parameter,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData


class BaseLogQualityAnalysisModel:
    """Base class for log analysis models."""

    def __init__(
        self,
        log_data: "LogData",
        context: LogAnalysisContext,
    ) -> None:
        self.log_data = log_data
        self.parameters = context.parameters
        self.vehicle_components = context.vehicle_components
        self.configuration_steps = context.configuration_steps
        self.apm_doc = context.apm_doc

    def check(self) -> LogQualityResult:
        """Run the model-specific quality analysis and return a result."""
        msg = f"{self.__class__.__name__} must implement check()"
        raise NotImplementedError(msg)

    def step_for_parameter(self, param_name: str) -> str:
        try:
            return find_configuration_step_for_parameter(self.configuration_steps, param_name) or ""
        except ValueError:
            return ""

    def build_result(self, issues: list[QualityIssue], name: str) -> LogQualityResult:
        return LogQualityResult(
            available=True,
            state=LogQualityState.INFO if not issues else LogQualityState.WARNING,
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
        try:
            resolved = find_configuration_step_for_message(self.configuration_steps, message_name)
        except ValueError:
            return "", fallback_name
        if resolved is None:
            return "", fallback_name
        step, related = resolved
        return step, related.get(message_name, {}).get("name", fallback_name)

    def field_available(self, message_name: str, field_name: str) -> bool:
        """Check whether a field exists in this log's schema for a message type, before reading it."""
        columns = self.log_data.get_message_columns(message_name)
        return columns is not None and field_name in (columns.dtype.names or ())

    def field_values_or_issue(  # pylint: disable=too-many-arguments
        self,
        message_name: str,
        field_name: str,
        *,
        scaled: bool = True,
        missing_field_message: str,
        missing_values_message: str,
    ) -> tuple[Any | None, list[QualityIssue]]:
        """Return field values or a single issue explaining why values are unavailable."""
        issues: list[QualityIssue] = []
        if not self.field_available(message_name, field_name):
            issues.append(QualityIssue(missing_field_message))
            return None, issues

        values = self.log_data.get_field(message_name, field_name, scaled=scaled)
        if len(values) == 0:
            issues.append(QualityIssue(missing_values_message))
            return None, issues

        return values, issues
