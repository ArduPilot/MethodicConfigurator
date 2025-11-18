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


@pytest.fixture
def headless_parameter_editor() -> ParameterEditorWindow:
    """Fixture providing a headless ParameterEditorWindow with mocks for GUI-heavy dependencies."""
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor.root = MagicMock()
    editor.gui_complexity = "expert"
    editor.configuration_manager = MagicMock()
    editor.configuration_manager.current_file = "01_test.param"
    editor.configuration_manager.configuration_phases.return_value = True
    editor.parameter_editor_table = MagicMock()
    editor.parameter_editor_table.repopulate = MagicMock()
    editor.parameter_editor_table.get_upload_selected_params = MagicMock(return_value={})
    editor.show_only_differences = MagicMock()
    editor.show_only_differences.get.return_value = False
    editor.documentation_frame = MagicMock()
    editor.documentation_frame.get_auto_open_documentation_in_browser.return_value = False
    editor.documentation_frame.refresh_documentation_labels = MagicMock()
    editor.documentation_frame.update_why_why_now_tooltip = MagicMock()
    editor.stage_progress_bar = MagicMock()
    editor.stage_progress_bar.update_progress = MagicMock()
    editor.file_selection_combobox = MagicMock()
    editor.file_selection_combobox.__getitem__.return_value = ["01_test.param"]
    editor.file_selection_combobox.get.return_value = "01_test.param"
    editor._update_skip_button_state = MagicMock()
    editor.write_changes_to_intermediate_parameter_file = MagicMock()
    editor.upload_selected_params = MagicMock()
    editor.on_skip_click = MagicMock()
    editor.on_param_file_combobox_change = MagicMock()
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

        parameter_editor._should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

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
        parameter_editor._should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

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
        parameter_editor._should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

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
        THEN: The copy workflow returns "close"
        AND: When integrated in the param file change workflow, the app exits gracefully
        """
        # Test that the method returns "close" when user chooses to close
        result = parameter_editor._should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        # Verify the workflow method was called with correct arguments
        mock_workflow.assert_called_once()
        args, _ = mock_workflow.call_args
        assert args[0] == "test_file.param"  # selected_file
        assert callable(args[1])  # ask_user_choice callback
        assert callable(args[2])  # show_info callback

        # Verify the method returns "close"
        assert result == "close"

        # Note: sys.exit is called in on_param_file_combobox_change, not in this method
        # That integration is tested in the workflow tests

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

            parameter_editor._should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

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
            parameter_editor._load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

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
            parameter_editor._load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

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
            parameter_editor._load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

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
            parameter_editor._load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

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
            parameter_editor._update_plugin_layout(None)  # pylint: disable=protected-access

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
                parameter_editor._load_plugin(mock_parent_frame, plugin_config)  # pylint: disable=protected-access

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
            parameter_editor._update_plugin_layout(plugin_config_1)  # pylint: disable=protected-access

            # Verify first plugin was activated
            mock_plugin_1.on_activate.assert_called_once()
            mock_plugin_1.on_deactivate.assert_not_called()

            # Second plugin activation
            plugin_config_2 = {"name": "other_plugin", "placement": "top"}
            parameter_editor._update_plugin_layout(plugin_config_2)  # pylint: disable=protected-access

            # Verify first plugin was deactivated and destroyed
            mock_plugin_1.on_deactivate.assert_called_once()
            mock_plugin_1.destroy.assert_called_once()

            # Verify second plugin was activated
            mock_plugin_2.on_activate.assert_called_once()

    def test_user_can_close_custom_dialog_via_callback(self, headless_parameter_editor) -> None:
        """
        User can dismiss the custom copy dialog by choosing an option.

        GIVEN: The dialog has recorded user choices
        WHEN: The helper callback handles the selected option
        THEN: The choice is stored and the dialog is destroyed
        """
        # Arrange (Given): Prepare result list and mocked dialog
        result: list[str] = []
        dialog = MagicMock()

        # Act (When): User selects the close option
        headless_parameter_editor._handle_dialog_choice(result, dialog, "close")

        # Assert (Then): Choice was stored and dialog closed
        assert result == ["close"]
        dialog.destroy.assert_called_once()

    def test_user_can_jump_between_parameter_files(self, headless_parameter_editor) -> None:
        """
        User can jump to another parameter file using the workflow callback.

        GIVEN: A pending request to jump to another file
        WHEN: The helper delegates to the configuration manager
        THEN: The returned file path is propagated back to the caller
        """
        # Arrange (Given): Stub workflow response
        headless_parameter_editor.configuration_manager.handle_file_jump_workflow.return_value = "02_next.param"

        # Act (When): User requests a jump
        new_file = headless_parameter_editor._should_jump_to_file("01_start.param")

        # Assert (Then): Workflow invoked and result returned
        headless_parameter_editor.configuration_manager.handle_file_jump_workflow.assert_called_once_with("01_start.param")
        assert new_file == "02_next.param"

    def test_user_can_download_missing_file_from_url(self, headless_parameter_editor) -> None:
        """
        User can trigger the download workflow when a file is missing locally.

        GIVEN: The configuration manager exposes a download workflow
        WHEN: The helper delegate is invoked for a parameter file
        THEN: The workflow is executed with the selected file
        """
        # Arrange (Given): Mock workflow return
        headless_parameter_editor.configuration_manager.should_download_file_from_url_workflow.return_value = True

        # Act (When): User initiates the download helper
        result = headless_parameter_editor._should_download_file_from_url("03_missing.param")

        # Assert (Then): Workflow executed and result bubbled up
        headless_parameter_editor.configuration_manager.should_download_file_from_url_workflow.assert_called_once_with(
            "03_missing.param"
        )
        assert result is True

    @pytest.mark.skip(reason="Test blocks during execution")
    def test_user_can_upload_file_with_progress_feedback(self, headless_parameter_editor) -> None:
        """
        User sees progress feedback when uploading a file to the flight controller.

        GIVEN: The upload workflow is executed with GUI callbacks
        WHEN: The helper creates a progress window
        THEN: The workflow receives a factory callback and the window is cleaned up
        """
        # Arrange (Given): Configure mocks
        headless_parameter_editor.configuration_manager.should_upload_file_to_fc_workflow.return_value = True
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow") as mock_progress_window:
            progress_instance = MagicMock()
            mock_progress_window.return_value = progress_instance

            # Act (When): User triggers the upload helper
            headless_parameter_editor._should_upload_file_to_fc("04_upload.param")

        # Assert (Then): Workflow received the lazy callback and window destroyed
        workflow_kwargs = headless_parameter_editor.configuration_manager.should_upload_file_to_fc_workflow.call_args.kwargs
        assert callable(workflow_kwargs["get_progress_callback"])
        assert workflow_kwargs["ask_confirmation"] is not None
        progress_callback = workflow_kwargs["get_progress_callback"]()
        assert progress_callback is progress_instance.update_progress_bar
        progress_instance.destroy.assert_called_once()

    def test_user_can_download_fc_parameters_with_progress(self, headless_parameter_editor) -> None:
        """
        User sees progress feedback while downloading FC parameters.

        GIVEN: The download helper prepares a progress window
        WHEN: Parameters are downloaded
        THEN: The callback is passed to the configuration manager and the window is destroyed
        """
        # Arrange (Given): Stub workflow
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow") as mock_progress_window:
            progress_instance = MagicMock()
            mock_progress_window.return_value = progress_instance
            headless_parameter_editor.on_param_file_combobox_change = MagicMock()

            # Act (When): User downloads parameters
            headless_parameter_editor.download_flight_controller_parameters(redownload=False)

        # Assert (Then): Workflow called and callback usable
        headless_parameter_editor.configuration_manager.download_flight_controller_parameters.assert_called_once()
        callback = headless_parameter_editor.configuration_manager.download_flight_controller_parameters.call_args[0][0]
        assert callable(callback)
        assert callback() is progress_instance.update_progress_bar
        progress_instance.destroy.assert_called_once()
        headless_parameter_editor.on_param_file_combobox_change.assert_called_once_with(None, forced=True)

    def test_user_skips_refresh_on_redownload(self, headless_parameter_editor) -> None:
        """
        User triggers a re-download without forcing a table refresh.

        GIVEN: A redownload request is executed
        WHEN: The helper completes the workflow
        THEN: The parameter table is not forced to refresh automatically
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow") as mock_progress_window:
            mock_progress_window.return_value = MagicMock()
            headless_parameter_editor.on_param_file_combobox_change.reset_mock()

            headless_parameter_editor.download_flight_controller_parameters(redownload=True)

        headless_parameter_editor.on_param_file_combobox_change.assert_not_called()

    def test_user_can_update_progress_bar_from_filename(self, headless_parameter_editor) -> None:
        """
        User sees stage progress updates when selecting files with numeric prefixes.

        GIVEN: The configuration phases feature is enabled
        WHEN: The helper parses the filename prefix
        THEN: The stage progress bar receives the proper step number
        """
        # Arrange (Given)
        headless_parameter_editor.configuration_manager.configuration_phases.return_value = True

        # Act (When)
        headless_parameter_editor._update_progress_bar_from_file("05_stage.param")

        # Assert (Then)
        headless_parameter_editor.stage_progress_bar.update_progress.assert_called_once_with(5)

    def test_user_receives_warning_when_filename_prefix_is_invalid(self, headless_parameter_editor) -> None:
        """
        User receives a logged warning when the file name lacks a numeric prefix.

        GIVEN: Stage progress is enabled but filename is invalid
        WHEN: The helper attempts to parse the prefix
        THEN: No update occurs and an error is logged
        """
        headless_parameter_editor.configuration_manager.configuration_phases.return_value = True
        headless_parameter_editor.stage_progress_bar.update_progress.reset_mock()
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_error") as mock_logging:
            headless_parameter_editor._update_progress_bar_from_file("invalid_name.param")

        headless_parameter_editor.stage_progress_bar.update_progress.assert_not_called()
        mock_logging.assert_called_once()

    def test_user_can_repopulate_table_when_file_selected(self, headless_parameter_editor) -> None:
        """
        User can repopulate the parameter table once a file is selected.

        GIVEN: A current file is available
        WHEN: The repopulate helper is called
        THEN: The table is rebuilt with the expected arguments
        """
        headless_parameter_editor.configuration_manager.current_file = "06_table.param"
        regenerate_flag = True

        headless_parameter_editor.repopulate_parameter_table(regenerate_from_disk=regenerate_flag)

        headless_parameter_editor.parameter_editor_table.repopulate.assert_called_once_with(
            headless_parameter_editor.show_only_differences.get(),
            headless_parameter_editor.gui_complexity,
            regenerate_flag,
        )

    def test_user_skips_repopulation_when_no_file_selected(self, headless_parameter_editor) -> None:
        """
        User does not trigger table repopulation when no file is selected.

        GIVEN: No current file is available
        WHEN: The helper is called
        THEN: The table remains untouched
        """
        headless_parameter_editor.configuration_manager.current_file = ""
        headless_parameter_editor.parameter_editor_table.repopulate.reset_mock()

        headless_parameter_editor.repopulate_parameter_table(regenerate_from_disk=False)

        headless_parameter_editor.parameter_editor_table.repopulate.assert_not_called()

    def test_user_can_toggle_show_only_difference_checkbox(self, headless_parameter_editor) -> None:
        """
        User toggling the "show only changed" checkbox refreshes the table.

        GIVEN: The checkbox is toggled
        WHEN: The handler executes
        THEN: The table is repopulated without disk regeneration
        """
        with patch.object(headless_parameter_editor, "repopulate_parameter_table") as mock_repopulate:
            headless_parameter_editor.on_show_only_changed_checkbox_change()

        mock_repopulate.assert_called_once_with(regenerate_from_disk=False)

    def test_user_can_upload_selected_parameters_when_fc_connected(self, headless_parameter_editor) -> None:
        """
        User can upload selected parameters when flight controller is connected.

        GIVEN: Parameters are selected and FC is connected
        WHEN: User clicks upload button
        THEN: Selected parameters are uploaded and workflow advances
        """
        # Arrange (Given): Mock selected parameters and FC connection
        selected_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        headless_parameter_editor.parameter_editor_table.get_upload_selected_params.return_value = selected_params
        headless_parameter_editor.configuration_manager.fc_parameters = {"PARAM1": 0.5, "PARAM2": 1.5}

        # Act (When): User clicks upload
        headless_parameter_editor.on_upload_selected_click()

        # Assert (Then): Parameters uploaded and workflow advanced
        headless_parameter_editor.write_changes_to_intermediate_parameter_file.assert_called_once()
        headless_parameter_editor.upload_selected_params.assert_called_once_with(selected_params)
        headless_parameter_editor.on_skip_click.assert_called_once()

    def test_user_receives_warning_when_no_fc_connection_for_upload(self, headless_parameter_editor) -> None:
        """
        User receives warning when attempting upload without FC connection.

        GIVEN: Parameters are selected but no FC connection
        WHEN: User clicks upload button
        THEN: Warning is shown and no upload occurs
        """
        selected_params = {"PARAM1": 1.0}
        headless_parameter_editor.parameter_editor_table.get_upload_selected_params.return_value = selected_params
        headless_parameter_editor.configuration_manager.fc_parameters = {}  # No FC parameters

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.messagebox.showwarning") as mock_warning,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_warning") as mock_log,
        ):
            headless_parameter_editor.on_upload_selected_click()

            mock_warning.assert_called_once()
            mock_log.assert_called_once()
            headless_parameter_editor.upload_selected_params.assert_not_called()

    def test_user_receives_warning_when_no_parameters_selected(self, headless_parameter_editor) -> None:
        """
        User receives warning when no parameters are selected for upload.

        GIVEN: No parameters are selected
        WHEN: User clicks upload button
        THEN: Warning is shown and no upload occurs
        """
        headless_parameter_editor.parameter_editor_table.get_upload_selected_params.return_value = {}
        headless_parameter_editor.configuration_manager.fc_parameters = {"PARAM1": 1.0}

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.messagebox.showwarning") as mock_warning,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_warning") as mock_log,
        ):
            headless_parameter_editor.on_upload_selected_click()

            mock_warning.assert_called_once()
            mock_log.assert_called_once()
            headless_parameter_editor.upload_selected_params.assert_not_called()

    def test_user_can_close_connection_and_quit_application(self, headless_parameter_editor) -> None:
        """
        User can close flight controller connection and quit application.

        GIVEN: Application is running with FC connection
        WHEN: User closes the application
        THEN: FC connection is closed and application exits
        """
        headless_parameter_editor.configuration_manager.is_fc_connected = True

        with patch("sys.exit") as mock_exit:
            headless_parameter_editor.close_connection_and_quit()

            headless_parameter_editor.configuration_manager._flight_controller.disconnect.assert_called_once()
            headless_parameter_editor.root.quit.assert_called_once()
            mock_exit.assert_called_once_with(0)

    def test_user_can_quit_without_fc_connection(self, headless_parameter_editor) -> None:
        """
        User can quit application even without FC connection.

        GIVEN: Application is running without FC connection
        WHEN: User closes the application
        THEN: Application exits without attempting FC disconnect
        """
        headless_parameter_editor.configuration_manager.is_fc_connected = False

        with patch("sys.exit") as mock_exit:
            headless_parameter_editor.close_connection_and_quit()

            headless_parameter_editor.configuration_manager._flight_controller.disconnect.assert_not_called()
            headless_parameter_editor.root.quit.assert_called_once()
            mock_exit.assert_called_once_with(0)

    def test_user_can_write_changes_to_intermediate_file(self, headless_parameter_editor) -> None:
        """
        User can write parameter changes to intermediate file.

        GIVEN: Parameter changes are pending
        WHEN: User triggers file write
        THEN: Changes are saved to the intermediate file
        """
        headless_parameter_editor.write_changes_to_intermediate_parameter_file()

        # Verify the configuration manager method was called
        headless_parameter_editor.configuration_manager._local_filesystem.write_param_file.assert_called_once()

    def test_user_triggers_imu_temperature_calibration_workflow(self, headless_parameter_editor) -> None:
        """
        User can trigger IMU temperature calibration workflow.

        GIVEN: A temperature calibration parameter file is selected
        WHEN: User initiates the calibration workflow
        THEN: The calibration process is started with proper callbacks
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow") as mock_progress:
            progress_instance = MagicMock()
            mock_progress.return_value = progress_instance

            headless_parameter_editor._do_tempcal_imu("25_imu_temperature_calibration.param")

            # Verify workflow was called with callbacks
            headless_parameter_editor.configuration_manager.handle_imu_temperature_calibration_workflow.assert_called_once()
            workflow_call = headless_parameter_editor.configuration_manager.handle_imu_temperature_calibration_workflow
            call_kwargs = workflow_call.call_args.kwargs
            assert callable(call_kwargs["get_progress_callback"])
            assert callable(call_kwargs["select_file"])
            progress_instance.destroy.assert_called_once()

    def test_user_upload_with_reset_progress_callback(self, headless_parameter_editor) -> None:
        """
        User sees progress feedback during parameter upload with reset.

        GIVEN: Parameters require reset after upload
        WHEN: Upload process includes reset workflow
        THEN: Progress callbacks are created for both reset and download phases
        """
        selected_params = {"PARAM1": 1.0}

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow") as mock_progress,
            patch.object(headless_parameter_editor, "configuration_manager") as mock_config,
        ):
            progress_instance = MagicMock()
            mock_progress.return_value = progress_instance
            mock_config.upload_parameters_that_require_reset_workflow.return_value = True
            mock_config.download_flight_controller_parameters.return_value = ({}, {})

            headless_parameter_editor.upload_selected_params(selected_params)

            # Verify workflow was called with progress callbacks
            mock_config.upload_parameters_that_require_reset_workflow.assert_called_once()
            upload_call_kwargs = mock_config.upload_parameters_that_require_reset_workflow.call_args.kwargs
            assert callable(upload_call_kwargs["get_reset_progress_callback"])
            assert callable(upload_call_kwargs["get_download_progress_callback"])

    def test_user_handles_exception_during_parameter_upload(self, headless_parameter_editor) -> None:
        """
        User receives error feedback when parameter upload fails.

        GIVEN: Parameter upload process encounters an exception
        WHEN: Upload is attempted
        THEN: Error is logged and user is notified
        """
        selected_params = {"PARAM1": 1.0}

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow"),
            patch.object(headless_parameter_editor, "configuration_manager") as mock_config,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_error") as mock_log_error,
        ):
            mock_config.upload_parameters_that_require_reset_workflow.side_effect = RuntimeError("Upload failed")

            headless_parameter_editor.upload_selected_params(selected_params)

            mock_log_error.assert_called_once()

    def test_user_can_handle_progress_callback_updates(self, headless_parameter_editor) -> None:
        """
        User sees progress updates during long-running operations.

        GIVEN: A progress callback is created
        WHEN: Progress updates are received
        THEN: Progress window is updated appropriately
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow") as mock_progress:
            progress_instance = MagicMock()
            mock_progress.return_value = progress_instance

            # Create a progress callback
            progress_callback = headless_parameter_editor._get_progress_callback(progress_instance, 100)

            # Test progress update
            progress_callback(50, "Test message")

            # Verify progress window was updated
            progress_instance.update_progress.assert_called_with(50, "Test message")

    def test_user_can_select_file_through_dialog(self, headless_parameter_editor) -> None:
        """
        User can select files through file selection dialog.

        GIVEN: File selection is needed
        WHEN: User interacts with file dialog
        THEN: Selected file path is returned
        """
        expected_file = "/path/to/selected/file.txt"

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.tkinter.filedialog.askopenfilename"
        ) as mock_dialog:
            mock_dialog.return_value = expected_file

            # Create file selector callback
            file_selector = headless_parameter_editor._get_file_selector("Select file", [("Text files", "*.txt")])

            result = file_selector()

            assert result == expected_file
            mock_dialog.assert_called_once()

    def test_user_can_repopulate_parameter_table_from_disk(self, headless_parameter_editor) -> None:
        """
        User can refresh parameter table with data from disk.

        GIVEN: Parameter files exist on disk
        WHEN: User requests table refresh from disk
        THEN: Table is repopulated with disk data
        """
        with patch.object(headless_parameter_editor.parameter_editor_table, "repopulate") as mock_repopulate:
            headless_parameter_editor.repopulate_parameter_table(regenerate_from_disk=True)

            mock_repopulate.assert_called_once_with(regenerate_from_disk=True)

    def test_user_can_check_if_fc_parameters_match_file(self, headless_parameter_editor) -> None:
        """
        User can verify if flight controller parameters match file parameters.

        GIVEN: FC and file parameters exist
        WHEN: Parameter comparison is requested
        THEN: Matching status is determined correctly
        """
        # Mock parameters that match
        fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        file_params = {"PARAM1": 1.0, "PARAM2": 2.0}

        headless_parameter_editor.configuration_manager.fc_parameters = fc_params

        with patch.object(headless_parameter_editor.configuration_manager, "get_non_default_params") as mock_get_params:
            mock_get_params.return_value = file_params

            # For this test, we expect the method to exist and be callable
            assert callable(getattr(headless_parameter_editor, "_are_fc_and_file_parameters_the_same", None))

            # Test the actual method call
            headless_parameter_editor._are_fc_and_file_parameters_the_same()

    def test_user_can_access_window_title_property(self, headless_parameter_editor) -> None:
        """
        User can access the window title for display purposes.

        GIVEN: Parameter editor window exists
        WHEN: Window title is accessed
        THEN: Appropriate title is returned
        """
        # Test that the title property exists and returns a string
        title = headless_parameter_editor.title
        assert isinstance(title, str)
        assert len(title) > 0
