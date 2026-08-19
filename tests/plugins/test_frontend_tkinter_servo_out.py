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

from ardupilot_methodic_configurator.plugins.data_model_servo_out import ServoOutDataModel, ServoOutRecommendationStatus
from ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out import ServoOutView

# pytest injects fixtures by matching the test function parameter name.
# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def servo_out_view(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Provide a real servo-output view with modal dialogs isolated."""
    model = MagicMock(spec=ServoOutDataModel)
    model.get_recommendations.return_value = (
        {"SERVO1_FUNCTION": 33},
        "Recommended 1 motor output assignment.",
        ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE,
    )
    showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showinfo")
    showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showerror")
    parent = ttk.Frame(tk_root)
    parameter_editor_table = MagicMock()
    try:
        yield SimpleNamespace(
            view=ServoOutView(
                parent,
                model,
                SimpleNamespace(
                    root=tk_root,
                    parameter_editor_table=parameter_editor_table,
                    show_only_differences=SimpleNamespace(get=lambda: False),
                    gui_complexity="simple",
                ),
            ),
            model=model,
            showinfo=showinfo,
            showerror=showerror,
            parameter_editor_table=parameter_editor_table,
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
        servo_out_view.model.apply_recommendations.return_value = (
            ["SERVO1_FUNCTION"],
            "Applied 1 motor output assignment.",
            ServoOutRecommendationStatus.APPLIED,
        )

        # Act (When)
        servo_out_view.view._on_apply()

        # Assert (Then)
        servo_out_view.showinfo.assert_called_once_with("Servo Output Functions", "Applied 1 motor output assignment.")
        servo_out_view.showerror.assert_not_called()
        servo_out_view.parameter_editor_table.repopulate_table.assert_called_once_with(
            show_only_differences=False, gui_complexity="simple"
        )
        assert "SERVO1_FUNCTION=33" in servo_out_view.view._summary.get()

    def test_user_sees_reason_when_no_recommendation_can_be_applied(self, servo_out_view) -> None:
        """
        An unapplied recommendation provides an actionable error.

        GIVEN: The model cannot apply any motor assignments
        WHEN: The user selects Apply Recommended Motor Outputs
        THEN: The view shows the model's reason without a success dialog
        """
        # Arrange (Given)
        servo_out_view.model.apply_recommendations.return_value = (
            [],
            "No servo output assignments could be applied.",
            ServoOutRecommendationStatus.ERROR,
        )

        # Act (When)
        servo_out_view.view._on_apply()

        # Assert (Then)
        servo_out_view.showerror.assert_called_once_with(
            "Servo Output Functions", "No servo output assignments could be applied."
        )
        servo_out_view.showinfo.assert_not_called()

    def test_user_sees_information_when_outputs_are_already_complete(self, servo_out_view) -> None:
        """
        An already-complete output mapping is not shown as an error.

        GIVEN: The model reports that all motor outputs are already assigned
        WHEN: The user selects Apply Recommended Motor Outputs
        THEN: The view shows an informational dialog instead of an error
        """
        # Arrange (Given)
        servo_out_view.model.apply_recommendations.return_value = (
            [],
            "All motor output functions are already assigned; no changes are needed.",
            ServoOutRecommendationStatus.NO_CHANGES,
        )

        # Act (When)
        servo_out_view.view._on_apply()

        # Assert (Then)
        servo_out_view.showinfo.assert_called_once_with(
            "Servo Output Functions", "All motor output functions are already assigned; no changes are needed."
        )
        servo_out_view.showerror.assert_not_called()

    def test_user_sees_information_when_a_motor_is_not_assigned(self, servo_out_view) -> None:
        """A homeless-motor warning is informational because this view cannot route it."""
        message = "Motor1 is not assigned to any output."
        servo_out_view.model.apply_recommendations.return_value = (
            [],
            message,
            ServoOutRecommendationStatus.UNASSIGNED_MOTORS,
        )

        servo_out_view.view._on_apply()

        servo_out_view.showinfo.assert_called_once_with("Servo Output Functions", message)
        servo_out_view.showerror.assert_not_called()

    def test_unassigned_motor_message_is_informational_without_tk(self, mocker) -> None:
        """The dialog classification remains testable when a display is unavailable."""
        message = "Motor1 is not assigned to any output."
        model = MagicMock(spec=ServoOutDataModel)
        model.apply_recommendations.return_value = ([], message, ServoOutRecommendationStatus.UNASSIGNED_MOTORS)
        view = ServoOutView.__new__(ServoOutView)
        view.model = model
        mocker.patch.object(ServoOutView, "_refresh_summary")
        showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showinfo")
        showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showerror")

        view._on_apply()

        showinfo.assert_called_once_with("Servo Output Functions", message)
        showerror.assert_not_called()

    def test_apply_failure_with_unassigned_warning_is_still_an_error(self, mocker) -> None:
        """A failed apply is not hidden by a trailing unassigned-motor warning."""
        message = "No servo output assignments could be applied. Motor1 is not assigned to any output."
        model = MagicMock(spec=ServoOutDataModel)
        model.apply_recommendations.return_value = ([], message, ServoOutRecommendationStatus.ERROR)
        view = ServoOutView.__new__(ServoOutView)
        view.model = model
        mocker.patch.object(ServoOutView, "_refresh_summary")
        showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showinfo")
        showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_servo_out.showerror")

        view._on_apply()

        showerror.assert_called_once_with("Servo Output Functions", message)
        showinfo.assert_not_called()
