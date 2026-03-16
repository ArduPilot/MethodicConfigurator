"""
Manages configuration steps at the filesystem level.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json import JSONDecodeError
from json import load as json_load
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from os import path as os_path
from re import search as re_search
from typing import Any, Optional, TypedDict

# from sys import exit as sys_exit
# from logging import debug as logging_debug
from jsonschema import validate as json_validate
from jsonschema.exceptions import ValidationError
from simpleeval import InvalidExpression

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_safe_evaluator import safe_evaluate


class PhaseData(TypedDict, total=False):
    """
    Type definition for configuration phase data.

    Attributes:
        start: The starting file number for this phase
        end: The ending file number for this phase (computed)
        weight: The weight for UI layout proportions (computed)
        description: Human-readable description of the phase
        optional: Whether this phase is optional

    """

    start: int
    end: int
    weight: int
    description: str
    optional: bool


class ConfigurationSteps:
    """
    A class to manage configuration steps for the ArduPilot methodic configurator.

    This class provides methods for reading and validating configuration steps, including forced and derived parameters.
    It is designed to simplify the interaction with configuration steps for managing ArduPilot configuration files.

    Attributes:
        configuration_steps_filename (str): The name of the file containing documentation for the configuration files.
        configuration_steps (dict): A dictionary containing the configuration steps.

    """

    def __init__(self, _vehicle_dir: str, vehicle_type: str) -> None:
        self.configuration_steps_filename = "configuration_steps_" + vehicle_type + ".json"
        self.configuration_steps: dict[str, dict] = {}
        self.configuration_phases: dict[str, PhaseData] = {}
        self.forced_parameters: dict[str, ParDict] = {}
        self.derived_parameters: dict[str, ParDict] = {}
        self.log_loaded_file = False

    def re_init(self, vehicle_dir: str, vehicle_type: str) -> None:  # pylint: disable=too-many-branches
        if vehicle_type == "":
            return
        self.configuration_steps_filename = "configuration_steps_" + vehicle_type + ".json"
        # Define a list of directories to search for the configuration_steps_filename file
        search_directories = [vehicle_dir, os_path.dirname(os_path.abspath(__file__))]
        file_found = False
        json_content = {}
        for i, directory in enumerate(search_directories):
            try:
                with open(os_path.join(directory, self.configuration_steps_filename), encoding="utf-8-sig") as file:
                    json_content = json_load(file)
                    file_found = True
                    if self.log_loaded_file:
                        if i == 0:
                            logging_warning(
                                _("Configuration steps '%s' loaded from %s (overwriting default configuration steps)."),
                                self.configuration_steps_filename,
                                directory,
                            )
                        if i == 1:
                            logging_info(
                                _("Configuration steps '%s' loaded from %s."), self.configuration_steps_filename, directory
                            )
                    break
            except FileNotFoundError:
                pass
            except JSONDecodeError as e:
                logging_error(_("Error in file '%s': %s"), self.configuration_steps_filename, e)
                break
        # Validate the vehicle configuration steps file against the configuration_steps_schema.json schema
        if file_found:
            schema_file = os_path.join(os_path.dirname(os_path.abspath(__file__)), "configuration_steps_schema.json")
            try:
                with open(schema_file, encoding="utf-8") as schema:
                    schema_data = json_load(schema)
                    json_validate(instance=json_content, schema=schema_data)
            except FileNotFoundError:
                logging_error(_("Schema file '%s' not found"), schema_file)
            except ValidationError as e:
                logging_error(_("Configuration steps validation error: %s"), str(e))
            except JSONDecodeError as e:
                logging_error(_("Error in schema file '%s': %s"), schema_file, e)

        if file_found and "steps" in json_content:
            self.configuration_steps = json_content["steps"]
            for filename, file_info in self.configuration_steps.items():
                self.__validate_parameters_in_configuration_steps(filename, file_info, "forced")
                self.__validate_parameters_in_configuration_steps(filename, file_info, "derived")
        else:
            logging_warning(_("No configuration steps documentation and no forced and derived parameters will be available."))

        if file_found and "phases" in json_content:
            self.configuration_phases = json_content["phases"]
        else:
            logging_warning(_("No configuration phases documentation will be available."))
        self.log_loaded_file = True

    def __validate_parameters_in_configuration_steps(self, filename: str, file_info: dict, parameter_type: str) -> None:
        """
        Validates the parameters in the configuration steps.

        This method checks if the parameters in the configuration steps are correctly formatted.
        If a parameter is missing the 'New Value' or 'Change Reason' attribute, an error message is logged.
        """
        if parameter_type + "_parameters" in file_info:
            if not isinstance(file_info[parameter_type + "_parameters"], dict):
                logging_error(
                    _("Error in file '%s': '%s' %s parameter is not a dictionary"),
                    self.configuration_steps_filename,
                    filename,
                    parameter_type,
                )
                return
            for parameter, parameter_info in file_info[parameter_type + "_parameters"].items():
                if "New Value" not in parameter_info:
                    logging_error(
                        _("Error in file '%s': '%s' %s parameter '%s' 'New Value' attribute not found."),
                        self.configuration_steps_filename,
                        filename,
                        parameter_type,
                        parameter,
                    )
                if "Change Reason" not in parameter_info:
                    logging_error(
                        _("Error in file '%s': '%s' %s parameter '%s' 'Change Reason' attribute not found."),
                        self.configuration_steps_filename,
                        filename,
                        parameter_type,
                        parameter,
                    )

    @staticmethod
    def _condition_passes(parameter_info: dict, variables: dict) -> bool:
        """Return True when there is no 'if' guard or the guard evaluates to truthy."""
        if "if" not in parameter_info:
            return True
        try:
            return bool(safe_evaluate(str(parameter_info["if"]), variables))
        except SyntaxError as e:
            logging_warning("Condition '%s' has a syntax error: %s", parameter_info["if"], e)
            return False
        except (NameError, KeyError, InvalidExpression):
            return False  # Expected when variables like fc_parameters are not yet available

    @staticmethod
    def _handle_param_error(error_msg: str, parameter_type: str, ignore_fc_derived_param_warnings: bool = False) -> str:
        """Log an error/warning and return the appropriate value for the caller."""
        if parameter_type == "forced":
            logging_error(error_msg)
            return error_msg
        if not ignore_fc_derived_param_warnings:
            logging_warning(error_msg)
        return ""

    @staticmethod
    def _ensure_file_entry(destination: dict[str, ParDict], filename: str) -> None:
        """Ensure the filename key exists in the destination dictionary."""
        if filename not in destination:
            destination[filename] = ParDict()

    def _eval_new_value(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        new_value_expr: object,
        filename: str,
        parameter: str,
        parameter_type: str,
        variables: dict,
    ) -> tuple[Any, str]:
        """Evaluate a 'New Value' expression. Returns (result, "") on success or (None, error_msg) on failure."""
        new_value_str = str(new_value_expr)
        if re_search(r"\bfc_parameters\b", new_value_str) and (
            "fc_parameters" not in variables or variables["fc_parameters"] == {}
        ):
            error_msg = _(
                "In file '{configuration_steps_filename}': '{filename}' {parameter_type} "
                "parameter '{parameter}' could not be computed: 'fc_parameters' not found, is an FC connected?"
            )
            return None, error_msg.format(
                configuration_steps_filename=self.configuration_steps_filename,
                filename=filename,
                parameter_type=parameter_type,
                parameter=parameter,
            )
        try:
            return safe_evaluate(new_value_str, variables), ""
        except (ZeroDivisionError, ValueError) as math_error:
            # ZeroDivisionError: division by zero or 0.0 raised to negative power
            # ValueError: math domain error (e.g., Diameter_inches**-0.838 when Diameter_inches is 0)
            error_msg = _(
                "In file '{configuration_steps_filename}': '{filename}' {parameter_type} "
                "parameter '{parameter}' evaluation resulted in math error: {math_error}"
            )
            return None, error_msg.format(
                configuration_steps_filename=self.configuration_steps_filename,
                filename=filename,
                parameter_type=parameter_type,
                parameter=parameter,
                math_error=math_error,
            )

    def _resolve_string_result(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        result: str,
        parameter: str,
        doc_dict: dict,
        filename: str,
        parameter_type: str,
    ) -> tuple[Any, str]:
        """
        Convert a string evaluation result to a numeric value via documentation metadata.

        Returns (resolved_value, "") on success or (None, error_msg) on any failure.
        """
        if parameter not in doc_dict:
            error_msg = _(
                "In file '{configuration_steps_filename}': '{filename}' {parameter_type} "
                "parameter '{parameter}' could not be computed, no documentation metadata available for it"
            )
            return None, error_msg.format(
                configuration_steps_filename=self.configuration_steps_filename,
                filename=filename,
                parameter_type=parameter_type,
                parameter=parameter,
            )
        values = doc_dict[parameter]["values"]
        if values:
            try:
                return next(key for key, value in values.items() if value == result), ""
            except StopIteration:
                error_msg = _(
                    "In file '{configuration_steps_filename}': '{filename}' {parameter_type} "
                    "parameter '{parameter}' string value '{result}' not found in documentation metadata values"
                )
                return None, error_msg.format(
                    configuration_steps_filename=self.configuration_steps_filename,
                    filename=filename,
                    parameter_type=parameter_type,
                    parameter=parameter,
                    result=result,
                )
        bitmasks = doc_dict[parameter]["Bitmask"]
        if bitmasks:
            try:
                return 2 ** next(key for key, bitmask in bitmasks.items() if bitmask == result), ""
            except StopIteration:
                error_msg = _(
                    "In file '{configuration_steps_filename}': '{filename}' {parameter_type} "
                    "parameter '{parameter}' string value '{result}' not found in documentation metadata bitmasks"
                )
                return None, error_msg.format(
                    configuration_steps_filename=self.configuration_steps_filename,
                    filename=filename,
                    parameter_type=parameter_type,
                    parameter=parameter,
                    result=result,
                )
        return result, ""

    def _compute_single_parameter(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        filename: str,
        parameter: str,
        parameter_info: dict,
        parameter_type: str,
        destination: dict[str, ParDict],
        variables: dict,
        ignore_fc_derived_param_warnings: bool,
    ) -> str:
        """Process a single parameter entry. Returns "" on success, or an error message on fatal error."""
        # Add-from-FC shorthand: derived entry with 'if' but no 'New Value'.
        # This shorthand is only valid for derived parameters; forced parameters require 'New Value'.
        if "New Value" not in parameter_info:
            if parameter_type == "forced":
                logging_warning(
                    "In file '%s': '%s' forced parameter '%s' has no 'New Value' - "
                    "add-from-FC shorthand is only valid for derived parameters",
                    self.configuration_steps_filename,
                    filename,
                    parameter,
                )
                return ""
            fc_params = variables.get("fc_parameters", {})
            if parameter in fc_params:
                self._ensure_file_entry(destination, filename)
                destination[filename][parameter] = Par(float(fc_params[parameter]), "")
            return ""
        try:
            result, error_msg = self._eval_new_value(
                parameter_info["New Value"], filename, parameter, parameter_type, variables
            )
            if error_msg:
                return self._handle_param_error(error_msg, parameter_type, ignore_fc_derived_param_warnings)
            if isinstance(result, str):
                result, error_msg = self._resolve_string_result(
                    result, parameter, variables["doc_dict"], filename, parameter_type
                )
                if error_msg:
                    return self._handle_param_error(error_msg, parameter_type, ignore_fc_derived_param_warnings)
            self._ensure_file_entry(destination, filename)
            change_reason = _(parameter_info["Change Reason"]) if parameter_info["Change Reason"] else ""
            destination[filename][parameter] = Par(float(result), change_reason)
        except (SyntaxError, NameError, KeyError, InvalidExpression) as _e:
            error_msg = _(
                "In file '{self.configuration_steps_filename}': '{filename}' {parameter_type} "
                "parameter '{parameter}' could not be computed: {_e}"
            )
            return self._handle_param_error(error_msg.format(**locals()), parameter_type)
        return ""

    def compute_parameters(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        filename: str,
        file_info: dict,
        parameter_type: str,
        variables: dict,
        ignore_fc_derived_param_warnings: bool = False,
    ) -> str:
        """
        Computes the forced or derived parameters for a given configuration file.

        If the parameter is forced, it is added to the forced_parameters dictionary.
        If the parameter is derived, it is added to the derived_parameters dictionary.
        """
        if parameter_type + "_parameters" not in file_info or not variables:
            return ""
        destination = self.forced_parameters if parameter_type == "forced" else self.derived_parameters
        for parameter, parameter_info in file_info[parameter_type + "_parameters"].items():
            if not self._condition_passes(parameter_info, variables):
                continue
            error_msg = self._compute_single_parameter(
                filename, parameter, parameter_info, parameter_type, destination, variables, ignore_fc_derived_param_warnings
            )
            if error_msg:
                return error_msg
        return ""

    def compute_deletions(self, filename: str, file_info: dict, variables: dict) -> set[str]:
        """
        Compute parameter names to be deleted from the configuration file.

        Evaluates the optional 'if' condition for each entry in the 'delete_parameters' section.
        A parameter is deleted when its condition evaluates to True (or when no condition is present).

        Args:
            filename: The name of the configuration file (used for error logging).
            file_info: The configuration step dictionary for this file.
            variables: Variables available for evaluating 'if' expressions.

        Returns:
            Set of parameter names that should be removed from the file.

        """
        if "delete_parameters" not in file_info or not variables:
            if "delete_parameters" in file_info and not variables:
                logging_warning("Skipping delete_parameters for '%s': no evaluation variables available", filename)
            return set()
        to_delete: set[str] = set()
        for parameter, parameter_info in file_info["delete_parameters"].items():
            if "if" in parameter_info:
                try:
                    if safe_evaluate(str(parameter_info["if"]), variables):
                        to_delete.add(parameter)
                except SyntaxError as e:
                    logging_warning(
                        "In '%s': delete_parameters condition for '%s' has a syntax error: %s",
                        filename,
                        parameter,
                        e,
                    )
                except (NameError, KeyError, InvalidExpression):
                    pass  # Expected when variables like fc_parameters are not yet available
            else:
                to_delete.add(parameter)
        return to_delete

    def auto_changed_by(self, selected_file: str) -> str:
        if selected_file in self.configuration_steps:
            return str(self.configuration_steps[selected_file].get("auto_changed_by", ""))
        return ""

    def jump_possible(self, selected_file: str) -> dict[str, str]:
        if selected_file in self.configuration_steps:
            return dict(self.configuration_steps[selected_file].get("jump_possible", {}))
        return {}

    def get_documentation_text_and_url(self, selected_file: str, prefix_key: str) -> tuple[str, str]:
        documentation = self.configuration_steps.get(selected_file, {}) if self.configuration_steps else None
        if documentation is None:
            text = _(
                "File '{self.configuration_steps_filename}' not found. No intermediate parameter configuration steps available"
            )
            text = text.format(**locals())
            url = ""
        else:
            text = _("No documentation available for {selected_file} in the {self.configuration_steps_filename} file")
            text = documentation.get(prefix_key + "_text", text.format(**locals()))
            url = documentation.get(prefix_key + "_url", "")
        return text, url

    def get_seq_tooltip_text(self, selected_file: str, tooltip_key: str) -> str:
        documentation = self.configuration_steps.get(selected_file, {}) if self.configuration_steps else None
        if documentation is None:
            text = _(
                "File '{self.configuration_steps_filename}' not found. No intermediate parameter configuration steps available"
            )
            text = text.format(**locals())
        else:
            text = _("No documentation available for {selected_file} in the {self.configuration_steps_filename} file")
            text = documentation.get(tooltip_key, text.format(**locals()))
        return text

    def get_sorted_phases_with_end_and_weight(self, total_files: int) -> dict[str, PhaseData]:
        """
        Get sorted phases with added 'end' and 'weight' information.

        Returns phases sorted by start position, with each phase containing:
        - 'end': The end file number (start of next phase or total_files)
        - 'weight': Weight for UI layout (max(2, end - start))
        """
        active_phases = {k: v for k, v in self.configuration_phases.items() if "start" in v}

        # Sort phases by start position
        sorted_phases: dict[str, PhaseData] = dict(sorted(active_phases.items(), key=lambda x: x[1].get("start", 0)))

        # Add the end information to each phase using the start of the next phase
        phase_names = list(sorted_phases.keys())
        for i, phase_name in enumerate(phase_names):
            if i < len(phase_names) - 1:
                next_phase_name = phase_names[i + 1]
                sorted_phases[phase_name]["end"] = sorted_phases[next_phase_name].get("start", total_files)
            else:
                sorted_phases[phase_name]["end"] = total_files
            phase_start = sorted_phases[phase_name].get("start", 0)
            phase_end = sorted_phases[phase_name].get("end", total_files)
            sorted_phases[phase_name]["weight"] = max(2, phase_end - phase_start)

        return sorted_phases

    def get_plugin(self, selected_file: str) -> Optional[dict]:
        """
        Get the plugin configuration for the selected file.

        Args:
            selected_file: The filename to get plugin info for

        Returns:
            The plugin dict with 'name' and 'placement' if exists, None otherwise

        """
        if selected_file in self.configuration_steps:
            return self.configuration_steps[selected_file].get("plugin")
        return None
