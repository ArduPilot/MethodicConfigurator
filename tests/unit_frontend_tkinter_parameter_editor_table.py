#!/usr/bin/env python3

"""
Unit tests for the ParameterEditorTable class.

These tests focus on implementation details, internal methods, and widget creation.
For behavior-driven tests focused on user workflows, see test_frontend_tkinter_parameter_editor_table.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from typing import Any, Optional, cast
from unittest.mock import MagicMock, patch

import pytest
from conftest import PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED, PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterEditor,
)
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import (
    PairTupleCombobox,
    setup_combobox_mousewheel_handling,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import (
    NEW_VALUE_DIFFERENT_STR,
    NEW_VALUE_WIDGET_WIDTH,
    ParameterEditorTable,
    ParameterEditorTableDialogs,
)

# pylint: disable=protected-access, redefined-outer-name, too-few-public-methods, too-many-lines


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
    # pylint: disable=duplicate-code
    metadata = metadata or {}

    if is_calibration:
        metadata["Calibration"] = True
    if is_readonly:
        metadata["ReadOnly"] = True
    if is_bitmask:
        metadata["Bitmask"] = {0: "Bit 0", 1: "Bit 1", 2: "Bit 2"}
    if is_multiple_choice:
        metadata["values"] = {"0": "Option 0", "1": "Option 1"}
    # pylint: enable=duplicate-code

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
def mock_parameter_editor_window() -> MagicMock:
    """Create a mock parent window editor."""
    parent_window = MagicMock()
    parent_window.gui_complexity = "simple"
    parent_window.repopulate_parameter_table = MagicMock()
    parent_window.on_skip_click = MagicMock()
    parent_window.root = MagicMock(spec=tk.Tk)
    return parent_window


@pytest.fixture
def table_dialogs() -> ParameterEditorTableDialogs:
    """Provide dialog callbacks that record invocations for assertions."""
    return ParameterEditorTableDialogs(
        show_error=MagicMock(),
        show_info=MagicMock(),
        ask_yes_no=MagicMock(return_value=True),
    )


@pytest.fixture
def parameter_editor_table(
    mock_master: tk.Tk,
    mock_local_filesystem: MagicMock,
    mock_parameter_editor_window: MagicMock,
    table_dialogs: ParameterEditorTableDialogs,
) -> ParameterEditorTable:
    """Create a ParameterEditorTable instance for testing, using ParameterEditor abstraction."""
    with patch("tkinter.ttk.Style") as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = "white"

        # Create a mock ParameterEditor
        mock_param_editor = MagicMock(spec=ParameterEditor)
        mock_param_editor._local_filesystem = mock_local_filesystem
        mock_param_editor.current_file = "test_file"
        mock_param_editor.is_fc_connected = True

        # Set up get_parameters_as_par_dict to return the right parameters
        def get_current_file_parameters() -> ParDict:
            return mock_local_filesystem.file_parameters.get(mock_param_editor.current_file, ParDict())

        mock_param_editor.get_parameters_as_par_dict.return_value = get_current_file_parameters()

        # Mock the _repopulate_configuration_step_parameters method to return the expected tuple
        mock_param_editor._repopulate_configuration_step_parameters.return_value = ([], [])

        # Mock the parameters attribute that gets populated during _repopulate_configuration_step_parameters
        mock_param_editor.current_step_parameters = {}

        # Mock the delete method to actually delete from the _local_filesystem parameters
        def mock_delete_parameter(param_name: str) -> None:
            current_file = mock_param_editor.current_file
            if (
                current_file in mock_local_filesystem.file_parameters
                and param_name in mock_local_filesystem.file_parameters[current_file]
            ):
                del mock_local_filesystem.file_parameters[current_file][param_name]

        mock_param_editor.delete_parameter_from_current_file = MagicMock(side_effect=mock_delete_parameter)

        # Mock _has_unsaved_changes to return False by default
        mock_param_editor._has_unsaved_changes.return_value = False
        mock_param_editor.should_display_bitmask_parameter_editor_usage.return_value = False

        # Create the table instance
        table = ParameterEditorTable(mock_master, mock_param_editor, mock_parameter_editor_window, dialogs=table_dialogs)

        mock_parameter_editor_window.root = mock_master

        # Mock necessary tkinter widgets and methods
        table.add_parameter_row = MagicMock()
        table.view_port = mock_master
        table.canvas = MagicMock()
        table.canvas.yview = MagicMock()
        table.canvas.yview_moveto = MagicMock()

        # Mock grid_slaves to handle widget cleanup
        table.grid_slaves = MagicMock(return_value=[])

        # Initialize variables dict
        table.variables = {}

        # Initialize upload_checkbutton_var dict
        table.upload_checkbutton_var = {}

        return table


def test_init_creates_instance_with_correct_attributes(
    parameter_editor_table, mock_master, mock_local_filesystem, mock_parameter_editor_window
) -> None:
    """Test internal attributes are correctly initialized."""
    assert parameter_editor_table.main_frame == mock_master
    assert parameter_editor_table.parameter_editor._local_filesystem == mock_local_filesystem
    assert parameter_editor_table.parameter_editor_window == mock_parameter_editor_window
    assert parameter_editor_table.parameter_editor.current_file == "test_file"
    assert isinstance(parameter_editor_table.upload_checkbutton_var, dict)
    assert parameter_editor_table.parameter_editor._has_unsaved_changes() is False


def test_user_sees_consistent_visual_styling_across_application(parameter_editor_table: ParameterEditorTable) -> None:
    """Test that styling is applied during initialization."""
    assert parameter_editor_table is not None
    assert parameter_editor_table.main_frame is not None


def test_init_with_style_lookup_failure(mock_master, mock_local_filesystem, mock_parameter_editor_window) -> None:
    """Test initialization handles style lookup failures gracefully."""
    with patch("tkinter.ttk.Style", autospec=True) as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = None

        mock_param_editor = MagicMock(spec=ParameterEditor)
        mock_param_editor._local_filesystem = mock_local_filesystem
        mock_param_editor.current_file = "test_file"
        mock_param_editor.get_parameters_as_par_dict.return_value = {}

        table = ParameterEditorTable(mock_master, mock_param_editor, mock_parameter_editor_window)

        assert table is not None
        mock_style.assert_called()
        style_instance.lookup.assert_called()
        style_instance.configure.assert_called_with("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))


def test_repopulate_empty_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate_table handles empty parameter sets."""
    test_file = "test_file"
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict({test_file: ParDict({})})

    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    parameter_editor_table.add_parameter_row.assert_not_called()


