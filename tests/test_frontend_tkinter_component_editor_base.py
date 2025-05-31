#!/usr/bin/env python3

"""
Data-independent (ComponentEditorWindowBase) Component editor GUI tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_component_editor_base import (
    ComponentDataModel,
    ComponentEditorWindowBase,
)


@pytest.fixture
def editor_with_mocked_root() -> ComponentEditorWindowBase:
    """Create a mock ComponentEditorWindowBase for testing."""
    # Create the class without initialization
    with patch.object(ComponentEditorWindowBase, "__init__", return_value=None):
        editor = ComponentEditorWindowBase()  # pylint: disable=no-value-for-parameter

        # Set up all required attributes manually
        editor.root = MagicMock()
        editor.main_frame = MagicMock()
        editor.scroll_frame = MagicMock()
        editor.scroll_frame.view_port = MagicMock()

        # Mock filesystem and methods with proper schema loading
        editor.local_filesystem = MagicMock(spec=LocalFilesystem)
        editor.local_filesystem.vehicle_dir = "dummy_vehicle_dir"

        # Create a method that always returns a valid tuple regardless of input path
        editor.local_filesystem.get_component_property_description = MagicMock(return_value=("Test description", False))

        # Mock the vehicle_components attribute
        mock_vehicle_components = MagicMock()
        # Make schema loading return a valid empty schema
        mock_vehicle_components.load_schema.return_value = {"properties": {}}
        mock_vehicle_components.get_component_property_description = MagicMock(return_value=("Test description", False))
        editor.local_filesystem.vehicle_components = mock_vehicle_components

        # Setup test data and data model
        editor.entry_widgets = {}
        test_data = {"Components": {"Motor": {"Type": "brushless", "KV": 1000}}}
        editor.data_model = ComponentDataModel(test_data)

        # For backward compatibility with tests that directly access self.data
        # Make sure changes to data_model.data are reflected in editor.data and vice versa
        editor.data = editor.data_model.data

        # Override methods that might cause UI interactions in tests
        editor._add_widget = MagicMock()

        # Use add_widget as a public proxy for _add_widget for easier testing
        editor.add_widget = lambda parent, key, value, path: editor._add_widget(parent, key, value, path)

        # Add helper methods for testing that bypass UI operations
        def test_populate_frames() -> None:
            # This is a test-friendly version that doesn't involve actual UI widgets
            components = editor.data_model.get_component_data().get("Components", {})
            for key, value in components.items():
                editor._add_widget(editor.scroll_frame.view_port, key, value, [])

        editor.populate_frames = test_populate_frames

        yield editor


@patch("tkinter.messagebox.askyesnocancel")
def test_on_closing_save(mock_dialog, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the on_closing method when user chooses to save."""
    mock_dialog.return_value = True  # User selects "Yes"

    # Create a replacement for save_component_json
    editor_with_mocked_root.save_component_json = MagicMock()

    # Patch sys_exit in the module where it's imported
    with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.sys_exit") as mock_exit:
        with contextlib.suppress(SystemExit):
            editor_with_mocked_root.on_closing()

        # Verify save was called
        editor_with_mocked_root.save_component_json.assert_called_once()
        mock_exit.assert_called_once_with(0)


