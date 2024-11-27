"""
Manages vehicle components at the filesystem level.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json import JSONDecodeError
from json import dump as json_dump
from json import load as json_load

# from logging import info as logging_info
# from logging import warning as logging_warning
# from sys import exit as sys_exit
from logging import debug as logging_debug
from logging import error as logging_error
from os import path as os_path
from os import walk as os_walk
from re import match as re_match
from typing import Any, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.middleware_template_overview import TemplateOverview


class VehicleComponents:
    """
    This class provides methods to load and save
    vehicle components configurations from a JSON file.
    """

    def __init__(self) -> None:
        self.vehicle_components_json_filename = "vehicle_components.json"
        self.vehicle_components: Union[None, dict[Any, Any]] = None

    def load_vehicle_components_json_data(self, vehicle_dir: str) -> dict[Any, Any]:
        data = {}
        filepath = os_path.join(vehicle_dir, self.vehicle_components_json_filename)
        try:
            with open(filepath, encoding="utf-8") as file:
                data = json_load(file)
        except FileNotFoundError:
            # Normal users do not need this information
            logging_debug(_("File '%s' not found in %s."), self.vehicle_components_json_filename, vehicle_dir)
        except JSONDecodeError:
            logging_error(_("Error decoding JSON data from file '%s'."), filepath)
        self.vehicle_components = data
        return data

    def save_vehicle_components_json_data(self, data: dict, vehicle_dir: str) -> bool:
        filepath = os_path.join(vehicle_dir, self.vehicle_components_json_filename)
        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json_dump(data, file, indent=4)
        except Exception as e:  # pylint: disable=broad-except
            logging_error(_("Error saving JSON data to file '%s': %s"), filepath, e)
            return True
        return False

    def get_fc_fw_type_from_vehicle_components_json(self) -> str:
        if self.vehicle_components and "Components" in self.vehicle_components:
            components = self.vehicle_components["Components"]
        else:
            components = None
        if components:
            fw_type: str = components.get("Flight Controller", {}).get("Firmware", {}).get("Type", "")
            if fw_type in self.supported_vehicles():
                return fw_type
            error_msg = _("Firmware type {fw_type} in {self.vehicle_components_json_filename} is not supported")
            logging_error(error_msg.format(**locals()))
        return ""

    def get_fc_fw_version_from_vehicle_components_json(self) -> str:
        if self.vehicle_components and "Components" in self.vehicle_components:
            components = self.vehicle_components["Components"]
        else:
            components = None
        if components:
            version_str: str = components.get("Flight Controller", {}).get("Firmware", {}).get("Version", "")
            version_str = version_str.lstrip().split(" ")[0] if version_str else ""
            if re_match(r"^\d+\.\d+\.\d+$", version_str):
                return version_str
            error_msg = _("FW version string {version_str} on {self.vehicle_components_json_filename} is invalid")
            logging_error(error_msg.format(**locals()))
        return ""

    @staticmethod
    def supported_vehicles() -> list[str]:
        return ["AP_Periph", "AntennaTracker", "ArduCopter", "ArduPlane", "ArduSub", "Blimp", "Heli", "Rover", "SITL"]

    @staticmethod
    def get_vehicle_components_overviews() -> dict[str, TemplateOverview]:
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
                    comp_data = comp_data.get("Components", {})
                    vehicle_components_overview = TemplateOverview(comp_data)
                    vehicle_components_dict[relative_path] = vehicle_components_overview

        return vehicle_components_dict
