"""
ArduPilot parameter dictionary data model.

This module provides the ParDict class which extends dict[str, Par]
with specialized methods for managing ArduPilot parameters.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par


class ParDict(dict[str, Par]):
    """
    A specialized dictionary for managing ArduPilot parameters.

    This class extends dict[str, Par] to provide additional functionality
    for merging and comparing parameter dictionaries.
    """

    def __init__(self, initial_data: Optional[dict[str, Par]] = None) -> None:
        """
        Initialize the ParDict.

        Args:
            initial_data: Optional initial parameter data to populate the dictionary.

        """
        super().__init__()
        if initial_data:
            self.update(initial_data)

    def append(self, other: "ParDict") -> None:
        """
        Append parameters from another ParDict.

        Parameters with the same name will be replaced with values from the other dictionary.

        Args:
            other: Another ParDict to append from.

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only append another ParDict instance")
            raise TypeError(msg)

        for param_name, param_value in other.items():
            self[param_name] = param_value

    def remove_if_similar(self, other: "ParDict") -> None:
        """
        Remove parameters from this dictionary if their values match those in another dictionary.

        This method compares parameter values and removes parameters from the current
        dictionary if they have the same name and value as parameters in the other dictionary.

        Args:
            other: Another ParDict to compare against.

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only compare with another ParDict instance")
            raise TypeError(msg)

        # Create a list of keys to remove to avoid modifying dict during iteration
        keys_to_remove = []

        for param_name, param_value in self.items():
            if param_name in other and param_value == other[param_name]:
                keys_to_remove.append(param_name)

        # Remove the parameters that matched
        for key in keys_to_remove:
            del self[key]

    def remove_if_value_is_similar(self, other: "ParDict") -> None:
        """
        Remove parameters from this dictionary if their values match those in another dictionary.

        This method compares only parameter values and ignores comments when determining similarity.
        Parameters from the current dictionary are removed if they have the same name and value
        as parameters in the other dictionary, regardless of comment differences.

        This is particularly useful when comparing flight controller parameters (which have no comments)
        with file parameters (which typically have comments).

        Args:
            other: Another ParDict to compare against.

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only compare with another ParDict instance")
            raise TypeError(msg)

        # Create a list of keys to remove to avoid modifying dict during iteration
        keys_to_remove = []

        for param_name, param_value in self.items():
            if param_name in other and param_value.value == other[param_name].value:
                keys_to_remove.append(param_name)

        # Remove the parameters that matched
        for key in keys_to_remove:
            del self[key]

    def get_different_parameters(self, other: "ParDict") -> "ParDict":
        """
        Get parameters that are different between this and another dictionary.

        Returns a new ParDict containing parameters that:
        - Exist in this dictionary but not in the other
        - Exist in both dictionaries but have different values

        Args:
            other: Another ParDict to compare against.

        Returns:
            A new ParDict containing the different parameters.

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only compare with another ParDict instance")
            raise TypeError(msg)

        different_params = ParDict()

        for param_name, param_value in self.items():
            if param_name not in other or param_value != other[param_name]:
                different_params[param_name] = param_value

        return different_params

    def get_common_parameters(self, other: "ParDict") -> "ParDict":
        """
        Get parameters that are identical between this and another dictionary.

        Returns a new ParDict containing parameters that exist
        in both dictionaries with identical values.

        Args:
            other: Another ParDict to compare against.

        Returns:
            A new ParDict containing the common parameters.

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only compare with another ParDict instance")
            raise TypeError(msg)

        common_params = ParDict()

        for param_name, param_value in self.items():
            if param_name in other and param_value == other[param_name]:
                common_params[param_name] = param_value

        return common_params

    def filter_by_prefix(self, prefix: str) -> "ParDict":
        """
        Filter parameters by name prefix.

        Args:
            prefix: The prefix to filter by.

        Returns:
            A new ParDict containing only parameters whose names start with the prefix.

        """
        filtered_params = ParDict()

        for param_name, param_value in self.items():
            if param_name.startswith(prefix):
                filtered_params[param_name] = param_value

        return filtered_params

    def get_parameter_count(self) -> int:
        """
        Get the total number of parameters in the dictionary.

        Returns:
            The number of parameters.

        """
        return len(self)

    def copy(self) -> "ParDict":
        """
        Create a shallow copy of the ParDict.

        Returns:
            A new ParDict with the same parameters.

        """
        return ParDict(dict(self))

    def __repr__(self) -> str:
        """
        Return a string representation of the ParDict.

        Returns:
            A string representation showing the class name and parameter count.

        """
        return f"ParDict({len(self)} parameters)"

    def __str__(self) -> str:
        """
        Return a human-readable string representation of the ParDict.

        Returns:
            A string showing the parameter count and first few parameter names.

        """
        param_count = len(self)
        if param_count == 0:
            return "ParDict(empty)"

        param_names = list(self.keys()) if param_count <= 3 else [*list(self.keys())[:3], "..."]

        return f"ParDict({param_count} parameters: {', '.join(param_names)})"
