#!/usr/bin/env python3

"""
Component editor GUI tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
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

        # Mock filesystem and methods
        editor.local_filesystem = MagicMock(spec=LocalFilesystem)
        editor.local_filesystem.vehicle_dir = "dummy_vehicle_dir"

        # Setup test data
        editor.entry_widgets = {}
        editor.data = {"Components": {"Motor": {"Type": "brushless", "KV": 1000}}}

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
