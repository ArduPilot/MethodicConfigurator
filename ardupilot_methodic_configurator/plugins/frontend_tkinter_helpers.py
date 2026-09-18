"""
Shared helpers for Tkinter plugin views.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""


def refresh_parameter_editor_table(base_window: object) -> None:
    """Refresh the parameter table using the current window display settings."""
    parameter_editor_table = getattr(base_window, "parameter_editor_table", None)
    if parameter_editor_table is None:
        return
    show_only_differences_var = getattr(base_window, "show_only_differences", None)
    show_only_differences = show_only_differences_var.get() if show_only_differences_var else False
    gui_complexity = getattr(base_window, "gui_complexity", "simple")
    parameter_editor_table.repopulate_table(show_only_differences=show_only_differences, gui_complexity=gui_complexity)


def refresh_parameter_editor_after_calibration(base_window: object) -> None:
    """Read back calibration results and update the active parameter table."""
    download_parameters = getattr(base_window, "download_flight_controller_parameters", None)
    if callable(download_parameters):
        download_parameters(redownload=True)

    parameter_editor = getattr(base_window, "parameter_editor", None)
    update_parameters = getattr(parameter_editor, "update_parameters_from_fc_values", None)
    if callable(update_parameters):
        update_parameters()

    repopulate_table = getattr(base_window, "repopulate_parameter_table", None)
    if callable(repopulate_table):
        repopulate_table()
    else:
        refresh_parameter_editor_table(base_window)
