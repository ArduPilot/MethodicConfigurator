#!/usr/bin/python3

"""
Unit tests for the BitmaskHelper class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import BitmaskHelper

# pylint: disable=redefined-outer-name


@pytest.fixture
def bitmask_dict() -> dict[int, str]:
    """Create a sample bitmask dictionary for testing."""
    return {
        0: "Option 1",  # 2^0 = 1
        1: "Option 2",  # 2^1 = 2
        2: "Option 3",  # 2^2 = 4
        3: "Option 4",  # 2^3 = 8
        4: "Option 5",  # 2^4 = 16
    }


def test_get_checked_keys(bitmask_dict) -> None:
    """Test getting checked keys from a decimal value."""
    # Test with no bits set
    keys = BitmaskHelper.get_checked_keys(0, bitmask_dict)
    assert keys == set()

    # Test with single bit set
    keys = BitmaskHelper.get_checked_keys(1, bitmask_dict)
    assert keys == {0}

    # Test with multiple bits set
    keys = BitmaskHelper.get_checked_keys(7, bitmask_dict)  # 1 + 2 + 4 = 7
    assert keys == {0, 1, 2}

    # Test with all bits set
    keys = BitmaskHelper.get_checked_keys(31, bitmask_dict)  # 1 + 2 + 4 + 8 + 16 = 31
    assert keys == {0, 1, 2, 3, 4}

    # Test with some bits set
    keys = BitmaskHelper.get_checked_keys(18, bitmask_dict)  # 2 + 16 = 18
    assert keys == {1, 4}


def test_get_value_from_keys() -> None:
    """Test getting decimal value from a list of checked keys."""
    # Test with no keys
    value = BitmaskHelper.get_value_from_keys([])
    assert value == "0"

    # Test with single key
    value = BitmaskHelper.get_value_from_keys([0])
    assert value == "1"

    # Test with multiple keys
    value = BitmaskHelper.get_value_from_keys([0, 1, 2])
    assert value == "7"  # 1 + 2 + 4 = 7

    # Test with all keys
    value = BitmaskHelper.get_value_from_keys([0, 1, 2, 3, 4])
    assert value == "31"  # 1 + 2 + 4 + 8 + 16 = 31

    # Test with some keys
    value = BitmaskHelper.get_value_from_keys([1, 4])
    assert value == "18"  # 2 + 16 = 18
