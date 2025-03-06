"""
Manages vehicle components at the filesystem level.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

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

from jsonschema import ValidationError, validate

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
        self.vehicle_components_schema_filename = "vehicle_components_schema.json"
        self.vehicle_components: Union[None, dict[Any, Any]] = None
        self.schema: Union[None, dict[Any, Any]] = None

    def load_schema(self) -> dict:
        """
        Load the JSON schema for vehicle components.

        :return: The schema as a dictionary
        """
        if self.schema is not None:
            return self.schema

        # Determine the location of the schema file
        schema_path = os_path.join(os_path.dirname(__file__), self.vehicle_components_schema_filename)

        try:
            with open(schema_path, encoding="utf-8") as file:
                self.schema = json_load(file)
            return self.schema
        except FileNotFoundError:
            logging_error(_("Schema file '%s' not found."), schema_path)
        except JSONDecodeError:
            logging_error(_("Error decoding JSON schema from file '%s'."), schema_path)
        return {}

    def validate_vehicle_components(self, data: dict) -> tuple[bool, str]:
        """
        Validate vehicle components data against the schema.

        :param data: The vehicle components data to validate
        :return: A tuple of (is_valid, error_message)
        """
        schema = self.load_schema()
        if not schema:
            return False, _("Could not load validation schema")

        try:
            validate(instance=data, schema=schema)
            return True, ""
        except ValidationError as e:
            return False, f"{_('Validation error')}: {e.message}"

    def load_vehicle_components_json_data(self, vehicle_dir: str) -> dict[Any, Any]:
        data: dict[Any, Any] = {}
        filepath = os_path.join(vehicle_dir, self.vehicle_components_json_filename)
        try:
            with open(filepath, encoding="utf-8") as file:
                data = json_load(file)

            # Validate the loaded data against the schema
            is_valid, error_message = self.validate_vehicle_components(data)
            if not is_valid:
                logging_error(_("Invalid vehicle components file '%s': %s"), filepath, error_message)
                # We still return the data even if invalid for debugging purposes
        except FileNotFoundError:
            # Normal users do not need this information
            logging_debug(_("File '%s' not found in %s."), self.vehicle_components_json_filename, vehicle_dir)
        except JSONDecodeError:
            logging_error(_("Error decoding JSON data from file '%s'."), filepath)
        self.vehicle_components = data
        return data

    def save_vehicle_components_json_data(self, data: dict, vehicle_dir: str) -> tuple[bool, str]:  # noqa: PLR0911 # pylint: disable=too-many-return-statements
        """
        Save the vehicle components data to a JSON file.

        :param data: The vehicle components data to save
        :param vehicle_dir: The directory to save the file in
        :return: A tuple of (error_occurred, error_message)
        """
        # Ensure all data matches schema types before validation
        data = self.ensure_data_types_match_schema(data)

        # Validate before saving
        is_valid, error_message = self.validate_vehicle_components(data)
        if not is_valid:
            msg = _("Cannot save invalid vehicle components data: {}").format(error_message)
            logging_error(msg)
            return True, msg

        filepath = os_path.join(vehicle_dir, self.vehicle_components_json_filename)
        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json_dump(data, file, indent=4)
        except FileNotFoundError:
            msg = _("Directory '{}' not found").format(vehicle_dir)
            logging_error(msg)
            return True, msg
        except PermissionError:
            msg = _("Permission denied when writing to file '{}'").format(filepath)
            logging_error(msg)
            return True, msg
        except IsADirectoryError:
            msg = _("Path '{}' is a directory, not a file").format(filepath)
            logging_error(msg)
            return True, msg
        except OSError as e:
            msg = _("OS error when writing to file '{}': {}").format(filepath, str(e))
            logging_error(msg)
            return True, msg
        except TypeError as e:
            msg = _("Type error when serializing data to JSON: {}").format(str(e))
            logging_error(msg)
            return True, msg
        except ValueError as e:
            msg = _("Value error when serializing data to JSON: {}").format(str(e))
            logging_error(msg)
            return True, msg
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Still have a fallback for truly unexpected errors
            msg = _("Unexpected error saving data to file '{}': {}").format(filepath, str(e))
            logging_error(msg)
            return True, msg

        return False, ""

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
    def supported_vehicles() -> tuple[str, ...]:
        return ("AP_Periph", "AntennaTracker", "ArduCopter", "ArduPlane", "ArduSub", "Blimp", "Heli", "Rover", "SITL")

    @staticmethod
    def get_vehicle_components_overviews() -> dict[str, TemplateOverview]:
        """
        Finds all subdirectories of the templates base directory containing a
        "vehicle_components.json" file, creates a dictionary where the keys are
        the subdirectory names (relative to templates base directory) and the
        values are instances of TemplateOverview.

        :return: A dictionary mapping subdirectory paths to TemplateOverview instances.
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
        if self.vehicle_components is not None:
            self._recursively_clear_dict(self.vehicle_components)

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
            elif isinstance(value, (int, float)):
                # For numerical values, set to 0
                data[key] = 0 if isinstance(value, int) else 0.0
            elif isinstance(value, bool):
                # For boolean values, set to False
                data[key] = False
            else:
                # For strings and other types, set to empty string or None
                data[key] = "" if isinstance(value, str) else None

    def ensure_data_types_match_schema(self, data: dict) -> dict:  # noqa: PLR0915
        """
        Process the data dictionary to ensure all values match the expected types in the schema.
        This method converts values to the correct types as defined in the schema.

        :param data: The vehicle components data to process
        :return: The processed data with corrected types
        """
        # Make sure schema is loaded
        if self.schema is None:
            self.load_schema()

        if not self.schema:
            logging_error(_("Could not load schema for type validation"))
            return data

        # Create a deep copy of data to avoid modifying it during iteration
        import copy

        processed_data = copy.deepcopy(data)

        def process_object(obj_data: dict, schema_props: dict, path: str = "") -> None:
            """Recursively process an object against schema properties."""
            for prop_name, prop_value in list(obj_data.items()):  # Use list() to allow modification during iteration
                current_path = f"{path}.{prop_name}" if path else prop_name

                if prop_name not in schema_props:
                    continue

                prop_schema = schema_props[prop_name]

                # Handle nested objects
                if prop_schema.get("type") == "object" and isinstance(prop_value, dict):
                    if "properties" in prop_schema:
                        process_object(obj_data[prop_name], prop_schema["properties"], current_path)

                # Handle arrays
                elif prop_schema.get("type") == "array" and isinstance(prop_value, list):
                    if "items" in prop_schema and prop_schema["items"].get("type") == "object":
                        for i, item in enumerate(prop_value):
                            if isinstance(item, dict) and "properties" in prop_schema["items"]:
                                item_path = f"{current_path}[{i}]"
                                process_object(item, prop_schema["items"]["properties"], item_path)

                # Handle string conversions
                elif prop_schema.get("type") == "string" and prop_value is not None:
                    if not isinstance(prop_value, str):
                        logging_debug(
                            _("Converting %s from %s to string: %s"), current_path, type(prop_value).__name__, prop_value
                        )
                        obj_data[prop_name] = str(prop_value)

                # Handle number conversions
                elif prop_schema.get("type") == "number" and prop_value is not None:
                    if not isinstance(prop_value, (int, float)) or isinstance(prop_value, bool):  # bool is a subclass of int
                        try:
                            obj_data[prop_name] = float(prop_value)
                            logging_debug(_("Converting %s to number: %s"), current_path, prop_value)
                        except (ValueError, TypeError):
                            logging_error(_("Failed to convert %s to number: %s"), current_path, prop_value)
                            obj_data[prop_name] = 0.0  # Default to 0.0 on conversion failure

                # Handle integer conversions
                elif prop_schema.get("type") == "integer" and prop_value is not None:
                    if not isinstance(prop_value, int) or isinstance(prop_value, bool):  # Handle bool separately
                        try:
                            if isinstance(prop_value, bool):
                                obj_data[prop_name] = 1 if prop_value else 0
                            else:
                                obj_data[prop_name] = int(float(prop_value))
                            logging_debug(_("Converting %s to integer: %s"), current_path, prop_value)
                        except (ValueError, TypeError):
                            logging_error(_("Failed to convert %s to integer: %s"), current_path, prop_value)
                            obj_data[prop_name] = 0  # Default to 0 on conversion failure

                # Handle boolean conversions
                elif prop_schema.get("type") == "boolean" and prop_value is not None and not isinstance(prop_value, bool):
                    if isinstance(prop_value, str):
                        obj_data[prop_name] = prop_value.lower() in ("true", "yes", "y", "1", "on")
                    elif isinstance(prop_value, (int, float)):
                        # 0 is False, any other number is True
                        obj_data[prop_name] = bool(prop_value)
                    else:
                        obj_data[prop_name] = bool(prop_value)
                    logging_debug(_("Converting %s to boolean: %s → %s"), current_path, prop_value, obj_data[prop_name])

        # Start processing from the root object
        if "properties" in self.schema:
            process_object(processed_data, self.schema["properties"])

        return processed_data
