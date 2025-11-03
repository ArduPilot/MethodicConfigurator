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

from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_MOTOR_TEST

# pylint: disable=redefined-outer-name, too-many-arguments, too-many-positional-arguments, unused-argument, protected-access


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
        # Mock _should_copy_fc_values_to_file to return False (no copy needed)
        parameter_editor.configuration_manager._should_copy_fc_values_to_file = MagicMock(return_value=(False, None, None))

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        parameter_editor.configuration_manager._should_copy_fc_values_to_file.assert_called_once_with("test_file.param")
        mock_exit.assert_not_called()

    @patch("sys.exit")
    @patch.object(ConfigurationManager, "handle_copy_fc_values_workflow", return_value=True)
    def test_user_can_successfully_copy_flight_controller_values_to_configuration_file(
        self, mock_workflow: MagicMock, mock_exit: MagicMock, parameter_editor, mock_local_filesystem
    ) -> None:
        """
        User can successfully copy flight controller parameter values to a configuration file.

        GIVEN: A user is prompted to copy FC values to a configuration file
        WHEN: The user chooses 'Yes' to proceed with copying
        THEN: The copy workflow is executed successfully
        AND: The application continues running without exiting
        """
        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        # Verify the workflow method was called with correct arguments
        mock_workflow.assert_called_once()
        args, _ = mock_workflow.call_args
        assert args[0] == "test_file.param"  # selected_file
        assert callable(args[1])  # ask_user_choice callback
        assert callable(args[2])  # show_info callback

        mock_exit.assert_not_called()

    @patch("sys.exit")
    @patch.object(ConfigurationManager, "handle_copy_fc_values_workflow", return_value=None)
    def test_user_can_decline_copying_flight_controller_values_to_configuration_file(
        self, mock_workflow: MagicMock, mock_exit: MagicMock, parameter_editor, mock_local_filesystem
    ) -> None:
        """
        User can decline to copy flight controller parameter values to a configuration file.

        GIVEN: A user is prompted to copy FC values to a configuration file
        WHEN: The user chooses 'No' to decline copying
        THEN: The copy workflow is executed but no copying occurs
        AND: The application continues running without exiting
        """
        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        # Verify the workflow method was called with correct arguments
        mock_workflow.assert_called_once()
        args, _ = mock_workflow.call_args
        assert args[0] == "test_file.param"  # selected_file
        assert callable(args[1])  # ask_user_choice callback
        assert callable(args[2])  # show_info callback

        mock_exit.assert_not_called()

    @patch("sys.exit")
    @patch.object(ConfigurationManager, "handle_copy_fc_values_workflow", return_value="close")
    def test_user_can_cancel_and_close_application_when_prompted_to_copy_flight_controller_values(
        self, mock_workflow: MagicMock, mock_exit: MagicMock, parameter_editor, mock_local_filesystem
    ) -> None:
        """
        User can cancel the copy operation and close the application when prompted.

        GIVEN: A user is prompted to copy FC values to a configuration file
        WHEN: The user chooses 'Close' to cancel and exit
        THEN: The copy workflow is executed but cancelled
        AND: The application exits gracefully
        """
        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        # Verify the workflow method was called with correct arguments
        mock_workflow.assert_called_once()
        args, _ = mock_workflow.call_args
        assert args[0] == "test_file.param"  # selected_file
        assert callable(args[1])  # ask_user_choice callback
        assert callable(args[2])  # show_info callback

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
        # Mock _should_copy_fc_values_to_file to return True with relevant params
        relevant_fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        parameter_editor.configuration_manager._should_copy_fc_values_to_file = MagicMock(
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

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory")
    def test_load_plugin_creates_motor_test_view_when_model_available(self, mock_factory, parameter_editor) -> None:
        """
        Test that __load_plugin creates plugin view using factory when data model is available.

        GIVEN: A plugin configuration for motor_test and a valid data model
        WHEN: __load_plugin is called
        THEN: Plugin factory is used to create the view with the correct parameters
        """
        # Mock the factory methods
        mock_factory.is_registered.return_value = True
        mock_plugin_view = MagicMock()
        mock_plugin_view.pack = MagicMock()
        mock_factory.create.return_value = mock_plugin_view

        # Mock the configuration manager to return a valid model
        mock_model = MagicMock()
        with patch.object(parameter_editor.configuration_manager, "create_plugin_data_model", return_value=mock_model):
            # Create a mock parent frame
            mock_parent_frame = MagicMock()

            # Call the method
            plugin_config = {"name": "motor_test"}
            parameter_editor._ParameterEditorWindow__load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

            # Verify factory was used correctly
            mock_factory.is_registered.assert_called_once_with("motor_test")
            mock_factory.create.assert_called_once_with("motor_test", mock_parent_frame, mock_model, parameter_editor)
            mock_plugin_view.pack.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory")
    def test_load_plugin_shows_error_message_when_model_creation_fails(self, mock_factory, parameter_editor) -> None:
        """
        Test that __load_plugin shows error message when data model creation fails.

        GIVEN: A plugin configuration for motor_test but model creation returns None
        WHEN: __load_plugin is called
        THEN: An error label is displayed and plugin is not created
        """
        # Mock the factory methods
        mock_factory.is_registered.return_value = True

        # Mock the configuration manager to return None (model creation failed)
        with patch.object(parameter_editor.configuration_manager, "create_plugin_data_model", return_value=None):
            # Create a mock parent frame
            mock_parent_frame = MagicMock()

            # Call the method
            plugin_config = {"name": "motor_test"}
            parameter_editor._ParameterEditorWindow__load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

            # Verify factory create was not called
            mock_factory.create.assert_not_called()

            # Verify error label was created and packed
            mock_parent_frame.children = []  # Simulate ttk.Frame behavior
            # The actual label creation happens inside the method

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label")
    def test_load_plugin_shows_error_when_model_creation_returns_none(
        self, mock_label, mock_factory, parameter_editor
    ) -> None:
        """
        Test that __load_plugin shows error message when create_plugin_data_model returns None.

        GIVEN: create_plugin_data_model returns None (FC not connected)
        WHEN: __load_plugin is called for motor_test
        THEN: An error label is displayed
        """
        # Mock the factory
        mock_factory.is_registered.return_value = True

        # Mock the configuration manager to return None
        with patch.object(parameter_editor.configuration_manager, "create_plugin_data_model", return_value=None):
            # Create a mock parent frame
            mock_parent_frame = MagicMock()

            # Call the method
            plugin_config = {"name": "motor_test"}
            parameter_editor._ParameterEditorWindow__load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

            # Verify error label was created
            mock_label.assert_called_with(mock_parent_frame, text="Plugin requires flight controller connection")
            mock_label.return_value.pack.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory")
    def test_load_plugin_shows_error_for_unknown_plugin(self, mock_factory, parameter_editor) -> None:
        """
        Test that __load_plugin shows error message for unknown plugin names.

        GIVEN: A plugin configuration with an unknown plugin name
        WHEN: __load_plugin is called
        THEN: An error label is displayed
        """
        # Mock factory to report plugin not registered
        mock_factory.is_registered.return_value = False

        # Create a mock parent frame
        mock_parent_frame = MagicMock()

        # Call the method with unknown plugin
        plugin_config = {"name": "unknown_plugin"}
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label") as mock_label:
            parameter_editor._ParameterEditorWindow__load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

            # Verify error label was created with translated text
            mock_label.assert_called_once()
            call_args = mock_label.call_args
            assert call_args[0][0] == mock_parent_frame
            assert "unknown_plugin" in call_args[1]["text"]
            mock_label.return_value.pack.assert_called_once()

    def test_update_plugin_layout_switches_from_plugin_to_no_plugin(self, parameter_editor) -> None:
        """
        Test switching from a plugin file to a non-plugin file properly cleans up.

        GIVEN: A parameter editor with an active plugin layout
        WHEN: __update_plugin_layout is called with None (no plugin)
        THEN: The plugin layout is destroyed and normal layout is restored
        """
        # Setup: Set current plugin to simulate having a plugin active
        parameter_editor.current_plugin = {"name": PLUGIN_MOTOR_TEST, "placement": "left"}
        parameter_editor.current_plugin_view = None  # Initialize attribute needed by cleanup
        parameter_editor.parameter_area_paned = None  # Initialize attribute needed by cleanup

        # Mock the necessary attributes
        mock_container = MagicMock()
        mock_table = MagicMock()
        parameter_editor.parameter_area_container = mock_container
        parameter_editor.parameter_editor_table = mock_table
        parameter_editor.main_frame = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame") as mock_frame,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable"),
        ):
            # Call with None to simulate switching to non-plugin file
            parameter_editor._ParameterEditorWindow__update_plugin_layout(None)  # pylint: disable=protected-access

            # Verify cleanup happened - container is destroyed (not individual widgets)
            mock_container.destroy.assert_called_once()

            # Verify new container was created
            mock_frame.assert_called()

            # Verify current_plugin was updated to None
            assert parameter_editor.current_plugin is None

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory")
    def test_load_plugin_handles_factory_exception(self, mock_factory, parameter_editor) -> None:
        """
        Test that __load_plugin handles exceptions from the plugin factory gracefully.

        GIVEN: A registered plugin but factory.create raises an exception
        WHEN: __load_plugin is called
        THEN: An error message is displayed and logged
        """
        # Mock the factory methods
        mock_factory.is_registered.return_value = True
        mock_factory.create.side_effect = TypeError("Invalid arguments")

        # Mock the configuration manager to return a valid model
        mock_model = MagicMock()
        with patch.object(parameter_editor.configuration_manager, "create_plugin_data_model", return_value=mock_model):
            # Create a mock parent frame
            mock_parent_frame = MagicMock()

            # Call the method
            plugin_config = {"name": "motor_test"}
            with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label") as mock_label:
                parameter_editor._ParameterEditorWindow__load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

                # Verify error label was created with proper styling
                assert mock_label.called
                call_args = mock_label.call_args
                assert "foreground" in call_args[1]
                assert call_args[1]["foreground"] == "red"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory")
    def test_switching_between_two_plugin_files_calls_lifecycle_hooks(self, mock_factory, parameter_editor) -> None:
        """
        Test that switching between two different plugin files calls lifecycle hooks properly.

        GIVEN: Two different plugin configurations
        WHEN: Switching from one plugin file to another
        THEN: on_deactivate is called on the first plugin and on_activate on the second
        """
        # Setup: Mock factory
        mock_factory.is_registered.return_value = True

        # Create two mock plugin views with lifecycle hooks
        mock_plugin_1 = MagicMock()
        mock_plugin_1.on_activate = MagicMock()
        mock_plugin_1.on_deactivate = MagicMock()
        mock_plugin_1.pack = MagicMock()
        mock_plugin_1.destroy = MagicMock()

        mock_plugin_2 = MagicMock()
        mock_plugin_2.on_activate = MagicMock()
        mock_plugin_2.on_deactivate = MagicMock()
        mock_plugin_2.pack = MagicMock()
        mock_plugin_2.destroy = MagicMock()

        mock_factory.create.side_effect = [mock_plugin_1, mock_plugin_2]

        # Mock the configuration manager to return a valid model
        mock_model = MagicMock()
        with (
            patch.object(parameter_editor.configuration_manager, "create_plugin_data_model", return_value=mock_model),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.tk.PanedWindow"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable"),
        ):
            # Setup initial state
            parameter_editor.current_plugin = None
            parameter_editor.current_plugin_view = None
            parameter_editor.parameter_area_paned = None
            parameter_editor.parameter_area_container = MagicMock()
            parameter_editor.parameter_editor_table = MagicMock()
            parameter_editor.main_frame = MagicMock()

            # First plugin activation
            plugin_config_1 = {"name": "motor_test", "placement": "left"}
            parameter_editor._ParameterEditorWindow__update_plugin_layout(plugin_config_1)  # pylint: disable=protected-access

            # Verify first plugin was activated
            mock_plugin_1.on_activate.assert_called_once()
            mock_plugin_1.on_deactivate.assert_not_called()

            # Second plugin activation
            plugin_config_2 = {"name": "other_plugin", "placement": "top"}
            parameter_editor._ParameterEditorWindow__update_plugin_layout(plugin_config_2)  # pylint: disable=protected-access

            # Verify first plugin was deactivated and destroyed
            mock_plugin_1.on_deactivate.assert_called_once()
            mock_plugin_1.destroy.assert_called_once()

            # Verify second plugin was activated
            mock_plugin_2.on_activate.assert_called_once()