def test_repopulate_clears_existing_content(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate_table clears existing widgets before repopulating."""
    test_file = "test_file"
    dummy_widget = ttk.Label(parameter_editor_table)
    parameter_editor_table.grid_slaves = MagicMock(return_value=[dummy_widget])
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment")})}
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict({"PARAM1": Par(0.0, "default")})

    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    assert not dummy_widget.winfo_exists()


def test_repopulate_handles_none_current_file(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate_table handles missing current file gracefully."""
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict({"": ParDict({})})
    parameter_editor_table.parameter_editor.current_file = ""
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {}
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict({})

    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    parameter_editor_table.add_parameter_row.assert_not_called()


def test_repopulate_single_parameter(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate_table with single parameter."""
    test_file = "test_file"
    parameter_editor_table.parameter_editor.current_file = test_file
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment")})}
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict({"PARAM1": Par(0.0, "default")})

    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")


def test_repopulate_multiple_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate_table with multiple parameters."""
    test_file = "test_file"
    parameter_editor_table.parameter_editor.current_file = test_file
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {
            test_file: ParDict(
                {
                    "PARAM1": Par(1.0, "test comment 1"),
                    "PARAM2": Par(2.0, "test comment 2"),
                    "PARAM3": Par(3.0, "test comment 3"),
                }
            )
        }
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
        {
            "PARAM1": Par(0.0, "default"),
            "PARAM2": Par(0.0, "default"),
            "PARAM3": Par(0.0, "default"),
        }
    )

    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")


def test_repopulate_preserves_checkbutton_states(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate_table preserves upload checkbutton states."""
    test_file = "test_file"
    param1_var = tk.BooleanVar(value=True)
    param2_var = tk.BooleanVar(value=False)
    parameter_editor_table.upload_checkbutton_var = {"PARAM1": param1_var, "PARAM2": param2_var}
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment"), "PARAM2": Par(2.0, "test comment")})}
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
    }
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
        {"PARAM1": Par(0.0, "default"), "PARAM2": Par(0.0, "default")}
    )

    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")


def test_repopulate_show_only_differences(parameter_editor_table: ParameterEditorTable) -> None:
    """Test repopulate_table filtering with show_only_differences."""
    test_file = "test_file"
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {
            test_file: ParDict(
                {
                    "PARAM1": Par(1.0, "test comment"),
                    "PARAM2": Par(2.5, "test comment"),
                    "PARAM3": Par(3.0, "test comment"),
                }
            )
        }
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
        {
            "PARAM1": Par(0.0, "default"),
            "PARAM2": Par(0.0, "default"),
            "PARAM3": Par(0.0, "default"),
        }
    )

    parameter_editor_table.repopulate_table(show_only_differences=True, gui_complexity="simple")


@pytest.mark.parametrize("pending_scroll", [True, False])
def test_repopulate_uses_scroll_helper(parameter_editor_table: ParameterEditorTable, pending_scroll: bool) -> None:
    """Test repopulate_table uses scroll helper correctly."""
    parameter_editor_table._pending_scroll_to_bottom = pending_scroll
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict({"test_file": ParDict({})})
    parameter_editor_table.parameter_editor._repopulate_configuration_step_parameters = MagicMock(return_value=([], []))
    parameter_editor_table._update_table = MagicMock()
    parameter_editor_table.view_port.winfo_children = MagicMock(return_value=[])
    parameter_editor_table._create_headers_and_tooltips = MagicMock(return_value=((), ()))
    parameter_editor_table._should_show_upload_column = MagicMock(return_value=False)

    with patch.object(parameter_editor_table, "_apply_scroll_position") as mock_scroll:
        parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    mock_scroll.assert_called_once_with(pending_scroll)
    assert parameter_editor_table._pending_scroll_to_bottom is False


@pytest.mark.parametrize(
    ("scroll_to_bottom", "expected_position"),
    [(True, 1.0), (False, 0.0)],
)
def test_apply_scroll_position_moves_canvas(
    parameter_editor_table: ParameterEditorTable, scroll_to_bottom: bool, expected_position: float
) -> None:
    """Test _apply_scroll_position moves canvas to correct position."""
    canvas_yview = parameter_editor_table.canvas.yview_moveto
    assert isinstance(canvas_yview, MagicMock)
    canvas_yview.reset_mock()

    with patch.object(parameter_editor_table, "update_idletasks") as mock_update_idletasks:
        parameter_editor_table._apply_scroll_position(scroll_to_bottom)

    mock_update_idletasks.assert_called_once_with()
    canvas_yview.assert_called_once_with(expected_position)


class TestWidgetCreationBehavior:
    """Test widget creation methods for visual indicators."""

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


class TestEventHandlerBehavior:
    """Test event handler methods."""

    def test_on_parameter_delete_confirmed(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter deletion when confirmed."""
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {
            "test_file": ParDict({"TEST_PARAM": Par(1.0, "comment")})
        }
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table = MagicMock()
        parameter_editor_table.canvas = MagicMock()
        parameter_editor_table.canvas.yview.return_value = [0.5, 0.8]

        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = True
        parameter_editor_table._on_parameter_delete("TEST_PARAM")

        assert "TEST_PARAM" not in parameter_editor_table.parameter_editor._local_filesystem.file_parameters["test_file"]
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table.assert_called_once_with()

    def test_on_parameter_delete_cancelled(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter deletion when cancelled."""
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {
            "test_file": {"TEST_PARAM": Par(1.0, "comment")}
        }

        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = False
        parameter_editor_table._on_parameter_delete("TEST_PARAM")

        assert "TEST_PARAM" in parameter_editor_table.parameter_editor._local_filesystem.file_parameters["test_file"]

    def test_confirm_parameter_addition_valid_fc_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test successful parameter addition."""
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {"test_file": ParDict({})}
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table = MagicMock()

        with patch.object(
            parameter_editor_table.parameter_editor,
            "add_parameter_to_current_file",
            return_value=True,
        ):
            result = parameter_editor_table._confirm_parameter_addition("NEW_PARAM")

            assert result is True
            parameter_editor_table.parameter_editor.add_parameter_to_current_file.assert_called_once_with("NEW_PARAM")

    def test_confirm_parameter_addition_empty_name(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter addition with empty name."""
        parameter_editor_table.parameter_editor.add_parameter_to_current_file = MagicMock(
            side_effect=InvalidParameterNameError("Parameter name can not be empty.")
        )

        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)
        result = parameter_editor_table._confirm_parameter_addition("")

        assert result is False
        error_dialog.assert_called_once()

    def test_confirm_parameter_addition_existing_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test parameter addition when parameter already exists."""
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {
            "test_file": ParDict({"EXISTING_PARAM": Par(1.0, "comment")})
        }

        parameter_editor_table.parameter_editor.add_parameter_to_current_file = MagicMock(
            side_effect=InvalidParameterNameError("Parameter already exists, edit it instead")
        )

        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)
        result = parameter_editor_table._confirm_parameter_addition("EXISTING_PARAM")

        assert result is False
        error_dialog.assert_called_once()


class TestHeaderCreationBehavior:
    """Test header creation methods."""

    def test_create_headers_and_tooltips_simple_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test header creation in simple mode."""
        headers, tooltips = parameter_editor_table._create_headers_and_tooltips(show_upload_column=False)

        assert headers == PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE
        assert len(tooltips) == len(headers)
        assert len(tooltips) == 7

    def test_create_headers_and_tooltips_advanced_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test header creation in advanced mode."""
        headers, tooltips = parameter_editor_table._create_headers_and_tooltips(show_upload_column=True)

        assert headers == PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED
        assert len(tooltips) == len(headers)
        assert len(tooltips) == 8

    def test_headers_and_tooltips_localization(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test header localization."""
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table._") as mock_translate:
            mock_translate.side_effect = lambda x: f"TRANSLATED_{x}"

            _headers, _ = parameter_editor_table._create_headers_and_tooltips(show_upload_column=False)

            assert mock_translate.call_count >= 6


class TestBitmaskFunctionalityBehavior:
    """Test bitmask functionality."""

    def test_bitmask_window_creation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test bitmask selection window creation."""
        mock_event = MagicMock()
        mock_widget = MagicMock()
        mock_widget.get.return_value = "5"
        mock_widget.unbind = MagicMock()
        mock_event.widget = mock_widget
        mock_change_reason_widget = MagicMock(spec=ttk.Entry)
        mock_value_is_different_widget = MagicMock(spec=ttk.Label)

        param = create_mock_data_model_ardupilot_parameter(
            name="TEST_PARAM",
            value=3.0,
            is_bitmask=True,
        )

        parameter_editor_table.main_frame = MagicMock()
        parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
            {"TEST_PARAM": Par(0.0, "default")}
        )

        with (
            patch("tkinter.Toplevel") as mock_toplevel,
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Checkbutton"),
            patch("tkinter.ttk.Label"),
        ):
            parameter_editor_table._open_bitmask_selection_window(
                mock_event, param, mock_change_reason_widget, mock_value_is_different_widget
            )

            mock_toplevel.assert_called_once()
            mock_event.widget.unbind.assert_called_once_with("<Double-Button-1>")

    def test_bitmask_value_calculation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test bitmask value calculation placeholder."""
        # Value calculation logic is in nested function


class TestMousewheelHandlingBehavior:
    """Test mousewheel handling for comboboxes."""

    def test_setup_combobox_mousewheel_handling(self, parameter_editor_table: ParameterEditorTable) -> None:  # pylint: disable=unused-argument
        """Test mousewheel handling setup."""
        mock_combobox = MagicMock(spec=PairTupleCombobox)

        setup_combobox_mousewheel_handling(mock_combobox)

        assert hasattr(mock_combobox, "dropdown_is_open")

        expected_bindings = [
            ("<<ComboboxDropdown>>",),
            ("<FocusOut>",),
            ("<MouseWheel>",),
            ("<Button-4>",),
            ("<Button-5>",),
        ]

        bind_calls = mock_combobox.bind.call_args_list
        for expected_binding in expected_bindings:
            assert any(call.args[0] == expected_binding[0] for call in bind_calls), f"Binding {expected_binding[0]} not found"

    def test_mousewheel_handler_when_dropdown_closed(self) -> None:
        """Test mousewheel handling when dropdown is closed."""
        with patch("tkinter.Tk"):
            mock_combobox = MagicMock(spec=PairTupleCombobox)
            mock_master = MagicMock()
            mock_combobox.master = mock_master
            mock_combobox.dropdown_is_open = False

            setup_combobox_mousewheel_handling(mock_combobox)

            mousewheel_bind_call = None
            for call in mock_combobox.bind.call_args_list:
                if call[0][0] == "<MouseWheel>":
                    mousewheel_bind_call = call
                    break

            assert mousewheel_bind_call is not None

            handler = mousewheel_bind_call[0][1]
            mock_event = MagicMock()
            mock_event.delta = 120

            result = handler(mock_event)

            assert result == "break"
            mock_master.event_generate.assert_called_once_with("<MouseWheel>", delta=120)

    def test_mousewheel_handler_when_dropdown_open(self) -> None:
        """Test mousewheel handling when dropdown is open."""
        with patch("tkinter.Tk"):
            mock_combobox = MagicMock(spec=PairTupleCombobox)
            mock_master = MagicMock()
            mock_combobox.master = mock_master

            setup_combobox_mousewheel_handling(mock_combobox)

            mock_combobox.dropdown_is_open = True

            mousewheel_bind_call = None
            for call in mock_combobox.bind.call_args_list:
                if call[0][0] == "<MouseWheel>":
                    mousewheel_bind_call = call
                    break

            assert mousewheel_bind_call is not None

            handler = mousewheel_bind_call[0][1]
            mock_event = MagicMock()
            mock_event.delta = 120

            result = handler(mock_event)

            assert result is None
            mock_master.event_generate.assert_not_called()

    def test_dropdown_state_management(self) -> None:
        """Test dropdown state tracking."""
        with patch("tkinter.Tk"):
            mock_combobox = MagicMock(spec=PairTupleCombobox)

            setup_combobox_mousewheel_handling(mock_combobox)

            dropdown_opened_handler = None
            dropdown_closed_handler = None

            for call in mock_combobox.bind.call_args_list:
                if call[0][0] == "<<ComboboxDropdown>>":
                    dropdown_opened_handler = call[0][1]
                elif call[0][0] == "<FocusOut>":
                    dropdown_closed_handler = call[0][1]

            assert dropdown_opened_handler is not None
            assert dropdown_closed_handler is not None

            mock_event = MagicMock()
            dropdown_opened_handler(mock_event)
            assert mock_combobox.dropdown_is_open is True

            dropdown_closed_handler(mock_event)
            assert mock_combobox.dropdown_is_open is False


class TestUIErrorInfoHandling:
    """Test UI message handling in repopulate_table method."""

    def test_repopulate_handles_no_different_parameters_found(self, parameter_editor_table) -> None:
        """Test handling when no different parameters found."""
        parameter_editor_table.parameter_editor.get_different_parameters.return_value = {}
        parameter_editor_table.parameter_editor.current_file = "test_file.param"
        parameter_editor_table.parameter_editor_window.gui_complexity = "simple"

        info_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_info)

        parameter_editor_table.repopulate_table(
            show_only_differences=True,
            gui_complexity="simple",
        )

        info_dialog.assert_called_once()
        call_args = info_dialog.call_args[0]
        assert "No different parameters found" in call_args[1]
        assert "test_file.param" in call_args[1]
        parameter_editor_table.parameter_editor_window.on_skip_click.assert_called_once()

    def test_update_table_handles_keyerror_with_critical_logging_and_exit(self, parameter_editor_table) -> None:
        """Test KeyError handling during table update."""
        faulty_param = create_mock_data_model_ardupilot_parameter(name="FAULTY_PARAM", value=1.0)
        params = {"FAULTY_PARAM": faulty_param}

        parameter_editor_table._create_column_widgets = MagicMock(side_effect=KeyError("Test KeyError"))
        parameter_editor_table._configure_table_columns = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.logging_critical") as mock_critical,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.sys_exit") as mock_exit,
        ):
            parameter_editor_table._update_table(params, "simple")

            mock_critical.assert_called_once()
            call_args = mock_critical.call_args[0]
            assert "FAULTY_PARAM" in call_args[1]
            assert "Test KeyError" in str(call_args[3])

            mock_exit.assert_called_once_with(1)

    def test_update_table_creates_add_button_with_tooltip(self, parameter_editor_table) -> None:
        """Test Add button creation with tooltip."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=1.0)
        params = {"TEST_PARAM": param}

        parameter_editor_table.parameter_editor.current_file = "test_file.param"

        with (
            patch.object(parameter_editor_table, "_create_column_widgets") as mock_create_widgets,
            patch("tkinter.ttk.Button") as mock_button,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip,
        ):
            mock_create_widgets.return_value = [MagicMock() for _ in range(7)]

            parameter_editor_table._update_table(params, "simple")

            mock_button.assert_called_once()
            call_args, call_kwargs = mock_button.call_args
            assert call_args[0] == parameter_editor_table.view_port
            assert call_kwargs["text"] == _("Add")
            assert call_kwargs["style"] == "narrow.TButton"
            assert call_kwargs["command"] == parameter_editor_table._on_parameter_add

            mock_tooltip.assert_called()
            tooltip_call_args = mock_tooltip.call_args[0]
            assert "Add a parameter to the test_file.param file" in tooltip_call_args[1]

    def test_create_flightcontroller_value_sets_correct_background_colors(self, parameter_editor_table) -> None:  # pylint: disable=too-many-statements # noqa: PLR0915
        """Test FC value label background colors."""
        param_default = MagicMock()
        param_default.has_fc_value = True
        param_default.fc_value_equals_default_value = True
        param_default.fc_value_as_string = "1.0"
        param_default.tooltip_fc_value = None

        param_below = MagicMock()
        param_below.has_fc_value = True
        param_below.fc_value_equals_default_value = False
        param_below.fc_value_is_below_limit.return_value = True
        param_below.fc_value_as_string = "1.0"
        param_below.tooltip_fc_value = None

        param_above = MagicMock()
        param_above.has_fc_value = True
        param_above.fc_value_equals_default_value = False
        param_above.fc_value_is_below_limit.return_value = False
        param_above.fc_value_is_above_limit.return_value = True
        param_above.fc_value_as_string = "10.0"
        param_above.tooltip_fc_value = None

        param_unknown = MagicMock()
        param_unknown.has_fc_value = True
        param_unknown.fc_value_equals_default_value = False
        param_unknown.fc_value_is_below_limit.return_value = False
        param_unknown.fc_value_is_above_limit.return_value = False
        param_unknown.fc_value_has_unknown_bits_set.return_value = True
        param_unknown.fc_value_as_string = "5.0"
        param_unknown.tooltip_fc_value = None

        param_no_fc = MagicMock()
        param_no_fc.has_fc_value = False

        param_normal = MagicMock()
        param_normal.has_fc_value = True
        param_normal.fc_value_equals_default_value = False
        param_normal.fc_value_is_below_limit.return_value = False
        param_normal.fc_value_is_above_limit.return_value = False
        param_normal.fc_value_has_unknown_bits_set.return_value = False
        param_normal.fc_value_as_string = "5.0"
        param_normal.tooltip_fc_value = None

        with (
            patch("tkinter.ttk.Label") as mock_label,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
        ):
            parameter_editor_table._create_flightcontroller_value(param_default)
            parameter_editor_table._create_flightcontroller_value(param_below)
            parameter_editor_table._create_flightcontroller_value(param_above)
            parameter_editor_table._create_flightcontroller_value(param_unknown)
            parameter_editor_table._create_flightcontroller_value(param_no_fc)
            parameter_editor_table._create_flightcontroller_value(param_normal)

            calls = mock_label.call_args_list
            assert len(calls) == 6

            assert calls[0][1]["background"] == "light blue"
            assert calls[1][1]["background"] == "orangered"
            assert calls[2][1]["background"] == "red3"
            assert calls[3][1]["background"] == "red3"
            assert calls[4][1]["background"] == "orange"

    def test_update_combobox_style_on_selection_updates_ui_when_value_changes(self, parameter_editor_table) -> None:
        """Test combobox style update on selection."""
        combobox_widget = MagicMock()
        combobox_widget.get_selected_key.return_value = "test_value"
        combobox_widget.configure = MagicMock()
        combobox_widget.on_combo_configure = MagicMock()

        change_reason_widget = MagicMock()
        value_is_different = MagicMock()
        value_is_different.config = MagicMock()
        event = MagicMock()
        event.width = 0

        param = MagicMock()
        param.name = "TEST_PARAM"
        param.new_value_equals_default_value = False
        param.is_different_from_fc = True
        param.tooltip_change_reason = "Why it changed"

        with (
            patch.object(parameter_editor_table, "_handle_parameter_value_update", return_value=True) as handle_mock,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as tooltip_mock,
        ):
            parameter_editor_table._update_combobox_style_on_selection(
                combobox_widget,
                param,
                event,
                change_reason_widget,
                value_is_different,
            )

            handle_mock.assert_called_once_with(
                param,
                "test_value",
                include_range_check=False,
            )
            tooltip_mock.assert_called_once_with(change_reason_widget, "Why it changed")
            value_is_different.config.assert_called_once()
            combobox_widget.configure.assert_called_once_with(style="readonly.TCombobox")
            assert event.width == NEW_VALUE_WIDGET_WIDTH
            combobox_widget.on_combo_configure.assert_called_once_with(event)

    def test_update_new_value_entry_text_sets_correct_styles(self, parameter_editor_table) -> None:
        """Test entry widget style setting."""
        mock_entry = MagicMock()

        param_default = MagicMock()
        param_default.value_as_string = "1.0"
        param_default.new_value_equals_default_value = True
        param_default.is_below_limit.return_value = False
        param_default.is_above_limit.return_value = False
        param_default.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_default)
        mock_entry.configure.assert_called_with(style="default_v.TEntry")

        mock_entry.reset_mock()

        param_below = MagicMock()
        param_below.value_as_string = "0.5"
        param_below.new_value_equals_default_value = False
        param_below.is_below_limit.return_value = True
        param_below.is_above_limit.return_value = False
        param_below.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_below)
        mock_entry.configure.assert_called_with(style="below_limit.TEntry")

        mock_entry.reset_mock()

        param_above = MagicMock()
        param_above.value_as_string = "10.0"
        param_above.new_value_equals_default_value = False
        param_above.is_below_limit.return_value = False
        param_above.is_above_limit.return_value = True
        param_above.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_above)
        mock_entry.configure.assert_called_with(style="above_limit.TEntry")

        mock_entry.reset_mock()

        param_unknown = MagicMock()
        param_unknown.value_as_string = "5.0"
        param_unknown.new_value_equals_default_value = False
        param_unknown.is_below_limit.return_value = False
        param_unknown.is_above_limit.return_value = False
        param_unknown.has_unknown_bits_set.return_value = True

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_unknown)
        mock_entry.configure.assert_called_with(style="above_limit.TEntry")

        mock_entry.reset_mock()

        param_normal = MagicMock()
        param_normal.value_as_string = "5.0"
        param_normal.new_value_equals_default_value = False
        param_normal.is_below_limit.return_value = False
        param_normal.is_above_limit.return_value = False
        param_normal.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_normal)
        mock_entry.configure.assert_called_with(style="TEntry")

    def test_create_new_value_entry_creates_combobox_for_multiple_choice(self, parameter_editor_table) -> None:
        """Test combobox creation for multiple choice parameters."""
        param = MagicMock()
        param.is_multiple_choice = True
        param.choices_dict = {"Option1": "1", "Option2": "2", "Option3": "3"}
        param.get_selected_value_from_dict.return_value = "Option2"
        param.value_as_string = "Option2"
        param.name = "TEST_PARAM"
        param.is_editable = True
        param.new_value_equals_default_value = False

        change_reason_widget = MagicMock()
        value_is_different = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.PairTupleCombobox"
            ) as mock_combobox,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.get_widget_font_family_and_size"
            ) as mock_font,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.platform_system") as mock_platform,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.setup_combobox_mousewheel_handling"
            ) as mock_mousewheel,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
        ):
            mock_font.return_value = ("Arial", 10)
            mock_platform.return_value = "Linux"
            mock_instance = MagicMock()
            mock_combobox.return_value = mock_instance

            result = parameter_editor_table._create_new_value_entry(param, change_reason_widget, value_is_different)

            mock_combobox.assert_called_once()
            call_args = mock_combobox.call_args
            assert call_args[0][0] == parameter_editor_table.view_port
            assert call_args[0][1] == list(param.choices_dict.items())
            assert call_args[0][2] == param.value_as_string
            assert call_args[0][3] == param.name
            assert call_args[1]["style"] == "readonly.TCombobox"

            mock_instance.set.assert_called_once_with("Option2")

            mock_font.assert_called_once_with(mock_instance)
            mock_instance.config.assert_called_once_with(
                state="readonly",
                width=NEW_VALUE_WIDGET_WIDTH,
                font=("Arial", 11),
            )

            bind_calls = mock_instance.bind.call_args_list
            combobox_selected_calls = [call for call in bind_calls if call[0][0] == "<<ComboboxSelected>>"]
            assert len(combobox_selected_calls) == 1

            mock_mousewheel.assert_called_once_with(mock_instance)

            assert result == mock_instance

    def test_create_new_value_entry_shows_error_for_non_editable_parameters(self, parameter_editor_table) -> None:
        """Test non-editable parameter handling."""
        forced_param = MagicMock()
        forced_param.is_multiple_choice = False
        forced_param.is_editable = False
        forced_param.is_forced = True
        forced_param.is_derived = False
        forced_param.value_as_string = "1.0"

        derived_param = MagicMock()
        derived_param.is_multiple_choice = False
        derived_param.is_editable = False
        derived_param.is_forced = False
        derived_param.is_derived = True
        derived_param.value_as_string = "2.0"

        change_reason_widget = MagicMock()
        value_is_different = MagicMock()

        with (
            patch("tkinter.ttk.Entry") as mock_entry,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
            patch.object(parameter_editor_table._dialogs, "show_error") as mock_error,
        ):
            mock_entry_instance = MagicMock()
            mock_entry.return_value = mock_entry_instance

            forced_entry = parameter_editor_table._create_new_value_entry(
                forced_param, change_reason_widget, value_is_different
            )

            mock_entry_instance.config.assert_called_with(state="disabled", background="light grey")

            button1_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-1>"]
            button3_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-3>"]
            assert len(button1_calls) == 1
            assert len(button3_calls) == 1

            mock_event = MagicMock()
            mock_event.widget = forced_entry

            button1_calls[0][0][1](mock_event)

            mock_error.assert_called_with(_("Forced Parameter"), mock_error.call_args[0][1])
            assert "correct value" in mock_error.call_args[0][1]

        mock_error.reset_mock()
        mock_entry.reset_mock()

        with (
            patch("tkinter.ttk.Entry") as mock_entry,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
            patch.object(parameter_editor_table._dialogs, "show_error") as mock_error,
        ):
            mock_entry_instance = MagicMock()
            mock_entry.return_value = mock_entry_instance

            derived_entry = parameter_editor_table._create_new_value_entry(
                derived_param, change_reason_widget, value_is_different
            )

            mock_entry_instance.config.assert_called_with(state="disabled", background="light grey")

            button1_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-1>"]
            button3_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-3>"]
            assert len(button1_calls) == 1
            assert len(button3_calls) == 1

            mock_event = MagicMock()
            mock_event.widget = derived_entry

            button1_calls[0][0][1](mock_event)

            mock_error.assert_called_with(_("Derived Parameter"), mock_error.call_args[0][1])
            assert "derived from information" in mock_error.call_args[0][1]


