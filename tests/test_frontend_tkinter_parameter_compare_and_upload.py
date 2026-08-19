#!/usr/bin/env python3

"""
Tests for the external parameter-file upload window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=protected-access

from unittest.mock import MagicMock, call, patch

from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload import ParameterFileUploadWindow
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import (
    ParameterEditorTable,
    ParameterTableOptions,
)


def _window_without_tk() -> ParameterFileUploadWindow:
    window = ParameterFileUploadWindow.__new__(ParameterFileUploadWindow)
    window.parent = MagicMock()
    window.parameters = {"ROLL_P": MagicMock()}
    window.table = MagicMock()
    window.table.canvas.yview.return_value = (0.4, 0.8)
    window.table.get_unselected_manually_edited_different_parameter_names.return_value = []
    window.table_options = ParameterTableOptions(values_editable=False)
    window.show_only_changed = MagicMock()
    return window


def test_manual_column_enables_only_the_selected_external_parameter() -> None:
    """
    Enable only the manually selected external row.

    GIVEN an external parameter row whose Manual checkbox is clear
    WHEN the user selects Manual
    THEN only that row becomes editable without rebuilding the static table.
    """
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.options = ParameterTableOptions(values_editable=False, manual_override_for_all_parameters=True)
    table.view_port = MagicMock()
    table.repopulate_table = MagicMock()
    table._set_external_value_widget_editability = MagicMock()
    parameter = MagicMock(name="ROLL_P", is_readonly=False)
    parameter.name = "ROLL_P"
    variable = MagicMock()
    variable.get.return_value = True

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.tk.BooleanVar", return_value=variable),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.ttk.Checkbutton") as checkbutton,
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip_lazily"),
    ):
        table._create_manual_override_widget(parameter)
        checkbutton.call_args.kwargs["command"]()

    assert table.options.manually_editable_parameters == {"ROLL_P"}
    assert table._set_external_value_widget_editability.call_args.args == (parameter, True)
    table.repopulate_table.assert_not_called()


def test_clearing_manual_checkbox_discards_the_in_memory_edit() -> None:
    """
    Restore a temporary edit when Manual is cleared.

    GIVEN a temporarily edited external parameter
    WHEN the user clears its Manual checkbox
    THEN its file value is restored and its row is disabled without rebuilding the table.
    """
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.options = ParameterTableOptions(
        values_editable=False,
        manual_override_for_all_parameters=True,
        manually_editable_parameters={"ROLL_P"},
    )
    table.view_port = MagicMock()
    table.repopulate_table = MagicMock()
    table._set_external_value_widget_editability = MagicMock()
    difference_label = MagicMock()
    table._value_is_different_labels = {"ROLL_P": difference_label}
    parameter = MagicMock(is_readonly=False)
    parameter.name = "ROLL_P"
    parameter.is_different_from_fc = False
    variable = MagicMock()
    variable.get.return_value = False

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.tk.BooleanVar", return_value=variable),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.ttk.Checkbutton") as checkbutton,
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip_lazily"),
    ):
        table._create_manual_override_widget(parameter)
        checkbutton.call_args.kwargs["command"]()

    assert not table.options.manually_editable_parameters
    parameter.reset_new_value_to_file_value.assert_called_once_with()
    difference_label.config.assert_called_once_with(text=" ")
    assert table._set_external_value_widget_editability.call_args.args == (parameter, False)
    table.repopulate_table.assert_not_called()


def test_manual_checkbox_restores_numeric_entry_background_when_enabled() -> None:
    """
    Make an externally loaded numeric value visibly editable.

    GIVEN an external numeric parameter with a disabled entry
    WHEN the user selects its Manual checkbox
    THEN the entry becomes enabled with its normal white background
    """
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    entry = MagicMock()
    parameter = MagicMock(name="ROLL_P")
    parameter.name = "ROLL_P"
    table._new_value_widgets = {"ROLL_P": entry}

    with patch.object(table, "_update_new_value_entry_text") as update_text:
        table._set_external_value_widget_editability(parameter, editable=True)

    assert entry.configure.call_args_list == [
        call(state="normal", background="white"),
        call(state="normal"),
    ]
    update_text.assert_called_once_with(entry, parameter)


def test_manual_checkbox_syncs_numeric_entry_before_disabling() -> None:
    """Restore the file value before a manually edited entry is disabled."""
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    entry = MagicMock()
    parameter = MagicMock(name="ROLL_P")
    parameter.name = "ROLL_P"
    table._new_value_widgets = {"ROLL_P": entry}

    with patch.object(table, "_update_new_value_entry_text") as update_text:
        table._set_external_value_widget_editability(parameter, editable=False)

    assert entry.configure.call_args_list == [
        call(state="normal", background="light grey"),
        call(state="disabled"),
    ]
    update_text.assert_called_once_with(entry, parameter)


def test_external_table_omits_editor_only_columns() -> None:
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.options = ParameterTableOptions(
        show_parameter_actions=False,
        show_upload_column=True,
        show_manual_override_column=True,
        show_change_reason_column=False,
        manual_override_for_all_parameters=True,
    )

    headers, tooltips = table._create_headers_and_tooltips(show_upload_column=True)

    assert headers[0] == "Parameter"
    assert "Unit" in headers
    assert headers[-1] == "Manual"
    assert len(headers) == len(tooltips) == 7
    assert "Upload" in headers
    assert "Manual" in headers
    assert "Why are you changing this parameter?" not in headers


def test_external_table_checks_bitmask_state_on_external_parameter() -> None:
    """External-only names must not be looked up in the current AMC configuration step."""
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.options = ParameterTableOptions(
        show_parameter_actions=False,
        show_upload_column=False,
        show_manual_override_column=False,
        show_change_reason_column=False,
    )
    table.parameters = {"EXTERNAL_ONLY": MagicMock(is_editable=True, is_bitmask=False)}
    table.parameter_editor = MagicMock()
    table.parameter_editor.should_display_bitmask_parameter_editor_usage.side_effect = KeyError("EXTERNAL_ONLY")
    table.parameter_editor_window = MagicMock()
    table.view_port = MagicMock()
    table._create_column_widgets = MagicMock(return_value=[])
    table._grid_column_widgets = MagicMock()
    table._configure_table_columns = MagicMock()
    table._get_parent_root = MagicMock(return_value=None)

    table._update_table(table.parameters, "normal")

    table.parameter_editor.should_display_bitmask_parameter_editor_usage.assert_not_called()


def test_external_table_returns_only_upload_checked_parameters() -> None:
    """
    Build an upload payload from checked writable rows only.

    GIVEN one checked and one unchecked external parameter
    WHEN the table builds the upload payload
    THEN only the checked parameter is included.
    """
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.options = ParameterTableOptions(show_upload_column=True)
    table.parameters = {
        "ROLL_P": MagicMock(is_readonly=False),
        "PITCH_P": MagicMock(is_readonly=False),
    }
    table.parameter_editor = MagicMock()
    table.upload_checkbutton_var = {
        "ROLL_P": MagicMock(get=MagicMock(return_value=True)),
        "PITCH_P": MagicMock(get=MagicMock(return_value=False)),
    }
    expected = ParDict({"ROLL_P": Par(0.2)})
    table.parameter_editor.parameters_as_par_dict.return_value = expected

    selected = table.get_upload_selected_params("normal")

    assert selected == expected
    table.parameter_editor.parameters_as_par_dict.assert_called_once_with({"ROLL_P": table.parameters["ROLL_P"]})


def test_external_upload_defaults_select_only_parameters_changed_from_fc() -> None:
    """
    Initialize external Upload selections from FC differences.

    GIVEN changed, unchanged, and FC-missing external parameters
    WHEN upload checkboxes are initialized
    THEN only changed and missing writable parameters are selected.
    """
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.parameters = {
        "CHANGED": MagicMock(is_different_from_fc=True, has_fc_value=True, is_readonly=False),
        "UNCHANGED": MagicMock(is_different_from_fc=False, has_fc_value=True, is_readonly=False),
        "MISSING": MagicMock(is_different_from_fc=False, has_fc_value=False, is_readonly=False),
    }
    table.parameter_editor = MagicMock(is_fc_connected=True)
    table.view_port = MagicMock()
    table._upload_selection_defaults = {}
    table.upload_checkbutton_var = {}
    changed_variable = MagicMock()
    unchanged_variable = MagicMock()
    missing_variable = MagicMock()

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.tk.BooleanVar",
            side_effect=[changed_variable, unchanged_variable, missing_variable],
        ) as boolean_var,
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.ttk.Checkbutton"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
    ):
        table._create_upload_checkbutton("CHANGED")
        table._create_upload_checkbutton("UNCHANGED")
        table._create_upload_checkbutton("MISSING")

    assert boolean_var.call_args_list[0].kwargs == {"value": True}
    assert boolean_var.call_args_list[1].kwargs == {"value": False}
    assert boolean_var.call_args_list[2].kwargs == {"value": True}


def test_external_readonly_parameter_cannot_be_selected_for_upload() -> None:
    """
    Prevent read-only external parameters from being uploaded.

    GIVEN a changed external parameter that metadata marks read-only
    WHEN its Upload checkbox is initialized
    THEN it remains deselected and disabled.
    """
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.parameters = {
        "READ_ONLY": MagicMock(is_different_from_fc=True, has_fc_value=True, is_readonly=True),
    }
    table.parameter_editor = MagicMock(is_fc_connected=True)
    table.view_port = MagicMock()
    table._upload_selection_defaults = {}
    table.upload_checkbutton_var = {}
    variable = MagicMock()
    checkbox = MagicMock()

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.tk.BooleanVar",
            return_value=variable,
        ) as boolean_var,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.ttk.Checkbutton",
            return_value=checkbox,
        ),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
    ):
        table._create_upload_checkbutton("READ_ONLY")

    boolean_var.assert_called_once_with(value=False)
    checkbox.configure.assert_called_once_with(state="disabled")

    table.options = ParameterTableOptions(show_upload_column=True)
    table.upload_checkbutton_var = {"READ_ONLY": MagicMock(get=MagicMock(return_value=True))}
    table.parameter_editor.parameters_as_par_dict.return_value = ParDict()
    selected = table.get_upload_selected_params("normal")

    assert not selected
    table.parameter_editor.parameters_as_par_dict.assert_called_once_with({})


def test_upload_warns_about_unselected_manual_edits() -> None:
    """
    Warn about omitted temporary manual edits.

    GIVEN changed manual edits omitted from upload selection
    WHEN the user starts upload
    THEN the modal warns and does not begin uploading.
    """
    window = _window_without_tk()
    selected_params = ParDict({"ROLL_P": Par(0.2)})
    window.table.get_unselected_manually_edited_different_parameter_names.return_value = ["YAW_P", "PITCH_P"]
    window.table.get_upload_selected_params.return_value = selected_params
    window.parent.parameter_editor.ensure_upload_preconditions.return_value = True
    window.parent.upload_external_params.return_value = True
    window.close = MagicMock()

    window.upload_parameters()

    window.parent.ui.show_warning.assert_called_once_with(
        "Manual parameter edits not selected",
        "The following manually edited parameters differ from the flight controller "
        "but are not selected for upload:\n\nYAW_P\nPITCH_P",
    )
    window.table.get_upload_selected_params.assert_not_called()
    window.parent.upload_external_params.assert_not_called()
    window.close.assert_not_called()


def test_warning_candidates_require_manual_edit_difference_and_unselected_upload() -> None:
    table = ParameterEditorTable.__new__(ParameterEditorTable)
    table.options = ParameterTableOptions(manually_editable_parameters={"WARN", "NOT_EDITED", "UNCHANGED", "SELECTED"})
    table.parameters = {
        "WARN": MagicMock(is_dirty=True, is_different_from_fc=True),
        "NOT_EDITED": MagicMock(is_dirty=False, is_different_from_fc=True),
        "UNCHANGED": MagicMock(is_dirty=True, is_different_from_fc=False),
        "SELECTED": MagicMock(is_dirty=True, is_different_from_fc=True),
    }
    table.upload_checkbutton_var = {
        "WARN": MagicMock(get=MagicMock(return_value=False)),
        "NOT_EDITED": MagicMock(get=MagicMock(return_value=False)),
        "UNCHANGED": MagicMock(get=MagicMock(return_value=False)),
        "SELECTED": MagicMock(get=MagicMock(return_value=True)),
    }

    assert table.get_unselected_manually_edited_different_parameter_names() == ["WARN"]


def test_upload_uses_external_parameters_without_advancing_project() -> None:
    """
    Route one-off values through the external upload workflow.

    GIVEN a valid checked external parameter
    WHEN its upload succeeds
    THEN the external workflow is used and the AMC step is not advanced.
    """
    window = _window_without_tk()
    selected_params = ParDict({"ROLL_P": Par(0.2)})
    window.table.get_upload_selected_params.return_value = selected_params
    window.parent.parameter_editor.ensure_upload_preconditions.return_value = True
    window.parent.upload_external_params.return_value = True
    window.close = MagicMock()

    window.upload_parameters()

    window.table.get_upload_selected_params.assert_called_once_with(window.parent.gui_complexity)
    window.parent.parameter_editor.ensure_upload_preconditions.assert_called_once_with(
        dict(selected_params), window.parent.ui.show_warning
    )
    window.parent.upload_external_params.assert_called_once_with(selected_params)
    window.close.assert_called_once_with()
    window.parent.on_skip_click.assert_not_called()


def test_failed_external_upload_keeps_modal_open() -> None:
    """
    Keep the external modal open after a failed upload.

    GIVEN a valid external upload selection whose FC validation fails
    WHEN the parent reports upload failure
    THEN the modal stays open so the user can retry or cancel.
    """
    window = _window_without_tk()
    selected_params = ParDict({"ROLL_P": Par(0.2)})
    window.table.get_upload_selected_params.return_value = selected_params
    window.parent.parameter_editor.ensure_upload_preconditions.return_value = True
    window.parent.upload_external_params.return_value = False
    window.close = MagicMock()

    window.upload_parameters()

    window.parent.upload_external_params.assert_called_once_with(selected_params)
    window.close.assert_not_called()


def test_reset_defaults_requires_confirmation() -> None:
    """
    Require explicit confirmation before resetting all FC parameters.

    GIVEN the external parameter window is open
    WHEN the user confirms the reset action
    THEN the data-model reset workflow is called with the error callback.
    """
    window = _window_without_tk()
    window.parent.ui.ask_yesno.return_value = True
    window.close = MagicMock()

    window.reset_all_parameters_to_default()

    window.parent.ui.ask_yesno.assert_called_once_with(
        "Reset all FC parameters",
        "Are you sure you want to reset all FC parameters to their default values?",
    )
    window.parent.reset_all_parameters_to_default.assert_called_once_with()
    window.close.assert_called_once_with()


def test_reset_defaults_is_cancelled_without_confirmation() -> None:
    """Do not reset FC parameters when the user declines the confirmation."""
    window = _window_without_tk()
    window.parent.ui.ask_yesno.return_value = False

    window.reset_all_parameters_to_default()

    window.parent.parameter_editor.reset_all_parameters_to_default.assert_not_called()


def test_parameter_editor_propagates_external_workflow_failure() -> None:
    """
    Propagate the external workflow result through the UI layer.

    GIVEN the external model workflow reports failed validation
    WHEN the parameter-editor window orchestrates the upload
    THEN it returns False to its modal caller.
    """
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor.root = MagicMock()
    editor.parameter_editor = MagicMock()
    editor.parameter_editor.upload_external_params_workflow = MagicMock()
    editor.ui = MagicMock()
    editor.ui.upload_params_with_progress.return_value = False
    selected = ParDict({"ROLL_P": Par(0.2)})

    result = editor.upload_external_params(selected)

    assert result is False
    editor.ui.upload_params_with_progress.assert_called_once_with(
        editor.root,
        editor.parameter_editor.upload_external_params_workflow,
        selected,
    )
