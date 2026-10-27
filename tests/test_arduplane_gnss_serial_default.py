#!/usr/bin/env python3

"""
Regression tests for ArduPlane GNSS serial transport selection.

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
STEP = "18_gnss.param"
TEMPLATES = ("empty_4.7.x", "normal_plane")
GPS_DRIVERS = {
    "None": 0,
    "AUTO": 1,
    "uBlox": 2,
    "NMEA": 5,
    "HIL": 7,
    "DroneCAN": 9,
    "MAVLink": 14,
    "MSP": 19,
    "ExternalAHRS": 21,
}


def gnss_filesystem(connection: str, driver: str, version: str, saved: ParDict) -> MagicMock:
    """Use the real Plane step calculations with a project and component selection."""
    step = json.loads((ROOT / "configuration_steps_ArduPlane.json").read_text(encoding="utf-8"))["steps"][STEP]
    calculations = ConfigurationSteps("", "ArduPlane")
    filesystem = MagicMock()
    filesystem.file_parameters = {STEP: saved}
    filesystem.configuration_steps = {STEP: step}
    filesystem.forced_parameters = calculations.forced_parameters
    filesystem.derived_parameters = calculations.derived_parameters
    filesystem.add_parameters = calculations.add_parameters
    filesystem.param_default_dict = {"GPS1_GNSS_MODE": Par(0), "GPS1_TYPE": Par(1)}
    filesystem.doc_dict = {
        "GPS_TYPE": {"values": {str(number): name for name, number in GPS_DRIVERS.items()}},
        "GPS1_TYPE": {"values": {str(number): name for name, number in GPS_DRIVERS.items()}},
    }
    filesystem.get_eval_variables.return_value = {
        "vehicle_components": {
            "Flight Controller": {"Firmware": {"Version": version}},
            "GNSS Receiver": {"FC Connection": {"Type": connection, "Protocol": driver}},
        },
        "doc_dict": filesystem.doc_dict,
    }
    filesystem.compute_forced_and_derived_parameters.side_effect = calculations.compute_forced_and_derived_parameters
    filesystem.compute_parameters.side_effect = calculations.compute_parameters
    filesystem.compute_deletions.side_effect = calculations.compute_deletions
    filesystem.compute_add_parameters.side_effect = calculations.compute_add_parameters
    return filesystem


@pytest.mark.parametrize("template", TEMPLATES)
def test_generic_plane_gnss_template_does_not_choose_serial3(template: str) -> None:
    """The Plane templates keep all other GNSS settings but no UART default."""
    parameters = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / template / STEP))
    assert "SERIAL3_PROTOCOL" not in parameters
    assert "BRD_SAFETY_DEFLT" in parameters
    assert {name for name in parameters if name.startswith("SERIAL")} == set()


@pytest.mark.parametrize("template_case", [("empty_4.7.x", "4.7.2", "GPS1_TYPE"), ("normal_plane", "4.5.7", "GPS_TYPE")])
@pytest.mark.parametrize(
    "gnss_case",
    [
        ("None", "None", None),
        ("SERIAL3", "AUTO", "SERIAL3_PROTOCOL"),
        ("SERIAL2", "uBlox", "SERIAL2_PROTOCOL"),
        ("SERIAL4", "NMEA", "SERIAL4_PROTOCOL"),
        ("CAN1", "DroneCAN", None),
        ("SERIAL3", "MAVLink", None),
        ("SERIAL3", "MSP", None),
        ("SERIAL3", "HIL", None),
        ("SERIAL3", "ExternalAHRS", None),
    ],
)
def test_gnss_step_derives_driver_and_only_physical_gps_serial_transport(
    template_case: tuple[str, str, str], gnss_case: tuple[str, str, str | None]
) -> None:
    """Physical serial GNSS gets transport 5 while other positioning paths do not."""
    template, version, gps_parameter = template_case
    saved = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / template / STEP))
    filesystem = gnss_filesystem(gnss_case[0], gnss_case[1], version, saved)
    _parameters, errors, _infos, _duplicates, _renames, derived, _imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {})

    assert not errors
    assert derived[gps_parameter].value == GPS_DRIVERS[gnss_case[1]]
    serial = {name: param.value for name, param in derived.items() if name.startswith("SERIAL")}
    assert serial == ({gnss_case[2]: 5} if gnss_case[2] else {})


def test_saved_serial_setting_and_eligible_fc_import_are_preserved() -> None:
    """Saved port settings survive and the existing GNSS import rule still applies."""
    saved = ParDict({"SERIAL2_PROTOCOL": Par(5, "saved GPS port"), "SERIAL2_BAUD": Par(115, "saved baud")})
    filesystem = gnss_filesystem("SERIAL2", "uBlox", "4.7.2", saved)
    parameters, errors, _infos, duplicates, renames, derived, imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(
        STEP, {"SERIAL2_PROTOCOL": 5, "SERIAL2_BAUD": 115, "GPS1_GNSS_MODE": 3, "SERIAL3_PROTOCOL": 2}
    )

    assert not errors
    assert not duplicates
    assert not renames
    assert parameters["SERIAL2_PROTOCOL"].get_new_value() == 5
    assert parameters["SERIAL2_BAUD"].get_new_value() == 115
    assert parameters["SERIAL2_BAUD"].change_reason == "saved baud"
    assert derived["SERIAL2_PROTOCOL"].value == 5
    assert imported == {"GPS1_GNSS_MODE"}
    assert parameters["GPS1_GNSS_MODE"].get_new_value() == 3
    assert "SERIAL3_PROTOCOL" not in parameters


def test_existing_gnss_connection_rename_moves_saved_baud() -> None:
    """A project baud setting follows the selected port through existing rename logic."""
    filesystem = gnss_filesystem("SERIAL4", "uBlox", "4.7.2", ParDict({"SERIAL3_BAUD": Par(115)}))
    _parameters, errors, _infos, _duplicates, renames, derived, _imported = ConfigurationStepProcessor(
        filesystem
    ).process_configuration_step(STEP, {})

    assert not errors
    assert renames == [("SERIAL3_BAUD", "SERIAL4_BAUD")]
    assert derived["SERIAL4_PROTOCOL"].value == 5


def test_editor_displays_derived_gnss_serial_protocol() -> None:
    """A newly selected physical UART protocol appears in the editor table model."""
    saved = ParDict.from_file(str(ROOT / "vehicle_templates" / "ArduPlane" / "empty_4.7.x" / STEP))
    filesystem = gnss_filesystem("SERIAL2", "uBlox", "4.7.2", saved)
    flight_controller = MagicMock()
    flight_controller.fc_parameters = {}
    editor = ParameterEditor(STEP, flight_controller, filesystem)

    errors, _infos = editor._repopulate_configuration_step_parameters()  # pylint: disable=protected-access

    assert not errors
    assert editor.current_step_parameters["SERIAL2_PROTOCOL"].get_new_value() == 5
    assert "SERIAL2_PROTOCOL" in editor._added_parameters  # pylint: disable=protected-access
