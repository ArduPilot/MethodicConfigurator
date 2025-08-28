#!/usr/bin/python3

"""
Integration tests for the ParameterEditorTable class.

These tests focus on end-to-end workflows and realistic usage scenarios,
testing the interaction between multiple components and methods.

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
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable

# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def mock_root() -> tk.Tk:
    """Create a real tkinter root window for integration testing."""
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the window during testing
        yield root
        root.destroy()
    except tk.TclError:
        # Skip tests if Tkinter is not available
        pytest.skip("Tkinter not available in test environment")


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Create a realistic mock LocalFilesystem with comprehensive data."""
    filesystem = MagicMock(spec=LocalFilesystem)

    # Configuration steps
    filesystem.configuration_steps = {
        "01_first_step.param": {
            "description": "First configuration step",
            "forced_parameters": {"FORCED_PARAM": 5.0},
            "derived_parameters": {"DERIVED_PARAM": "fc_parameters['BATT_CAPACITY'] * 0.8"},
        },
        "02_second_step.param": {"description": "Second configuration step"},
    }

    # File parameters
    filesystem.file_parameters = {
        "01_first_step.param": {
            "PARAM_1": Par(1.0, "First parameter comment"),
            "PARAM_2": Par(2.5, "Second parameter comment"),
            "FORCED_PARAM": Par(5.0, "This is forced"),
            "DERIVED_PARAM": Par(800.0, "This is derived"),
            "BATT_CAPACITY": Par(1000.0, "Battery capacity"),
            "RC1_MIN": Par(1000.0, "RC channel 1 minimum"),
            "RC1_MAX": Par(2000.0, "RC channel 1 maximum"),
        },
        "02_second_step.param": {"PARAM_3": Par(3.14, "Pi parameter"), "PARAM_4": Par(-1.5, "Negative parameter")},
    }

    # Forced parameters
    filesystem.forced_parameters = {"01_first_step.param": {"FORCED_PARAM": Par(5.0, "Forced value - cannot be changed")}}

    # Derived parameters
    filesystem.derived_parameters = {"01_first_step.param": {"DERIVED_PARAM": Par(800.0, "Derived from battery capacity")}}

    # Parameter documentation
    filesystem.doc_dict = {
        "PARAM_1": {
            "Description": "First test parameter",
            "DisplayName": "Parameter 1",
            "units": "m/s",
            "unit_tooltip": "meters per second",
            "min": 0.0,
            "max": 10.0,
        },
        "PARAM_2": {
            "Description": "Second test parameter",
            "DisplayName": "Parameter 2",
            "units": "Hz",
            "unit_tooltip": "Hertz",
            "min": -5.0,
            "max": 5.0,
        },
        "PARAM_3": {"Description": "Pi constant parameter", "DisplayName": "Parameter 3", "ReadOnly": True},
        "PARAM_4": {
            "Description": "Negative test parameter",
            "DisplayName": "Parameter 4",
            "Calibration": True,
            "min": -10.0,
            "max": 0.0,
        },
        "FORCED_PARAM": {
            "Description": "Forced parameter for testing",
            "DisplayName": "Forced Parameter",
            "units": "A",
            "min": 0.0,
            "max": 20.0,
        },
        "DERIVED_PARAM": {"Description": "Derived parameter for testing", "DisplayName": "Derived Parameter", "units": "mAh"},
        "BATT_CAPACITY": {
            "Description": "Battery capacity",
            "DisplayName": "Battery Capacity",
            "units": "mAh",
            "min": 100.0,
            "max": 50000.0,
        },
        "RC1_MIN": {
            "Description": "RC channel 1 minimum PWM",
            "DisplayName": "RC1 Min",
            "units": "PWM",
            "min": 800.0,
            "max": 1200.0,
        },
        "RC1_MAX": {
            "Description": "RC channel 1 maximum PWM",
            "DisplayName": "RC1 Max",
            "units": "PWM",
            "min": 1800.0,
            "max": 2200.0,
        },
    }

    # Parameter defaults
    filesystem.param_default_dict = {
        "PARAM_1": Par(0.0, "Default value"),
        "PARAM_2": Par(0.0, "Default value"),
        "PARAM_3": Par(3.14159, "Default pi value"),
        "PARAM_4": Par(-1.0, "Default negative value"),
        "FORCED_PARAM": Par(1.0, "Default forced value"),
        "DERIVED_PARAM": Par(1000.0, "Default derived value"),
        "BATT_CAPACITY": Par(1000.0, "Default battery capacity"),
        "RC1_MIN": Par(1000.0, "Default RC min"),
        "RC1_MAX": Par(2000.0, "Default RC max"),
    }

    # Helper methods
    filesystem.get_eval_variables.return_value = {"fc_parameters": {}, "battery_capacity": 1000.0}
    filesystem.compute_parameters.return_value = None
    filesystem.merge_forced_or_derived_parameters.return_value = False

    return filesystem


