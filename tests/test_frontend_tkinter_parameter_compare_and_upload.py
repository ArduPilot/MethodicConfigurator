#!/usr/bin/env python3

"""
Tests for the external parameter-file upload window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=protected-access

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from ardupilot_methodic_configurator import frontend_tkinter_parameter_compare_and_upload as compare_module
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload import (
    ParameterFileUploadWindow,
    StandaloneUploadHost,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload import main as standalone_main
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorUiServices, ParameterEditorWindow
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
    upload_selection = MagicMock()
    table.upload_checkbutton_var = {"ROLL_P": upload_selection}
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
    upload_selection.set.assert_called_once()
    assert upload_selection.set.call_args.args == (True,)
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
    upload_selection = MagicMock()
    table.upload_checkbutton_var = {"ROLL_P": upload_selection}
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
    upload_selection.set.assert_not_called()
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


def test_successful_external_upload_updates_fc_values_before_closing() -> None:
    """Refresh a real external parameter's FC-value snapshot after upload verification."""
    window = _window_without_tk()
    parameter = ArduPilotParameter("ROLL_P", Par(0.2), fc_value=0.1)
    window.parameters = {"ROLL_P": parameter}
    window.parent.parameter_editor.fc_parameters = {"ROLL_P": 0.2}
    selected_params = ParDict({"ROLL_P": Par(0.2)})
    window.table.get_upload_selected_params.return_value = selected_params
    window.parent.parameter_editor.ensure_upload_preconditions.return_value = True
    window.parent.upload_external_params.return_value = True
    window.close = MagicMock()

    window.upload_parameters()

    assert parameter.fc_value_as_string == "0.2"
    assert not parameter.is_different_from_fc
    window.close.assert_called_once_with()


def test_standalone_upload_host_closes_the_event_loop() -> None:
    """The shared host callback retains the standalone upload close behavior."""
    root = MagicMock()
    host = StandaloneUploadHost(root, MagicMock(), MagicMock(), on_close=root.quit)

    host.repopulate_parameter_table()
    host.on_skip_click()

    root.quit.assert_called_once_with()


def test_closing_external_upload_window_refreshes_parent_table() -> None:
    """Refresh the normal parameter table after the modal is closed."""
    window = _window_without_tk()
    window.root = MagicMock()

    window.close()

    window.root.destroy.assert_called_once_with()
    window.parent.repopulate_parameter_table.assert_called_once_with()


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


@pytest.mark.parametrize("use_current_directory", [False, True])
def test_standalone_reset_preserves_project_defaults_when_defaults_become_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, use_current_directory: bool
) -> None:
    """
    Reset the FC without overwriting a user's project defaults.

    GIVEN: Startup returns no defaults and a project contains ROLL_P,9
    WHEN: Defaults become available after a standalone FC reset
    THEN: Downloads stay in scratch storage and the project file is unchanged.
    """
    vehicle_path = tmp_path / "vehicle"
    vehicle_path.mkdir()
    monkeypatch.chdir(vehicle_path)
    vehicle_dir = "." if use_current_directory else str(vehicle_path)
    default_file = vehicle_path / "00_default.param"
    original_defaults = b"ROLL_P,9\n"
    default_file.write_bytes(original_defaults)
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    flight_controller = MagicMock()
    flight_controller.info.vehicle_type = "ArduCopter"
    flight_controller.info.flight_sw_version = "4.6.0"
    flight_controller.reset_all_parameters_to_default_and_reconnect.return_value = (True, "")
    downloaded_defaults = ParDict({"ROLL_P": Par(0.1)})

    def download_params(
        _progress_callback=None,
        parameter_values_filename: Path | None = None,
        parameter_defaults_filename: Path | None = None,
        **_kwargs,
    ) -> tuple[dict, ParDict]:
        assert parameter_values_filename == scratch_dir / "complete.param"
        assert parameter_defaults_filename == scratch_dir / "00_default.param"
        defaults = downloaded_defaults if flight_controller.download_params.call_count > 1 else ParDict()
        flight_controller.fc_parameters = {"ROLL_P": 0.1}
        ParDict({"ROLL_P": Par(0.1)}).export_to_param(str(parameter_values_filename))
        if defaults:
            defaults.export_to_param(str(parameter_defaults_filename))
        return flight_controller.fc_parameters, defaults

    flight_controller.download_params.side_effect = download_params
    with patch.object(LocalFilesystem, "load_parameter_metadata_for_flight_controller", return_value=""):
        editor = ParameterEditor.for_connected_flight_controller(
            flight_controller, vehicle_dir, parameter_download_dir=scratch_dir
        )
    ui = ParameterEditorUiServices.__new__(ParameterEditorUiServices)
    ui.create_progress_window = MagicMock()
    ui.show_error = MagicMock()
    host = StandaloneUploadHost(MagicMock(), editor, ui, gui_complexity="simple")

    assert host.reset_all_parameters_to_default() is True

    assert flight_controller.download_params.call_count == 2
    assert editor.fc_parameters == {"ROLL_P": 0.1}
    assert default_file.read_bytes() == original_defaults
    assert ParDict.from_file(str(scratch_dir / "00_default.param")) == downloaded_defaults
    ui.show_error.assert_not_called()
    ui.create_progress_window.return_value.destroy.assert_called()


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


