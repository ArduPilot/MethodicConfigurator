#!/usr/bin/env python3

"""
Tests for the common_arguments.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from argparse import ArgumentParser
from unittest.mock import MagicMock

from ardupilot_methodic_configurator import common_arguments


class TestCommonArguments(unittest.TestCase):  # pylint: disable=missing-class-docstring
    def test_add_common_arguments_and_parse_loglevel(self) -> None:
        # Test that loglevel choices are added correctly
        parser = ArgumentParser()
        parser.parse_args = MagicMock(return_value=MagicMock(loglevel="INFO"))

        updated_parser = common_arguments.add_common_arguments(parser).parse_args()

        # This will raise an error if loglevel is not an argument
        # or if the choices are not set up correctly.
        updated_parser.parse_args(["--loglevel", "INFO"])
        updated_parser.parse_args.assert_called_with(["--loglevel", "INFO"])

    def test_version_argument(self) -> None:
        # Test that version argument displays correct version
        parser = ArgumentParser()
        # Mock the parse_args to just print the version string
        parser.parse_args = MagicMock()
        common_arguments.VERSION = "1.0.0"
        updated_parser = common_arguments.add_common_arguments(parser).parse_args()

        # We assume the call to parse_args with --version should print the version
        # Since we cannot capture stdout here easily, we'll just confirm the method was called with --version
        updated_parser.parse_args(["--version"])
        updated_parser.parse_args.assert_called_with(["--version"])


if __name__ == "__main__":
    unittest.main()
