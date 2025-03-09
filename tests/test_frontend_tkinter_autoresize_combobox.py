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

    def test_tooltip(self) -> None:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base.show_tooltip") as mock_show_tooltip:
            self.combobox.set_entries_tuple(["one", "two", "three"], "two", tooltip="Test Tooltip")
            mock_show_tooltip.assert_called_once_with(self.combobox, "Test Tooltip")

    def test_update_values(self) -> None:
        self.combobox.set_entries_tuple(["four", "five", "six"], "five")
        assert self.combobox.get() == "five"
        assert self.combobox["values"] == ("four", "five", "six")

    def test_invalid_selection(self) -> None:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base.logging_error") as mock_logging_error:
            self.combobox.set_entries_tuple(["seven", "eight"], "nine")
            mock_logging_error.assert_called_once()

    def test_no_selection(self) -> None:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base.logging_warning") as mock_logging_warning:
            self.combobox.set_entries_tuple(["ten", "eleven"], "")
            mock_logging_warning.assert_called_once()

    def test_set_entries_with_spaces(self) -> None:
        """Test values with spaces."""
        values = ["option one", "option  two", "option   three"]
        self.combobox.set_entries_tuple(values, "option  two")
        assert self.combobox["values"] == tuple(values)
        assert self.combobox.get() == "option  two"


if __name__ == "__main__":
    unittest.main()
