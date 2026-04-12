"""
Data model for vehicle components.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from logging import debug as logging_debug
from copy import deepcopy
from logging import error as logging_error
from logging import warning as logging_warning
from math import isnan, nan
from typing import Any, Optional, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.battery_cell_voltages import (
    BATTERY_CELL_VOLTAGE_TYPES,
    BATTERY_DEFAULT_CHEMISTRY,
    BatteryCell,
)
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
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
        self._data: ComponentData = deepcopy(initial_data) if initial_data else {"Components": {}, "Format version": 1}
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
                type_name = getattr(datatype, "__name__", repr(datatype))
                logging_warning(
                    _("Failed to cast value '%s' to %s for path %s: %s"),
                    value,
                    type_name,
                    path,
                    "list and dict types require structured data",
                )
                return self._process_value(path, str(value) if value is not None else None)

            # Standard type conversion
            return datatype(value)

        except (ValueError, TypeError, AttributeError) as e:
            # Log the error and fall back to the original processing method
            type_name = getattr(datatype, "__name__", repr(datatype))
            logging_warning(_("Failed to cast value '%s' to %s for path %s: %s"), value, type_name, path, e)
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

    def post_init(
        self,
        doc_dict: dict,
        fc_parameters: Optional[dict[str, float]] = None,
        file_parameters: Optional[dict[str, ParDict]] = None,
    ) -> None:
        """Update the data structure to ensure all required fields are present."""
        self.update_json_structure(fc_parameters, file_parameters)

        self.init_possible_choices(doc_dict)
        self.correct_display_values_in_loaded_data()

    def import_fc_or_file_parameter(
        self, fc_parameters: dict[str, float], file_parameters: dict[str, ParDict], parameter_name: str
    ) -> float:
        """Import a parameter from FC or file; returns nan if unavailable."""
        val = fc_parameters.get(parameter_name)
        if val is not None:
            return float(val)
        for par_dict in file_parameters.values():
            par = par_dict.get(parameter_name)
            if par is not None:
                return float(par.value)
        return nan

    def update_json_structure(
        self,
        fc_parameters: Optional[dict[str, float]] = None,
        file_parameters: Optional[dict[str, ParDict]] = None,
    ) -> None:
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
                        "Chemistry": BATTERY_DEFAULT_CHEMISTRY,
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

        # Handle GNSS protocol name migration from older versions
        # Protocol names were made more descriptive with manufacturer names
        gnss_protocol_migration = {
            "SBF": "Septentrio(SBF)",
            "GSOF": "Trimble(GSOF)",
            "SBF-DualAntenna": "Septentrio-DualAntenna(SBF)",
        }
        gnss_receiver_protocol = (
            self._data.get("Components", {}).get("GNSS Receiver", {}).get("FC Connection", {}).get("Protocol")
        )
        if gnss_receiver_protocol in gnss_protocol_migration:
            # Migrate to new protocol name
            gnss_receiver = self._data.setdefault("Components", {}).setdefault("GNSS Receiver", {})
            gnss_receiver.setdefault("FC Connection", {})["Protocol"] = gnss_protocol_migration[gnss_receiver_protocol]

        # Merge existing data onto default structure (preserves existing values)
        self._data = self._deep_merge_dicts(default_structure, self._data)
        self._data["Components"] = self._reorder_components(self._data.get("Components", {}))
        self._data["Program version"] = __version__

        self.init_battery_chemistry()  # must be done before migrating legacy battery fields to ensure correct chemistry is set
        self.migrate_legacy_battery_fields(fc_parameters=fc_parameters, file_parameters=file_parameters)

    def migrate_legacy_battery_fields(
        self,
        fc_parameters: Optional[dict[str, float]] = None,
        file_parameters: Optional[dict[str, ParDict]] = None,
    ) -> None:
        """
        Migrate legacy battery voltage fields: add Volt per cell arm and Volt per cell min when missing.

        These fields were added to the schema in v2.11.0 and old files won't have them.
        Derive sensible defaults from the stored chemistry so parameters compute correctly on first use.
        """
        fc_parameters = fc_parameters or {}
        file_parameters = file_parameters or {}

        battery_specs = self._data.get("Components", {}).get("Battery", {}).get("Specifications", {})
        if isinstance(battery_specs, dict) and "Volt per cell max" in battery_specs:
            try:
                num_cells = int(float(str(battery_specs.get("Number of cells"))))
            except (ValueError, TypeError):
                num_cells = 0
            reorder = False
            if "Volt per cell arm" not in battery_specs:
                batt_arm_volt = self.import_fc_or_file_parameter(fc_parameters, file_parameters, "BATT_ARM_VOLT")
                if not isnan(batt_arm_volt) and num_cells > 0:
                    battery_specs["Volt per cell arm"] = round(batt_arm_volt / num_cells, 4)
                else:
                    battery_specs["Volt per cell arm"] = BatteryCell.recommended_cell_voltage(
                        self._battery_chemistry, "Volt per cell arm"
                    )
                reorder = True
            if "Volt per cell min" not in battery_specs:
                mot_batt_volt_min = self.import_fc_or_file_parameter(fc_parameters, file_parameters, "MOT_BAT_VOLT_MIN")
                if not isnan(mot_batt_volt_min) and num_cells > 0:
                    battery_specs["Volt per cell min"] = round(mot_batt_volt_min / num_cells, 4)
                else:
                    battery_specs["Volt per cell min"] = BatteryCell.recommended_cell_voltage(
                        self._battery_chemistry, "Volt per cell min"
                    )
                reorder = True
            if reorder:
                # Reorder keys into canonical field order; preserve any unrecognised extra keys at the end
                desired_order = ["Chemistry", *BATTERY_CELL_VOLTAGE_TYPES, "Number of cells", "Capacity mAh"]
                reordered = {k: battery_specs[k] for k in desired_order if k in battery_specs}
                reordered.update({k: v for k, v in battery_specs.items() if k not in reordered})
                self._data["Components"]["Battery"]["Specifications"] = reordered

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

    def _reorder_components(self, existing_components: ComponentData) -> ComponentData:
        """
        Reorder components according to the desired structure while preserving existing data.

        Args:
            existing_components: The existing components dictionary

        Returns:
            A new dictionary with components reordered according to the desired structure

        """
        desired_component_order = [
            "Flight Controller",
            "Frame",
            "Battery Monitor",
            "Battery",
            "ESC",
            "Motors",
            "Propellers",
            "GNSS Receiver",
            "RC Controller",
            "RC Transmitter",
            "RC Receiver",
            "Telemetry",
        ]

        # Create reordered components dict
        reordered_components = {}
        remaining_components = existing_components.copy()

        # First, add components in the desired order
        for component_name in desired_component_order:
            if component_name in remaining_components:
                reordered_components[component_name] = remaining_components.pop(component_name)

        # Then add any remaining unknown components at the end
        reordered_components.update(remaining_components)

        # Second step: for each component, ensure Product fields are in correct order (Version before URL)
        # and ensure "Notes" is always the last field
        for component_name, component_data in reordered_components.items():
            if "Product" in component_data and isinstance(component_data["Product"], dict):
                product = component_data["Product"]
                if "Version" in product and "URL" in product:
                    # Create new ordered product dict
                    ordered_product = {}
                    # Add fields in desired order
                    for field in ["Manufacturer", "Model", "Version", "URL"]:
                        if field in product:
                            ordered_product[field] = product[field]
                    # Add any remaining fields
                    for field, value in product.items():
                        if field not in ordered_product:
                            ordered_product[field] = value
                    reordered_components[component_name]["Product"] = ordered_product

            if "Notes" in component_data:
                notes_value = component_data.pop("Notes")
                component_data["Notes"] = notes_value

        return reordered_components

    def init_battery_chemistry(self) -> None:
        self._battery_chemistry = (
            self._data.get("Components", {}).get("Battery", {}).get("Specifications", {}).get("Chemistry", "")
        )
        if self._battery_chemistry not in BatteryCell.chemistries():
            logging_error(_("Invalid battery chemistry %s, defaulting to Lipo"), self._battery_chemistry)
            self._data.get("Components", {}).get("Battery", {}).get("Specifications", {})["Chemistry"] = (
                BATTERY_DEFAULT_CHEMISTRY
            )
            self._battery_chemistry = BATTERY_DEFAULT_CHEMISTRY

    def init_possible_choices(self, doc_dict: dict[str, Any]) -> None:
        """Initialize possible choices for validation rules."""
        # this method should be implemented in the ComponentDataModelValidation mixedin

    def correct_display_values_in_loaded_data(self) -> None:
        """Correct display values stored in JSON during model initialization."""
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
