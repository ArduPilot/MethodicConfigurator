#!/usr/bin/env python3

"""
Tests for ardupilot_methodic_configurator/frontend_tkinter_log_quality.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_log_availability import (
    LogQualityReportWindow,
    _format_parameter_value,
)


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


@pytest.mark.parametrize("upload_result", [None, True])
def test_quality_fix_accepts_non_false_upload_result(upload_result: bool | None) -> None:
    """
    Treat callbacks without an explicit failure result as successful.

    GIVEN a parameter-fix callback returning None or True,
    WHEN the quality report applies a fix,
    THEN the displayed parameter state is updated and the dialog closes.
    """
    # Arrange: bypass Tk construction and provide a side-effect callback.
    window = LogQualityReportWindow.__new__(LogQualityReportWindow)
    window.summary = MagicMock(related_parameter_values={})
    window.upload_callback = MagicMock(return_value=upload_result)
    dialog = MagicMock()
    fixes = [("MOT_SPIN_MIN", 0.1, 0.15, ["finding"])]

    # Act: apply the proposed change.
    window._apply_param_fixes(fixes, dialog)

    # Assert: None is not mistaken for an upload failure.
    assert window.summary.related_parameter_values == {"MOT_SPIN_MIN": 0.15}
    dialog.destroy.assert_called_once()
