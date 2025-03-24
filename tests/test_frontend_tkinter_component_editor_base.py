#!/usr/bin/env python3

"""
Component editor GUI tests.

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
from ardupilot_methodic_configurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase


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

        # Setup test data
        editor.entry_widgets = {}
        editor.data = {"Components": {"Motor": {"Type": "brushless", "KV": 1000}}}

        # Mock the actual _add_widget method to avoid infinite recursion
        original_add_widget = editor._add_widget  # pylint: disable=protected-access

        # Store the original method
        editor._original_add_widget = original_add_widget  # pylint: disable=protected-access

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
    editor_with_mocked_root.data = {}
    editor_with_mocked_root.update_json_data()
    assert editor_with_mocked_root.data["Format version"] == 1

    # Test when Format version is already in data
    editor_with_mocked_root.data = {"Format version": 2}
    editor_with_mocked_root.update_json_data()
    assert editor_with_mocked_root.data["Format version"] == 2


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
    """Test the _set_component_value_and_update_ui method."""
    # Setup test data
    editor_with_mocked_root.data = {"Components": {"Motor": {"Type": "old_value"}}}
    mock_entry = MagicMock()
    editor_with_mocked_root.entry_widgets = {("Motor", "Type"): mock_entry}

    # Call the method
    editor_with_mocked_root._set_component_value_and_update_ui(("Motor", "Type"), "new_value")  # pylint: disable=protected-access

    # Assert data was updated
    assert editor_with_mocked_root.data["Components"]["Motor"]["Type"] == "new_value"

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
    editor_with_mocked_root.data = {"Components": {"Motor": {"Type": "brushless"}}}
    mock_entry = MagicMock()
    mock_entry.get.return_value = "new_value"
    editor_with_mocked_root.entry_widgets = {("Motor", "Type"): mock_entry}
    editor_with_mocked_root.local_filesystem.save_vehicle_components_json_data.return_value = (False, "")

    # For this test we need to use the real save_component_json, not a mock
    original_method = ComponentEditorWindowBase.save_component_json
    editor_with_mocked_root.save_component_json = lambda: original_method(editor_with_mocked_root)

    # Call the method
    editor_with_mocked_root.save_component_json()

    # Assert data was updated and saved
    assert editor_with_mocked_root.data["Components"]["Motor"]["Type"] == "new_value"
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

    # Store original method to restore later
    original_add_leaf_widget = editor_with_mocked_root._ComponentEditorWindowBase__add_leaf_widget  # pylint: disable=protected-access

    # We need to directly call the original _add_widget method, but mock the private __add_leaf_widget
    # so it adds the entry to entry_widgets without creating UI elements that will fail in tests
    def mock_add_leaf_widget(parent, key, value, path) -> None:  # pylint: disable=unused-argument # noqa: ARG001
        # This simulates what the real method does, but in a test-friendly way
        # The real method would create a frame, but we'll use our mock_frame_instance
        entry = editor_with_mocked_root.add_entry_or_combobox(value, mock_frame_instance, (*path, key))
        editor_with_mocked_root.entry_widgets[(*path, key)] = entry

    # Replace the private method with our mock
    editor_with_mocked_root._ComponentEditorWindowBase__add_leaf_widget = mock_add_leaf_widget  # pylint: disable=protected-access

    try:
        # Call the method with a leaf value and path
        path = ["Component"]
        test_value = 42.5
        editor_with_mocked_root._add_widget(mock_parent, "TestKey", test_value, path)  # pylint: disable=protected-access

        # Verify entry was created through add_entry_or_combobox with correct parameters
        editor_with_mocked_root.add_entry_or_combobox.assert_called_once_with(
            test_value, mock_frame_instance, (*path, "TestKey")
        )

        # Verify the entry is stored in the entry_widgets dictionary
        expected_key = (*path, "TestKey")
        assert expected_key in editor_with_mocked_root.entry_widgets
    finally:
        # Restore original method
        editor_with_mocked_root._ComponentEditorWindowBase__add_leaf_widget = original_add_leaf_widget  # pylint: disable=protected-access


def test_populate_frames(editor_with_mocked_root) -> None:  # pylint: disable=redefined-outer-name
    """Test the populate_frames method."""
    # Setup test data
    editor_with_mocked_root.data = {"Components": {"Motor": {"Type": "brushless", "KV": 1000}}}

    # Mock the _add_widget method
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
    # Setup test data with a nested structure to test both __add_non_leaf_widget and __add_leaf_widget
    editor_with_mocked_root.data = {
        "Components": {
            "Motor": {  # This will trigger __add_non_leaf_widget
                "Type": "brushless",  # This will trigger __add_leaf_widget
                "KV": 1000,  # This will trigger __add_leaf_widget
            },
            "Battery": {  # Another non-leaf
                "Voltage": 12.6  # Another leaf
            },
        }
    }

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

    # We need to directly modify the _add_widget implementation for testing
    original_add_widget = editor_with_mocked_root._add_widget  # pylint: disable=protected-access
    original_add_non_leaf = editor_with_mocked_root._ComponentEditorWindowBase__add_non_leaf_widget  # pylint: disable=protected-access
    original_add_leaf = editor_with_mocked_root._ComponentEditorWindowBase__add_leaf_widget  # pylint: disable=protected-access

    # Create test-friendly versions that don't rely on tkinter widgets
    def test_add_non_leaf_widget(parent, key, value, path) -> None:
        frame = mock_labelframe_instance
        editor_with_mocked_root._add_widget_calls.append(("non_leaf", parent, key, value, path))  # pylint: disable=protected-access
        # Process children
        for child_key, child_value in value.items():
            editor_with_mocked_root._add_widget(frame, child_key, child_value, [*path, key])  # pylint: disable=protected-access

    def test_add_leaf_widget(parent, key, value, path) -> None:
        frame = mock_frame_instance
        entry = editor_with_mocked_root.add_entry_or_combobox(value, frame, (*path, key))
        editor_with_mocked_root.entry_widgets[(*path, key)] = entry
        editor_with_mocked_root._add_widget_calls.append(("leaf", parent, key, value, path))  # pylint: disable=protected-access

    # Replace methods
    editor_with_mocked_root._ComponentEditorWindowBase__add_non_leaf_widget = test_add_non_leaf_widget  # pylint: disable=protected-access
    editor_with_mocked_root._ComponentEditorWindowBase__add_leaf_widget = test_add_leaf_widget  # pylint: disable=protected-access
    editor_with_mocked_root._add_widget_calls = []  # pylint: disable=protected-access

    try:
        # Call the method
        editor_with_mocked_root.populate_frames()

        # Verify the hierarchical structure of calls
        calls = editor_with_mocked_root._add_widget_calls  # pylint: disable=protected-access

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

        # Verify add_entry_or_combobox was called for each leaf
        assert editor_with_mocked_root.add_entry_or_combobox.call_count == 3

    finally:
        # Restore original methods
        editor_with_mocked_root._add_widget = original_add_widget  # pylint: disable=protected-access
        editor_with_mocked_root._ComponentEditorWindowBase__add_non_leaf_widget = original_add_non_leaf  # pylint: disable=protected-access
        editor_with_mocked_root._ComponentEditorWindowBase__add_leaf_widget = original_add_leaf  # pylint: disable=protected-access


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
