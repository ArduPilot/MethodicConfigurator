#!/usr/bin/env python3

"""
Behavior-driven datatype tests for configuration_steps_strings module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from gettext_capture_helper import capture_gettext_calls

from ardupilot_methodic_configurator import configuration_steps_strings as config_strings


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