@pytest.fixture
def mock_parameter_editor() -> MagicMock:
    """Create a realistic mock parameter editor."""
    editor = MagicMock()
    editor.gui_complexity = "advanced"
    editor.repopulate_parameter_table = MagicMock()
    return editor


@pytest.fixture
def parameter_editor_table(
    mock_root: tk.Tk, mock_local_filesystem: MagicMock, mock_parameter_editor: MagicMock
) -> ParameterEditorTable:
    """Create a ParameterEditorTable instance for integration testing."""
    with patch("tkinter.ttk.Style") as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = "white"  # Return valid color instead of memory address

        table = ParameterEditorTable(mock_root, mock_local_filesystem, mock_parameter_editor)

        # Create a real frame for the view_port to enable actual widget testing
        table.view_port = ttk.Frame(mock_root)
        table.canvas = MagicMock()
        table.canvas.yview = MagicMock()

        return table


class TestCompleteParameterWorkflows:  # pylint: disable=too-few-public-methods
    """Test complete parameter editing workflows from start to finish."""

    def test_gui_complexity_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete UI complexity workflow affecting column layout."""
        # Test advanced mode (default)
        assert parameter_editor_table._should_show_upload_column() is True
        assert parameter_editor_table._get_change_reason_column_index(show_upload_column=True) == 7

        # Test simple mode
        parameter_editor_table.parameter_editor.gui_complexity = "simple"
        assert parameter_editor_table._should_show_upload_column() is False
        assert parameter_editor_table._get_change_reason_column_index(show_upload_column=False) == 6

        # Test explicit override
        assert parameter_editor_table._should_show_upload_column("advanced") is True


class TestParameterAdditionAndDeletion:
    """Test parameter addition and deletion workflows."""

    def test_parameter_addition_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete parameter addition workflow."""
        parameter_editor_table.current_file = "01_first_step.param"
        fc_parameters = {"NEW_PARAM": 42.0}

        # Test successful parameter addition
        result = parameter_editor_table._confirm_parameter_addition("NEW_PARAM", fc_parameters)

        assert result is True
        assert "NEW_PARAM" in parameter_editor_table.local_filesystem.file_parameters["01_first_step.param"]
        assert parameter_editor_table.local_filesystem.file_parameters["01_first_step.param"]["NEW_PARAM"].value == 42.0
        assert parameter_editor_table.at_least_one_param_edited is True

    def test_parameter_addition_validation_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter addition validation workflow."""
        parameter_editor_table.current_file = "01_first_step.param"

        # Test empty parameter name
        with patch("tkinter.messagebox.showerror") as mock_error:
            result = parameter_editor_table._confirm_parameter_addition("", {})
            assert result is False
            mock_error.assert_called_once()

        # Test existing parameter name
        with patch("tkinter.messagebox.showerror") as mock_error:
            result = parameter_editor_table._confirm_parameter_addition("PARAM_1", {})
            assert result is False
            mock_error.assert_called_once()

    def test_parameter_deletion_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete parameter deletion workflow."""
        parameter_editor_table.current_file = "01_first_step.param"
        parameter_editor_table.canvas.yview.return_value = [0.5, 0.8]

        # Test confirmed deletion
        with patch("tkinter.messagebox.askyesno", return_value=True):
            parameter_editor_table._on_parameter_delete("PARAM_1")

            assert "PARAM_1" not in parameter_editor_table.local_filesystem.file_parameters["01_first_step.param"]
            assert parameter_editor_table.at_least_one_param_edited is True
            parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_called_once_with("01_first_step.param")

        # Reset for next test
        parameter_editor_table.local_filesystem.file_parameters["01_first_step.param"]["PARAM_2"] = Par(
            2.5, "Second parameter comment"
        )
        parameter_editor_table.at_least_one_param_edited = False
        parameter_editor_table.parameter_editor.repopulate_parameter_table.reset_mock()

        # Test cancelled deletion
        with patch("tkinter.messagebox.askyesno", return_value=False):
            parameter_editor_table._on_parameter_delete("PARAM_2")

            assert "PARAM_2" in parameter_editor_table.local_filesystem.file_parameters["01_first_step.param"]
            assert parameter_editor_table.at_least_one_param_edited is False
            parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_not_called()


