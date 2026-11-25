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

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import (
    refresh_parameter_editor_after_calibration,
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


def test_calibration_refresh_copies_only_known_changed_parameters() -> None:
    """Calibration readback must not overwrite unrelated staged edits."""
    parameter_editor = SimpleNamespace(
        fc_parameters={"AHRS_TRIM_X": 0.01, "INS_GYRO_FILTER": 42.0},
        current_step_parameters={"AHRS_TRIM_X": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
    )
    base_window = SimpleNamespace(
        download_flight_controller_parameters=MagicMock(),
        parameter_editor=parameter_editor,
        repopulate_parameter_table=MagicMock(),
    )

    refresh_parameter_editor_after_calibration(base_window, parameter_names_to_copy={"AHRS_TRIM_X"})

    parameter_editor.update_parameters_from_fc_values.assert_called_once_with({"AHRS_TRIM_X": 0.01})
    base_window.repopulate_parameter_table.assert_called_once_with()


def test_calibration_refresh_does_not_copy_parameters_outside_the_active_step() -> None:
    """Calibration readback never asks the editor to copy parameters absent from the active step."""
    parameter_editor = SimpleNamespace(
        fc_parameters={"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02},
        current_step_parameters={"INS_GYRO_FILTER": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
    )
    base_window = SimpleNamespace(
        download_flight_controller_parameters=MagicMock(),
        parameter_editor=parameter_editor,
        repopulate_parameter_table=MagicMock(),
    )

    refresh_parameter_editor_after_calibration(
        base_window,
        parameter_names_to_copy={"AHRS_TRIM_X", "AHRS_TRIM_Y"},
    )

    parameter_editor.update_parameters_from_fc_values.assert_not_called()
    base_window.repopulate_parameter_table.assert_called_once_with()


def test_calibration_refresh_does_not_copy_stale_cache_after_failed_readback() -> None:
    """A failed parameter download must not stage values left in the pre-calibration cache."""
    parameter_editor = SimpleNamespace(
        fc_parameters={"AHRS_TRIM_X": 0.01},
        current_step_parameters={"AHRS_TRIM_X": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
        find_other_steps_with_stale_calibration_values=MagicMock(),
    )
    base_window = SimpleNamespace(
        download_flight_controller_parameters=MagicMock(return_value=({}, {})),
        parameter_editor=parameter_editor,
        repopulate_parameter_table=MagicMock(),
    )

    stale_files = refresh_parameter_editor_after_calibration(
        base_window,
        parameter_names_to_copy={"AHRS_TRIM_X"},
        check_other_steps=True,
    )

    assert stale_files == []
    parameter_editor.update_parameters_from_fc_values.assert_not_called()
    parameter_editor.find_other_steps_with_stale_calibration_values.assert_not_called()
    base_window.repopulate_parameter_table.assert_called_once_with()


def test_calibration_refresh_without_download_updates_fc_value_of_changed_rows() -> None:
    """
    A value saved to the FC without a re-download is not shown as pending upload.

    GIVEN: A parameter whose FC value is stale after the plugin wrote a new value to the FC
    WHEN: The calibration refresh copies the readback without downloading
    THEN: The row's FC and staged values both match the readback, so it does not differ from the FC
    """
    # Arrange (Given)
    parameter = ArduPilotParameter("MOT_SPIN_ARM", Par(0.1, ""), {}, fc_value=0.1)
    parameter_editor = SimpleNamespace(
        fc_parameters={"MOT_SPIN_ARM": 0.15},
        current_step_parameters={"MOT_SPIN_ARM": parameter},
    )
    parameter_editor.update_parameters_from_fc_values = lambda values: [
        parameter.set_new_value(str(value), ignore_out_of_range=True) for value in values.values()
    ]
    base_window = SimpleNamespace(parameter_editor=parameter_editor, repopulate_parameter_table=MagicMock())

    # Act (When)
    refresh_parameter_editor_after_calibration(base_window, {"MOT_SPIN_ARM"}, redownload=False)

    # Assert (Then)
    assert parameter.get_new_value() == 0.15
    assert parameter.fc_value_as_string == "0.15"
    assert not parameter.is_different_from_fc


def test_calibration_refresh_can_keep_the_current_step_open_when_nothing_differs() -> None:
    """A plugin that is still in use asks for a refresh that never skips to the next step."""
    base_window = SimpleNamespace(
        repopulate_parameter_table=MagicMock(),
        repopulate_parameter_table_without_skipping=MagicMock(),
    )

    refresh_parameter_editor_after_calibration(base_window, redownload=False, skip_when_no_differences=False)

    base_window.repopulate_parameter_table_without_skipping.assert_called_once_with()
    base_window.repopulate_parameter_table.assert_not_called()
