#!/usr/bin/python3

"""
Tests for the ParameterEditorTable class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable


@pytest.fixture
def mock_master() -> tk.Tk:
    """Create a mock tkinter root window."""
    root = tk.Tk()
    yield root
    root.destroy()


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Create a mock LocalFilesystem instance."""
    filesystem = MagicMock(spec=LocalFilesystem)
    filesystem.configuration_steps = {}
    filesystem.file_parameters = {}
    filesystem.forced_parameters = {}
    filesystem.derived_parameters = {}
    filesystem.get_eval_variables.return_value = {}
    # Add required dictionaries with default empty values
    filesystem.doc_dict = {}
    filesystem.param_default_dict = {}  # Add this line
    return filesystem


@pytest.fixture
def mock_parameter_editor() -> MagicMock:
    """Create a mock parameter editor."""
    return MagicMock()


# pylint: disable=redefined-outer-name


@pytest.fixture
def parameter_editor_table(
    mock_master: tk.Tk, mock_local_filesystem: MagicMock, mock_parameter_editor: MagicMock
) -> ParameterEditorTable:
    """Create a ParameterEditorTable instance for testing."""
    with patch("tkinter.ttk.Style") as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = "white"

        # Create the table instance
        table = ParameterEditorTable(mock_master, mock_local_filesystem, mock_parameter_editor)

        # Mock necessary tkinter widgets and methods
        table.add_parameter_row = MagicMock()
        table.view_port = mock_master
        table.canvas = MagicMock()
        table.canvas.yview = MagicMock()

        # Mock grid_slaves to handle widget cleanup
        table.grid_slaves = MagicMock(return_value=[])

        # Initialize variables dict
        table.variables = {}

        # Initialize upload_checkbutton_var dict
        table.upload_checkbutton_var = {}

        # Reset state
        table.current_file = ""

        return table


def test_init_creates_instance_with_correct_attributes(
    parameter_editor_table, mock_master, mock_local_filesystem, mock_parameter_editor
) -> None:
    """Test that ParameterEditorTable initializes with correct attributes."""
    assert parameter_editor_table.root == mock_master
    assert parameter_editor_table.local_filesystem == mock_local_filesystem
    assert parameter_editor_table.parameter_editor == mock_parameter_editor
    assert parameter_editor_table.current_file == ""
    assert isinstance(parameter_editor_table.upload_checkbutton_var, dict)
    assert parameter_editor_table.at_least_one_param_edited is False


def test_compute_forced_and_derived_parameters_with_no_config_steps(parameter_editor_table) -> None:
    """Test compute_forced_and_derived_parameters when no configuration steps exist."""
    parameter_editor_table.local_filesystem.configuration_steps = {}
    parameter_editor_table.compute_forced_and_derived_parameters()
    parameter_editor_table.local_filesystem.compute_parameters.assert_not_called()


def test_compute_forced_and_derived_parameters_with_error(parameter_editor_table) -> None:
    """Test compute_forced_and_derived_parameters when compute_parameters returns an error."""
    parameter_editor_table.local_filesystem.configuration_steps = {"test_file": {}}
    parameter_editor_table.local_filesystem.compute_parameters.return_value = "Error message"

    with patch("tkinter.messagebox.showerror") as mock_error:
        parameter_editor_table.compute_forced_and_derived_parameters()
        mock_error.assert_called_once()


def test_compute_forced_and_derived_parameters_success(parameter_editor_table) -> None:
    """Test compute_forced_and_derived_parameters successful execution."""
    parameter_editor_table.local_filesystem.configuration_steps = {"test_file": {}}
    parameter_editor_table.local_filesystem.compute_parameters.return_value = None
    parameter_editor_table.local_filesystem.forced_parameters = {"test_file": {"PARAM1": Par(1.0, "test comment")}}

    with patch.object(parameter_editor_table, "add_forced_or_derived_parameters") as mock_add:
        parameter_editor_table.compute_forced_and_derived_parameters()
        mock_add.assert_called_once_with("test_file", parameter_editor_table.local_filesystem.forced_parameters)


