#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_usage_popup_window.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_base import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import UsagePopupWindow


@pytest.fixture
def mock_set_display() -> MagicMock:
    """Mock the set_display_usage_popup method."""
    with patch(
        "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_display_usage_popup"
    ) as mock_fun:
        yield mock_fun


class TestUsagePopupWindow(unittest.TestCase):
    """Test cases for the UsagePopupWindow class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self) -> None:
        self.root.destroy()

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup")
    def test_should_display(self, mock_display_popup) -> None:
        """Test should_display method."""
        mock_display_popup.return_value = True
        assert UsagePopupWindow.should_display("test_type") is True
        mock_display_popup.assert_called_once_with("test_type")

    @patch("tkinter.BooleanVar")
    @pytest.mark.usefixtures("mock_set_display")
    def test_display_popup(self, mock_bool_var) -> None:
        """Test display method."""
        mock_bool_var.return_value.get.return_value = True
        usage_window = BaseWindow(self.root)
        instructions = RichText(usage_window.main_frame)

        UsagePopupWindow.display(
            parent=self.root,
            usage_popup_window=usage_window,
            title="Test Usage",
            ptype="test_type",
            geometry="300x200",
            instructions_text=instructions,
        )

        assert usage_window.root.title() == "Test Usage"
        assert usage_window.root.geometry().startswith("300x200")
        # Test button creation and checkbox state
        checkbuttons = [w for w in usage_window.main_frame.winfo_children() if isinstance(w, ttk.Checkbutton)]
        assert len(checkbuttons) == 1


if __name__ == "__main__":
    unittest.main()
