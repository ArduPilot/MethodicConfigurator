"""
Filesystem operations.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from sys import exit as sys_exit
from argparse import ArgumentParser
from logging import debug as logging_debug
from logging import error as logging_error
from logging import exception as logging_exception
from logging import info as logging_info
from logging import warning as logging_warning
from os import getcwd as os_getcwd
from os import listdir as os_listdir
from os import path as os_path
from os import remove as os_remove
from os import rename as os_rename
from os import rmdir as os_rmdir
from platform import system as platform_system
from re import compile as re_compile
from shutil import Error as shutil_Error
from shutil import copy2 as shutil_copy2
from shutil import copytree as shutil_copytree
from shutil import rmtree as shutil_rmtree
from subprocess import SubprocessError, run
from typing import Any, Optional, Union
from zipfile import ZipFile

from argcomplete.completers import DirectoriesCompleter

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import (
    PARAM_DEFINITION_XML_FILE,
    Par,
    format_columns,
    get_xml_dir,
    get_xml_url,
    load_default_param_file,
    parse_parameter_metadata,
    split_into_lines,
    update_parameter_documentation,
)
from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents

TOOLTIP_MAX_LENGTH = 105


def is_within_tolerance(x: float, y: float, atol: float = 1e-08, rtol: float = 1e-04) -> bool:
    """
    Determines if the absolute difference between two numbers is within a specified tolerance.

    This function checks if the absolute difference between `x` and `y` is less than or equal to
    the sum of the absolute tolerance (`atol`) and the product of the relative tolerance (`rtol`)
    and the absolute value of `y`.

    Args:
      x (float): The first number to compare.
      y (float): The second number to compare.
      atol (float, optional): The absolute tolerance. Default is 1e-08.
      rtol (float, optional): The relative tolerance. Default is 1e-04.

    Returns:
      bool: True if the difference is within the tolerance, False otherwise.

    """
    return abs(x - y) <= atol + (rtol * abs(y))


class LocalFilesystem(VehicleComponents, ConfigurationSteps, ProgramSettings):  # pylint: disable=too-many-public-methods
    """
    A class to manage local filesystem operations for the ArduPilot methodic configurator.

    This class provides methods for initializing and re-initializing the filesystem context,
    reading parameters from files, and handling configuration steps. It is designed to simplify
    the interaction with the local filesystem for managing ArduPilot configuration files.

    Args:
        vehicle_dir (str): The directory path where the vehicle configuration files are stored.
        vehicle_type (str): The type of the vehicle (e.g., "ArduCopter", "Rover").
        file_parameters (dict): A dictionary of parameters read from intermediate parameter files.
        param_default_dict (dict): A dictionary of default parameter values.
        doc_dict (dict): A dictionary containing documentation for each parameter.

    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        vehicle_dir: str,
        vehicle_type: str,
        fw_version: str,
        allow_editing_template_files: bool,
        save_component_to_system_templates: bool,
    ) -> None:
        self.file_parameters: dict[str, dict[str, Par]] = {}
        VehicleComponents.__init__(self, save_component_to_system_templates)
        ConfigurationSteps.__init__(self, vehicle_dir, vehicle_type)
        ProgramSettings.__init__(self)
        self.vehicle_type = vehicle_type
        self.fw_version = fw_version
        self.allow_editing_template_files = allow_editing_template_files
        self.param_default_dict: dict[str, Par] = {}
        self.vehicle_dir = vehicle_dir
        self.doc_dict: dict[str, Any] = {}
        if vehicle_dir is not None:
            self.re_init(vehicle_dir, vehicle_type)

    def re_init(self, vehicle_dir: str, vehicle_type: str, blank_component_data: bool = False) -> None:
        self.vehicle_dir = vehicle_dir
        self.doc_dict = {}

        if not self.load_vehicle_components_json_data(vehicle_dir):
            return

        if blank_component_data:
            self.wipe_component_info()
            if self.vehicle_components_fs.data and "Components" in self.vehicle_components_fs.data:
                self.save_vehicle_components_json_data(self.vehicle_components_fs.data, self.vehicle_dir)

        if not self.fw_version:
            self.fw_version = self.get_fc_fw_version_from_vehicle_components_json()

        if vehicle_type == "":
            vehicle_type = self.get_fc_fw_type_from_vehicle_components_json()
        if vehicle_type == "":
            vehicle_type = "ArduCopter"
            logging_warning(_("Could not detect vehicle type. Defaulting to %s."), vehicle_type)
        self.vehicle_type = vehicle_type

        ConfigurationSteps.re_init(self, vehicle_dir, vehicle_type)

        # Rename parameter files if some new files got added to the vehicle directory
        self.rename_parameter_files()

        # Read intermediate parameters from files
        self.file_parameters = self.read_params_from_files()
        if not self.file_parameters:
            return  # No files intermediate parameters files found, no need to continue, the rest needs them

        # Read ArduPilot parameter documentation
        xml_url = get_xml_url(vehicle_type, self.fw_version)
        xml_dir = get_xml_dir(vehicle_dir)
        self.doc_dict = parse_parameter_metadata(xml_url, xml_dir, PARAM_DEFINITION_XML_FILE, vehicle_type, TOOLTIP_MAX_LENGTH)
        self.param_default_dict = load_default_param_file(xml_dir)

        # Extend parameter documentation metadata if <parameter_file>.pdef.xml exists
        for filename in self.file_parameters:
            pdef_xml_file = filename.replace(".param", ".pdef.xml")
            if os_path.exists(os_path.join(xml_dir, pdef_xml_file)):
                doc_dict = parse_parameter_metadata("", xml_dir, pdef_xml_file, vehicle_type, TOOLTIP_MAX_LENGTH)
                self.doc_dict.update(doc_dict)

        self.__extend_and_reformat_parameter_documentation_metadata()

    def vehicle_configuration_files_exist(self, vehicle_dir: str) -> bool:
        if os_path.exists(vehicle_dir) and os_path.isdir(vehicle_dir):
            vehicle_configuration_files = os_listdir(vehicle_dir)
            if platform_system() == "Windows":
                vehicle_configuration_files = [f.lower() for f in vehicle_configuration_files]
            pattern = re_compile(r"^\d{2}_.*\.param$")
            if self.vehicle_components_fs.json_filename in vehicle_configuration_files and any(
                pattern.match(f) for f in vehicle_configuration_files
            ):
                return True
        return False

    def rename_parameter_files(self) -> None:
        if self.vehicle_dir is None or self.configuration_steps is None:
            return
        # Rename parameter files if some new files got added to the vehicle directory
        for new_filename in self.configuration_steps:
            if "old_filenames" in self.configuration_steps[new_filename]:
                for old_filename in self.configuration_steps[new_filename]["old_filenames"]:
                    if self.vehicle_configuration_file_exists(old_filename) and old_filename != new_filename:
                        if self.vehicle_configuration_file_exists(new_filename):
                            logging_error(
                                _("File %s already exists. Will not rename file %s to %s."),
                                new_filename,
                                old_filename,
                                new_filename,
                            )
                            continue
                        new_filename_path = os_path.join(self.vehicle_dir, new_filename)
                        old_filename_path = os_path.join(self.vehicle_dir, old_filename)
                        os_rename(old_filename_path, new_filename_path)
                        logging_info("Renamed %s to %s", old_filename, new_filename)

    def _format_columns_sorted_numerically(
        self, values: dict[str, Any], max_width: int = 105, max_columns: int = 4
    ) -> list[str]:
        """
        Formats a dictionary of values into column-major horizontally aligned columns with numeric sorting.

        This is similar to format_columns from annotate_params.py but sorts the values numerically by key.

        Args:
            values (Dict[str, Any]): The dictionary of values to format.
            max_width (int, optional): The maximum number of characters on all columns. Default is 105.
            max_columns (int): Maximum number of columns

        Returns:
            List[str]: The list of formatted strings.

        """
        if not values:
            return []

        # Sort values numerically by key
        try:
            # Try to sort by numeric key (int first, then float)
            try:
                sorted_items = sorted(values.items(), key=lambda x: int(x[0]))
            except ValueError:
                sorted_items = sorted(values.items(), key=lambda x: float(x[0]))
        except ValueError:
            # Fall back to string sorting if numeric sorting fails
            sorted_items = sorted(values.items())

        # Format each key-value pair
        formatted_items = [f"{key}: {value}" for key, value in sorted_items]

        if not formatted_items:
            return []

        # Calculate optimal column width and number of columns
        max_item_length = max(len(item) for item in formatted_items)
        optimal_columns = min(max_columns, max(1, max_width // (max_item_length + 2)))  # +2 for spacing

        # Ensure we don't exceed max_width with the chosen number of columns
        while optimal_columns > 1 and (max_item_length + 2) * optimal_columns > max_width:
            optimal_columns -= 1

        # Arrange items in column-major order
        num_items = len(formatted_items)
        rows_per_column = (num_items + optimal_columns - 1) // optimal_columns  # Ceiling division

        result = []
        for row in range(rows_per_column):
            row_items = []
            for col in range(optimal_columns):
                index = col * rows_per_column + row
                if index < num_items:
                    row_items.append(formatted_items[index].ljust(max_item_length))
            if row_items:
                result.append("  ".join(row_items).rstrip())

        return result

    def __extend_and_reformat_parameter_documentation_metadata(self) -> None:  # pylint: disable=too-many-branches
        for param_name, param_info in self.doc_dict.items():
            if "fields" in param_info:
                param_fields = param_info["fields"]
                if "Units" in param_fields:
                    units_list = param_fields["Units"].split("(")
                    param_info["unit"] = units_list[0].strip()
                    if len(units_list) > 1:
                        param_info["unit_tooltip"] = units_list[1].strip(")").strip()
                if "Range" in param_fields:
                    param_info["min"] = float(param_fields["Range"].split(" ")[0].strip())
                    param_info["max"] = float(param_fields["Range"].split(" ")[1].strip())
                if "Calibration" in param_fields:
                    param_info["Calibration"] = self.str_to_bool(param_fields["Calibration"].strip())
                if "ReadOnly" in param_fields:
                    param_info["ReadOnly"] = self.str_to_bool(param_fields["ReadOnly"].strip())
                if "RebootRequired" in param_fields:
                    param_info["RebootRequired"] = self.str_to_bool(param_fields["RebootRequired"].strip())
                if "Bitmask" in param_fields:
                    bitmask_items = param_fields["Bitmask"].split(",")
                    param_info["Bitmask"] = {}
                    for item in bitmask_items:
                        key, value = item.split(":")
                        param_info["Bitmask"][int(key.strip())] = value.strip()

            if param_info.get("values"):
                try:
                    param_info["Values"] = {int(k): v for k, v in param_info["values"].items()}
                except ValueError:
                    try:
                        param_info["Values"] = {float(k): v for k, v in param_info["values"].items()}
                    except ValueError:
                        logging_warning(_("Could not convert values to int or float for %s"), param_name)
                        logging_warning(
                            _("Parameter %s has invalid metadata. Please file a bug at %s"),
                            param_name,
                            "https://github.com/ArduPilot/ardupilot/issues",
                        )
                # print(param_info['Values'])

            prefix_parts = [
                f"{param_info['humanName']}",
            ]
            prefix_parts += param_info["documentation"]
            for key, value in param_info["fields"].items():
                if key not in {"Units", "UnitText"}:
                    prefix_parts += split_into_lines(f"{key}: {value}", TOOLTIP_MAX_LENGTH)
            prefix_parts += format_columns(param_info["values"], TOOLTIP_MAX_LENGTH)
            if param_name in self.param_default_dict:
                default_value = format(self.param_default_dict[param_name].value, ".6f").rstrip("0").rstrip(".")
                prefix_parts += [f"Default: {default_value}"]
            param_info["doc_tooltip"] = ("\n").join(prefix_parts)

            # Create a numerically sorted version for Current Value column tooltips
            prefix_parts_sorted = [
                f"{param_info['humanName']}",
            ]
            prefix_parts_sorted += param_info["documentation"]
            for key, value in param_info["fields"].items():
                if key not in {"Units", "UnitText"}:
                    prefix_parts_sorted += split_into_lines(f"{key}: {value}", TOOLTIP_MAX_LENGTH)
            prefix_parts_sorted += self._format_columns_sorted_numerically(param_info["values"], TOOLTIP_MAX_LENGTH)
            if param_name in self.param_default_dict:
                default_value = format(self.param_default_dict[param_name].value, ".6f").rstrip("0").rstrip(".")
                prefix_parts_sorted += [f"Default: {default_value}"]
            param_info["doc_tooltip_sorted_numerically"] = ("\n").join(prefix_parts_sorted)

    def read_params_from_files(self) -> dict[str, dict[str, "Par"]]:
        """
        Reads intermediate parameter files from a directory and stores their contents in a dictionary.

        This function scans the specified directory for files matching a specific pattern,
        reads each file, and stores the parameter names and values in a dictionary.
        Files named '00_default.param' and '01_ignore_readonly.param' are ignored.

        Returns:
        - Dict[str, Dict[str, 'Par']]: A dictionary with filenames as keys and as values
                                       a dictionary with (parameter names, values) pairs.

        """
        parameters: dict[str, dict[str, Par]] = {}
        if os_path.isdir(self.vehicle_dir):
            # Regular expression pattern for filenames starting with two digits followed by an underscore and ending in .param
            pattern = re_compile(r"^\d{2}_.*\.param$")

            for filename in sorted(os_listdir(self.vehicle_dir)):
                if pattern.match(filename):
                    if filename in {"00_default.param", "01_ignore_readonly.param"}:
                        continue
                    parameters[filename] = Par.load_param_file_into_dict(os_path.join(self.vehicle_dir, filename))
        else:
            logging_error(_("Error: %s is not a directory."), self.vehicle_dir)
        return parameters

    @staticmethod
    def str_to_bool(s: str) -> Optional[bool]:
        """
        Converts a string representation of a boolean value to a boolean.

        This function interprets the string 'true', 'yes', '1' as True, and 'false', 'no', '0' as False.
        Any other input will return None.

        Args:
          s (str): The string to convert.

        Returns:
          Optional[bool]: True, False, or None if the string does not match any known boolean representation.

        """
        if s.lower() == "true" or s.lower() == "yes" or s.lower() == "1":
            return True
        if s.lower() == "false" or s.lower() == "no" or s.lower() == "0":
            return False
        return None

    def export_to_param(self, params: dict[str, "Par"], filename_out: str, annotate_doc: bool = True) -> None:
        """
        Exports a dictionary of parameters to a .param file and optionally annotates the documentation.

        This function formats the provided parameters into a string suitable for a .param file,
        writes the string to the specified output file, and optionally updates the parameter documentation.

        Args:
          params (Dict[str, 'Par']): A dictionary of parameters to export.
          filename_out (str): The name of the output file.
          annotate_doc (bool, optional): Whether to update the parameter documentation. Default is True.

        """
        Par.export_to_param(Par.format_params(params), os_path.join(self.vehicle_dir, filename_out))
        if annotate_doc:
            update_parameter_documentation(
                self.doc_dict, os_path.join(self.vehicle_dir, filename_out), "missionplanner", self.param_default_dict
            )

    def vehicle_configuration_file_exists(self, filename: str) -> bool:
        """
        Check if a vehicle configuration file exists in the vehicle directory.

        Args:
          filename (str): The name of the file to check.

        Returns:
          bool: True if the file exists and is a file (not a directory) and is not empty, False otherwise.

        """
        file_path = os_path.join(self.vehicle_dir, filename)
        return os_path.exists(file_path) and os_path.isfile(file_path) and os_path.getsize(file_path) > 0

    def __all_intermediate_parameter_file_comments(self) -> dict[str, str]:
        """
        Retrieves all comments associated with parameters from intermediate parameter files.

        This method iterates through all intermediate parameter files, collects comments for each parameter,
        and returns them as a dictionary where the keys are parameter names and the values are the comments.
        Comments from the same parameter in different files are not merged; only the comment from the last file is returned.

        Returns:
        - Dict[str, str]: A dictionary mapping parameter names to their comments.

        """
        ret = {}
        for params in self.file_parameters.values():
            for param, info in params.items():
                if info.comment:
                    ret[param] = info.comment
        return ret

    def annotate_intermediate_comments_to_param_dict(self, param_dict: dict[str, float]) -> dict[str, "Par"]:
        """
        Annotates comments from intermediate parameter files to a parameter value-only dictionary.

        This function takes a dictionary of parameters with only values and adds comments from
        intermediate parameter files to create a new dictionary where each parameter is represented
        by a 'Par' object containing both the value and the comment.

        Args:
          param_dict (Dict[str, float]): A dictionary of parameters with only values.

        Returns:
          Dict[str, 'Par']: A dictionary of parameters with intermediate parameter file comments.

        """
        ret = {}
        ip_comments = self.__all_intermediate_parameter_file_comments()
        for param, value in param_dict.items():
            ret[param] = Par(float(value), ip_comments.get(param, ""))
        return ret

    def categorize_parameters(self, param: dict[str, "Par"]) -> tuple[dict[str, "Par"], dict[str, "Par"], dict[str, "Par"]]:
        """
        Categorize parameters into three categories based on their default values and documentation attributes.

        This method iterates through the provided dictionary of parameters and categorizes them into three groups:
        - Non-default, read-only parameters
        - Non-default, writable calibrations
        - Non-default, writable non-calibrations

        Args:
          param (Dict[str, 'Par']): A dictionary mapping parameter names to their 'Par' objects.

        Returns:
          Tuple[Dict[str, "Par"], Dict[str, "Par"], Dict[str, "Par"]]: A tuple of three dictionaries.
                                  Each dictionary represents one of the categories mentioned above.

        """
        non_default__read_only_params = {}
        non_default__writable_calibrations = {}
        non_default__writable_non_calibrations = {}
        for param_name, param_info in param.items():
            if param_name in self.param_default_dict and is_within_tolerance(
                param_info.value, self.param_default_dict[param_name].value
            ):
                continue  # parameter has a default value, ignore it

            if param_name in self.doc_dict and self.doc_dict[param_name].get("ReadOnly", False):
                non_default__read_only_params[param_name] = param_info
                continue

            if param_name in self.doc_dict and self.doc_dict[param_name].get("Calibration", False):
                non_default__writable_calibrations[param_name] = param_info
                continue
            non_default__writable_non_calibrations[param_name] = param_info

        return non_default__read_only_params, non_default__writable_calibrations, non_default__writable_non_calibrations

    @staticmethod
    def get_directory_name_from_full_path(full_path: str) -> str:
        # Normalize the path to ensure it's in a standard format
        normalized_path = os_path.normpath(full_path)

        # Split the path into head and tail, then get the basename of the tail
        return os_path.basename(os_path.split(normalized_path)[1])

    # Extract the vehicle name from the directory path
    def get_vehicle_directory_name(self) -> str:
        return self.get_directory_name_from_full_path(self.vehicle_dir)

    def zip_file_path(self) -> str:
        vehicle_name = self.get_vehicle_directory_name()
        return os_path.join(self.vehicle_dir, f"{vehicle_name}.zip")

    def zip_file_exists(self) -> bool:
        zip_file_path = self.zip_file_path()
        return os_path.exists(zip_file_path) and os_path.isfile(zip_file_path)

    def add_configuration_file_to_zip(self, zipf: ZipFile, filename: str) -> None:
        if self.vehicle_configuration_file_exists(filename):
            zipf.write(os_path.join(self.vehicle_dir, filename), arcname=filename)

    def zip_files(self, files_to_zip: list[tuple[bool, str]]) -> None:
        """
        Zips the intermediate parameter files that were written to, including specific summary files.

        This method creates a zip archive containing all intermediate parameter files, along with
        specific summary files if they were written. The zip file is saved in the same directory as the
        intermediate parameter files. The method checks for the existence of each file before
        attempting to add it to the zip archive.

        Args:
          files_to_zip (List[Tuple[bool, str]]): A list of tuples, where each tuple contains a boolean
                                            indicating if the file was written and a string for the filename.

        """
        zip_file_path = self.zip_file_path()
        with ZipFile(zip_file_path, "w") as zipf:
            # Add all intermediate parameter files
            for file_name in self.file_parameters:
                self.add_configuration_file_to_zip(zipf, file_name)
                # Add step-specific documentation metadata files
                pdef_xml_file = file_name.replace(".param", ".pdef.xml")
                self.add_configuration_file_to_zip(zipf, pdef_xml_file)

            # Check for and add specific files if they exist
            specific_files = [
                "00_default.param",
                "apm.pdef.xml",
                self.configuration_steps_filename,
                self.vehicle_components_fs.json_filename,
                "vehicle.jpg",
                "last_uploaded_filename.txt",
                "tempcal_gyro.png",
                "tempcal_acc.png",
            ]
            for file_name in specific_files:
                self.add_configuration_file_to_zip(zipf, file_name)

            for wrote, filename in files_to_zip:
                if wrote:
                    self.add_configuration_file_to_zip(zipf, filename)

        logging_info(_("Intermediate parameter files and summary files zipped to %s"), zip_file_path)

    def vehicle_image_filepath(self) -> str:
        return os_path.join(self.vehicle_dir, "vehicle.jpg")

    def vehicle_image_exists(self) -> bool:
        return os_path.exists(self.vehicle_image_filepath()) and os_path.isfile(self.vehicle_image_filepath())

    @staticmethod
    def new_vehicle_dir(base_dir: str, new_dir: str) -> str:
        return os_path.join(base_dir, new_dir)

    @staticmethod
    def directory_exists(directory: str) -> bool:
        return os_path.exists(directory) and os_path.isdir(directory)

    def copy_template_files_to_new_vehicle_dir(
        self, template_dir: str, new_vehicle_dir: str, blank_change_reason: bool, copy_vehicle_image: bool
    ) -> str:
        # Copy the template files to the new vehicle directory
        try:
            if not os_path.exists(template_dir):
                error_msg = _("Template directory does not exist: {template_dir}")
                error_msg = error_msg.format(**locals())
                logging_error(error_msg)
                return error_msg

            if not os_path.exists(new_vehicle_dir):
                error_msg = _("New vehicle directory does not exist: {new_vehicle_dir}")
                error_msg = error_msg.format(**locals())
                logging_error(error_msg)
                return error_msg

            skip_files = {
                "apm.pdef.xml",
                "last_uploaded_filename.txt",
                "tempcal_acc.png",
                "tempcal_gyro.png",
            }
            if not copy_vehicle_image:
                skip_files.add("vehicle.jpg")

            for item in os_listdir(template_dir):
                if item in skip_files:
                    continue
                source = os_path.join(template_dir, item)
                dest = os_path.join(new_vehicle_dir, item)
                if blank_change_reason and item.endswith(".param"):
                    # Blank the change reason in the template files, strip the comments that start with #
                    with open(source, encoding="utf-8") as file:
                        lines = file.readlines()
                    with open(dest, "w", encoding="utf-8") as file:
                        file.writelines(line.split("#")[0].strip() + "\n" for line in lines)
                elif os_path.isdir(source):
                    shutil_copytree(source, dest)
                else:
                    shutil_copy2(source, dest)
        except (OSError, shutil_Error) as _e:
            error_msg = _("Error copying template files to new vehicle directory: {_e}")
            return error_msg.format(**locals())
        return ""

    def remove_created_files_and_vehicle_dir(self) -> str:
        # Remove the created files in the new vehicle directory
        try:
            if not os_path.exists(self.vehicle_dir):
                # Use the actual vehicle_dir value to avoid KeyError from missing format keys
                error_msg = _("New vehicle directory does not exist: {vehicle_dir}")
                error_msg = error_msg.format(vehicle_dir=self.vehicle_dir)
                logging_error(error_msg)
                return error_msg

            # delete all files in the vehicle directory and delete the vehicle directory
            errors: list[str] = []
            for item in os_listdir(self.vehicle_dir):
                item_path = os_path.join(self.vehicle_dir, item)
                try:
                    # If the entry is a symlink, remove the link instead of recursing into the target
                    if os_path.islink(item_path):
                        os_remove(item_path)
                    elif os_path.isdir(item_path):
                        shutil_rmtree(item_path)
                    else:
                        os_remove(item_path)
                except OSError as e:
                    logging_exception(_("Error removing %s"), item_path, e)
                    errors.append(str(e))

            # Try to remove the now-empty vehicle directory
            try:
                os_rmdir(self.vehicle_dir)
            except OSError as e:
                logging_exception(_("Error removing directory %s"), self.vehicle_dir, e)
                errors.append(str(e))

            if errors:
                # Return a combined, localized error message
                error_msg = _("Error removing created files: {error_list}")
                return error_msg.format(error_list="; ".join(errors))
        except OSError as _e:  # filesystem-related errors
            error_msg = _("Error removing created files: {_e}")
            logging_exception(_("Error removing created files:"), exc_info=_e)
            return error_msg.format(**locals())
        return ""

    @staticmethod
    def getcwd() -> str:
        return os_getcwd()

    def tempcal_imu_result_param_tuple(self) -> tuple[str, str]:
        tempcal_imu_result_param_filename = "03_imu_temperature_calibration_results.param"
        return tempcal_imu_result_param_filename, os_path.join(self.vehicle_dir, tempcal_imu_result_param_filename)

    def copy_fc_values_to_file(self, selected_file: str, params: dict[str, float]) -> int:
        ret = 0
        if selected_file in self.file_parameters:
            for param, v in self.file_parameters[selected_file].items():
                if param in params:
                    v.value = params[param]
                    ret += 1
                else:
                    logging_warning(_("Parameter %s not found in the current parameter file"), param)
        return ret

    def write_last_uploaded_filename(self, current_file: str) -> None:
        try:
            with open(os_path.join(self.vehicle_dir, "last_uploaded_filename.txt"), "w", encoding="utf-8") as file:
                file.write(current_file)
        except Exception as e:  # pylint: disable=broad-except
            logging_error(_("Error writing last uploaded filename: %s"), e)

    def __read_last_uploaded_filename(self) -> str:
        try:
            with open(os_path.join(self.vehicle_dir, "last_uploaded_filename.txt"), encoding="utf-8") as file:
                return file.read().strip()
        except FileNotFoundError as e:
            logging_debug(_("last_uploaded_filename.txt not found: %s"), e)
        except Exception as e:  # pylint: disable=broad-except
            logging_error(_("Error reading last uploaded filename: %s"), e)
        return ""

    def get_start_file(self, explicit_index: int, tcal_available: bool) -> str:
        # Get the list of intermediate parameter files files that will be processed sequentially
        files = list(self.file_parameters.keys())

        if explicit_index >= 0:
            if not files:
                return ""

            # Determine the starting file based on the --n command line argument
            start_file_index = explicit_index  # Ensure the index is within the range of available files
            if start_file_index >= len(files):
                start_file_index = len(files) - 1
                logging_warning(
                    _("Starting file index %s is out of range. Starting with file %s instead."),
                    explicit_index,
                    files[start_file_index],
                )
            return files[start_file_index]

        if tcal_available:
            start_file = files[0]
            info_msg = _("Starting with the first file.")
        else:
            start_file = files[2]
            info_msg = _("Starting with the first non-tcal file.")

        last_uploaded_filename = self.__read_last_uploaded_filename()
        if last_uploaded_filename:
            logging_info(_("Last uploaded file was %s."), last_uploaded_filename)
        else:
            logging_info(_("No last uploaded file found. %s."), info_msg)
            return start_file

        if last_uploaded_filename not in files:
            # Handle the case where last_uploaded_filename is not found in the list
            logging_warning(_("Last uploaded file not found in the list of files.  %s."), info_msg)
            return start_file

        # Find the index of last_uploaded_filename in files
        last_uploaded_index = files.index(last_uploaded_filename)
        # Check if there is a file following last_uploaded_filename
        start_file_index = last_uploaded_index + 1
        if start_file_index >= len(files):
            # Handle the case where last_uploaded_filename is the last file in the list
            logging_warning(_("Last uploaded file is the last file in the list. Starting from the beginning."))
            return start_file
        return files[start_file_index]

    def backup_fc_parameters_to_file(
        self,
        param_dict: dict[str, float],
        filename: str,
        overwrite_existing_file: bool = False,
        even_if_last_uploaded_filename_exists: bool = True,
    ) -> None:
        if (even_if_last_uploaded_filename_exists or not self.__read_last_uploaded_filename()) and (
            overwrite_existing_file or not self.vehicle_configuration_file_exists(filename)
        ):
            Par.export_to_param(
                Par.format_params({param: Par(float(value), "") for param, value in param_dict.items()}),
                os_path.join(self.vehicle_dir, filename),
            )

    def get_eval_variables(self) -> dict[str, dict[str, Any]]:
        variables = {}
        if (
            hasattr(self, "vehicle_components_fs")
            and self.vehicle_components_fs.data
            and "Components" in self.vehicle_components_fs.data
        ):
            variables["vehicle_components"] = self.vehicle_components_fs.data["Components"]
        if hasattr(self, "doc_dict") and self.doc_dict:
            variables["doc_dict"] = self.doc_dict
        return variables

    def update_and_export_vehicle_params_from_fc(
        self, source_param_values: Union[dict[str, float], None], existing_fc_params: list[str]
    ) -> str:
        """
        Update parameter values from flight controller data and export to vehicle files.

        This function performs several operations in sequence:
        1. Updates parameter values using the provided source values
        2. Computes forced parameters based on configuration steps
        3. Computes derived parameters that depend on other parameters
        4. Exports the updated parameters to files in the vehicle directory

        Args:
            source_param_values: Dictionary mapping parameter names to their values from the
                                source (typically flight controller). If None, no direct updates occur.
            existing_fc_params: List of params that exist in the FC if empty or None all parameters are+
                                assumed to exist

        Returns:
            str: Empty string if successful, error message otherwise.

        """
        eval_variables = self.get_eval_variables()
        # the eval variables do not contain fc_parameter values
        # and that is intentional, the fc_parameters are not to be used in here
        for param_filename, param_dict in self.file_parameters.items():
            for param_name, param in param_dict.items():
                if source_param_values and param_name in source_param_values:
                    param.value = source_param_values[param_name]
            if self.configuration_steps and param_filename in self.configuration_steps:
                step_dict = self.configuration_steps[param_filename]
                error_msg = self.compute_parameters(param_filename, step_dict, "forced", eval_variables)
                if error_msg:
                    return error_msg
                self.merge_forced_or_derived_parameters(param_filename, self.forced_parameters, existing_fc_params)
                error_msg = self.compute_parameters(param_filename, step_dict, "derived", eval_variables)
                if error_msg:
                    return error_msg
                self.merge_forced_or_derived_parameters(param_filename, self.derived_parameters, existing_fc_params)
            self.export_to_param(
                param_dict, param_filename, annotate_doc=bool(ProgramSettings.get_setting("annotate_docs_into_param_files"))
            )
        return ""

    def merge_forced_or_derived_parameters(
        self, filename: str, new_parameters: dict[str, dict[str, Par]], existing_fc_params: Optional[list[str]]
    ) -> bool:
        """
        Merge forced or derived parameter values in the self.file_parameter list.

        Args:
            filename: The name of the parameter file
            new_parameters: Dictionary of new parameters to potentially add
            existing_fc_params: Optional list of flight controller parameters names

        """
        if new_parameters is None or filename not in new_parameters:
            return False

        at_least_one_param_changed = False
        for param_name, param in new_parameters[filename].items():
            if filename not in self.file_parameters:
                continue
            if existing_fc_params is None or not existing_fc_params or param_name in existing_fc_params:
                if param_name in self.file_parameters[filename]:
                    if not is_within_tolerance(self.file_parameters[filename][param_name].value, param.value):
                        at_least_one_param_changed = True
                else:
                    at_least_one_param_changed = True
                self.file_parameters[filename][param_name] = param
        return at_least_one_param_changed

    def write_param_default_values(self, param_default_values: dict[str, "Par"]) -> bool:
        param_default_values = dict(sorted(param_default_values.items()))
        if self.param_default_dict != param_default_values:
            self.param_default_dict = param_default_values
            return True
        return False

    def write_param_default_values_to_file(
        self, param_default_values: dict[str, "Par"], filename: str = "00_default.param"
    ) -> None:
        if self.write_param_default_values(param_default_values):
            Par.export_to_param(Par.format_params(self.param_default_dict), os_path.join(self.vehicle_dir, filename))

    def get_download_url_and_local_filename(self, selected_file: str) -> tuple[str, str]:
        if (
            selected_file in self.configuration_steps
            and "download_file" in self.configuration_steps[selected_file]
            and self.configuration_steps[selected_file]["download_file"]
        ):
            src = self.configuration_steps[selected_file]["download_file"].get("source_url", "")
            dst = self.configuration_steps[selected_file]["download_file"].get("dest_local", "")
            if self.vehicle_dir and src and dst:
                return src, os_path.join(self.vehicle_dir, dst)
        return "", ""

    def get_upload_local_and_remote_filenames(self, selected_file: str) -> tuple[str, str]:
        if (
            selected_file in self.configuration_steps
            and "upload_file" in self.configuration_steps[selected_file]
            and self.configuration_steps[selected_file]["upload_file"]
        ):
            src = self.configuration_steps[selected_file]["upload_file"].get("source_local", "")
            dst = self.configuration_steps[selected_file]["upload_file"].get("dest_on_fc", "")
            if self.vehicle_dir and src and dst:
                return os_path.join(self.vehicle_dir, src), dst
        return "", ""

    @staticmethod
    def get_git_commit_hash() -> str:
        # Try to get git hash using git command
        try:
            result = run(
                ["git", "rev-parse", "HEAD"],  # noqa: S607
                capture_output=True,
                text=True,
                cwd=os_path.dirname(__file__),
                check=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (SubprocessError, FileNotFoundError) as e:
            # Log the specific error and fallback to reading the git_hash.txt file
            msg = f"Failed to get git hash via command: {e}"
            logging_debug(msg)
            git_hash_file = os_path.join(os_path.dirname(__file__), "git_hash.txt")
            try:
                with open(git_hash_file, encoding="utf-8") as file:
                    return file.read().strip()
            except OSError as exp:
                msg = f"Failed to read git hash from file: {exp}"
                logging_debug(msg)
        return ""

    def find_lowest_available_backup_number(self) -> int:
        """
        Find the lowest non-existing backup number.

        Returns:
            The lowest available backup number

        """
        backup_num = 1  # Start from 01
        while self.vehicle_configuration_file_exists(f"autobackup_{backup_num:02d}.param"):
            backup_num += 1
            if backup_num > 99:  # Prevent endless loop, cap at 99
                # Overwrite the highest number if we reach the cap
                return 99
        return backup_num

    @staticmethod
    def add_argparse_arguments(parser: ArgumentParser) -> ArgumentParser:
        parser.add_argument(
            "-t",
            "--vehicle-type",
            choices=VehicleComponents.supported_vehicles(),
            default="",
            help=_("The type of the vehicle. Default is ArduCopter"),
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--vehicle-dir",
            type=str,
            default=os_getcwd(),
            help=_(
                "Directory containing vehicle-specific intermediate parameter files. Default is the current working directory"
            ),
        ).completer = DirectoriesCompleter()  # type: ignore[no-untyped-call]
        parser.add_argument(
            "--n",
            type=int,
            default=-1,
            help=_(
                "Start directly on the nth intermediate parameter file (skips previous files). "
                "Default is to start on the file next to the last that you wrote to the flight controller. "
                "If the file does not exist, it will start on the first file."
            ),
        )
        parser.add_argument(
            "--allow-editing-template-files",
            action="store_true",
            help=_(
                "Allow opening and editing template files directly. "
                "Only for software developers that know what they are doing. "
                "Default is %(default)s"
            ),
        )
        parser.add_argument(
            "--save-component-to-system-templates",
            action="store_true",
            help=_(
                "Save the vehicle component to the system templates. "
                "Only for software developers that know what they are doing. "
                "Default is %(default)s"
            ),
        )
        return parser
