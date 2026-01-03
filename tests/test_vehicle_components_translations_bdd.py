#!/usr/bin/env python3

"""
Behavior-driven datatype tests for vehicle_components translation helpers.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from gettext_capture_helper import capture_gettext_calls

from ardupilot_methodic_configurator import vehicle_components


class TestVehicleComponentsTranslationHelpers:
    """BDD coverage for vehicle component translation helpers."""

    def test_translatable_strings_forward_literals_to_gettext(self, monkeypatch) -> None:
        """
        translatable_strings forwards every literal to gettext.

        GIVEN: translatable_strings simply enumerates literal strings
        WHEN: The shared gettext capture helper records inputs
        THEN: The recorder captures non-empty strings exclusively
        """
        captured_values = capture_gettext_calls(
            monkeypatch,
            vehicle_components,
            vehicle_components.translatable_strings,
        )

        assert captured_values
        assert all(isinstance(value, str) and value for value in captured_values)

    def test_translatable_descriptions_forward_literals_to_gettext(self, monkeypatch) -> None:
        """
        translatable_descriptions forwards schema literals to gettext.

        GIVEN: translatable_descriptions iterates strings from the schema definition
        WHEN: The helper intercepts gettext invocations
        THEN: The recorder receives only non-empty strings
        """
        captured_values = capture_gettext_calls(
            monkeypatch,
            vehicle_components,
            vehicle_components.translatable_descriptions,
        )

        assert captured_values
        assert all(isinstance(value, str) and value for value in captured_values)