class TestParentWidgetResolution:
    """Test parent widget resolution methods."""

    def test_get_parent_root_returns_top_level(self, parameter_editor_table: ParameterEditorTable, mock_master: tk.Tk) -> None:
        nested = tk.Frame(mock_master)
        parameter_editor_table.main_frame = nested

        assert parameter_editor_table._get_parent_root() is mock_master

    def test_get_parent_toplevel_uses_winfo_fallback(
        self, parameter_editor_table: ParameterEditorTable, mock_master: tk.Tk
    ) -> None:
        fake_frame = MagicMock(spec=tk.Misc)
        fake_frame.master = None
        fallback = tk.Toplevel(mock_master)
        fake_frame.winfo_toplevel.return_value = fallback
        parameter_editor_table.main_frame = fake_frame

        try:
            assert parameter_editor_table._get_parent_toplevel() is fallback
        finally:
            fallback.destroy()


class TestLayoutUtilityMethods:
    """Test column creation, grid placement, and configuration."""

    def test_create_column_widgets_appends_upload_column(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter()
        with (
            patch.object(parameter_editor_table, "_create_change_reason_entry", return_value="change"),
            patch.object(parameter_editor_table, "_create_value_different_label", return_value="diff"),
            patch.object(parameter_editor_table, "_create_delete_button", return_value="delete"),
            patch.object(parameter_editor_table, "_create_parameter_name", return_value="name"),
            patch.object(parameter_editor_table, "_create_flightcontroller_value", return_value="fc"),
            patch.object(parameter_editor_table, "_create_new_value_entry", return_value="new"),
            patch.object(parameter_editor_table, "_create_unit_label", return_value="unit"),
            patch.object(parameter_editor_table, "_create_upload_checkbutton", return_value="upload"),
        ):
            widgets = parameter_editor_table._create_column_widgets("PARAM", param, show_upload_column=True)

        assert widgets == ["delete", "name", "fc", "diff", "new", "unit", "upload", "change"]

    def test_grid_column_widgets_places_upload_column(self, parameter_editor_table: ParameterEditorTable) -> None:
        row_widgets = [MagicMock() for _ in range(8)]

        parameter_editor_table._grid_column_widgets(row_widgets, row=2, show_upload_column=True)

        row_widgets[6].grid.assert_called_once_with(row=2, column=6, sticky="e", padx=0)
        change_reason_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=True)
        row_widgets[change_reason_index].grid.assert_called_with(row=2, column=change_reason_index, sticky="ew", padx=(0, 5))

    def test_configure_table_columns_configures_upload_column(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.view_port = MagicMock()

        parameter_editor_table._configure_table_columns(show_upload_column=True)

        parameter_editor_table.view_port.columnconfigure.assert_any_call(6, weight=0)
        change_reason_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=True)
        parameter_editor_table.view_port.columnconfigure.assert_any_call(change_reason_index, weight=1)


