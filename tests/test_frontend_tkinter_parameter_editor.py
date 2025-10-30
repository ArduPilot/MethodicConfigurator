#!/usr/bin/env python3

"""
Tests for the ParameterEditorWindow class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.data_model_par_dict import Par
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
    # Create the configuration manager for the test
    config_manager = ConfigurationManager("test_file.param", mock_flight_controller, mock_local_filesystem)

    # Create the object without calling __init__
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)

    # Create a mock for parameter_editor_table
    mock_parameter_editor_table = MagicMock()

    # Manually set required attributes for tests using real root
    editor.root = root
    editor.main_frame = MagicMock()  # Still mock the main frame to avoid complex UI setup
    editor.configuration_manager = config_manager  # Add the missing configuration_manager
    editor.flight_controller = mock_flight_controller
    editor.local_filesystem = mock_local_filesystem
    editor.at_least_one_changed_parameter_written = False
    editor.parameter_editor_table = mock_parameter_editor_table

    return editor


@pytest.fixture
def configured_parameter_editor(mock_flight_controller, mock_local_filesystem) -> ParameterEditorWindow:
    """Fixture providing a configured ParameterEditorWindow for business logic testing."""
    with (
        patch("tkinter.Tk"),
        patch.object(ParameterEditorWindow, "__init__", return_value=None),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_info"),
    ):
        # Create the configuration manager for the test
        config_manager = ConfigurationManager("test_file.param", mock_flight_controller, mock_local_filesystem)

        editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
        editor.configuration_manager = config_manager
        editor.flight_controller = mock_flight_controller
        editor.local_filesystem = mock_local_filesystem
        return editor


class TestParameterEditorWindow:
    """Test cases for the ParameterEditorWindow class."""

    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_no_auto_change(
        self, mock_exit: MagicMock, parameter_editor, mock_local_filesystem
    ) -> None:
        """Test that nothing happens when there is no auto_changed_by value."""
        # Mock should_copy_fc_values_to_file to return False (no copy needed)
        parameter_editor.configuration_manager.should_copy_fc_values_to_file = MagicMock(return_value=(False, None, None))

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        parameter_editor.configuration_manager.should_copy_fc_values_to_file.assert_called_once_with("test_file.param")
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
        # Mock should_copy_fc_values_to_file to return True with relevant params
        relevant_fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        parameter_editor.configuration_manager.should_copy_fc_values_to_file = MagicMock(
            return_value=(True, relevant_fc_params, "External Tool")
        )
        parameter_editor.configuration_manager.copy_fc_values_to_file = MagicMock(return_value=True)

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

        parameter_editor.configuration_manager.should_copy_fc_values_to_file.assert_called_once_with("test_file.param")
        parameter_editor.configuration_manager.copy_fc_values_to_file.assert_called_once()
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
        # Mock should_copy_fc_values_to_file to return True with relevant params
        relevant_fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        parameter_editor.configuration_manager.should_copy_fc_values_to_file = MagicMock(
            return_value=(True, relevant_fc_params, "External Tool")
        )
        parameter_editor.configuration_manager.copy_fc_values_to_file = MagicMock(return_value=True)

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

        parameter_editor.configuration_manager.should_copy_fc_values_to_file.assert_called_once_with("test_file.param")
        parameter_editor.configuration_manager.copy_fc_values_to_file.assert_not_called()
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
        # Mock should_copy_fc_values_to_file to return True with relevant params
        relevant_fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        parameter_editor.configuration_manager.should_copy_fc_values_to_file = MagicMock(
            return_value=(True, relevant_fc_params, "External Tool")
        )
        parameter_editor.configuration_manager.copy_fc_values_to_file = MagicMock(return_value=True)

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

        parameter_editor.configuration_manager.should_copy_fc_values_to_file.assert_called_once_with("test_file.param")
        parameter_editor.configuration_manager.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_called_once_with(0)

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    def test_dialog_creation(  # pylint: disable=too-many-locals
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
        # Mock should_copy_fc_values_to_file to return True with relevant params
        relevant_fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        parameter_editor.configuration_manager.should_copy_fc_values_to_file = MagicMock(
            return_value=(True, relevant_fc_params, "External Tool")
        )

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
        assert mock_label.call_count == 2  # message label and link label
        assert mock_button.call_count == 3  # Close, Yes, No buttons
        mock_frame.assert_called_once()

        # Verify message label creation
        message_label_call = mock_label.call_args_list[0]
        assert message_label_call[1]["text"].startswith("This configuration step requires external changes by: External Tool")
        assert message_label_call[1]["justify"] == "left"
        assert message_label_call[1]["padx"] == 20
        assert message_label_call[1]["pady"] == 10

        # Verify link label creation
        link_label_call = mock_label.call_args_list[1]
        assert link_label_call[1]["text"] == "Click here to open the Tuning Guide relevant Section"
        assert link_label_call[1]["fg"] == "blue"
        assert link_label_call[1]["cursor"] == "hand2"
        # Font should be a tuple with underline
        font_arg = link_label_call[1]["font"]
        assert isinstance(font_arg, tuple)
        assert len(font_arg) == 3
        assert font_arg[2] == "underline"

        # Verify link label is packed and bound correctly
        link_label_mock = mock_label.return_value
        # Both labels call pack, so check that the link label's pack call was made
        assert link_label_mock.pack.call_count == 2
        link_label_mock.pack.assert_any_call(pady=(0, 10))  # link label pack call
        link_label_mock.pack.assert_any_call(padx=10, pady=10)  # message label pack call
        link_label_mock.bind.assert_called_once_with("<Button-1>", ANY)  # lambda function, so use ANY

        # Verify buttons are created with correct text
        button_calls = mock_button.call_args_list
        assert button_calls[0][1]["text"] == "Close"
        assert button_calls[1][1]["text"] == "Yes"
        assert button_calls[2][1]["text"] == "No"

        # Verify button frame is packed correctly
        frame_mock = mock_frame.return_value
        frame_mock.pack.assert_called_once_with(pady=10)
