#!/usr/bin/env python3

"""
Behavior-driven datatype tests for configuration_steps_strings module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

from gettext_capture_helper import capture_gettext_calls

from ardupilot_methodic_configurator import configuration_steps_strings as config_strings


def _load_translation_update_script() -> ModuleType:
    """Load the root-level translation updater without relying on the current working directory."""
    script_path = Path(__file__).parent.parent / "update_configuration_steps_translation.py"
    module_spec = spec_from_file_location("update_configuration_steps_translation", script_path)
    assert module_spec
    assert module_spec.loader
    module = module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class TestConfigurationStepsStringsModule:
    """BDD tests for string collection helpers."""

    def test_configuration_steps_strings_invokes_gettext_with_text(self, monkeypatch) -> None:
        """
        configuration_steps_strings forwards collected strings to gettext.

        GIVEN: configuration_steps_strings aggregates literal strings from JSON resources
        WHEN: The gettext capture helper intercepts inputs
        THEN: Every captured value is a non-empty string and the function returns None
        """
        captured_values = capture_gettext_calls(
            monkeypatch,
            config_strings,
            config_strings.configuration_steps_strings,
        )
        assert captured_values
        assert all(isinstance(value, str) and value for value in captured_values)

    def test_configuration_steps_descriptions_invokes_gettext_with_text(self, monkeypatch) -> None:
        """
        configuration_steps_descriptions forwards schema strings to gettext.

        GIVEN: configuration_steps_descriptions enumerates strings from the schema file
        WHEN: The shared capture helper records gettext inputs
        THEN: Every value reaching gettext is a non-empty string and the function returns None
        """
        captured_values = capture_gettext_calls(
            monkeypatch,
            config_strings,
            config_strings.configuration_steps_descriptions,
        )
        assert captured_values
        assert all(isinstance(value, str) and value for value in captured_values)

    def test_configuration_steps_strings_include_every_change_reason(self, monkeypatch) -> None:
        """Every Change Reason in the JSON resources is registered for translation."""
        captured_values = capture_gettext_calls(
            monkeypatch,
            config_strings,
            config_strings.configuration_steps_strings,
        )
        translation_updater = _load_translation_update_script()
        extracted_strings = translation_updater.gather_all_translatable_strings(str(Path(config_strings.__file__).parent))

        assert set(extracted_strings["change_reasons"]) <= set(captured_values)

    def test_translation_update_script_loads_when_tests_are_run_outside_repository_root(self) -> None:
        """The translation updater can be loaded by this test without repository-root imports."""
        translation_updater = _load_translation_update_script()

        assert callable(translation_updater.gather_all_translatable_strings)