class TestWidgetCreationIntegration:
    """Test widget creation in realistic scenarios."""

    def test_complete_widget_creation_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test creating a complete set of widgets for a parameter row."""
        param_name = "PARAM_1"
        param_metadata = parameter_editor_table.local_filesystem.doc_dict["PARAM_1"]
        param = ArduPilotParameter(
            param_name,
            Par(1.5, "Test parameter"),
            metadata=param_metadata,
            default_par=Par(1.6, "Test parameter"),
            fc_value=1.5,
        )
        show_upload_column = True
        fc_connected = True

        # Mock widget creation methods to return real widgets
        with patch.object(parameter_editor_table, "_create_new_value_entry") as mock_new_value:
            mock_new_value.return_value = ttk.Entry(parameter_editor_table.view_port)

            column = parameter_editor_table._create_column_widgets(param_name, param, show_upload_column, fc_connected)

            # Should create 8 widgets (including upload column)
            assert len(column) == 8

            # Verify all widgets are created
            assert all(widget is not None for widget in column)

    def test_upload_checkbutton_creation_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test upload checkbutton creation in different connection states."""
        # Test connected state
        checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM", fc_connected=True)
        assert isinstance(checkbutton, ttk.Checkbutton)
        assert str(checkbutton.cget("state")) == "normal"
        assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM"].get() is True

        # Test disconnected state
        checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM2", fc_connected=False)
        assert isinstance(checkbutton, ttk.Checkbutton)
        assert str(checkbutton.cget("state")) == "disabled"
        assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM2"].get() is False


class TestFileOperationsIntegration:
    """Test file operations and parameter management integration."""

    def test_repopulate_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete repopulate workflow."""
        test_file = "01_first_step.param"
        fc_parameters = {"PARAM_1": 1.0, "PARAM_2": 2.5, "FORCED_PARAM": 5.0, "DERIVED_PARAM": 800.0}

        # Clear existing widgets
        for widget in parameter_editor_table.view_port.winfo_children():
            widget.destroy()

        # Test repopulate
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False, gui_complexity="simple")

        # Verify current file is set
        assert parameter_editor_table.current_file == test_file

    def test_show_only_differences_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test show only differences workflow."""
        test_file = "01_first_step.param"
        # FC has different values for some parameters
        fc_parameters = {
            "PARAM_1": 1.0,  # Same as file
            "PARAM_2": 3.0,  # Different from file (2.5)
            # FORCED_PARAM not in FC - should show as difference
        }

        # Test with show_only_differences=True
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=True, gui_complexity="simple")

        # Verify current file is set
        assert parameter_editor_table.current_file == test_file

    def test_multi_file_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test workflow with multiple parameter files."""
        # Test first file
        test_file1 = "01_first_step.param"
        fc_parameters1 = {"PARAM_1": 1.0, "PARAM_2": 2.5}
        parameter_editor_table.repopulate(test_file1, fc_parameters1, show_only_differences=False, gui_complexity="simple")
        assert parameter_editor_table.current_file == test_file1

        # Test second file
        test_file2 = "02_second_step.param"
        fc_parameters2 = {"PARAM_3": 3.14, "PARAM_4": -1.5}
        parameter_editor_table.repopulate(test_file2, fc_parameters2, show_only_differences=False, gui_complexity="simple")
        assert parameter_editor_table.current_file == test_file2


if __name__ == "__main__":
    pytest.main([__file__])
