#!/usr/bin/env python3

"""
Integration tests for the ParameterEditorTable class.

These tests focus on end-to-end workflows and realistic usage scenarios,
testing the interaction between multiple components and methods.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager, InvalidParameterNameError
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
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
            "FORCED_PARAM": Par(5.0, "Forced value - cannot be changed"),
            "DERIVED_PARAM": Par(800.0, "Derived from battery capacity"),
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
    # Create a mock flight controller with proper FC parameters that can be updated by tests
    mock_flight_controller = MagicMock()
    # Use a dict that tests can modify directly
    fc_params_dict = {}
    mock_flight_controller.fc_parameters = fc_params_dict
    # Create a ConfigurationManager with the mock filesystem
    config_manager = ConfigurationManager(
        current_file="01_first_step.param", flight_controller=mock_flight_controller, filesystem=mock_local_filesystem
    )
    with patch("tkinter.ttk.Style") as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = "white"  # Return valid color instead of memory address

        table = ParameterEditorTable(mock_root, config_manager, mock_parameter_editor)

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
        config_manager = parameter_editor_table.configuration_manager
        config_manager.current_file = "01_first_step.param"
        # Simulate FC parameter available
        config_manager.flight_controller.fc_parameters = {"NEW_PARAM": 42.0}

        # Test successful parameter addition using ConfigurationManager
        result = config_manager.add_parameter_to_current_file("NEW_PARAM")

        assert result is True
        assert "NEW_PARAM" in config_manager.get_parameters_as_par_dict()
        assert config_manager.get_parameters_as_par_dict()["NEW_PARAM"].value == 42.0

    def test_parameter_addition_validation_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter addition validation workflow."""
        config_manager = parameter_editor_table.configuration_manager
        config_manager.current_file = "01_first_step.param"

        # Test empty parameter name
        with pytest.raises(InvalidParameterNameError):
            config_manager.add_parameter_to_current_file("")

        # Test existing parameter name
        # PARAM_1 already exists in the file from fixture
        # Try to add it again - should fail
        with pytest.raises(InvalidParameterNameError):
            config_manager.add_parameter_to_current_file("PARAM_1")

    def test_parameter_deletion_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete parameter deletion workflow."""
        config_manager = parameter_editor_table.configuration_manager
        config_manager.current_file = "01_first_step.param"
        parameter_editor_table.canvas.yview.return_value = [0.5, 0.8]

        # Populate the domain model from file parameters
        config_manager.repopulate_configuration_step_parameters()

        # Simulate that the file was just loaded (no unsaved changes yet)
        # Repopulate creates fresh parameters that are not dirty

        # Initially no changes
        assert not config_manager.has_unsaved_changes()

        # Test confirmed deletion - PARAM_1 already exists in file from fixture
        with patch("tkinter.messagebox.askyesno", return_value=True):
            parameter_editor_table._on_parameter_delete("PARAM_1")

            assert "PARAM_1" not in config_manager.get_parameters_as_par_dict()
            # Deletion should mark file as having changes
            assert config_manager.has_unsaved_changes()
            parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_called_once_with()

        # Reset for next test - PARAM_2 also already exists in file from fixture
        parameter_editor_table.parameter_editor.repopulate_parameter_table.reset_mock()

        # Test cancelled deletion
        with patch("tkinter.messagebox.askyesno", return_value=False):
            parameter_editor_table._on_parameter_delete("PARAM_2")

            assert "PARAM_2" in config_manager.get_parameters_as_par_dict()
            parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_not_called()

    def test_parameter_addition_marks_as_changed(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that adding a parameter marks the file as having changes."""
        config_manager = parameter_editor_table.configuration_manager

        # Clear the flag manually to start fresh (simulating a just-loaded file)
        config_manager._file_has_changes = False  # pylint: disable=protected-access

        # Verify initially no changes
        if not any(param.is_dirty for param in config_manager.parameters.values()):
            assert not config_manager.has_unsaved_changes()

        # Add a new parameter from flight controller
        fc_params = config_manager.fc_parameters
        if fc_params:
            # Find a parameter that exists in FC but not in current file
            for test_param in fc_params:
                if test_param not in config_manager.get_parameters_as_par_dict():
                    config_manager.add_parameter_to_current_file(test_param)
                    # Adding should mark file as having changes
                    assert config_manager.has_unsaved_changes()
                    break

    def test_add_then_delete_same_parameter_has_no_changes(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that adding and then deleting the same parameter results in no net changes."""
        config_manager = parameter_editor_table.configuration_manager
        config_manager.current_file = "02_second_step.param"

        # Repopulate to get clean state
        config_manager.repopulate_configuration_step_parameters()

        # Verify initially no changes (or save initial state)
        initial_has_changes = config_manager.has_unsaved_changes()

        # Find a parameter to add from FC
        fc_params = config_manager.fc_parameters
        if fc_params:
            # Find a parameter that exists in FC but not in current file
            test_param = None
            for param_name in fc_params:
                if param_name not in config_manager.get_parameters_as_par_dict():
                    test_param = param_name
                    break

            if test_param:
                # Add the parameter
                config_manager.add_parameter_to_current_file(test_param)
                # Should have changes now
                assert config_manager.has_unsaved_changes()

                # Delete the same parameter
                config_manager.delete_parameter_from_current_file(test_param)

                # Should be back to initial state (no net changes)
                assert config_manager.has_unsaved_changes() == initial_has_changes


class TestWidgetCreationIntegration:
    """Test widget creation in realistic scenarios."""

    def test_complete_widget_creation_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test creating a complete set of widgets for a parameter row."""
        param_name = "PARAM_1"
        param_metadata = parameter_editor_table.configuration_manager.filesystem.doc_dict["PARAM_1"]
        param = ArduPilotParameter(
            param_name,
            Par(1.5, "Test parameter"),
            metadata=param_metadata,
            default_par=Par(1.6, "Test parameter"),
            fc_value=1.5,
        )
        show_upload_column = True

        # Mock widget creation methods to return real widgets
        with patch.object(parameter_editor_table, "_create_new_value_entry") as mock_new_value:
            mock_new_value.return_value = ttk.Entry(parameter_editor_table.view_port)

            column = parameter_editor_table._create_column_widgets(param_name, param, show_upload_column)

            # Should create 8 widgets (including upload column)
            assert len(column) == 8

            # Verify all widgets are created
            assert all(widget is not None for widget in column)

    def test_upload_checkbutton_creation_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test upload checkbutton creation in different connection states."""
        # Test connected state
        parameter_editor_table.configuration_manager.flight_controller.master = MagicMock()
        checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM")
        assert isinstance(checkbutton, ttk.Checkbutton)
        assert str(checkbutton.cget("state")) == "normal"
        assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM"].get() is True

        # Test disconnected state
        parameter_editor_table.configuration_manager.flight_controller.master = None
        checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM2")
        assert isinstance(checkbutton, ttk.Checkbutton)
        assert str(checkbutton.cget("state")) == "disabled"
        assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM2"].get() is False


class TestFileOperationsIntegration:
    """Test file operations and parameter management integration."""

    def test_repopulate_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test complete repopulate workflow."""
        test_file = "01_first_step.param"
        fc_parameters = {"PARAM_1": 1.0, "PARAM_2": 2.5, "FORCED_PARAM": 5.0, "DERIVED_PARAM": 800.0}

        # Update flight controller parameters to match test data
        parameter_editor_table.configuration_manager.flight_controller.fc_parameters.update(fc_parameters)

        # Clear existing widgets
        for widget in parameter_editor_table.view_port.winfo_children():
            widget.destroy()

        # Test repopulate
        parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple")

        # Verify current file is set
        assert parameter_editor_table.configuration_manager.current_file == test_file

    def test_show_only_differences_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test show only differences workflow."""
        test_file = "01_first_step.param"
        # FC has different values for some parameters
        fc_parameters = {
            "PARAM_1": 1.0,  # Same as file
            "PARAM_2": 3.0,  # Different from file (2.5)
            # FORCED_PARAM not in FC - should show as difference
        }

        # Update flight controller parameters to match test data
        parameter_editor_table.configuration_manager.flight_controller.fc_parameters.update(fc_parameters)

        # Test with show_only_differences=True
        parameter_editor_table.repopulate(show_only_differences=True, gui_complexity="simple")

        # Verify current file is set
        assert parameter_editor_table.configuration_manager.current_file == test_file

    def test_multi_file_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test workflow with multiple parameter files."""
        # Test first file
        test_file1 = "01_first_step.param"
        fc_parameters1 = {"PARAM_1": 1.0, "PARAM_2": 2.5}
        # Set current file and update flight controller parameters
        parameter_editor_table.configuration_manager.current_file = test_file1
        parameter_editor_table.configuration_manager.flight_controller.fc_parameters.update(fc_parameters1)
        parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple")
        assert parameter_editor_table.configuration_manager.current_file == test_file1

        # Test second file
        test_file2 = "02_second_step.param"
        fc_parameters2 = {"PARAM_3": 3.14, "PARAM_4": -1.5}
        # Set current file and update flight controller parameters
        parameter_editor_table.configuration_manager.current_file = test_file2
        parameter_editor_table.configuration_manager.flight_controller.fc_parameters.clear()
        parameter_editor_table.configuration_manager.flight_controller.fc_parameters.update(fc_parameters2)
        parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple")
        assert parameter_editor_table.configuration_manager.current_file == test_file2


if __name__ == "__main__":
    pytest.main([__file__])
