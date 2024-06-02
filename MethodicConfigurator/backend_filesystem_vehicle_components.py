#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

from os import path as os_path

# from sys import exit as sys_exit
# from logging import debug as logging_debug
#from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error

from json import load as json_load
from json import dump as json_dump
from json import JSONDecodeError


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
