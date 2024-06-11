#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

from os import path as os_path
from os import getcwd as os_getcwd
from os import listdir as os_listdir
from os import makedirs as os_makedirs
from os import rename as os_rename
from os import walk as os_walk
from os import sep as os_sep

from shutil import copy2 as shutil_copy2
from shutil import copytree as shutil_copytree

from re import compile as re_compile
from re import match as re_match
from re import escape as re_escape
from re import sub as re_sub

# from sys import exit as sys_exit
from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error

from json import load as json_load
from json import dump as json_dump

from platform import system as platform_system

from typing import Dict
from typing import List
from typing import Tuple

from zipfile import ZipFile

from platformdirs import site_config_dir
from platformdirs import user_config_dir

from MethodicConfigurator.annotate_params import BASE_URL, PARAM_DEFINITION_XML_FILE, Par
from MethodicConfigurator.annotate_params import get_xml_data
from MethodicConfigurator.annotate_params import create_doc_dict
from MethodicConfigurator.annotate_params import format_columns
from MethodicConfigurator.annotate_params import split_into_lines
from MethodicConfigurator.annotate_params import update_parameter_documentation

from MethodicConfigurator.backend_filesystem_vehicle_components import VehicleComponents
from MethodicConfigurator.backend_filesystem_configuration_steps import ConfigurationSteps

from MethodicConfigurator.middleware_template_overview import TemplateOverview

TOOLTIP_MAX_LENGTH = 105


def is_within_tolerance(x: float, y: float, atol: float = 1e-08, rtol: float = 1e-03) -> bool:
    """
    Determines if the absolute difference between two numbers is within a specified tolerance.

    This function checks if the absolute difference between `x` and `y` is less than or equal to
    the sum of the absolute tolerance (`atol`) and the product of the relative tolerance (`rtol`)
    and the absolute value of `y`.

    Parameters:
    - x (float): The first number to compare.
    - y (float): The second number to compare.
    - atol (float, optional): The absolute tolerance. Defaults to 1e-08.
    - rtol (float, optional): The relative tolerance. Defaults to 1e-03.

    Returns:
    - bool: True if the difference is within the tolerance, False otherwise.
    """
    return abs(x - y) <= atol + (rtol * abs(y))


