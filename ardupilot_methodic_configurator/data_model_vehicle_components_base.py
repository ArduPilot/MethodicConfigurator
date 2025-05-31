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

# Type aliases to improve code readability
ComponentPath = tuple[str, ...]
ComponentData = dict[str, Any]
ComponentValue = Union[str, int, float]
ValidationRulePath = tuple[str, str, str]  # Exactly 3 elements for validation rules


class ComponentDataModelBase:
    """
    A class to handle component data operations separate from UI logic.

    This improves testability by isolating data operations.
    """

    def __init__(self, initial_data: ComponentData, component_datatypes: dict[str, Any]) -> None:
        self._data: ComponentData = initial_data if initial_data else {"Components": {}, "Format version": 1}
        self._battery_chemistry: str = ""
        self._possible_choices: dict[ValidationRulePath, tuple[str, ...]] = {}
        self._mot_pwm_types: tuple[str, ...] = ()
        self._component_datatypes: dict[str, Any] = component_datatypes

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

    def update_json_structure(self) -> None:  # pylint: disable=too-many-branches
        """
        Update the data structure to ensure all required fields are present.

        Used to update old JSON files to the latest format.
        """
        # Get current data
        data = self._data

        # Ensure the format version is set.
        if "Format version" not in data:
            data["Format version"] = 1

        # To update old JSON files that do not have these new fields
        if "Components" not in data:
            data["Components"] = {}

        if "Battery" not in data["Components"]:
            data["Components"]["Battery"] = {}

        if "Specifications" not in data["Components"]["Battery"]:
            data["Components"]["Battery"]["Specifications"] = {}

        if "Chemistry" not in data["Components"]["Battery"]["Specifications"]:
            data["Components"]["Battery"]["Specifications"]["Chemistry"] = "Lipo"

        if "Capacity mAh" not in data["Components"]["Battery"]["Specifications"]:
            data["Components"]["Battery"]["Specifications"]["Capacity mAh"] = 0

        # To update old JSON files that do not have these new "Frame.Specifications.TOW * Kg" fields
        if "Frame" not in data["Components"]:
            data["Components"]["Frame"] = {}

        if "Specifications" not in data["Components"]["Frame"]:
            data["Components"]["Frame"]["Specifications"] = {}

        if "TOW min Kg" not in data["Components"]["Frame"]["Specifications"]:
            data["Components"]["Frame"]["Specifications"]["TOW min Kg"] = 1

        if "TOW max Kg" not in data["Components"]["Frame"]["Specifications"]:
            data["Components"]["Frame"]["Specifications"]["TOW max Kg"] = 1

        # Older versions used receiver instead of Receiver, rename it for consistency with other fields
        if "GNSS receiver" in data["Components"]:
            data["Components"]["GNSS Receiver"] = data["Components"].pop("GNSS receiver")

        data["Program version"] = __version__

        # To update old JSON files that do not have this new "Flight Controller.Specifications.MCU Series" field
        if "Flight Controller" not in data["Components"]:
            data["Components"]["Flight Controller"] = {}

        if "Specifications" not in data["Components"]["Flight Controller"]:
            fc_data = data["Components"]["Flight Controller"]
            data["Components"]["Flight Controller"] = {
                "Product": fc_data.get("Product", {}),
                "Firmware": fc_data.get("Firmware", {}),
                "Specifications": {"MCU Series": "Unknown"},
                "Notes": fc_data.get("Notes", ""),
            }

        self._data = data

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

    def get_combobox_values_for_path(self, path: ValidationRulePath) -> tuple[str, ...]:
        """Get valid combobox values for a given path."""
        return self._possible_choices.get(path, ())
