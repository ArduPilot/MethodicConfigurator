#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

# pylint: skip-file

import unittest
from unittest.mock import patch, MagicMock
import tkinter as tk
from MethodicConfigurator.frontend_tkinter_base import show_error_message
from MethodicConfigurator.frontend_tkinter_base import show_tooltip


class TestShowErrorMessage(unittest.TestCase):  # pylint: disable=missing-class-docstring
    @patch('tkinter.messagebox.showerror')
    @patch('tkinter.Tk')
    @patch('tkinter.ttk.Style') # Mock the ttk.Style class
    def test_show_error_message(self, mock_style, mock_tk, mock_showerror):
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


class TestShowTooltip(unittest.TestCase):
    @patch('tkinter.Toplevel')
    @patch('tkinter.ttk.Label')
    def test_show_tooltip(self, mock_label, mock_toplevel):
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
        mock_widget.bind.call_args[0][1](mock_event)

        # Assert that the Tkinter Toplevel class was instantiated
        mock_toplevel.assert_called_once()

        # Assert that the Tkinter Label class was instantiated with the correct parameters
        mock_label.assert_called_once_with(mock_toplevel.return_value, text="Test Tooltip Message",
                                           background="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT)

        # Assert that the Tkinter Toplevel instance's deiconify method was called
        # mock_toplevel.return_value.deiconify.assert_called()

        # Assert that the Tkinter Toplevel instance's withdraw method was called
        mock_toplevel.return_value.withdraw.assert_called()

        # Assert that the Tkinter Label instance's pack method was called
        mock_label.return_value.pack.assert_called_once()


if __name__ == '__main__':
    unittest.main()