class LocalFilesystem(VehicleComponents, ConfigurationSteps):  # pylint: disable=too-many-public-methods
    """
    A class to manage local filesystem operations for the ArduPilot methodic configurator.

    This class provides methods for initializing and re-initializing the filesystem context,
    reading parameters from files, and handling configuration steps. It is designed to simplify
    the interaction with the local filesystem for managing ArduPilot configuration files.

    Attributes:
        vehicle_dir (str): The directory path where the vehicle configuration files are stored.
        vehicle_type (str): The type of the vehicle (e.g., "ArduCopter", "Rover").
        file_parameters (dict): A dictionary of parameters read from intermediate parameter files.
        param_default_dict (dict): A dictionary of default parameter values.
        doc_dict (dict): A dictionary containing documentation for each parameter.
    """
    def __init__(self, vehicle_dir: str, vehicle_type: str, allow_editing_template_files: bool = False):
        self.file_parameters = None
        VehicleComponents.__init__(self)
        ConfigurationSteps.__init__(self, vehicle_dir, vehicle_type)
        self.allow_editing_template_files = allow_editing_template_files
        if vehicle_dir is not None:
            self.re_init(vehicle_dir, vehicle_type)

    def re_init(self, vehicle_dir: str, vehicle_type: str):
        ConfigurationSteps.re_init(self, vehicle_dir, vehicle_type)
        self.vehicle_dir = vehicle_dir
        self.vehicle_type = vehicle_type
        self.param_default_dict = {}
        self.doc_dict = {}

        # Rename parameter files if some new files got added to the vehicle directory
        self.rename_parameter_files()

        # Read intermediate parameters from files
        self.file_parameters = self.read_params_from_files()
        if not self.file_parameters:
            return # No files intermediate parameters files found, no need to continue, the rest needs them

        # Read ArduPilot parameter documentation
        xml_dir = vehicle_dir if os_path.isdir(vehicle_dir) else os_path.dirname(os_path.realpath(vehicle_dir))
        xml_root, self.param_default_dict = get_xml_data(BASE_URL + vehicle_type + "/", xml_dir, PARAM_DEFINITION_XML_FILE)
        self.doc_dict = create_doc_dict(xml_root, vehicle_type, TOOLTIP_MAX_LENGTH)

        self.__extend_and_reformat_parameter_documentation_metadata()
        self.load_vehicle_components_json_data(vehicle_dir)

    def rename_parameter_files(self):
        # Rename parameter files if some new files got added to the vehicle directory
        if self.vehicle_dir is not None and self.configuration_steps is not None:
            for new_filename in self.configuration_steps:
                if 'old_filenames' in self.configuration_steps[new_filename]:
                    for old_filename in self.configuration_steps[new_filename]['old_filenames']:
                        if self.intermediate_parameter_file_exists(old_filename) and old_filename != new_filename:
                            new_filename_path = os_path.join(self.vehicle_dir, new_filename)
                            old_filename_path = os_path.join(self.vehicle_dir, old_filename)
                            os_rename(old_filename_path, new_filename_path)
                            logging_info("Renamed %s to %s", old_filename, new_filename)

    def __extend_and_reformat_parameter_documentation_metadata(self):
        for param_name, param_info in self.doc_dict.items():
            if 'fields' in param_info:
                if 'Units' in param_info['fields']:
                    param_info['unit'] = param_info['fields']['Units'].split('(')[0].strip()
                    param_info['unit_tooltip'] = param_info['fields']['Units'].split('(')[1].strip(')')
                if 'Range' in param_info['fields']:
                    param_info['min'] = float(param_info['fields']['Range'].split(' ')[0].strip())
                    param_info['max'] = float(param_info['fields']['Range'].split(' ')[1].strip())
                if 'Calibration' in param_info['fields']:
                    param_info['Calibration'] = self.str_to_bool(param_info['fields']['Calibration'].strip())
                if 'ReadOnly' in param_info['fields']:
                    param_info['ReadOnly'] = self.str_to_bool(param_info['fields']['ReadOnly'].strip())
                if 'RebootRequired' in param_info['fields']:
                    param_info['RebootRequired'] = self.str_to_bool(param_info['fields']['RebootRequired'].strip())
                if 'Bitmask' in param_info['fields']:
                    bitmask_items = param_info['fields']['Bitmask'].split(',')
                    param_info['Bitmask'] = {}
                    for item in bitmask_items:
                        key, value = item.split(':')
                        param_info['Bitmask'][int(key.strip())] = value.strip()

            prefix_parts = [
                f"{param_info['humanName']}",
            ]
            prefix_parts += param_info["documentation"]
            for key, value in param_info["fields"].items():
                if key not in ['Units', 'UnitText']:
                    prefix_parts += split_into_lines(f"{key}: {value}", TOOLTIP_MAX_LENGTH)
            prefix_parts += format_columns(param_info["values"], TOOLTIP_MAX_LENGTH)
            if param_name in self.param_default_dict:
                default_value = format(self.param_default_dict[param_name].value, '.6f').rstrip('0').rstrip('.')
                prefix_parts += [f"Default: {default_value}"]
            param_info['doc_tooltip'] = ('\n').join(prefix_parts)

    def read_params_from_files(self):
        """
        Reads intermediate parameter files from a directory and stores their contents in a dictionary.

        This function scans the specified directory for files matching a specific pattern,
        reads each file, and stores the parameter names and values in a dictionary.
        Files named '00_default.param' and '01_ignore_readonly.param' are ignored.

        Returns:
        - Dict[str, Dict[str, 'Par']]: A dictionary with filenames as keys and as values
                                       a dictionary with (parameter names, values) pairs.
        """
        parameters = {}
        if os_path.isdir(self.vehicle_dir):
            # Regular expression pattern for filenames starting with two digits followed by an underscore and ending in .param
            pattern = re_compile(r'^\d{2}_.*\.param$')

            for filename in sorted(os_listdir(self.vehicle_dir)):
                if pattern.match(filename):
                    if filename in ['00_default.param', '01_ignore_readonly.param']:
                        continue
                    parameters[filename] = Par.load_param_file_into_dict(os_path.join(self.vehicle_dir, filename))
        else:
            logging_error("Error: %s is not a directory.", self.vehicle_dir)
        return parameters

    @staticmethod
    def str_to_bool(s):
        """
        Converts a string representation of a boolean value to a boolean.

        This function interprets the string 'true', 'yes', '1' as True, and 'false', 'no', '0' as False.
        Any other input will return None.

        Parameters:
        - s (str): The string to convert.

        Returns:
        - Optional[bool]: True, False, or None if the string does not match any known boolean representation.
        """
        if s.lower() == "true" or s.lower() == "yes" or s.lower() == "1":
            return True
        if s.lower() == "false" or s.lower() == "no" or s.lower() == "0":
            return False
        return None

    def export_to_param(self, params: Dict[str, 'Par'], filename_out: str, annotate_doc: bool = True) -> None:
        """
        Exports a dictionary of parameters to a .param file and optionally annotates the documentation.

        This function formats the provided parameters into a string suitable for a .param file,
        writes the string to the specified output file, and optionally updates the parameter documentation.

        Parameters:
        - params (Dict[str, 'Par']): A dictionary of parameters to export.
        - filename_out (str): The name of the output file.
        - annotate_doc (bool, optional): Whether to update the parameter documentation. Defaults to True.
        """
        Par.export_to_param(Par.format_params(params), os_path.join(self.vehicle_dir, filename_out))
        if annotate_doc:
            update_parameter_documentation(self.doc_dict,
                                           os_path.join(self.vehicle_dir, filename_out),
                                           "missionplanner",
                                           self.param_default_dict)

    def intermediate_parameter_file_exists(self, filename: str) -> bool:
        """
        Check if an intermediate parameter file exists in the vehicle directory.

        Parameters:
        - filename (str): The name of the file to check.

        Returns:
        - bool: True if the file exists and is a file (not a directory), False otherwise.
        """
        return os_path.exists(os_path.join(self.vehicle_dir, filename)) and \
            os_path.isfile(os_path.join(self.vehicle_dir, filename))

    def __all_intermediate_parameter_file_comments(self) -> Dict[str, str]:
        """
        Retrieves all comments associated with parameters from intermediate parameter files.

        This method iterates through all intermediate parameter files, collects comments for each parameter,
        and returns them as a dictionary where the keys are parameter names and the values are the comments.
        Comments from the same parameter in different files are not merged; only the comment from the last file is returned.

        Returns:
        - Dict[str, str]: A dictionary mapping parameter names to their comments.
        """
        ret = {}
        for _filename, params in self.file_parameters.items():
            for param, info in params.items():
                if info.comment:
                    ret[param] = info.comment
        return ret

    def annotate_intermediate_comments_to_param_dict(self, param_dict: Dict[str, float]) -> Dict[str, 'Par']:
        """
        Annotates comments from intermediate parameter files to a parameter value-only dictionary.

        This function takes a dictionary of parameters with only values and adds comments from
        intermediate parameter files to create a new dictionary where each parameter is represented
        by a 'Par' object containing both the value and the comment.

        Parameters:
        - param_dict (Dict[str, float]): A dictionary of parameters with only values.

        Returns:
        - Dict[str, 'Par']: A dictionary of parameters with intermediate parameter file comments.
        """
        ret = {}
        ip_comments = self.__all_intermediate_parameter_file_comments()
        for param, value in param_dict.items():
            ret[param] = Par(float(value), ip_comments.get(param, ''))
        return ret

    def categorize_parameters(self, param: Dict[str, 'Par']) -> List[Dict[str, 'Par']]:
        """
        Categorize parameters into three categories based on their default values and documentation attributes.

        This method iterates through the provided dictionary of parameters and categorizes them into three groups:
        - Non-default, read-only parameters
        - Non-default, writable calibrations
        - Non-default, writable non-calibrations

        Parameters:
        - param (Dict[str, 'Par']): A dictionary mapping parameter names to their 'Par' objects.

        Returns:
        - List[Dict[str, 'Par']]: A list containing three dictionaries.
                                  Each dictionary represents one of the categories mentioned above.
        """
        non_default__read_only_params = {}
        non_default__writable_calibrations = {}
        non_default__writable_non_calibrations = {}
        for param_name, param_info in param.items():
            if param_name in self.param_default_dict and is_within_tolerance(param_info.value,
                                                                             self.param_default_dict[param_name].value):
                continue     # parameter has a default value, ignore it

            if param_name in self.doc_dict and self.doc_dict[param_name].get('ReadOnly', False):
                non_default__read_only_params[param_name] = param_info
                continue

            if param_name in self.doc_dict and self.doc_dict[param_name].get('Calibration', False):
                non_default__writable_calibrations[param_name] = param_info
                continue
            non_default__writable_non_calibrations[param_name] = param_info

        return non_default__read_only_params, non_default__writable_calibrations, non_default__writable_non_calibrations

    # Extract the vehicle name from the directory path
    def get_vehicle_directory_name(self):
        # Normalize the path to ensure it's in a standard format
        normalized_path = os_path.normpath(self.vehicle_dir)

        # Split the path into head and tail, then get the basename of the tail
        directory_name = os_path.basename(os_path.split(normalized_path)[1])

        return directory_name

    def zip_file_path(self):
        vehicle_name = self.get_vehicle_directory_name()
        return os_path.join(self.vehicle_dir, f"{vehicle_name}.zip")

    def zip_file_exists(self):
        zip_file_path = self.zip_file_path()
        return os_path.exists(zip_file_path) and os_path.isfile(zip_file_path)

    def zip_files(self, files_to_zip: List[Tuple[bool, str]]):
        """
        Zips the intermediate parameter files that were written to, including specific summary files.

        This method creates a zip archive containing all intermediate parameter files, along with
        specific summary files if they were written. The zip file is saved in the same directory as the
        intermediate parameter files. The method checks for the existence of each file before
        attempting to add it to the zip archive.

        Parameters:
        - files_to_zip (List[Tuple[bool, str]]): A list of tuples, where each tuple contains a boolean
                                            indicating if the file was written and a string for the filename.
        """
        zip_file_path = self.zip_file_path()
        with ZipFile(zip_file_path, 'w') as zipf:
            # Add all intermediate parameter files
            for file_name in self.file_parameters:
                zipf.write(os_path.join(self.vehicle_dir, file_name), arcname=file_name)

            # Check for and add specific files if they exist
            specific_files = ["00_default.param", "apm.pdef.xml", self.configuration_steps_filename,
                              "vehicle_components.json", "vehicle.jpg", "last_uploaded_filename.txt",
                              "tempcal_gyro.png", "tempcal_acc.png"]
            for file_name in specific_files:
                file_path = os_path.join(self.vehicle_dir, file_name)
                if os_path.exists(file_path):
                    zipf.write(file_path, arcname=file_name)

            for wrote, filename in files_to_zip:
                if wrote:
                    file_path = os_path.join(self.vehicle_dir, filename)
                    if os_path.exists(file_path):
                        zipf.write(file_path, arcname=filename)

        logging_info("Intermediate parameter files and summary files zipped to %s", zip_file_path)

    @staticmethod
    def application_icon_filepath():
        script_dir = os_path.dirname(os_path.abspath(__file__))
        return os_path.join(script_dir, 'ArduPilot_icon.png')

    @staticmethod
    def application_logo_filepath():
        script_dir = os_path.dirname(os_path.abspath(__file__))
        return os_path.join(script_dir, 'ArduPilot_logo.png')

    def vehicle_image_filepath(self):
        return os_path.join(self.vehicle_dir, 'vehicle.jpg')

    def vehicle_image_exists(self):
        return os_path.exists(self.vehicle_image_filepath())

    @staticmethod
    def new_vehicle_dir(base_dir: str, new_dir: str):
        return os_path.join(base_dir, new_dir)

    @staticmethod
    def directory_exists(directory: str) -> bool:
        return os_path.exists(directory)

    def create_new_vehicle_dir(self, new_vehicle_dir: str):
        # Check if the new vehicle directory already exists
        if os_path.exists(new_vehicle_dir):
            return "Directory already exists, choose a different one"

        try:
            # Create the new vehicle directory
            os_makedirs(new_vehicle_dir, exist_ok=True)
        except OSError as e:
            logging_error("Error creating new vehicle directory: %s", e)
            return str(e)
        return ""

    def copy_template_files_to_new_vehicle_dir(self, template_dir: str, new_vehicle_dir: str):
        # Copy the template files to the new vehicle directory
        for item in os_listdir(template_dir):
            s = os_path.join(template_dir, item)
            d = os_path.join(new_vehicle_dir, item)
            if os_path.isdir(s):
                shutil_copytree(s, d)
            else:
                shutil_copy2(s, d)

    @staticmethod
    def getcwd():
        return os_getcwd()

    @staticmethod
    def valid_directory_name(dir_name: str):
        """
        Check if a given directory name contains only alphanumeric characters, underscores, hyphens,
        and the OS directory separator.

        This function is designed to ensure that the directory name does not contain characters that are
        invalid for directory names in many operating systems. It does not guarantee that the name
        is valid in all contexts or operating systems, as directory name validity can vary.

        Parameters:
        - dir_name (str): The directory name to check.

        Returns:
        - bool: True if the directory name matches the allowed pattern, False otherwise.
        """
        # Include os.sep in the pattern
        pattern = r'^[\w' + re_escape(os_sep) + '-]+$'
        return re_match(pattern, dir_name) is not None

    def tempcal_imu_result_param_tuple(self):
        tempcal_imu_result_param_filename = "03_imu_temperature_calibration_results.param"
        return [tempcal_imu_result_param_filename, os_path.join(self.vehicle_dir, tempcal_imu_result_param_filename)]

    def copy_fc_values_to_file(self, selected_file: str, params: Dict[str, float]):
        ret = 0
        if selected_file in self.file_parameters:
            for param, v in self.file_parameters[selected_file].items():
                if param in params:
                    v.value = params[param]
                    ret += 1
                else:
                    logging_warning("Parameter %s not found in the current parameter file", param)
        return ret

    @staticmethod
    def __user_config_dir():
        user_config_directory = user_config_dir(".ardupilot_methodic_configurator", False, roaming=True, ensure_exists=True)

        if not os_path.exists(user_config_directory):
            raise FileNotFoundError(f"The user configuration directory '{user_config_directory}' does not exist.")
        if not os_path.isdir(user_config_directory):
            raise NotADirectoryError(f"The path '{user_config_directory}' is not a directory.")

        return user_config_directory

    @staticmethod
    def __site_config_dir():
        site_config_directory = site_config_dir(".ardupilot_methodic_configurator", False, version=None, multipath=False,
                                                ensure_exists=True)

        if not os_path.exists(site_config_directory):
            raise FileNotFoundError(f"The site configuration directory '{site_config_directory}' does not exist.")
        if not os_path.isdir(site_config_directory):
            raise NotADirectoryError(f"The path '{site_config_directory}' is not a directory.")

        return site_config_directory

    @staticmethod
    def __get_settings_as_dict():
        settings_path = os_path.join(LocalFilesystem.__user_config_dir(), "settings.json")

        settings = {}

        try:
            with open(settings_path, "r", encoding='utf-8') as settings_file:
                settings = json_load(settings_file)
        except FileNotFoundError:
            # If the file does not exist, it will be created later
            pass

        if "Format version" not in settings:
            settings["Format version"] = 1

        if "directory_selection" not in settings:
            settings["directory_selection"] = {}
        return settings

    @staticmethod
    def __set_settings_from_dict(settings):
        settings_path = os_path.join(LocalFilesystem.__user_config_dir(), "settings.json")

        with open(settings_path, "w", encoding='utf-8') as settings_file:
            json_dump(settings, settings_file, indent=4)

    @staticmethod
    def __get_settings_config():
        settings = LocalFilesystem.__get_settings_as_dict()

        # Regular expression pattern to match single backslashes
        pattern = r"(?<!\\)\\(?!\\)|(?<!/)/(?!/)"

        # Replacement string
        if platform_system() == 'Windows':
            replacement = r"\\"
        else:
            replacement = r"/"
        return settings, pattern, replacement

    @staticmethod
    def store_recently_used_template_dirs(template_dir: str, new_base_dir: str):
        settings, pattern, replacement = LocalFilesystem.__get_settings_config()

        # Update the settings with the new values
        settings["directory_selection"].update({
            "template_dir": re_sub(pattern, replacement, template_dir),
            "new_base_dir": re_sub(pattern, replacement, new_base_dir)
        })

        LocalFilesystem.__set_settings_from_dict(settings)

    @staticmethod
    def store_template_dir(relative_template_dir: str):
        settings, pattern, replacement = LocalFilesystem.__get_settings_config()

        template_dir = os_path.join(LocalFilesystem.get_templates_base_dir(), relative_template_dir)

        # Update the settings with the new values
        settings["directory_selection"].update({
            "template_dir": re_sub(pattern, replacement, template_dir)
        })

        LocalFilesystem.__set_settings_from_dict(settings)

    @staticmethod
    def store_recently_used_vehicle_dir(vehicle_dir: str):
        settings, pattern, replacement = LocalFilesystem.__get_settings_config()

        # Update the settings with the new values
        settings["directory_selection"].update({
            "vehicle_dir": re_sub(pattern, replacement, vehicle_dir)
        })

        LocalFilesystem.__set_settings_from_dict(settings)


    @staticmethod
    def get_templates_base_dir():
        current_dir = os_path.dirname(os_path.abspath(__file__))
        if platform_system() == 'Windows':
            current_dir = current_dir.replace("\\_internal", "")
        else:
            current_dir = current_dir.replace("/MethodicConfigurator", "")
        program_dir = current_dir

        if platform_system() == 'Windows':
            site_directory = LocalFilesystem.__site_config_dir()
        else:
            site_directory = program_dir
        return os_path.join(site_directory, "vehicle_templates")

    @staticmethod
    def get_recently_used_dirs():
        template_default_dir = os_path.join(LocalFilesystem.get_templates_base_dir(),
                                            "ArduCopter", "diatone_taycan_mxc", "4.5.3-params")

        settings_directory = LocalFilesystem.__user_config_dir()
        vehicles_default_dir = os_path.join(settings_directory, "vehicles")
        if not os_path.exists(vehicles_default_dir):
            os_makedirs(vehicles_default_dir, exist_ok=True)

        settings = LocalFilesystem.__get_settings_as_dict()
        template_dir = settings["directory_selection"].get("template_dir", template_default_dir)
        new_base_dir = settings["directory_selection"].get("new_base_dir", vehicles_default_dir)
        vehicle_dir = settings["directory_selection"].get("vehicle_dir", vehicles_default_dir)

        return template_dir, new_base_dir, vehicle_dir

    def write_last_uploaded_filename(self, current_file: str):
        try:
            with open(os_path.join(self.vehicle_dir, 'last_uploaded_filename.txt'), 'w', encoding='utf-8') as file:
                file.write(current_file)
        except Exception as e:  # pylint: disable=broad-except
            logging_error("Error writing last uploaded filename: %s", e)

    def __read_last_uploaded_filename(self) -> str:
        try:
            with open(os_path.join(self.vehicle_dir, 'last_uploaded_filename.txt'), 'r', encoding='utf-8') as file:
                return file.read().strip()
        except FileNotFoundError as e:
            logging_debug("last_uploaded_filename.txt not found: %s", e)
        except Exception as e:  # pylint: disable=broad-except
            logging_error("Error reading last uploaded filename: %s", e)
        return ""

    def get_start_file(self, explicit_index: int):
        # Get the list of intermediate parameter files files that will be processed sequentially
        files = list(self.file_parameters.keys())

        if explicit_index >= 0:
            if not files:
                return ""

            # Determine the starting file based on the --n command line argument
            start_file_index = explicit_index # Ensure the index is within the range of available files
            if start_file_index >= len(files):
                start_file_index = len(files) - 1
                logging_warning("Starting file index %s is out of range. Starting with file %s instead.",
                                explicit_index, files[start_file_index])
            return files[start_file_index]

        last_uploaded_filename = self.__read_last_uploaded_filename()
        if last_uploaded_filename:
            logging_info("Last uploaded file was %s.", last_uploaded_filename)
        else:
            logging_info("No last uploaded file found. Starting with the first file.")
            return files[0]

        if last_uploaded_filename not in files:
            # Handle the case where last_uploaded_filename is not found in the list
            logging_warning("Last uploaded file not found in the list of files. Starting with the first file.")
            return files[0]

        # Find the index of last_uploaded_filename in files
        last_uploaded_index = files.index(last_uploaded_filename)
        # Check if there is a file following last_uploaded_filename
        start_file_index = last_uploaded_index + 1
        if start_file_index >= len(files):
            # Handle the case where last_uploaded_filename is the last file in the list
            logging_warning("Last uploaded file is the last file in the list. Starting from there.")
            start_file_index = len(files) - 1
        return files[start_file_index]

    def get_eval_variables(self):
        variables = {}
        if hasattr(self, 'vehicle_components') and self.vehicle_components and \
                'Components' in self.vehicle_components:
            variables['vehicle_components'] = self.vehicle_components['Components']
        if hasattr(self, 'doc_dict') and self.doc_dict:
            variables['doc_dict'] = self.doc_dict
        return variables

    def copy_fc_params_values_to_template_created_vehicle_files(self, fc_parameters: Dict[str, 'Par']):
        eval_variables = self.get_eval_variables()
        eval_variables['fc_parameters'] = fc_parameters
        for param_filename, param_dict in self.file_parameters.items():
            for param_name, param in param_dict.items():
                if param_name in fc_parameters:
                    param.value = fc_parameters[param_name]
            if self.configuration_steps and param_filename in self.configuration_steps:
                step_dict = self.configuration_steps[param_filename]
                error_msg = self.compute_parameters(param_filename, step_dict, 'forced', eval_variables)
                if error_msg:
                    return error_msg
                error_msg = self.compute_parameters(param_filename, step_dict, 'derived', eval_variables)
                if error_msg:
                    return error_msg
            Par.export_to_param(Par.format_params(param_dict), os_path.join(self.vehicle_dir, param_filename))
        return ''

    @staticmethod
    def supported_vehicles():
        return ['AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane',
                                    'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL']

    @staticmethod
    def get_vehicle_components_overviews():
        """
        Finds all subdirectories of base_dir containing a "vehicle_components.json" file,
        creates a dictionary where the keys are the subdirectory names (relative to base_dir)
        and the values are instances of VehicleComponents.

        :param base_dir: The base directory to start searching from.
        :return: A dictionary mapping subdirectory paths to VehicleComponents instances.
        """
        vehicle_components_dict = {}
        file_to_find = VehicleComponents().vehicle_components_json_filename
        template_default_dir = LocalFilesystem.get_templates_base_dir()
        for root, _dirs, files in os_walk(template_default_dir):
            if file_to_find in files:
                relative_path = os_path.relpath(root, template_default_dir)
                vehicle_components = VehicleComponents()
                comp_data = vehicle_components.load_vehicle_components_json_data(root)
                if comp_data:
                    comp_data = comp_data.get('Components', {})
                    vehicle_components_overview = TemplateOverview(comp_data)
                    vehicle_components_dict[relative_path] = vehicle_components_overview

        return vehicle_components_dict

    @staticmethod
    def add_argparse_arguments(parser):
        parser.add_argument('-t', '--vehicle-type',
                            choices=LocalFilesystem.supported_vehicles(),
                            default='',
                            help='The type of the vehicle. Defaults to ArduCopter')
        parser.add_argument('--vehicle-dir',
                            type=str,
                            default=os_getcwd(),
                            help='Directory containing vehicle-specific intermediate parameter files. '
                            'Defaults to the current working directory')
        parser.add_argument('--n',
                            type=int,
                            default=-1,
                            help='Start directly on the nth intermediate parameter file (skips previous files). '
                            'Default is to start on the file next to the last that you wrote to the flight controller.'
                            'If the file does not exist, it will start on the first file.')
        parser.add_argument('--allow-editing-template-files',
                            action='store_true',
                            help='Allow opening and editing template files directly. '
                            'Only for software developers that know what they are doing.')
        return parser
