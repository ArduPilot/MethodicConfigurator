#!/usr/bin/env python3

"""
Tests for the tilt-rotor tricopter QuadPlane ArduPlane templates.

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
PLANE_TEMPLATES_DIR = PACKAGE_DIR / "vehicle_templates" / "ArduPlane"
TEMPLATE_DIR = PLANE_TEMPLATES_DIR / "HeeWing_T1-S_Ranger_VTOL"
GENERIC_TEMPLATE_DIR = PLANE_TEMPLATES_DIR / "tilt_tri_quadplane"
TILT_TRI_TEMPLATE_DIRS = pytest.mark.parametrize("template_dir", [TEMPLATE_DIR, GENERIC_TEMPLATE_DIR], ids=lambda d: d.name)
PLANE_STEPS_FILE = PACKAGE_DIR / "configuration_steps_ArduPlane.json"


def _step(file_name: str, template_dir: Path = TEMPLATE_DIR) -> ParDict:
    return ParDict.from_file(str(template_dir / file_name))


def _components() -> dict:
    with (TEMPLATE_DIR / "vehicle_components.json").open(encoding="utf-8") as file:
        components: dict = json.load(file)["Components"]
    return components


def _plane_steps() -> dict:
    with PLANE_STEPS_FILE.open(encoding="utf-8") as file:
        steps: dict = json.load(file)["steps"]
    return steps


def _first_step_setting(parameter_name: str, template_dir: Path) -> int:
    """Return the numeric prefix of the first template step that sets the parameter."""
    for parameter_file in sorted(template_dir.glob("[0-9][0-9]_*.param")):
        if parameter_file.name != "00_default.param" and parameter_name in ParDict.from_file(str(parameter_file)):
            return int(parameter_file.name[:2])
    msg = f"{parameter_name} is not set by any template step"
    raise AssertionError(msg)


@TILT_TRI_TEMPLATE_DIRS
def test_quadplane_enable_parameters_are_staged_across_reboots(template_dir: Path) -> None:
    """
    QuadPlane and tilt-rotor parameters only appear after the enabling reboot.

    GIVEN: The tilt-tri template step files
    WHEN: The steps that enable QuadPlane, select the frame and configure the tilt mechanism are compared
    THEN: Q_ENABLE comes first, then Q_TILT_ENABLE, and the frame class is set before the reboot that activates it
    """

    def first(parameter_name: str) -> int:
        return _first_step_setting(parameter_name, template_dir)

    assert first("Q_ENABLE") < first("Q_TILT_ENABLE")
    assert first("Q_FRAME_CLASS") < first("Q_TILT_ENABLE")
    assert first("Q_TILT_ENABLE") <= first("Q_TILT_TYPE")
    assert first("Q_TILT_ENABLE") < 12, "The frame must be active before the step 12 motor test"


def test_vectored_yaw_tilt_tri_outputs() -> None:
    """
    The output layout matches the owner's vectored-yaw tilt tricopter wiring.

    GIVEN: The servo output and ESC steps of the tilt-tri template
    WHEN: The frame, tilt, output functions and DShot masks are read
    THEN: Outputs 3, 4 and 5 drive motors 1, 4 and 2, the tilt servos are vectored, and the DShot masks match the ESCs
    """
    outputs = _step("11_servo_outputs.param")
    frame = _step("08_esc_telemetry.param")
    esc = _step("15_esc.param")

    assert frame["Q_FRAME_CLASS"].value == 7
    assert outputs["Q_TILT_TYPE"].value == 2
    assert outputs["Q_TILT_MASK"].value == 3
    assert _step("12_control_surfaces_and_tilt_servos.param")["Q_TILT_YAW_ANGLE"].value > 0
    assert [outputs[f"SERVO{i}_FUNCTION"].value for i in (3, 4, 5)] == [33, 36, 34]
    assert (outputs["SERVO8_FUNCTION"].value, outputs["SERVO9_FUNCTION"].value) == (76, 75)
    assert outputs["SERVO6_FUNCTION"].value == 0, "Output 6 shares a timer with the DShot output 5"
    esc_outputs_mask = sum(1 << (i - 1) for i in (3, 4, 5))
    assert esc["SERVO_BLH_BDMASK"].value == esc_outputs_mask
    assert esc["SERVO_BLH_MASK"].value == esc_outputs_mask
    assert esc["SERVO_BLH_AUTO"].value == 1


@TILT_TRI_TEMPLATE_DIRS
def test_quadplane_loop_rate_is_not_left_at_the_fixed_wing_default(template_dir: Path) -> None:
    """
    An explicit fixed-wing loop rate would override the QuadPlane default.

    GIVEN: The general configuration step of the tilt-tri template
    WHEN: SCHED_LOOP_RATE is read
    THEN: It uses the 300 Hz rate ArduPlane selects for QuadPlanes
    """
    assert _step("24_general_configuration.param", template_dir)["SCHED_LOOP_RATE"].value == 300


@TILT_TRI_TEMPLATE_DIRS
def test_template_has_no_copter_only_tuning_parameter_names(template_dir: Path) -> None:
    """
    QuadPlane tuning uses Q_ prefixed parameter names.

    GIVEN: All tilt-tri template step files
    WHEN: Parameter names are collected
    THEN: None use the ArduCopter-only attitude, position or navigation controller names
    """
    copter_prefixes = ("ATC_", "PSC_", "WPNAV_", "LOIT_", "MOT_")
    names = {
        name
        for parameter_file in template_dir.glob("[0-9][0-9]_*.param")
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
    step_file = "14_initial_atc.param"
    config_steps = ConfigurationSteps("vehicle_dir", "ArduPlane")

    error = config_steps.compute_parameters(
        step_file,
        steps[step_file],
        "derived",
        {"fc_parameters": {parameter_name: 0}, "vehicle_components": _components(), "doc_dict": {}},
    )

    assert error == ""
    assert config_steps.derived_parameters[step_file][parameter_name].value == quadplane_default


@TILT_TRI_TEMPLATE_DIRS
def test_flight_mode_switch_has_no_manual_mode(template_dir: Path) -> None:
    """
    A tilt-rotor in MANUAL tilts the rotors fully forward at 90 deg/s, so it is kept off the mode switch.

    GIVEN: The flight modes step of the tilt-tri template
    WHEN: The flight mode channel and the six switch positions are read
    THEN: Channel 8 selects the modes, no position is MANUAL and the 3-position switch positions are VTOL, FBWA and QRTL
    """
    modes = _step("23_flight_modes.param", template_dir)
    manual, fbwa, qstabilize, qrtl = 0, 5, 17, 21

    assert modes["FLTMODE_CH"].value == 8
    assert all(modes[f"FLTMODE{i}"].value != manual for i in range(1, 7))
    assert [modes[f"FLTMODE{i}"].value for i in (1, 4, 6)] == [qstabilize, fbwa, qrtl]
    assert modes["INITIAL_MODE"].value == qstabilize


@TILT_TRI_TEMPLATE_DIRS
def test_front_motors_tilt_and_rear_motor_stays_fixed(template_dir: Path) -> None:
    """
    Only the two front motors of the tilt-tri frame tilt.

    GIVEN: The servo output step of a tilt-tri template
    WHEN: The frame class, tilt mask and tilt type are read
    THEN: The frame is a Tri, motors 1 and 2 tilt with vectored yaw, and the rear motor 4 is not in the tilt mask
    """
    outputs = _step("11_servo_outputs.param", template_dir)
    frame = _step("08_esc_telemetry.param", template_dir)
    rear_motor_bit = 1 << (4 - 1)

    assert frame["Q_ENABLE"].value == 1
    assert frame["Q_FRAME_CLASS"].value == 7
    assert outputs["Q_TILT_ENABLE"].value == 1
    assert outputs["Q_TILT_TYPE"].value == 2
    assert outputs["Q_TILT_MASK"].value == 0b011
    assert not int(outputs["Q_TILT_MASK"].value) & rear_motor_bit


def test_generic_tilt_tri_output_layout() -> None:
    """
    The generic tilt-tri template groups the DShot motors on outputs 1 to 3.

    GIVEN: The servo output and ESC steps of the generic tilt-tri template
    WHEN: The output functions and DShot masks are read
    THEN: Outputs 1-3 drive motors 1, 2 and 4, outputs 5-6 the front tilt servos, 7-9 the control surfaces,
          and the BLHeli and bidirectional DShot masks cover only the motor outputs
    """
    outputs = _step("11_servo_outputs.param", GENERIC_TEMPLATE_DIR)
    esc = _step("15_esc.param", GENERIC_TEMPLATE_DIR)
    motor1, motor2, motor4, tilt_front_left, tilt_front_right = 33, 34, 36, 75, 76
    aileron, elevator, rudder = 4, 19, 21

    assert [outputs[f"SERVO{i}_FUNCTION"].value for i in (1, 2, 3)] == [motor1, motor2, motor4]
    assert outputs["SERVO4_FUNCTION"].value == 0, "Output 4 usually shares a timer with the DShot motor outputs"
    assert (outputs["SERVO5_FUNCTION"].value, outputs["SERVO6_FUNCTION"].value) == (tilt_front_right, tilt_front_left)
    assert [outputs[f"SERVO{i}_FUNCTION"].value for i in (7, 8, 9)] == [aileron, elevator, rudder]
    assert esc["SERVO_BLH_MASK"].value == 0b111
    assert esc["SERVO_BLH_BDMASK"].value == 0b111


def test_generic_tilt_tri_components_describe_a_dshot_tri_frame() -> None:
    """
    The generic template components match its parameter files.

    GIVEN: The generic tilt-tri template components
    WHEN: The frame, ESC protocol and template name are read
    THEN: The frame class is Tri, the ESCs use DShot300 as Q_M_PWM_TYPE says, RPM telemetry drives the notch filter,
          and no product is preset
    """
    with (GENERIC_TEMPLATE_DIR / "vehicle_components.json").open(encoding="utf-8") as file:
        data = json.load(file)
    components = data["Components"]

    assert data["Configuration template"] == "tilt_tri_quadplane"
    assert components["Frame"]["Specifications"]["Frame class"] == "Tri"
    assert components["ESC"]["FC->ESC Connection"]["Protocol"] == "DShot300"
    assert _step("08_esc_telemetry.param", GENERIC_TEMPLATE_DIR)["Q_M_PWM_TYPE"].value == 5
    assert components["ESC"]["ESC->FC Telemetry"]["Protocol"] == "BDShotOnly"
    assert _step("26_motor_notch_filter_setup.param", GENERIC_TEMPLATE_DIR)["INS_HNTCH_MODE"].value == 3
    assert all(not component.get("Product", {}).get("Model") for component in components.values())


@TILT_TRI_TEMPLATE_DIRS
def test_tilt_servo_adjustments_are_in_the_control_surface_step(template_dir: Path) -> None:
    """
    Tilt servo travel, rates and the vectored-yaw angle are adjusted after the tilt mechanism is enabled.

    GIVEN: The servo output and control surface steps of a tilt-tri template
    WHEN: The tilt and servo range parameters are located
    THEN: Step 11 only selects functions and the tilt mechanism, and step 12 holds the ranges, reversals and tilt rates
    """
    outputs = _step("11_servo_outputs.param", template_dir)
    adjustments = _step("12_control_surfaces_and_tilt_servos.param", template_dir)
    range_suffixes = ("_MIN", "_MAX", "_TRIM", "_REVERSED")

    assert not [name for name in outputs if name.startswith("SERVO") and name.endswith(range_suffixes)]
    assert {"Q_TILT_RATE_UP", "Q_TILT_RATE_DN", "Q_TILT_YAW_ANGLE"} <= set(adjustments)
    assert not {"Q_TILT_ENABLE", "Q_TILT_MASK", "Q_TILT_TYPE"} & set(adjustments)
    tilt_outputs = [name[: -len("_FUNCTION")] for name in outputs if outputs[name].value in (75, 76)]
    assert len(tilt_outputs) == 2
    for output in tilt_outputs:
        assert {f"{output}{suffix}" for suffix in range_suffixes} <= set(adjustments)


def test_control_surface_step_follows_the_servo_output_step() -> None:
    """
    ArduPlane adjusts control surfaces and tilt servos right after assigning the servo functions.

    GIVEN: The ArduPlane configuration steps
    WHEN: The new control surface step and its neighbours are read
    THEN: It follows 11_servo_outputs.param, precedes the motor and ESC steps, imports servo adjustments and warns first
    """
    steps = _plane_steps()
    names = list(steps)
    step = steps["12_control_surfaces_and_tilt_servos.param"]

    assert names[names.index("12_control_surfaces_and_tilt_servos.param") - 1] == "11_servo_outputs.param"
    assert names.index("12_control_surfaces_and_tilt_servos.param") < names.index("15_esc.param")
    assert "SERVO[0-9]+_(MIN|MAX|TRIM|REVERSED)" in step["autoimport_nondefault_regexp"]
    assert "Q_TILT_YAW_ANGLE" in step["autoimport_nondefault_regexp"]
    assert step["instructions_popup"]["type"] == "warning"
    assert steps["13_motor.param"]["old_filenames"] == ["12_motor.param"]
    assert steps["63_range_finder.param"]["old_filenames"] == ["62_range_finder.param"]
    assert "64_position_controller.param" in steps
