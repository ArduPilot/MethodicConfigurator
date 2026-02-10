#!/usr/bin/env python3

"""
Tests for the argparse_check_range.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from argparse import ArgumentParser, Namespace

import pytest

from ardupilot_methodic_configurator.argparse_check_range import CheckRange

# pylint: disable=unused-argument


class TestCheckRangeInitialization:
    """Test CheckRange initialization and configuration."""

    def test_developer_cannot_specify_both_min_and_inf_bounds(self) -> None:
        """
        Developer cannot configure CheckRange with both min and inf bounds.

        GIVEN: A developer is configuring argument range validation
        WHEN: They attempt to specify both min and inf parameters
        THEN: A ValueError should be raised to prevent conflicting configuration
        """
        with pytest.raises(ValueError, match="either min or inf, but not both"):
            CheckRange(option_strings=["--test"], dest="test", min=0, inf=0)

    def test_developer_cannot_specify_both_max_and_sup_bounds(self) -> None:
        """
        Developer cannot configure CheckRange with both max and sup bounds.

        GIVEN: A developer is configuring argument range validation
        WHEN: They attempt to specify both max and sup parameters
        THEN: A ValueError should be raised to prevent conflicting configuration
        """
        with pytest.raises(ValueError, match="either max or sup, but not both"):
            CheckRange(option_strings=["--test"], dest="test", max=10, sup=10)


class TestCheckRangeIntervalDescription:
    """Test CheckRange interval description generation."""

    def test_user_sees_correct_interval_for_closed_range(self) -> None:
        """
        User sees correct interval description for closed range [min, max].

        GIVEN: A CheckRange is configured with min=0 and max=10
        WHEN: The user requests the valid range description
        THEN: They should see "valid range: [0, 10]"
        """
        action = CheckRange(option_strings=["--test"], dest="test", min=0, max=10)
        assert action.interval() == "valid range: [0, 10]"

    def test_user_sees_correct_interval_for_open_range(self) -> None:
        """
        User sees correct interval description for open range (inf, sup).

        GIVEN: A CheckRange is configured with inf=0 and sup=10
        WHEN: The user requests the valid range description
        THEN: They should see "valid range: (0, 10)"
        """
        action = CheckRange(option_strings=["--test"], dest="test", inf=0, sup=10)
        assert action.interval() == "valid range: (0, 10)"

    def test_user_sees_correct_interval_for_unbounded_range(self) -> None:
        """
        User sees correct interval description for unbounded range.

        GIVEN: A CheckRange is configured without any bounds
        WHEN: The user requests the valid range description
        THEN: They should see "valid range: (-infinity, +infinity)"
        """
        action = CheckRange(option_strings=["--test"], dest="test")
        assert action.interval() == "valid range: (-infinity, +infinity)"


class TestCheckRangeValueValidation:
    """Test CheckRange value validation during argument parsing."""

    @pytest.fixture
    def mock_parser(self) -> ArgumentParser:
        """Fixture providing a mock argument parser for testing."""
        return ArgumentParser()

    @pytest.fixture
    def mock_namespace(self) -> Namespace:
        """Fixture providing a mock namespace for testing."""
        return Namespace()

    def test_user_receives_error_for_non_numeric_input(self, mock_parser, mock_namespace) -> None:
        """
        User receives clear error when providing non-numeric input.

        GIVEN: An argument parser configured with range validation (min=0, max=10)
        WHEN: The user provides a non-numeric value like "non-number"
        THEN: The parser should exit with an error indicating the value must be numeric
        """
        mock_parser.add_argument("--test", action=CheckRange, min=0, max=10)

        with pytest.raises(SystemExit) as excinfo:
            mock_parser.parse_args(["--test", "non-number"])
        assert str(excinfo.value) == "2"

    def test_user_receives_error_for_value_below_minimum(self, mock_parser, mock_namespace) -> None:
        """
        User receives clear error when value is below the minimum bound.

        GIVEN: An argument parser configured with range validation (min=0, max=10)
        WHEN: The user provides a value below the minimum (like -1)
        THEN: The parser should exit with an error showing the valid range
        """
        mock_parser.add_argument("--test", type=int, action=CheckRange, min=0, max=10)

        with pytest.raises(SystemExit) as excinfo:
            mock_parser.parse_args(["--test", "-1"])
        assert str(excinfo.value) == "2"

    def test_user_receives_error_for_value_above_maximum(self, mock_parser, mock_namespace) -> None:
        """
        User receives clear error when value exceeds the maximum bound.

        GIVEN: An argument parser configured with range validation (min=0, max=10)
        WHEN: The user provides a value above the maximum (like 11)
        THEN: The parser should exit with an error showing the valid range
        """
        mock_parser.add_argument("--test", type=int, action=CheckRange, min=0, max=10)

        with pytest.raises(SystemExit) as excinfo:
            mock_parser.parse_args(["--test", "11"])
        assert str(excinfo.value) == "2"

    def test_user_receives_error_for_value_equal_to_inf_bound(self, mock_parser, mock_namespace) -> None:
        """
        User receives clear error when value equals the exclusive lower bound.

        GIVEN: An argument parser configured with open range validation (inf=0, sup=10)
        WHEN: The user provides a value equal to inf (like 0)
        THEN: The parser should exit with an error showing the valid range
        """
        mock_parser.add_argument("--test", type=int, action=CheckRange, inf=0, sup=10)

        with pytest.raises(SystemExit) as excinfo:
            mock_parser.parse_args(["--test", "0"])
        assert str(excinfo.value) == "2"

    def test_user_receives_error_for_value_equal_to_sup_bound(self, mock_parser, mock_namespace) -> None:
        """
        User receives clear error when value equals the exclusive upper bound.

        GIVEN: An argument parser configured with open range validation (inf=0, sup=10)
        WHEN: The user provides a value equal to sup (like 10)
        THEN: The parser should exit with an error showing the valid range
        """
        mock_parser.add_argument("--test", type=int, action=CheckRange, inf=0, sup=10)

        with pytest.raises(SystemExit) as excinfo:
            mock_parser.parse_args(["--test", "10"])
        assert str(excinfo.value) == "2"

    def test_user_can_successfully_provide_valid_value(self, mock_parser, mock_namespace) -> None:
        """
        User can successfully provide a value within the valid range.

        GIVEN: An argument parser configured with range validation (min=0, max=10)
        WHEN: The user provides a valid numeric value within range (like 5)
        THEN: The value should be successfully stored in the namespace
        """
        mock_parser.add_argument("--test", type=int, action=CheckRange, min=0, max=10)
        args = mock_parser.parse_args(["--test", "5"])

        assert args.test == 5

    def test_user_can_successfully_provide_valid_value_in_open_range(self, mock_parser, mock_namespace) -> None:
        """
        User can successfully provide a value within an open range.

        GIVEN: An argument parser configured with open range validation (inf=0, sup=10)
        WHEN: The user provides a valid numeric value within the open range (like 5)
        THEN: The value should be successfully stored in the namespace
        """
        mock_parser.add_argument("--test", type=int, action=CheckRange, inf=0, sup=10)
        args = mock_parser.parse_args(["--test", "5"])

        assert args.test == 5

    def test_user_can_successfully_provide_valid_value_with_no_bounds(self, mock_parser, mock_namespace) -> None:
        """
        User can successfully provide any numeric value when no bounds are set.

        GIVEN: An argument parser configured with no range bounds
        WHEN: The user provides any numeric value (like 1000)
        THEN: The value should be successfully stored in the namespace
        """
        mock_parser.add_argument("--test", type=int, action=CheckRange)
        args = mock_parser.parse_args(["--test", "1000"])

        assert args.test == 1000
