"""
Configuration step data model for parameter processing and domain model creation.

This file contains business logic for processing configuration steps, including parameter
computation, domain model creation, and connection renaming operations.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import info as logging_info
from typing import Any, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict


class ConfigurationStepProcessor:
    """
    Handles configuration step processing operations.

    This class encapsulates the business logic for processing configuration steps,
    including parameter computation, domain model creation, and connection renaming.
    """

    # Bits indicating ExpressLRS in RC_OPTIONS parameter
    # 9: Suppress CRSF mode/rate message for ELRS systems
    # 13: Use 420kbaud for ELRS protocol
    ELRS_RC_OPTIONS_BITS = (9, 13)

    def __init__(self, local_filesystem: LocalFilesystem) -> None:
        """
        Initialize the configuration step processor.

        Args:
            local_filesystem: The local filesystem instance to work with

        """
        self.local_filesystem = local_filesystem

        # A dictionary that maps variable names to their values
        # These variables are used by the forced_parameters and derived_parameters in configuration_steps_*.json files
        self.variables = self.local_filesystem.get_eval_variables()
        # Ensure transient helper variables are not persisted across steps
        self.variables.pop("fc_parameters", None)
        self.variables.pop("new_connection_prefix", None)

    def process_configuration_step(  # pylint: disable=too-many-locals
        self,
        selected_file: str,
        fc_parameters: dict[str, float],
    ) -> tuple[
        dict[str, ArduPilotParameter],
        list[tuple[str, str]],
        list[tuple[str, str]],
        set[str],
        list[tuple[str, str]],
        ParDict,
    ]:
        """
        Process a configuration step including parameter computation and domain model creation.

        Args:
            selected_file: The name of the selected parameter file
            fc_parameters: Dictionary of flight controller parameters

        Returns:
            Tuple containing:
            - Dictionary of ArduPilotParameter domain model objects
            - List of (title, message) tuples for UI error feedback
            - List of (title, message) tuples for UI info feedback
            - Set of parameter names to remove (duplicates from rename operations)
            - List of (old_name, new_name) pairs to rename
            - ParDict of derived parameters to apply to domain model

        """
        ui_errors: list[tuple[str, str]] = []
        ui_infos: list[tuple[str, str]] = []
        duplicates_to_remove: set[str] = set()
        renames_to_apply: list[tuple[str, str]] = []
        derived_params_to_apply: ParDict = ParDict()

        # Process configuration step operations if configuration steps exist
        if self.local_filesystem.configuration_steps and selected_file in self.local_filesystem.configuration_steps:
            variables = self.variables.copy()
            variables["fc_parameters"] = fc_parameters

            # Compute derived parameters (does NOT mutate filesystem.file_parameters)
            error_msg = self.local_filesystem.compute_parameters(
                selected_file, self.local_filesystem.configuration_steps[selected_file], "derived", variables
            )
            if error_msg:
                ui_errors.append((_("Error in derived parameters"), error_msg))
            # Collect derived parameter values to apply later in domain model
            elif selected_file in self.local_filesystem.derived_parameters:
                # Filter derived parameters that exist in FC (if fc_parameters provided)
                fc_param_names = set(fc_parameters.keys()) if fc_parameters else set()
                for param_name, param in self.local_filesystem.derived_parameters[selected_file].items():
                    # Only include if no FC filter OR parameter exists in FC
                    if not fc_param_names or param_name in fc_param_names:
                        derived_params_to_apply[param_name] = param

            # Populate new_connection_prefix from rename_connection configuration step (per-step scope)
            if "rename_connection" in self.local_filesystem.configuration_steps.get(selected_file, {}):
                variables["new_connection_prefix"] = self.local_filesystem.configuration_steps[selected_file][
                    "rename_connection"
                ]
            else:
                variables.pop("new_connection_prefix", None)

            # Calculate connection rename operations (does NOT mutate filesystem.file_parameters)
            rename_ui_infos, duplicates_to_remove, renames_to_apply = self._handle_connection_renaming(
                selected_file, variables
            )
            ui_infos.extend(rename_ui_infos)

        # Create domain model parameters
        current_step_parameters = self._create_domain_model_parameters(selected_file, fc_parameters)

        # Check for ExpressLRS and add FLTMODE_CH warning
        if current_step_parameters.get("RC_OPTIONS") is not None or current_step_parameters.get("FLTMODE_CH") is not None:
            rc_options = int(fc_parameters.get("RC_OPTIONS", 32))
            if (rc_options & (1 << self.ELRS_RC_OPTIONS_BITS[0])) or (rc_options & (1 << self.ELRS_RC_OPTIONS_BITS[1])):
                fltmode_ch = fc_parameters.get("FLTMODE_CH", 5)
                if fltmode_ch == 5:
                    ui_infos.append(
                        (
                            _("ExpressLRS Configuration Warning"),
                            _(
                                "FLTMODE_CH must be set to a channel other than 5 (currently set to 5).\n"
                                "Please change FLTMODE_CH to a different channel (e.g., 6, 7, 8, etc.)\n"
                                "to avoid conflicts with the required RC5 arming channel."
                            ),
                        )
                    )

        return current_step_parameters, ui_errors, ui_infos, duplicates_to_remove, renames_to_apply, derived_params_to_apply

    def _handle_connection_renaming(
        self, selected_file: str, variables: dict
    ) -> tuple[list[tuple[str, str]], set[str], list[tuple[str, str]]]:
        """
        Calculate connection renaming operations for the selected file.

        This method calculates what renames should happen but does NOT modify
        filesystem.file_parameters. The operations are returned for the caller
        to apply to the domain model.

        Args:
            selected_file: The name of the selected parameter file
            variables: Dictionary of variables for parameter evaluation

        Returns:
            Tuple containing:
            - List of (title, message) tuples for UI info feedback
            - Set of parameter names to remove (duplicates)
            - List of (old_name, new_name) pairs to rename

        """
        new_connection_prefix = variables.get("new_connection_prefix")
        if not new_connection_prefix:
            return [], set(), []

        # Calculate rename operations WITHOUT mutating file_parameters
        duplicated_parameters, renamed_pairs = self._calculate_connection_rename_operations(
            self.local_filesystem.file_parameters[selected_file], new_connection_prefix, variables
        )

        ui_infos: list[tuple[str, str]] = []

        # Handle duplicated parameters
        for old_name in duplicated_parameters:
            logging_info(_("Removing duplicate parameter %s"), old_name)
            info_msg = _("The parameter '{old_name}' was removed due to duplication.")
            ui_infos.append((_("Parameter Removed"), info_msg.format(**locals())))

        # Handle renamed parameters
        for old_name, new_name in renamed_pairs:
            logging_info(_("Renaming parameter %s to %s"), old_name, new_name)
            info_msg = _(
                "The parameter '{old_name}' was renamed to '{new_name}'.\n"
                "to obey the flight controller connection defined in the component editor window."
            )
            ui_infos.append((_("Parameter Renamed"), info_msg.format(**locals())))

        return ui_infos, duplicated_parameters, renamed_pairs

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
            forced_par = self.local_filesystem.forced_parameters.get(selected_file, ParDict()).get(param_name, None)
            derived_par = self.local_filesystem.derived_parameters.get(selected_file, ParDict()).get(param_name, None)

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
    def _calculate_connection_rename_operations(
        parameters: ParDict, new_connection_prefix: str, variables: Optional[dict[str, Any]] = None
    ) -> tuple[set[str], list[tuple[str, str]]]:
        """
        Calculate connection prefix rename operations without mutating the parameters dictionary.

        This method determines which parameters should be renamed and which are duplicates,
        but does NOT modify the input dictionary. The caller is responsible for applying
        the operations to their domain model.

        Args:
            parameters: Dictionary of parameter objects to analyze (NOT modified)
            new_connection_prefix: The new prefix to apply
            variables: Optional dictionary of variables for evaluation

        Returns:
            Tuple containing:
            - Set of parameter names that should be removed (duplicates)
            - List of (old_name, new_name) pairs that should be renamed

        """
        if variables:
            # If variables provided, evaluate the new_connection_prefix
            new_connection_prefix = eval(str(new_connection_prefix), {}, variables)  # noqa: S307 pylint: disable=eval-used

        # Generate the rename mapping
        renames = ConfigurationStepProcessor._generate_connection_renames(list(parameters.keys()), new_connection_prefix)

        # Track unique new names and actual renames to perform
        # Initialize with all existing parameter names to prevent conflicts
        new_names = set(parameters.keys())
        duplicates: set[str] = set()
        renamed_pairs = []
        for old_name, new_name in renames.items():
            if new_name in new_names:
                # Do not perform rename due to conflict, let the user handle it
                pass
            else:
                new_names.add(new_name)
                if new_name != old_name:
                    renamed_pairs.append((old_name, new_name))

        return duplicates, renamed_pairs

    def create_ardupilot_parameter(
        self,
        param_name: str,
        param: Par,
        selected_file: str,
        fc_parameters: dict[str, float],
    ) -> ArduPilotParameter:
        """
        Create an ArduPilotParameter domain model object.

        Args:
            param_name: The name of the parameter
            param: The parameter object from the file
            selected_file: The name of the selected parameter file
            fc_parameters: Dictionary of flight controller parameters

        Returns:
            ArduPilotParameter: The created domain model parameter

        """
        # Get parameter metadata and default values
        metadata = self.local_filesystem.doc_dict.get(param_name, {})
        default_par = self.local_filesystem.param_default_dict.get(param_name, None)

        # Check if parameter is forced or derived
        forced_par = self.local_filesystem.forced_parameters.get(selected_file, ParDict()).get(param_name, None)
        derived_par = self.local_filesystem.derived_parameters.get(selected_file, ParDict()).get(param_name, None)

        # Get FC value if available
        fc_value = fc_parameters.get(param_name)

        # Create domain model parameter
        return ArduPilotParameter(param_name, param, metadata, default_par, fc_value, forced_par, derived_par)
