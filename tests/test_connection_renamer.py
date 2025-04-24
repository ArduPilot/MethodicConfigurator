#!/usr/bin/python3

"""
Unit tests for the ConnectionRenamer class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.ardupilot_parameter import ConnectionRenamer

# pylint: disable=redefined-outer-name


@pytest.fixture
def connection_params() -> dict[str, Any]:
    """Set up test parameters for connection renaming."""
    # Sample parameter names for different connection types
    can_parameters = ["CAN_P1_DRIVER", "CAN_P1_BITRATE", "CAN_D1_PROTOCOL", "CAN_D1_UC_NODE", "CAN_D1_UC_OPTION"]
    serial_parameters = ["SERIAL1_PROTOCOL", "SERIAL1_BAUD", "SERIAL1_OPTIONS", "SERIAL2_PROTOCOL", "SERIAL2_BAUD"]
    mixed_parameters = can_parameters + serial_parameters

    # Sample parameter objects dictionary
    param_objects = {}
    for param_name in mixed_parameters:
        param_objects[param_name] = Par(value=1.0, comment=f"Comment for {param_name}")

    return {
        "can_parameters": can_parameters,
        "serial_parameters": serial_parameters,
        "mixed_parameters": mixed_parameters,
        "param_objects": param_objects,
    }


def test_generate_renames_can(connection_params) -> None:
    """Test generating renames for CAN parameters."""
    # Test renaming CAN1 to CAN2
    renames = ConnectionRenamer.generate_renames(connection_params["can_parameters"], "CAN2")

    expected_renames = {
        "CAN_P1_DRIVER": "CAN_P2_DRIVER",
        "CAN_P1_BITRATE": "CAN_P2_BITRATE",
        "CAN_D1_PROTOCOL": "CAN_D2_PROTOCOL",
        "CAN_D1_UC_NODE": "CAN_D2_UC_NODE",
        "CAN_D1_UC_OPTION": "CAN_D2_UC_OPTION",
    }

    for k, v in expected_renames.items():
        assert renames.get(k) == v

    # Test with CAN parameters that don't match the target prefix
    renames = ConnectionRenamer.generate_renames(["CAN_P3_DRIVER", "CAN_D3_PROTOCOL"], "CAN2")
    # Should rename to CAN2 versions if pattern matches
    assert renames == {
        "CAN_P3_DRIVER": "CAN_P2_DRIVER",
        "CAN_D3_PROTOCOL": "CAN_D2_PROTOCOL",
    }


def test_generate_renames_serial(connection_params) -> None:
    """Test generating renames for SERIAL parameters."""
    # Test renaming SERIAL1 to SERIAL3
    renames = ConnectionRenamer.generate_renames(connection_params["serial_parameters"], "SERIAL3")

    expected_renames = {
        "SERIAL1_PROTOCOL": "SERIAL3_PROTOCOL",
        "SERIAL1_BAUD": "SERIAL3_BAUD",
        "SERIAL1_OPTIONS": "SERIAL3_OPTIONS",
        "SERIAL2_PROTOCOL": "SERIAL3_PROTOCOL",
        "SERIAL2_BAUD": "SERIAL3_BAUD",
    }

    for old_name, new_name in expected_renames.items():
        assert renames.get(old_name) == new_name

    # All SERIAL* parameters are renamed to SERIAL3_*
    assert set(renames.values()) == {"SERIAL3_PROTOCOL", "SERIAL3_BAUD", "SERIAL3_OPTIONS"}


def test_apply_renames_without_duplicates(connection_params) -> None:
    """Test applying renames without any duplicate parameters."""
    # Create a copy to avoid modifying the original
    params = connection_params["param_objects"].copy()

    # Apply renames for CAN1 to CAN2
    duplicated_names, renamed_pairs = ConnectionRenamer.apply_renames(params, "CAN2")

    # Check that the parameters were renamed correctly
    assert "CAN_P2_DRIVER" in params
    assert "CAN_D2_PROTOCOL" in params
    assert "CAN_P1_DRIVER" not in params
    assert "CAN_D1_PROTOCOL" not in params

    # Check that only CAN parameters were renamed
    assert "SERIAL1_PROTOCOL" in params
    assert "SERIAL2_BAUD" in params

    # Check renamed pairs
    renamed_dict = dict(renamed_pairs)
    assert renamed_dict["CAN_P1_DRIVER"] == "CAN_P2_DRIVER"
    assert renamed_dict["CAN_D1_PROTOCOL"] == "CAN_D2_PROTOCOL"


def test_apply_renames_with_duplicates(connection_params) -> None:
    """Test applying renames with duplicate parameters."""
    # Create params with potential duplicates
    params = connection_params["param_objects"].copy()

    # Add a parameter that would cause a duplicate after renaming
    params["CAN_P2_DRIVER"] = Par(value=2.0, comment="Already exists")

    # Apply renames for CAN1 to CAN2
    duplicated_params, renamed_pairs = ConnectionRenamer.apply_renames(params, "CAN2")

    # Check that CAN_P1_DRIVER was removed to avoid duplicates
    assert "CAN_P1_DRIVER" not in params

    # Check that the duplicate key is not present after renaming (both removed)
    assert "CAN_P2_DRIVER" not in params

    # Check that other CAN2 parameters are present
    assert "CAN_D2_PROTOCOL" in params
    assert "CAN_P2_BITRATE" in params


def test_apply_renames_with_variables(connection_params) -> None:
    """Test applying renames with variable evaluation."""
    # Create variables dictionary
    variables: dict[str, Any] = {"selected_can": "CAN3"}

    # Create a copy to avoid modifying the original
    params = connection_params["param_objects"].copy()

    # Apply renames with variables
    duplicated_params, renamed_pairs = ConnectionRenamer.apply_renames(params, "selected_can", variables)

    # Check that the parameters were renamed correctly using the evaluated variable
    assert "CAN_P3_DRIVER" in params
    assert "CAN_D3_PROTOCOL" in params
    assert "CAN_P1_DRIVER" not in params
    assert "CAN_D1_PROTOCOL" not in params

    # Check renamed pairs
    renamed_dict = dict(renamed_pairs)
    assert renamed_dict["CAN_P1_DRIVER"] == "CAN_P3_DRIVER"
    assert renamed_dict["CAN_D1_PROTOCOL"] == "CAN_D3_PROTOCOL"
