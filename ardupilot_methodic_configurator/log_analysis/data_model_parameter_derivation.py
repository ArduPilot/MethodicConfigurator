"""
Parameter-derivation service used by log-analysis models.

The service adapts Methodic Configurator's configuration-step evaluator to a
small, in-memory API. Analysis models depend on this service rather than on
the filesystem-oriented ConfigurationSteps class.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
from dataclasses import dataclass
from typing import Any, Protocol

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps
from ardupilot_methodic_configurator.log_analysis.utils import APMDoc


@dataclass(frozen=True)
class ParameterDerivationInputs:
    """In-memory context required to evaluate configuration-step parameters."""

    configuration_steps: dict[str, Any]
    parameters: dict[str, float]
    vehicle_components: dict[str, Any]
    apm_doc: APMDoc | None


class ParameterDeriver(Protocol):
    """Minimal parameter-derivation API required by detailed log analysis."""

    def expected_parameter_value(
        self,
        step_filename: str,
        param_name: str,
        inputs: ParameterDerivationInputs,
    ) -> tuple[float | None, str]:
        """Return the expected value and its source, or ``(None, "")`` when unavailable."""

    def derived_and_forced_parameters_matching(self, pattern: str, inputs: ParameterDerivationInputs) -> dict[str, str]:
        """Return matching derived/forced parameter names mapped to their step filenames."""


class ConfigurationStepParameterDeriver:
    """In-memory adapter around the shared configuration-step expression evaluator."""

    def __init__(self) -> None:
        # Construction is intentionally side-effect free: configuration data is
        # supplied by LogAnalysisContext, not loaded from a vehicle directory.
        self._evaluator = ConfigurationSteps(_vehicle_dir="", vehicle_type="")

    def expected_parameter_value(
        self,
        step_filename: str,
        param_name: str,
        inputs: ParameterDerivationInputs,
    ) -> tuple[float | None, str]:
        """Evaluate one forced or derived parameter from supplied in-memory inputs."""
        if step_filename not in inputs.configuration_steps:
            return None, ""

        eval_variables: dict[str, Any] = {"vehicle_components": inputs.vehicle_components}
        if inputs.apm_doc:
            eval_variables["doc_dict"] = inputs.apm_doc
        if inputs.parameters:
            eval_variables["fc_parameters"] = inputs.parameters

        step_dict = inputs.configuration_steps[step_filename]
        forced_error, derived_error = self._evaluator.compute_forced_and_derived_parameters(
            step_filename, step_dict, eval_variables, ignore_fc_derived_param_warnings=True
        )
        if forced_error or derived_error:
            return None, ""

        for source, values_by_step in (
            ("forced", self._evaluator.forced_parameters),
            ("derived", self._evaluator.derived_parameters),
        ):
            if step_filename in values_by_step and param_name in values_by_step[step_filename]:
                return values_by_step[step_filename][param_name].value, source

        return None, ""

    def derived_and_forced_parameters_matching(self, pattern: str, inputs: ParameterDerivationInputs) -> dict[str, str]:
        """Return all forced and derived parameters matching a regular expression."""
        compiled = re.compile(pattern)
        result: dict[str, str] = {}
        for step_filename, step_info in inputs.configuration_steps.items():
            for param_name in step_info.get("derived_parameters", {}):
                if compiled.match(param_name):
                    result[param_name] = step_filename
            for param_name in step_info.get("forced_parameters", {}):
                if compiled.match(param_name):
                    result[param_name] = step_filename
        return result
