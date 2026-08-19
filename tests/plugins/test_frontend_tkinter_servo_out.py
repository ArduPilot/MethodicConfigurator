#!/usr/bin/env python3

"""
Behavior-driven tests for the servo-output Tkinter plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugins.data_model_servo_out import ServoOutDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out import ServoOutView


@pytest.fixture
def servo_out_view(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Provide a real servo-output view with modal dialogs isolated."""
    model = MagicMock(spec=ServoOutDataModel)
    model.get_recommendations.return_value = ({"SERVO1_FUNCTION": 33}, "Recommended 1 motor output assignment.")
    showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showinfo")
    showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showerror")
    parent = ttk.Frame(tk_root)
    try:
        yield SimpleNamespace(
            view=ServoOutView(parent, model, SimpleNamespace(root=tk_root)),
            model=model,
            showinfo=showinfo,
            showerror=showerror,
        )
    finally:
        parent.destroy()


class TestServoOutputView:
    """Test user feedback while applying servo-output recommendations."""

    def test_user_sees_applied_assignments_after_accepting_recommendation(self, servo_out_view) -> None:
        """
        Applied recommendations are acknowledged with a success dialog.

        GIVEN: The model can apply a proposed motor assignment
        WHEN: The user selects Apply Recommended Motor Outputs
        THEN: The view shows a success dialog and refreshes the recommendation summary
        """
        # Arrange (Given)
        servo_out_view.model.apply_recommendations.return_value = (["SERVO1_FUNCTION"], "Applied 1 motor output assignment.")

        # Act (When)
        servo_out_view.view._on_apply()

        # Assert (Then)
        servo_out_view.showinfo.assert_called_once_with("Servo Output Functions", "Applied 1 motor output assignment.")
        servo_out_view.showerror.assert_not_called()
        assert "SERVO1_FUNCTION=33" in servo_out_view.view._summary.get()

    def test_user_sees_reason_when_no_recommendation_can_be_applied(self, servo_out_view) -> None:
        """
        An unapplied recommendation provides an actionable error.

        GIVEN: The model cannot apply any motor assignments
        WHEN: The user selects Apply Recommended Motor Outputs
        THEN: The view shows the model's reason without a success dialog
        """
        # Arrange (Given)
        servo_out_view.model.apply_recommendations.return_value = ([], "No servo output assignments could be applied.")

        # Act (When)
        servo_out_view.view._on_apply()

        # Assert (Then)
        servo_out_view.showerror.assert_called_once_with(
            "Servo Output Functions", "No servo output assignments could be applied."
        )
        servo_out_view.showinfo.assert_not_called()
