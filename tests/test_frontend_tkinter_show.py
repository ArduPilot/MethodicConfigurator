#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_show.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_show import (
    show_error_message,
    show_no_connection_error,
    show_no_param_files_error,
    show_tooltip,
)


class TestShowErrorMessage(unittest.TestCase):
    """Test cases for the show_error_message function."""

    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.Tk")
    @patch("tkinter.ttk.Style")  # Mock the ttk.Style class
    def test_show_error_message(self, _mock_style, mock_tk, mock_showerror) -> None:  # noqa: PT019
        # Mock the Tkinter Tk class to prevent it from actually creating a window
        mock_tk.return_value.withdraw.return_value = None
        mock_tk.return_value.destroy.return_value = None

        # Call the function with test parameters
        show_error_message("Test Title", "Test Message")

        # Assert that the Tkinter Tk class was instantiated
        mock_tk.assert_called_once()

        # Assert that the Tkinter messagebox.showerror function was called with the correct parameters
        mock_showerror.assert_called_once_with("Test Title", "Test Message")

        # Assert that the Tkinter Tk instance's withdraw method was called
        mock_tk.return_value.withdraw.assert_called_once()

        # Assert that the Tkinter Tk instance's destroy method was called
        mock_tk.return_value.destroy.assert_called_once()

    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.Tk")
    @patch("tkinter.ttk.Style")
    def test_show_error_message_with_special_chars(self, mock_style, mock_tk, mock_showerror) -> None:
        """Test error message with special characters."""
        mock_tk.return_value.withdraw.return_value = None
        mock_tk.return_value.destroy.return_value = None
        mock_style.return_value = MagicMock()

        show_error_message("Test & Title", "Test\nMessage with & special < chars >")
        mock_showerror.assert_called_once_with("Test & Title", "Test\nMessage with & special < chars >")


class TestShowTooltip(unittest.TestCase):
    """Test cases for the show_tooltip function."""

    @patch("tkinter.Toplevel")
    @patch("tkinter.ttk.Label")
    def test_show_tooltip(self, mock_label, mock_toplevel) -> None:
        # Mock the Tkinter Toplevel class to prevent it from actually creating a window
        mock_toplevel.return_value.deiconify.return_value = None
        mock_toplevel.return_value.withdraw.return_value = None

        # Mock the Tkinter Label class to prevent it from actually creating a label
        mock_label.return_value.pack.return_value = None

        # Create a mock widget
        mock_widget = MagicMock()
        mock_widget.winfo_rootx.return_value = 100
        mock_widget.winfo_rooty.return_value = 200
        mock_widget.winfo_width.return_value = 50
        mock_widget.winfo_height.return_value = 30

        # Call the function with test parameters
        show_tooltip(mock_widget, "Test Tooltip Message")

        # Create a mock event object
        mock_event = MagicMock()

        # Simulate the <Enter> event to trigger the deiconify method
        enter_event = mock_widget.bind.call_args_list[0][0][1]
        enter_event(mock_event)

        # Assert that the Tkinter Toplevel class was instantiated
        mock_toplevel.assert_called_once()

        # Assert that the Tkinter Label class was instantiated with the correct parameters
        mock_label.assert_called_once_with(
            mock_toplevel.return_value,
            text="Test Tooltip Message",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            justify=tk.LEFT,
        )

        # Assert that the Tkinter Toplevel instance's deiconify method was called
        mock_toplevel.return_value.deiconify.assert_called()

        # Simulate the <Leave> event to trigger the withdraw method
        leave_event = mock_widget.bind.call_args_list[1][0][1]
        leave_event(mock_event)

        # Assert that the Tkinter Toplevel instance's withdraw method was called
        mock_toplevel.return_value.withdraw.assert_called()

    def test_tooltip_positioning(self) -> None:
        mock_widget = MagicMock()
        mock_widget.winfo_rootx.return_value = 100
        mock_widget.winfo_rooty.return_value = 200
        mock_widget.winfo_width.return_value = 50
        mock_widget.winfo_height.return_value = 30

        with patch("tkinter.Toplevel") as mock_toplevel:
            mock_toplevel_instance = MagicMock()
            mock_toplevel.return_value = mock_toplevel_instance
            show_tooltip(mock_widget, "Test Tooltip")

            # Trigger enter event
            enter_event = mock_widget.bind.call_args_list[0][0][1]
            enter_event(MagicMock())

            # Check tooltip positioning
            expected_x = mock_widget.winfo_rootx() + min(mock_widget.winfo_width() // 2, 100)
            expected_y = mock_widget.winfo_rooty() + mock_widget.winfo_height()
            mock_toplevel_instance.geometry.assert_called_with(f"+{expected_x}+{expected_y}")


class TestShowNoParamFilesError(unittest.TestCase):
    """Test cases for the show_no_param_files_error function."""

    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.Tk")
    @patch("tkinter.ttk.Style")
    def test_show_no_param_files_error(self, _mock_style, mock_tk, mock_showerror) -> None:  # noqa: PT019
        mock_tk.return_value.withdraw.return_value = None
        mock_tk.return_value.destroy.return_value = None

        show_no_param_files_error("test_dir")

        mock_tk.assert_called_once()
        mock_showerror.assert_called_once_with(
            "No Parameter Files Found",
            (
                "No intermediate parameter files found in the selected 'test_dir' vehicle directory.\n"
                "Please select and step inside a vehicle directory containing valid ArduPilot intermediate parameter files."
                "\n\nMake sure to step inside the directory (double-click) and not just select it."
            ),
        )
        mock_tk.return_value.withdraw.assert_called_once()
        mock_tk.return_value.destroy.assert_called_once()


class TestShowNoConnectionError(unittest.TestCase):
    """Test cases for the show_no_connection_error function."""

    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.Tk")
    @patch("tkinter.ttk.Style")
    def test_show_no_connection_error(self, _mock_style, mock_tk, mock_showerror) -> None:  # noqa: PT019
        mock_tk.return_value.withdraw.return_value = None
        mock_tk.return_value.destroy.return_value = None

        show_no_connection_error("test_error")

        mock_tk.assert_called_once()
        mock_showerror.assert_called_once_with(
            "No Connection to the Flight Controller",
            "test_error\n\nPlease connect a flight controller to the PC,\nwait at least 7 seconds and retry.",
        )
        mock_tk.return_value.withdraw.assert_called_once()
        mock_tk.return_value.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
