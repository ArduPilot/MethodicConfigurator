#!/usr/bin/env python3
"""
Check ArduPlane battery failsafe defaults against Plane action meanings.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "ardupilot_methodic_configurator"
TEMPLATE_FILE = PACKAGE_DIR / "vehicle_templates" / "ArduPlane" / "empty_4.7.x" / "10_battery.param"
PLANE_TEMPLATES_DIR = PACKAGE_DIR / "vehicle_templates" / "ArduPlane"
STEPS_FILE = PACKAGE_DIR / "configuration_steps_ArduPlane.json"

# https://ardupilot.org/plane/docs/apms-failsafe-function.html#battery-failsafe-actions
PLANE_BATTERY_ACTIONS = {"BATT_FS_LOW_ACT": (1, "RTL"), "BATT_FS_CRT_ACT": (2, "Land")}


@pytest.fixture
def template_actions() -> dict[str, int]:
    """Read the two action values proposed by the empty Plane 4.7 template."""
    return {
        name: int(value)
        for line in TEMPLATE_FILE.read_text(encoding="utf-8").splitlines()
        if line.startswith(tuple(PLANE_BATTERY_ACTIONS))
        for name, value in [line.split(",", maxsplit=1)]
    }


def _read_parameter_values(parameter_file: Path) -> dict[str, int]:
    """Read numeric parameter values while ignoring descriptive comments."""
    return {
        name: int(value.partition("#")[0].strip())
        for line in parameter_file.read_text(encoding="utf-8").splitlines()
        if line and not line.lstrip().startswith("#")
        for name, value in [line.split(",", maxsplit=1)]
        if name.endswith("_FS_LOW_ACT") or name == "BATT_FS_CRT_ACT"
    }


@pytest.fixture
def forced_actions() -> dict[str, dict[str, int | str]]:
    """Read the action values and explanations in the Plane battery step."""
    steps = json.loads(STEPS_FILE.read_text(encoding="utf-8"))["steps"]
    return {name: steps["10_battery.param"]["forced_parameters"][name] for name in PLANE_BATTERY_ACTIONS}


def test_plane_battery_template_proposes_documented_action_values(template_actions: dict[str, int]) -> None:
    """Given Plane action meanings, the template proposes RTL at low and Land at critical battery."""
    assert template_actions == {name: value for name, (value, _) in PLANE_BATTERY_ACTIONS.items()}


def test_plane_battery_step_forces_documented_actions_with_accurate_reasons(
    forced_actions: dict[str, dict[str, int | str]],
) -> None:
    """Given Plane action meanings, the battery step forces each action with its correct explanation."""
    assert {name: action["New Value"] for name, action in forced_actions.items()} == {
        name: value for name, (value, _) in PLANE_BATTERY_ACTIONS.items()
    }
    for name, (_, documented_action) in PLANE_BATTERY_ACTIONS.items():
        assert documented_action in forced_actions[name]["Change Reason"]
    assert "DO_LAND" in forced_actions["BATT_FS_CRT_ACT"]["Change Reason"]


def test_plane_battery_template_and_forced_actions_agree(
    template_actions: dict[str, int], forced_actions: dict[str, dict[str, int | str]]
) -> None:
    """Given both Plane sources, the action values shown to the user match the forced values."""
    assert template_actions == {name: action["New Value"] for name, action in forced_actions.items()}


@pytest.mark.parametrize("template_name", ["normal_plane", "empty_4.7.x"])
def test_plane_battery_templates_use_documented_low_and_critical_actions(template_name: str) -> None:
    """Given either Plane template, the battery step uses RTL at low and Land at critical battery."""
    values = _read_parameter_values(PLANE_TEMPLATES_DIR / template_name / "10_battery.param")

    assert {name: values[name] for name in PLANE_BATTERY_ACTIONS} == {
        name: value for name, (value, _) in PLANE_BATTERY_ACTIONS.items()
    }


@pytest.mark.parametrize("template_name", ["normal_plane", "empty_4.7.x"])
def test_plane_everyday_use_returns_home_on_low_battery_for_both_monitors(template_name: str) -> None:
    """Given either Plane template, Everyday Use selects RTL for both battery monitors."""
    values = _read_parameter_values(PLANE_TEMPLATES_DIR / template_name / "70_everyday_use.param")

    assert values["BATT_FS_LOW_ACT"] == 1
    assert values["BATT2_FS_LOW_ACT"] == 1
