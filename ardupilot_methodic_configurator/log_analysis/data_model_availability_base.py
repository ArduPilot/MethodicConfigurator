"""
Base Availability model for all base classes and combined results.

Defines the common result data model and the base class used by all subsystem availability analysis models.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import TYPE_CHECKING, Any

import numpy as np

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import (
    AvailabilityIssue,
    LogAvailabilityResult,
    LogAvailabilityState,
)
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_derivation import ParameterDerivationInputs
from ardupilot_methodic_configurator.log_analysis.utils import (
    find_configuration_step_for_message,
    find_configuration_step_for_parameter,
    find_log_bit_in_apm_file,
    get_log_bitmask,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysisResult
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData


class BaseLogModel:
    """Common log-data services shared by availability and analysis models."""

    def __init__(
        self,
        log_data: "LogData",
        context: LogAnalysisContext,
    ) -> None:
        self.configuration_steps = context.configuration_steps
        self.log_data = log_data
        self.parameters = context.parameters
        self.vehicle_components = context.vehicle_components
        self.apm_doc = context.apm_doc
        self.parameter_deriver = context.parameter_deriver

    def step_for_parameter(self, param_name: str) -> str:
        try:
            return find_configuration_step_for_parameter(self.configuration_steps, param_name) or ""
        except ValueError:
            return ""

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
    ) -> tuple[Any | None, list[AvailabilityIssue]]:
        """Return field values or a single issue explaining why values are unavailable."""
        issues: list[AvailabilityIssue] = []
        if not self.field_available(message_name, field_name):
            issues.append(AvailabilityIssue(missing_field_message))
            return None, issues

        values = self.log_data.get_field(message_name, field_name, scaled=scaled)
        if len(values) == 0:
            issues.append(AvailabilityIssue(missing_values_message))
            return None, issues

        if np.issubdtype(values.dtype, np.number) and not np.isfinite(values).all():
            issues.append(AvailabilityIssue(_("{field} contains non-finite telemetry values").format(field=field_name)))
            return None, issues

        return values, issues

    def diagnose_bitmask_absence(
        self,
        message_name: str,
        bit_name: str,
        fallback_name: str,
        *,
        not_logged_hint: str,
    ) -> tuple[str, list[AvailabilityIssue], bool]:
        """
        Diagnose absence of a message via LOG_BITMASK.

        Returns: reason, issues, bitmask_disabled.
        """
        bitmask = self.parameters.get("LOG_BITMASK")
        bitmask_field = get_log_bitmask(self.apm_doc) if self.apm_doc else None
        log_bit = find_log_bit_in_apm_file(bitmask_field, bit_name) if bitmask_field else None

        step, _name = self.resolve_message_step(message_name, fallback_name)

        if log_bit is not None and bitmask is not None and (int(bitmask) & (1 << log_bit)) == 0:
            reason = _("{message} logging is disabled in LOG_BITMASK").format(message=fallback_name)
            suggested_value = float(int(bitmask) | (1 << log_bit))
            issues = [
                AvailabilityIssue(
                    _("Enable {message} logging (LOG_BITMASK bit)").format(message=fallback_name),
                    step,
                    param_name="LOG_BITMASK",
                    suggested_value=suggested_value,
                )
            ]
            return reason, issues, True

        reason = _("{message} telemetry not logged but logging enabled; {hint}").format(
            message=fallback_name, hint=not_logged_hint
        )
        issues = [AvailabilityIssue(_("No {message} messages found").format(message=message_name), step)]
        return reason, issues, False

    def check_fields_present(
        self,
        message_name: str,
        field_names: tuple[str, ...],
        *,
        scaled: bool = True,
    ) -> list[AvailabilityIssue]:
        """Check that each field in field_names exists on message_name and has readable data."""
        issues: list[AvailabilityIssue] = []
        for field_name in field_names:
            _values, field_issues = self.field_values_or_issue(
                message_name,
                field_name,
                missing_field_message=_("{field} field not present in this firmware's {msg} schema").format(
                    field=field_name, msg=message_name
                ),
                missing_values_message=_("{field} values missing from {msg} records").format(
                    field=field_name, msg=message_name
                ),
                scaled=scaled,
            )
            issues += field_issues
        return issues


class BaseLogAvailabilityModel(BaseLogModel):
    """Base class for subsystem availability models."""

    def check(self) -> LogAvailabilityResult:
        """Run the model-specific availability analysis and return a result."""
        msg = f"{self.__class__.__name__} must implement check()"
        raise NotImplementedError(msg)

    def build_result(self, issues: list[AvailabilityIssue], name: str, related_step: str = "") -> LogAvailabilityResult:
        return LogAvailabilityResult(
            available=True,
            state=LogAvailabilityState.INFO if not issues else LogAvailabilityState.WARNING,
            reason=_("{name} data present and good for analysis").format(name=name)
            if not issues
            else _("{name} data has availability issues").format(name=name),
            issues=issues,
            name=name,
            related_step=related_step,
        )


class BaseLogAnalysisModel(BaseLogModel):
    """Base class for detailed analysis models requiring configuration evaluation."""

    def __init__(self, log_data: "LogData", context: LogAnalysisContext) -> None:
        BaseLogModel.__init__(self, log_data, context)

    def analyse(self) -> "LogAnalysisResult":
        """Run the model-specific detailed analysis and return its result."""
        msg = f"{self.__class__.__name__} must implement analyse()"
        raise NotImplementedError(msg)

    def expected_parameter_value(self, step_filename: str, param_name: str) -> tuple[float | None, str]:
        """
        Compute what a derived or forced parameter's value should be at a given step.

        Returns: (expected_value, source) where source is "forced" or "derived",
        or None if this parameter isn't forced or derived at this step.
        """
        return self.parameter_deriver.expected_parameter_value(step_filename, param_name, self._parameter_derivation_inputs())

    def derived_and_forced_parameters_matching(self, pattern: str) -> dict[str, str]:
        """
        Find every forced and derived parameter across all configuration steps.

        Returns: param_name: step_filename
        """
        return self.parameter_deriver.derived_and_forced_parameters_matching(pattern, self._parameter_derivation_inputs())

    def _parameter_derivation_inputs(self) -> ParameterDerivationInputs:
        """Build the in-memory inputs used by the injected derivation service."""
        return ParameterDerivationInputs(
            configuration_steps=self.configuration_steps,
            parameters=self.parameters,
            vehicle_components=self.vehicle_components,
            apm_doc=self.apm_doc,
        )
