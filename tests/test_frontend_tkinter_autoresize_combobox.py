#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_autoresize_combobox.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import patch

from ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox import (
    AutoResizeCombobox,
    update_combobox_width,
)


class TestUpdateComboboxWidth(unittest.TestCase):
    """Test cases for the update_combobox_width function."""

    def test_update_combobox_width(self) -> None:
        combobox = ttk.Combobox(values=["short", "longer", "longest"])
        update_combobox_width(combobox)
        assert combobox.cget("width") == 7

    def test_update_combobox_width_empty_values(self) -> None:
        combobox = ttk.Combobox(values=[])
        update_combobox_width(combobox)
        # Should use the minimum width (4) when no values
        assert combobox.cget("width") == 4

    def test_update_combobox_width_very_short_values(self) -> None:
        combobox = ttk.Combobox(values=["a", "b", "c"])
        update_combobox_width(combobox)
        # Should use the minimum width (4) when values are short
        assert combobox.cget("width") == 4


class TestAutoResizeCombobox(unittest.TestCase):
    """Test cases for the AutoResizeCombobox class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.combobox = AutoResizeCombobox(
            self.root, values=["one", "two", "three"], selected_element="two", tooltip="Test Tooltip"
        )

    def tearDown(self) -> None:
        self.root.destroy()

    def test_initial_selection(self) -> None:
        assert self.combobox.get() == "two"

    def test_update_values(self) -> None:
        self.combobox.set_entries_tuple(["four", "five", "six"], "five")
        assert self.combobox.get() == "five"
        assert self.combobox["values"] == ("four", "five", "six")

    def test_set_entries_with_spaces(self) -> None:
        """Test values with spaces."""
        values = ["option one", "option  two", "option   three"]
        self.combobox.set_entries_tuple(values, "option  two")
        assert self.combobox["values"] == tuple(values)
        assert self.combobox.get() == "option  two"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.logging_error")
    def test_set_entries_invalid_selection(self, mock_logging_error) -> None:
        """Test when selected element is not in values list."""
        values = ["one", "two", "three"]
        self.combobox.set_entries_tuple(values, "four")

        # Should log an error
        mock_logging_error.assert_called_once()
        # Selected value should not be set
        assert self.combobox.get() == "two"  # Maintains previous value

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.logging_warning")
    def test_set_entries_no_selection(self, mock_logging_warning) -> None:
        """Test when no selection is provided."""
        values = ["one", "two", "three"]
        self.combobox.set_entries_tuple(values, "")

        # Should log a warning
        mock_logging_warning.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width")
    def test_set_entries_empty_values(self, mock_update_width) -> None:
        """Test behavior with empty values list."""
        self.combobox.set_entries_tuple([], "")

        # Width update should not be called with empty values
        mock_update_width.assert_not_called()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.show_tooltip")
    def test_tooltip_display(self, mock_show_tooltip) -> None:
        """Test tooltip is shown when provided."""
        self.combobox.set_entries_tuple(["one", "two"], "one", "Help text")

        # Tooltip should be shown
        mock_show_tooltip.assert_called_once_with(self.combobox, "Help text")

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.show_tooltip")
    def test_no_tooltip_when_none(self, mock_show_tooltip) -> None:
        """Test tooltip is not shown when None."""
        self.combobox.set_entries_tuple(["one", "two"], "one", None)

        # Tooltip should not be shown
        mock_show_tooltip.assert_not_called()


if __name__ == "__main__":
    unittest.main()