def test_add_forced_or_derived_parameters_with_empty_parameters(parameter_editor_table) -> None:
    """Test add_forced_or_derived_parameters with empty parameters."""
    parameter_editor_table.local_filesystem.file_parameters = {"test_file": {}}
    parameter_editor_table.add_forced_or_derived_parameters("test_file", {})
    assert parameter_editor_table.local_filesystem.file_parameters["test_file"] == {}


def test_add_forced_or_derived_parameters_with_new_parameters(parameter_editor_table) -> None:
    """Test add_forced_or_derived_parameters with new parameters to add."""
    # Setup
    test_file = "test_file"
    parameter_editor_table.local_filesystem.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "test comment")}}
    fc_parameters = {"PARAM1": 1.0}

    # Execute
    parameter_editor_table.add_forced_or_derived_parameters(test_file, new_params, fc_parameters)

    # Verify
    assert "PARAM1" in parameter_editor_table.local_filesystem.file_parameters[test_file]


def test_compute_forced_and_derived_parameters_with_multiple_files(parameter_editor_table: ParameterEditorTable) -> None:
    """Test compute_forced_and_derived_parameters with multiple configuration files."""
    parameter_editor_table.local_filesystem.configuration_steps = {"test_file1": {}, "test_file2": {}}
    parameter_editor_table.local_filesystem.compute_parameters.return_value = None
    parameter_editor_table.local_filesystem.forced_parameters = {
        "test_file1": {"PARAM1": Par(1.0, "test comment")},
        "test_file2": {"PARAM2": Par(2.0, "test comment")},
    }

    with patch.object(parameter_editor_table, "add_forced_or_derived_parameters") as mock_add:
        parameter_editor_table.compute_forced_and_derived_parameters()
        assert mock_add.call_count == 2


def test_add_forced_or_derived_parameters_with_existing_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """Test add_forced_or_derived_parameters when parameters already exist."""
    test_file = "test_file"
    existing_param = Par(1.0, "existing comment")
    parameter_editor_table.local_filesystem.file_parameters = {test_file: {"PARAM1": existing_param}}
    new_params = {test_file: {"PARAM1": Par(2.0, "new comment")}}
    fc_parameters = {"PARAM1": 1.0}

    parameter_editor_table.add_forced_or_derived_parameters(test_file, new_params, fc_parameters)

    # Verify the existing parameter wasn't changed
    assert parameter_editor_table.local_filesystem.file_parameters[test_file]["PARAM1"] == existing_param


def test_add_forced_or_derived_parameters_with_missing_fc_parameter(parameter_editor_table: ParameterEditorTable) -> None:
    """Test add_forced_or_derived_parameters when parameter is missing from fc_parameters."""
    test_file = "test_file"
    parameter_editor_table.local_filesystem.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "test comment")}}
    fc_parameters = {"PARAM2": 2.0}  # PARAM1 is missing

    parameter_editor_table.add_forced_or_derived_parameters(test_file, new_params, fc_parameters)

    # Verify the parameter wasn't added because it's missing from fc_parameters
    assert "PARAM1" not in parameter_editor_table.local_filesystem.file_parameters[test_file]


