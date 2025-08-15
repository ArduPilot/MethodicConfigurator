"""
Manages vehicle components at the filesystem level.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json import JSONDecodeError
from json import dump as json_dump
from json import load as json_load

# from logging import warning as logging_warning
# from sys import exit as sys_exit
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from os import makedirs as os_makedirs
from os import path as os_path
from os import walk as os_walk
from re import match as re_match
from typing import Any, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.data_model_template_overview import TemplateOverview
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema


class VehicleComponents:
    """Load and save vehicle components configurations from a JSON file."""

    def __init__(self, save_component_to_system_templates: bool = False) -> None:
        self.vehicle_components_fs: FilesystemJSONWithSchema = FilesystemJSONWithSchema(
            "vehicle_components.json", "vehicle_components_schema.json"
        )
        self.save_component_to_system_templates = save_component_to_system_templates

    def load_schema(self) -> dict:
        """
        Load the JSON schema for vehicle components.

        :return: The schema as a dictionary
        """
        return self.vehicle_components_fs.load_schema()

    def load_component_templates(self) -> dict[str, list[dict]]:
        """
        Load component templates from both system and user templates directories.

        User templates take precedence over system templates.

        :return: The merged templates as a dictionary
        """
        # Load system templates (read-only, comes with software)
        system_templates = self._load_system_templates()

        # Load user templates (user-editable)
        user_templates = self._load_user_templates()

        # Merge templates, with user templates taking precedence
        merged_templates = system_templates.copy()
        for component_name, templates in user_templates.items():
            if component_name not in merged_templates:
                merged_templates[component_name] = []

            # Add each user template, replacing system templates with the same name
            for user_template in templates:
                template_name = user_template.get("name")
                if template_name:
                    # Add a flag to mark this as a user template
                    user_template["is_user_modified"] = True

                    # Find index of system template with same name, if any
                    replaced = False
                    for i, template in enumerate(merged_templates.get(component_name, [])):
                        if template.get("name") == template_name:
                            merged_templates[component_name][i] = user_template
                            replaced = True
                            break

                    if not replaced:
                        merged_templates.setdefault(component_name, []).append(user_template)

        return merged_templates

    def _load_system_templates(self) -> dict[str, list[dict]]:
        """
        Load system component templates.

        :return: The system component templates as a dictionary
        """
        templates_filename = "system_vehicle_components_template.json"
        templates_dir = ProgramSettings.get_templates_base_dir()
        filepath = os_path.join(templates_dir, templates_filename)

        templates = {}
        try:
            with open(filepath, encoding="utf-8") as file:
                templates = json_load(file)
        except FileNotFoundError:
            logging_debug(_("System component templates file '%s' not found."), filepath)
        except JSONDecodeError:
            logging_error(_("Error decoding JSON system component templates from file '%s'."), filepath)
        return templates

    def _load_user_templates(self) -> dict[str, list[dict]]:
        """
        Load user component templates.

        :return: The user component templates as a dictionary
        """
        templates_filename = "user_vehicle_components_template.json"
        templates_dir = ProgramSettings.get_templates_base_dir()
        filepath = os_path.join(templates_dir, templates_filename)

        templates = {}
        try:
            with open(filepath, encoding="utf-8") as file:
                templates = json_load(file)
        except FileNotFoundError:
            logging_debug(_("User component templates file '%s' not found."), filepath)
        except JSONDecodeError:
            logging_error(_("Error decoding JSON user component templates from file '%s'."), filepath)
        return templates

    def save_component_templates(self, templates: dict) -> tuple[bool, str]:  # pylint: disable=too-many-branches
        """
        Save component templates.

        For user templates: Only save templates that are user-modified or not present in system templates.
        For system templates: Merge with existing system templates, adding new ones.

        :param templates: The templates to save
        :return: A tuple of (error_occurred, error_message)
        """
        # Load system templates to compare against
        system_templates = self._load_system_templates()

        # Determine which templates need to be saved to user file
        templates_to_save: dict[str, list[dict[str, Any]]] = {}

        if self.save_component_to_system_templates:
            # For system templates, start with existing system templates
            templates_to_save = system_templates.copy()

            # Then add new templates that don't exist yet
            for component_name, component_templates in templates.items():
                if component_name not in templates_to_save:
                    templates_to_save[component_name] = []

                # Create a mapping of existing template names for this component
                existing_template_names = {t.get("name"): True for t in templates_to_save[component_name]}

                for template in component_templates:
                    template_name = template.get("name")
                    if not template_name:
                        continue

                    # Only add if it doesn't exist in system templates yet
                    if template_name not in existing_template_names:
                        template_copy = template.copy()
                        if "is_user_modified" in template_copy:
                            del template_copy["is_user_modified"]
                        templates_to_save[component_name].append(template_copy)
                        existing_template_names[template_name] = True
        else:
            for component_name, component_templates in templates.items():
                templates_to_save[component_name] = []

                # Create a mapping of system template names for this component
                if component_name in system_templates:
                    system_template_names = {t.get("name"): t for t in system_templates.get(component_name, [])}
                else:
                    system_template_names = {}

                for template in component_templates:
                    template_name = template.get("name")
                    if not template_name:
                        continue

                    # If the template is marked as user-modified, save it
                    if template.get("is_user_modified", False):
                        # Remove the flag before saving
                        template_copy = template.copy()
                        if "is_user_modified" in template_copy:
                            del template_copy["is_user_modified"]
                        templates_to_save[component_name].append(template_copy)
                        continue

                    # If the template exists in system templates, check if it's different
                    if template_name in system_template_names:
                        system_template = system_template_names[template_name]

                        # Deep comparison of data section
                        if template.get("data") != system_template.get("data"):
                            # Template is modified from system version
                            template_copy = template.copy()
                            templates_to_save[component_name].append(template_copy)
                    else:
                        # Template doesn't exist in system templates, so it's user-added
                        templates_to_save[component_name].append(template.copy())

                # Remove empty component entries
                if not templates_to_save[component_name]:
                    del templates_to_save[component_name]

        return self.save_component_templates_to_file(templates_to_save)

    def save_component_templates_to_file(self, templates_to_save: dict[str, list[dict[str, Any]]]) -> tuple[bool, str]:
        if self.save_component_to_system_templates:
            # Save to system templates file
            templates_filename = "system_vehicle_components_template.json"
        else:
            # Save to user templates file
            templates_filename = "user_vehicle_components_template.json"
        templates_dir = ProgramSettings.get_templates_base_dir()

        # Create the directory if it doesn't exist
        try:
            os_makedirs(templates_dir, exist_ok=True)
        except Exception as e:  # pylint: disable=broad-exception-caught
            msg = _("Failed to create templates directory '{}': {}").format(templates_dir, str(e))
            logging_error(msg)
            return True, msg

        # Now create the file path and write to it
        filepath = os_path.join(templates_dir, templates_filename)

        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json_dump(templates_to_save, file, indent=4)
            return False, ""  # Success
        except FileNotFoundError:
            msg = _("File not found when writing to '{}': {}").format(filepath, _("Path not found"))
            logging_error(msg)
        except PermissionError:
            msg = _("Permission denied when writing to file '{}'").format(filepath)
            logging_error(msg)
        except OSError as e:
            msg = _("OS error when writing to file '{}': {}").format(filepath, str(e))
            logging_error(msg)
        except Exception as e:  # pylint: disable=broad-exception-caught
            msg = _("Unexpected error saving templates to file '{}': {}").format(filepath, str(e))
            logging_error(msg)
        return True, msg

    def validate_vehicle_components(self, data: dict) -> tuple[bool, str]:
        """
        Validate vehicle components data against the schema.

        :param data: The vehicle components data to validate
        :return: A tuple of (is_valid, error_message)
        """
        return self.vehicle_components_fs.validate_json_against_schema(data)

    def load_vehicle_components_json_data(self, vehicle_dir: str) -> dict[Any, Any]:
        return self.vehicle_components_fs.load_json_data(vehicle_dir)

    def save_vehicle_components_json_data(self, data: dict, vehicle_dir: str) -> tuple[bool, str]:
        """
        Save the vehicle components data to a JSON file.

        :param data: The vehicle components data to save
        :param vehicle_dir: The directory to save the file in
        :return: A tuple of (error_occurred, error_message)
        """
        return self.vehicle_components_fs.save_json_data(data, vehicle_dir)

    def get_fc_fw_type_from_vehicle_components_json(self) -> str:
        data = self.vehicle_components_fs.data
        components = data["Components"] if data and "Components" in data else None
        if components:
            fw_type: str = components.get("Flight Controller", {}).get("Firmware", {}).get("Type", "")
            if fw_type in self.supported_vehicles():
                return fw_type
            error_msg = _("Firmware type {fw_type} in {filename} is not supported")
            logging_error(error_msg.format(fw_type=fw_type, filename=self.vehicle_components_fs.json_filename))
        return ""

    def get_fc_fw_version_from_vehicle_components_json(self) -> str:
        data = self.vehicle_components_fs.data
        components = data["Components"] if data and "Components" in data else None
        if components:
            version_str: str = components.get("Flight Controller", {}).get("Firmware", {}).get("Version", "")
            version_str = version_str.lstrip().split(" ")[0] if version_str else ""
            if re_match(r"^\d+\.\d+\.\d+$", version_str):
                return version_str
            error_msg = _("FW version string {version_str} on {filename} is invalid")
            logging_error(error_msg.format(version_str=version_str, filename=self.vehicle_components_fs.json_filename))
        return ""

    @staticmethod
    def supported_vehicles() -> tuple[str, ...]:
        return ("AP_Periph", "AntennaTracker", "ArduCopter", "ArduPlane", "ArduSub", "Blimp", "Heli", "Rover", "SITL")

    @staticmethod
    def get_vehicle_components_overviews() -> dict[str, TemplateOverview]:
        """
        Finds all subdirectories of the templates base directory containing a "vehicle_components.json" file.

        Creates a dictionary where the keys are
        the subdirectory names (relative to templates base directory) and the
        values are instances of TemplateOverview.

        :return: A dictionary mapping subdirectory paths to TemplateOverview instances.
        """
        vehicle_components_dict = {}
        file_to_find = VehicleComponents().vehicle_components_fs.json_filename
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

    @staticmethod
    def get_vehicle_image_filepath(relative_template_path: str) -> str:
        template_default_dir = ProgramSettings.get_templates_base_dir()
        return os_path.join(template_default_dir, relative_template_path, "vehicle.jpg")

    def wipe_component_info(self) -> None:
        """
        Wipe the vehicle components data by clearing all data from the vehicle_components dictionary.

        This resets the internal state without affecting any files.
        Preserves the complete structure of the dictionary including all branches and leaves,
        but sets leaf values to empty values based on their type.
        """
        data = self.vehicle_components_fs.data
        if data is not None:
            self._recursively_clear_dict(data)
            default_data = {
                "RC Receiver": {
                    "FC Connection": {"Type": "RCin/SBUS", "Protocol": "All"},
                },
                "Telemetry": {
                    "FC Connection": {"Type": "SERIAL1", "Protocol": "MAVLink2"},
                },
                "Battery Monitor": {
                    "FC Connection": {"Type": "Analog", "Protocol": "Analog Voltage and Current"},
                },
                "Battery": {
                    "Specifications": {
                        "Chemistry": "Lipo",
                        "Volt per cell max": 4.2,
                        "Volt per cell low": 3.6,
                        "Volt per cell crit": 3.55,
                    },
                },
                "ESC": {
                    "FC Connection": {"Type": "Main Out", "Protocol": "Normal"},
                },
                "Motors": {
                    "Specifications": {"Poles": 14},
                },
                "GNSS Receiver": {
                    "FC Connection": {"Type": "SERIAL3", "Protocol": "AUTO"},
                },
            }

            def merge_defaults(target: dict, defaults: dict) -> None:
                for key, default_value in defaults.items():
                    if key not in target or not target[key]:
                        target[key] = default_value
                    elif isinstance(default_value, dict) and isinstance(target[key], dict):
                        merge_defaults(target[key], default_value)

            merge_defaults(data["Components"], default_data)

    def _recursively_clear_dict(self, data: Union[dict, list, float, bool, str]) -> None:
        """
        Recursively clear leaf values in a nested dictionary while preserving structure.

        :param data: Dictionary to clear
        """
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            if isinstance(value, dict):
                # If it's a dictionary, recurse deeper
                self._recursively_clear_dict(value)
            elif isinstance(value, list):
                # If it's a list, preserve it but empty it
                data[key] = []
            elif isinstance(value, bool):
                data[key] = False
            elif isinstance(value, int):
                data[key] = 0
            elif isinstance(value, float):
                data[key] = 0.0
            elif isinstance(value, str):
                data[key] = ""
            else:
                data[key] = None


def main() -> None:
    """Main function for standalone execution."""
    vehicle_components = VehicleComponents()
    schema = VehicleComponentsJsonSchema(vehicle_components.load_schema())

    component_property_paths = [
        ("Flight Controller", "Product", "Manufacturer"),
        ("Flight Controller", "Product", "Model"),
        ("Flight Controller", "Product", "URL"),
        ("Flight Controller", "Product", "Version"),
        ("Flight Controller", "Firmware", "Type"),
        ("Flight Controller", "Firmware", "Version"),
        ("Flight Controller", "Specifications", "MCU Series"),
        ("Flight Controller", "Notes"),
        ("Flight Controller",),
        ("Flight Controller", "Product"),
        ("Flight Controller", "Firmware"),
        ("Flight Controller", "Specifications"),
        ("Frame",),
        ("Frame", "Product"),
        ("Frame", "Specifications"),
        ("Frame", "Product", "Manufacturer"),
        ("Frame", "Product", "Model"),
        ("Frame", "Product", "URL"),
        ("Frame", "Product", "Version"),
        ("Frame", "Specifications", "TOW min Kg"),
        ("Frame", "Specifications", "TOW max Kg"),
        ("Frame", "Notes"),
    ]

    logging_info("\nTesting description lookup for sample paths:")
    logging_info("=============================================")

    for path in component_property_paths:
        desc, is_optional = schema.get_component_property_description(path)
        msg = f"Path: {path}\nDescription: {desc}, Optional: {is_optional}"
        logging_info(msg)
        logging_info("-" * 50)


if __name__ == "__main__":
    main()
