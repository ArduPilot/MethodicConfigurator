#!/usr/bin/env python3
"""
Check Rover battery defaults allow escalation from RTL to Hold.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "ardupilot_methodic_configurator"
TEMPLATES_DIR = PACKAGE_DIR / "vehicle_templates" / "Rover"

# Hold has higher priority than RTL, so a low-battery Hold would suppress critical RTL.
# https://github.com/ArduPilot/ardupilot/blob/Rover-4.7.0/Rover/Rover.h#L376-L396
# https://github.com/ArduPilot/ardupilot/blob/Rover-4.7.0/libraries/AP_BattMonitor/AP_BattMonitor.cpp#L882-L898
ROVER_BATTERY_ACTIONS = {"FS_LOW_ACT": (1, "RTL"), "FS_CRT_ACT": (2, "Hold")}


def _read_battery_actions(parameter_file: Path) -> dict[str, int]:
    """Read battery action values without their descriptive comments."""
    actions = {}
    for line in parameter_file.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition(",")
        if name.startswith("BATT") and name.endswith(tuple(ROVER_BATTERY_ACTIONS)):
            actions[name] = int(value.partition("#")[0].strip())
    return actions


def test_rover_battery_step_returns_home_before_stopping_on_critical_battery() -> None:
    """Given Rover priorities, the battery step selects RTL at low and Hold at critical battery."""
    steps = json.loads((PACKAGE_DIR / "configuration_steps_Rover.json").read_text(encoding="utf-8"))["steps"]
    forced_actions = steps["13_battery.param"]["forced_parameters"]

    for suffix, (value, action_name) in ROVER_BATTERY_ACTIONS.items():
        action = forced_actions[f"BATT_{suffix}"]
        assert action["New Value"] == value
        assert action["Change Reason"].startswith(f"{action_name}:")


@pytest.mark.parametrize("template_name", ["AION_R1", "Carisma_SCA-1E", "empty_4.7.x"])
def test_rover_battery_templates_allow_escalation_for_each_monitor(template_name: str) -> None:
    """Given a Rover template, each configured monitor returns home at low and stops at critical battery."""
    actions = _read_battery_actions(TEMPLATES_DIR / template_name / "13_battery.param")

    for prefix in ("BATT_", "BATT2_"):
        if prefix == "BATT_" or any(name.startswith(prefix) for name in actions):
            for suffix, (value, _) in ROVER_BATTERY_ACTIONS.items():
                assert actions[f"{prefix}{suffix}"] == value


@pytest.mark.parametrize("template_name", ["AION_R1", "Carisma_SCA-1E"])
def test_rover_everyday_use_preserves_rtl_to_hold_escalation(template_name: str) -> None:
    """Given everyday-use overrides, both monitors still return home before a critical-battery stop."""
    template_dir = TEMPLATES_DIR / template_name
    actions = _read_battery_actions(template_dir / "13_battery.param")
    actions.update(_read_battery_actions(template_dir / "70_everyday_use.param"))

    for prefix in ("BATT_", "BATT2_"):
        for suffix, (value, _) in ROVER_BATTERY_ACTIONS.items():
            assert actions[f"{prefix}{suffix}"] == value
