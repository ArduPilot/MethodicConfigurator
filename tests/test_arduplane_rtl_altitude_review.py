#!/usr/bin/env python3

"""
Check that ArduPlane Everyday Use reviews the connected RTL altitude without prescribing one.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from pathlib import Path

import pytest

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "ardupilot_methodic_configurator"
STEP_FILE = "70_everyday_use.param"


def _step(vehicle_type: str) -> dict:
    """Read a bundled vehicle's Everyday Use step without modifying its rules."""
    path = PACKAGE_DIR / f"configuration_steps_{vehicle_type}.json"
    return json.loads(path.read_text(encoding="utf-8"))["steps"][STEP_FILE]


def _template_values(vehicle_type: str, template_name: str) -> dict[str, float]:
    """Read only parameter names and values from a bundled Everyday Use template."""
    path = PACKAGE_DIR / "vehicle_templates" / vehicle_type / template_name / STEP_FILE
    return {
        name: float(value.partition("#")[0].strip())
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.lstrip().startswith("#")
        for name, value in [line.split(",", maxsplit=1)]
    }


@pytest.mark.parametrize("template_name", ["empty_4.7.x", "normal_plane"])
def test_generic_plane_everyday_template_does_not_assign_rtl_altitude(template_name: str) -> None:
    """GIVEN either new Plane template, WHEN loaded, THEN no RTL altitude is prescribed."""
    values = _template_values("ArduPlane", template_name)

    assert "RTL_ALT" not in values
    assert "RTL_ALTITUDE" not in values
    assert values["RTL_CLIMB_MIN"] == 0


@pytest.mark.parametrize("fc_altitude", [100.0, 35.0, -1.0])
def test_plane_step_copies_actual_fc_rtl_altitude_for_review(fc_altitude: float) -> None:
    """GIVEN a connected Plane FC, WHEN Step 70 loads, THEN its actual metres value is offered."""
    step = _step("ArduPlane")
    calculations = ConfigurationSteps("", "ArduPlane")

    calculations.compute_add_parameters(STEP_FILE, step, {"fc_parameters": {"RTL_ALTITUDE": fc_altitude}})

    assert step["add_parameters"]["RTL_ALTITUDE"] == {"if": "'RTL_ALTITUDE' in fc_parameters"}
    assert calculations.add_parameters[STEP_FILE]["RTL_ALTITUDE"].value == fc_altitude


def test_plane_step_preserves_saved_rtl_altitude() -> None:
    """GIVEN a saved altitude, WHEN Step 70 loads, THEN the live FC value does not replace it."""
    saved = Par(27.0, "pilot-selected altitude")
    existing = ParDict({"RTL_ALTITUDE": saved})
    calculations = ConfigurationSteps("", "ArduPlane")

    calculations.compute_add_parameters(
        STEP_FILE, _step("ArduPlane"), {"fc_parameters": {"RTL_ALTITUDE": 100.0}}, existing_params=existing
    )

    assert calculations.add_parameters.get(STEP_FILE, ParDict()) == {}
    assert existing["RTL_ALTITUDE"] is saved


@pytest.mark.parametrize("variables", [{}, {"fc_parameters": {}}])
def test_plane_step_does_not_invent_altitude_without_fc_parameter(variables: dict) -> None:
    """GIVEN no live RTL_ALTITUDE, WHEN Step 70 loads, THEN it offers no fallback."""
    calculations = ConfigurationSteps("", "ArduPlane")

    calculations.compute_add_parameters(STEP_FILE, _step("ArduPlane"), variables)

    assert calculations.add_parameters.get(STEP_FILE, ParDict()) == {}


def test_other_vehicle_rtl_settings_remain_distinct() -> None:
    """GIVEN Copter and Rover templates, WHEN Plane rules change, THEN their RTL settings remain."""
    copter = _template_values("ArduCopter", "Tarot_X4")
    rover = _template_values("Rover", "AION_R1")

    assert copter["RTL_ALT"] == 3500
    assert rover["RTL_ALT"] == 500
    assert "RTL_ALTITUDE" not in _step("ArduCopter").get("add_parameters", {})
    assert "RTL_ALTITUDE" not in _step("Rover").get("add_parameters", {})