def test_standalone_main_uses_shared_parameter_application() -> None:
    """Standalone compare and upload delegates connection and model startup to shared layers."""
    args = Namespace(
        loglevel="INFO",
        reboot_time=8,
        baudrate=115200,
        device="test",
        vehicle_dir="vehicle",
        vehicle_type="ArduPlane",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
    )
    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.argument_parser",
            return_value=args,
        ),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload."
            "run_standalone_parameter_application"
        ) as run_application,
    ):
        standalone_main()

    run_application.assert_called_once()
    called_args, kwargs = run_application.call_args
    assert called_args[0] is args
    assert kwargs["root_factory"]
    assert kwargs["flight_controller_factory"]
    initialize_editor = called_args[1]
    open_window = called_args[2]
    root = MagicMock()
    flight_controller = MagicMock()
    ui = MagicMock()
    ui.askopenfilename.return_value = "external.param"
    parameter_editor = MagicMock()
    parameter_editor.load_external_parameter_file.return_value = {"ROLL_P": MagicMock()}

    with (
        patch(
            "ardupilot_methodic_configurator.data_model_parameter_editor.ParameterEditor.for_connected_flight_controller",
            return_value=parameter_editor,
        ) as create_editor,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.ParameterFileUploadWindow",
        ) as dialog,
    ):
        assert initialize_editor(root, flight_controller, ui) is parameter_editor
        opened_window = open_window(root, parameter_editor, ui)

    ui.askopenfilename.assert_called_once()
    assert ui.askopenfilename.call_args.kwargs["parent"] is root
    create_editor.assert_called_once()
    assert create_editor.call_args.args == (flight_controller, "vehicle", "ArduPlane")
    download_dir = create_editor.call_args.kwargs["parameter_download_dir"]
    assert download_dir.name.startswith("amc-parameter-compare-")
    assert download_dir != Path("vehicle")
    parameter_editor.load_external_parameter_file.assert_called_once_with("external.param")
    dialog.assert_called_once()
    assert opened_window is dialog.return_value


