#!/usr/bin/python3

"""
Tests for the ParameterEditorWindow class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from typing import Any
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow


class TestParameterEditorWindow(unittest.TestCase):  # pylint: disable=too-many-instance-attributes
    """Test cases for the ParameterEditorWindow class."""

    def setUp(self) -> None:
        # Create mock objects for dependencies
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests

        self.mock_flight_controller = MagicMock()
        self.mock_flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}

        self.mock_local_filesystem = MagicMock()
        self.mock_local_filesystem.file_parameters = {"test_file.param": {"PARAM1": Par(1.0), "PARAM2": Par(2.0)}}

        # Patch necessary methods and classes
        self.toplevel_patcher = patch("tkinter.Toplevel")
        self.mock_toplevel = self.toplevel_patcher.start()
        # Setup the mock toplevel to better simulate dialog behavior
        self.mock_dialog = MagicMock()
        self.mock_toplevel.return_value = self.mock_dialog
        self.mock_dialog.result = [None]  # Initialize result list

        self.label_patcher = patch("tkinter.Label")
        self.mock_label = self.label_patcher.start()

        self.frame_patcher = patch("tkinter.Frame")
        self.mock_frame = self.frame_patcher.start()

        self.button_patcher = patch("tkinter.Button")
        self.mock_button = self.button_patcher.start()

        # Better than patching __init__, just create the object directly
        # and set its attributes manually
        self.parameter_editor = ParameterEditorWindow.__new__(ParameterEditorWindow)

        # Create a mock for parameter_editor_table
        self.mock_parameter_editor_table = MagicMock()

        # Manually set required attributes for tests
        self.parameter_editor.root = self.root
        self.parameter_editor.main_frame = ttk.Frame(self.root)
        self.parameter_editor.current_file = "test_file.param"
        self.parameter_editor.flight_controller = self.mock_flight_controller
        self.parameter_editor.local_filesystem = self.mock_local_filesystem
        self.parameter_editor.at_least_one_changed_parameter_written = False
        self.parameter_editor.parameter_editor_table = self.mock_parameter_editor_table

    def tearDown(self) -> None:
        self.toplevel_patcher.stop()
        self.label_patcher.stop()
        self.frame_patcher.stop()
        self.button_patcher.stop()
        self.root.destroy()

    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_no_auto_change(self, mock_exit: MagicMock) -> None:
        """Test that nothing happens when there is no auto_changed_by value."""
        self.mock_local_filesystem.auto_changed_by.return_value = None

        self.parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        self.mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        self.mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_not_called()

    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_yes_response(self, mock_exit: MagicMock) -> None:
        """Test handling 'Yes' response in the dialog."""
        self.mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Create a fake dialog response mechanism - simulate "Yes" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "Yes" button callback and execute it
            for call in self.mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("Yes"):
                    # This is the "Yes" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        self.root.wait_window = MagicMock(side_effect=side_effect)

        # Ensure the toplevel dialog has a result list that can be modified by the command
        self.mock_dialog.result = [None]

        self.parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        self.mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        self.mock_local_filesystem.copy_fc_values_to_file.assert_called_once()
        mock_exit.assert_not_called()

    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_no_response(self, mock_exit: MagicMock) -> None:
        """Test handling 'No' response in the dialog."""
        self.mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Create a fake dialog response mechanism - simulate "No" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "No" button callback and execute it
            for call in self.mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("No"):
                    # This is the "No" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        self.root.wait_window = MagicMock(side_effect=side_effect)

        # Ensure the toplevel dialog has a result list that can be modified by the command
        self.mock_dialog.result = [None]

        self.parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        self.mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        self.mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_not_called()

    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_close_response(self, mock_exit: MagicMock) -> None:
        """Test handling 'Close' response in the dialog."""
        self.mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Create a fake dialog response mechanism - simulate "Close" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "Close" button callback and execute it
            for call in self.mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("Close"):
                    # This is the "Close" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        self.root.wait_window = MagicMock(side_effect=side_effect)

        # Ensure the toplevel dialog has a result list that can be modified by the command
        self.mock_dialog.result = [None]

        self.parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        self.mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        self.mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_called_once_with(0)

    @patch("tkinter.Button")
    def test_dialog_creation(self, mock_button: MagicMock) -> None:  # pylint: disable=unused-argument
        """Test the creation of the dialog with its components."""
        self.mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Don't let the test exit
        with patch("sys.exit"):
            # Replace wait_window with a mock that doesn't block
            def fake_wait_window(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401 # pylint: disable=unused-argument
                pass

            self.root.wait_window = MagicMock(side_effect=fake_wait_window)

            # Ensure the toplevel dialog has a result list
            self.mock_dialog.result = [None]

            self.parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        # Verify dialog creation
        self.mock_toplevel.assert_called_once()

        # Check for label, buttons, and frame creation
        self.mock_label.assert_called_once()
        self.mock_frame.assert_called_once()


if __name__ == "__main__":
    unittest.main()
