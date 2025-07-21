#!/usr/bin/python3

"""
Tests for the ParameterEditorWindow class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow

# pylint: disable=redefined-outer-name, too-many-arguments, too-many-positional-arguments, unused-argument


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Create a mock flight controller for testing."""
    mock_fc = MagicMock()
    mock_fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
    return mock_fc


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Create a mock local filesystem for testing."""
    mock_fs = MagicMock()
    mock_fs.file_parameters = {"test_file.param": {"PARAM1": Par(1.0), "PARAM2": Par(2.0)}}
    return mock_fs


@pytest.fixture
def parameter_editor(root, mock_flight_controller, mock_local_filesystem) -> ParameterEditorWindow:
    """Create a ParameterEditorWindow instance for testing with real widgets in headless mode."""
    # Create the object without calling __init__
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)

    # Create a mock for parameter_editor_table
    mock_parameter_editor_table = MagicMock()

    # Manually set required attributes for tests using real root
    editor.root = root
    editor.main_frame = MagicMock()  # Still mock the main frame to avoid complex UI setup
    editor.current_file = "test_file.param"
    editor.flight_controller = mock_flight_controller
    editor.local_filesystem = mock_local_filesystem
    editor.at_least_one_changed_parameter_written = False
    editor.parameter_editor_table = mock_parameter_editor_table

    return editor


class TestParameterEditorWindow:
    """Test cases for the ParameterEditorWindow class."""

    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_no_auto_change(
        self, mock_exit: MagicMock, parameter_editor, mock_local_filesystem
    ) -> None:
        """Test that nothing happens when there is no auto_changed_by value."""
        mock_local_filesystem.auto_changed_by.return_value = None

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_not_called()

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_yes_response(
        self,
        mock_exit: MagicMock,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test handling 'Yes' response in the dialog."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Create a fake dialog response mechanism - simulate "Yes" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "Yes" button callback and execute it
            for call in mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("Yes"):
                    # This is the "Yes" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        root.wait_window = MagicMock(side_effect=side_effect)

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_called_once()
        mock_exit.assert_not_called()

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_no_response(
        self,
        mock_exit: MagicMock,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test handling 'No' response in the dialog."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Create a fake dialog response mechanism - simulate "No" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "No" button callback and execute it
            for call in mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("No"):
                    # This is the "No" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        root.wait_window = MagicMock(side_effect=side_effect)

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_not_called()

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_close_response(
        self,
        mock_exit: MagicMock,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test handling 'Close' response in the dialog."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Create a fake dialog response mechanism - simulate "Close" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "Close" button callback and execute it
            for call in mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("Close"):
                    # This is the "Close" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        root.wait_window = MagicMock(side_effect=side_effect)

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_called_once_with(0)

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    def test_dialog_creation(
        self,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test the creation of the dialog with its components."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Don't let the test exit
        with patch("sys.exit"):
            # Replace wait_window with a mock that doesn't block
            def fake_wait_window(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401 # pylint: disable=unused-argument
                pass

            root.wait_window = MagicMock(side_effect=fake_wait_window)

            parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        # Verify dialog creation
        mock_toplevel.assert_called_once()

        # Check for label, buttons, and frame creation
        mock_label.assert_called_once()
        mock_frame.assert_called_once()
