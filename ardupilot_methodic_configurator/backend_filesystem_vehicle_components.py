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
from os import path as os_path
from os import walk as os_walk
from re import match as re_match
from typing import Any, Union

from jsonschema import ValidationError, validate, validators

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
                loaded_schema: dict[Any, Any] = json_load(file)

                # Validate the schema itself against the JSON Schema meta-schema
                try:
                    # Get the Draft7Validator class which has the META_SCHEMA property
                    validator_class = validators.Draft7Validator
                    meta_schema = validator_class.META_SCHEMA

                    # Validate the loaded schema against the meta-schema
                    validate(instance=loaded_schema, schema=meta_schema)
                    logging_debug(_("Schema file '%s' is valid."), schema_path)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logging_error(_("Schema file '%s' is not a valid JSON Schema: %s"), schema_path, str(e))

                self.schema = loaded_schema
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
        # Validate before saving
        # commented out until https://github.com/ArduPilot/MethodicConfigurator/pull/237 gets merged
        # is_valid, error_message = self.validate_vehicle_components(data)
        # if not is_valid:
        #     msg = _("Cannot save invalid vehicle components data: {}").format(error_message)
        #     logging_error(msg)
        #     return True, msg

        filepath = os_path.join(vehicle_dir, self.vehicle_components_json_filename)
        try:
            with open(filepath, "w", encoding="utf-8", newline="\n") as file:
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

    def get_component_property_description(self, path: tuple[str, ...]) -> tuple[str, bool]:
        """
        Get description and optional status from schema using a component path.

        Args:
            path (tuple): The path to the component in the JSON data.

        Returns:
            tuple[str, bool]: A tuple containing (description, is_optional),
                            where is_optional defaults to False if not specified.

        """
        if not path or len(path) == 0:
            return ("", False)

        try:
            # Start with the Components node since all our editable items are under it
            current = self.schema.get("properties", {}).get("Components", {})  # type: ignore[union-attr]

            # Handle different path scenarios
            if len(path) == 1:
                return self._get_top_level_component_description(current, path[0])
            if len(path) == 3 and path[1] == "Product":
                return self._get_product_field_description(path[2])
            return self._get_nested_property_description(current, path)
        except Exception as _e:  # pylint: disable=broad-exception-caught
            msg = _("Exception occurred in get_component_property_description: {}").format(str(_e))
            logging_error(msg)
            return ("", False)

    def _get_top_level_component_description(self, current_schema: dict[str, Any], component_type: str) -> tuple[str, bool]:
        """Get description for top-level components like 'Flight Controller'."""
        if component_type in current_schema.get("properties", {}):
            description = current_schema["properties"][component_type].get("description", "")
            is_optional = current_schema["properties"][component_type].get("x-is-optional", False)
            return (description, is_optional)
        return ("", False)

    def _get_product_field_description(self, field_name: str) -> tuple[str, bool]:
        """Get description for product fields (Manufacturer, Model, etc.)."""
        product_def = self.schema.get("definitions", {}).get("product", {})  # type: ignore[union-attr]
        if "properties" in product_def and field_name in product_def["properties"]:
            description = product_def["properties"][field_name].get("description", "")
            is_optional = product_def["properties"][field_name].get("x-is-optional", False)
            return (description, is_optional)
        return ("", False)

    def _get_nested_property_description(self, current_schema: dict[str, Any], path: tuple[str, ...]) -> tuple[str, bool]:
        """Get description for nested properties in the component structure."""
        # Get the component type (e.g., "Flight Controller")
        component_type = path[0]

        # Navigate to the specific component type
        if component_type in current_schema.get("properties", {}):
            current = current_schema["properties"][component_type]
        else:
            return ("", False)

        # Resolve reference if present
        current = self._resolve_schema_reference(current)

        # Handle requests for section fields (Product, Firmware, Specifications, etc.)
        if len(path) == 2:
            return self._get_section_field_description(current, path[1])

        # For deeper nested fields, navigate through the path
        return self._traverse_nested_path(current, path[1:])

    def _resolve_schema_reference(self, schema_obj: dict[str, Any]) -> dict[str, Any]:
        """Resolve a schema reference in the form of {"$ref": "#/path/to/definition"}."""
        if "$ref" in schema_obj:
            ref_path = schema_obj["$ref"].replace("#/", "").split("/")
            ref_obj = self.schema
            for ref_part in ref_path:
                ref_obj = ref_obj.get(ref_part, {})  # type: ignore[union-attr]
            return ref_obj  # type: ignore[return-value]
        return schema_obj

    def _get_section_field_description(self, current: dict[str, Any], section: str) -> tuple[str, bool]:
        """Get description for section fields like Product, Firmware, etc."""
        # First check in direct properties
        if "properties" in current and section in current["properties"]:
            description = current["properties"][section].get("description", "")
            is_optional = current["properties"][section].get("x-is-optional", False)
            return (description, is_optional)

        # Then check in allOf constructs
        if "allOf" in current:
            for allof_item in current["allOf"]:
                # Handle reference in allOf item
                if "$ref" in allof_item:
                    ref_obj = self._resolve_schema_reference(allof_item)

                    if "properties" in ref_obj and section in ref_obj["properties"]:
                        description = ref_obj["properties"][section].get("description", "")
                        is_optional = ref_obj["properties"][section].get("x-is-optional", False)
                        return (description, is_optional)

                # Direct properties check in this allOf item
                elif "properties" in allof_item and section in allof_item["properties"]:
                    description = allof_item["properties"][section].get("description", "")
                    is_optional = allof_item["properties"][section].get("x-is-optional", False)
                    return (description, is_optional)

        # If not found, return empty with default optional status
        return ("", False)

    def _traverse_nested_path(self, current: dict[str, Any], path_parts: tuple[str, ...]) -> tuple[str, bool]:
        """Traverse a nested path in the schema to find a property description."""
        for part in path_parts:
            found = False

            # Check strategies in order: direct properties, allOf, and references
            found, current = self._check_direct_properties(current, part)
            if not found:
                found, current = self._check_allof_constructs(current, part)
            if not found:
                found, current = self._check_references(current, part)

            # If not found after all checks, return empty
            if not found:
                return ("", False)

            # If we found a $ref in the current object, resolve it
            current = self._resolve_schema_reference(current)

        # Return the description and optional status of the final object
        description = current.get("description", "")
        is_optional = current.get("x-is-optional", False)
        return (description, is_optional)

    def _check_direct_properties(self, schema_obj: dict[str, Any], property_name: str) -> tuple[bool, dict]:
        """Check if property exists directly in schema's properties."""
        if "properties" in schema_obj and property_name in schema_obj["properties"]:
            return True, schema_obj["properties"][property_name]
        return False, schema_obj

    def _check_allof_constructs(self, schema_obj: dict[str, Any], property_name: str) -> tuple[bool, dict]:
        """Check if property exists in any allOf constructs."""
        if "allOf" in schema_obj:
            for allof_item in schema_obj["allOf"]:
                # Handle reference in allOf item
                if "$ref" in allof_item:
                    ref_obj = self._resolve_schema_reference(allof_item)

                    if "properties" in ref_obj and property_name in ref_obj["properties"]:
                        return True, ref_obj["properties"][property_name]

                # Direct check in this allOf item
                elif "properties" in allof_item and property_name in allof_item["properties"]:
                    return True, allof_item["properties"][property_name]

        return False, schema_obj

    def _check_references(self, schema_obj: dict[str, Any], property_name: str) -> tuple[bool, dict]:
        """Check if property exists in referenced schema object."""
        if "$ref" in schema_obj:
            ref_obj = self._resolve_schema_reference(schema_obj)

            # Look in the resolved reference direct properties
            if "properties" in ref_obj and property_name in ref_obj["properties"]:
                return True, ref_obj["properties"][property_name]

            # Look in allOf constructs in the reference
            if "allOf" in ref_obj:
                for allof_item in ref_obj["allOf"]:
                    if "properties" in allof_item and property_name in allof_item["properties"]:
                        return True, allof_item["properties"][property_name]

        return False, schema_obj


def main() -> None:
    """Main function for standalone execution."""
    vehicle_components = VehicleComponents()
    vehicle_components.load_schema()

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
        desc, is_optional = vehicle_components.get_component_property_description(path)
        msg = f"Path: {path}\nDescription: {desc}, Optional: {is_optional}"
        logging_info(msg)
        logging_info("-" * 50)


if __name__ == "__main__":
    main()
