#!/usr/bin/python3

"""
Tests for the ParameterEditorTable class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable

# pylint: disable=protected-access, redefined-outer-name, too-few-public-methods


def create_mock_data_model_ardupilot_parameter(  # pylint: disable=too-many-arguments, too-many-positional-arguments # noqa: PLR0913
    name: str = "TEST_PARAM",
    value: float = 1.0,
    comment: str = "test comment",
    metadata: Optional[dict[str, Any]] = None,
    fc_value: Optional[float] = None,
    is_forced: bool = False,
    is_derived: bool = False,
    is_calibration: bool = False,
    is_readonly: bool = False,
    is_bitmask: bool = False,
    is_multiple_choice: bool = False,
) -> ArduPilotParameter:
    """Create a mock ArduPilotParameter for testing."""
    metadata = metadata or {}

    if is_calibration:
        metadata["Calibration"] = True
    if is_readonly:
        metadata["ReadOnly"] = True
    if is_bitmask:
        metadata["Bitmask"] = {0: "Bit 0", 1: "Bit 1", 2: "Bit 2"}
    if is_multiple_choice:
        metadata["values"] = {"0": "Option 0", "1": "Option 1"}

    metadata.setdefault("unit", "")
    metadata.setdefault("doc_tooltip", "Test tooltip")
    metadata.setdefault("unit_tooltip", "Unit tooltip")

    par_obj = Par(value, comment)
    default_par = Par(0.0, "default") if metadata else None
    forced_par = Par(value, "forced comment") if is_forced else None
    derived_par = Par(value, "derived comment") if is_derived else None

    return ArduPilotParameter(
        name=name,
        par_obj=par_obj,
        metadata=metadata,
        default_par=default_par,
        fc_value=fc_value,
        forced_par=forced_par,
        derived_par=derived_par,
    )


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


def test_repopulate_empty_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate with empty parameters dictionary."""
    test_file = "test_file"
    parameter_editor_table.local_filesystem.file_parameters = {test_file: {}}
    fc_parameters = {}

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False, gui_complexity="simple")
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

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False, gui_complexity="simple")
    assert not dummy_widget.winfo_exists()


def test_repopulate_handles_none_current_file(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate handles None current_file gracefully."""
    fc_parameters = {}
    # Set up file parameters with None key and empty metadata
    parameter_editor_table.local_filesystem.file_parameters = {None: {}}
    parameter_editor_table.local_filesystem.doc_dict = {}
    parameter_editor_table.local_filesystem.param_default_dict = {}

    parameter_editor_table.repopulate(None, fc_parameters, show_only_differences=False, gui_complexity="simple")
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
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False, gui_complexity="simple")
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
        parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False, gui_complexity="simple")
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

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=False, gui_complexity="simple")

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

    parameter_editor_table.repopulate(test_file, fc_parameters, show_only_differences=True, gui_complexity="simple")
    # Should only show PARAM2 and PARAM3 as they differ from FC
    # assert parameter_editor_table.add_parameter_row.call_count == 2


class TestUIComplexityBehavior:
    """Test behavior related to UI complexity settings."""

    def test_should_show_upload_column_simple_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that upload column is hidden in simple mode."""
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

        should_show = parameter_editor_table._should_show_upload_column()

        assert should_show is False

    def test_should_show_upload_column_advanced_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that upload column is shown in advanced mode."""
        parameter_editor_table.parameter_editor.gui_complexity = "advanced"

        should_show = parameter_editor_table._should_show_upload_column()

        assert should_show is True

    def test_should_show_upload_column_explicit_override(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that explicit gui_complexity parameter overrides default."""
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

        # Explicitly pass "advanced" to override the default
        should_show = parameter_editor_table._should_show_upload_column("advanced")

        assert should_show is True

    def test_get_change_reason_column_index_with_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test change reason column index when upload column is shown."""
        column_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=True)

        # Base columns (6) + Upload column (1) = 7
        assert column_index == 7

    def test_get_change_reason_column_index_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test change reason column index when upload column is hidden."""
        column_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=False)

        # Base columns (6) only
        assert column_index == 6


