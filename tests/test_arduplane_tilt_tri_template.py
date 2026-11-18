#!/usr/bin/env python3

"""
Tests for the HeeWing T1-S Ranger tilt-rotor tricopter VTOL ArduPlane template.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import copy
import json
from pathlib import Path

import pytest

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps
from ardupilot_methodic_configurator.data_model_par_dict import ParDict

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "ardupilot_methodic_configurator"
TEMPLATE_DIR = PACKAGE_DIR / "vehicle_templates" / "ArduPlane" / "HeeWing_T1-S_Ranger_VTOL"
PLANE_STEPS_FILE = PACKAGE_DIR / "configuration_steps_ArduPlane.json"


def _step(file_name: str) -> ParDict:
    return ParDict.from_file(str(TEMPLATE_DIR / file_name))


def _components() -> dict:
    with (TEMPLATE_DIR / "vehicle_components.json").open(encoding="utf-8") as file:
        return json.load(file)["Components"]


def _plane_steps() -> dict:
    with PLANE_STEPS_FILE.open(encoding="utf-8") as file:
        return json.load(file)["steps"]


def _first_step_setting(parameter_name: str) -> int:
    """Return the numeric prefix of the first template step that sets the parameter."""
    for parameter_file in sorted(TEMPLATE_DIR.glob("[0-9][0-9]_*.param")):
        if parameter_file.name != "00_default.param" and parameter_name in ParDict.from_file(str(parameter_file)):
            return int(parameter_file.name[:2])
    msg = f"{parameter_name} is not set by any template step"
    raise AssertionError(msg)


def test_quadplane_enable_parameters_are_staged_across_reboots() -> None:
    """
    QuadPlane and tilt-rotor parameters only appear after the enabling reboot.

    GIVEN: The tilt-tri template step files
    WHEN: The steps that enable QuadPlane, select the frame and configure the tilt mechanism are compared
    THEN: Q_ENABLE comes first, then Q_TILT_ENABLE, and the frame class is set before the reboot that activates it
    """
    assert _first_step_setting("Q_ENABLE") < _first_step_setting("Q_TILT_ENABLE")
    assert _first_step_setting("Q_FRAME_CLASS") < _first_step_setting("Q_TILT_ENABLE")
    assert _first_step_setting("Q_TILT_ENABLE") <= _first_step_setting("Q_TILT_TYPE")
    assert _first_step_setting("Q_TILT_ENABLE") < 12, "The frame must be active before the step 12 motor test"


def test_vectored_yaw_tilt_tri_outputs() -> None:
    """
    The output layout matches the owner's vectored-yaw tilt tricopter wiring.

    GIVEN: The servo output and ESC steps of the tilt-tri template
    WHEN: The frame, tilt, output functions and DShot masks are read
    THEN: Outputs 3, 4 and 5 drive motors 1, 4 and 2, the tilt servos are vectored, and the DShot masks match the ESCs
    """
    outputs = _step("11_servo_outputs.param")
    frame = _step("08_esc_telemetry.param")
    esc = _step("14_esc.param")

    assert frame["Q_FRAME_CLASS"].value == 7
    assert outputs["Q_TILT_TYPE"].value == 2
    assert outputs["Q_TILT_MASK"].value == 3
    assert outputs["Q_TILT_YAW_ANGLE"].value > 0
    assert [outputs[f"SERVO{i}_FUNCTION"].value for i in (3, 4, 5)] == [33, 36, 34]
    assert (outputs["SERVO8_FUNCTION"].value, outputs["SERVO9_FUNCTION"].value) == (76, 75)
    assert outputs["SERVO6_FUNCTION"].value == 0, "Output 6 shares a timer with the DShot output 5"
    esc_outputs_mask = sum(1 << (i - 1) for i in (3, 4, 5))
    assert esc["SERVO_BLH_BDMASK"].value == esc_outputs_mask
    assert esc["SERVO_BLH_MASK"].value == esc_outputs_mask
    assert esc["SERVO_BLH_AUTO"].value == 1


def test_quadplane_loop_rate_is_not_left_at_the_fixed_wing_default() -> None:
    """
    An explicit fixed-wing loop rate would override the QuadPlane default.

    GIVEN: The general configuration step of the tilt-tri template
    WHEN: SCHED_LOOP_RATE is read
    THEN: It uses the 300 Hz rate ArduPlane selects for QuadPlanes
    """
    assert _step("23_general_configuration.param")["SCHED_LOOP_RATE"].value == 300


def test_template_has_no_copter_only_tuning_parameter_names() -> None:
    """
    QuadPlane tuning uses Q_ prefixed parameter names.

    GIVEN: All tilt-tri template step files
    WHEN: Parameter names are collected
    THEN: None use the ArduCopter-only attitude, position or navigation controller names
    """
    copter_prefixes = ("ATC_", "PSC_", "WPNAV_", "LOIT_", "MOT_")
    names = {
        name
        for parameter_file in TEMPLATE_DIR.glob("[0-9][0-9]_*.param")
        if parameter_file.name != "00_default.param"
        for name in ParDict.from_file(str(parameter_file))
    }

    assert not {name for name in names if name.startswith(copter_prefixes)}
    assert "ANGLE_MAX" not in names
    assert "RTL_ALT" not in names


def test_mavlink_rc_receiver_and_telemetry_share_one_mavlink2_port() -> None:
    """
    MAVLink over ELRS carries RC and telemetry on one serial port.

    GIVEN: The tilt-tri template components with a MAVRadio RC receiver and MAVLink2 telemetry on SERIAL1
    WHEN: The RC receiver step derives the serial protocol
    THEN: SERIAL1 stays MAVLink2 instead of being switched to RCIN, matching the template file
    """
    components = _components()
    steps = _plane_steps()
    step_file = "05_remote_controller_receiver.param"
    config_steps = ConfigurationSteps("vehicle_dir", "ArduPlane")

    error = config_steps.compute_parameters(
        step_file, steps[step_file], "derived", {"fc_parameters": {}, "vehicle_components": components, "doc_dict": {}}
    )

    assert error == ""
    assert components["RC Receiver"]["FC Connection"]["Type"] == components["Telemetry"]["FC Connection"]["Type"]
    assert config_steps.derived_parameters[step_file]["SERIAL1_PROTOCOL"].value == 2
    assert _step(step_file)["SERIAL1_PROTOCOL"].value == 2
    assert _step("07_telemetry.param")["SERIAL1_PROTOCOL"].value == 2


def test_serial_rc_receivers_other_than_mavradio_still_use_rcin() -> None:
    """
    The MAVRadio exception does not change other serial RC receivers.

    GIVEN: The tilt-tri template components with the RC receiver switched to CRSF
    WHEN: The RC receiver step derives the serial protocol
    THEN: SERIAL1 is set to RCIN
    """
    components = copy.deepcopy(_components())
    components["RC Receiver"]["FC Connection"]["Protocol"] = "CRSF"
    steps = _plane_steps()
    step_file = "05_remote_controller_receiver.param"
    config_steps = ConfigurationSteps("vehicle_dir", "ArduPlane")

    error = config_steps.compute_parameters(
        step_file, steps[step_file], "derived", {"fc_parameters": {}, "vehicle_components": components, "doc_dict": {}}
    )

    assert error == ""
    assert config_steps.derived_parameters[step_file]["SERIAL1_PROTOCOL"].value == 23


@pytest.mark.parametrize(
    ("parameter_name", "quadplane_default"),
    [("Q_A_ACC_R_MAX", 400), ("Q_A_ACC_P_MAX", 400), ("Q_A_ACC_Y_MAX", 100)],
)
def test_derived_quadplane_acceleration_limits_do_not_exceed_quadplane_defaults(
    parameter_name: str, quadplane_default: float
) -> None:
    """
    Small propellers must not raise QuadPlane acceleration limits above the ArduPlane defaults.

    GIVEN: The tilt-tri template components with 5.1 inch propellers
    WHEN: The initial attitude controller step derives the acceleration limits
    THEN: Each limit is capped at the ArduPlane QuadPlane default
    """
    steps = _plane_steps()
    step_file = "13_initial_atc.param"
    config_steps = ConfigurationSteps("vehicle_dir", "ArduPlane")

    error = config_steps.compute_parameters(
        step_file,
        steps[step_file],
        "derived",
        {"fc_parameters": {parameter_name: 0}, "vehicle_components": _components(), "doc_dict": {}},
    )

    assert error == ""
    assert config_steps.derived_parameters[step_file][parameter_name].value == quadplane_default
