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


class ParameterUnchangedError(Exception):
    """
    Raised when a call to set_new_value would not change the stored value.

    This allows callers to distinguish between an invalid input (ValueError)
    and a valid input that simply results in no change.
    """


class ParameterOutOfRangeError(Exception):
    """
    Raised when a provided value is outside the configured min/max limits.

    This allows callers (usually the UI) to ask the user for confirmation
    before proceeding. If the caller passes `ignore_out_of_range=True` to
    `set_new_value`, the value will be accepted despite being out of range.
    """


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

    def has_unknown_bits_set(self, value: Optional[int] = None) -> str:
        """Check if the given value has unknown bits set."""
        if self.is_bitmask:
            allowed_mask = 0
            for k in self.bitmask_dict:
                allowed_mask |= 1 << int(k)

            new_value = int(self._new_value) if value is None else value
            if new_value & ~allowed_mask:
                return _("The value for {param_name} contains unknown bit(s).").format(param_name=self._name)
        return ""

    def fc_value_is_above_limit(self) -> str:
        """Return an error message if the FC value is above the limit for this parameter."""
        return self.is_above_limit(self._fc_value) if self._fc_value is not None else ""

    def fc_value_is_below_limit(self) -> str:
        """Return an error message if the FC value is below the limit for this parameter."""
        return self.is_below_limit(self._fc_value) if self._fc_value is not None else ""

    def fc_value_has_unknown_bits_set(self) -> str:
        """Return an error message if the FC value has unknown bits set."""
        return self.has_unknown_bits_set(int(self._fc_value)) if self._fc_value is not None else ""

    def set_new_value(self, value: str, ignore_out_of_range: bool = False) -> float:  # pylint: disable=too-many-branches
        """
        Set the new parameter value from a UI string input.

        This method parses and validates the provided string and updates
        ``self._new_value``. On invalid input it raises a ``ValueError`` or
        ``TypeError`` with a user-friendly, translatable message.

        Args:
            value: The new value as a string (e.g. "1.23", "0x10", or a choice label).
            ignore_out_of_range: If True accept values outside min/max limits.

        Returns:
            The new value as a float (or int for bitmask values).

        Raises:
            TypeError: if the provided value is not a string.
            ValueError: if the value is invalid for this parameter (not in choices,
                        invalid bitmask bits, invalid numeric format, etc.).
            ParameterOutOfRangeError: if the value is outside min/max limits and
                `ignore_out_of_range` is False.
            ParameterUnchangedError: if the provided value is valid but does not
                change the currently stored value.

        """
        if self._is_forced or self._is_derived:
            raise ValueError(_("This parameter is forced or derived and cannot be changed."))

        if not isinstance(value, str):
            raise TypeError(_("Parameter value must be provided as a string."))

        s = value.strip()
        if s == "":
            raise ValueError(_("Empty value is not allowed for {param_name}").format(param_name=self._name))

        # Multiple-choice parameters: accept either the choice label or the numeric key
        if self.is_multiple_choice:
            new_value = float(s)
            # No change
            if new_value == self._new_value:
                raise ParameterUnchangedError(
                    _("The provided value for {param_name} would not change the parameter.").format(param_name=self._name)
                )

            self._new_value = new_value
            return self._new_value

        # Bitmask parameters: require integer value; allow 0x / 0b prefixes
        if self.is_bitmask:
            try:
                int_value = int(s, 0)
            except ValueError as exc:
                raise ValueError(
                    _("The value for {param_name} must be an integer for bitmask parameters.").format(param_name=self._name)
                ) from exc

            if int_value == int(self._new_value):
                raise ParameterUnchangedError(
                    _("The provided bitmask value for {param_name} would not change the parameter.").format(
                        param_name=self._name
                    )
                )

            msg = self.has_unknown_bits_set(int_value)
            if msg and not ignore_out_of_range:
                raise ParameterOutOfRangeError(msg)

            self._new_value = float(int_value)
            return self._new_value

        # Otherwise expect a numeric value
        try:
            f = float(s)
        except ValueError as exc:
            raise ValueError(_("The value for {param_name} must be a number.").format(param_name=self._name)) from exc

        if not isfinite(f) or isnan(f):
            raise ValueError(self.is_invalid_number(f))

        if is_within_tolerance(self._new_value, f):
            raise ParameterUnchangedError(
                _(
                    "The provided numeric value for {param_name} is within tolerance and would not change the parameter."
                ).format(param_name=self._name)
            )

        msg = self.is_above_limit(f)
        if msg and not ignore_out_of_range:
            raise ParameterOutOfRangeError(msg)

        msg = self.is_below_limit(f)
        if msg and not ignore_out_of_range:
            raise ParameterOutOfRangeError(msg)

        self._new_value = f
        return self._new_value

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
        # Ensure keys are integers (metadata may contain string keys)
        return {int(key) for key in bitmask_dict if (value >> int(key)) & 1}

    @staticmethod
    def get_value_from_keys(checked_keys: set[int]) -> str:
        """
        Convert a list of checked bit keys to a decimal value.

        Args:
            checked_keys: List of bit positions that are set

        Returns:
            The decimal value string representing the bits set

        """
        return str(sum(1 << key for key in checked_keys))