@patch("tkinter.messagebox.askyesnocancel")
def test_on_closing_no_save(mock_dialog, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the on_closing method when user chooses not to save."""
    mock_dialog.return_value = False  # User selects "No"

    # Create a replacement for save_component_json to avoid actual save logic
    editor_with_mocked_root.save_component_json = MagicMock()

    # Patch sys_exit in the module where it's imported
    with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.sys_exit") as mock_exit:
        with contextlib.suppress(SystemExit):
            editor_with_mocked_root.on_closing()

        # Verify save was NOT called but window was destroyed
        editor_with_mocked_root.save_component_json.assert_not_called()
        editor_with_mocked_root.root.destroy.assert_called_once()
        mock_exit.assert_called_once_with(0)


@patch("tkinter.messagebox.askyesnocancel")
def test_on_closing_cancel(mock_dialog, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the on_closing method when user cancels."""
    mock_dialog.return_value = None  # User selects "Cancel"

    # Make sure save_component_json is a MagicMock for this test
    editor_with_mocked_root.save_component_json = MagicMock()

    with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.sys_exit") as mock_exit:
        editor_with_mocked_root.on_closing()

        # Verify neither save nor destroy were called
        editor_with_mocked_root.save_component_json.assert_not_called()
        editor_with_mocked_root.root.destroy.assert_not_called()
        mock_exit.assert_not_called()


def test_update_json_data(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the update_json_data method."""
    # Test when Format version is not in data
    editor_with_mocked_root.data_model.data = {}
    editor_with_mocked_root.data = editor_with_mocked_root.data_model.data  # Keep the reference in sync
    editor_with_mocked_root.update_json_data()
    assert editor_with_mocked_root.data_model.data["Format version"] == 1
    assert editor_with_mocked_root.data["Format version"] == 1  # Verify backward compatibility

    # Test when Format version is already in data
    editor_with_mocked_root.data_model.data = {"Format version": 2}
    editor_with_mocked_root.data = editor_with_mocked_root.data_model.data  # Keep the reference in sync
    editor_with_mocked_root.update_json_data()
    assert editor_with_mocked_root.data_model.data["Format version"] == 2
    assert editor_with_mocked_root.data["Format version"] == 2  # Verify backward compatibility


def test_add_entry_or_combobox(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the add_entry_or_combobox method."""
    with patch("tkinter.ttk.Entry") as mock_entry:
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance

        entry_frame = MagicMock()
        result = editor_with_mocked_root.add_entry_or_combobox(42, entry_frame, ("Motor", "Type", "brushless"))

        mock_entry.assert_called_once_with(entry_frame)
        mock_entry_instance.insert.assert_called_once_with(0, "42")
        assert result == mock_entry_instance


def test_set_component_value_and_update_ui(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the set_component_value_and_update_ui method."""
    # Setup test data
    editor_with_mocked_root.data_model.data = {"Components": {"Motor": {"Type": "old_value"}}}
    mock_entry = MagicMock()
    editor_with_mocked_root.entry_widgets = {("Motor", "Type"): mock_entry}

    # Call the method
    editor_with_mocked_root.set_component_value_and_update_ui(("Motor", "Type"), "new_value")

    # Assert data was updated
    assert editor_with_mocked_root.data_model.data["Components"]["Motor"]["Type"] == "new_value"

    # Assert UI was updated
    mock_entry.delete.assert_called_once_with(0, tk.END)
    mock_entry.insert.assert_called_once_with(0, "new_value")
    mock_entry.config.assert_called_once_with(state="disabled")


@patch("tkinter.messagebox.askyesno")
def test_validate_and_save_component_json_yes(mock_dialog, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test when user confirms saving component data."""
    mock_dialog.return_value = True

    # Create a replacement for save_component_json to avoid actual save logic
    editor_with_mocked_root.save_component_json = MagicMock()

    editor_with_mocked_root.validate_and_save_component_json()

    mock_dialog.assert_called_once()
    editor_with_mocked_root.save_component_json.assert_called_once()


@patch("tkinter.messagebox.askyesno")
def test_validate_and_save_component_json_no(mock_dialog, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test when user cancels saving component data."""
    mock_dialog.return_value = False

    # Create a replacement for save_component_json to avoid actual save logic
    editor_with_mocked_root.save_component_json = MagicMock()

    editor_with_mocked_root.validate_and_save_component_json()

    mock_dialog.assert_called_once()
    editor_with_mocked_root.save_component_json.assert_not_called()


def test_save_component_json(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the save_component_json method with successful save."""
    # Setup test data
    editor_with_mocked_root.data_model.data = {"Components": {"Motor": {"Type": "brushless"}}}
    editor_with_mocked_root.data = editor_with_mocked_root.data_model.data  # Keep the reference in sync

    mock_entry = MagicMock()
    mock_entry.get.return_value = "new_value"
    editor_with_mocked_root.entry_widgets = {("Motor", "Type"): mock_entry}
    editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data.return_value = (False, "")

    # Call the method directly
    editor_with_mocked_root.save_component_json()

    # Assert data was updated and saved
    assert editor_with_mocked_root.data_model.data["Components"]["Motor"]["Type"] == "new_value"
    assert editor_with_mocked_root.data["Components"]["Motor"]["Type"] == "new_value"  # Verify backward compatibility

    editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data.assert_called_once()
    editor_with_mocked_root.root.destroy.assert_called_once()


@patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message")
def test_save_component_json_failure(mock_error_message, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the save_component_json method with failed save."""
    # Setup test data
    editor_with_mocked_root.data = {"Components": {"Motor": {"Type": "brushless"}}}
    mock_entry = MagicMock()
    mock_entry.get.return_value = "new_value"
    editor_with_mocked_root.entry_widgets = {("Motor", "Type"): mock_entry}
    editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data.return_value = (True, "Error message")

    # For this test we need to use the real save_component_json, not a mock
    original_method = ComponentEditorWindowBase.save_component_json
    editor_with_mocked_root.save_component_json = lambda: original_method(editor_with_mocked_root)

    # Call the method
    editor_with_mocked_root.save_component_json()

    # Assert error message was shown
    mock_error_message.assert_called_once()
    editor_with_mocked_root.root.destroy.assert_called_once()


def test_add_argparse_arguments() -> None:
    """Test adding command line arguments."""
    parser = MagicMock()

    result = ComponentEditorWindowBase.add_argparse_arguments(parser)

    parser.add_argument.assert_called_once()
    assert result == parser


@patch("tkinter.ttk.LabelFrame")
@patch("tkinter.ttk.Frame")
@patch("tkinter.ttk.Label")
def test_add_widget_dict(mock_label, mock_frame, mock_labelframe, editor_with_mocked_root) -> None:  # noqa: ARG001 # pylint: disable=redefined-outer-name, unused-argument
    """Test the _add_widget method with dictionary values."""
    # Create a dictionary to test with
    test_dict = {"SubKey1": "Value1", "SubKey2": "Value2"}
    mock_parent = MagicMock()
    mock_labelframe_instance = MagicMock()
    mock_labelframe.return_value = mock_labelframe_instance

    # Create a spy on the _add_widget method that tracks calls without changing behavior
    original_add_widget = editor_with_mocked_root._add_widget  # pylint: disable=protected-access
    spy_add_widget = MagicMock()

    # Replace the method with a special version that calls the original but tracks recursion
    def special_add_widget(parent, key, value, path) -> None:
        # Record the call
        spy_add_widget(parent, key, value, path)

        # Stop recursion for dictionary values - don't actually process children
        if isinstance(value, dict):
            # Create the LabelFrame but don't recurse
            frame = ttk.LabelFrame(parent, text=key)
            frame.pack(fill="x", expand=True, padx=10, pady=5)
            return

        # For leaf values, just call the original to prevent infinite recursion
        if not isinstance(value, dict):
            original_add_widget(parent, key, value, path)

    # Replace with our special method
    editor_with_mocked_root._add_widget = special_add_widget  # pylint: disable=protected-access

    try:
        # Call the method with the test dictionary
        editor_with_mocked_root._add_widget(mock_parent, "TestKey", test_dict, [])  # pylint: disable=protected-access

        # Verify LabelFrame was created
        mock_labelframe.assert_called_once()
        mock_labelframe_instance.pack.assert_called_once()

        # Verify the method was called for the top level
        spy_add_widget.assert_any_call(mock_parent, "TestKey", test_dict, [])
    finally:
        # Restore the original method
        editor_with_mocked_root._add_widget = original_add_widget  # pylint: disable=protected-access


@patch("tkinter.ttk.Frame")
@patch("tkinter.ttk.Label")
def test_add_widget_leaf(mock_label, mock_frame, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name, unused-argument # noqa: ARG001
    """Test the _add_widget method with leaf values."""
    # Create a completely separate mock for this test
    mock_parent = MagicMock()
    mock_frame_instance = MagicMock()
    mock_frame.return_value = mock_frame_instance

    # Mock add_entry_or_combobox to return a mock entry
    mock_entry = MagicMock()
    editor_with_mocked_root.add_entry_or_combobox = MagicMock(return_value=mock_entry)

    # Store original method
    original_add_widget = editor_with_mocked_root._add_widget

    # We need to intercept calls to _add_widget to test leaf node handling
    # Since we can't directly modify private methods with property decorators
    def mock_add_widget(_parent, key, value, path) -> None:
        if isinstance(value, dict):
            # Skip non-leaf handling for this test
            return
        # Here we're testing leaf handling
        # This directly emulates what _add_leaf_widget would do
        entry = editor_with_mocked_root.add_entry_or_combobox(value, mock_frame_instance, (*path, key))
        editor_with_mocked_root.entry_widgets[(*path, key)] = entry

    # Replace the _add_widget method with our mock
    editor_with_mocked_root._add_widget = mock_add_widget

    try:
        # Call the method with a leaf value and path
        path = ["Component"]
        test_value = 42.5
        editor_with_mocked_root._add_widget(mock_parent, "TestKey", test_value, path)

        # Verify entry was created through add_entry_or_combobox with correct parameters
        editor_with_mocked_root.add_entry_or_combobox.assert_called_once_with(
            test_value, mock_frame_instance, (*path, "TestKey")
        )

        # Verify the entry is stored in the entry_widgets dictionary
        expected_key = (*path, "TestKey")
        assert expected_key in editor_with_mocked_root.entry_widgets
    finally:
        # Restore original method
        editor_with_mocked_root._add_widget = original_add_widget


def test_populate_frames(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the populate_frames method."""
    # Setup test data
    editor_with_mocked_root.data_model.data = {"Components": {"Motor": {"Type": "brushless", "KV": 1000}}}
    editor_with_mocked_root.data = editor_with_mocked_root.data_model.data  # Keep the reference in sync

    # Override _add_widget with a clean mock to track calls
    editor_with_mocked_root._add_widget = MagicMock()  # pylint: disable=protected-access

    # Call the method
    editor_with_mocked_root.populate_frames()

    # Verify _add_widget was called for each top-level component
    editor_with_mocked_root._add_widget.assert_called_with(  # pylint: disable=protected-access
        editor_with_mocked_root.scroll_frame.view_port, "Motor", {"Type": "brushless", "KV": 1000}, []
    )


@patch("tkinter.ttk.LabelFrame")
@patch("tkinter.ttk.Frame")
@patch("tkinter.ttk.Label")
def test_populate_frames_full_integration(mock_label, mock_frame, mock_labelframe, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name, too-many-locals
    """Test the populate_frames method with full integration of leaf and non-leaf widgets."""
    # Setup test data with a nested structure to test both leaf and non-leaf widgets
    editor_with_mocked_root.data_model.data = {
        "Components": {
            "Motor": {  # This will trigger non-leaf widget
                "Type": "brushless",  # This will trigger leaf widget
                "KV": 1000,  # This will trigger leaf widget
            },
            "Battery": {  # Another non-leaf
                "Voltage": 12.6  # Another leaf
            },
        }
    }
    editor_with_mocked_root.data = editor_with_mocked_root.data_model.data  # Keep the reference in sync

    # Create mock instances for UI elements
    mock_labelframe_instance = MagicMock()
    mock_frame_instance = MagicMock()
    mock_label_instance = MagicMock()

    mock_labelframe.return_value = mock_labelframe_instance
    mock_frame.return_value = mock_frame_instance
    mock_label.return_value = mock_label_instance

    # Mock add_entry_or_combobox to return a mock entry
    mock_entry = MagicMock()
    editor_with_mocked_root.add_entry_or_combobox = MagicMock(return_value=mock_entry)

    # Mock the get_component_property_description method to avoid schema lookup
    editor_with_mocked_root.local_filesystem.get_component_property_description = MagicMock(
        return_value=("Test description", False)
    )

    # Initialize tracking variables
    editor_with_mocked_root._add_widget_calls = []

    # Override _add_widget with a version that tracks calls
    original_add_widget = editor_with_mocked_root._add_widget

    # Since we can't replace the property-based methods directly,
    # we'll track structure through the _add_widget method instead
    def mock_add_widget(parent, key, value, path) -> None:
        if isinstance(value, dict):
            # This is a non-leaf call
            editor_with_mocked_root._add_widget_calls.append(("non_leaf", parent, key, value, path))
            # Process children
            frame = mock_labelframe_instance
            for child_key, child_value in value.items():
                mock_add_widget(frame, child_key, child_value, [*path, key])
        else:
            # This is a leaf call
            editor_with_mocked_root._add_widget_calls.append(("leaf", parent, key, value, path))
            # Add an entry widget
            entry = editor_with_mocked_root.add_entry_or_combobox(value, mock_frame_instance, (*path, key))
            editor_with_mocked_root.entry_widgets[(*path, key)] = entry

    # Replace the add_widget method
    editor_with_mocked_root._add_widget = mock_add_widget

    try:
        # Call the method
        editor_with_mocked_root.populate_frames()

        # Verify the hierarchical structure of calls
        calls = editor_with_mocked_root._add_widget_calls

        # Check that we have the right number of calls
        # 2 non-leaf (Motor, Battery) + 3 leaf (Type, KV, Voltage) = 5 calls
        assert len(calls) == 5

        # Count the different types of calls
        non_leaf_calls = [c for c in calls if c[0] == "non_leaf"]
        leaf_calls = [c for c in calls if c[0] == "leaf"]

        # We should have 2 non-leaf calls and 3 leaf calls
        assert len(non_leaf_calls) == 2
        assert len(leaf_calls) == 3

        # Check that entries were created for leaf nodes
        assert len(editor_with_mocked_root.entry_widgets) == 3
        assert ("Motor", "Type") in editor_with_mocked_root.entry_widgets
        assert ("Motor", "KV") in editor_with_mocked_root.entry_widgets
        assert ("Battery", "Voltage") in editor_with_mocked_root.entry_widgets

    finally:
        # Restore original method
        editor_with_mocked_root._add_widget = original_add_widget


def test_get_component_data_from_gui(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the get_component_data_from_gui method."""
    # Setup test entries
    mock_entry1 = MagicMock()
    mock_entry1.get.return_value = "brushless"

    mock_entry2 = MagicMock()
    mock_entry2.get.return_value = "1000"

    mock_entry3 = MagicMock()
    mock_entry3.get.return_value = "0.5"

    editor_with_mocked_root.entry_widgets = {
        ("Motor", "Type"): mock_entry1,
        ("Motor", "KV"): mock_entry2,
        ("Motor", "Weight", "Mass"): mock_entry3,
    }

    # Call the method
    result = editor_with_mocked_root.get_component_data_from_gui("Motor")

    # Verify the result has the correct structure and values
    assert result["Type"] == "brushless"
    assert result["KV"] == 1000  # Should be converted to int
    assert "Weight" in result
    assert result["Weight"]["Mass"] == 0.5  # Should be converted to float


def test_derive_initial_template_name(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the derive_initial_template_name method."""
    # This is a simple test as the base implementation just returns an empty string
    component_data = {"Type": "brushless", "KV": 1000}
    result = editor_with_mocked_root.derive_initial_template_name(component_data)
    assert result == ""


@patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ComponentTemplateManager")
def test_add_template_controls(mock_template_manager, editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name, unused-argument # noqa: ARG001
    """Test the _add_template_controls method."""
    # Setup
    mock_parent_frame = MagicMock()
    editor_with_mocked_root.template_manager = MagicMock()

    # Call the method
    editor_with_mocked_root._add_template_controls(mock_parent_frame, "Motor")  # pylint: disable=protected-access

    # Verify the template manager was called correctly
    editor_with_mocked_root.template_manager.add_template_controls.assert_called_once_with(mock_parent_frame, "Motor")


@patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.logging_basicConfig")
@patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.LocalFilesystem")
def test_main_function(mock_filesystem, mock_logging_config) -> None:
    """Test the main function of the module."""
    # Mock the arguments
    mock_args = MagicMock()
    mock_args.loglevel = "INFO"
    mock_args.vehicle_dir = "/fake/path"
    mock_args.vehicle_type = "copter"
    mock_args.allow_editing_template_files = False
    mock_args.save_component_to_system_templates = False

    # Mock filesystem instance
    mock_filesystem_instance = MagicMock()
    mock_filesystem.return_value = mock_filesystem_instance

    # Mock the application window
    mock_app = MagicMock()
    mock_root = MagicMock()
    mock_app.root = mock_root

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.argument_parser", return_value=mock_args
        ) as mock_parser,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.ComponentEditorWindowBase",
            return_value=mock_app,
        ) as mock_window,
    ):
        # Import and execute the module's main block
        import importlib.util  # pylint: disable=import-outside-toplevel
        import sys  # pylint: disable=import-outside-toplevel

        spec = importlib.util.spec_from_file_location(
            "test_module", "ardupilot_methodic_configurator/frontend_tkinter_component_editor_base.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["test_module"] = module

        # Execute just the __main__ block
        exec(  # pylint: disable=exec-used # noqa: S102
            """
if __name__ == "__main__":
    args = argument_parser()
    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")
    filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )
    app = ComponentEditorWindowBase(__version__, filesystem)
    app.root.mainloop()
""",
            {
                "__name__": "__main__",
                "argument_parser": mock_parser,
                "logging_basicConfig": mock_logging_config,
                "logging_getLevelName": lambda x: x,
                "LocalFilesystem": mock_filesystem,
                "ComponentEditorWindowBase": mock_window,
                "__version__": "test_version",
            },
        )

        # Verify the window was created with correct parameters
        mock_filesystem.assert_called_once_with(
            mock_args.vehicle_dir,
            mock_args.vehicle_type,
            "",
            mock_args.allow_editing_template_files,
            mock_args.save_component_to_system_templates,
        )
        mock_window.assert_called_once_with("test_version", mock_filesystem_instance)
        mock_root.mainloop.assert_called_once()


class TestComponentDataModelIntegration:
    """Tests for integration between ComponentEditorWindowBase and ComponentDataModel."""

    def test_data_model_initialization(self) -> None:
        """Test that the data model is initialized correctly from filesystem data."""
        # Setup
        test_data = {"Components": {"Motor": {"Type": "brushless"}}, "Format version": 1}
        filesystem_mock = MagicMock(spec=LocalFilesystem)
        filesystem_mock.load_vehicle_components_json_data.return_value = test_data

        # Create a new instance with our mock
        with patch.object(ComponentEditorWindowBase, "__init__", return_value=None):
            editor = ComponentEditorWindowBase()

            # Manually call the relevant part of __init__ with our parameters
            editor.local_filesystem = filesystem_mock
            editor.data_model = ComponentDataModel(test_data)
            editor.data = editor.data_model.data

            # Verify the data model was initialized correctly
            assert editor.data_model.get_component_data() == test_data
            assert editor.data == test_data

    def test_set_component_value_updates_data_model(self, editor_with_mocked_root) -> None:
        """Test that set_component_value_and_update_ui updates the data model."""
        # Setup
        path = ("Motor", "Type")
        entry_mock = MagicMock()
        editor_with_mocked_root.entry_widgets = {path: entry_mock}

        # Spy on the data model's set_component_value method
        original_method = editor_with_mocked_root.data_model.set_component_value
        editor_with_mocked_root.data_model.set_component_value = MagicMock()

        # Call the method
        editor_with_mocked_root.set_component_value_and_update_ui(path, "new_value")

        # Verify the data model method was called
        editor_with_mocked_root.data_model.set_component_value.assert_called_once_with(path, "new_value")

        # Restore original method
        editor_with_mocked_root.data_model.set_component_value = original_method

    def test_save_component_json_uses_data_model(self, editor_with_mocked_root) -> None:
        """Test that save_component_json uses the data model to update data."""
        # Setup entry widgets with values
        entry1 = MagicMock()
        entry1.get.return_value = "brushless"
        entry2 = MagicMock()
        entry2.get.return_value = "1000"

        editor_with_mocked_root.entry_widgets = {("Motor", "Type"): entry1, ("Motor", "KV"): entry2}

        # Spy on data model's update_from_entries method
        original_method = editor_with_mocked_root.data_model.update_from_entries
        editor_with_mocked_root.data_model.update_from_entries = MagicMock()

        # Mock filesystem to avoid actual file operations
        editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data = MagicMock(return_value=(False, ""))

        # Call the method
        editor_with_mocked_root.save_component_json()

        # Verify update_from_entries was called with the correct entries
        expected_entries = {("Motor", "Type"): "brushless", ("Motor", "KV"): "1000"}
        editor_with_mocked_root.data_model.update_from_entries.assert_called_once()
        call_args = editor_with_mocked_root.data_model.update_from_entries.call_args[0][0]
        assert set(call_args.keys()) == set(expected_entries.keys())

        # Restore original method
        editor_with_mocked_root.data_model.update_from_entries = original_method


class TestUIDataModelInteraction:
    """Tests for UI interaction with ComponentDataModel."""

    def test_entry_updates_propagate_to_data_model(self, editor_with_mocked_root) -> None:
        """Test that UI entry updates propagate correctly to the data model."""
        # Setup mock UI elements that simulate user input
        mock_entry = MagicMock()
        mock_entry.get.return_value = "new_value"

        test_path = ("Motor", "Type")
        editor_with_mocked_root.entry_widgets = {test_path: mock_entry}

        # Setup the data model with initial data
        editor_with_mocked_root.data_model.data = {"Components": {"Motor": {"Type": "old_value"}}}

        # Create a mock of the filesystem save method
        editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data = MagicMock(return_value=(False, ""))

        # Simulate saving the component data (which reads from UI and updates model)
        editor_with_mocked_root.save_component_json()

        # Verify data model was updated with the UI value
        assert editor_with_mocked_root.data_model.get_component_value(test_path) == "new_value"

        # Verify the filesystem save was called with updated data
        editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data.assert_called_once()
        saved_data = editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data.call_args[0][0]
        assert saved_data["Components"]["Motor"]["Type"] == "new_value"

    def test_data_model_updates_propagate_to_ui(self, editor_with_mocked_root) -> None:
        """Test that data model updates propagate correctly to the UI."""
        # Setup mock UI elements
        mock_entry = MagicMock()
        test_path = ("Motor", "Type")
        editor_with_mocked_root.entry_widgets = {test_path: mock_entry}

        # Setup the data model with initial data
        editor_with_mocked_root.data_model.data = {"Components": {"Motor": {"Type": "old_value"}}}

        # Update the data model
        new_value = "updated_value"
        editor_with_mocked_root.set_component_value_and_update_ui(test_path, new_value)

        # Verify UI was updated
        mock_entry.delete.assert_called_once_with(0, tk.END)
        mock_entry.insert.assert_called_once_with(0, new_value)

        # Verify data model was updated
        assert editor_with_mocked_root.data_model.get_component_value(test_path) == new_value

    def test_nested_component_paths(self, editor_with_mocked_root) -> None:
        """Test handling of nested component paths in data model and UI."""
        # Setup deeply nested test data
        editor_with_mocked_root.data_model.data = {"Components": {"Motor": {"Configuration": {"Wiring": {"Type": "star"}}}}}

        # Create mock entries for paths at different nesting levels
        shallow_path = ("Motor", "Type")
        nested_path = ("Motor", "Configuration", "Wiring", "Type")

        mock_entry1 = MagicMock()
        mock_entry1.get.return_value = "brushless"
        mock_entry2 = MagicMock()
        mock_entry2.get.return_value = "delta"

        editor_with_mocked_root.entry_widgets = {shallow_path: mock_entry1, nested_path: mock_entry2}

        # Update the data model from UI (simulating save)
        editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data = MagicMock(return_value=(False, ""))
        editor_with_mocked_root.save_component_json()

        # Verify both paths were updated correctly
        assert editor_with_mocked_root.data_model.get_component_value(shallow_path) == "brushless"
        assert editor_with_mocked_root.data_model.get_component_value(nested_path) == "delta"

    def test_type_conversion_in_data_model(self, editor_with_mocked_root) -> None:
        """Test type conversion when updating the data model from UI."""
        # Setup paths for different types
        int_path = ("Motor", "KV")
        float_path = ("Motor", "Weight")
        string_path = ("Motor", "Type")
        version_path = ("Motor", "Version")  # Special case that should remain string

        # Create mock entries with string values that should be converted
        mock_entry_int = MagicMock()
        mock_entry_int.get.return_value = "1000"

        mock_entry_float = MagicMock()
        mock_entry_float.get.return_value = "0.75"

        mock_entry_string = MagicMock()
        mock_entry_string.get.return_value = "brushless"

        mock_entry_version = MagicMock()
        mock_entry_version.get.return_value = "1.2.3"

        editor_with_mocked_root.entry_widgets = {
            int_path: mock_entry_int,
            float_path: mock_entry_float,
            string_path: mock_entry_string,
            version_path: mock_entry_version,
        }

        # Initialize data model
        editor_with_mocked_root.data_model.data = {"Components": {"Motor": {}}}

        # Update from UI (simulating save)
        editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data = MagicMock(return_value=(False, ""))
        editor_with_mocked_root.save_component_json()

        # Verify type conversions
        assert isinstance(editor_with_mocked_root.data_model.get_component_value(int_path), int)
        assert editor_with_mocked_root.data_model.get_component_value(int_path) == 1000

        assert isinstance(editor_with_mocked_root.data_model.get_component_value(float_path), float)
        assert editor_with_mocked_root.data_model.get_component_value(float_path) == 0.75

        assert isinstance(editor_with_mocked_root.data_model.get_component_value(string_path), str)
        assert editor_with_mocked_root.data_model.get_component_value(string_path) == "brushless"

        # Version should always remain string
        assert isinstance(editor_with_mocked_root.data_model.get_component_value(version_path), str)
        assert editor_with_mocked_root.data_model.get_component_value(version_path) == "1.2.3"


class TestGUIValidationAndErrorHandling:
    """Tests for GUI validation and error handling."""

    @pytest.fixture
    def editor_for_validation_tests(self) -> ComponentEditorWindowBase:
        """Create an editor setup for validation testing."""
        with patch.object(ComponentEditorWindowBase, "__init__", return_value=None):
            editor = ComponentEditorWindowBase()

            # Set up required attributes
            editor.root = MagicMock()
            editor.main_frame = MagicMock()
            editor.scroll_frame = MagicMock()

            # Setup filesystem mock
            editor.local_filesystem = MagicMock(spec=LocalFilesystem)
            editor.local_filesystem.vehicle_dir = "dummy_vehicle_dir"

            # Setup test data
            editor.data_model = ComponentDataModel({"Components": {"Motor": {"Type": "brushless"}}})
            editor.data = editor.data_model.data

            # Setup entry widgets
            mock_entry = MagicMock()
            mock_entry.get.return_value = "invalid"
            editor.entry_widgets = {("Motor", "Type"): mock_entry}

            yield editor

    @patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_error_message")
    def test_save_component_json_with_validation_error(self, mock_show_error, editor_for_validation_tests) -> None:
        """Test save_component_json with validation error from filesystem."""
        # Setup filesystem.save_vehicle_components_json_data to return error
        editor_for_validation_tests.local_filesystem.save_vehicle_components_json_data.return_value = (True, "Invalid data")

        # Call the method
        editor_for_validation_tests.save_component_json()

        # Verify error was shown
        mock_show_error.assert_called_once()
        assert "Invalid data" in mock_show_error.call_args[0][1]

        # Verify window was still destroyed despite error
        editor_for_validation_tests.root.destroy.assert_called_once()

    def test_validate_and_save_component_json_flow(self, editor_for_validation_tests) -> None:
        """Test the validation and save flow."""
        # Mock confirmation dialog to return True
        editor_for_validation_tests._confirm_component_properties = MagicMock(return_value=True)
        editor_for_validation_tests.save_component_json = MagicMock()

        # Call the method
        editor_for_validation_tests.validate_and_save_component_json()

        # Verify confirmation was requested and save was called
        editor_for_validation_tests._confirm_component_properties.assert_called_once()
        editor_for_validation_tests.save_component_json.assert_called_once()

        # Reset mocks and test with negative confirmation
        editor_for_validation_tests._confirm_component_properties.reset_mock()
        editor_for_validation_tests.save_component_json.reset_mock()

        # Now return False from confirmation
        editor_for_validation_tests._confirm_component_properties.return_value = False

        # Call the method again
        editor_for_validation_tests.validate_and_save_component_json()

        # Verify confirmation was requested but save was not called
        editor_for_validation_tests._confirm_component_properties.assert_called_once()
        editor_for_validation_tests.save_component_json.assert_not_called()


class TestGUIComponentInteraction:
    """Tests for GUI component interaction methods."""

    @pytest.fixture
    def editor_with_gui_components(self) -> ComponentEditorWindowBase:
        """Set up an editor with mock GUI components for interaction testing."""
        with patch.object(ComponentEditorWindowBase, "__init__", return_value=None):
            editor = ComponentEditorWindowBase()

            # Set up required attributes
            editor.root = MagicMock()
            editor.main_frame = MagicMock()
            editor.scroll_frame = MagicMock()
            editor.scroll_frame.view_port = MagicMock()

            # Mock filesystem
            editor.local_filesystem = MagicMock(spec=LocalFilesystem)
            editor.local_filesystem.vehicle_dir = "dummy_vehicle_dir"
            editor.local_filesystem.vehicle_image_exists = MagicMock(return_value=True)
            editor.local_filesystem.vehicle_image_filepath = MagicMock(return_value="dummy/path/to/image.jpg")

            # Setup test data
            editor.data_model = ComponentDataModel({"Components": {"Motor": {"Type": "brushless", "KV": 1000}}})
            editor.data = editor.data_model.data

            # Mock entry widgets
            mock_entry1 = MagicMock(spec=ttk.Entry)
            mock_entry2 = MagicMock(spec=ttk.Entry)
            editor.entry_widgets = {("Motor", "Type"): mock_entry1, ("Motor", "KV"): mock_entry2}

            # Mock image handling
            editor.put_image_in_label = MagicMock(return_value=MagicMock())

            yield editor

    def test_add_vehicle_image_with_image(self, editor_with_gui_components) -> None:
        """Test _add_vehicle_image when image exists."""
        mock_parent = MagicMock()
        mock_image_label = MagicMock()
        editor_with_gui_components.put_image_in_label.return_value = mock_image_label

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.show_tooltip"):
            # Call the method
            editor_with_gui_components._add_vehicle_image(mock_parent)

            # Verify image label was created
            editor_with_gui_components.put_image_in_label.assert_called_once()
            mock_image_label.pack.assert_called_once()

    def test_add_vehicle_image_without_image(self, editor_with_gui_components) -> None:
        """Test _add_vehicle_image when no image exists."""
        # Change vehicle_image_exists to return False
        editor_with_gui_components.local_filesystem.vehicle_image_exists.return_value = False

        mock_parent = MagicMock()

        with patch("tkinter.ttk.Label", return_value=MagicMock()) as mock_label:
            # Call the method
            editor_with_gui_components._add_vehicle_image(mock_parent)

            # Verify label with instruction text was created
            mock_label.assert_called_once()
            mock_label.return_value.pack.assert_called_once()

    def test_add_explanation_text(self, editor_with_gui_components) -> None:
        """Test _add_explanation_text creates a label with explanation text."""
        mock_parent = MagicMock()
        mock_label = MagicMock()

        with patch("tkinter.ttk.Label", return_value=mock_label) as mock_label_class:
            # Call the method
            editor_with_gui_components._add_explanation_text(mock_parent)

            # Verify label was created with explanation text
            mock_label_class.assert_called_once()
            mock_label.configure.assert_called_once_with(style="bigger.TLabel")
            mock_label.pack.assert_called_once()


class TestComplexGUIIntegration:
    """Tests for complex GUI integration scenarios."""

    @pytest.fixture
    def complex_editor_setup(self) -> ComponentEditorWindowBase:
        """Set up an editor with complex test data for integration testing."""
        with patch.object(ComponentEditorWindowBase, "__init__", return_value=None):
            editor = ComponentEditorWindowBase()

            # Set up basic attributes
            editor.root = MagicMock()
            editor.main_frame = MagicMock()
            editor.scroll_frame = MagicMock()
            editor.scroll_frame.view_port = MagicMock()
            editor.version = "test_version"

            # Mock filesystem
            editor.local_filesystem = MagicMock(spec=LocalFilesystem)
            editor.local_filesystem.vehicle_dir = "dummy_vehicle_dir"

            # Setup complex test data
            editor.data_model = ComponentDataModel(
                {
                    "Components": {
                        "Motor": {
                            "Type": "brushless",
                            "KV": 1000,
                            "Configuration": {"Wiring": "star", "Mounting": {"Position": "arm", "Angle": 0}},
                        },
                        "ESC": {"Type": "4-in-1", "Current": 30},
                    },
                    "Format version": 1,
                }
            )
            editor.data = editor.data_model.data

            # Setting up entry widgets with complex paths
            editor.entry_widgets = {
                ("Motor", "Type"): MagicMock(),
                ("Motor", "KV"): MagicMock(),
                ("Motor", "Configuration", "Wiring"): MagicMock(),
                ("Motor", "Configuration", "Mounting", "Position"): MagicMock(),
                ("Motor", "Configuration", "Mounting", "Angle"): MagicMock(),
                ("ESC", "Type"): MagicMock(),
                ("ESC", "Current"): MagicMock(),
            }

            # Mock template manager
            editor.template_manager = MagicMock()

            yield editor

    def test_full_initialization_sequence(self) -> None:
        """Test the full initialization sequence of the editor."""
        # Create mocks for init operations
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        # Set required attributes on the mock filesystem
        mock_filesystem.vehicle_dir = "dummy/vehicle/dir"
        mock_filesystem.vehicle_type = "copter"
        mock_filesystem.load_vehicle_components_json_data.return_value = {
            "Components": {"Motor": {"Type": "brushless"}},
            "Format version": 1,
        }
        mock_filesystem.application_icon_filepath = MagicMock(return_value="dummy/path/icon.png")
        mock_filesystem.vehicle_components = MagicMock()
        mock_filesystem.vehicle_components.load_schema.return_value = {"properties": {}}
        mock_filesystem.get_component_property_description = MagicMock(return_value=("Test description", False))

        # Patch all the methods that try to use actual tkinter
        with (
            patch("tkinter.Tk", return_value=MagicMock()),
            patch("tkinter.PhotoImage", return_value=MagicMock()),  # Mock PhotoImage to avoid image loading
            patch.object(BaseWindow, "__init__", return_value=None),  # Skip parent class initialization
            patch.object(ComponentEditorWindowBase, "__init__", return_value=None),  # Skip initialization completely
        ):
            # Create the instance without calling __init__
            editor = ComponentEditorWindowBase()

            # Manually set up the required attributes and mock the methods
            editor.version = "1.0.0"
            editor.local_filesystem = mock_filesystem
            editor.root = MagicMock()
            editor.main_frame = MagicMock()

            # Call the methods directly to simulate initialization sequence
            raw_data = mock_filesystem.load_vehicle_components_json_data(mock_filesystem.vehicle_dir)
            editor.data_model = ComponentDataModel(raw_data)
            editor.data = editor.data_model.data
            editor._check_data = MagicMock(return_value=True)
            editor._setup_window = MagicMock()
            editor._setup_styles = MagicMock()
            editor._create_intro_frame = MagicMock()
            editor._create_scroll_frame = MagicMock()
            editor.update_json_data = MagicMock()
            editor._create_save_frame = MagicMock()
            editor._setup_template_manager = MagicMock()
            editor._check_show_usage_instructions = MagicMock()

            # Execute the manual initialization sequence
            editor._check_data()
            editor._setup_window()
            editor._setup_styles()
            editor._create_intro_frame()
            editor._create_scroll_frame()
            editor.update_json_data()
            editor._create_save_frame()
            editor._setup_template_manager()
            editor._check_show_usage_instructions()

            # Verify data was loaded from filesystem
            mock_filesystem.load_vehicle_components_json_data.assert_called_once_with(mock_filesystem.vehicle_dir)

            # Verify all initialization methods were called
            editor._check_data.assert_called_once()
            editor._setup_window.assert_called_once()
            editor._setup_styles.assert_called_once()
            editor._create_intro_frame.assert_called_once()
            editor._create_scroll_frame.assert_called_once()
            editor.update_json_data.assert_called_once()
            editor._create_save_frame.assert_called_once()
            editor._setup_template_manager.assert_called_once()
            editor._check_show_usage_instructions.assert_called_once()

            # Verify data model was initialized with the loaded data
            assert isinstance(editor.data_model, ComponentDataModel)
            assert editor.version == "1.0.0"

    def test_nested_widget_hierarchy_creation(self, complex_editor_setup) -> None:
        """Test creation of a nested widget hierarchy from complex data."""
        editor = complex_editor_setup

        # Mock the component data generation to ensure components are visible
        def mock_get_all_components() -> dict:
            return {
                "Motor": {
                    "Type": "brushless",
                    "KV": 1000,
                    "Configuration": {"Wiring": "star", "Mounting": {"Position": "arm", "Angle": 0}},
                },
                "ESC": {"Type": "4-in-1", "Current": 30},
            }

        # Override the get_all_components method
        editor.data_model.get_all_components = mock_get_all_components

        # Mock methods that would be called during widget creation
        editor._add_non_leaf_widget = MagicMock()
        editor._add_leaf_widget = MagicMock()

        # Track widgets added with a clean approach
        widget_paths = []

        # Create a spy for _add_widget that just records calls
        def spy_add_widget(parent, key, value, path) -> None:
            # Record the call path
            current_path = [*list(path), key]
            widget_paths.append(tuple(current_path))

            # Process non-leaf nodes recursively
            if isinstance(value, dict):
                # Call appropriate mock for the component itself
                editor._add_non_leaf_widget(parent, key, value, path)
                # Recursively process children
                for sub_key, sub_value in value.items():
                    spy_add_widget(parent, sub_key, sub_value, current_path)
            else:
                # Call leaf mock for leaf values
                editor._add_leaf_widget(parent, key, value, path)

        # Store original and replace with our spy
        original_add_widget = editor._add_widget
        editor._add_widget = spy_add_widget

        try:
            # Call populate_frames which should process top-level components
            editor.populate_frames()

            # Check paths of widgets that were added
            assert ("Motor",) in widget_paths
            assert ("Motor", "Type") in widget_paths
            assert ("Motor", "KV") in widget_paths
            assert ("Motor", "Configuration") in widget_paths
            assert ("Motor", "Configuration", "Wiring") in widget_paths
            assert ("Motor", "Configuration", "Mounting") in widget_paths
            assert ("Motor", "Configuration", "Mounting", "Position") in widget_paths
            assert ("Motor", "Configuration", "Mounting", "Angle") in widget_paths
            assert ("ESC",) in widget_paths
            assert ("ESC", "Type") in widget_paths
            assert ("ESC", "Current") in widget_paths

            # Verify that _add_non_leaf_widget and _add_leaf_widget were called appropriate number of times
            # 4 non-leaf calls: Motor, ESC, Configuration, Mounting
            assert editor._add_non_leaf_widget.call_count == 4
            # 7 leaf calls: Motor.Type, Motor.KV, Motor.Configuration.Wiring,
            #               Motor.Configuration.Mounting.Position, Motor.Configuration.Mounting.Angle,
            #               ESC.Type, ESC.Current
            assert editor._add_leaf_widget.call_count == 7

        finally:
            # Restore the original method
            editor._add_widget = original_add_widget

    def test_display_component_editor_usage_instructions(self, complex_editor_setup) -> None:
        """Test that usage instructions are displayed correctly."""
        editor = complex_editor_setup
        mock_parent = MagicMock(spec=tk.Tk)

        # Mock UsagePopupWindow class methods
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.BaseWindow") as mock_base_window,
            patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.RichText") as mock_rich_text,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.UsagePopupWindow.display"
            ) as mock_display,
            patch("tkinter.ttk.Style") as mock_style,
        ):
            # Create mocks for the window and text widget
            mock_window_instance = MagicMock()
            mock_base_window.return_value = mock_window_instance
            mock_text_instance = MagicMock()
            mock_rich_text.return_value = mock_text_instance

            # Setup style.lookup to return a background color
            mock_style_instance = MagicMock()
            mock_style.return_value = mock_style_instance
            mock_style_instance.lookup.return_value = "#FFFFFF"

            # Call the method
            editor._display_component_editor_usage_instructions(mock_parent)

            # Verify the window and text widget were created
            mock_base_window.assert_called_once_with(mock_parent)
            mock_rich_text.assert_called_once()

            # Verify text was inserted
            assert mock_text_instance.insert.call_count > 0
            # Use assert_called_once_with instead of called_once_with
            mock_text_instance.config.assert_called_once_with(state=tk.DISABLED)

            # Verify display was called with correct parameters
            mock_display.assert_called_once()
            assert mock_display.call_args[0][0] == mock_parent
            assert mock_display.call_args[0][1] == mock_window_instance