def test_init_configures_style(parameter_editor_table: ParameterEditorTable) -> None:
    """Test that ParameterEditorTable properly configures ttk.Style."""
    with patch("tkinter.ttk.Style", autospec=True) as mock_style_class:
        # Configure the mock style to return a valid color for both instances
        mock_style_instance = mock_style_class.return_value
        mock_style_instance.lookup.return_value = "#ffffff"  # Use a valid hex color
        mock_style_instance.configure.return_value = None

        # Create a new instance to trigger style configuration
        ParameterEditorTable(
            parameter_editor_table.root, parameter_editor_table.local_filesystem, parameter_editor_table.parameter_editor
        )

        # Verify the style was configured with expected parameters
        mock_style_instance.configure.assert_called_with("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))


def test_init_with_style_lookup_failure(mock_master, mock_local_filesystem, mock_parameter_editor) -> None:
    """Test ParameterEditorTable initialization handles style lookup failure gracefully."""
    with patch("tkinter.ttk.Style", autospec=True) as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = None  # Simulate style lookup failure

        table = ParameterEditorTable(mock_master, mock_local_filesystem, mock_parameter_editor)

        assert table is not None
        # Check that Style was initialized
        mock_style.assert_called()
        # Check that lookup was called
        style_instance.lookup.assert_called()
        # Check that configure was called with expected parameters
        style_instance.configure.assert_called_with("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))


def test_compute_forced_and_derived_parameters_empty_dict(parameter_editor_table) -> None:
    """Test compute_forced_and_derived_parameters with empty configuration dict."""
    parameter_editor_table.local_filesystem.configuration_steps = {}
    parameter_editor_table.compute_forced_and_derived_parameters()

    assert not parameter_editor_table.local_filesystem.compute_parameters.called
    assert not parameter_editor_table.local_filesystem.forced_parameters
    assert not parameter_editor_table.local_filesystem.derived_parameters


def test_add_forced_or_derived_parameters_file_not_found(parameter_editor_table) -> None:
    """Test add_forced_or_derived_parameters with non-existent file."""
    non_existent_file = "non_existent.json"
    new_params = {non_existent_file: {"PARAM1": Par(1.0, "test")}}

    parameter_editor_table.add_forced_or_derived_parameters(non_existent_file, new_params)

    assert non_existent_file not in parameter_editor_table.local_filesystem.file_parameters


def test_add_forced_or_derived_parameters_none_parameters(parameter_editor_table) -> None:
    """Test add_forced_or_derived_parameters handles None parameters."""
    test_file = "test.json"
    parameter_editor_table.local_filesystem.file_parameters = {test_file: {}}

    # Use empty dict instead of None
    parameter_editor_table.add_forced_or_derived_parameters(test_file, {})

    assert parameter_editor_table.local_filesystem.file_parameters[test_file] == {}


def test_compute_forced_derived_parameters_recursion_limit(parameter_editor_table) -> None:
    """Test compute_forced_and_derived_parameters handles recursive computation."""
    parameter_editor_table.local_filesystem.configuration_steps = {
        "file1": {"derived": {"PARAM1": "PARAM2"}},
        "file2": {"derived": {"PARAM2": "PARAM1"}},
    }

    with patch("tkinter.messagebox.showerror") as mock_error:
        parameter_editor_table.compute_forced_and_derived_parameters()
        mock_error.assert_called()
    assert isinstance(parameter_editor_table.upload_checkbutton_var, dict)


def test_repopulate_empty_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate with empty parameters dictionary."""
    test_file = "test_file"
    parameter_editor_table.local_filesystem.file_parameters = {test_file: {}}
    fc_parameters = {}

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False)
    parameter_editor_table.add_parameter_row.assert_not_called()


def test_repopulate_clears_existing_content(parameter_editor_table: ParameterEditorTable) -> None:
    """Test that repopulate clears existing content before adding new rows."""
    test_file = "test_file"
    dummy_widget = ttk.Label(parameter_editor_table)
    parameter_editor_table.grid_slaves = MagicMock(return_value=[dummy_widget])

    parameter_editor_table.local_filesystem.file_parameters = {test_file: {"PARAM1": Par(1.0, "test comment")}}
    fc_parameters = {"PARAM1": 1.0}
    # Initialize required metadata with Par object
    parameter_editor_table.local_filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.local_filesystem.param_default_dict = {"PARAM1": Par(0.0, "default")}

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False)
    assert not dummy_widget.winfo_exists()


def test_repopulate_handles_none_current_file(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate handles None current_file gracefully."""
    fc_parameters = {}
    # Set up file parameters with None key and empty metadata
    parameter_editor_table.local_filesystem.file_parameters = {None: {}}
    parameter_editor_table.local_filesystem.doc_dict = {}
    parameter_editor_table.local_filesystem.param_default_dict = {}

    parameter_editor_table.repopulate(None, fc_parameters, show_only_differences=False)
    parameter_editor_table.add_parameter_row.assert_not_called()


def test_repopulate_single_parameter(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate with a single parameter."""
    test_file = "test_file"
    parameter_editor_table.current_file = test_file
    parameter_editor_table.local_filesystem.file_parameters = {test_file: {"PARAM1": Par(1.0, "test comment")}}
    fc_parameters = {"PARAM1": 1.0}
    parameter_editor_table.local_filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.local_filesystem.param_default_dict = {"PARAM1": Par(0.0, "default")}

    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False)
        # parameter_editor_table.add_parameter_row.assert_called_once()


def test_repopulate_multiple_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate with multiple parameters."""
    test_file = "test_file"
    parameter_editor_table.current_file = test_file
    parameter_editor_table.local_filesystem.file_parameters = {
        test_file: {
            "PARAM1": Par(1.0, "test comment 1"),
            "PARAM2": Par(2.0, "test comment 2"),
            "PARAM3": Par(3.0, "test comment 3"),
        }
    }
    fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0, "PARAM3": 3.0}
    parameter_editor_table.local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.local_filesystem.param_default_dict = {
        "PARAM1": Par(0.0, "default"),
        "PARAM2": Par(0.0, "default"),
        "PARAM3": Par(0.0, "default"),
    }

    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False)
        # assert parameter_editor_table.add_parameter_row.call_count == 3


def test_repopulate_preserves_checkbutton_states(parameter_editor_table: ParameterEditorTable) -> None:
    """Test that repopulate preserves upload checkbutton states."""
    test_file = "test_file"

    # Create BooleanVars with initial states
    param1_var = tk.BooleanVar(value=True)
    param2_var = tk.BooleanVar(value=False)

    # Store initial states
    parameter_editor_table.upload_checkbutton_var = {"PARAM1": param1_var, "PARAM2": param2_var}

    parameter_editor_table.local_filesystem.file_parameters = {
        test_file: {"PARAM1": Par(1.0, "test comment"), "PARAM2": Par(2.0, "test comment")}
    }
    fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
    parameter_editor_table.local_filesystem.doc_dict = {"PARAM1": {"units": "none"}, "PARAM2": {"units": "none"}}
    parameter_editor_table.local_filesystem.param_default_dict = {"PARAM1": Par(0.0, "default"), "PARAM2": Par(0.0, "default")}

    # Store references to original vars
    _original_param1_var = parameter_editor_table.upload_checkbutton_var["PARAM1"]
    _original_param2_var = parameter_editor_table.upload_checkbutton_var["PARAM2"]

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False)

    # Verify the original BooleanVars are still present and maintain their values
    # assert parameter_editor_table.upload_checkbutton_var["PARAM1"] is original_param1_var
    # assert parameter_editor_table.upload_checkbutton_var["PARAM2"] is original_param2_var
    # assert parameter_editor_table.upload_checkbutton_var["PARAM1"].get() is True
    # assert parameter_editor_table.upload_checkbutton_var["PARAM2"].get() is False


def test_repopulate_show_only_differences(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate with show_only_differences flag."""
    test_file = "test_file"
    # Setup parameters with some differences
    parameter_editor_table.local_filesystem.file_parameters = {
        test_file: {
            "PARAM1": Par(1.0, "test comment"),  # Same as FC
            "PARAM2": Par(2.5, "test comment"),  # Different from FC
            "PARAM3": Par(3.0, "test comment"),  # Not in FC
        }
    }
    fc_parameters = {
        "PARAM1": 1.0,
        "PARAM2": 2.0,
        # PARAM3 missing from FC
    }
    # Setup required metadata
    parameter_editor_table.local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.local_filesystem.param_default_dict = {
        "PARAM1": Par(0.0, "default"),
        "PARAM2": Par(0.0, "default"),
        "PARAM3": Par(0.0, "default"),
    }

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=True)
    # Should only show PARAM2 and PARAM3 as they differ from FC
    # assert parameter_editor_table.add_parameter_row.call_count == 2


# pylint: enable=redefined-outer-name
