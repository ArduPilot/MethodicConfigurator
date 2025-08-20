"""
Data model interface for vehicle components templates.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

from ardupilot_methodic_configurator.data_model_vehicle_components_base import (
    ComponentData,
    ComponentDataModelBase,
    ComponentPath,
)


class ComponentDataModelTemplates(ComponentDataModelBase):
    """
    A class to handle component data operations (template interface) separate from UI logic.

    This improves testability by isolating data operations.
    """

    def update_component(self, component_name: str, component_data: dict) -> None:
        """Update a component with new data."""
        if "Components" not in self._data:
            self._data["Components"] = {}
        self._data["Components"][component_name] = component_data

    def derive_initial_template_name(self, component_data: dict[str, Any]) -> str:
        """Derive an initial template name from the component data."""
        initial_template_name: str = ""
        product_data = component_data.get("Product")
        if product_data is not None:
            manufacturer = product_data.get("Manufacturer", "")
            model = product_data.get("Model", "")
            # Convert to strings to handle None and other types gracefully
            manufacturer_str = str(manufacturer) if manufacturer is not None else ""
            model_str = str(model) if model is not None else ""
            initial_template_name = manufacturer_str + " " + model_str
        return initial_template_name

    def extract_component_data_from_entries(self, component_name: str, entries: dict[ComponentPath, str]) -> ComponentData:
        """
        Extract component data for a specific component from entries.

        This extracts and processes component data from entry values,
        organizing them into a properly structured dictionary.
        """
        component_data: ComponentData = {}

        # Find all entries belonging to this component and extract their values
        for path, value in entries.items():
            if len(path) >= 1 and path[0] == component_name:
                # Process the value based on type
                datatype = self._get_component_datatype(path)
                if datatype:
                    processed_value = self._safe_cast_value(value, datatype, path)
                else:  # fallback to a less intelligent method
                    # If the component has a specific datatype, use it to process the value
                    processed_value = self._process_value(path, value)

                # Create the nested structure
                current_level: ComponentData = component_data
                for key in path[1:-1]:  # Skip component_name and the last key
                    if key not in current_level:
                        current_level[key] = {}
                    current_level = current_level[key]

                # Set the value at the final level
                current_level[path[-1]] = processed_value

        return component_data