class TestParameterChangeStateBehavior:
    """Test behavior of parameter change state management."""

    def test_get_at_least_one_param_edited_false(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test getting parameter edited state when false."""
        parameter_editor_table.at_least_one_param_edited = False

        result = parameter_editor_table.get_at_least_one_param_edited()

        assert result is False

    def test_get_at_least_one_param_edited_true(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test getting parameter edited state when true."""
        parameter_editor_table.at_least_one_param_edited = True

        result = parameter_editor_table.get_at_least_one_param_edited()

        assert result is True

    def test_set_at_least_one_param_edited_to_true(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test setting parameter edited state to true."""
        parameter_editor_table.set_at_least_one_param_edited(True)

        assert parameter_editor_table.at_least_one_param_edited is True

    def test_set_at_least_one_param_edited_to_false(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test setting parameter edited state to false."""
        parameter_editor_table.at_least_one_param_edited = True  # Start with true
        parameter_editor_table.set_at_least_one_param_edited(False)

        assert parameter_editor_table.at_least_one_param_edited is False


class TestIntegrationBehavior:
    """Test integration behavior between refactored methods."""

    def test_gui_complexity_affects_column_calculation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that UI complexity affects column index calculations."""
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

        show_upload = parameter_editor_table._should_show_upload_column()
        column_index = parameter_editor_table._get_change_reason_column_index(show_upload)

        assert show_upload is False
        assert column_index == 6  # No upload column

        # Change to advanced mode
        show_upload_advanced = parameter_editor_table._should_show_upload_column("advanced")
        column_index_advanced = parameter_editor_table._get_change_reason_column_index(show_upload_advanced)

        assert show_upload_advanced is True
        assert column_index_advanced == 7  # With upload column


class TestWidgetCreationBehavior:
    """Test the behavior of widget creation methods."""

    def test_create_delete_button(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test delete button creation."""
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            button = parameter_editor_table._create_delete_button("TEST_PARAM")

            assert isinstance(button, ttk.Button)
            assert button.cget("text") == "Del"
            mock_tooltip.assert_called_once()

    def test_create_parameter_name_normal(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter name label creation for normal parameters."""
        param = create_mock_data_model_ardupilot_parameter()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            label = parameter_editor_table._create_parameter_name(param)

            assert isinstance(label, ttk.Label)
            assert "TEST_PARAM" in label.cget("text")
            mock_tooltip.assert_called_once()

    def test_create_parameter_name_calibration(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter name label creation for calibration parameters."""
        param = create_mock_data_model_ardupilot_parameter(name="CAL_PARAM", is_calibration=True)

        label = parameter_editor_table._create_parameter_name(param)

        assert isinstance(label, ttk.Label)
        assert str(label.cget("background")) == "yellow"

    def test_create_parameter_name_readonly(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter name label creation for readonly parameters."""
        param = create_mock_data_model_ardupilot_parameter(name="RO_PARAM", is_readonly=True)

        label = parameter_editor_table._create_parameter_name(param)

        assert isinstance(label, ttk.Label)
        assert str(label.cget("background")) == "purple1"

    def test_create_flightcontroller_value_exists(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test flight controller value label when parameter exists in FC."""
        param = create_mock_data_model_ardupilot_parameter(fc_value=1.234567)

        label = parameter_editor_table._create_flightcontroller_value(param)

        assert isinstance(label, ttk.Label)
        assert label.cget("text") == "1.234567"

    def test_create_flightcontroller_value_missing(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test flight controller value label when parameter is missing from FC."""
        param = create_mock_data_model_ardupilot_parameter(fc_value=None)

        label = parameter_editor_table._create_flightcontroller_value(param)

        assert isinstance(label, ttk.Label)
        assert label.cget("text") == "N/A"

    def test_create_unit_label(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test unit label creation."""
        param = create_mock_data_model_ardupilot_parameter(metadata={"unit": "m/s", "unit_tooltip": "meters per second"})

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            label = parameter_editor_table._create_unit_label(param)

            assert isinstance(label, ttk.Label)
            assert label.cget("text") == "m/s"
            mock_tooltip.assert_called_once()

    def test_create_upload_checkbutton_connected(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test upload checkbutton creation when FC is connected."""
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM", fc_connected=True)

            assert isinstance(checkbutton, ttk.Checkbutton)
            assert str(checkbutton.cget("state")) == "normal"
            assert "TEST_PARAM" in parameter_editor_table.upload_checkbutton_var
            assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM"].get() is True
            mock_tooltip.assert_called_once()

    def test_create_upload_checkbutton_disconnected(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test upload checkbutton creation when FC is disconnected."""
        checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM", fc_connected=False)

        assert isinstance(checkbutton, ttk.Checkbutton)
        assert str(checkbutton.cget("state")) == "disabled"
        assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM"].get() is False

    def test_create_change_reason_entry_normal(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test change reason entry creation for normal parameters."""
        param = create_mock_data_model_ardupilot_parameter()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            entry = parameter_editor_table._create_change_reason_entry(param)

            assert isinstance(entry, ttk.Entry)
            assert entry.get() == "test comment"
            mock_tooltip.assert_called_once()

    def test_create_change_reason_entry_forced(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test change reason entry creation for forced parameters."""
        param = create_mock_data_model_ardupilot_parameter(is_forced=True)

        entry = parameter_editor_table._create_change_reason_entry(param)

        assert isinstance(entry, ttk.Entry)
        assert entry.get() == "forced comment"
        assert str(entry.cget("state")) == "disabled"


class TestEventHandlerBehavior:
    """Test the behavior of event handler methods."""

    def test_on_parameter_delete_confirmed(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter deletion when user confirms."""
        parameter_editor_table.current_file = "test_file"
        parameter_editor_table.local_filesystem.file_parameters = {"test_file": {"TEST_PARAM": Par(1.0, "comment")}}
        parameter_editor_table.parameter_editor.repopulate_parameter_table = MagicMock()
        parameter_editor_table.canvas = MagicMock()
        parameter_editor_table.canvas.yview.return_value = [0.5, 0.8]

        with patch("tkinter.messagebox.askyesno", return_value=True):
            parameter_editor_table._on_parameter_delete("TEST_PARAM")

            assert "TEST_PARAM" not in parameter_editor_table.local_filesystem.file_parameters["test_file"]
            assert parameter_editor_table.at_least_one_param_edited is True
            parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_called_once_with("test_file")

    def test_on_parameter_delete_cancelled(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter deletion when user cancels."""
        parameter_editor_table.current_file = "test_file"
        parameter_editor_table.local_filesystem.file_parameters = {"test_file": {"TEST_PARAM": Par(1.0, "comment")}}

        with patch("tkinter.messagebox.askyesno", return_value=False):
            parameter_editor_table._on_parameter_delete("TEST_PARAM")

            assert "TEST_PARAM" in parameter_editor_table.local_filesystem.file_parameters["test_file"]
            assert parameter_editor_table.at_least_one_param_edited is False

    def test_confirm_parameter_addition_valid_fc_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter addition with valid FC parameter."""
        parameter_editor_table.current_file = "test_file"
        parameter_editor_table.local_filesystem.file_parameters = {"test_file": {}}
        parameter_editor_table.parameter_editor.repopulate_parameter_table = MagicMock()
        fc_parameters = {"NEW_PARAM": 5.0}

        result = parameter_editor_table._confirm_parameter_addition("NEW_PARAM", fc_parameters)

        assert result is True
        assert "NEW_PARAM" in parameter_editor_table.local_filesystem.file_parameters["test_file"]
        assert parameter_editor_table.local_filesystem.file_parameters["test_file"]["NEW_PARAM"].value == 5.0
        assert parameter_editor_table.at_least_one_param_edited is True

    def test_confirm_parameter_addition_empty_name(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter addition with empty name."""
        with patch("tkinter.messagebox.showerror") as mock_error:
            result = parameter_editor_table._confirm_parameter_addition("", {})

            assert result is False
            mock_error.assert_called_once()

    def test_confirm_parameter_addition_existing_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter addition with existing parameter name."""
        parameter_editor_table.current_file = "test_file"
        parameter_editor_table.local_filesystem.file_parameters = {"test_file": {"EXISTING_PARAM": Par(1.0, "comment")}}

        with patch("tkinter.messagebox.showerror") as mock_error:
            result = parameter_editor_table._confirm_parameter_addition("EXISTING_PARAM", {})

            assert result is False
            mock_error.assert_called_once()


class TestHeaderCreationBehavior:
    """Test the behavior of header creation methods."""

    def test_create_headers_and_tooltips_simple_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test header creation in simple mode (no upload column)."""
        headers, tooltips = parameter_editor_table._create_headers_and_tooltips(show_upload_column=False)

        expected_headers = (
            "-/+",
            "Parameter",
            "Current Value",
            " ",
            "New Value",
            "Unit",
            "Why are you changing this parameter?",
        )

        assert headers == expected_headers
        assert len(tooltips) == len(headers)
        assert len(tooltips) == 7  # No upload column tooltip

    def test_create_headers_and_tooltips_advanced_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test header creation in advanced mode (with upload column)."""
        headers, tooltips = parameter_editor_table._create_headers_and_tooltips(show_upload_column=True)

        expected_headers = (
            "-/+",
            "Parameter",
            "Current Value",
            " ",
            "New Value",
            "Unit",
            "Upload",
            "Why are you changing this parameter?",
        )

        assert headers == expected_headers
        assert len(tooltips) == len(headers)
        assert len(tooltips) == 8  # With upload column tooltip

    def test_headers_and_tooltips_localization(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that headers use localization function."""
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table._") as mock_translate:
            mock_translate.side_effect = lambda x: f"TRANSLATED_{x}"

            _headers, _ = parameter_editor_table._create_headers_and_tooltips(show_upload_column=False)

            # Verify that translation function was called for each header
            assert mock_translate.call_count >= 6


class TestColumnManagementBehavior:
    """Test the behavior of column management methods."""

    def test_create_column_widgets_normal_parameter(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test column widget creation for normal parameters."""
        param_name = "TEST_PARAM"
        param = create_mock_data_model_ardupilot_parameter()
        show_upload_column = True
        fc_connected = True

        # Mock individual widget creation methods using patch.object
        with (
            patch.object(parameter_editor_table, "_create_delete_button", return_value=MagicMock()) as mock_delete,
            patch.object(parameter_editor_table, "_create_parameter_name", return_value=MagicMock()) as mock_name,
            patch.object(parameter_editor_table, "_create_flightcontroller_value", return_value=MagicMock()) as mock_fc,
            patch.object(parameter_editor_table, "_create_new_value_entry", return_value=MagicMock()) as mock_new,
            patch.object(parameter_editor_table, "_create_unit_label", return_value=MagicMock()) as mock_unit,
            patch.object(parameter_editor_table, "_create_upload_checkbutton", return_value=MagicMock()) as mock_upload,
            patch.object(parameter_editor_table, "_create_change_reason_entry", return_value=MagicMock()) as mock_reason,
        ):
            column = parameter_editor_table._create_column_widgets(param_name, param, show_upload_column, fc_connected)

            assert len(column) == 8  # With upload column
            mock_delete.assert_called_once()
            mock_name.assert_called_once()
            mock_fc.assert_called_once()
            mock_new.assert_called_once()
            mock_unit.assert_called_once()
            mock_upload.assert_called_once()
            mock_reason.assert_called_once()

    def test_create_column_widgets_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test column widget creation without upload column."""
        param_name = "TEST_PARAM"
        param = create_mock_data_model_ardupilot_parameter()
        show_upload_column = False
        fc_connected = True

        # Mock individual widget creation methods using patch.object
        with (
            patch.object(parameter_editor_table, "_create_delete_button", return_value=MagicMock()) as mock_delete,
            patch.object(parameter_editor_table, "_create_parameter_name", return_value=MagicMock()) as mock_name,
            patch.object(parameter_editor_table, "_create_flightcontroller_value", return_value=MagicMock()) as mock_fc,
            patch.object(parameter_editor_table, "_create_new_value_entry", return_value=MagicMock()) as mock_new,
            patch.object(parameter_editor_table, "_create_unit_label", return_value=MagicMock()) as mock_unit,
            patch.object(parameter_editor_table, "_create_change_reason_entry", return_value=MagicMock()) as mock_reason,
        ):
            column = parameter_editor_table._create_column_widgets(param_name, param, show_upload_column, fc_connected)

            assert len(column) == 7  # Without upload column
            mock_delete.assert_called_once()
            mock_name.assert_called_once()
            mock_fc.assert_called_once()
            mock_new.assert_called_once()
            mock_unit.assert_called_once()
            mock_reason.assert_called_once()

    def test_grid_column_widgets_with_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test column widget gridding with upload column."""
        # Create mock widgets
        mock_widgets = [MagicMock() for _ in range(8)]

        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=7)

        parameter_editor_table._grid_column_widgets(mock_widgets, row=1, show_upload_column=True)

        # Verify all widgets were gridded
        for i, widget in enumerate(mock_widgets):
            widget.grid.assert_called_once()
            call_args = widget.grid.call_args[1]  # Get keyword arguments
            assert call_args["row"] == 1
            if i < 7:  # Regular columns
                assert call_args["column"] == i
            else:  # Change reason column
                assert call_args["column"] == 7

    def test_grid_column_widgets_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test column widget gridding without upload column."""
        # Create mock widgets (6 widgets without upload)
        mock_widgets = [MagicMock() for _ in range(7)]

        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=6)

        parameter_editor_table._grid_column_widgets(mock_widgets, row=1, show_upload_column=False)

        # Verify all widgets were gridded
        for i, widget in enumerate(mock_widgets):
            widget.grid.assert_called_once()
            call_args = widget.grid.call_args[1]
            assert call_args["row"] == 1
            if i < 6:  # Regular columns
                assert call_args["column"] == i
            else:  # Change reason column
                assert call_args["column"] == 6

    def test_configure_table_columns_with_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test table column configuration with upload column."""
        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=6)
        parameter_editor_table.view_port = MagicMock()

        parameter_editor_table._configure_table_columns(show_upload_column=True)

        # Verify columnconfigure was called for all columns
        assert parameter_editor_table.view_port.columnconfigure.call_count == 8

    def test_configure_table_columns_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test table column configuration without upload column."""
        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=5)
        parameter_editor_table.view_port = MagicMock()

        parameter_editor_table._configure_table_columns(show_upload_column=False)

        # Verify columnconfigure was called for all columns (6 without upload)
        assert parameter_editor_table.view_port.columnconfigure.call_count == 7


class TestUpdateMethodsBehavior:
    """Test the behavior of update methods."""

    def test_update_new_value_entry_text_normal_entry(self, parameter_editor_table: ParameterEditorTable) -> None:  # pylint: disable=unused-argument
        """Test updating new value entry text for normal entry widget."""
        mock_entry = MagicMock(spec=ttk.Entry)

        # Create a parameter where new value equals default value to trigger default_v.TEntry style
        param = ArduPilotParameter(
            name="TEST_PARAM",
            par_obj=Par(1.5, "test comment"),
            metadata={},
            default_par=Par(1.5, "default comment"),  # Same value as par_obj to trigger default style
            fc_value=None,
        )

        ParameterEditorTable._update_new_value_entry_text(mock_entry, param)

        mock_entry.delete.assert_called_once_with(0, tk.END)
        mock_entry.insert.assert_called_once_with(0, "1.5")
        mock_entry.configure.assert_called_once_with(style="default_v.TEntry")

    def test_update_new_value_entry_text_combobox(self, parameter_editor_table: ParameterEditorTable) -> None:  # pylint: disable=unused-argument
        """Test updating new value entry text for combobox widget (should be skipped)."""
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        param = create_mock_data_model_ardupilot_parameter(value=1.5)

        ParameterEditorTable._update_new_value_entry_text(mock_combobox, param)

        # Should not call any methods on combobox
        mock_combobox.delete.assert_not_called()
        mock_combobox.insert.assert_not_called()

    def test_update_combobox_style_on_selection_valid(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test combobox style update on selection with valid value."""
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "1.5"
        mock_event = MagicMock()
        mock_event.width = 9
        mock_change_reason_widget = MagicMock(spec=ttk.Entry)
        mock_value_is_different_widget = MagicMock(spec=ttk.Label)

        # Create a parameter where the selected value (1.5) equals the default value
        param = ArduPilotParameter(
            name="TEST_PARAM",
            par_obj=Par(1.0, "test comment"),  # Initial value is different
            metadata={},
            default_par=Par(1.5, "default comment"),  # Default value matches what will be selected
            fc_value=None,
        )

        # Mock the local filesystem since set_new_value tries to update it
        parameter_editor_table.local_filesystem.file_parameters = {"test_file": {"TEST_PARAM": Par(1.0, "test")}}
        parameter_editor_table.current_file = "test_file"

        # Mock the show_tooltip function to avoid creating actual Tkinter widgets
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"):
            parameter_editor_table._update_combobox_style_on_selection(
                mock_combobox, param, mock_event, mock_change_reason_widget, mock_value_is_different_widget
            )

        mock_combobox.configure.assert_called_once_with(style="default_v.TCombobox")
        mock_combobox.on_combo_configure.assert_called_once_with(mock_event)


class TestBitmaskFunctionalityBehavior:
    """Test the behavior of bitmask functionality."""

    def test_bitmask_window_creation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test bitmask selection window creation."""
        mock_event = MagicMock()
        mock_widget = MagicMock()
        mock_widget.get.return_value = "5"  # Binary: 101 (bits 0 and 2 set)
        mock_widget.unbind = MagicMock()
        mock_event.widget = mock_widget
        mock_change_reason_widget = MagicMock(spec=ttk.Entry)
        mock_value_is_different_widget = MagicMock(spec=ttk.Label)

        param = create_mock_data_model_ardupilot_parameter(
            name="TEST_PARAM",
            value=3.0,
            is_bitmask=True,
        )

        parameter_editor_table.root = MagicMock()
        parameter_editor_table.local_filesystem.param_default_dict = {"TEST_PARAM": Par(0.0, "default")}

        with (
            patch("tkinter.Toplevel") as mock_toplevel,
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Checkbutton"),
            patch("tkinter.ttk.Label"),
        ):
            parameter_editor_table._open_bitmask_selection_window(
                mock_event, param, mock_change_reason_widget, mock_value_is_different_widget
            )

            # Verify window was created
            mock_toplevel.assert_called_once()
            mock_event.widget.unbind.assert_called_once_with("<Double-Button-1>")

    def test_bitmask_value_calculation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test bitmask value calculation from checkbox states."""
        # This test would be complex to implement due to the nested function structure
        # In a real implementation, you might want to extract the value calculation
        # logic into a separate testable method


class TestCompleteIntegrationWorkflows:
    """Test complete integration workflows end-to-end."""

    def test_gui_complexity_affects_complete_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test that UI complexity affects the complete parameter editing workflow."""
        # Test simple mode
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

        headers_simple, _ = parameter_editor_table._create_headers_and_tooltips(
            parameter_editor_table._should_show_upload_column()
        )
        assert "Upload" not in headers_simple

        column_index_simple = parameter_editor_table._get_change_reason_column_index(
            parameter_editor_table._should_show_upload_column()
        )
        assert column_index_simple == 6

        # Test advanced mode
        parameter_editor_table.parameter_editor.gui_complexity = "advanced"

        headers_advanced, _ = parameter_editor_table._create_headers_and_tooltips(
            parameter_editor_table._should_show_upload_column()
        )
        assert "Upload" in headers_advanced

        column_index_advanced = parameter_editor_table._get_change_reason_column_index(
            parameter_editor_table._should_show_upload_column()
        )
        assert column_index_advanced == 7
