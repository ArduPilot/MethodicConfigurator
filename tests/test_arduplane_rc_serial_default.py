#!/usr/bin/env python3

"""
Regression tests for generic ArduPlane RC receiver serial assignments.

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

ROOT = Path(__file__).resolve().parents[1] / "ardupilot_methodic_configurator"
STEP = "05_remote_controller_receiver.param"
TEMPLATES = ("empty_4.7.x", "normal_plane")


@pytest.mark.parametrize("template", TEMPLATES)
def test_generic_plane_template_has_no_serial2_rc_default(template: str) -> None:
    """Generic receiver files must not choose a serial port for the aircraft."""
    parameters = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / template / STEP))
    assert "SERIAL2_PROTOCOL" not in parameters


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize(
    ("connection", "expected_port"),
    [("SERIAL2", "SERIAL2_PROTOCOL"), ("SERIAL3", "SERIAL3_PROTOCOL"), ("RCIN", None)],
)
def test_receiver_connection_derives_only_selected_serial_port(
    template: str, connection: str, expected_port: str | None
) -> None:
    """The existing Plane step computes RCIN only for the selected serial connection."""
    saved = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / template / STEP))
    step = json.loads((ROOT / "configuration_steps_ArduPlane.json").read_text(encoding="utf-8"))["steps"][STEP]
    calculations = ConfigurationSteps("", "ArduPlane")
    filesystem = MagicMock()
    filesystem.file_parameters = {STEP: saved}
    filesystem.configuration_steps = {STEP: step}
    filesystem.forced_parameters = calculations.forced_parameters
    filesystem.derived_parameters = calculations.derived_parameters
    filesystem.param_default_dict = {}
    filesystem.doc_dict = {}
    filesystem.get_eval_variables.return_value = {
        "vehicle_components": {"RC Receiver": {"FC Connection": {"Type": connection, "Protocol": 1}}}
    }
    filesystem.compute_forced_and_derived_parameters.side_effect = calculations.compute_forced_and_derived_parameters
    filesystem.compute_deletions.side_effect = calculations.compute_deletions
    filesystem.compute_add_parameters.side_effect = calculations.compute_add_parameters

    parameters, errors, _infos, _duplicates, _renames, derived, imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {})

    assert not errors
    assert imported == set()
    assert "SERIAL2_PROTOCOL" not in parameters
    serial_assignments = {name: param.value for name, param in derived.items() if name.startswith("SERIAL")}
    assert serial_assignments == ({expected_port: 23} if expected_port else {})


def test_saved_serial_setting_and_imported_rc_parameter_are_preserved() -> None:
    """The step keeps saved serial settings and imports eligible nondefault FC RC values."""
    step = json.loads((ROOT / "configuration_steps_ArduPlane.json").read_text(encoding="utf-8"))["steps"][STEP]
    calculations = ConfigurationSteps("", "ArduPlane")
    filesystem = MagicMock()
    filesystem.file_parameters = {STEP: ParDict({"SERIAL2_PROTOCOL": Par(2, "saved telemetry")})}
    filesystem.configuration_steps = {STEP: step}
    filesystem.forced_parameters = calculations.forced_parameters
    filesystem.derived_parameters = calculations.derived_parameters
    filesystem.param_default_dict = {"RC_OPTIONS": Par(0)}
    filesystem.doc_dict = {}
    filesystem.get_eval_variables.return_value = {
        "vehicle_components": {"RC Receiver": {"FC Connection": {"Type": "SERIAL3", "Protocol": 1}}}
    }
    filesystem.compute_forced_and_derived_parameters.side_effect = calculations.compute_forced_and_derived_parameters
    filesystem.compute_deletions.side_effect = calculations.compute_deletions
    filesystem.compute_add_parameters.side_effect = calculations.compute_add_parameters

    parameters, errors, _infos, _duplicates, _renames, derived, imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {"SERIAL2_PROTOCOL": 2, "SERIAL3_PROTOCOL": 0, "RC_OPTIONS": 32})

    assert not errors
    assert parameters["SERIAL2_PROTOCOL"].get_new_value() == 2
    assert parameters["SERIAL2_PROTOCOL"].change_reason == "saved telemetry"
    assert derived["SERIAL3_PROTOCOL"].value == 23
    assert imported == {"RC_OPTIONS"}
    assert parameters["RC_OPTIONS"].get_new_value() == 32
