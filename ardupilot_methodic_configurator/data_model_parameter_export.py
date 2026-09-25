"""
Business logic for exporting flight-controller parameters.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from typing import Any

from ardupilot_methodic_configurator.annotate_params import update_parameter_documentation
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_configuration_step import ConfigurationStepProcessor
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_conversion import parameters_as_par_dict


@dataclass(frozen=True)
class FilterPair:
    """The two choices for one binary parameter property."""

    include_matching: bool
    include_other: bool
    matching_suffix: str
    other_suffix: str

    def matches(self, value: bool) -> bool:
        """Accept a property value when its corresponding choice is selected."""
        return self.include_matching if value else self.include_other

    def filename_suffix(self) -> str:
        """Describe a restricted pair; omit the suffix for both or neither."""
        if self.include_matching != self.include_other:
            return self.matching_suffix if self.include_matching else self.other_suffix
        return ""


@dataclass(frozen=True)
class ParameterExportFilters:  # pylint: disable=too-many-instance-attributes
    """Filter choices used when selecting parameters for export."""

    include_calibrations: bool = False
    include_non_calibrations: bool = True
    include_read_only: bool = False
    include_non_read_only: bool = True
    include_default_values: bool = False
    include_non_default_values: bool = True
    include_inside_limits: bool = True
    include_outside_limits: bool = True

    def pairs(self) -> tuple[FilterPair, FilterPair, FilterPair, FilterPair]:
        """Return filter pairs in the order used by filenames and matching."""
        return (
            FilterPair(self.include_calibrations, self.include_non_calibrations, "calibrations", "non-calibrations"),
            FilterPair(self.include_read_only, self.include_non_read_only, "read-only", "non-read-only"),
            FilterPair(self.include_default_values, self.include_non_default_values, "default-values", "non-default-values"),
            FilterPair(
                self.include_inside_limits,
                self.include_outside_limits,
                "inside-or-undocumented-limits",
                "outside-limits",
            ),
        )


def build_export_filename(vehicle_name: str, filters: ParameterExportFilters) -> str:
    """Build a descriptive parameter export filename from the selected filter options."""
    suffixes = (pair.filename_suffix() for pair in filters.pairs())
    filename_parts = [vehicle_name, *(suffix for suffix in suffixes if suffix)]
    return "_".join(filename_parts) + ".param"


def create_fc_parameter_snapshot(
    config_step_processor: ConfigurationStepProcessor,
    fc_parameters: dict[str, float],
) -> dict[str, ArduPilotParameter]:
    """Create independent parameter objects for the current FC values."""
    return {
        param_name: config_step_processor.create_ardupilot_parameter(
            param_name,
            Par(param_value),
            "",
            fc_parameters,
        )
        for param_name, param_value in fc_parameters.items()
    }


def filter_parameters_for_export(
    parameters: dict[str, ArduPilotParameter], filters: ParameterExportFilters
) -> dict[str, ArduPilotParameter]:
    """Return parameters matching every selected export filter row."""

    def is_outside_limits(parameter: ArduPilotParameter) -> bool:
        return bool(parameter.fc_value_is_above_limit() or parameter.fc_value_is_below_limit())

    calibration_filter, read_only_filter, default_filter, limits_filter = filters.pairs()

    return {
        param_name: parameter
        for param_name, parameter in parameters.items()
        if calibration_filter.matches(parameter.is_calibration)
        and read_only_filter.matches(parameter.is_readonly)
        and default_filter.matches(parameter.fc_value_equals_default_value)
        and limits_filter.matches(not is_outside_limits(parameter))
    }


def export_parameters(
    parameters: dict[str, ArduPilotParameter],
    filename: str,
    annotate_doc: bool,
    doc_dict: dict[str, Any],
    param_default_dict: ParDict,
) -> None:
    """Export selected FC parameters without changing AMC project state."""
    params = parameters_as_par_dict(parameters)
    params.export_to_param(filename)
    if annotate_doc:
        update_parameter_documentation(doc_dict, filename, "missionplanner", param_default_dict)


def sorted_export_parameter_names(
    parameters: dict[str, ArduPilotParameter], column: str, descending: bool = False
) -> list[str]:
    """Order exported parameters by name, numeric FC value, or unit."""
    if column not in {"name", "fc_value", "unit"}:
        msg = f"Unknown export sort column: {column}"
        raise ValueError(msg)

    def sort_key(name: str) -> tuple[float | str, str]:
        parameter = parameters[name]
        if column == "fc_value":
            return (float(parameter.fc_value_as_string), name)
        value = parameter.unit if column == "unit" else name
        return (value.casefold(), name)

    return sorted(parameters, key=sort_key, reverse=descending)
