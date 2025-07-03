"""
Data model for vehicle component display logic.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_vehicle_components_base import (
    ComponentDataModelBase,
    ComponentPath,
)


class ComponentDataModelDisplay(ComponentDataModelBase):
    """
    Business logic for determining component display rules and configuration.

    This class separates the data processing logic from UI concerns,
    improving testability and maintainability.
    """

    def should_display_in_simple_mode(  # pylint: disable=too-many-branches
        self, key: str, value: dict, path: list[str], complexity_mode: str
    ) -> bool:
        """
        Determine if a component should be displayed in simple mode.

        In simple mode, only show components that have at least one non-optional parameter.

        Args:
            key (str): The component key
            value (dict): The component value
            path (list): The path to the component
            complexity_mode (str): Current complexity mode ("simple" or "normal")

        Returns:
            bool: True if the component should be displayed, False otherwise

        """
        # If not in simple mode, always display the component
        if complexity_mode != "simple":
            return True

        # Top-level components need special handling
        if not path and key in self.get_all_components():
            # Check if this component has any non-optional parameters
            ret = False
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, dict):
                    # For nested dictionaries, recursively check
                    if self.should_display_in_simple_mode(sub_key, sub_value, [*path, key], complexity_mode):
                        ret = True
                        break
                else:
                    # For leaf nodes, check if they are optional
                    current_path = (*path, key, sub_key)
                    _, is_optional = self.schema.get_component_property_description(current_path)
                    if not is_optional:
                        ret = True
                        break
            return ret

        # For non-top-level components or leaf nodes
        if isinstance(value, dict):
            # Check if this component has any non-optional parameters
            for sub_key, sub_value in value.items():
                current_path = (*path, key, sub_key)
                if isinstance(sub_value, dict):
                    if self.should_display_in_simple_mode(sub_key, sub_value, [*path, key], complexity_mode):
                        return True
                else:
                    _, is_optional = self.schema.get_component_property_description(current_path)
                    if not is_optional:
                        return True

        return False

    def should_display_leaf_in_simple_mode(self, path: ComponentPath, complexity_mode: str) -> bool:
        """
        Determine if a leaf component should be displayed in simple mode.

        Args:
            path: The component path
            complexity_mode: Current complexity mode ("simple" or "normal")

        Returns:
            bool: True if the component should be displayed, False otherwise

        """
        if complexity_mode != "simple":
            return True

        _, is_optional = self.schema.get_component_property_description(path)
        return not is_optional

    def prepare_non_leaf_widget_config(self, key: str, value: dict, path: list[str]) -> dict:
        """
        Prepare configuration for non-leaf widget creation. Pure function for easy testing.

        Args:
            key: Component key
            value: Component value dictionary
            path: Path to the component

        Returns:
            Dictionary with widget configuration data

        """
        is_toplevel = len(path) == 0  # More explicit than checking parent type
        current_path = (*path, key)
        description, is_optional = self.schema.get_component_property_description(current_path)
        description = _(description) if description else ""

        # Enhance tooltip for optional fields
        if is_optional and description:
            description += _("\nThis is optional and can be left blank")

        return {
            "key": key,
            "value": value,
            "path": current_path,
            "description": description,
            "is_optional": is_optional,
            "is_toplevel": is_toplevel,
        }

    def prepare_leaf_widget_config(self, key: str, value: Union[str, float], path: list[str]) -> dict:
        """
        Prepare configuration for leaf widget creation. Pure function for easy testing.

        Args:
            key: Component key
            value: Component value
            path: Path to the component

        Returns:
            Dictionary with widget configuration data

        """
        component_path = (*path, key)
        description, is_optional = self.schema.get_component_property_description(component_path)
        description = _(description) if description else ""

        # Enhance tooltip for optional fields
        if is_optional and description:
            description += _("\nThis is optional and can be left blank")

        return {
            "key": key,
            "value": value,
            "path": component_path,
            "description": description,
            "is_optional": is_optional,
        }
