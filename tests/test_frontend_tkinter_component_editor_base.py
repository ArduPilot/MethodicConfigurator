#!/usr/bin/env python3

"""
Behavior-driven tests for ComponentEditorWindowBase.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser
from tkinter import ttk
from typing import Union, get_args, get_origin
from unittest.mock import MagicMock, patch

import pytest
from test_data_model_vehicle_components_common import REALISTIC_VEHICLE_DATA, ComponentDataModelFixtures

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_vehicle_components import ComponentDataModel
from ardupilot_methodic_configurator.frontend_tkinter_component_editor_base import (
    VEHICLE_IMAGE_HEIGHT_PIX,
    VEHICLE_IMAGE_WIDTH_PIX,
    WINDOW_WIDTH_PIX,
    ComponentEditorWindowBase,
    EntryWidget,
    argument_parser,
)

# pylint: disable=protected-access, too-many-lines, redefined-outer-name, unused-argument, too-few-public-methods


def setup_common_editor_mocks(editor) -> ComponentEditorWindowBase:
    """Set up common mock attributes and methods for editor fixtures."""
    # Set up all required attributes manually
    editor.root = MagicMock()
    editor.main_frame = MagicMock()
    editor.scroll_frame = MagicMock()
    editor.scroll_frame.view_port = MagicMock()
    editor.version = "1.0.0"

    # Mock filesystem and methods with proper schema loading
    editor.local_filesystem = MagicMock(spec=LocalFilesystem)
    editor.local_filesystem.vehicle_dir = "dummy_vehicle_dir"
    editor.local_filesystem.get_component_property_description = MagicMock(return_value=("Test description", False))
    editor.local_filesystem.vehicle_image_exists = MagicMock(return_value=False)
    editor.local_filesystem.vehicle_image_filepath = MagicMock(return_value="test.jpg")
    editor.local_filesystem.save_component_to_system_templates = MagicMock()

    # Mock the vehicle_components_fs attribute structure
    mock_vehicle_components_fs = MagicMock()
    mock_vehicle_components_fs.data = MagicMock()
    mock_vehicle_components_fs.json_filename = "vehicle_components.json"
    editor.local_filesystem.vehicle_components_fs = mock_vehicle_components_fs

    # Mock the vehicle_components methods that are accessed directly
    editor.local_filesystem.load_schema = MagicMock(return_value={"properties": {}})
    editor.local_filesystem.get_component_property_description = MagicMock(return_value=("Test description", False))

    # Setup test data and data model
    editor.entry_widgets = {}

    # Create data model with realistic test data
    component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
    schema = ComponentDataModelFixtures.create_schema()
    editor.data_model = ComponentDataModel(REALISTIC_VEHICLE_DATA, component_datatypes, schema)

    # Mock specific methods that are used in tests
    editor.data_model.set_component_value = MagicMock()
    editor.data_model.update_component = MagicMock()

    # Override methods that might cause UI interactions in tests
    # Mock _add_widget completely to avoid UI creation
    editor._add_widget = MagicMock()
    editor.put_image_in_label = MagicMock(return_value=MagicMock())
    editor.add_entry_or_combobox = MagicMock(return_value=MagicMock())
    editor.complexity_var = MagicMock()

    return editor


def add_editor_helper_methods(editor) -> None:
    """Add common helper methods for testing that bypass UI operations."""

    # Use add_widget as a public proxy for _add_widget for easier testing
    def add_widget_proxy(parent, key, value, path) -> None:
        return editor._add_widget(parent, key, value, path)

    editor.add_widget = add_widget_proxy

    # Add helper methods for testing that bypass UI operations
    def test_populate_frames() -> None:
        # This is a test-friendly version that doesn't involve actual UI widgets
        components = editor.data_model.get_all_components()
        for key, value in components.items():
            editor._add_widget(editor.scroll_frame.view_port, key, value, [])

    editor.populate_frames = test_populate_frames


class SharedTestArgumentParser:
    """Shared test cases for the argument_parser function to avoid duplication."""

    def test_argument_parser(self) -> None:
        """Test argument_parser function."""
        with patch("sys.argv", ["test_script", "--vehicle-dir", "test_dir", "--vehicle-type", "ArduCopter"]):
            args = argument_parser()

            assert hasattr(args, "vehicle_dir")
            assert hasattr(args, "vehicle_type")
            assert hasattr(args, "skip_component_editor")

    def test_argument_parser_with_skip_component_editor(self) -> None:
        """Test argument_parser with skip-component-editor flag."""
        with patch(
            "sys.argv", ["test_script", "--vehicle-dir", "test_dir", "--vehicle-type", "ArduCopter", "--skip-component-editor"]
        ):
            args = argument_parser()

            assert args.skip_component_editor is True


@pytest.fixture
def editor_with_mocked_root() -> ComponentEditorWindowBase:
    """Create a mock ComponentEditorWindowBase for testing."""
    # Create the class without initialization
    with patch.object(ComponentEditorWindowBase, "__init__", return_value=None):
        editor = ComponentEditorWindowBase()  # pylint: disable=no-value-for-parameter

        # Set up common mocks and helper methods
        setup_common_editor_mocks(editor)
        add_editor_helper_methods(editor)

        yield editor


class TestArgumentParserBehavior:
    """Test argument parser behavior and functionality."""

    def test_argument_parser_creates_all_required_attributes(self) -> None:
        """Test that argument parser creates all required command line attributes."""
        with patch("sys.argv", ["test_script", "--vehicle-dir", "test_dir", "--vehicle-type", "ArduCopter"]):
            args = argument_parser()

            # Verify all expected attributes exist
            required_attrs = ["vehicle_dir", "vehicle_type", "skip_component_editor", "loglevel"]
            for attr in required_attrs:
                assert hasattr(args, attr), f"Missing required attribute: {attr}"

    def test_argument_parser_handles_skip_component_editor_flag(self) -> None:
        """Test that skip-component-editor flag is properly handled."""
        with patch(
            "sys.argv", ["test_script", "--vehicle-dir", "test", "--vehicle-type", "ArduCopter", "--skip-component-editor"]
        ):
            args = argument_parser()
            assert args.skip_component_editor is True

        with patch("sys.argv", ["test_script", "--vehicle-dir", "test", "--vehicle-type", "ArduCopter"]):
            args = argument_parser()
            assert args.skip_component_editor is False

    def test_argument_parser_handles_different_log_levels(self) -> None:
        """Test that different log levels are properly parsed."""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]

        for level in log_levels:
            with patch(
                "sys.argv",
                ["test_script", "--vehicle-dir", "test", "--vehicle-type", "ArduCopter", "--loglevel", level],
            ):
                args = argument_parser()
                assert args.loglevel == level


@pytest.fixture
def mock_filesystem() -> MagicMock:
    """Fixture providing a mock filesystem with realistic test data."""
    filesystem = MagicMock(spec=LocalFilesystem)
    filesystem.vehicle_dir = "test_vehicle"
    filesystem.doc_dict = {}
    filesystem.vehicle_image_exists.return_value = False
    filesystem.vehicle_image_filepath.return_value = "test.jpg"
    filesystem.save_component_to_system_templates = MagicMock()

    # Mock schema loading to return valid data
    filesystem.load_schema.return_value = {"properties": {}}
    filesystem.load_vehicle_components_json_data.return_value = REALISTIC_VEHICLE_DATA

    return filesystem


@pytest.fixture
def mock_data_model() -> MagicMock:
    """Fixture providing a mock data model with realistic behavior."""
    data_model = MagicMock(spec=ComponentDataModel)
    data_model.is_valid_component_data.return_value = True
    data_model.has_components.return_value = True
    data_model.get_all_components.return_value = REALISTIC_VEHICLE_DATA
    data_model.extract_component_data_from_entries.return_value = {"test": "data"}
    data_model.save_to_filesystem.return_value = (False, "")
    return data_model


@pytest.fixture
def configured_editor(mock_filesystem: MagicMock, mock_data_model: MagicMock) -> ComponentEditorWindowBase:
    """Fixture providing a properly configured editor for behavior testing."""
    return ComponentEditorWindowBase.create_for_testing(
        version="1.0.0", local_filesystem=mock_filesystem, data_model=mock_data_model
    )


class TestUserArgumentParsingWorkflows:
    """Test user workflows for command line argument parsing."""

    def test_user_can_parse_basic_command_arguments(self) -> None:
        """
        User can provide basic command line arguments to start the application.

        GIVEN: A user wants to start the component editor with basic settings
        WHEN: They provide vehicle directory and type arguments
        THEN: The arguments should be parsed correctly with default values
        """
        # Arrange: Set up command line arguments
        test_args = ["test_script", "--vehicle-dir", "test_dir", "--vehicle-type", "ArduCopter"]

        # Act: Parse the arguments
        with patch("sys.argv", test_args):
            args = argument_parser()

        # Assert: Verify arguments are parsed correctly
        assert args.vehicle_dir == "test_dir"
        assert args.vehicle_type == "ArduCopter"
        assert args.skip_component_editor is False

    def test_user_can_skip_component_editor_when_needed(self) -> None:
        """
        User can skip the component editor interface when components are pre-configured.

        GIVEN: A user has already configured their vehicle components
        WHEN: They provide the skip-component-editor flag
        THEN: The skip flag should be properly set to True
        """
        # Arrange: Set up command line arguments with skip flag
        test_args = ["test_script", "--vehicle-dir", "test", "--vehicle-type", "ArduCopter", "--skip-component-editor"]

        # Act: Parse the arguments
        with patch("sys.argv", test_args):
            args = argument_parser()

        # Assert: Verify skip flag is enabled
        assert args.skip_component_editor is True

    def test_user_can_configure_different_log_levels_for_debugging(self) -> None:
        """
        User can set different logging levels for troubleshooting purposes.

        GIVEN: A user needs to debug the application behavior
        WHEN: They specify different log levels
        THEN: Each log level should be properly parsed
        """
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]

        for level in log_levels:
            # Arrange: Set up command line arguments with specific log level
            test_args = ["test_script", "--vehicle-dir", "test", "--vehicle-type", "ArduCopter", "--loglevel", level]

            # Act: Parse the arguments
            with patch("sys.argv", test_args):
                args = argument_parser()

            # Assert: Verify log level is set correctly
            assert args.loglevel == level


class TestDataValidationWorkflows:
    """Test user workflows for data validation."""

    def test_user_sees_no_errors_when_all_data_is_valid(self, editor_with_mocked_root: ComponentEditorWindowBase) -> None:
        """
        User receives no error messages when all component data is valid.

        GIVEN: A user has filled in all component fields with valid data
        WHEN: The system validates all entered data
        THEN: No error messages should be displayed and validation should pass
        """
        # Arrange: Set up valid entry widgets with proper data
        mock_entry = MagicMock(spec=ttk.Entry)
        mock_entry.get.return_value = "1000"

        mock_combobox = MagicMock(spec=ttk.Combobox)
        mock_combobox.get.return_value = "PWM"

        editor_with_mocked_root.entry_widgets = {
            ("Motor", "Specifications", "KV"): mock_entry,
            ("RC Receiver", "FC Connection", "Protocol"): mock_combobox,
        }

        # Mock data model to return valid validation
        editor_with_mocked_root.data_model.validate_all_data = MagicMock(return_value=(True, []))

        # Act: User triggers validation
        result = editor_with_mocked_root.validate_data_and_highlight_errors_in_red()

        # Assert: No errors should be returned
        assert result == ""
        editor_with_mocked_root.data_model.validate_all_data.assert_called_once()

    def test_user_sees_error_highlighting_for_invalid_entry_values(
        self, editor_with_mocked_root: ComponentEditorWindowBase
    ) -> None:
        """
        User sees visual feedback when entry fields contain invalid values.

        GIVEN: A user has entered invalid data in text entry fields
        WHEN: The system validates the data
        THEN: Invalid entries should be highlighted in red and error messages displayed
        """
        # Arrange: Set up invalid entry data
        mock_invalid_entry = MagicMock(spec=ttk.Entry)
        mock_invalid_entry.get.return_value = "99999"  # Invalid high value

        editor_with_mocked_root.entry_widgets = {
            ("Motor", "Specifications", "KV"): mock_invalid_entry,
        }

        # Mock validation to return errors
        editor_with_mocked_root.data_model.validate_all_data = MagicMock(return_value=(False, ["KV value too high"]))
        editor_with_mocked_root.data_model.validate_entry_limits = MagicMock(
            return_value=("Value exceeds maximum limit", None)
        )

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message") as mock_error:
            # Act: User triggers validation
            result = editor_with_mocked_root.validate_data_and_highlight_errors_in_red()

            # Assert: Entry should be styled as invalid and error shown
            mock_invalid_entry.configure.assert_called_once_with(style="entry_input_invalid.TEntry")
            mock_error.assert_called_once()
            assert result != ""

    def test_user_sees_error_highlighting_for_invalid_combobox_selections(
        self, editor_with_mocked_root: ComponentEditorWindowBase
    ) -> None:
        """
        User sees visual feedback when combobox selections are invalid.

        GIVEN: A user has selected invalid options in combobox fields
        WHEN: The system validates the selections
        THEN: Invalid comboboxes should be highlighted in red
        """
        # Arrange: Set up invalid combobox selection
        mock_invalid_combobox = MagicMock(spec=ttk.Combobox)
        mock_invalid_combobox.get.return_value = "INVALID_PROTOCOL"

        editor_with_mocked_root.entry_widgets = {
            ("RC Receiver", "FC Connection", "Protocol"): mock_invalid_combobox,
        }

        # Mock validation to return errors
        editor_with_mocked_root.data_model.validate_all_data = MagicMock(return_value=(False, ["Invalid protocol selected"]))
        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=("PWM", "SBUS", "PPM"))

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message"):
            # Act: User triggers validation
            result = editor_with_mocked_root.validate_data_and_highlight_errors_in_red()

            # Assert: Combobox should be styled as invalid
            mock_invalid_combobox.configure.assert_called_once_with(style="comb_input_invalid.TCombobox")
            assert result != ""

    def test_user_sees_valid_styling_for_corrected_combobox_values(
        self, editor_with_mocked_root: ComponentEditorWindowBase
    ) -> None:
        """
        User sees positive visual feedback when combobox values become valid.

        GIVEN: A user has corrected a combobox selection to a valid value
        WHEN: The system validates the corrected data
        THEN: The combobox should be highlighted as valid
        """
        # Arrange: Set up valid combobox selection
        mock_valid_combobox = MagicMock(spec=ttk.Combobox)
        mock_valid_combobox.get.return_value = "PWM"

        editor_with_mocked_root.entry_widgets = {
            ("RC Receiver", "FC Connection", "Protocol"): mock_valid_combobox,
        }

        # Mock validation - overall fails but this combobox is valid
        editor_with_mocked_root.data_model.validate_all_data = MagicMock(return_value=(False, ["Other validation error"]))
        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=("PWM", "SBUS", "PPM"))

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message"):
            # Act: User triggers validation
            editor_with_mocked_root.validate_data_and_highlight_errors_in_red()

            # Assert: Combobox should be styled as valid
            mock_valid_combobox.configure.assert_called_once_with(style="comb_input_valid.TCombobox")

    def test_user_sees_limited_error_messages_when_many_errors_exist(
        self, editor_with_mocked_root: ComponentEditorWindowBase
    ) -> None:
        """
        User sees a manageable number of error messages when many validation errors exist.

        GIVEN: A user has multiple validation errors across many fields
        WHEN: The system validates all data
        THEN: Only the first 3 errors should be shown with a count of remaining errors
        """
        # Arrange: Set up entry that will trigger validation
        mock_entry = MagicMock(spec=ttk.Entry)
        mock_entry.get.return_value = "invalid"

        editor_with_mocked_root.entry_widgets = {
            ("Motor", "Specifications", "KV"): mock_entry,
        }

        # Mock validation to return many errors
        many_errors = ["Error 1", "Error 2", "Error 3", "Error 4", "Error 5"]
        editor_with_mocked_root.data_model.validate_all_data = MagicMock(return_value=(False, many_errors))
        editor_with_mocked_root.data_model.validate_entry_limits = MagicMock(return_value=("Invalid value", None))

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message") as mock_error:
            # Act: User triggers validation
            result = editor_with_mocked_root.validate_data_and_highlight_errors_in_red()

            # Assert: Should show first 3 errors + count of remaining
            mock_error.assert_called_once()
            error_message = mock_error.call_args[0][1]
            assert "Error 1" in error_message
            assert "Error 2" in error_message
            assert "Error 3" in error_message
            assert "2 more errors" in error_message
            assert result != ""

    def test_user_validation_only_processes_entry_and_combobox_widgets(
        self, editor_with_mocked_root: ComponentEditorWindowBase
    ) -> None:
        """
        User data validation only processes actual input widgets, ignoring other UI elements.

        GIVEN: A user interface contains various widget types including input fields
        WHEN: The system validates user input data
        THEN: Only Entry and Combobox widgets should be included in validation
        """
        # Arrange: Set up mixed widget types
        mock_entry = MagicMock(spec=ttk.Entry)
        mock_entry.get.return_value = "1000"

        mock_combobox = MagicMock(spec=ttk.Combobox)
        mock_combobox.get.return_value = "PWM"

        mock_label = MagicMock()  # Non-input widget

        editor_with_mocked_root.entry_widgets = {
            ("Motor", "Specifications", "KV"): mock_entry,
            ("RC Receiver", "FC Connection", "Protocol"): mock_combobox,
            ("Some", "Label", "Widget"): mock_label,  # Should be ignored
        }

        editor_with_mocked_root.data_model.validate_all_data = MagicMock(return_value=(True, []))

        # Act: User triggers validation
        result = editor_with_mocked_root.validate_data_and_highlight_errors_in_red()

        # Assert: Only Entry and Combobox values should be validated
        expected_values = {
            ("Motor", "Specifications", "KV"): "1000",
            ("RC Receiver", "FC Connection", "Protocol"): "PWM",
            # Label widget should NOT be included
        }
        editor_with_mocked_root.data_model.validate_all_data.assert_called_once_with(expected_values)
        assert result == ""


class TestComponentDataManagementWorkflows:
    """Test user workflows for managing component data."""

    def test_user_can_extract_component_data_from_gui_inputs(self, configured_editor: ComponentEditorWindowBase) -> None:
        """
        User can extract component data that they've entered through the GUI.

        GIVEN: A user has filled in component data through GUI fields
        WHEN: They request to extract the data for a specific component
        THEN: The system should return the correctly formatted component data
        """
        # Arrange: Set up mock entry widgets with realistic user input
        component_name = "Motor"
        mock_entry1 = MagicMock()
        mock_entry1.get.return_value = "T-Motor MN3110"
        mock_entry2 = MagicMock()
        mock_entry2.get.return_value = "700"

        configured_editor.entry_widgets = {("Motor", "Model"): mock_entry1, ("Motor", "Specifications", "KV"): mock_entry2}

        expected_result = {"Model": "T-Motor MN3110", "Specifications": {"KV": "700"}}
        configured_editor.data_model.extract_component_data_from_entries.return_value = expected_result

        # Act: Extract component data from GUI
        result = configured_editor.get_component_data_from_gui(component_name)

        # Assert: Extracted data should match expected format
        configured_editor.data_model.extract_component_data_from_entries.assert_called_once_with(
            component_name, {("Motor", "Model"): "T-Motor MN3110", ("Motor", "Specifications", "KV"): "700"}
        )
        assert result == expected_result

    def test_user_can_update_component_values_and_see_ui_changes(self, configured_editor: ComponentEditorWindowBase) -> None:
        """
        User can update component values and immediately see the changes in the UI.

        GIVEN: A user wants to modify a component value
        WHEN: They update the value through the interface
        THEN: Both the data model and UI widget should be updated
        """
        # Arrange: Set up component path and new value
        path = ("Motor", "Model")
        new_value = "Updated Motor Model"
        mock_entry = MagicMock()
        configured_editor.entry_widgets[path] = mock_entry

        # Act: Update component value and UI
        configured_editor.set_component_value_and_update_ui(path, new_value)

        # Assert: Both data model and UI should be updated
        configured_editor.data_model.set_component_value.assert_called_once_with(path, new_value)
        mock_entry.delete.assert_called_once_with(0, tk.END)
        mock_entry.insert.assert_called_once_with(0, new_value)
        mock_entry.config.assert_called_once_with(state="disabled")

    def test_user_can_update_values_even_without_corresponding_ui_widget(
        self, configured_editor: ComponentEditorWindowBase
    ) -> None:
        """
        User can update component values even when no UI widget exists.

        GIVEN: A user updates a component value programmatically
        WHEN: No corresponding UI widget exists for that path
        THEN: The data model should still be updated without errors
        """
        # Arrange: Set up component path with no corresponding widget
        path = ("Motor", "NonExistentField")
        new_value = "Some Value"

        # Act: Update component value without widget
        configured_editor.set_component_value_and_update_ui(path, new_value)

        # Assert: Data model should be updated
        configured_editor.data_model.set_component_value.assert_called_once_with(path, new_value)


class TestSaveOperationWorkflows:
    """Test user workflows for saving component data."""

    @pytest.fixture
    def editor_for_save_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for save operation testing."""
        data_model = MagicMock(spec=ComponentDataModel)
        data_model.save_to_filesystem.return_value = (False, "")

        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

        # Mock UI methods to avoid actual UI operations
        editor.validate_data_and_highlight_errors_in_red = MagicMock(return_value="")
        return editor

    def test_user_can_successfully_save_component_data(self, editor_for_save_tests: ComponentEditorWindowBase) -> None:
        """
        User can successfully save their component configuration.

        GIVEN: A user has completed their component configuration
        WHEN: They save the configuration and it succeeds
        THEN: The data should be saved
        """
        # Arrange: Configure successful save operation
        editor_for_save_tests.data_model.save_to_filesystem.return_value = (False, "")

        # Act: Save component data
        editor_for_save_tests.save_component_json()

        # Assert: Save operation should be attempted
        editor_for_save_tests.data_model.save_to_filesystem.assert_called_once_with(editor_for_save_tests.local_filesystem)

    def test_user_receives_error_feedback_when_save_fails(self, editor_for_save_tests: ComponentEditorWindowBase) -> None:
        """
        User receives clear error feedback when save operation fails.

        GIVEN: A user attempts to save their configuration
        WHEN: The save operation fails due to an error
        THEN: An error message should be displayed to the user
        """
        # Arrange: Configure failed save operation
        editor_for_save_tests.data_model.save_to_filesystem.return_value = (True, "File system error")

        # Act: Attempt to save with mocked error display
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message") as mock_error:
            editor_for_save_tests.save_component_json()

        # Assert: Error message should be displayed
        editor_for_save_tests.data_model.save_to_filesystem.assert_called_once_with(editor_for_save_tests.local_filesystem)
        mock_error.assert_called_once()

    def test_user_must_confirm_before_saving_component_data(self, editor_for_save_tests: ComponentEditorWindowBase) -> None:
        """
        User must confirm that all component properties are correct before saving.

        GIVEN: A user wants to save their component configuration
        WHEN: They trigger the save operation
        THEN: They should be prompted to confirm their data is correct
        """
        # Arrange: Mock the confirmation dialog
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.messagebox.askyesno", return_value=True
        ):
            # Act: Trigger validate and save operation
            editor_for_save_tests.on_save_pressed()

        # Assert: Validation and save should proceed
        editor_for_save_tests.validate_data_and_highlight_errors_in_red.assert_called_once()