class TestWidgetFactoryHelpers:
    """Test widget helper functions and tooltips."""

    def test_create_parameter_name_applies_tooltip(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(
            name="HAS_TOOLTIP",
            metadata={"doc_tooltip": "tooltip"},
        )

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tip:
            label = parameter_editor_table._create_parameter_name(param)

        assert isinstance(label, ttk.Label)
        mock_tip.assert_called_once_with(label, "tooltip")

    def test_create_value_different_label_reflects_state(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(value=2.0, fc_value=1.0)
        label = parameter_editor_table._create_value_different_label(param)
        assert NEW_VALUE_DIFFERENT_STR in label.cget("text")

    def test_create_unit_label_sets_tooltip(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(metadata={"unit": "m/s", "unit_tooltip": "unit"})
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tip:
            label = parameter_editor_table._create_unit_label(param)
        assert isinstance(label, ttk.Label)
        mock_tip.assert_called_once_with(label, "unit")

    def test_create_upload_checkbutton_reflects_fc_connection(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.parameter_editor.is_fc_connected = False
        button = parameter_editor_table._create_upload_checkbutton("PARAM")
        assert parameter_editor_table.upload_checkbutton_var["PARAM"].get() is False
        assert button.instate(("disabled",))


class TestHandlerEdgeCases:
    """Test handler helper edge cases."""

    def test_handle_parameter_value_update_result_unknown_status_returns_false(
        self, parameter_editor_table: ParameterEditorTable
    ) -> None:
        from ardupilot_methodic_configurator.data_model_parameter_editor import (
            ParameterValueUpdateResult,
            ParameterValueUpdateStatus,
        )

        param = create_mock_data_model_ardupilot_parameter()
        unknown_result = ParameterValueUpdateResult(cast("ParameterValueUpdateStatus", None))

        assert parameter_editor_table._handle_parameter_value_update_result(unknown_result, param, "1") is False

    def test_new_value_entry_handler_deduplicates_focusout(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(name="HANDLER", value=1.0)
        change_reason = ttk.Entry(parameter_editor_table.view_port)
        diff_label = ttk.Label(parameter_editor_table.view_port)

        def _fake_handle_update(_param_name: str, new_value: str, include_range_check: bool = True) -> bool:  # noqa: ARG001 # pylint: disable=unused-argument
            param._new_value = float(new_value)
            return True

        with patch.object(
            parameter_editor_table,
            "_handle_parameter_value_update",
            side_effect=_fake_handle_update,
        ) as handle_mock:
            entry = parameter_editor_table._create_new_value_entry(param, change_reason, diff_label)
            entry.delete(0, tk.END)
            entry.insert(0, "2")
            key_event = SimpleNamespace(widget=entry, type=tk.EventType.KeyPress)
            focus_event = SimpleNamespace(widget=entry, type=tk.EventType.FocusOut)
            entry.testing_on_parameter_value_change(key_event)
            entry.testing_on_parameter_value_change(focus_event)

        assert handle_mock.call_count == 1

    def test_change_reason_handler_removes_duplicate_events(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter()
        param.set_change_reason = MagicMock(return_value=True)
        entry = parameter_editor_table._create_change_reason_entry(param)
        entry.delete(0, tk.END)
        entry.insert(0, "Updated")

        key_event = SimpleNamespace(widget=entry, type=tk.EventType.KeyPress)
        focus_event = SimpleNamespace(widget=entry, type=tk.EventType.FocusOut)
        entry.testing_on_change_reason_change(key_event)
        entry.testing_on_change_reason_change(focus_event)

        param.set_change_reason.assert_called_once_with("Updated")


class TestParameterAdditionWorkflows:
    """Test add-parameter dialog flows and error handling."""

    def test_on_parameter_add_creates_dialog_window(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test dialog window creation."""
        parameter_editor_table.parameter_editor.get_possible_add_param_names.return_value = ["TEST_PARAM1", "TEST_PARAM2"]

        mock_window = MagicMock()
        mock_window.root = MagicMock(spec=tk.Toplevel)
        mock_window.main_frame = MagicMock()

        mock_search_var = MagicMock()
        mock_search_var.get.return_value = ""
        mock_search_entry = MagicMock()
        mock_listbox = MagicMock()
        mock_listbox.size.return_value = 2
        mock_listbox.curselection.return_value = ()
        mock_button = MagicMock()

        mock_widgets = (mock_search_var, mock_search_entry, mock_listbox, mock_button)

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.BaseWindow",
                return_value=mock_window,
            ),
            patch.object(parameter_editor_table, "_create_parameter_add_dialog_widgets", return_value=mock_widgets),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.BaseWindow.center_window"),
        ):
            parameter_editor_table._on_parameter_add()

            mock_window.root.title.assert_called_once()
            mock_window.root.geometry.assert_called_once_with("250x400")
            mock_window.root.transient.assert_called_once()
            mock_window.root.grab_set.assert_called_once()

            assert mock_search_var.trace_add.called
            assert mock_listbox.bind.called

    def test_on_parameter_add_handles_operation_not_possible(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Test OperationNotPossibleError handling."""
        parameter_editor_table.parameter_editor.get_possible_add_param_names.side_effect = OperationNotPossibleError("nope")

        with pytest.raises(OperationNotPossibleError):
            parameter_editor_table._on_parameter_add()

    def test_confirm_parameter_addition_handles_errors(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.parameter_editor.add_parameter_to_current_file.side_effect = InvalidParameterNameError("bad")
        assert parameter_editor_table._confirm_parameter_addition("bad") is False
        parameter_editor_table._dialogs.show_error.assert_called()

        parameter_editor_table._dialogs.show_error.reset_mock()
        parameter_editor_table.parameter_editor.add_parameter_to_current_file.side_effect = OperationNotPossibleError("ops")
        assert parameter_editor_table._confirm_parameter_addition("bad") is False
        parameter_editor_table._dialogs.show_error.assert_called()


class TestUploadSelectionBehavior:
    """Test upload selection helper based on GUI complexity."""

    def test_get_upload_selected_params_simple_returns_all(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table._should_show_upload_column = MagicMock(return_value=False)
        parameter_editor_table.parameter_editor.get_parameters_as_par_dict.return_value = ParDict({})

        result = parameter_editor_table.get_upload_selected_params("simple")
        assert result == ParDict({})

    def test_get_upload_selected_params_filters_checked(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table._should_show_upload_column = MagicMock(return_value=True)
        parameter_editor_table.upload_checkbutton_var = {
            "A": tk.BooleanVar(value=True),
            "B": tk.BooleanVar(value=False),
        }
        parameter_editor_table.parameter_editor.get_parameters_as_par_dict.return_value = ParDict({"A": Par(1.0, "")})

        result = parameter_editor_table.get_upload_selected_params("normal")
        assert result == ParDict({"A": Par(1.0, "")})
