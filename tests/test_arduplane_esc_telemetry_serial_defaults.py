#!/usr/bin/env python3

"""
Regression tests for generic ArduPlane ESC telemetry serial defaults.

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
STEP = "08_esc_telemetry.param"
TEMPLATES = ("empty_4.7.x", "normal_plane")


def esc_filesystem(
    connection: str,
    telemetry_protocol: str,
    control_protocol: str = "Normal",
    saved: ParDict | None = None,
    control_type: str = "Main Out",
) -> MagicMock:
    """Run the actual Plane step rules with documented parameter value mappings."""
    step = json.loads((ROOT / "configuration_steps_ArduPlane.json").read_text(encoding="utf-8"))["steps"][STEP]
    calculations = ConfigurationSteps("", "ArduPlane")
    filesystem = MagicMock()
    filesystem.file_parameters = {STEP: saved if saved is not None else ParDict()}
    filesystem.configuration_steps = {STEP: step}
    filesystem.forced_parameters = calculations.forced_parameters
    filesystem.derived_parameters = calculations.derived_parameters
    filesystem.add_parameters = calculations.add_parameters
    filesystem.param_default_dict = {"SERVO_BLH_TRATE": Par(10)}
    filesystem.doc_dict = {
        "Q_M_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}},
        "SERIAL3_PROTOCOL": {"values": {"16": "ESC Telemetry", "28": "Scripting", "38": "FETtecOneWire"}},
        "SERIAL5_PROTOCOL": {"values": {"16": "ESC Telemetry", "28": "Scripting", "38": "FETtecOneWire"}},
    }
    filesystem.get_eval_variables.return_value = {
        "vehicle_components": {
            "ESC": {
                "FC->ESC Connection": {"Type": control_type, "Protocol": control_protocol},
                "ESC->FC Telemetry": {"Type": connection, "Protocol": telemetry_protocol},
            }
        },
        "doc_dict": filesystem.doc_dict,
    }
    filesystem.compute_forced_and_derived_parameters.side_effect = calculations.compute_forced_and_derived_parameters
    filesystem.compute_deletions.side_effect = calculations.compute_deletions
    filesystem.compute_add_parameters.side_effect = calculations.compute_add_parameters
    return filesystem


@pytest.mark.parametrize("template", TEMPLATES)
def test_generic_esc_template_retains_only_nonserial_settings(template: str) -> None:
    """The generic files keep ESC settings while dropping hardware-specific SERIAL5 values."""
    parameters = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / template / STEP))
    assert "SERIAL5_BAUD" not in parameters
    assert "SERIAL5_PROTOCOL" not in parameters
    assert parameters["SERVO_BLH_TRATE"].value == 10
    if template == "normal_plane":
        assert parameters["Q_M_PWM_TYPE"].value == 0
    else:
        assert "Q_M_PWM_TYPE" not in parameters


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize(
    ("connection", "protocol", "control", "expected"),
    [
        ("None", "None", "Normal", {"Q_M_PWM_TYPE": 0}),
        ("SERIAL5", "ESC Telemetry", "DShot600", {"Q_M_PWM_TYPE": 6, "SERIAL5_PROTOCOL": 16}),
        ("SERIAL3", "ESC Telemetry", "DShot600", {"Q_M_PWM_TYPE": 6, "SERIAL3_PROTOCOL": 16}),
        ("SERIAL5", "Scripting", "Normal", {"Q_M_PWM_TYPE": 0, "SERIAL5_PROTOCOL": 28, "SCR_ENABLE": 1}),
        ("Main Out", "BDShotOnly", "DShot600", {"Q_M_PWM_TYPE": 6}),
        ("SERIAL3", "FETtecOneWire", "Normal", {"Q_M_PWM_TYPE": 0, "SERIAL3_PROTOCOL": 38}),
    ],
)
def test_esc_connection_derives_only_selected_serial_protocol(
    template: str, connection: str, protocol: str, control: str, expected: dict[str, int]
) -> None:
    """None, UART, scripting, BDShot, and OneWire telemetry follow existing rules."""
    saved = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / template / STEP))
    filesystem = esc_filesystem(connection, protocol, control, saved)
    parameters, errors, _infos, _duplicates, _renames, derived, _imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {})

    assert not errors
    assert {name: param.value for name, param in derived.items()} == expected
    assert not any(name.startswith("SERIAL5") for name in parameters)
    assert not any(name.endswith("_BAUD") for name in derived)


def test_serial_esc_control_still_derives_onewire_protocol() -> None:
    """Same-port FETtec control retains its serial protocol without a SERIAL5 default."""
    filesystem = esc_filesystem("SERIAL3", "FETtecOneWire", "FETtecOneWire", control_type="SERIAL3")
    parameters, errors, _infos, _duplicates, _renames, derived, _imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {})

    assert not errors
    assert not parameters
    assert {name: param.value for name, param in derived.items()} == {"SERIAL3_PROTOCOL": 38}


def test_saved_esc_uart_baud_and_protocol_remain_when_port_is_unchanged() -> None:
    """Existing project serial values are retained on the selected telemetry port."""
    saved = ParDict({"SERIAL5_BAUD": Par(115, "saved baud"), "SERIAL5_PROTOCOL": Par(16, "saved protocol")})
    filesystem = esc_filesystem("SERIAL5", "ESC Telemetry", "DShot600", saved)
    parameters, errors, _infos, duplicates, renames, derived, _imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {"SERIAL5_BAUD": 115, "SERIAL5_PROTOCOL": 16})

    assert not errors
    assert not duplicates
    assert not renames
    assert parameters["SERIAL5_BAUD"].get_new_value() == 115
    assert parameters["SERIAL5_BAUD"].change_reason == "saved baud"
    assert parameters["SERIAL5_PROTOCOL"].get_new_value() == 16
    assert derived["SERIAL5_PROTOCOL"].value == 16


def test_esc_step_imports_eligible_fc_value_without_importing_serial_baud() -> None:
    """Only the step's existing SERVO_BLH_TRATE import rule adds a nondefault FC value."""
    filesystem = esc_filesystem("None", "None")
    parameters, errors, _infos, _duplicates, _renames, derived, imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {"SERVO_BLH_TRATE": 12, "SERIAL5_BAUD": 115})

    assert not errors
    assert imported == {"SERVO_BLH_TRATE"}
    assert parameters["SERVO_BLH_TRATE"].get_new_value() == 12
    assert "SERIAL5_BAUD" not in parameters
    assert "SERIAL5_PROTOCOL" not in derived


def test_editor_displays_derived_uart_protocol_missing_from_template() -> None:
    """The editor adds a selected UART protocol absent from the generic ESC step file."""
    saved = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / "empty_4.7.x" / STEP))
    filesystem = esc_filesystem("SERIAL5", "ESC Telemetry", "DShot600", saved)
    flight_controller = MagicMock()
    flight_controller.fc_parameters = {}
    editor = ParameterEditor(STEP, flight_controller, filesystem)

    errors, _infos = editor._repopulate_configuration_step_parameters()  # pylint: disable=protected-access

    assert not errors
    assert editor.current_step_parameters["SERIAL5_PROTOCOL"].get_new_value() == 16
    assert "SERIAL5_PROTOCOL" in editor._added_parameters  # pylint: disable=protected-access
