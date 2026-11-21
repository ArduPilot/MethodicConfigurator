#!/usr/bin/env python3

"""
Regression tests for generic ArduPlane telemetry serial defaults.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps
from ardupilot_methodic_configurator.data_model_configuration_step import ConfigurationStepProcessor
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

ROOT = Path(__file__).resolve().parents[1] / "ardupilot_methodic_configurator"
STEP = "07_telemetry.param"
TEMPLATES = ("empty_4.7.x", "normal_plane")


def telemetry_filesystem(connection: str, saved: ParDict | None = None) -> MagicMock:
    """Connect real Plane step calculations to the existing step processor."""
    step = json.loads((ROOT / "configuration_steps_ArduPlane.json").read_text(encoding="utf-8"))["steps"][STEP]
    calculations = ConfigurationSteps("", "ArduPlane")
    filesystem = MagicMock()
    filesystem.file_parameters = {STEP: saved if saved is not None else ParDict()}
    filesystem.configuration_steps = {STEP: step}
    filesystem.forced_parameters = calculations.forced_parameters
    filesystem.derived_parameters = calculations.derived_parameters
    filesystem.add_parameters = calculations.add_parameters
    filesystem.param_default_dict = {"RC_OPTIONS": Par(0)}
    filesystem.doc_dict = {}
    filesystem.get_eval_variables.return_value = {
        "vehicle_components": {"Telemetry": {"FC Connection": {"Type": connection, "Protocol": 2}}}
    }
    filesystem.compute_forced_and_derived_parameters.side_effect = calculations.compute_forced_and_derived_parameters
    filesystem.compute_deletions.side_effect = calculations.compute_deletions
    filesystem.compute_add_parameters.side_effect = calculations.compute_add_parameters
    return filesystem


@pytest.mark.parametrize("template", TEMPLATES)
def test_generic_telemetry_step_is_empty_but_loadable(template: str) -> None:
    """Neither generic Plane template assigns a port, baud rate, or flow control."""
    path = ROOT / "vehicle_templates" / "ArduPlane" / template / STEP
    assert path.is_file()
    assert not ParDict.from_file(str(path))


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("connection", ["None", "SERIAL1", "SERIAL2", "SERIAL4"])
def test_selected_telemetry_port_is_the_only_derived_setting(template: str, connection: str) -> None:
    """An empty step derives only the chosen protocol, with no inferred baud or flow control."""
    saved = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / template / STEP))
    filesystem = telemetry_filesystem(connection, saved)
    parameters, errors, _infos, _duplicates, _renames, derived, imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {})

    expected = {} if connection == "None" else {f"{connection}_PROTOCOL": 2}
    assert not errors
    assert not parameters
    assert {name: param.value for name, param in derived.items()} == expected
    assert imported == set()


def test_saved_baud_and_other_serial_settings_survive_unchanged_connection() -> None:
    """Saved project settings remain when the chosen telemetry connection has not moved."""
    saved = ParDict({"SERIAL2_BAUD": Par(115, "radio baud"), "SERIAL2_PROTOCOL": Par(2, "saved protocol")})
    filesystem = telemetry_filesystem("SERIAL2", saved)
    parameters, errors, _infos, duplicates, renames, derived, _imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {"SERIAL2_BAUD": 115, "SERIAL2_PROTOCOL": 0})

    assert not errors
    assert duplicates == set()
    assert not renames
    assert parameters["SERIAL2_BAUD"].get_new_value() == 115
    assert parameters["SERIAL2_BAUD"].change_reason == "radio baud"
    assert parameters["SERIAL2_PROTOCOL"].get_new_value() == 2
    assert derived["SERIAL2_PROTOCOL"].value == 2


def test_existing_connection_rename_moves_saved_baud_with_selected_port() -> None:
    """A saved radio baud setting follows the existing serial-port rename workflow."""
    filesystem = telemetry_filesystem("SERIAL4", ParDict({"SERIAL2_BAUD": Par(115, "radio baud")}))
    _parameters, errors, _infos, _duplicates, renames, derived, _imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {"SERIAL2_BAUD": 115, "SERIAL4_PROTOCOL": 0})

    assert not errors
    assert renames == [("SERIAL2_BAUD", "SERIAL4_BAUD")]
    assert derived["SERIAL4_PROTOCOL"].value == 2


def test_empty_step_derived_protocol_is_added_to_editor_table_model() -> None:
    """The editor presents and tracks a protocol derived from an initially empty step."""
    filesystem = telemetry_filesystem("SERIAL4")
    flight_controller = MagicMock()
    flight_controller.fc_parameters = {}
    editor = ParameterEditor(STEP, flight_controller, filesystem)

    errors, _infos = editor._repopulate_configuration_step_parameters()  # pylint: disable=protected-access

    assert not errors
    assert set(editor.current_step_parameters) == {"SERIAL4_PROTOCOL"}
    assert editor.current_step_parameters["SERIAL4_PROTOCOL"].get_new_value() == 2
    assert "SERIAL4_PROTOCOL" in editor._added_parameters  # pylint: disable=protected-access


def test_saved_serial_setting_survives_without_autoimporting_unrelated_fc_values() -> None:
    """The telemetry step keeps saved settings and follows its no-autoimport rule."""
    filesystem = telemetry_filesystem("None", ParDict({"SERIAL2_BAUD": Par(115, "saved radio")}))
    parameters, errors, _infos, _duplicates, _renames, derived, imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {"SERIAL2_BAUD": 115, "RC_OPTIONS": 32})

    assert not errors
    assert parameters["SERIAL2_BAUD"].get_new_value() == 115
    assert not derived
    assert imported == set()
    assert "RC_OPTIONS" not in parameters
