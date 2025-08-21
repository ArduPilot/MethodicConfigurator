"""
Data model for vehicle components.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from logging import debug as logging_debug
from logging import error as logging_error
from logging import warning as logging_warning
from typing import Any, Optional, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# Type aliases to improve code readability
ComponentPath = tuple[str, ...]
ComponentData = dict[str, Any]
ComponentValue = Union[str, int, float]


class ComponentDataModelBase:
    """
    A class to handle component data operations separate from UI logic.

    This improves testability by isolating data operations.
    """

    def __init__(
        self, initial_data: ComponentData, component_datatypes: dict[str, Any], schema: VehicleComponentsJsonSchema
    ) -> None:
        self._data: ComponentData = initial_data if initial_data else {"Components": {}, "Format version": 1}
        self._battery_chemistry: str = ""
        self._possible_choices: dict[ComponentPath, tuple[str, ...]] = {}
        self._mot_pwm_types: tuple[str, ...] = ()
        self._component_datatypes: dict[str, Any] = component_datatypes
        self._is_new_project: bool = False
        self.schema: VehicleComponentsJsonSchema = schema

    def get_component_data(self) -> ComponentData:
        """
        Get the complete component data.

        Only used in pytest code
        """
        return self._data

    def get_component_value(self, path: ComponentPath) -> Union[ComponentData, ComponentValue]:
        """Get a specific component value from the data structure."""
        data_path = self._data["Components"]
        for key in path:
            if key not in data_path:
                empty_dict: dict[str, Any] = {}
                return empty_dict
            data_path = data_path[key]

        # Ensure we return a value that matches our ComponentValue type
        if isinstance(data_path, (str, int, float, dict)):
            return data_path
        # If it's some other type, convert to string
        return str(data_path)

    def set_component_value(self, path: ComponentPath, value: Union[ComponentData, ComponentValue, None]) -> None:
        """Set a specific component value in the data structure."""
        if value is None:
            value = ""

        # Ensure Components key exists
        if "Components" not in self._data:
            self._data["Components"] = {}
        data_path: ComponentData = self._data["Components"]

        # Navigate to the correct place in the data structure
        for key in path[:-1]:
            if key not in data_path:
                data_path[key] = {}
            data_path = data_path[key]

        # Update the value using type-safe casting
        datatype = self._get_component_datatype(path)
        if datatype:
            data_path[path[-1]] = self._safe_cast_value(value, datatype, path)
        else:  # fallback to a less intelligent method
            # If the component has a specific datatype, use it to process the value
            data_path[path[-1]] = self._process_value(path, str(value) if value is not None else None)

    def _get_component_datatype(self, path: ComponentPath) -> Optional[type]:
        """
        Safely get the Python datatype for a component path from the nested datatypes dictionary.

        Args:
            path: The component path tuple (e.g., ("Battery", "Specifications", "Capacity mAh"))

        Returns:
            The Python type if found, None otherwise

        """
        if not self._component_datatypes or len(path) < 3:
            return None

        try:
            component_type = path[0]
            section = path[1]
            field = path[2]

            result = self._component_datatypes.get(component_type, {}).get(section, {}).get(field)
            # Ensure we return a type or None
            return result if isinstance(result, type) else None
        except (KeyError, AttributeError, TypeError):
            return None

    def _safe_cast_value(  # noqa: PLR0911 pylint: disable=too-many-return-statements
        self, value: Union[ComponentData, ComponentValue, None], datatype: type, path: ComponentPath
    ) -> Any:  # noqa: ANN401 # Use Any to handle dict/list returns that don't fit ComponentValue
        """
        Safely cast a value to the specified datatype with proper error handling.

        Args:
            value: The value to cast
            datatype: The target Python type
            path: The component path for error context

        Returns:
            The cast value, or falls back to _process_value on error

        """
        if value is None:
            # Handle None values based on datatype
            if datatype is str:
                return ""
            if datatype in (int, float):
                return datatype(0)
            if datatype is bool:
                return False
            if datatype is list:
                return []
            if datatype is dict:
                return {}
            return ""

        # If already the correct type, return as-is
        if isinstance(value, datatype):
            return value

        try:
            # Special handling for boolean conversion
            if datatype is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "on")
                return bool(value)

            # Special handling for list/dict types
            if datatype in (list, dict):
                logging_error(_("Invalid datatype '%s' for path %s"), value, datatype.__name__, path)
                return ""

            # Standard type conversion
            return datatype(value)

        except (ValueError, TypeError, AttributeError) as e:
            # Log the error and fall back to the original processing method
            logging_warning(_("Failed to cast value '%s' to %s for path %s: %s"), value, datatype.__name__, path, e)
            return self._process_value(path, str(value) if value is not None else None)

    def _process_value(self, path: ComponentPath, value: Union[str, None]) -> ComponentValue:
        """Process a string value into the appropriate type based on context."""
        # Handle None value
        if value is None:
            return ""

        # Special handling for Version fields
        if path[-1] != "Version":
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return str(value).strip()
        return str(value).strip()

    def get_all_components(self) -> ComponentData:
        """Get all components data."""
        empty_dict: ComponentData = {}
        return self._data.get("Components", empty_dict)  # type: ignore[no-any-return]

    def has_components(self) -> bool:
        """Check if there are any components in the data."""
        return len(self.get_all_components()) >= 1

    def save_to_filesystem(self, filesystem: LocalFilesystem) -> tuple[bool, str]:
        """Save component data to filesystem - centralizes save logic."""
        return filesystem.save_vehicle_components_json_data(self.get_component_data(), filesystem.vehicle_dir)

    def post_init(self, doc_dict: dict) -> None:
        """Update the data structure to ensure all required fields are present."""
        self.update_json_structure()

        self.init_possible_choices(doc_dict)
        self.init_battery_chemistry()

    def update_json_structure(self) -> None:
        """
        Update the data structure to ensure all required fields are present.

        Used to update old JSON files to the latest format.
        """
        # Define the default structure with all required fields
        default_structure = {
            "Format version": 1,
            "Program version": __version__,
            "Components": {
                "Battery": {
                    "Specifications": {
                        "Chemistry": "Lipo",
                        "Capacity mAh": 0,
                    }
                },
                "Frame": {
                    "Specifications": {
                        "TOW min Kg": 1,
                        "TOW max Kg": 1,
                    }
                },
                "Flight Controller": {
                    "Product": {},
                    "Firmware": {},
                    "Specifications": {"MCU Series": "Unknown"},
                    "Notes": "",
                },
            },
        }

        # Handle legacy field renaming before merging
        if "GNSS receiver" in self._data.get("Components", {}):
            components = self._data.setdefault("Components", {})
            components["GNSS Receiver"] = components.pop("GNSS receiver")

        # Handle legacy battery monitor protocol migration for protocols that don't need hardware connections
        # This is a local import to avoid a circular import dependency
        from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (  # pylint: disable=import-outside-toplevel, cyclic-import # noqa: PLC0415
            BATT_MONITOR_CONNECTION,
            OTHER_PORTS,
        )

        # Calculate protocols that use OTHER_PORTS (don't require specific hardware connections)
        battmon_other_protocols = {
            str(value["protocol"]) for value in BATT_MONITOR_CONNECTION.values() if value.get("type") == OTHER_PORTS
        }
        battery_monitor_protocol = (
            self._data.get("Components", {}).get("Battery Monitor", {}).get("FC Connection", {}).get("Protocol")
        )
        if battery_monitor_protocol in battmon_other_protocols:
            # These protocols don't require specific hardware connections, so we can safely migrate them
            battery_monitor = self._data.setdefault("Components", {}).setdefault("Battery Monitor", {})
            battery_monitor.setdefault("FC Connection", {})["Type"] = "other"

        # Merge existing data onto default structure (preserves existing values)
        self._data = self._deep_merge_dicts(default_structure, self._data)
        self._data["Program version"] = __version__

    def _deep_merge_dicts(self, default: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge two dictionaries, preserving existing values and key order.

        Args:
            default: Default structure with fallback values
            existing: Existing data to preserve

        Returns:
            Merged dictionary with existing values taking precedence and preserving existing key order

        """
        # Start with existing dictionary to preserve its key order
        result = existing.copy()

        # Add any missing keys from the default structure
        for key, value in default.items():
            if key not in result:
                # Key doesn't exist in existing data, add it from default
                result[key] = value
            elif isinstance(result[key], dict) and isinstance(value, dict):
                # Both are dictionaries, recursively merge them
                result[key] = self._deep_merge_dicts(value, result[key])
            # If key exists in result but isn't a dict, keep the existing value (no change needed)

        return result

    def init_battery_chemistry(self) -> None:
        self._battery_chemistry = (
            self._data.get("Components", {}).get("Battery", {}).get("Specifications", {}).get("Chemistry", "")
        )
        if self._battery_chemistry not in BatteryCell.chemistries():
            logging_error(_("Invalid battery chemistry %s, defaulting to Lipo"), self._battery_chemistry)
            self._battery_chemistry = "Lipo"

    def init_possible_choices(self, doc_dict: dict[str, Any]) -> None:
        """Initialize possible choices for validation rules."""
        # this method should be implemented in the ComponentDataModelValidation mixedin

    def get_combobox_values_for_path(self, path: ComponentPath) -> tuple[str, ...]:
        """Get valid combobox values for a given path."""
        return self._possible_choices.get(path, ())

    def set_configuration_template(self, vehicle_template_name: str) -> None:
        """Set the vehicle configuration template name in the data."""
        self._data["Configuration template"] = vehicle_template_name
        self._is_new_project = True

    def is_new_project(self) -> bool:
        """Check if the project is new."""
        return self._is_new_project
