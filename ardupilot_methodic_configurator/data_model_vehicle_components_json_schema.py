"""
Data model for vehicle components JSON schema.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import error as logging_error
from typing import Any

from ardupilot_methodic_configurator import _


class VehicleComponentsJsonSchema:
    """Vehicle components JSON schema Business logic."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    def get_all_value_datatypes(self) -> dict[str, Any]:
        """
        Get a dictionary of all value data types used in the vehicle_components_dict as defined in the schema.

        The keys are the vehicle_components_dict keys and their values are the actual Python datatype

        :return: A nested dictionary mapping data names to their Python datatypes.
        """
        value_datatypes: dict[str, Any] = {}

        # Start with the Components node since all our editable items are under it
        components_schema = self.schema.get("properties", {}).get("Components", {})
        if not components_schema:
            return {}

        # Traverse all component types (Flight Controller, Frame, etc.)
        for component_type, component_schema in components_schema.get("properties", {}).items():
            value_datatypes[component_type] = {}
            self._extract_datatypes_from_component(component_schema, value_datatypes[component_type])

        return value_datatypes

    def _extract_datatypes_from_component(self, component_schema: dict[str, Any], target_dict: dict[str, Any]) -> None:
        """Extract datatypes from a component schema recursively."""
        # Resolve reference if present
        resolved_schema = self._resolve_schema_reference(component_schema)

        # Check direct properties
        if "properties" in resolved_schema:
            for prop_name, prop_schema in resolved_schema["properties"].items():
                self._extract_datatypes_from_property(prop_schema, prop_name, target_dict)

        # Check allOf constructs
        if "allOf" in resolved_schema:
            for allof_item in resolved_schema["allOf"]:
                self._extract_datatypes_from_component(allof_item, target_dict)

    def _extract_datatypes_from_property(
        self, prop_schema: dict[str, Any], prop_name: str, target_dict: dict[str, Any]
    ) -> None:
        """Extract datatype from a property schema."""
        # Resolve reference if present
        resolved_schema = self._resolve_schema_reference(prop_schema)

        # If this property has nested properties, create a nested dict and recurse
        if "properties" in resolved_schema:
            target_dict[prop_name] = {}
            for nested_prop_name, nested_prop_schema in resolved_schema["properties"].items():
                self._extract_datatypes_from_property(nested_prop_schema, nested_prop_name, target_dict[prop_name])

        # Handle allOf constructs in properties
        elif "allOf" in resolved_schema:
            target_dict[prop_name] = {}
            for allof_item in resolved_schema["allOf"]:
                self._extract_datatypes_from_property(allof_item, prop_name, target_dict)

        # If this property has a direct type, convert to Python type and record it as a leaf value
        elif "type" in resolved_schema:
            target_dict[prop_name] = self._json_type_to_python_type(resolved_schema["type"])

        # If no type or properties found, create empty dict as placeholder
        else:
            target_dict[prop_name] = {}

    def _json_type_to_python_type(self, json_type: str) -> type:
        """
        Convert JSON Schema type string to actual Python type.

        :param json_type: JSON Schema type string
        :return: Corresponding Python type
        """
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        return type_mapping.get(json_type, str)  # Default to str if unknown type

    def modify_schema_for_mcu_series(self, is_optional: bool) -> None:
        """
        Modify the schema to set x-is-optional property for MCU Series field based on its value.

        Dynamically updates the schema to make the MCU Series field optional

        Args:
            is_optional: If it should be marked as optional

        """
        if not self.schema:  # Still None after loading
            logging_error(_("Cannot modify schema: Schema could not be loaded"))
            return

        # Navigate to the MCU Series field in the schema
        flight_controller_def = self.schema.get("definitions", {}).get("flightController", {})
        flight_controller_properties = None

        # Check in allOf construct
        if "allOf" in flight_controller_def:
            for item in flight_controller_def["allOf"]:
                if "properties" in item and "Specifications" in item["properties"]:
                    flight_controller_properties = item
                    break

        if not flight_controller_properties:
            logging_error(_("Could not find Specifications in flight controller schema"))
            return

        specifications = flight_controller_properties["properties"]["Specifications"]

        if "properties" in specifications and "MCU Series" in specifications["properties"]:
            try:
                mcu_series_field = specifications["properties"]["MCU Series"]

                if is_optional:
                    mcu_series_field["x-is-optional"] = True
                else:
                    # Remove x-is-optional if it exists
                    mcu_series_field.pop("x-is-optional", None)

                logging_debug(
                    _("Modified schema: MCU Series x-is-optional=%s to value=%u"),
                    mcu_series_field.get("x-is-optional", False),
                    is_optional,
                )
            except Exception as err:  # pylint: disable=broad-exception-caught
                logging_error(_("Error modifying schema for MCU Series: %s"), str(err))

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
            current = self.schema.get("properties", {}).get("Components", {})

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
        product_def = self.schema.get("definitions", {}).get("product", {})
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
                ref_obj = ref_obj.get(ref_part, {})
            return ref_obj
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
