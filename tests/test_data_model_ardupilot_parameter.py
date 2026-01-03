#!/usr/bin/env python3

"""
Unit tests for the ArduPilotParameter domain model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import (
    ArduPilotParameter,
    ParameterUnchangedError,
)
from ardupilot_methodic_configurator.data_model_par_dict import Par

# pylint: disable=redefined-outer-name, protected-access


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
