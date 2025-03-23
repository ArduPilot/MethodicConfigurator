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

from jsonschema import ValidationError, validate, validators

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.middleware_template_overview import TemplateOverview


class VehicleComponents:
    """
    This class provides methods to load and save
    vehicle components configurations from a JSON file.
    """

    def __init__(self, save_component_to_system_templates: bool = False) -> None:
        self.vehicle_components_json_filename = "vehicle_components.json"
        self.vehicle_components_schema_filename = "vehicle_components_schema.json"
        self.vehicle_components: Union[None, dict[Any, Any]] = None
        self.schema: Union[None, dict[Any, Any]] = None
        self.save_component_to_system_templates = save_component_to_system_templates

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

    def _get_component_schema_property_description(self, component_info: dict[str, Any]) -> tuple[str, bool]:
        """Get description and optional status from a component schema property."""
        description = component_info.get("description", "")
        is_optional = component_info.get("x-is-optional", False)
        return (description, is_optional)

    def _get_top_level_component_description(self, current_schema: dict[str, Any], component_type: str) -> tuple[str, bool]:
        """Get description for top-level components like 'Flight Controller'."""
        if component_type in current_schema.get("properties", {}):
            return self._get_component_schema_property_description(current_schema["properties"][component_type])
        return ("", False)

    def _get_product_field_description(self, field_name: str) -> tuple[str, bool]:
        """Get description for product fields (Manufacturer, Model, etc.)."""
        product_def = self.schema.get("definitions", {}).get("product", {})  # type: ignore[union-attr]
        if "properties" in product_def and field_name in product_def["properties"]:
            return self._get_component_schema_property_description(product_def["properties"][field_name])
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
            return self._get_component_schema_property_description(current["properties"][section])

        # Then check in allOf constructs
        if "allOf" in current:
            for allof_item in current["allOf"]:
                # Handle reference in allOf item
                if "$ref" in allof_item:
                    ref_obj = self._resolve_schema_reference(allof_item)

                    if "properties" in ref_obj and section in ref_obj["properties"]:
                        return self._get_component_schema_property_description(ref_obj["properties"][section])

                # Direct properties check in this allOf item
                elif "properties" in allof_item and section in allof_item["properties"]:
                    return self._get_component_schema_property_description(allof_item["properties"][section])

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
        return self._get_component_schema_property_description(current)

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