class TestWindowClosingWorkflows:
    """Test user workflows for closing the editor window."""

    @pytest.fixture
    def editor_for_closing_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for window closing tests."""
        editor = ComponentEditorWindowBase.create_for_testing(version="1.0.0", local_filesystem=mock_filesystem)
        editor.save_component_json = MagicMock()
        return editor

    def test_user_can_save_before_closing_when_prompted(self, editor_for_closing_tests: ComponentEditorWindowBase) -> None:
        """
        User can choose to save their work when closing the window.

        GIVEN: A user wants to close the component editor
        WHEN: They choose to save their changes in the confirmation dialog
        THEN: The save operation should be executed before closing
        """
        # Arrange: Mock user choosing to save and a successful save operation
        editor_for_closing_tests.save_component_json = MagicMock(return_value=False)
        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.messagebox.askyesnocancel",
                return_value=True,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.sys_exit") as mock_exit,
        ):
            # Act: Trigger window closing
            editor_for_closing_tests.on_closing()

        # Assert: Save should be called and application should exit
        editor_for_closing_tests.save_component_json.assert_called_once()
        mock_exit.assert_called_once_with(0)

    def test_user_can_close_without_saving_when_prompted(self, editor_for_closing_tests: ComponentEditorWindowBase) -> None:
        """
        User can choose to close without saving when prompted.

        GIVEN: A user wants to close the component editor
        WHEN: They choose not to save their changes in the confirmation dialog
        THEN: The window should close without saving
        """
        # Arrange: Mock user choosing not to save
        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.messagebox.askyesnocancel",
                return_value=False,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.sys_exit") as mock_exit,
        ):
            # Act: Trigger window closing
            editor_for_closing_tests.on_closing()

        # Assert: Save should not be called but window should close
        editor_for_closing_tests.save_component_json.assert_not_called()
        editor_for_closing_tests.root.destroy.assert_called_once()
        mock_exit.assert_called_once_with(0)

    def test_user_can_cancel_closing_operation(self, editor_for_closing_tests: ComponentEditorWindowBase) -> None:
        """
        User can cancel the closing operation and continue editing.

        GIVEN: A user accidentally triggers window closing
        WHEN: They choose to cancel in the confirmation dialog
        THEN: The window should remain open and no actions should be taken
        """
        # Arrange: Mock user canceling the operation
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.messagebox.askyesnocancel",
            return_value=None,
        ):
            # Act: Trigger window closing
            editor_for_closing_tests.on_closing()

        # Assert: Nothing should happen
        editor_for_closing_tests.save_component_json.assert_not_called()
        editor_for_closing_tests.root.destroy.assert_not_called()


class TestWidgetCreationWorkflows:
    """Test user workflows for widget creation and management."""

    @pytest.fixture
    def editor_with_realistic_data(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor with realistic component data."""
        data_model = MagicMock(spec=ComponentDataModel)
        data_model.get_all_components.return_value = REALISTIC_VEHICLE_DATA

        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

        # Mock widget creation methods to avoid UI dependencies
        editor._add_widget = MagicMock()
        editor.scroll_frame = MagicMock()
        editor.scroll_frame.view_port = MagicMock()

        return editor

    def test_user_sees_all_components_populated_in_interface(
        self, editor_with_realistic_data: ComponentEditorWindowBase
    ) -> None:
        """
        User sees all their vehicle components populated in the interface.

        GIVEN: A user has multiple vehicle components configured
        WHEN: The interface populates the component widgets
        THEN: Each component should be processed and displayed
        """
        # Act: Populate the interface frames
        editor_with_realistic_data.populate_frames()

        # Assert: All components should be processed
        call_count = editor_with_realistic_data._add_widget.call_count
        expected_components = len(REALISTIC_VEHICLE_DATA)
        assert call_count == expected_components

    def test_user_can_interact_with_different_widget_types(
        self, editor_with_realistic_data: ComponentEditorWindowBase
    ) -> None:
        """
        User can interact with different types of component widgets.

        GIVEN: A user has various types of component data (dictionaries and leaf values)
        WHEN: They interact with the widget creation system
        THEN: The system should handle both dict and non-dict values appropriately
        """
        # Arrange: Test both dictionary and leaf value scenarios
        test_parent = MagicMock()

        # Act: Test dict value (should call _add_non_leaf_widget logic)
        editor_with_realistic_data.add_widget(test_parent, "TestComponent", {"nested": "data"}, [])

        # Act: Test leaf value (should call _add_leaf_widget logic)
        editor_with_realistic_data.add_widget(test_parent, "TestValue", "simple_value", [])

        # Assert: Widget addition should be called for both cases
        assert editor_with_realistic_data._add_widget.call_count == 2


