"""
Configuration step data model for parameter processing and domain model creation.

This file contains business logic for processing configuration steps, including parameter
computation, domain model creation, and connection renaming operations.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import info as logging_info
from typing import Any, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter


class ConfigurationStepProcessor:
    """
    Handles configuration step processing operations.

    This class encapsulates the business logic for processing configuration steps,
    including parameter computation, domain model creation, and connection renaming.
    """

    def __init__(self, local_filesystem: LocalFilesystem) -> None:
        """
        Initialize the configuration step processor.

        Args:
            local_filesystem: The local filesystem instance to work with

        """
        self.local_filesystem = local_filesystem

    def process_configuration_step(
        self,
        selected_file: str,
        fc_parameters: dict[str, float],
        variables: dict,
    ) -> tuple[dict[str, ArduPilotParameter], bool, list[tuple[str, str]], list[tuple[str, str]]]:
        """
        Process a configuration step including parameter computation and domain model creation.

        Args:
            selected_file: The name of the selected parameter file
            fc_parameters: Dictionary of flight controller parameters
            variables: Variables dictionary for evaluation

        Returns:
            Tuple containing:
            - Dictionary of ArduPilotParameter domain model objects
            - Boolean indicating if at least one parameter was edited
            - List of (title, message) tuples for UI error feedback
            - List of (title, message) tuples for UI info feedback

        """
        at_least_one_param_edited = False
        ui_errors: list[tuple[str, str]] = []
        ui_infos: list[tuple[str, str]] = []

        # Process configuration step operations if configuration steps exist
        if self.local_filesystem.configuration_steps and selected_file in self.local_filesystem.configuration_steps:
            variables["fc_parameters"] = fc_parameters

            # Compute derived parameters
            error_msg = self.local_filesystem.compute_parameters(
                selected_file, self.local_filesystem.configuration_steps[selected_file], "derived", variables
            )
            if error_msg:
                ui_errors.append((_("Error in derived parameters"), error_msg))
            # Merge derived parameter values
            elif self.local_filesystem.merge_forced_or_derived_parameters(
                selected_file, self.local_filesystem.derived_parameters, list(fc_parameters.keys())
            ):
                at_least_one_param_edited = True

            # Handle connection renaming
            connection_edited, ui_infos = self._handle_connection_renaming(selected_file, variables)
            if connection_edited:
                at_least_one_param_edited = True

        # Create domain model parameters
        parameters = self._create_domain_model_parameters(selected_file, fc_parameters)

        return parameters, at_least_one_param_edited, ui_errors, ui_infos

    def _handle_connection_renaming(self, selected_file: str, variables: dict) -> tuple[bool, list[tuple[str, str]]]:
        """
        Handle connection renaming operations for the selected file.

        Args:
            selected_file: The name of the selected parameter file
            variables: Variables dictionary for evaluation

        Returns:
            Tuple containing:
            - True if parameters were modified, False otherwise
            - List of (title, message) tuples for UI info feedback

        """
        if "rename_connection" not in self.local_filesystem.configuration_steps[selected_file]:
            return False, []

        new_connection_prefix = self.local_filesystem.configuration_steps[selected_file]["rename_connection"]

        # Apply renames to the parameters dictionary
        duplicated_parameters, renamed_pairs = self._apply_connection_renames(
            self.local_filesystem.file_parameters[selected_file], new_connection_prefix, variables
        )

        at_least_one_param_edited = False
        ui_infos: list[tuple[str, str]] = []

        # Handle duplicated parameters
        for old_name in duplicated_parameters:
            logging_info(_("Removing duplicate parameter %s"), old_name)
            info_msg = _("The parameter '{old_name}' was removed due to duplication.")
            ui_infos.append((_("Parameter Removed"), info_msg.format(**locals())))
            at_least_one_param_edited = True

        # Handle renamed parameters
        for old_name, new_name in renamed_pairs:
            logging_info(_("Renaming parameter %s to %s"), old_name, new_name)
            info_msg = _(
                "The parameter '{old_name}' was renamed to '{new_name}'.\n"
                "to obey the flight controller connection defined in the component editor window."
            )
            ui_infos.append((_("Parameter Renamed"), info_msg.format(**locals())))
            at_least_one_param_edited = True

        return at_least_one_param_edited, ui_infos

    def _create_domain_model_parameters(
        self, selected_file: str, fc_parameters: dict[str, float]
    ) -> dict[str, ArduPilotParameter]:
        """
        Create ArduPilotParameter domain model objects for each parameter in the file.

        Args:
            selected_file: The name of the selected parameter file
            fc_parameters: Dictionary of flight controller parameters

        Returns:
            Dictionary mapping parameter names to ArduPilotParameter objects

        """
        parameters: dict[str, ArduPilotParameter] = {}

        for param_name, param in self.local_filesystem.file_parameters[selected_file].items():
            # Get parameter metadata and default values
            metadata = self.local_filesystem.doc_dict.get(param_name, {})
            default_par = self.local_filesystem.param_default_dict.get(param_name, None)

            # Check if parameter is forced or derived
            forced_par = self.local_filesystem.forced_parameters.get(selected_file, {}).get(param_name, None)
            derived_par = self.local_filesystem.derived_parameters.get(selected_file, {}).get(param_name, None)

            # Get FC value if available
            fc_value = fc_parameters.get(param_name)

            # Create domain model parameter
            parameters[param_name] = ArduPilotParameter(
                param_name, param, metadata, default_par, fc_value, forced_par, derived_par
            )

        return parameters

    def filter_different_parameters(self, parameters: dict[str, ArduPilotParameter]) -> dict[str, ArduPilotParameter]:
        """
        Filter parameters to only include those that are different from FC values or missing from FC.

        Args:
            parameters: Dictionary of all parameters

        Returns:
            Dictionary of parameters that are different from FC

        """
        return {name: param for name, param in parameters.items() if param.is_different_from_fc or not param.has_fc_value}

    @staticmethod
    def _generate_connection_renames(parameters: list[str], new_connection_prefix: str) -> dict[str, str]:
        """
        Generate a dictionary of parameter renames based on a new connection prefix.

        Args:
            parameters: List of parameter names to potentially rename
            new_connection_prefix: The new prefix to apply (like "CAN2")

        Returns:
            Dictionary mapping old parameter names to new parameter names

        """
        renames: dict[str, str] = {}

        # Extract the type and number from the new connection prefix
        if len(new_connection_prefix) < 2:
            return renames

        new_type = new_connection_prefix[:-1]  # e.g., "CAN" from "CAN2"
        new_number = new_connection_prefix[-1]  # e.g., "2" from "CAN2"

        for param_name in parameters:
            new_prefix = new_connection_prefix
            old_prefix = param_name.split("_")[0]
            if new_type == "CAN" and "CAN_P" in param_name:
                old_prefix = param_name.split("_")[0] + "_" + param_name.split("_")[1]
                new_prefix = "CAN_P" + new_number
            if new_type == "CAN" and "CAN_D" in param_name:
                old_prefix = param_name.split("_")[0] + "_" + param_name.split("_")[1]
                new_prefix = "CAN_D" + new_number

            if new_type in old_prefix:
                renames[param_name] = param_name.replace(old_prefix, new_prefix)

        return renames

    @staticmethod
    def _apply_connection_renames(
        parameters: dict[str, Any], new_connection_prefix: str, variables: Optional[dict[str, Any]] = None
    ) -> tuple[set[str], list[tuple[str, str]]]:
        """
        Apply connection prefix renames to a parameter dictionary.

        Args:
            parameters: Dictionary of parameter objects to rename, it will modify it
            new_connection_prefix: The new prefix to apply
            variables: Optional dictionary of variables for evaluation

        Returns:
            Tuple containing:
            - Set of duplicated parameter names that got removed
            - List of (old_name, new_name) pairs that were renamed

        """
        if variables:
            # If variables provided, evaluate the new_connection_prefix
            new_connection_prefix = eval(str(new_connection_prefix), {}, variables)  # noqa: S307 pylint: disable=eval-used

        # Generate the rename mapping
        renames = ConfigurationStepProcessor._generate_connection_renames(list(parameters.keys()), new_connection_prefix)

        # Track unique new names and actual renames performed
        new_names = set()
        duplicates = set()
        renamed_pairs = []
        for old_name, new_name in renames.items():
            if new_name in new_names:
                parameters.pop(old_name)
                duplicates.add(old_name)
            else:
                new_names.add(new_name)
                if new_name != old_name:
                    parameters[new_name] = parameters.pop(old_name)
                    renamed_pairs.append((old_name, new_name))

        return duplicates, renamed_pairs
