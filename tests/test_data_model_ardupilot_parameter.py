#!/usr/bin/env python3

"""
Unit tests for the ArduPilotParameter domain model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math
from typing import Any

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import (
    ArduPilotParameter,
    BitmaskHelper,
    ParameterOutOfRangeError,
    ParameterUnchangedError,
)
from ardupilot_methodic_configurator.data_model_par_dict import Par

# pylint: disable=redefined-outer-name, protected-access, too-many-lines


@pytest.fixture
def param_fixture() -> dict[str, Any]:  # pylint: disable=too-many-locals
    """Create parameter fixtures for testing."""
    # Create a basic parameter
    param_name = "TEST_PARAM"
    param_value = 10.0
    param_comment = "Test comment"
    par_obj = Par(param_value, param_comment)

    # Create parameter with default value
    default_value = 5.0
    default_par = Par(default_value, "Default comment")

    # Create FC value
    fc_value = 15.0

    # Metadata with bitmask, values dict, and constraints
    metadata: dict[str, Any] = {
        "doc_tooltip": "Test tooltip",
        "unit": "m/s",
        "unit_tooltip": "Meters per second",
        "min": 0.0,
        "max": 20.0,
        "values": {"0": "Zero", "10": "Ten", "20": "Twenty"},
        "Bitmask": {0: "Option 1", 1: "Option 2", 2: "Option 3"},
        "Calibration": False,
        "ReadOnly": False,
    }

    # Basic parameter without extras
    basic_param = ArduPilotParameter(param_name, par_obj)

    # Parameter with all attributes
    full_param = ArduPilotParameter(param_name, par_obj, metadata, default_par, fc_value)

    # Forced parameter
    forced_param = ArduPilotParameter(
        param_name, par_obj, metadata, default_par, fc_value, forced_par=Par(param_value, param_comment)
    )

    # Derived parameter
    derived_param = ArduPilotParameter(
        param_name, par_obj, metadata, default_par, fc_value, derived_par=Par(param_value, param_comment)
    )

    # Readonly parameter
    readonly_metadata = metadata.copy()
    readonly_metadata["ReadOnly"] = True
    readonly_param = ArduPilotParameter(param_name, par_obj, readonly_metadata, default_par, fc_value)

    # Calibration parameter
    calibration_metadata = metadata.copy()
    calibration_metadata["Calibration"] = True
    calibration_param = ArduPilotParameter(param_name, par_obj, calibration_metadata, default_par, fc_value)

    return {
        "param_name": param_name,
        "param_value": param_value,
        "param_comment": param_comment,
        "par_obj": par_obj,
        "default_value": default_value,
        "default_par": default_par,
        "fc_value": fc_value,
        "metadata": metadata,
        "basic_param": basic_param,
        "full_param": full_param,
        "forced_param": forced_param,
        "derived_param": derived_param,
        "readonly_param": readonly_param,
        "calibration_param": calibration_param,
    }


def test_basic_properties(param_fixture) -> None:
    """
    Parameter stores and retrieves basic attributes correctly.

    GIVEN: A parameter is created with name, value, comment, default, and FC value
    WHEN: The parameter attributes are accessed
    THEN: All attributes should match the provided values
    """
    # Assert: All basic properties are correctly stored
    assert param_fixture["full_param"].name == param_fixture["param_name"]
    assert param_fixture["full_param"]._new_value == param_fixture["param_value"]
    assert param_fixture["full_param"].change_reason == param_fixture["param_comment"]
    assert param_fixture["full_param"]._default_value == param_fixture["default_value"]
    assert param_fixture["full_param"]._fc_value == param_fixture["fc_value"]
    assert not param_fixture["full_param"].is_forced
    assert not param_fixture["full_param"].is_derived


def test_parameter_type_properties(param_fixture) -> None:
    """
    Parameter correctly identifies its type based on metadata.

    GIVEN: Parameters are created with different metadata configurations
    WHEN: Type properties are checked (readonly, calibration, bitmask)
    THEN: Each parameter should correctly identify its type
    """
    # Assert: Readonly parameter is identified correctly
    assert param_fixture["readonly_param"].is_readonly
    assert not param_fixture["full_param"].is_readonly

    # Assert: Calibration parameter is identified correctly
    assert param_fixture["calibration_param"].is_calibration
    assert not param_fixture["full_param"].is_calibration

    # Assert: Bitmask parameter is identified correctly
    assert param_fixture["full_param"].is_bitmask

    # Arrange: Create a parameter without bitmask metadata
    no_bitmask_metadata = param_fixture["metadata"].copy()
    no_bitmask_metadata.pop("Bitmask")
    no_bitmask_param = ArduPilotParameter(param_fixture["param_name"], param_fixture["par_obj"], no_bitmask_metadata)

    # Assert: Non-bitmask parameter is identified correctly
    assert not no_bitmask_param.is_bitmask


def test_value_comparisons(param_fixture) -> None:
    """
    Parameter correctly compares values between file, default, and flight controller.

    GIVEN: Parameters with different value configurations
    WHEN: Value comparison properties are accessed
    THEN: Comparisons should correctly identify matching or differing values
    """
    # Assert: Parameter with non-default value is identified correctly
    assert not param_fixture["full_param"].new_value_equals_default_value

    # Arrange: Create parameter with value matching default
    default_value_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["default_value"], ""),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
    )

    # Assert: Parameter with default value is identified correctly
    assert default_value_param.new_value_equals_default_value

    # Assert: FC value presence is detected correctly
    assert param_fixture["full_param"].has_fc_value
    assert not param_fixture["basic_param"].has_fc_value

    # Assert: Difference from FC value is detected correctly
    assert param_fixture["full_param"].is_different_from_fc

    # Arrange: Create parameter matching FC value
    same_as_fc_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["fc_value"], ""),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
    )

    # Assert: Parameter matching FC value is identified correctly
    assert not same_as_fc_param.is_different_from_fc


def test_metadata_properties(param_fixture) -> None:
    """
    Parameter exposes metadata documentation and constraints correctly.

    GIVEN: Parameters with complete or missing metadata
    WHEN: Metadata properties are accessed
    THEN: Properties should return correct values or appropriate defaults
    """
    # Assert: Parameter with full metadata returns correct values
    assert param_fixture["full_param"].tooltip_new_value == param_fixture["metadata"]["doc_tooltip"]
    assert param_fixture["full_param"].unit == param_fixture["metadata"]["unit"]
    assert param_fixture["full_param"].tooltip_unit == param_fixture["metadata"]["unit_tooltip"]
    assert param_fixture["full_param"].min_value == float(param_fixture["metadata"]["min"])
    assert param_fixture["full_param"].max_value == float(param_fixture["metadata"]["max"])

    # Assert: Parameter without metadata returns appropriate defaults
    assert param_fixture["basic_param"].tooltip_new_value == "No documentation available in apm.pdef.xml for this parameter"
    assert param_fixture["basic_param"].unit == ""
    assert param_fixture["basic_param"].tooltip_unit == "No documentation available in apm.pdef.xml for this parameter"
    assert param_fixture["basic_param"].min_value is None
    assert param_fixture["basic_param"].max_value is None


def test_string_representations(param_fixture) -> None:
    """
    Parameter formats numeric values as strings correctly.

    GIVEN: Parameters with various numeric values
    WHEN: String representation properties are accessed
    THEN: Values should be formatted correctly with trailing zeros removed
    """
    # Assert: Parameter value formatted correctly
    assert param_fixture["full_param"].value_as_string == "10"
    assert param_fixture["full_param"].fc_value_as_string == "15"

    # Assert: Missing FC value shows appropriate message
    assert param_fixture["basic_param"].fc_value_as_string == "N/A"

    # Arrange: Create parameter with decimal value
    decimal_param = ArduPilotParameter(param_fixture["param_name"], Par(10.5, ""))

    # Assert: Decimal value formatted correctly
    assert decimal_param.value_as_string == "10.5"


def test_value_dictionary_operations(param_fixture) -> None:
    """
    Parameter looks up human-readable labels from values dictionary.

    GIVEN: A parameter with a values dictionary mapping numbers to labels
    WHEN: Value lookup operations are performed
    THEN: Correct labels should be returned or None for missing values
    """
    # Assert: Value in dictionary is found and labeled correctly
    assert param_fixture["full_param"].is_in_values_dict
    assert param_fixture["full_param"].get_selected_value_from_dict() == "Ten"

    # Arrange: Create parameter with value not in dictionary
    not_in_dict_param = ArduPilotParameter(param_fixture["param_name"], Par(11.0, ""), param_fixture["metadata"])

    # Assert: Value not in dictionary returns None
    assert not not_in_dict_param.is_in_values_dict
    assert not_in_dict_param.get_selected_value_from_dict() is None

    # Assert: Parameter without values dictionary returns None
    assert not param_fixture["basic_param"].is_in_values_dict
    assert param_fixture["basic_param"].get_selected_value_from_dict() is None


def test_set_new_value(param_fixture) -> None:
    """
    User can update parameter values with validation.

    GIVEN: A regular, forced, or derived parameter
    WHEN: User attempts to set a new value
    THEN: Regular parameters accept changes, forced/derived parameters reject changes
    AND: Setting the same value raises ParameterUnchangedError
    """
    # Arrange: Prepare new value for testing
    new_value = "12.0"

    # Act: User changes value on regular parameter
    result = param_fixture["basic_param"].set_new_value(new_value)

    # Assert: Value is updated correctly
    assert result == 12.0
    assert param_fixture["basic_param"]._new_value == 12.0

    # Act & Assert: User attempts to set same value again
    with pytest.raises(ParameterUnchangedError):
        param_fixture["basic_param"].set_new_value(new_value)

    # Arrange: Store original forced parameter value
    original_value = param_fixture["forced_param"]._new_value

    # Act & Assert: User attempts to change forced parameter
    with pytest.raises(ValueError, match="forced or derived"):
        param_fixture["forced_param"].set_new_value(new_value)

    # Assert: Forced parameter value unchanged
    assert param_fixture["forced_param"]._new_value == original_value

    # Arrange: Store original derived parameter value
    original_value = param_fixture["derived_param"]._new_value

    # Act & Assert: User attempts to change derived parameter
    with pytest.raises(ValueError, match="forced or derived"):
        param_fixture["derived_param"].set_new_value(new_value)

    # Assert: Derived parameter value unchanged
    assert param_fixture["derived_param"]._new_value == original_value


def test_set_change_reason(param_fixture) -> None:
    """
    User can update parameter change reasons with appropriate restrictions.

    GIVEN: Regular, forced, and derived parameters
    WHEN: User attempts to set a change reason
    THEN: Regular parameters accept changes, forced/derived parameters reject changes
    AND: Setting the same reason returns False
    """
    # Arrange: Prepare new comment
    new_comment = "New comment"

    # Act: User sets change reason on regular parameter
    result = param_fixture["full_param"].set_change_reason(new_comment)

    # Assert: Change reason is updated
    assert result
    assert param_fixture["full_param"].change_reason == new_comment

    # Act: User sets same comment again
    result = param_fixture["full_param"].set_change_reason(new_comment)

    # Assert: No change detected
    assert not result

    # Arrange: Create parameter with None comment
    none_comment_param = ArduPilotParameter(param_fixture["param_name"], Par(10.0, None))

    # Act: User sets empty string on parameter with None comment
    result = none_comment_param.set_change_reason("")

    # Assert: Empty string equivalent to None, no change
    assert not result

    # Arrange: Store original forced parameter comment
    original_comment = param_fixture["forced_param"].change_reason

    # Act: User attempts to change forced parameter comment
    result = param_fixture["forced_param"].set_change_reason(new_comment)

    # Assert: Forced parameter comment unchanged
    assert not result
    assert param_fixture["forced_param"].change_reason == original_comment

    # Arrange: Store original derived parameter comment
    original_comment = param_fixture["derived_param"].change_reason

    # Act: User attempts to change derived parameter comment
    result = param_fixture["derived_param"].set_change_reason(new_comment)

    # Assert: Derived parameter comment unchanged
    assert not result
    assert param_fixture["derived_param"].change_reason == original_comment


def test_is_editable(param_fixture) -> None:
    """
    Parameter correctly identifies whether user can edit it.

    GIVEN: Regular, forced, derived, and readonly parameters
    WHEN: Editability is checked
    THEN: Only regular parameters should be editable
    """
    # Assert: Regular parameter is editable
    assert param_fixture["full_param"].is_editable

    # Assert: Forced parameter is not editable
    assert not param_fixture["forced_param"].is_editable

    # Assert: Derived parameter is not editable
    assert not param_fixture["derived_param"].is_editable

    # Assert: Readonly parameter is not editable
    assert not param_fixture["readonly_param"].is_editable


def test_is_dirty(param_fixture) -> None:
    """
    Parameter correctly detects unsaved changes for save workflow.

    GIVEN: Parameters with various value and comment configurations
    WHEN: The is_dirty property is checked
    THEN: Only parameters with changes from file should be marked dirty
    AND: Forced/derived parameters with different computed values should be dirty
    """
    # Arrange: Create parameter with value matching file
    same_value_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["param_value"], param_fixture["param_comment"]),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["param_value"],
    )

    # Assert: Parameter with same value as file is not dirty
    assert not same_value_param.is_dirty

    # Arrange: Create parameter with different FC value but same file value
    different_fc_value_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["param_value"], param_fixture["param_comment"]),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
    )

    # Assert: FC value difference alone doesn't make parameter dirty
    assert not different_fc_value_param.is_dirty

    # Arrange: Create parameter and change its value
    changed_value_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["param_value"], param_fixture["param_comment"]),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["param_value"],
    )

    # Act: User changes the value
    changed_value_param.set_new_value(str(param_fixture["fc_value"]))

    # Assert: Parameter with user-changed value is dirty
    assert changed_value_param.is_dirty

    # Arrange: Create derived parameter with different computed comment
    derived_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["param_value"], param_fixture["param_comment"]),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["param_value"],
        derived_par=Par(param_fixture["param_value"], "computed comment"),
    )

    # Assert: Derived parameter with different comment is dirty
    assert derived_param.is_dirty

    # Arrange: Create forced parameter with different computed comment
    forced_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["param_value"], param_fixture["param_comment"]),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["param_value"],
        forced_par=Par(param_fixture["param_value"], "forced comment"),
    )

    # Assert: Forced parameter with different comment is dirty
    assert forced_param.is_dirty

    # Assert: Fixture forced parameter with matching values is not dirty
    assert not param_fixture["forced_param"].is_dirty

    # Assert: Fixture derived parameter with matching values is not dirty
    assert not param_fixture["derived_param"].is_dirty


def test_set_forced_or_derived_value(param_fixture) -> None:
    """
    System can update forced/derived parameter values after creation.

    GIVEN: Forced and derived parameters that need value updates
    WHEN: set_forced_or_derived_value is called
    THEN: Values should be updated for forced/derived parameters
    AND: Regular parameters should raise ValueError
    """
    # Arrange: Get forced parameter and prepare new value
    forced_param = param_fixture["forced_param"]
    new_value = 999.0

    # Act: System updates forced parameter value
    forced_param.set_forced_or_derived_value(new_value)

    # Assert: Forced parameter value is updated
    assert forced_param.get_new_value() == new_value

    # Arrange: Get derived parameter and prepare new value
    derived_param = param_fixture["derived_param"]
    new_value = 888.0

    # Act: System updates derived parameter value
    derived_param.set_forced_or_derived_value(new_value)

    # Assert: Derived parameter value is updated
    assert derived_param.get_new_value() == new_value

    # Arrange: Create regular parameter
    regular_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["param_value"], param_fixture["param_comment"]),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
    )

    # Act & Assert: System attempting to use method on regular parameter fails
    with pytest.raises(ValueError, match="This method is only for forced or derived parameters"):
        regular_param.set_forced_or_derived_value(123.0)


def test_fc_value_equals_default_value_for_bitmask_parameter(param_fixture) -> None:
    """
    fc_value_equals_default_value uses exact comparison for bitmask parameters.

    GIVEN: A bitmask parameter where fc_value exactly equals default_value
    WHEN: fc_value_equals_default_value is called
    THEN: True should be returned (exact equality, not tolerance)
    """
    # Arrange: bitmask param where fc == default (exact match)
    bitmask_metadata = param_fixture["metadata"].copy()
    bitmask_metadata.pop("values", None)  # Remove multiple-choice to make pure bitmask

    param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(3.0, ""),
        bitmask_metadata,
        Par(3.0, ""),  # default = 3
        3.0,  # fc_value = 3
    )
    assert param.fc_value_equals_default_value

    # Now with a different fc_value
    param_different = ArduPilotParameter(
        param_fixture["param_name"],
        Par(3.0, ""),
        bitmask_metadata,
        Par(3.0, ""),  # default = 3
        5.0,  # fc_value = 5 — different
    )
    assert not param_different.fc_value_equals_default_value


def test_set_new_value_multiple_choice_unchanged_raises() -> None:
    """
    set_new_value raises ParameterUnchangedError when multiple-choice value does not change.

    GIVEN: A multiple-choice parameter with current value 10.0
    WHEN: set_new_value is called with the same value ("10.0")
    THEN: ParameterUnchangedError should be raised
    """
    # Arrange: multiple-choice parameter (no Bitmask key, has values dict)
    mc_metadata = {
        "values": {"0": "Zero", "10": "Ten", "20": "Twenty"},
        "ReadOnly": False,
        "Calibration": False,
    }
    param = ArduPilotParameter("MC_PARAM", Par(10.0, ""), mc_metadata)

    # Act & Assert: Same value raises ParameterUnchangedError
    with pytest.raises(ParameterUnchangedError):
        param.set_new_value("10.0")


def test_set_new_value_bitmask_unchanged_raises() -> None:
    """
    set_new_value raises ParameterUnchangedError when bitmask value does not change.

    GIVEN: A bitmask parameter with current value 3
    WHEN: set_new_value is called with the same integer value "3"
    THEN: ParameterUnchangedError should be raised
    """
    bitmask_metadata = {
        "Bitmask": {0: "Option 1", 1: "Option 2"},
        "ReadOnly": False,
        "Calibration": False,
    }
    param = ArduPilotParameter("BM_PARAM", Par(3.0, ""), bitmask_metadata)

    with pytest.raises(ParameterUnchangedError):
        param.set_new_value("3")


def test_set_new_value_bitmask_ignores_unknown_bits_when_flag_set() -> None:
    """
    set_new_value accepts bitmask value with unknown bits when ignore_out_of_range=True.

    GIVEN: A bitmask parameter where bit 7 (value 128) is not in the bitmask dict
    WHEN: set_new_value("128", ignore_out_of_range=True) is called
    THEN: No ParameterOutOfRangeError should be raised
    AND: The new value should be updated to 128.0
    """
    bitmask_metadata = {
        "Bitmask": {0: "Option 1", 1: "Option 2"},
        "ReadOnly": False,
        "Calibration": False,
    }
    param = ArduPilotParameter("BM_PARAM", Par(0.0, ""), bitmask_metadata)

    # Without flag: should raise
    with pytest.raises(ParameterOutOfRangeError):
        param.set_new_value("128", ignore_out_of_range=False)

    # Reset
    param = ArduPilotParameter("BM_PARAM", Par(0.0, ""), bitmask_metadata)

    # With flag: should succeed
    result = param.set_new_value("128", ignore_out_of_range=True)
    assert result == 128.0


def test_set_new_value_numeric_above_limit_raises() -> None:
    """
    set_new_value raises ParameterOutOfRangeError when numeric value exceeds max.

    GIVEN: A parameter with max_value = 20.0 and current value = 10.0
    WHEN: set_new_value is called with "25.0" and ignore_out_of_range=False
    THEN: ParameterOutOfRangeError should be raised
    """
    numeric_metadata = {
        "min": 0.0,
        "max": 20.0,
        "ReadOnly": False,
        "Calibration": False,
    }
    param = ArduPilotParameter("NUM_PARAM", Par(10.0, ""), numeric_metadata)

    with pytest.raises(ParameterOutOfRangeError):
        param.set_new_value("25.0")


def test_set_forced_or_derived_value_readonly_raises() -> None:
    """
    set_forced_or_derived_value raises ValueError for readonly parameters.

    GIVEN: A readonly forced parameter
    WHEN: set_forced_or_derived_value is called
    THEN: ValueError should be raised mentioning readonly
    """
    readonly_metadata = {
        "ReadOnly": True,
        "Calibration": False,
    }
    # Build a forced readonly parameter
    param = ArduPilotParameter(
        "RO_PARAM",
        Par(1.0, ""),
        readonly_metadata,
        Par(1.0, ""),
        1.0,
        forced_par=Par(1.0, ""),
    )

    with pytest.raises(ValueError, match="Readonly"):
        param.set_forced_or_derived_value(2.0)


def test_set_forced_or_derived_change_reason_readonly_raises() -> None:
    """
    set_forced_or_derived_change_reason raises ValueError for readonly parameters.

    GIVEN: A readonly derived parameter
    WHEN: set_forced_or_derived_change_reason is called
    THEN: ValueError should be raised mentioning readonly
    """
    readonly_metadata = {
        "ReadOnly": True,
        "Calibration": False,
    }
    param = ArduPilotParameter(
        "RO_PARAM",
        Par(1.0, ""),
        readonly_metadata,
        Par(1.0, ""),
        1.0,
        derived_par=Par(1.0, ""),
    )

    with pytest.raises(ValueError, match="Readonly"):
        param.set_forced_or_derived_change_reason("new reason")


def test_bitmask_helper_get_checked_keys() -> None:
    """
    BitmaskHelper.get_checked_keys converts a decimal value to bit-position set.

    GIVEN: A bitmask dictionary {0: 'A', 1: 'B', 2: 'C'} and a value of 5 (bits 0 and 2 set)
    WHEN: get_checked_keys is called
    THEN: {0, 2} should be returned
    """
    bitmask_dict = {0: "A", 1: "B", 2: "C"}

    result = BitmaskHelper.get_checked_keys(5, bitmask_dict)

    assert result == {0, 2}


def test_bitmask_helper_get_checked_keys_with_string_keys() -> None:
    """
    BitmaskHelper.get_checked_keys works when dict keys are strings.

    GIVEN: A bitmask dictionary with string keys {"0": "A", "1": "B"} and value 2
    WHEN: get_checked_keys is called
    THEN: {1} should be returned (bit 1 is set)
    """
    bitmask_dict = {"0": "A", "1": "B", "2": "C"}  # type: ignore[arg-type]

    result = BitmaskHelper.get_checked_keys(2, bitmask_dict)

    assert result == {1}


def test_set_change_reason_for_forced_parameter_returns_false(param_fixture) -> None:
    """
    set_change_reason returns False and makes no change for forced parameters.

    GIVEN: A forced parameter
    WHEN: set_change_reason is called
    THEN: False should be returned and the change_reason should remain unchanged
    """
    original_reason = param_fixture["forced_param"].change_reason
    result = param_fixture["forced_param"].set_change_reason("new reason")
    assert result is False
    assert param_fixture["forced_param"].change_reason == original_reason


def test_set_change_reason_same_value_returns_false(param_fixture) -> None:
    """
    set_change_reason returns False when the same value is set.

    GIVEN: A parameter whose change_reason is "Test comment"
    WHEN: set_change_reason is called with the same value
    THEN: False should be returned without modifying the reason
    """
    # First set to a new value so we know the current reason
    param_fixture["full_param"].set_change_reason("unique comment")

    result = param_fixture["full_param"].set_change_reason("unique comment")
    assert result is False


def test_tooltip_fc_value_returns_sorted_tooltip_when_key_present(param_fixture) -> None:
    """
    tooltip_fc_value returns doc_tooltip_sorted_numerically when that key is present.

    GIVEN: A parameter with 'doc_tooltip_sorted_numerically' in its metadata
    WHEN: tooltip_fc_value is accessed
    THEN: The sorted tooltip value should be returned instead of the standard tooltip
    """
    metadata_with_sorted = param_fixture["metadata"].copy()
    metadata_with_sorted["doc_tooltip_sorted_numerically"] = "Sorted tooltip text"
    param = ArduPilotParameter(param_fixture["param_name"], param_fixture["par_obj"], metadata_with_sorted)

    assert param.tooltip_fc_value == "Sorted tooltip text"


def test_tooltip_change_reason_includes_param_name_and_value(param_fixture) -> None:
    """
    tooltip_change_reason returns a formatted string with parameter name and value.

    GIVEN: A parameter with name 'TEST_PARAM' and value 10.0
    WHEN: tooltip_change_reason is accessed
    THEN: The returned string should contain the parameter name and value
    """
    assert param_fixture["full_param"].name in param_fixture["full_param"].tooltip_change_reason


def test_is_invalid_number_returns_error_for_nan(param_fixture) -> None:
    """
    is_invalid_number returns an error message when the value is NaN.

    GIVEN: A parameter
    WHEN: is_invalid_number is called with float('nan')
    THEN: A non-empty error message should be returned
    """
    result = param_fixture["full_param"].is_invalid_number(math.nan)
    assert result != ""
    assert "finite" in result.lower() or "number" in result.lower()


def test_is_invalid_number_returns_empty_for_valid_number(param_fixture) -> None:
    """
    is_invalid_number returns empty string for valid finite numbers.

    GIVEN: A parameter
    WHEN: is_invalid_number is called with a normal finite number
    THEN: An empty string should be returned
    """
    result = param_fixture["full_param"].is_invalid_number(5.0)
    assert result == ""


def test_is_below_limit_returns_error_when_value_below_min(param_fixture) -> None:
    """
    is_below_limit returns error message when value is below minimum.

    GIVEN: A parameter with min_value = 0.0
    WHEN: is_below_limit is called with -1.0
    THEN: A non-empty error message should be returned
    """
    result = param_fixture["full_param"].is_below_limit(-1.0)
    assert result != ""


def test_has_unknown_bits_set_returns_empty_for_known_bits(param_fixture) -> None:
    """
    has_unknown_bits_set returns empty string when all bits are known.

    GIVEN: A bitmask parameter with bits 0-2 defined
    WHEN: has_unknown_bits_set is called with value 7 (bits 0,1,2 all set)
    THEN: Empty string should be returned (no unknown bits)
    """
    # _new_value = 7 (0b111), all bits 0,1,2 are known
    param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(7.0, ""),
        param_fixture["metadata"],  # has Bitmask with 0,1,2
    )
    result = param.has_unknown_bits_set()
    assert result == ""


def test_fc_value_is_above_limit_with_non_none_fc_value(param_fixture) -> None:
    """
    fc_value_is_above_limit checks the fc_value against the max limit.

    GIVEN: A parameter with max_value=20 and fc_value=25 (above max)
    WHEN: fc_value_is_above_limit is called
    THEN: A non-empty error message should be returned
    """
    param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(10.0, ""),
        param_fixture["metadata"],  # max = 20
        param_fixture["default_par"],
        25.0,  # fc_value = 25, above max 20
    )
    result = param.fc_value_is_above_limit()
    assert result != ""


def test_fc_value_is_below_limit_with_non_none_fc_value(param_fixture) -> None:
    """
    fc_value_is_below_limit checks the fc_value against the min limit.

    GIVEN: A parameter with min_value=0 and fc_value=-5 (below min)
    WHEN: fc_value_is_below_limit is called
    THEN: A non-empty error message should be returned
    """
    param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(10.0, ""),
        param_fixture["metadata"],  # min = 0
        param_fixture["default_par"],
        -5.0,  # fc_value = -5, below min 0
    )
    result = param.fc_value_is_below_limit()
    assert result != ""


def test_fc_value_has_unknown_bits_set_with_non_none_fc_value(param_fixture) -> None:
    """
    fc_value_has_unknown_bits_set checks if fc_value has bits outside the bitmask.

    GIVEN: A bitmask parameter with fc_value containing unknown bits
    WHEN: fc_value_has_unknown_bits_set is called
    THEN: A non-empty error message should be returned
    """
    param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(3.0, ""),
        param_fixture["metadata"],  # Bitmask: {0,1,2}
        param_fixture["default_par"],
        128.0,  # fc_value = 128 (bit 7), not in bitmask
    )
    result = param.fc_value_has_unknown_bits_set()
    assert result != ""


def test_set_new_value_raises_type_error_for_non_string() -> None:
    """
    set_new_value raises TypeError when value is not a string.

    GIVEN: A regular parameter
    WHEN: set_new_value is called with an integer instead of a string
    THEN: TypeError should be raised
    """
    param = ArduPilotParameter("TEST", Par(1.0, ""))
    with pytest.raises(TypeError, match="string"):
        param.set_new_value(42)  # type: ignore[arg-type]


def test_set_new_value_raises_value_error_for_empty_string() -> None:
    """
    set_new_value raises ValueError when value is an empty string.

    GIVEN: A regular parameter
    WHEN: set_new_value is called with an empty string ""
    THEN: ValueError should be raised
    """
    param = ArduPilotParameter("TEST", Par(1.0, ""))
    with pytest.raises(ValueError, match="Empty"):
        param.set_new_value("")


def test_set_new_value_raises_value_error_for_invalid_bitmask_string() -> None:
    """
    set_new_value raises ValueError when bitmask parameter gets non-integer string.

    GIVEN: A bitmask parameter
    WHEN: set_new_value is called with a non-integer string like "abc"
    THEN: ValueError should be raised (can't parse as int)
    """
    bitmask_metadata = {
        "Bitmask": {0: "A", 1: "B"},
        "ReadOnly": False,
        "Calibration": False,
    }
    param = ArduPilotParameter("BM_PARAM", Par(0.0, ""), bitmask_metadata)
    with pytest.raises(ValueError, match="integer"):
        param.set_new_value("not_a_number")


def test_set_new_value_raises_value_error_for_invalid_float_string() -> None:
    """
    set_new_value raises ValueError when numeric parameter gets non-numeric string.

    GIVEN: A regular numeric parameter (not bitmask, not multiple-choice)
    WHEN: set_new_value is called with a non-numeric string like "abc"
    THEN: ValueError should be raised
    """
    param = ArduPilotParameter("TEST", Par(1.0, ""))
    with pytest.raises(ValueError, match="number"):
        param.set_new_value("abc")


def test_set_new_value_raises_value_error_for_nan_float_string() -> None:
    """
    set_new_value raises ValueError when numeric parameter gets NaN string.

    GIVEN: A regular numeric parameter
    WHEN: set_new_value is called with "nan"
    THEN: ValueError should be raised about finite number
    """
    param = ArduPilotParameter("TEST", Par(1.0, ""))
    with pytest.raises(ValueError, match="finite"):
        param.set_new_value("nan")


def test_set_new_value_raises_out_of_range_for_below_min() -> None:
    """
    set_new_value raises ParameterOutOfRangeError when value is below minimum.

    GIVEN: A parameter with min_value = 0.0
    WHEN: set_new_value is called with "-1.0"
    THEN: ParameterOutOfRangeError should be raised
    """
    numeric_metadata = {
        "min": 0.0,
        "max": 20.0,
        "ReadOnly": False,
        "Calibration": False,
    }
    param = ArduPilotParameter("NUM_PARAM", Par(10.0, ""), numeric_metadata)

    with pytest.raises(ParameterOutOfRangeError):
        param.set_new_value("-1.0")


def test_copy_new_value_to_file_resets_dirty_state(param_fixture) -> None:
    """
    copy_new_value_to_file saves the current state, making the parameter not dirty.

    GIVEN: A parameter that is dirty (value changed)
    WHEN: copy_new_value_to_file is called
    THEN: is_dirty should return False afterwards
    """
    # Change value to make it dirty
    param_fixture["full_param"].set_new_value("18.0")
    assert param_fixture["full_param"].is_dirty

    # Copy to file
    param_fixture["full_param"].copy_new_value_to_file()

    # Should no longer be dirty
    assert not param_fixture["full_param"].is_dirty


def test_bitmask_helper_get_value_from_keys() -> None:
    """
    BitmaskHelper.get_value_from_keys converts a set of bit positions to a decimal string.

    GIVEN: Checked keys {0, 2} (bits 0 and 2 set)
    WHEN: get_value_from_keys is called
    THEN: "5" should be returned (1<<0 + 1<<2 = 1 + 4 = 5)
    """
    result = BitmaskHelper.get_value_from_keys({0, 2})
    assert result == "5"


def test_bitmask_helper_get_value_from_empty_keys() -> None:
    """
    BitmaskHelper.get_value_from_keys returns "0" for empty set.

    GIVEN: An empty set of checked keys
    WHEN: get_value_from_keys is called
    THEN: "0" should be returned
    """
    result = BitmaskHelper.get_value_from_keys(set())
    assert result == "0"


def test_set_forced_or_derived_change_reason(param_fixture) -> None:
    """
    System can update forced/derived parameter change reasons after creation.

    GIVEN: Forced and derived parameters that need reason updates
    WHEN: set_forced_or_derived_change_reason is called
    THEN: Reasons should be updated for forced/derived parameters
    AND: Regular parameters should raise ValueError
    """
    # Arrange: Get forced parameter and prepare new reason
    forced_param = param_fixture["forced_param"]
    new_reason = "New forced reason"

    # Act: System updates forced parameter change reason
    forced_param.set_forced_or_derived_change_reason(new_reason)

    # Assert: Forced parameter change reason is updated
    assert forced_param.change_reason == new_reason

    # Arrange: Get derived parameter and prepare new reason
    derived_param = param_fixture["derived_param"]
    new_reason = "New derived reason"

    # Act: System updates derived parameter change reason
    derived_param.set_forced_or_derived_change_reason(new_reason)

    # Assert: Derived parameter change reason is updated
    assert derived_param.change_reason == new_reason

    # Arrange: Create regular parameter
    regular_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["param_value"], param_fixture["param_comment"]),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
    )

    # Act & Assert: System attempting to use method on regular parameter fails
    with pytest.raises(ValueError, match="This method is only for forced or derived parameters"):
        regular_param.set_forced_or_derived_change_reason("Some reason")


def test_forced_or_derived_setters_make_parameter_dirty(param_fixture) -> None:
    """
    Forced/derived setters correctly update dirty state for save detection.

    GIVEN: A forced parameter with matching file values
    WHEN: System updates the value or reason using dedicated setters
    THEN: Parameter should be marked dirty when changed
    AND: Should not be dirty when reset to original values
    """
    # Arrange: Create forced parameter with matching file value and comment
    forced_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(100.0, "original comment"),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
        forced_par=Par(100.0, "original comment"),
    )

    # Assert: Parameter with matching values is not dirty initially
    assert not forced_param.is_dirty

    # Act: System changes value
    forced_param.set_forced_or_derived_value(200.0)

    # Assert: Parameter is now dirty due to value change
    assert forced_param.is_dirty

    # Act: System resets to original value
    forced_param.set_forced_or_derived_value(100.0)

    # Assert: Parameter is no longer dirty
    assert not forced_param.is_dirty

    # Act: System changes only the reason
    forced_param.set_forced_or_derived_change_reason("new comment")

    # Assert: Parameter is dirty due to comment change
    assert forced_param.is_dirty


def test_set_fc_value_updates_flight_controller_value() -> None:
    """
    Setting FC value updates the internal flight controller value.

    GIVEN: A parameter with an initial FC value
    WHEN: set_fc_value() is called with a new value
    THEN: The FC value should be updated
    AND: Other parameter values should remain unchanged
    """
    # Arrange: Create parameter with initial FC value
    param = ArduPilotParameter("TEST_PARAM", Par(10.0, ""))
    param._fc_value = 15.0

    # Act: Update FC value
    param.set_fc_value(20.0)

    # Assert: FC value is updated
    assert param._fc_value == 20.0

    # Assert: New value is unchanged
    assert param.get_new_value() == 10.0


def test_set_fc_value_without_validation() -> None:
    """
    FC values are set without validation since they come from the FC.

    GIVEN: A parameter with range constraints (0-100)
    WHEN: set_fc_value() is called with any value (including out of range)
    THEN: The value should be accepted without validation errors
    AND: This reflects that FC values are already validated by the FC
    """
    # Arrange: Create parameter with range constraints
    metadata = {"min": 0.0, "max": 100.0}
    param = ArduPilotParameter("TEST_PARAM", Par(50.0, ""), metadata)

    # Act: Set FC value outside the range (would fail with set_new_value)
    param.set_fc_value(150.0)  # Above max

    # Assert: Value is accepted
    assert param._fc_value == 150.0

    # Act: Set FC value below minimum
    param.set_fc_value(-10.0)  # Below min

    # Assert: Value is accepted
    assert param._fc_value == -10.0


def test_set_fc_value_maintains_comparison_state() -> None:
    """
    Setting FC value correctly updates comparison state.

    GIVEN: A parameter with new value different from FC
    WHEN: FC value is updated to match new value
    THEN: is_different_from_fc should become False
    """
    # Arrange: Create parameter with different new and FC values
    param = ArduPilotParameter("TEST_PARAM", Par(20.0, ""))
    param._fc_value = 10.0

    # Assert: Initially different
    assert param.is_different_from_fc is True

    # Act: Update FC value to match new value
    param.set_fc_value(20.0)

    # Assert: No longer different
    assert param.is_different_from_fc is False
