"""
Shared helpers for Tkinter plugin views.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable, Collection
from typing import cast

from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock


def begin_calibration_navigation_lock(base_window: object, owner: object) -> bool:
    """Prevent competing calibrations and acquire the host's shared navigation lock."""
    navigation_lock = getattr(base_window, "navigation_lock", None)
    if isinstance(navigation_lock, NavigationLock):
        if navigation_lock.locked:
            return False
        navigation_lock.acquire(owner)
    return True


def end_calibration_navigation_lock(base_window: object, owner: object) -> None:
    """Release only this calibration's lock, also when a plugin is torn down."""
    navigation_lock = getattr(base_window, "navigation_lock", None)
    if isinstance(navigation_lock, NavigationLock):
        navigation_lock.release(owner)


def start_calibration_with_navigation_lock(base_window: object, owner: object, start: Callable[[], bool]) -> None:
    """Retain navigation for an asynchronous calibration, but release on failed startup."""
    if not begin_calibration_navigation_lock(base_window, owner):
        return
    started = False
    try:
        started = start()
    finally:
        if not started:
            end_calibration_navigation_lock(base_window, owner)


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
    *,
    check_other_steps: bool = False,
    redownload: bool = True,
) -> list[str]:
    """
    Download calibration results and refresh the active parameter table.

    Copying downloaded values into staged ``new_value`` fields is opt-in and
    limited to parameters the calibration is known to have changed. Optionally
    return names of other steps containing stale values, without changing them.
    """
    download_parameters = getattr(base_window, "download_flight_controller_parameters", None)
    readback_succeeded = True
    if redownload and callable(download_parameters):
        download_result = download_parameters(redownload=True)
        if isinstance(download_result, tuple):
            readback_succeeded = bool(download_result and download_result[0])

    parameter_editor = getattr(base_window, "parameter_editor", None)
    stale_files: list[str] = []
    if parameter_names_to_copy and readback_succeeded:
        stale_files = _copy_calibration_values(
            parameter_editor,
            parameter_names_to_copy,
            check_other_steps=check_other_steps,
        )

    repopulate_table = getattr(base_window, "repopulate_parameter_table", None)
    if callable(repopulate_table):
        repopulate_table()
    else:
        refresh_parameter_editor_table(base_window)
    return stale_files


def _copy_calibration_values(
    parameter_editor: object,
    parameter_names_to_copy: Collection[str],
    *,
    check_other_steps: bool,
) -> list[str]:
    """Stage selected calibration readback values and optionally find stale steps."""
    fc_parameters = getattr(parameter_editor, "fc_parameters", {})
    current_step_parameters = getattr(parameter_editor, "current_step_parameters", {}) or {}
    calibration_values = {name: fc_parameters[name] for name in parameter_names_to_copy if name in fc_parameters}
    relevant_fc_params = {name: value for name, value in calibration_values.items() if name in current_step_parameters}

    update_parameters = getattr(parameter_editor, "update_parameters_from_fc_values", None)
    if callable(update_parameters) and relevant_fc_params:
        update_parameters(relevant_fc_params)

    find_stale_steps = getattr(parameter_editor, "find_other_steps_with_stale_calibration_values", None)
    if check_other_steps and callable(find_stale_steps) and calibration_values:
        return cast("Callable[[dict[str, float]], list[str]]", find_stale_steps)(calibration_values)
    return []
