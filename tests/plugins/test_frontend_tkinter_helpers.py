#!/usr/bin/env python3

"""
Behavior-driven tests for shared Tkinter plugin helpers.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import (
    apply_calibration_readback,
    refresh_parameter_editor_table,
)


def test_user_sees_the_parameter_table_refreshed_with_window_display_settings() -> None:
    """
    A plugin refreshes the parameter table with the active display settings.

    GIVEN: A base window has a parameter table and display preferences
    WHEN: A plugin asks for the parameter table to be refreshed
    THEN: The table is repopulated with those preferences
    """
    # Arrange (Given)
    parameter_editor_table = MagicMock()
    base_window = SimpleNamespace(
        parameter_editor_table=parameter_editor_table,
        show_only_differences=SimpleNamespace(get=lambda: True),
        gui_complexity="advanced",
    )

    # Act (When)
    refresh_parameter_editor_table(base_window)

    # Assert (Then)
    parameter_editor_table.repopulate_table.assert_called_once_with(show_only_differences=True, gui_complexity="advanced")


def test_user_sees_known_calibration_values_applied_after_a_worker_has_already_downloaded_them() -> None:
    """
    Applying a completed worker readback does not start a second download.

    GIVEN: A background operation already refreshed the flight-controller parameter cache
    WHEN: The UI applies its calibration readback
    THEN: The current step is refreshed and only known calibration values are staged
    """
    parameter_editor = SimpleNamespace(
        fc_parameters={"AHRS_TRIM_X": 0.01},
        refresh_current_step_fc_values=MagicMock(),
        update_parameters_from_fc_values=MagicMock(),
    )
    base_window = SimpleNamespace(
        download_flight_controller_parameters=MagicMock(),
        parameter_editor=parameter_editor,
        repopulate_parameter_table=MagicMock(),
    )

    apply_calibration_readback(base_window, parameter_names_to_copy={"AHRS_TRIM_X"})

    base_window.download_flight_controller_parameters.assert_not_called()
    parameter_editor.refresh_current_step_fc_values.assert_called_once_with()
    parameter_editor.update_parameters_from_fc_values.assert_called_once_with({"AHRS_TRIM_X": 0.01})
    base_window.repopulate_parameter_table.assert_called_once_with()
