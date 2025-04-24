"""
ArduPilot parameter connection renaming utility.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, Optional


class ConnectionRenamer:
    """
    Utility class to handle renaming parameters based on connection prefixes.

    This captures the logic for renaming parameters when connection types change,
    particularly handling special cases like CAN bus connections.
    """

    @staticmethod
    def generate_renames(parameters: list[str], new_connection_prefix: str) -> dict[str, str]:
        """
        Generate a dictionary of parameter renames based on a new connection prefix.

        Args:
            parameters: List of parameter names to potentially rename
            new_connection_prefix: The new prefix to apply (like "CAN2")

        Returns:
            Dictionary mapping old parameter names to new parameter names

        """
        renames = {}

        # Extract the type and number from the new connection prefix
        if len(new_connection_prefix) < 2:
            return renames

        new_type = new_connection_prefix[:-1]  # e.g., "CAN" from "CAN2"
        new_number = new_connection_prefix[-1]  # e.g., "2" from "CAN2"

        for param_name in parameters:
            if new_type == "CAN" and param_name.startswith("CAN_"):
                # Handle CAN_P1_* or CAN_D1_* pattern for CAN parameters
                if "_P1_" in param_name:
                    new_param_name = param_name.replace("_P1_", f"_P{new_number}_")
                    renames[param_name] = new_param_name
                elif "_D1_" in param_name:
                    new_param_name = param_name.replace("_D1_", f"_D{new_number}_")
                    renames[param_name] = new_param_name
            elif param_name.startswith(f"{new_type}1_"):
                # Handle standard parameters like SERIAL1_BAUD
                new_param_name = param_name.replace(f"{new_type}1_", f"{new_type}{new_number}_")
                renames[param_name] = new_param_name

        return renames

    @staticmethod
    def apply_renames(
        parameters: dict[str, Any], new_connection_prefix: str, variables: Optional[dict[str, Any]] = None
    ) -> tuple[dict[str, Any], set[str], list[tuple[str, str]]]:
        """
        Apply connection prefix renames to a parameter dictionary.

        Args:
            parameters: Dictionary of parameter objects to rename
            new_connection_prefix: The new prefix to apply
            variables: Optional dictionary of variables for evaluation

        Returns:
            Tuple containing:
            - Updated parameters dictionary
            - Set of new parameter names
            - List of (old_name, new_name) pairs that were renamed

        """
        if variables:
            # If variables provided, evaluate the new_connection_prefix
            new_connection_prefix = eval(str(new_connection_prefix), {}, variables)  # noqa: S307 pylint: disable=eval-used

        # Generate the rename mapping
        renames = ConnectionRenamer.generate_renames(list(parameters.keys()), new_connection_prefix)

        # Track unique new names and actual renames performed
        new_names = set()
        renamed_pairs = []

        # Create a new dictionary to avoid modifying during iteration
        updated_parameters = parameters.copy()

        # First identify and process duplicates
        duplicates = []
        for old_name, new_name in renames.items():
            if new_name in parameters and old_name != new_name:
                duplicates.append(old_name)

        # Remove duplicates
        for old_name in duplicates:
            if old_name in updated_parameters:
                updated_parameters.pop(old_name)

        # Process remaining renames
        for old_name, new_name in renames.items():
            if old_name in updated_parameters and old_name not in duplicates:
                renamed_pairs.append((old_name, new_name))
                updated_parameters[new_name] = updated_parameters.pop(old_name)
                new_names.add(new_name)

        return updated_parameters, new_names, renamed_pairs
