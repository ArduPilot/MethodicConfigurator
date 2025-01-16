#!/usr/bin/python3

"""
Tests for the argparse_check_range.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from argparse import ArgumentParser

import pytest

from ardupilot_methodic_configurator.argparse_check_range import CheckRange


class TestCheckRange(unittest.TestCase):
    """Test the CheckRange class."""

    def setUp(self) -> None:
        self.parser = ArgumentParser()

    def test_init_with_both_min_and_inf(self) -> None:
        with pytest.raises(ValueError, match="either min or inf, but not both"):
            self.parser.add_argument("--test", action=CheckRange, min=0, inf=0)

    def test_init_with_both_max_and_sup(self) -> None:
        with pytest.raises(ValueError, match="either max or sup, but not both"):
            self.parser.add_argument("--test", action=CheckRange, max=10, sup=10)

    def test_interval_with_min_and_max(self) -> None:
        action = CheckRange(option_strings=["--test"], dest="test", min=0, max=10)
        assert action.interval() == "valid range: [0, 10]"

    def test_interval_with_inf_and_sup(self) -> None:
        action = CheckRange(option_strings=["--test"], dest="test", inf=0, sup=10)
        assert action.interval() == "valid range: (0, 10)"

    def test_interval_with_no_bounds(self) -> None:
        action = CheckRange(option_strings=["--test"], dest="test")
        assert action.interval() == "valid range: (-infinity, +infinity)"

    def test_call_with_non_number_value(self) -> None:
        self.parser.add_argument("--test", action=CheckRange, min=0, max=10)
        with pytest.raises(SystemExit) as excinfo:
            self.parser.parse_args(["--test", "non-number"])
        assert str(excinfo.value) == "2"

    def test_call_with_value_out_of_range(self) -> None:
        self.parser.add_argument("--test", action=CheckRange, min=0, max=10)
        with pytest.raises(SystemExit) as excinfo:
            self.parser.parse_args(["--test", "11"])
        assert str(excinfo.value) == "2"

    def test_call_with_value_equal_to_inf(self) -> None:
        self.parser.add_argument("--test", action=CheckRange, inf=0, sup=10)
        with pytest.raises(SystemExit) as excinfo:
            self.parser.parse_args(["--test", "0"])
        assert str(excinfo.value) == "2"

    def test_call_with_value_equal_to_sup(self) -> None:
        self.parser.add_argument("--test", action=CheckRange, inf=0, sup=10)
        with pytest.raises(SystemExit) as excinfo:
            self.parser.parse_args(["--test", "10"])
        assert str(excinfo.value) == "2"


if __name__ == "__main__":
    unittest.main()