@pytest.mark.parametrize("parent_visible", [False, True])
def test_upload_dialog_centers_on_visible_parent_or_screen(parent_visible: bool) -> None:
    """A withdrawn standalone root must not be used as the centering anchor."""
    host = MagicMock()
    host.root.winfo_viewable.return_value = parent_visible

    def initialize_window(window: ParameterFileUploadWindow, _parent_root: object) -> None:
        window.root = MagicMock()
        window.main_frame = MagicMock()
        window.calculate_scaled_geometry = MagicMock(return_value="500x620")
        window.center_window = MagicMock()
        window.center_window_on_screen = MagicMock()

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.BaseWindow.__init__",
            initialize_window,
        ),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.tk.BooleanVar"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.ttk.Label"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.ttk.Frame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.ttk.Checkbutton"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.ttk.Button"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.ParameterEditorTable"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.show_tooltip"),
    ):
        dialog = ParameterFileUploadWindow(host, "external.param", {})

    if parent_visible:
        dialog.center_window.assert_called_once_with(dialog.root, host.root)
        dialog.center_window_on_screen.assert_not_called()
        dialog.root.transient.assert_called_once_with(host.root)
    else:
        dialog.center_window_on_screen.assert_called_once_with(dialog.root)
        dialog.center_window.assert_not_called()
        dialog.root.transient.assert_not_called()


@pytest.fixture(name="standalone_callbacks")
def _standalone_callbacks() -> tuple:
    """Capture the compare/upload callbacks supplied to the shared application."""
    args = Namespace(loglevel="INFO", reboot_time=8, baudrate=115200, device="", vehicle_dir="vehicle", vehicle_type="Copter")
    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.argument_parser",
            return_value=args,
        ),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload."
            "run_standalone_parameter_application"
        ) as run,
    ):
        standalone_main()
    return run.call_args.args[1:]


def test_cancelling_external_file_selection_skips_model_setup(standalone_callbacks) -> None:
    """
    Cancel standalone compare/upload file selection without loading parameters.

    GIVEN: The flight controller is connected and the file chooser is open
    WHEN: The user cancels the chooser
    THEN: The callback returns no editor and does not start metadata setup
    """
    initialize, _open_dialog = standalone_callbacks
    root = MagicMock()
    ui = MagicMock()
    ui.askopenfilename.return_value = ""
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.initialize_standalone_parameter_editor"
    ) as create_editor:
        result = initialize(root, MagicMock(), ui)

    assert result is None
    assert ui.askopenfilename.call_args.kwargs["parent"] is root
    create_editor.assert_not_called()


def test_invalid_external_file_reports_error_before_opening_dialog(standalone_callbacks) -> None:
    """
    Keep the standalone comparison closed when a selected file cannot be loaded.

    GIVEN: The user selected an invalid parameter file
    WHEN: The model rejects the file
    THEN: The UI reports the file error and no dialog is created
    """
    initialize, open_dialog = standalone_callbacks
    editor = MagicMock()
    editor.load_external_parameter_file.side_effect = ValueError("invalid parameter syntax")
    ui = MagicMock()
    ui.askopenfilename.return_value = "invalid.param"
    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload."
            "initialize_standalone_parameter_editor",
            return_value=editor,
        ),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_compare_and_upload.ParameterFileUploadWindow"
        ) as dialog_type,
    ):
        initialize(MagicMock(), MagicMock(), ui)
        result = open_dialog(MagicMock(), editor, ui)

    assert result is False
    ui.show_error.assert_called_once_with("Parameter file error", "invalid parameter syntax")
    dialog_type.assert_not_called()


def test_standalone_compare_keeps_parameter_download_directory_until_window_closes() -> None:
    """Private FC snapshots stay available for upload validation and resets."""
    ui = MagicMock()
    ui.askopenfilename.return_value = "selected.param"
    editor = MagicMock()
    initialize = MagicMock(return_value=editor)

    def run_tool(_args, initialize_editor, _open_window, **_kwargs) -> None:
        initialize_editor(MagicMock(), MagicMock(), ui)
        download_dir = initialize.call_args.kwargs["parameter_download_dir"]
        assert download_dir.exists()

    with (
        patch.object(compare_module, "argument_parser", return_value=SimpleNamespace()),
        patch.object(compare_module, "initialize_standalone_parameter_editor", new=initialize),
        patch.object(compare_module, "run_standalone_parameter_application", side_effect=run_tool),
    ):
        compare_module.main()

    download_dir = initialize.call_args.kwargs["parameter_download_dir"]
    assert not download_dir.exists()
