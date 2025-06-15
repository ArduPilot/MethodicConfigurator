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


class TestCompleteParameterWorkflows:
    """Test complete parameter editing workflows from start to finish."""

    def test_parameter_validation_and_update_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete parameter validation and update workflow."""
        parameter_editor_table.current_file = "01_first_step.param"

        # Create a mock parameter value change event
        mock_entry = MagicMock(spec=ttk.Entry)
        mock_entry.get.return_value = "2.5"

        mock_event = MagicMock()
        mock_event.widget = mock_entry

        # Mock the static method for updating entry text
        with patch.object(parameter_editor_table, "_update_new_value_entry_text"):
            # Test the complete workflow
            parameter_editor_table._on_parameter_value_change(mock_event, "01_first_step.param", "PARAM_1")

            # Verify the parameter was updated
            assert parameter_editor_table.local_filesystem.file_parameters["01_first_step.param"]["PARAM_1"].value == 2.5
            assert parameter_editor_table.at_least_one_param_edited is True

    def test_parameter_bounds_validation_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter bounds validation in a complete workflow."""
        parameter_editor_table.current_file = "01_first_step.param"

        # Test value within bounds
        is_valid, value = parameter_editor_table._validate_parameter_value_format("5.0", "PARAM_1")
        assert is_valid is True
        assert value == 5.0

        # Test bounds validation - should be valid as 5.0 is within [0.0, 10.0]
        bounds_valid = parameter_editor_table._validate_parameter_bounds(value, "PARAM_1")
        assert bounds_valid is True

        # Test value outside bounds with user rejection
        with patch("tkinter.messagebox.askyesno", return_value=False):
            bounds_valid = parameter_editor_table._validate_parameter_bounds(15.0, "PARAM_1")
            assert bounds_valid is False

    def test_forced_parameter_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test workflow with forced parameters that cannot be edited."""
        parameter_editor_table.current_file = "01_first_step.param"

        # Test forced parameter detection
        is_forced, param_type = parameter_editor_table._is_forced_or_derived_parameter("FORCED_PARAM")
        assert is_forced is True
        assert param_type == "forced"

        # Test that forced parameters have disabled change reason entries
        param = Par(1.0, "original comment")
        mock_entry = MagicMock(spec=ttk.Entry)
        mock_entry.get.return_value = "5.0"

        change_reason_entry = parameter_editor_table._create_change_reason_entry("FORCED_PARAM", param, mock_entry)

        assert isinstance(change_reason_entry, ttk.Entry)
        assert str(change_reason_entry.cget("state")) == "disabled"
        assert str(change_reason_entry.cget("background")) == "light grey"

    def test_derived_parameter_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test workflow with derived parameters."""
        parameter_editor_table.current_file = "01_first_step.param"

        # Test derived parameter detection
        is_derived, param_type = parameter_editor_table._is_forced_or_derived_parameter("DERIVED_PARAM")
        assert is_derived is True
        assert param_type == "derived"

    def test_gui_complexity_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete UI complexity workflow affecting column layout."""
        # Test advanced mode (default)
        assert parameter_editor_table._should_show_upload_column() is True
        assert parameter_editor_table._get_change_reason_column_index(show_upload_column=True) == 6

        # Test simple mode
        parameter_editor_table.parameter_editor.gui_complexity = "simple"
        assert parameter_editor_table._should_show_upload_column() is False
        assert parameter_editor_table._get_change_reason_column_index(show_upload_column=False) == 5

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
        param = Par(1.5, "Test parameter")
        param_metadata = parameter_editor_table.local_filesystem.doc_dict["PARAM_1"]
        param_default = parameter_editor_table.local_filesystem.param_default_dict["PARAM_1"]
        doc_tooltip = "Test tooltip"
        fc_parameters = {"PARAM_1": 1.5}
        show_upload_column = True

        # Mock widget creation methods to return real widgets
        with patch.object(parameter_editor_table, "_create_new_value_entry") as mock_new_value:
            mock_new_value.return_value = ttk.Entry(parameter_editor_table.view_port)

            column = parameter_editor_table._create_column_widgets(
                param_name, param, param_metadata, param_default, doc_tooltip, fc_parameters, show_upload_column
            )

            # Should create 7 widgets (including upload column)
            assert len(column) == 7

            # Verify all widgets are created
            assert all(widget is not None for widget in column)

    def test_widget_creation_different_parameter_types(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test widget creation for different parameter types."""
        # Test calibration parameter
        param_metadata = {"Calibration": True}
        label = parameter_editor_table._create_parameter_name("CAL_PARAM", param_metadata, "tooltip")
        assert isinstance(label, ttk.Label)
        assert str(label.cget("background")) == "yellow"

        # Test readonly parameter
        param_metadata = {"ReadOnly": True}
        label = parameter_editor_table._create_parameter_name("RO_PARAM", param_metadata, "tooltip")
        assert isinstance(label, ttk.Label)
        assert str(label.cget("background")) == "red"

        # Test normal parameter
        param_metadata = {}
        label = parameter_editor_table._create_parameter_name("NORMAL_PARAM", param_metadata, "tooltip")
        assert isinstance(label, ttk.Label)

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
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False)

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
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=True)

        # Verify current file is set
        assert parameter_editor_table.current_file == test_file

    def test_multi_file_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test workflow with multiple parameter files."""
        # Test first file
        test_file1 = "01_first_step.param"
        fc_parameters1 = {"PARAM_1": 1.0, "PARAM_2": 2.5}
        parameter_editor_table.repopulate(test_file1, fc_parameters1, show_only_differences=False)
        assert parameter_editor_table.current_file == test_file1

        # Test second file
        test_file2 = "02_second_step.param"
        fc_parameters2 = {"PARAM_3": 3.14, "PARAM_4": -1.5}
        parameter_editor_table.repopulate(test_file2, fc_parameters2, show_only_differences=False)
        assert parameter_editor_table.current_file == test_file2


class TestValidationIntegration:
    """Test validation workflows in realistic scenarios."""

    def test_complete_validation_chain(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete validation chain from format to bounds to tolerance."""
        # Test valid input
        is_valid, value = parameter_editor_table._validate_parameter_value_format("5.0", "PARAM_1")
        assert is_valid is True
        assert value == 5.0

        bounds_valid = parameter_editor_table._validate_parameter_bounds(value, "PARAM_1")
        assert bounds_valid is True

        # Test tolerance checking
        with patch("ardupilot_methodic_configurator.backend_filesystem.is_within_tolerance", return_value=False):
            changed = parameter_editor_table._check_parameter_value_changed(1.0, value)
            assert changed is True

    def test_validation_error_handling(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test validation error handling workflows."""
        # Test invalid format
        with patch("tkinter.messagebox.showerror") as mock_error:
            is_valid, value = parameter_editor_table._validate_parameter_value_format("invalid", "PARAM_1")
            assert is_valid is False
            assert str(value) == "nan"
            mock_error.assert_called_once()

        # Test infinity rejection
        with patch("tkinter.messagebox.showerror") as mock_error:
            is_valid, value = parameter_editor_table._validate_parameter_value_format("inf", "PARAM_1")
            assert is_valid is False
            assert str(value) == "nan"
            mock_error.assert_called_once()

        # Test NaN rejection
        with patch("tkinter.messagebox.showerror") as mock_error:
            is_valid, value = parameter_editor_table._validate_parameter_value_format("nan", "PARAM_1")
            assert is_valid is False
            assert str(value) == "nan"
            mock_error.assert_called_once()

    def test_bounds_validation_edge_cases(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test bounds validation edge cases."""
        # Test exactly at minimum bound
        bounds_valid = parameter_editor_table._validate_parameter_bounds(0.0, "PARAM_1")
        assert bounds_valid is True

        # Test exactly at maximum bound
        bounds_valid = parameter_editor_table._validate_parameter_bounds(10.0, "PARAM_1")
        assert bounds_valid is True

        # Test slightly below minimum with user acceptance
        with patch("tkinter.messagebox.askyesno", return_value=True):
            bounds_valid = parameter_editor_table._validate_parameter_bounds(-0.1, "PARAM_1")
            assert bounds_valid is True

        # Test slightly above maximum with user rejection
        with patch("tkinter.messagebox.askyesno", return_value=False):
            bounds_valid = parameter_editor_table._validate_parameter_bounds(10.1, "PARAM_1")
            assert bounds_valid is False


class TestErrorRecoveryIntegration:
    """Test error recovery and resilience workflows."""

    def test_widget_finding_with_exceptions(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test widget finding with grid_info exceptions."""
        # Create mock widgets that raise TclError
        mock_entry = MagicMock(spec=ttk.Entry)
        mock_entry.grid_info.side_effect = tk.TclError("Widget not gridded")

        mock_label = MagicMock(spec=ttk.Label)
        mock_label.grid_info.return_value = {"column": 1, "row": 1}
        mock_label.cget.return_value = "TEST_PARAM"

        with patch.object(parameter_editor_table.view_port, "winfo_children", return_value=[mock_entry, mock_label]):
            widget = parameter_editor_table._find_change_reason_widget_by_parameter("TEST_PARAM")

            # Should handle the exception gracefully and return None
            assert widget is None

    def test_state_recovery_after_errors(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test state recovery after validation errors."""
        parameter_editor_table.current_file = "01_first_step.param"
        original_state = parameter_editor_table.at_least_one_param_edited

        # Simulate validation error that should not change state
        with patch("tkinter.messagebox.showerror"):
            is_valid, _ = parameter_editor_table._validate_parameter_value_format("invalid", "PARAM_1")
            assert is_valid is False

        # State should remain unchanged
        assert parameter_editor_table.at_least_one_param_edited == original_state

    def test_missing_metadata_handling(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test handling of missing parameter metadata."""
        # Test parameter not in doc_dict
        min_val, max_val = parameter_editor_table._get_parameter_validation_bounds("UNKNOWN_PARAM")
        assert min_val is None
        assert max_val is None

        # Should not crash when validating unknown parameter
        bounds_valid = parameter_editor_table._validate_parameter_bounds(5.0, "UNKNOWN_PARAM")
        assert bounds_valid is True  # No bounds means always valid


class TestPerformanceIntegration:
    """Test performance-related integration scenarios."""

    def test_large_parameter_set_handling(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test handling of large parameter sets."""
        # Create a large parameter set
        large_param_set = {}
        for i in range(100):
            param_name = f"PARAM_{i:03d}"
            large_param_set[param_name] = Par(float(i), f"Parameter {i}")

        parameter_editor_table.local_filesystem.file_parameters["large_file.param"] = large_param_set

        # Add corresponding metadata
        for i in range(100):
            param_name = f"PARAM_{i:03d}"
            parameter_editor_table.local_filesystem.doc_dict[param_name] = {"Description": f"Parameter {i}", "units": "units"}
            parameter_editor_table.local_filesystem.param_default_dict[param_name] = Par(0.0, "default")

        # Test repopulation with large set
        fc_parameters = {f"PARAM_{i:03d}": float(i) for i in range(100)}
        parameter_editor_table.repopulate("large_file.param", fc_parameters, show_only_differences=False)

        assert parameter_editor_table.current_file == "large_file.param"

    def test_rapid_parameter_changes(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test rapid consecutive parameter changes."""
        parameter_editor_table.current_file = "01_first_step.param"

        # Simulate rapid parameter changes
        for i in range(10):
            is_valid, value = parameter_editor_table._validate_parameter_value_format(str(float(i)), "PARAM_1")
            assert is_valid is True
            assert value == float(i)

            bounds_valid = parameter_editor_table._validate_parameter_bounds(value, "PARAM_1")
            assert bounds_valid is True

            with patch("ardupilot_methodic_configurator.backend_filesystem.is_within_tolerance", return_value=False):
                changed = parameter_editor_table._check_parameter_value_changed(0.0, value)
                if i > 0:  # Skip first iteration where value == 0
                    assert changed is True


class TestUIStateIntegration:
    """Test UI state management integration."""

    def test_upload_checkbutton_state_persistence(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that upload checkbutton states persist across operations."""
        # Create initial checkbutton states
        param1_var = tk.BooleanVar(value=True)
        param2_var = tk.BooleanVar(value=False)
        parameter_editor_table.upload_checkbutton_var = {"PARAM_1": param1_var, "PARAM_2": param2_var}

        # Verify initial states
        assert parameter_editor_table.upload_checkbutton_var["PARAM_1"].get() is True
        assert parameter_editor_table.upload_checkbutton_var["PARAM_2"].get() is False

        # Simulate some operations that should preserve state
        parameter_editor_table.at_least_one_param_edited = True
        parameter_editor_table._update_parameter_change_state(changed=True, param_name="PARAM_1")

        # States should remain unchanged
        assert parameter_editor_table.upload_checkbutton_var["PARAM_1"].get() is True
        assert parameter_editor_table.upload_checkbutton_var["PARAM_2"].get() is False

    def test_parameter_change_state_transitions(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter change state transitions."""
        # Start with no changes
        parameter_editor_table.at_least_one_param_edited = False

        # First change should set flag and log
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.logging_debug") as mock_log:
            parameter_editor_table._update_parameter_change_state(changed=True, param_name="PARAM_1")
            assert parameter_editor_table.at_least_one_param_edited is True
            mock_log.assert_called_once()

        # Subsequent changes should not log again
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.logging_debug") as mock_log:
            parameter_editor_table._update_parameter_change_state(changed=True, param_name="PARAM_2")
            assert parameter_editor_table.at_least_one_param_edited is True
            mock_log.assert_not_called()

        # No change should not affect state
        original_state = parameter_editor_table.at_least_one_param_edited
        parameter_editor_table._update_parameter_change_state(changed=False, param_name="PARAM_3")
        assert parameter_editor_table.at_least_one_param_edited == original_state


if __name__ == "__main__":
    pytest.main([__file__])
