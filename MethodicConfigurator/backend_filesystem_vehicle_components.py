#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

from os import path as os_path
from os import walk as os_walk

# from sys import exit as sys_exit
# from logging import debug as logging_debug
#from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error

from re import match as re_match

from json import load as json_load
from json import dump as json_dump
from json import JSONDecodeError

from MethodicConfigurator.backend_filesystem_program_settings import ProgramSettings

from MethodicConfigurator.middleware_template_overview import TemplateOverview


class VehicleComponents:
    """
    This class provides methods to load and save
    vehicle components configurations from a JSON file.
    """
    def __init__(self):
        self.vehicle_components_json_filename = "vehicle_components.json"
        self.vehicle_components = None

    def load_vehicle_components_json_data(self, vehicle_dir: str):
        data = {}
        try:
            filepath = os_path.join(vehicle_dir, self.vehicle_components_json_filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json_load(file)
        except FileNotFoundError:
            logging_warning("File '%s' not found in %s.", self.vehicle_components_json_filename, vehicle_dir)
        except JSONDecodeError:
            logging_error("Error decoding JSON data from file '%s'.", filepath)
        self.vehicle_components = data
        return data

    def save_vehicle_components_json_data(self, data, vehicle_dir: str) -> bool:
        filepath = os_path.join(vehicle_dir, self.vehicle_components_json_filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                json_dump(data, file, indent=4)
        except Exception as e:  # pylint: disable=broad-except
            logging_error("Error saving JSON data to file '%s': %s", filepath, e)
            return True
        return False

    def get_fc_fw_version_from_vehicle_components_json(self) -> str:
        if self.vehicle_components and 'Components' in self.vehicle_components:
            components = self.vehicle_components['Components']
        else:
            components = None
        if components:
            version_str = components.get('Flight Controller', {}).get('Firmware', {}).get('Version', '')
            version_str = version_str.lstrip().split(' ')[0] if version_str else ''
            if re_match(r'^\d+\.\d+\.\d+$', version_str):
                return version_str
            logging_error(f"FW version string {version_str} on {self.vehicle_components_json_filename} is invalid")
        return None

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
        template_default_dir = ProgramSettings.get_templates_base_dir()
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
