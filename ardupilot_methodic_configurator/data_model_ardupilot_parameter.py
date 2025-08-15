"""
ArduPilot parameter domain model.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import inf, isfinite, isnan, nan
from typing import Any, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import is_within_tolerance


class ArduPilotParameter:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Domain model representing an ArduPilot parameter with all its attributes."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        name: str,
        par_obj: Par,
        metadata: Optional[dict[str, Any]] = None,
        default_par: Optional[Par] = None,
        fc_value: Optional[float] = None,
        forced_par: Optional[Par] = None,
        derived_par: Optional[Par] = None,
    ) -> None:
        """
        Initialize the parameter with all its attributes.

        Args:
            name: Name of the parameter
            par_obj: Par object containing value and comment
            metadata: Dictionary of parameter metadata (from pdef.xml files)
            default_par: Default parameter object for comparison
            fc_value: Value from the flight controller, if connected
            forced_par: Parameter object containing forced value and change reason
            derived_par: Parameter object containing derived value and change reason

        """
        self._name = name
        self._metadata = metadata or {}
        self._default_value = default_par.value if default_par else None
        self._fc_value = fc_value

        forced_value = forced_par.value if forced_par is not None else None
        forced_reason = forced_par.comment if forced_par is not None else None
        derived_value = derived_par.value if derived_par is not None else None
        derived_reason = derived_par.comment if derived_par is not None else None
        self._is_forced = forced_value is not None and forced_value not in (nan, +inf, -inf)
        self._is_derived = derived_value is not None and derived_value not in (nan, +inf, -inf)

        # these are the values read from file, not the new values
        self._value_on_file = par_obj.value
        self._change_reason_on_file = par_obj.comment or ""

        # new value and change reason to be sent to the flight controller and/or saved to file
        if self._is_forced and forced_value is not None:  # second condition is redundant, but keeps linters happy
            self._new_value = forced_value
            self._change_reason = forced_reason or ""
        elif self._is_derived and derived_value is not None:  # second condition is redundant, but keeps linters happy
            self._new_value = float(derived_value)
            self._change_reason = derived_reason or ""
        else:
            self._new_value = par_obj.value
            self._change_reason = par_obj.comment or ""

    @property
    def name(self) -> str:
        """Return this parameter name."""
        return self._name

    @property
    def is_calibration(self) -> bool:
        """Return True if this is a calibration parameter."""
        return bool(self._metadata.get("Calibration", False))

    @property
    def is_readonly(self) -> bool:
        """Return True if this is a readonly parameter."""
        return bool(self._metadata.get("ReadOnly", False))

    @property
    def is_bitmask(self) -> bool:
        """Return True if this parameter uses a bitmask representation."""
        return "Bitmask" in self._metadata

    @property
    def is_forced(self) -> bool:
        """Return True if this parameter is forced from the configuration step."""
        return self._is_forced

    @property
    def is_derived(self) -> bool:
        """Return True if this parameter value is derived from component editor information."""
        return self._is_derived

    @property
    def is_multiple_choice(self) -> bool:
        """Return True if this parameter uses a multiple choice representation."""
        # these parameters do have choices defined in their metadata, the handful of discrete choices
        #  is limitative and most usecases require the use of a continuous range instead
        multiple_choice_blacklist = {
            "MOT_SPIN_ARM",
            "MOT_SPIN_MAX",
            "MOT_SPIN_MIN",
            "MOT_THST_EXPO",
            "ATC_ACCEL_P_MAX",
            "ATC_ACCEL_R_MAX",
            "ATC_ACCEL_Y_MAX",
        }
        return (
            self.choices_dict is not None
            and len(self.choices_dict) > 0
            and self.is_in_values_dict
            and self._name not in multiple_choice_blacklist
        )

    @property
    def is_editable(self) -> bool:
        """Return True if the parameter can be edited, False otherwise."""
        return not (self._is_forced or self._is_derived or self.is_readonly)

    @property
    def has_fc_value(self) -> bool:
        """Return True if there is a flight controller value for this parameter."""
        return self._fc_value is not None

    @property
    def fc_value_equals_default_value(self) -> bool:
        """Return True if the flight controller value equals the default value."""
        return (
            self._default_value is not None
            and self._fc_value is not None
            and (
                self._fc_value == self._default_value
                if self.is_bitmask or self.is_multiple_choice
                else is_within_tolerance(self._fc_value, self._default_value)
            )
        )

    @property
    def new_value_equals_default_value(self) -> bool:
        """Return True if the new parameter value equals the default value."""
        return self._default_value is not None and (
            self._new_value == self._default_value
            if self.is_bitmask or self.is_multiple_choice
            else is_within_tolerance(self._new_value, self._default_value)
        )

    @property
    def is_different_from_fc(self) -> bool:
        """Return True if the new parameter value is different from the flight controller value."""
        return self._fc_value is not None and (
            self._new_value != self._fc_value
            if self.is_bitmask or self.is_multiple_choice
            else not is_within_tolerance(self._new_value, self._fc_value)
        )

    @property
    def is_dirty(self) -> bool:
        """Return True if this parameter has unsaved changes."""
        value_dirty = (
            self._new_value != self._value_on_file
            if self.is_bitmask or self.is_multiple_choice
            else is_within_tolerance(self._new_value, self._value_on_file)
        )
        return value_dirty or self._change_reason != self._change_reason_on_file

    @property
    def choices_dict(self) -> dict[str, str]:
        """Return the multiple choices dictionary for this parameter."""
        return dict[str, str](self._metadata.get("values", {}))

    @property
    def bitmask_dict(self) -> dict[int, str]:
        """Return the bitmask dictionary for this parameter."""
        return dict[int, str](self._metadata.get("Bitmask", {}))

    @property
    def min_value(self) -> Optional[float]:
        """Return the minimum allowed value for this parameter."""
        min_val = self._metadata.get("min", None)
        return float(min_val) if min_val is not None else None

    @property
    def max_value(self) -> Optional[float]:
        """Return the maximum allowed value for this parameter."""
        max_val = self._metadata.get("max", None)
        return float(max_val) if max_val is not None else None

    @property
    def fc_value_as_string(self) -> str:
        """Return the flight controller value as a formatted string."""
        if self._fc_value is None:
            return _("N/A")
        return format(self._fc_value, ".6f").rstrip("0").rstrip(".")

    @property
    def value_as_string(self) -> str:
        """Return the parameter value as a formatted string."""
        return format(self._new_value, ".6f").rstrip("0").rstrip(".")

    @property
    def is_in_values_dict(self) -> bool:
        """Return True if the new value is in the values dictionary."""
        return bool(self.choices_dict and self.value_as_string in self.choices_dict)

    @property
    def tooltip_fc_value(self) -> str:
        """Return the numerically sorted documentation tooltip for this parameter."""
        return str(self._metadata.get("doc_tooltip_sorted_numerically", self.tooltip_new_value))

    @property
    def tooltip_new_value(self) -> str:
        """Return the documentation tooltip for this parameter."""
        return str(self._metadata.get("doc_tooltip", _("No documentation available in apm.pdef.xml for this parameter")))

    @property
    def tooltip_unit(self) -> str:
        """Return the unit tooltip for this parameter."""
        return str(self._metadata.get("unit_tooltip", _("No documentation available in apm.pdef.xml for this parameter")))

    @property
    def tooltip_change_reason(self) -> str:
        """Return the tooltip for the reason why this parameter should change."""
        msg = _("Reason why {param_name} should change to {value}")
        return msg.format(param_name=self._name, value=self._new_value)

    @property
    def unit(self) -> str:
        """Return the unit of this parameter."""
        return str(self._metadata.get("unit", ""))

    @property
    def change_reason(self) -> str:
        """Return the change reason string for this parameter."""
        return self._change_reason

    def get_selected_value_from_dict(self) -> Optional[str]:
        """Return the string representation from the values dictionary for the new value."""
        if self.is_in_values_dict:
            return self.choices_dict.get(self.value_as_string)
        return None

    def is_invalid_number(self, new_value: float) -> str:
        """Return an error message if the new value is an invalid number."""
        if not isfinite(new_value) or isnan(new_value):
            return _("The value for {param_name} must be a finite number.").format(param_name=self._name)
        return ""

    def is_above_limit(self, value: Optional[float] = None) -> str:
        """Return an error message if the value is above the limit for this parameter."""
        new_value = self._new_value if value is None else value
        if self.max_value is not None and new_value > self.max_value:
            return _("The value for {param_name} ({value}) should be smaller than {max_val}\n").format(
                param_name=self._name, value=new_value, max_val=self.max_value
            )
        return ""

    def is_below_limit(self, value: Optional[float] = None) -> str:
        """Return an error message if the value is below the limit for this parameter."""
        new_value = self._new_value if value is None else value
        if self.min_value is not None and new_value < self.min_value:
            return _("The value for {param_name} ({value}) should be greater than {min_val}\n").format(
                param_name=self._name, value=new_value, min_val=self.min_value
            )
        return ""

    def fc_value_is_above_limit(self) -> str:
        """Return an error message if the FC value is above the limit for this parameter."""
        return self.is_above_limit(self._fc_value) if self._fc_value is not None else ""

    def fc_value_is_below_limit(self) -> str:
        """Return an error message if the RC value is below the limit for this parameter."""
        return self.is_below_limit(self._fc_value) if self._fc_value is not None else ""

    def set_new_value(self, value: float) -> bool:
        """
        Set the new parameter value and return whether it changed.

        Args:
            value: The new value to set

        Returns:
            True if the new value was changed, False otherwise

        """
        if self._is_forced or self._is_derived:
            return False

        if (self.is_bitmask or self.is_multiple_choice) and value == self._new_value:
            return False

        if not (self.is_bitmask or self.is_multiple_choice) and is_within_tolerance(self._new_value, value):
            return False

        self._new_value = value
        return True

    def set_change_reason(self, change_reason: str) -> bool:
        """
        Set the parameter change_reason and return whether it changed.

        Args:
            change_reason: The new change_reason to set

        Returns:
            True if the change_reason was changed, False otherwise

        """
        if self._is_forced or self._is_derived:
            return False

        if change_reason == self._change_reason or (change_reason == "" and self._change_reason is None):
            return False

        self._change_reason = change_reason
        return True


class BitmaskHelper:
    """Helper class for working with ArduPilot parameter bitmasks."""

    @staticmethod
    def get_checked_keys(value: int, bitmask_dict: dict[int, str]) -> set[int]:
        """
        Convert a decimal value to a set of checked bit keys.

        Args:
            value: The decimal value to convert
            bitmask_dict: Dictionary mapping bit positions to descriptions

        Returns:
            Set of keys (bit positions) that are set in the value

        """
        return {key for key in bitmask_dict if (value >> key) & 1}

    @staticmethod
    def get_value_from_keys(checked_keys: set[int]) -> int:
        """
        Convert a list of checked bit keys to a decimal value.

        Args:
            checked_keys: List of bit positions that are set

        Returns:
            The decimal value representing the bits set

        """
        return sum(1 << key for key in checked_keys)


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
        renames: dict[str, str] = {}

        # Extract the type and number from the new connection prefix
        if len(new_connection_prefix) < 2:
            return renames

        new_type = new_connection_prefix[:-1]  # e.g., "CAN" from "CAN2"
        new_number = new_connection_prefix[-1]  # e.g., "2" from "CAN2"

        for param_name in parameters:
            new_prefix = new_connection_prefix
            old_prefix = param_name.split("_")[0]
            if new_type == "CAN" and "CAN_P" in param_name:
                old_prefix = param_name.split("_")[0] + "_" + param_name.split("_")[1]
                new_prefix = "CAN_P" + new_number
            if new_type == "CAN" and "CAN_D" in param_name:
                old_prefix = param_name.split("_")[0] + "_" + param_name.split("_")[1]
                new_prefix = "CAN_D" + new_number

            if new_type in old_prefix:
                renames[param_name] = param_name.replace(old_prefix, new_prefix)

        return renames

    @staticmethod
    def apply_renames(
        parameters: dict[str, Any], new_connection_prefix: str, variables: Optional[dict[str, Any]] = None
    ) -> tuple[set[str], list[tuple[str, str]]]:
        """
        Apply connection prefix renames to a parameter dictionary.

        Args:
            parameters: Dictionary of parameter objects to rename, it will modify it
            new_connection_prefix: The new prefix to apply
            variables: Optional dictionary of variables for evaluation

        Returns:
            Tuple containing:
            - Set of duplicated parameter names that got removed
            - List of (old_name, new_name) pairs that were renamed

        """
        if variables:
            # If variables provided, evaluate the new_connection_prefix
            new_connection_prefix = eval(str(new_connection_prefix), {}, variables)  # noqa: S307 pylint: disable=eval-used

        # Generate the rename mapping
        renames = ConnectionRenamer.generate_renames(list(parameters.keys()), new_connection_prefix)

        # Track unique new names and actual renames performed
        new_names = set()
        duplicates = set()
        renamed_pairs = []
        for old_name, new_name in renames.items():
            if new_name in new_names:
                parameters.pop(old_name)
                duplicates.add(old_name)
            else:
                new_names.add(new_name)
                if new_name != old_name:
                    parameters[new_name] = parameters.pop(old_name)
                    renamed_pairs.append((old_name, new_name))

        return duplicates, renamed_pairs