class TestComplexityComboboxWorkflows:
    """Test user workflows for GUI complexity management."""

    @pytest.fixture
    def editor_for_complexity_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for complexity testing."""
        editor = ComponentEditorWindowBase.create_for_testing(version="1.0.0", local_filesystem=mock_filesystem)

        # Mock the complexity variable and UI refresh methods
        editor.complexity_var = MagicMock()
        editor.complexity_var.get.return_value = "simple"
        editor.scroll_frame = MagicMock()
        editor.scroll_frame.view_port = MagicMock()
        editor.populate_frames = MagicMock()

        return editor

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ProgramSettings")
    def test_user_can_change_gui_complexity_level(
        self, mock_settings: MagicMock, editor_for_complexity_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User can change the GUI complexity level to match their expertise.

        GIVEN: A user wants to adjust the interface complexity
        WHEN: They change the complexity setting
        THEN: The setting should be saved and interface should refresh
        """
        # Arrange: Set up complexity change
        editor_for_complexity_tests.complexity_var.get.return_value = "normal"

        # Act: Trigger complexity change
        editor_for_complexity_tests._on_complexity_changed()

        # Assert: Setting should be saved and display refreshed
        mock_settings.set_setting.assert_called_once_with("gui_complexity", "normal")
        editor_for_complexity_tests.populate_frames.assert_called_once()

    def test_user_sees_interface_refresh_after_complexity_change(
        self, editor_for_complexity_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees the interface refresh when complexity level changes.

        GIVEN: A user has changed the GUI complexity level
        WHEN: The interface processes the complexity change
        THEN: The component display should be refreshed with new settings
        """
        # Act: Trigger interface refresh
        editor_for_complexity_tests._refresh_component_display()

        # Assert: Display should be refreshed
        editor_for_complexity_tests.populate_frames.assert_called_once()
        editor_for_complexity_tests.scroll_frame.view_port.update_idletasks.assert_called_once()


class TestModuleConstantsAndTypes:
    """Test module-level constants and type definitions."""

    def test_window_dimensions_are_reasonable_for_user_interface(self) -> None:
        """
        Window dimensions provide reasonable space for user interaction.

        GIVEN: A user needs adequate space to work with component configuration
        WHEN: The application defines window dimensions
        THEN: The dimensions should be practical for desktop use
        """
        # Assert: Window dimensions should be reasonable
        assert WINDOW_WIDTH_PIX > 600  # Minimum reasonable width
        assert VEHICLE_IMAGE_WIDTH_PIX > 50  # Visible image size

    def test_entry_widget_type_alias_supports_expected_widget_types(self) -> None:
        """
        Entry widget type alias includes all expected UI widget types.

        GIVEN: A user interacts with different types of input widgets
        WHEN: The system defines widget types
        THEN: The type alias should include common tkinter input widgets
        """
        # Assert: Type alias should include expected types
        origin = get_origin(EntryWidget)
        args = get_args(EntryWidget)

        assert origin is Union
        assert len(args) >= 2  # Should include at least Entry and Combobox

    def test_argparse_arguments_include_component_editor_options(self) -> None:
        """
        Argument parser includes options relevant to component editor functionality.

        GIVEN: A user needs to configure component editor behavior
        WHEN: Command line arguments are defined
        THEN: Component editor specific options should be available
        """
        # Arrange: Create test parser
        parser = ArgumentParser()

        # Act: Add component editor arguments
        ComponentEditorWindowBase.add_argparse_arguments(parser)

        # Assert: Component editor arguments should be added
        # This tests the method exists and can be called
        assert hasattr(ComponentEditorWindowBase, "add_argparse_arguments")


class TestCreateForTestingFactory:
    """Test the factory method for creating test instances."""

    def test_factory_creates_instance_with_minimal_dependencies(self) -> None:
        """
        Factory method creates usable instances with minimal dependencies.

        GIVEN: A developer needs to create test instances
        WHEN: They use the create_for_testing factory method
        THEN: A properly configured instance should be created
        """
        # Act: Create instance using factory
        editor = ComponentEditorWindowBase.create_for_testing()

        # Assert: Instance should be created with expected attributes
        assert isinstance(editor, ComponentEditorWindowBase)
        assert hasattr(editor, "data_model")
        assert hasattr(editor, "local_filesystem")

    def test_factory_accepts_custom_parameters_for_flexible_testing(self) -> None:
        """
        Factory method accepts custom parameters for flexible test scenarios.

        GIVEN: A developer needs specific test configurations
        WHEN: They provide custom parameters to the factory
        THEN: The instance should use the provided parameters
        """
        # Arrange: Create custom test dependencies
        custom_filesystem = MagicMock(spec=LocalFilesystem)
        custom_data_model = MagicMock(spec=ComponentDataModel)
        custom_version = "test_version"

        # Act: Create instance with custom parameters
        editor = ComponentEditorWindowBase.create_for_testing(
            version=custom_version, local_filesystem=custom_filesystem, data_model=custom_data_model
        )

        # Assert: Custom parameters should be used
        assert editor.version == custom_version
        assert editor.local_filesystem == custom_filesystem
        assert editor.data_model == custom_data_model


class TestErrorHandlingScenarios:
    """Test error handling in various user scenarios."""

    @pytest.fixture
    def editor_for_error_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for error scenario testing."""
        data_model = MagicMock(spec=ComponentDataModel)
        return ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

    def test_user_receives_appropriate_feedback_for_filesystem_errors(
        self, editor_for_error_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User receives appropriate feedback when filesystem operations fail.

        GIVEN: A user attempts to save but encounters filesystem errors
        WHEN: The save operation fails
        THEN: Clear error information should be provided
        """
        # Arrange: Configure filesystem error
        editor_for_error_tests.data_model.save_to_filesystem.return_value = (True, "Permission denied")

        # Act: Attempt save operation with error display mocked
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message") as mock_error:
            editor_for_error_tests.save_component_json()

        # Assert: Error handling should be triggered
        mock_error.assert_called_once()

    def test_system_gracefully_handles_missing_widget_references(
        self, editor_for_error_tests: ComponentEditorWindowBase
    ) -> None:
        """
        System gracefully handles references to non-existent widgets.

        GIVEN: A user's system references a widget that doesn't exist
        WHEN: An operation attempts to access the missing widget
        THEN: The operation should continue without errors
        """
        # Arrange: Set up scenario with missing widget
        path = ("NonExistent", "Widget")
        value = "test_value"

        # Act: Attempt to update non-existent widget
        editor_for_error_tests.set_component_value_and_update_ui(path, value)

        # Assert: Data model should still be updated (no exception should occur)
        editor_for_error_tests.data_model.set_component_value.assert_called_once_with(path, value)


class TestUIInitializationWorkflows:
    """Test user workflows for UI initialization and setup."""

    @pytest.fixture
    def editor_for_ui_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for UI testing."""
        data_model = MagicMock(spec=ComponentDataModel)
        data_model.is_valid_component_data.return_value = True
        data_model.has_components.return_value = True

        # Create editor but mock UI initialization to test individual methods
        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

        # Add mock UI elements that would be created during initialization
        editor.main_frame = MagicMock()
        editor.scroll_frame = MagicMock()
        editor.save_button = MagicMock()
        editor.template_manager = MagicMock()
        editor.complexity_var = MagicMock()

        return editor

    def test_user_sees_proper_window_setup_with_title_and_geometry(
        self, editor_for_ui_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees properly configured window with appropriate title and size.

        GIVEN: A user opens the component editor
        WHEN: The window is set up
        THEN: The window should have correct title and geometry settings
        """
        # Act: Setup window
        editor_for_ui_tests._setup_window()

        # Assert: Window should be configured properly
        editor_for_ui_tests.root.title.assert_called_once()
        editor_for_ui_tests.root.geometry.assert_called_once_with(f"{WINDOW_WIDTH_PIX}x600")
        editor_for_ui_tests.root.protocol.assert_called_once_with("WM_DELETE_WINDOW", editor_for_ui_tests.on_closing)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Style")
    def test_user_benefits_from_consistent_ui_styling(
        self, mock_style_class: MagicMock, editor_for_ui_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User benefits from consistent UI styling across all components.

        GIVEN: A user interacts with various UI elements
        WHEN: The styles are configured
        THEN: All style configurations should be applied for consistency
        """
        # Arrange: Mock the style instance
        mock_style = MagicMock()
        mock_style_class.return_value = mock_style
        # Provide a sensible default DPI scaling for tests so style font sizes are predictable
        # 9pt base with 1.5 scaling -> int(9 * 1.5) == 13, matching test expectations
        editor_for_ui_tests.dpi_scaling_factor = 1.5

        # Act: Setup styles
        editor_for_ui_tests._setup_styles()

        # Assert: All necessary styles should be configured
        assert mock_style.configure.call_count >= 7  # At least 7 style configurations
        mock_style.configure.assert_any_call("bigger.TLabel", font=("TkDefaultFont", -18))
        mock_style.configure.assert_any_call("comb_input_invalid.TCombobox", fieldbackground="red")
        mock_style.configure.assert_any_call("comb_input_valid.TCombobox", fieldbackground="white")

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Frame")
    def test_user_sees_introduction_frame_with_explanations(
        self, mock_frame_class: MagicMock, editor_for_ui_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees introduction frame with helpful explanations.

        GIVEN: A user opens the component editor for the first time
        WHEN: The introduction frame is created
        THEN: Explanatory content should be displayed to guide the user
        """
        # Arrange: Mock frame creation
        mock_intro_frame = MagicMock()
        mock_frame_class.return_value = mock_intro_frame

        # Mock the methods that would be called
        editor_for_ui_tests._add_explanation_text = MagicMock()
        editor_for_ui_tests._add_vehicle_image = MagicMock()

        # Act: Create introduction frame
        editor_for_ui_tests._create_intro_frame()

        # Assert: Frame should be created and content added
        mock_frame_class.assert_called_once_with(editor_for_ui_tests.main_frame)
        mock_intro_frame.pack.assert_called_once()
        editor_for_ui_tests._add_explanation_text.assert_called_once_with(mock_intro_frame)
        editor_for_ui_tests._add_vehicle_image.assert_called_once_with(mock_intro_frame)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ScrollFrame")
    def test_user_can_scroll_through_large_component_lists(
        self, mock_scroll_frame_class: MagicMock, editor_for_ui_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User can scroll through large lists of vehicle components.

        GIVEN: A user has many vehicle components to configure
        WHEN: The scrollable frame is set up
        THEN: The user should be able to scroll through all components
        """
        # Arrange: Mock ScrollFrame creation
        mock_scroll_frame = MagicMock()
        mock_scroll_frame_class.return_value = mock_scroll_frame

        # Act: Create scroll frame
        editor_for_ui_tests._create_scroll_frame()

        # Assert: Scroll frame should be created and configured
        mock_scroll_frame_class.assert_called_once_with(editor_for_ui_tests.main_frame)
        mock_scroll_frame.pack.assert_called_once_with(side="top", fill="both", expand=True)
        assert editor_for_ui_tests.scroll_frame == mock_scroll_frame

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Button")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_tooltip")
    def test_user_sees_save_button_with_helpful_tooltip(
        self,
        mock_tooltip: MagicMock,
        mock_frame_class: MagicMock,
        mock_button_class: MagicMock,
        editor_for_ui_tests: ComponentEditorWindowBase,
    ) -> None:
        """
        User sees a prominent save button with helpful tooltip information.

        GIVEN: A user wants to save their component configuration
        WHEN: The save frame is created
        THEN: A save button with tooltip should be available
        """
        # Arrange: Mock UI element creation
        mock_save_frame = MagicMock()
        mock_save_button = MagicMock()
        mock_frame_class.return_value = mock_save_frame
        mock_button_class.return_value = mock_save_button

        # Act: Create save frame
        editor_for_ui_tests._create_save_frame()

        # Assert: Save frame and button should be created with tooltip
        mock_frame_class.assert_called_once_with(editor_for_ui_tests.main_frame)
        mock_button_class.assert_called_once()
        mock_save_frame.pack.assert_called_once()
        mock_save_button.pack.assert_called_once_with(pady=7)
        mock_tooltip.assert_called_once()
        assert editor_for_ui_tests.save_button == mock_save_button

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ComponentTemplateManager")
    def test_user_can_access_template_management_functionality(
        self, mock_template_manager_class: MagicMock, editor_for_ui_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User can access template management functionality for reusable configurations.

        GIVEN: A user wants to save or load component templates
        WHEN: The template manager is set up
        THEN: Template management functionality should be available
        """
        # Arrange: Mock ComponentTemplateManager creation
        mock_template_manager = MagicMock()
        mock_template_manager_class.return_value = mock_template_manager

        # Act: Setup template manager
        editor_for_ui_tests._setup_template_manager()

        # Assert: Template manager should be created with proper callbacks
        mock_template_manager_class.assert_called_once()
        assert editor_for_ui_tests.template_manager == mock_template_manager

    def test_user_sees_data_validation_before_ui_setup(self, mock_filesystem: MagicMock) -> None:
        """
        User receives feedback when data validation fails before UI setup.

        GIVEN: A user has invalid component data
        WHEN: The editor checks data validity
        THEN: The system should prevent UI initialization and schedule window destruction
        """
        # Arrange: Create data model that reports invalid data
        invalid_data_model = MagicMock(spec=ComponentDataModel)
        invalid_data_model.is_valid_component_data.return_value = False
        invalid_data_model.has_components.return_value = True

        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=invalid_data_model
        )

        # Act: Check data validity
        result = editor._check_data()

        # Assert: Should return False and schedule window destruction
        assert result is False
        editor.root.after.assert_called_once_with(100, editor.root.destroy)

    def test_user_benefits_from_proper_data_model_initialization(self, mock_filesystem: MagicMock) -> None:
        """
        User benefits from proper data model initialization with post-init processing.

        GIVEN: A user has valid component data
        WHEN: The editor finalizes initialization
        THEN: The data model should be properly initialized with documentation
        """
        # Arrange: Create editor with valid data
        data_model = MagicMock(spec=ComponentDataModel)
        data_model.is_valid_component_data.return_value = True
        data_model.has_components.return_value = True

        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

        # Act: Finalize initialization
        editor._finalize_initialization()

        # Assert: Data model should be post-initialized
        data_model.post_init.assert_called_once_with(mock_filesystem.doc_dict)


class TestVehicleImageDisplayWorkflows:
    """Test user workflows for vehicle image display."""

    @pytest.fixture
    def editor_for_image_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for image testing."""
        editor = ComponentEditorWindowBase.create_for_testing(version="1.0.0", local_filesystem=mock_filesystem)
        editor.put_image_in_label = MagicMock(return_value=MagicMock())
        return editor

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_tooltip")
    def test_user_sees_vehicle_image_when_available(
        self, mock_tooltip: MagicMock, editor_for_image_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees their vehicle image when an image file is available.

        GIVEN: A user has added a vehicle.jpg image to their vehicle directory
        WHEN: The vehicle image section is displayed
        THEN: The image should be shown with helpful tooltip
        """
        # Arrange: Configure filesystem to report image exists
        editor_for_image_tests.local_filesystem.vehicle_image_exists.return_value = True
        editor_for_image_tests.local_filesystem.vehicle_image_filepath.return_value = "vehicle.jpg"

        mock_parent = MagicMock()
        mock_image_label = MagicMock()
        editor_for_image_tests.put_image_in_label.return_value = mock_image_label

        # Act: Add vehicle image
        editor_for_image_tests._add_vehicle_image(mock_parent)

        # Assert: Image should be displayed with tooltip
        editor_for_image_tests.put_image_in_label.assert_called_once_with(mock_parent, "vehicle.jpg", VEHICLE_IMAGE_HEIGHT_PIX)
        mock_image_label.pack.assert_called_once_with(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
        mock_tooltip.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Label")
    def test_user_sees_helpful_message_when_no_image_available(
        self, mock_label_class: MagicMock, editor_for_image_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees helpful message when no vehicle image is available.

        GIVEN: A user has not added a vehicle image file
        WHEN: The vehicle image section is displayed
        THEN: A helpful message should guide them to add an image
        """
        # Arrange: Configure filesystem to report no image exists
        editor_for_image_tests.local_filesystem.vehicle_image_exists.return_value = False

        mock_parent = MagicMock()
        mock_image_label = MagicMock()
        mock_label_class.return_value = mock_image_label

        # Act: Add vehicle image placeholder
        editor_for_image_tests._add_vehicle_image(mock_parent)

        # Assert: Helpful message should be displayed
        mock_label_class.assert_called_once()
        mock_image_label.pack.assert_called_once_with(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))


class TestWidgetDisplayLogicWorkflows:
    """Test user workflows for widget display logic."""

    @pytest.fixture
    def editor_for_widget_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for widget display testing."""
        data_model = MagicMock(spec=ComponentDataModel)
        data_model.should_display_in_simple_mode.return_value = True
        data_model.should_display_leaf_in_simple_mode.return_value = True
        data_model.prepare_non_leaf_widget_config.return_value = {
            "key": "TestComponent",
            "is_optional": False,
            "is_toplevel": True,
            "description": "Test description",
        }
        data_model.prepare_leaf_widget_config.return_value = {
            "key": "TestField",
            "value": "test_value",
            "path": ("TestComponent", "TestField"),
            "is_optional": False,
            "description": "Test field description",
        }

        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

        # Mock UI creation methods
        editor._create_non_leaf_widget_ui = MagicMock(return_value=MagicMock())
        editor._create_leaf_widget_ui = MagicMock()
        editor._add_template_controls = MagicMock()
        editor.add_entry_or_combobox = MagicMock(return_value=MagicMock())
        editor.complexity_var = MagicMock()
        editor.complexity_var.get.return_value = "normal"

        return editor

    def test_user_sees_non_leaf_widgets_for_component_grouping(
        self, editor_for_widget_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees grouped component widgets for better organization.

        GIVEN: A user has components with nested properties
        WHEN: Non-leaf widgets are created
        THEN: Grouped widgets should be properly configured and displayed
        """
        # Arrange: Test data for non-leaf widget
        mock_parent = MagicMock()
        test_component = {"nested_prop": "value"}
        path = []

        # Act: Add non-leaf widget
        editor_for_widget_tests._add_non_leaf_widget(mock_parent, "TestComponent", test_component, path)

        # Assert: Non-leaf widget should be created with proper configuration
        editor_for_widget_tests.data_model.prepare_non_leaf_widget_config.assert_called_once_with(
            "TestComponent", test_component, path
        )
        editor_for_widget_tests._create_non_leaf_widget_ui.assert_called_once()

    def test_user_sees_leaf_widgets_for_data_input(self, editor_for_widget_tests: ComponentEditorWindowBase) -> None:
        """
        User sees input widgets for entering component data.

        GIVEN: A user needs to enter specific component values
        WHEN: Leaf widgets are created
        THEN: Input widgets should be properly configured for data entry
        """
        # Arrange: Test data for leaf widget
        mock_parent = MagicMock()
        test_value = "test_value"
        path = ["TestComponent"]

        # Act: Add leaf widget
        editor_for_widget_tests._add_leaf_widget(mock_parent, "TestField", test_value, path)

        # Assert: Leaf widget should be created with proper configuration
        editor_for_widget_tests.data_model.prepare_leaf_widget_config.assert_called_once_with("TestField", test_value, path)
        editor_for_widget_tests._create_leaf_widget_ui.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.LabelFrame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_tooltip")
    def test_user_sees_properly_styled_component_frames(
        self, mock_tooltip: MagicMock, mock_labelframe_class: MagicMock, editor_for_widget_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees properly styled frames for component organization.

        GIVEN: A user views component configuration sections
        WHEN: Component frames are created
        THEN: Frames should be properly styled and positioned
        """
        # Arrange: Mock frame creation
        mock_parent = MagicMock()
        mock_frame = MagicMock()
        mock_labelframe_class.return_value = mock_frame

        config = {"key": "TestComponent", "is_optional": False, "is_toplevel": True, "description": "Test description"}

        # Act: Create non-leaf widget UI (call the real method to test actual UI creation)
        # Remove the mock to test the actual method behavior
        editor_for_widget_tests._create_non_leaf_widget_ui = ComponentEditorWindowBase._create_non_leaf_widget_ui.__get__(  # pylint: disable=no-value-for-parameter
            editor_for_widget_tests
        )
        result = editor_for_widget_tests._create_non_leaf_widget_ui(mock_parent, config)

        # Assert: Frame should be created and configured properly
        mock_labelframe_class.assert_called_once()
        mock_frame.pack.assert_called_once()
        mock_tooltip.assert_called_once_with(mock_frame, "Test description", position_below=False)
        assert result == mock_frame

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Label")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_tooltip")
    def test_user_sees_properly_configured_input_fields(
        self,
        mock_tooltip: MagicMock,
        mock_label_class: MagicMock,
        mock_frame_class: MagicMock,
        editor_for_widget_tests: ComponentEditorWindowBase,
    ) -> None:
        """
        User sees properly configured input fields for data entry.

        GIVEN: A user needs to enter component data
        WHEN: Input field widgets are created
        THEN: Fields should be properly labeled and configured
        """
        # Arrange: Mock UI element creation
        mock_parent = MagicMock()
        mock_entry_frame = MagicMock()
        mock_label = MagicMock()
        mock_entry = MagicMock()

        mock_frame_class.return_value = mock_entry_frame
        mock_label_class.return_value = mock_label
        editor_for_widget_tests.add_entry_or_combobox.return_value = mock_entry

        config = {
            "key": "TestField",
            "value": "test_value",
            "path": ("TestComponent", "TestField"),
            "is_optional": False,
            "description": "Test field description",
        }

        # Act: Create leaf widget UI (call the real method to test actual UI creation)
        # Remove the mock to test the actual method behavior
        editor_for_widget_tests._create_leaf_widget_ui = ComponentEditorWindowBase._create_leaf_widget_ui.__get__(  # pylint: disable=no-value-for-parameter, assignment-from-no-return
            editor_for_widget_tests
        )
        editor_for_widget_tests._create_leaf_widget_ui(mock_parent, config)

        # Assert: Input field should be created and configured
        mock_frame_class.assert_called_once_with(mock_parent)
        mock_label_class.assert_called_once()
        mock_entry_frame.pack.assert_called_once()
        mock_label.pack.assert_called_once_with(side=tk.LEFT)
        mock_entry.pack.assert_called_once()
        mock_tooltip.assert_called()
        assert editor_for_widget_tests.entry_widgets[("TestComponent", "TestField")] == mock_entry


class TestValidationWorkflows:
    """Test user workflows for data validation."""

    @pytest.fixture
    def editor_for_validation_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for validation testing."""
        editor = ComponentEditorWindowBase.create_for_testing(version="1.0.0", local_filesystem=mock_filesystem)
        # Mock validation method since it's abstract in base class
        editor.validate_data_and_highlight_errors_in_red = MagicMock(return_value="")
        editor._confirm_component_properties = MagicMock(return_value=True)
        return editor

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message")
    def test_user_receives_validation_errors_before_save(
        self, mock_error: MagicMock, editor_for_validation_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User receives clear validation errors before saving invalid data.

        GIVEN: A user has entered invalid component data
        WHEN: They attempt to save the configuration
        THEN: Validation errors should be displayed without saving
        """
        # Arrange: Configure validation to return error
        error_message = "Required field is missing"
        editor_for_validation_tests.validate_data_and_highlight_errors_in_red.return_value = error_message

        # Act: Attempt to validate and save
        editor_for_validation_tests.on_save_pressed()

        # Assert: Error should be displayed and save should not proceed
        mock_error.assert_called_once_with(_("Error"), error_message)
        editor_for_validation_tests._confirm_component_properties.assert_not_called()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.messagebox.askyesno")
    def test_user_must_confirm_component_properties_before_save(
        self, mock_confirm: MagicMock, editor_for_validation_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User must confirm that component properties are correct before saving.

        GIVEN: A user has valid component data
        WHEN: They attempt to save the configuration
        THEN: They should be asked to confirm all properties are correct
        """
        # Arrange: Configure successful validation but user cancels confirmation
        mock_confirm.return_value = False
        editor_for_validation_tests.save_component_json = MagicMock()

        # Remove the mock to test the actual method behavior
        editor_for_validation_tests._confirm_component_properties = (
            ComponentEditorWindowBase._confirm_component_properties.__get__(editor_for_validation_tests)  # pylint: disable=no-value-for-parameter
        )

        # Act: Attempt to validate and save
        editor_for_validation_tests.on_save_pressed()

        # Assert: Confirmation should be requested but save should not proceed
        mock_confirm.assert_called_once()
        editor_for_validation_tests.save_component_json.assert_not_called()


class TestMainScriptExecutionWorkflows:
    """Test user workflows for main script execution."""

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ComponentEditorWindowBase")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.LocalFilesystem")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.logging_basicConfig")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.argument_parser")
    def test_user_can_execute_main_script_with_proper_initialization(
        self, mock_parser: MagicMock, mock_logging: MagicMock, mock_filesystem_class: MagicMock, mock_editor_class: MagicMock
    ) -> None:
        """
        User can execute the main script with proper initialization.

        GIVEN: A user runs the component editor as a standalone script
        WHEN: The main execution block runs
        THEN: All components should be properly initialized and the GUI should start
        """
        # Arrange: Mock all dependencies
        mock_args = MagicMock()
        mock_args.loglevel = "INFO"
        mock_args.vehicle_dir = "test_dir"
        mock_args.vehicle_type = "ArduCopter"
        mock_args.allow_editing_template_files = False
        mock_args.save_component_to_system_templates = False
        mock_args.skip_component_editor = False

        mock_parser.return_value = mock_args
        mock_filesystem = MagicMock()
        mock_filesystem_class.return_value = mock_filesystem
        mock_editor = MagicMock()
        mock_editor.root = MagicMock()
        mock_editor_class.return_value = mock_editor

        # Act: Execute the main script logic by importing the module
        # This simulates running the script as __main__
        import ardupilot_methodic_configurator.frontend_tkinter_component_editor_base as module  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

        # We can't directly test the if __name__ == "__main__" block,
        # but we can test that the components exist and can be called
        assert hasattr(module, "argument_parser")
        assert hasattr(module, "ComponentEditorWindowBase")
        assert hasattr(module, "LocalFilesystem")


class TestComplexityControlWorkflows:
    """Test user workflows for complexity control and UI display filtering."""

    @pytest.fixture
    def editor_for_complexity_display_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for complexity display testing."""
        data_model = MagicMock(spec=ComponentDataModel)
        data_model.should_display_in_simple_mode.return_value = False  # Test filtering behavior
        data_model.should_display_leaf_in_simple_mode.return_value = False  # Test filtering behavior

        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

        editor.complexity_var = MagicMock()
        editor.complexity_var.get.return_value = "simple"

        return editor

    def test_user_in_simple_mode_sees_only_essential_components(
        self, editor_for_complexity_display_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User in simple mode sees only essential components for easier configuration.

        GIVEN: A user has selected simple GUI complexity mode
        WHEN: Component widgets are being created
        THEN: Only essential components should be displayed
        """
        # Arrange: Mock parent widget
        mock_parent = MagicMock()
        test_component = {"optional_prop": "value"}

        # Act: Attempt to add widget that should be filtered in simple mode
        editor_for_complexity_display_tests.add_widget(mock_parent, "OptionalComponent", test_component, [])

        # Assert: Data model should be consulted for display rules
        editor_for_complexity_display_tests.data_model.should_display_in_simple_mode.assert_called_once()

    def test_user_in_simple_mode_sees_only_essential_leaf_fields(
        self, editor_for_complexity_display_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User in simple mode sees only essential input fields.

        GIVEN: A user has selected simple GUI complexity mode
        WHEN: Leaf widgets (input fields) are being created
        THEN: Only essential fields should be displayed
        """
        # Arrange: Mock parent widget
        mock_parent = MagicMock()
        test_value = "optional_value"

        # Act: Attempt to add leaf widget that should be filtered in simple mode
        editor_for_complexity_display_tests.add_widget(mock_parent, "OptionalField", test_value, ["Component"])

        # Assert: Data model should be consulted for leaf display rules
        editor_for_complexity_display_tests.data_model.should_display_leaf_in_simple_mode.assert_called_once()


class TestTemplateControlsWorkflows:
    """Test user workflows for template controls in component frames."""

    @pytest.fixture
    def editor_for_template_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for template control testing."""
        data_model = MagicMock(spec=ComponentDataModel)
        data_model.get_all_components.return_value = {"TestComponent": {"prop": "value"}}

        editor = ComponentEditorWindowBase.create_for_testing(
            version="1.0.0", local_filesystem=mock_filesystem, data_model=data_model
        )

        editor.template_manager = MagicMock()
        editor.complexity_var = MagicMock()

        return editor

    def test_user_sees_template_controls_in_normal_mode_for_top_level_components(
        self, editor_for_template_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User sees template controls for top-level components in normal mode.

        GIVEN: A user is in normal complexity mode and viewing a top-level component
        WHEN: Template controls are added to component frames
        THEN: Template controls should be available for component management
        """
        # Arrange: Set normal complexity mode
        editor_for_template_tests.complexity_var.get.return_value = "normal"
        mock_parent_frame = MagicMock()
        component_name = "TestComponent"

        # Act: Add template controls
        editor_for_template_tests._add_template_controls(mock_parent_frame, component_name)

        # Assert: Template manager should add controls
        editor_for_template_tests.template_manager.add_template_controls.assert_called_once_with(
            mock_parent_frame, component_name
        )

    def test_user_does_not_see_template_controls_in_simple_mode(
        self, editor_for_template_tests: ComponentEditorWindowBase
    ) -> None:
        """
        User does not see template controls in simple mode for reduced complexity.

        GIVEN: A user is in simple complexity mode
        WHEN: Template controls would normally be added
        THEN: Template controls should be hidden to reduce interface complexity
        """
        # Arrange: Set simple complexity mode
        editor_for_template_tests.complexity_var.get.return_value = "simple"
        mock_parent_frame = MagicMock()
        component_name = "TestComponent"

        # Act: Attempt to add template controls
        editor_for_template_tests._add_template_controls(mock_parent_frame, component_name)

        # Assert: Template manager should not add controls
        editor_for_template_tests.template_manager.add_template_controls.assert_not_called()


class TestUsageInstructionsWorkflows:
    """Test user workflows for usage instructions display."""

    @pytest.fixture
    def editor_for_usage_tests(self, mock_filesystem: MagicMock) -> ComponentEditorWindowBase:
        """Fixture providing an editor configured for usage instruction testing."""
        editor = ComponentEditorWindowBase.create_for_testing(version="1.0.0", local_filesystem=mock_filesystem)

        # Mock UI elements needed for usage instructions
        editor.main_frame = MagicMock()

        return editor

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.UsagePopupWindow")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.BaseWindow")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.RichText")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ttk.Style")
    def test_user_sees_helpful_usage_instructions_on_first_use(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_style_class: MagicMock,
        mock_rich_text_class: MagicMock,
        mock_base_window_class: MagicMock,
        mock_usage_popup_class: MagicMock,
        editor_for_usage_tests: ComponentEditorWindowBase,
    ) -> None:
        """
        User sees helpful usage instructions when using the component editor for the first time.

        GIVEN: A user opens the component editor for the first time
        WHEN: The usage instructions are displayed
        THEN: Comprehensive instructions should guide the user through the interface
        """
        # Arrange: Mock all UI elements for instructions
        mock_usage_popup_window = MagicMock()
        mock_base_window_class.return_value = mock_usage_popup_window
        mock_rich_text = MagicMock()
        mock_rich_text_class.return_value = mock_rich_text
        mock_style = MagicMock()
        mock_style_class.return_value = mock_style

        # Create a mock Tk parent for testing
        mock_parent = MagicMock()

        # Act: Display usage instructions
        editor_for_usage_tests._display_component_editor_usage_instructions(mock_parent)

        # Assert: Usage instructions should be properly displayed
        mock_base_window_class.assert_called_once_with(mock_parent)
        mock_rich_text_class.assert_called_once()
        mock_usage_popup_class.display.assert_called_once()

        # Assert: Rich text should contain instructional content
        assert mock_rich_text.insert.call_count >= 5  # Multiple instruction steps should be inserted
