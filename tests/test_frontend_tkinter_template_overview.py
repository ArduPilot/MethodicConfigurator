#!/usr/bin/python3

"""
Tests for the frontend_tkinter_template_overview.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import unittest
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_template_overview import argument_parser, main


class TestTemplateOverviewWindow(unittest.TestCase):
    """Test cases for the TemplateOverviewWindow class."""


class TestArgumentParser(unittest.TestCase):
    """Test cases for argument parsing functionality."""

    def test_argument_parser_exit(self) -> None:
        """Test argument parser exits with no arguments."""
        with pytest.raises(SystemExit):
            argument_parser()

    @patch("sys.argv", ["script.py", "--loglevel", "DEBUG"])
    def test_main_function(self) -> None:
        """Test main function execution."""
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow") as mock_window,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.argument_parser") as mock_parser,
        ):
            mock_parser.return_value = argparse.Namespace(loglevel="DEBUG")
            main()
            mock_window.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
