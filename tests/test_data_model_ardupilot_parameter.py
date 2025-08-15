#!/usr/bin/python3

"""
Unit tests for the ArduPilotParameter domain model.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import (
    ArduPilotParameter,
    ParameterUnchangedError,
)

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
    forced_param = ArduPilotParameter(param_name, par_obj, metadata, default_par, fc_value, forced_par=Par(16.0, ""))

    # Derived parameter
    derived_param = ArduPilotParameter(param_name, par_obj, metadata, default_par, fc_value, derived_par=Par(17.0, ""))

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
    """Test that basic properties are set correctly."""
    assert param_fixture["full_param"].name == param_fixture["param_name"]
    assert param_fixture["full_param"]._new_value == param_fixture["param_value"]
    assert param_fixture["full_param"].change_reason == param_fixture["param_comment"]
    assert param_fixture["full_param"]._default_value == param_fixture["default_value"]
    assert param_fixture["full_param"]._fc_value == param_fixture["fc_value"]
    assert not param_fixture["full_param"].is_forced
    assert not param_fixture["full_param"].is_derived


def test_parameter_type_properties(param_fixture) -> None:
    """Test properties that identify parameter types."""
    assert param_fixture["readonly_param"].is_readonly
    assert not param_fixture["full_param"].is_readonly

    assert param_fixture["calibration_param"].is_calibration
    assert not param_fixture["full_param"].is_calibration

    assert param_fixture["full_param"].is_bitmask

    # Create a parameter without bitmask
    no_bitmask_metadata = param_fixture["metadata"].copy()
    no_bitmask_metadata.pop("Bitmask")
    no_bitmask_param = ArduPilotParameter(param_fixture["param_name"], param_fixture["par_obj"], no_bitmask_metadata)
    assert not no_bitmask_param.is_bitmask


def test_value_comparisons(param_fixture) -> None:
    """Test comparison between values."""
    # Test default value comparison
    assert not param_fixture["full_param"].new_value_equals_default_value
    default_value_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["default_value"], ""),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
    )
    assert default_value_param.new_value_equals_default_value

    # Test FC value existence
    assert param_fixture["full_param"].has_fc_value
    assert not param_fixture["basic_param"].has_fc_value

    # Test difference from FC
    assert param_fixture["full_param"].is_different_from_fc
    same_as_fc_param = ArduPilotParameter(
        param_fixture["param_name"],
        Par(param_fixture["fc_value"], ""),
        param_fixture["metadata"],
        param_fixture["default_par"],
        param_fixture["fc_value"],
    )
    assert not same_as_fc_param.is_different_from_fc


def test_metadata_properties(param_fixture) -> None:
    """Test metadata properties."""
    assert param_fixture["full_param"].tooltip_new_value == param_fixture["metadata"]["doc_tooltip"]
    assert param_fixture["full_param"].unit == param_fixture["metadata"]["unit"]
    assert param_fixture["full_param"].tooltip_unit == param_fixture["metadata"]["unit_tooltip"]
    assert param_fixture["full_param"].min_value == float(param_fixture["metadata"]["min"])
    assert param_fixture["full_param"].max_value == float(param_fixture["metadata"]["max"])

    # Test with missing metadata
    assert param_fixture["basic_param"].tooltip_new_value == "No documentation available in apm.pdef.xml for this parameter"
    assert param_fixture["basic_param"].unit == ""
    assert param_fixture["basic_param"].tooltip_unit == "No documentation available in apm.pdef.xml for this parameter"
    assert param_fixture["basic_param"].min_value is None
    assert param_fixture["basic_param"].max_value is None


def test_string_representations(param_fixture) -> None:
    """Test string representation of values."""
    assert param_fixture["full_param"].value_as_string == "10"
    assert param_fixture["full_param"].fc_value_as_string == "15"

    # Test with no FC value
    assert param_fixture["basic_param"].fc_value_as_string == "N/A"

    # Test with decimal places
    decimal_param = ArduPilotParameter(param_fixture["param_name"], Par(10.5, ""))
    assert decimal_param.value_as_string == "10.5"


def test_value_dictionary_operations(param_fixture) -> None:
    """Test operations involving the values dictionary."""
    # Value in dictionary
    assert param_fixture["full_param"].is_in_values_dict
    assert param_fixture["full_param"].get_selected_value_from_dict() == "Ten"

    # Value not in dictionary
    not_in_dict_param = ArduPilotParameter(param_fixture["param_name"], Par(11.0, ""), param_fixture["metadata"])
    assert not not_in_dict_param.is_in_values_dict
    assert not_in_dict_param.get_selected_value_from_dict() is None

    # No values dictionary
    assert not param_fixture["basic_param"].is_in_values_dict
    assert param_fixture["basic_param"].get_selected_value_from_dict() is None


def test_set_new_value(param_fixture) -> None:
    """Test setting parameter values."""
    # Regular parameter: use a non-bitmask parameter and provide string input
    new_value = "12.0"
    result = param_fixture["basic_param"].set_new_value(new_value)
    assert result == 12.0
    assert param_fixture["basic_param"]._new_value == 12.0

    # Same value - should raise ParameterUnchangedError
    with pytest.raises(ParameterUnchangedError):
        param_fixture["basic_param"].set_new_value(new_value)

    # Forced parameter - should raise ValueError and not change
    original_value = param_fixture["forced_param"]._new_value
    with pytest.raises(ValueError, match="forced or derived"):
        param_fixture["forced_param"].set_new_value(new_value)
    assert param_fixture["forced_param"]._new_value == original_value

    # Derived parameter - should raise ValueError and not change
    original_value = param_fixture["derived_param"]._new_value
    with pytest.raises(ValueError, match="forced or derived"):
        param_fixture["derived_param"].set_new_value(new_value)
    assert param_fixture["derived_param"]._new_value == original_value


def test_set_change_reason(param_fixture) -> None:
    """Test setting parameter comments."""
    # Regular parameter
    new_comment = "New comment"
    result = param_fixture["full_param"].set_change_reason(new_comment)
    assert result
    assert param_fixture["full_param"].change_reason == new_comment

    # Same comment - should return False for no change
    result = param_fixture["full_param"].set_change_reason(new_comment)
    assert not result

    # Empty string when comment is None
    none_comment_param = ArduPilotParameter(param_fixture["param_name"], Par(10.0, None))
    result = none_comment_param.set_change_reason("")
    assert not result

    # Forced parameter - should return False and not change
    original_comment = param_fixture["forced_param"].change_reason
    result = param_fixture["forced_param"].set_change_reason(new_comment)
    assert not result
    assert param_fixture["forced_param"].change_reason == original_comment

    # Derived parameter - should return False and not change
    original_comment = param_fixture["derived_param"].change_reason
    result = param_fixture["derived_param"].set_change_reason(new_comment)
    assert not result
    assert param_fixture["derived_param"].change_reason == original_comment


def test_is_editable(param_fixture) -> None:
    """Test checking if a parameter is editable."""
    assert param_fixture["full_param"].is_editable
    assert not param_fixture["forced_param"].is_editable
    assert not param_fixture["derived_param"].is_editable
    assert not param_fixture["readonly_param"].is_editable
