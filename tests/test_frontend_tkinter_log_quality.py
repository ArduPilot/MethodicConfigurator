#!/usr/bin/env python3

"""
Tests for ardupilot_methodic_configurator/frontend_tkinter_log_quality.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_log_quality import _format_parameter_value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (123.0, "123"),
        (0.15, "0.15"),
        (1.25, "1.25"),
    ],
)
def test_parameter_value_formatting_preserves_fractional_changes(value: float, expected: str) -> None:
    """
    Display parameter values without silently changing their meaning.

    GIVEN integral and fractional parameter values,
    WHEN they are formatted for the parameter-change review dialog,
    THEN integral values omit an unnecessary decimal and fractional values are preserved.
    """
    # Arrange: parametrized parameter values represent pending FC changes.

    # Act: format the value shown to the user.
    actual = _format_parameter_value(value)

    # Assert: the text faithfully represents the value that will be uploaded.
    assert actual == expected
