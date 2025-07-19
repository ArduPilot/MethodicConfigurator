"""
ArduPilot parameter domain model.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import is_within_tolerance


class ArduPilotParameter:
    """Domain model representing an ArduPilot parameter with all its attributes."""

    def __init__(
        self,
        name: str,
        par_obj: Par,
        metadata: Optional[dict[str, Any]] = None,
        default_par: Optional[Par] = None,
        fc_value: Optional[float] = None,
        is_forced: bool = False,
        is_derived: bool = False,
    ) -> None:
        """
        Initialize the parameter with all its attributes.

        Args:
            name: Name of the parameter
            par_obj: Par object containing value and comment
            metadata: Dictionary of parameter metadata (from pdef.xml files)
            default_par: Default parameter object for comparison
            fc_value: Value from the flight controller, if connected
            is_forced: Whether this parameter is forced (cannot be edited)
            is_derived: Whether this parameter is derived (calculated automatically)

        """
        self.name = name
        self.value = par_obj.value
        self.comment = par_obj.comment
        self.metadata = metadata or {}
        self.default_value = default_par.value if default_par else None
        self.fc_value = fc_value
        self.is_forced = is_forced
        self.is_derived = is_derived

    @property
    def is_calibration(self) -> bool:
        """Return True if this is a calibration parameter."""
        return self.metadata.get("Calibration", False)

    @property
    def is_readonly(self) -> bool:
        """Return True if this is a readonly parameter."""
        return self.metadata.get("ReadOnly", False)

    @property
    def is_bitmask(self) -> bool:
        """Return True if this parameter uses a bitmask representation."""
        return "Bitmask" in self.metadata

    @property
    def has_default_value(self) -> bool:
        """Return True if the current value equals the default value."""
        return self.default_value is not None and is_within_tolerance(self.value, self.default_value)

    @property
    def has_fc_value(self) -> bool:
        """Return True if there is a flight controller value for this parameter."""
        return self.fc_value is not None

    @property
    def is_different_from_fc(self) -> bool:
        """Return True if the parameter value is different from the flight controller value."""
        return self.fc_value is not None and not is_within_tolerance(self.value, self.fc_value)

    @property
    def doc_tooltip(self) -> str:
        """Return the documentation tooltip for this parameter."""
        return self.metadata.get("doc_tooltip", _("No documentation available in apm.pdef.xml for this parameter"))

    @property
    def unit(self) -> str:
        """Return the unit of this parameter."""
        return self.metadata.get("unit", "")

    @property
    def unit_tooltip(self) -> str:
        """Return the unit tooltip for this parameter."""
        return self.metadata.get("unit_tooltip", _("No documentation available in apm.pdef.xml for this parameter"))

    @property
    def values_dict(self) -> dict:
        """Return the values dictionary for this parameter."""
        return self.metadata.get("values", {})

    @property
    def bitmask_dict(self) -> dict:
        """Return the bitmask dictionary for this parameter."""
        return self.metadata.get("Bitmask", {})

    @property
    def min_value(self) -> Optional[float]:
        """Return the minimum allowed value for this parameter."""
        min_val = self.metadata.get("min", None)
        return float(min_val) if min_val is not None else None

    @property
    def max_value(self) -> Optional[float]:
        """Return the maximum allowed value for this parameter."""
        max_val = self.metadata.get("max", None)
        return float(max_val) if max_val is not None else None

    @property
    def value_as_string(self) -> str:
        """Return the parameter value as a formatted string."""
        return format(self.value, ".6f").rstrip("0").rstrip(".")

    @property
    def fc_value_as_string(self) -> str:
        """Return the flight controller value as a formatted string."""
        if self.fc_value is None:
            return _("N/A")
        return format(self.fc_value, ".6f").rstrip("0").rstrip(".")

    def is_in_values_dict(self) -> bool:
        """Return True if the current value is in the values dictionary."""
        return bool(self.values_dict and self.value_as_string in self.values_dict)

    def get_selected_value_from_dict(self) -> Optional[str]:
        """Return the string representation from the values dictionary for the current value."""
        if self.is_in_values_dict():
            return self.values_dict.get(self.value_as_string)
        return None

    def set_value(self, value: float) -> bool:
        """
        Set the parameter value and return whether it changed.

        Args:
            value: The new value to set

        Returns:
            True if the value was changed, False otherwise

        """
        if self.is_forced or self.is_derived:
            return False

        if is_within_tolerance(self.value, value):
            return False

        self.value = value
        return True

    def set_comment(self, comment: str) -> bool:
        """
        Set the parameter comment and return whether it changed.

        Args:
            comment: The new comment to set

        Returns:
            True if the comment was changed, False otherwise

        """
        if self.is_forced or self.is_derived:
            return False

        if comment == self.comment or (comment == "" and self.comment is None):
            return False

        self.comment = comment
        return True

    def is_editable(self) -> bool:
        """
        Check if this parameter is editable.

        Returns:
            True if the parameter can be edited, False otherwise

        """
        return not (self.is_forced or self.is_derived or self.is_readonly)

    def is_valid_value(self, value: float) -> bool:
        """
        Check if a value is valid for this parameter.

        Args:
            value: The value to check

        Returns:
            True if the value is valid, False otherwise

        """
        if self.min_value is not None and value < self.min_value:
            return False

        return not (self.max_value is not None and value > self.max_value)
