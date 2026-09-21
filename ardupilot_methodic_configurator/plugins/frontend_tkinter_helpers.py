"""
Shared helpers for Tkinter plugin views.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Collection


def refresh_parameter_editor_table(base_window: object) -> None:
    """Refresh the parameter table using the current window display settings."""
    parameter_editor_table = getattr(base_window, "parameter_editor_table", None)
    if parameter_editor_table is None:
        return
    show_only_differences_var = getattr(base_window, "show_only_differences", None)
    show_only_differences = show_only_differences_var.get() if show_only_differences_var else False
    gui_complexity = getattr(base_window, "gui_complexity", "simple")
    parameter_editor_table.repopulate_table(show_only_differences=show_only_differences, gui_complexity=gui_complexity)


def refresh_parameter_editor_after_calibration(
    base_window: object,
    parameter_names_to_copy: Collection[str] | None = None,
    download: bool = True,
) -> None:
    """
    Read back calibration results and refresh the active parameter table.

    ``download_flight_controller_parameters`` updates each parameter's FC column.
    Copying those values into staged ``new_value`` fields is therefore opt-in and
    limited to the parameters the calibration is known to have changed.
    """
    if download:
        download_parameters = getattr(base_window, "download_flight_controller_parameters", None)
        if callable(download_parameters):
            download_parameters(redownload=True)

    parameter_editor = getattr(base_window, "parameter_editor", None)
    if not download:
        refresh_fc_values = getattr(parameter_editor, "refresh_current_step_fc_values", None)
        if callable(refresh_fc_values):
            refresh_fc_values()

    update_parameters = getattr(parameter_editor, "update_parameters_from_fc_values", None)
    if callable(update_parameters) and parameter_names_to_copy:
        fc_parameters = getattr(parameter_editor, "fc_parameters", {})
        relevant_fc_params = {
            parameter_name: fc_parameters[parameter_name]
            for parameter_name in parameter_names_to_copy
            if parameter_name in fc_parameters
        }
        if relevant_fc_params:
            update_parameters(relevant_fc_params)

    repopulate_table = getattr(base_window, "repopulate_parameter_table", None)
    if callable(repopulate_table):
        repopulate_table()
    else:
        refresh_parameter_editor_table(base_window)
