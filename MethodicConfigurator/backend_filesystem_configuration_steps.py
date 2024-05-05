#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from os import path as os_path

# from sys import exit as sys_exit
# from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error

from json import load as json_load
from json import JSONDecodeError


class ConfigurationSteps:
    """
    A class to manage configuration steps for the ArduPilot methodic configurator.

    This class provides methods for reading and validating configuration steps, including forced and derived parameters.
    It is designed to simplify the interaction with configuration steps for managing ArduPilot configuration files.

    Attributes:
        configuration_steps_filename (str): The name of the file containing documentation for the configuration files.
        configuration_steps (dict): A dictionary containing the configuration steps.
    """
    def __init__(self, vehicle_dir: str, vehicle_type: str):
        self.configuration_steps_filename = vehicle_type + "_configuration_steps.json"
        self.configuration_steps = {}

        # Define a list of directories to search for the configuration_steps_filename file
        search_directories = [vehicle_dir, os_path.dirname(os_path.abspath(__file__))]
        file_found = False
        for i, directory in enumerate(search_directories):
            try:
                with open(os_path.join(directory, self.configuration_steps_filename), 'r', encoding='utf-8') as file:
                    self.configuration_steps = json_load(file)
                    file_found = True
                    if i == 0:
                        logging_warning("Configuration steps '%s' loaded from %s (overwriting default configuration steps).",
                                         self.configuration_steps_filename, directory)
                    if i == 1:
                        logging_info("Configuration steps '%s' loaded from %s.", self.configuration_steps_filename, directory)
                    break
            except FileNotFoundError:
                pass
            except JSONDecodeError as e:
                logging_error("Error in file '%s': %s", self.configuration_steps_filename, e)
                break
        if file_found:
            self.__validate_forced_parameters_in_configuration_steps()
            self.__validate_derived_parameters_in_configuration_steps()
        else:
            logging_warning("No configuration steps documentation and no forced and derived parameters will be available.")


    def __validate_forced_parameters_in_configuration_steps(self):
        """
        Validates the forced parameters in the configuration steps.

        This method checks if the forced parameters in the configuration steps are correctly formatted.
        If a forced parameter is missing the 'New Value' or 'Change Reason' attribute, an error message is logged.
        """
        for filename, file_info in self.configuration_steps.items():
            if 'forced_parameters' in file_info:
                if not isinstance(file_info['forced_parameters'], dict):
                    logging_error("Error in file '%s': '%s' forced parameter is not a dictionary",
                                        self.configuration_steps_filename, filename)
                    continue
                for parameter, parameter_info in file_info['forced_parameters'].items():
                    if "New Value" not in parameter_info:
                        logging_error("Error in file '%s': '%s' forced parameter '%s'"
                                          " 'New Value' attribute not found.",
                                          self.configuration_steps_filename, filename, parameter)
                    if "Change Reason" not in parameter_info:
                        logging_error("Error in file '%s': '%s' forced parameter '%s'"
                                          " 'Change Reason' attribute not found.",
                                          self.configuration_steps_filename, filename, parameter)

    def __validate_derived_parameters_in_configuration_steps(self):
        """
        Validates the derived parameters in the configuration steps.

        This method checks if the derived parameters in the configuration steps are correctly formatted.
        If a derived parameter is missing the 'New Value' or 'Change Reason' attribute, an error message is logged.
        """
        for filename, file_info in self.configuration_steps.items():
            if 'derived_parameters' in file_info:
                if not isinstance(file_info['derived_parameters'], dict):
                    logging_error("Error in file '%s': '%s' derived parameter is not a dictionary",
                                        self.configuration_steps_filename, filename)
                    continue
                for parameter, parameter_info in file_info['derived_parameters'].items():
                    if "New Value" not in parameter_info:
                        logging_error("Error in file '%s': '%s' derived parameter '%s'"
                                          " 'New Value' attribute not found.",
                                          self.configuration_steps_filename, filename, parameter)
                    if "Change Reason" not in parameter_info:
                        logging_error("Error in file '%s': '%s' derived parameter '%s'"
                                          " 'Change Reason' attribute not found.",
                                          self.configuration_steps_filename, filename, parameter)

    def auto_changed_by(self, selected_file: str):
        if selected_file in self.configuration_steps:
            return self.configuration_steps[selected_file].get('auto_changed_by', '')
        return ''

    def get_documentation_text_and_url(self, selected_file, text_key, url_key):
        documentation = self.configuration_steps.get(selected_file, {}) if \
            self.configuration_steps else None
        if documentation is None:
            text = f"File '{self.configuration_steps_filename}' not found. " \
                "No intermediate parameter configuration steps available"
            url = None
        else:
            text = documentation.get(text_key, f"No documentation available for {selected_file} in the "
                                     f"{self.configuration_steps_filename} file")
            url = documentation.get(url_key, None)
        return text, url
