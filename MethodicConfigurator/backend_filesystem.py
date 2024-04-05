#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

AP_FLAKE8_CLEAN

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from os import path as os_path
from os import listdir as os_listdir
from re import compile as re_compile
# from sys import exit as sys_exit
# from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
from json import load as json_load
from typing import Dict, List
from zipfile import ZipFile
from annotate_params import BASE_URL, PARAM_DEFINITION_XML_FILE, Par
from annotate_params import get_xml_data
from annotate_params import create_doc_dict
from annotate_params import format_columns
from annotate_params import split_into_lines
from annotate_params import update_parameter_documentation


TOOLTIP_MAX_LENGTH = 105


def is_within_tolerance(x: float, y: float, atol: float = 1e-08, rtol: float = 1e-03) -> bool:
    """
    Checks if the absolute difference between x and y is within a certain tolerance.

    Parameters:
    x, y (float): The two numbers to compare.
    atol (float): The absolute tolerance.
    rtol (float): The relative tolerance.

    Returns:
    bool: True if the difference is within the tolerance, False otherwise.
    """
    return abs(x - y) <= atol + (rtol * abs(y))


class LocalFilesystem:
    def __init__(self, vehicle_dir: str, vehicle_type: str):
        self.vehicle_dir = vehicle_dir
        self.vehicle_type = vehicle_type
        self.re_init(vehicle_dir, vehicle_type)

    def re_init(self, vehicle_dir: str, vehicle_type: str):
        self.vehicle_dir = vehicle_dir
        self.vehicle_type = vehicle_type
        # Read intermediate parameters from files
        self.file_parameters = self.read_params_from_files()

        self.file_documentation_filename = "file_documentation.json"
        try:
            with open(os_path.join(self.vehicle_dir, self.file_documentation_filename), 'r', encoding='utf-8') as file:
                self.file_documentation = json_load(file)
        except FileNotFoundError:
            logging_warning("File '%s' not found in %s.", self.file_documentation_filename, self.vehicle_dir)
            logging_warning("Will now try to find it in the current application directory")
            try:
                with open(self.file_documentation_filename, 'r', encoding='utf-8') as file:
                    self.file_documentation = json_load(file)
            except FileNotFoundError:
                self.file_documentation = {}
                logging_warning("File '%s' not found the current application directory", self.file_documentation_filename)
                logging_warning("No file documentation will be available.")

        # Read ArduPilot parameter documentation
        xml_dir = vehicle_dir if os_path.isdir(vehicle_dir) else os_path.dirname(os_path.realpath(vehicle_dir))
        xml_root, self.param_default_dict = get_xml_data(BASE_URL + vehicle_type + "/", xml_dir, PARAM_DEFINITION_XML_FILE)
        self.doc_dict = create_doc_dict(xml_root, vehicle_type, TOOLTIP_MAX_LENGTH)

        self.extend_and_reformat_parameter_documentation_metadata()

    def extend_and_reformat_parameter_documentation_metadata(self):
        for param_name, param_info in self.doc_dict.items():
            if 'fields' in param_info:
                if 'Units' in param_info['fields']:
                    param_info['unit'] = param_info['fields']['Units'].split('(')[0].strip()
                if 'Units' in param_info['fields']:
                    param_info['unit_tooltip'] = param_info['fields']['Units'].split('(')[1].strip(')')
                if 'Range' in param_info['fields']:
                    param_info['min'] = float(param_info['fields']['Range'].split(' ')[0].strip())
                if 'Range' in param_info['fields']:
                    param_info['max'] = float(param_info['fields']['Range'].split(' ')[1].strip())
                if 'Calibration' in param_info['fields']:
                    param_info['Calibration'] = self.str_to_bool(param_info['fields']['Calibration'].strip())
                if 'ReadOnly' in param_info['fields']:
                    param_info['ReadOnly'] = self.str_to_bool(param_info['fields']['ReadOnly'].strip())
                if 'RebootRequired' in param_info['fields']:
                    param_info['RebootRequired'] = self.str_to_bool(param_info['fields']['RebootRequired'].strip())

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
        Reads intermediate parameter files from a directory and stores their contents in a dictionary of dictionaries.

        Returns:
        dict: A dictionary with filenames as keys and as values a dictionary with (parameter names, values) pairs.
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
        if s.lower() == "true" or s.lower() == "yes" or s.lower() == "1":
            return True
        elif s.lower() == "false" or s.lower() == "no" or s.lower() == "0":
            return False
        else:
            return None

    def export_to_param(self, params: Dict[str, 'Par'], filename_out: str, annotate_doc: bool = True) -> None:
        Par.export_to_param(Par.format_params(params), os_path.join(self.vehicle_dir, filename_out))
        if annotate_doc:
            update_parameter_documentation(self.doc_dict,
                                           os_path.join(self.vehicle_dir, filename_out),
                                           "missionplanner",
                                           self.param_default_dict)

    def intermediate_parameter_file_exists(self, filename: str) -> bool:
        return os_path.exists(os_path.join(self.vehicle_dir, filename)) and \
            os_path.isfile(os_path.join(self.vehicle_dir, filename))

    def all_intermediate_parameter_file_comments(self) -> Dict[str, str]:
        """
        Retrieves all comments associated with parameters from intermediate parameter files.

        This method iterates through all intermediate parameter files and collects comments for each parameter.
        Comments from the same parameter in different files are not merged.
        If a parameter has a comment in multiple files, only the comment from the last file is returned.
        The comments are then returned as a dictionary where the keys are parameter names and the values are the comments.

        Returns:
            Dict[str, str]: A dictionary mapping parameter names to their comments.
        """
        ret = {}
        for _filename, params in self.file_parameters.items():
            for param, info in params.items():
                if info.comment:
                    ret[param] = info.comment
        return ret

    def annotate_intermediate_comments_to_param_dict(self, param_dict: Dict[str, float]) -> Dict[str, 'Par']:
        """
        Annotates comments from intermediate parameter files to a parameter value only dictionary.

        Args:
            param_dict (Dict[str, float]): A dictionary of parameters.

        Returns:
            Par: A dictionary of parameters with intermediate parameter file comments.
        """
        ret = {}
        ip_comments = self.all_intermediate_parameter_file_comments()
        for param, value in param_dict.items():
            ret[param] = Par(float(value), ip_comments.get(param, ''))
        return ret

    def categorize_parameters(self, param: Dict[str, 'Par']) -> List[Dict[str, 'Par']]:
        """
        Categorizes parameters into three categories based on their default values and documentation attributes.

        This method iterates through the provided dictionary of parameters and categorizes them into three groups:
        - Non-default, read-only parameters
        - Non-default, writable calibrations
        - Non-default, writable non-calibrations

        Parameters:
            param (Dict[str, 'Par']): A dictionary mapping parameter names to their 'Par' objects.

        Returns:
            List[Dict[str, 'Par']]: A list containing three dictionaries.
                                    Each dictionary represents one of the categories mentioned above.
        """
        non_default__read_only_params = {}
        non_default__writable_calibrations = {}
        non_default__writable_non_calibrations = {}
        for param_name, param_info in param.items():
            if param_name in self.param_default_dict and is_within_tolerance(param_info.value,
                                                                             self.param_default_dict[param_name].value):
                continue     # parameter has default value, ignore it

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

    def zip_files(self, wrote_complete, filename_complete, wrote_read_only, filename_read_only,
                  wrote_calibrations, filename_calibrations, wrote_non_calibrations, filename_non_calibrations):
        """
        Zips the intermediate parameter files that were written to.

        This method zips the intermediate parameter files that were written to the fight controller.
        The zip file are saved in the same directory as the intermediate parameter files.

        Parameters:
        wrote_complete (bool): True if complete parameter written to file, False otherwise.
        filename_complete (str): Name of complete file.
        wrote_read_only (bool): True if read-only parameters were written to file, False otherwise.
        filename_read_only (str): Name of  read-only file.
        wrote_calibrations (bool): True if calibration parameters were written to file, False otherwise.
        filename_calibrations (str): Name of calibration file.
        wrote_non_calibrations (bool): True if non-calibration parameters were written to file, False otherwise.
        filename_non_calibrations (str): Name of  non-calibration file.
        """
        zip_file_path = self.zip_file_path()
        with ZipFile(zip_file_path, 'w') as zipf:
            # Add all intermediate parameter files
            for file_name in self.file_parameters:
                zipf.write(os_path.join(self.vehicle_dir, file_name), arcname=file_name)

            # Check for and add specific files if they exist
            specific_files = ["00_default.param", "apm.pdef.xml", "file_documentation.json"]
            for file_name in specific_files:
                file_path = os_path.join(self.vehicle_dir, file_name)
                if os_path.exists(file_path):
                    zipf.write(file_path, arcname=file_name)

            # Add the newly created summary files
            if wrote_complete:
                zipf.write(os_path.join(self.vehicle_dir, filename_complete), arcname=filename_complete)
            if wrote_read_only:
                zipf.write(os_path.join(self.vehicle_dir, filename_read_only), arcname=filename_read_only)
            if wrote_calibrations:
                zipf.write(os_path.join(self.vehicle_dir, filename_calibrations), arcname=filename_calibrations)
            if wrote_non_calibrations:
                zipf.write(os_path.join(self.vehicle_dir, filename_non_calibrations), arcname=filename_non_calibrations)

        logging_info("Intermediate parameter files and summary files zipped to %s", zip_file_path)
