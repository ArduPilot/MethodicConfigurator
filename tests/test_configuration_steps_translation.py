#!/usr/bin/env python3
"""
Verify configuration step popup messages reach the gettext extraction input.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import ast
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest


# pylint: disable=duplicate-code
def _load_translation_update_script() -> ModuleType:
    """Load the scripts-directory translation updater without relying on sys.path."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "update_configuration_steps_translation.py"
    module_spec = spec_from_file_location("update_configuration_steps_translation", script_path)
    assert module_spec
    assert module_spec.loader
    module = module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


# pylint: enable=duplicate-code


_translation_update = _load_translation_update_script()
extract_strings_from_config_steps = _translation_update.extract_strings_from_config_steps
gather_all_translatable_strings = _translation_update.gather_all_translatable_strings
generate_config_steps_output = _translation_update.generate_config_steps_output


def test_all_vehicle_popup_messages_reach_gettext_input(tmp_path: Path) -> None:
    """
    Include existing and new popup messages in the generated translation input.

    GIVEN: Vehicle configuration files containing instruction popups
    WHEN: Their translatable strings are gathered and generated as Python
    THEN: Every popup message is present as a gettext literal, including newlines
    """
    config_dir = Path(__file__).resolve().parents[1] / "ardupilot_methodic_configurator"
    expected_messages = set()
    for config_file in config_dir.glob("configuration_steps_*.json"):
        data = json.loads(config_file.read_text(encoding="utf-8"))
        expected_messages.update(
            step["instructions_popup"]["msg"] for step in data.get("steps", {}).values() if "instructions_popup" in step
        )
    assert expected_messages

    all_strings = gather_all_translatable_strings(str(config_dir))
    output_file = tmp_path / "configuration_steps_strings.py"
    generate_config_steps_output(all_strings, [], str(output_file))

    generated = ast.parse(output_file.read_text(encoding="utf-8"))
    gettext_literals = {
        ast.literal_eval(node.args[0])
        for node in ast.walk(generated)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
    }
    assert set(all_strings["instructions_popup"]) == expected_messages
    assert expected_messages <= gettext_literals


@pytest.mark.parametrize("popup", [None, "message", {}, {"msg": None}, {"msg": 42}, {"msg": ""}, {"msg": " \n "}])
def test_invalid_popup_messages_do_not_interrupt_other_translations(tmp_path: Path, popup: object) -> None:
    """
    Ignore missing or invalid popup messages while preserving other step text.

    GIVEN: A configuration step with an empty or malformed optional popup
    WHEN: Translation strings are extracted
    THEN: The normal step text remains available and no popup message is added
    """
    config_file = tmp_path / "configuration_steps_test.json"
    config_file.write_text(
        json.dumps({"steps": {"1": {"instructions_popup": popup, "why": "Configure the receiver"}}}),
        encoding="utf-8",
    )

    strings = extract_strings_from_config_steps(str(config_file))

    assert strings["why"] == {"Configure the receiver"}
    assert strings["instructions_popup"] == set()
