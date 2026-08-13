#!/usr/bin/env python3

"""
Behavior-driven tests for the AHRS orientation Tkinter frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from tkinter import ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterValueUpdateStatus,
)
from ardupilot_methodic_configurator.plugins.data_model_ahrs_orientation import (
    AhrsOrientationDataModel,
    AhrsOrientationEstimate,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation import AhrsOrientationView

if TYPE_CHECKING:
    from collections.abc import Generator

    from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def view_with_model(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Create a view with mocked collaborators and no active after() loop."""
    model = MagicMock(spec=AhrsOrientationDataModel)
    model.get_required_steps.return_value = ("LEVEL", "NOSE DOWN", "RIGHT")
    model.validate_detection_prerequisites.return_value = (True, "")

    parameter_editor = MagicMock()
    parameter_editor.current_step_parameters = {}
    parameter_editor.update_parameter_value.return_value = SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED)
    parameter_editor.update_parameter_values_atomically.return_value = SimpleNamespace(
        status=ParameterValueUpdateStatus.UPDATED
    )

    parameter_editor_table = MagicMock()
    base_window = SimpleNamespace(
        root=tk_root,
        parameter_editor=parameter_editor,
        parameter_editor_table=parameter_editor_table,
        show_only_differences=SimpleNamespace(get=lambda: False),
        gui_complexity="simple",
    )

    mocker.patch.object(AhrsOrientationView, "_start_imu_polling")
    parent = ttk.Frame(tk_root)
    view = AhrsOrientationView(parent, model, cast("BaseWindow", base_window))
    try:
        yield SimpleNamespace(
            view=view,
            model=model,
            parameter_editor=parameter_editor,
            parameter_editor_table=parameter_editor_table,
        )
    finally:
        parent.destroy()


def _label_texts(widget) -> list[str]:
    texts: list[str] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Label):
            text = str(child.cget("text"))
            if text:
                texts.append(text)
        texts.extend(_label_texts(child))
    return texts


class TestAhrsOrientationViewUiSurface:  # pylint: disable=too-few-public-methods
    """Static UI assertions for the simplified orientation helper."""

    def test_view_does_not_show_detected_position_or_reset_button(self, view_with_model) -> None:
        """
        The helper should only show stillness information and one action button.

        GIVEN: The AHRS orientation helper view is created
        WHEN: Its widgets are inspected
        THEN: There is no Reset samples button and no Detected position label
        """
        texts = _label_texts(view_with_model.view)

        assert "Reset samples" not in texts
        assert "Detected position:" not in texts

    def test_progress_label_translates_pose_name(self, view_with_model, mocker) -> None:
        def translate(text: str) -> str:
            return "NIVELADO" if text == "LEVEL" else text

        mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation._", side_effect=translate)

        view_with_model.view._step_index = 0
        view_with_model.view._update_wizard_text()

        assert view_with_model.view._wizard_progress_var.get() == "Step 1/3: NIVELADO"


class TestAhrsOrientationViewCustomOrientation:
    """Low-match-score custom-orientation application behavior."""

    def test_continue_restarts_estimation_and_clears_previous_recommendation(self, view_with_model) -> None:
        """
        Continue should start a fresh run once the previous estimation is complete.

        GIVEN: A completed estimation with a visible recommendation
        WHEN: Continue is pressed again
        THEN: The wizard restarts from step one and the recommendation text is cleared
        """
        view = view_with_model.view
        view._wizard_active = False
        view._step_index = 2
        view._recommendation_var.set("previous recommendation")
        view_with_model.model.reset_sequence.reset_mock()

        view._on_continue()

        view_with_model.model.reset_sequence.assert_called_once_with()
        assert view._wizard_active is True
        assert view._step_index == 0
        assert view._recommendation_var.get() == ""
        assert str(view._continue_btn.cget("state")) == "normal"
        assert view._wizard_progress_var.get() == "Step 1/3: LEVEL"

    def test_detection_does_not_start_with_unsupported_fc_orientation(self, view_with_model, mocker) -> None:
        """Detection must stop when the active FC rotation cannot safely be inverted."""
        view = view_with_model.view
        view_with_model.model.is_connected.return_value = True
        view_with_model.model.validate_detection_prerequisites.return_value = (
            False,
            "Set AHRS_ORIENTATION to 0, upload, reboot, and reconnect.",
        )
        error_spy = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation.showerror")

        view._on_start_detection()

        assert view._wizard_active is False
        view_with_model.model.reset_sequence.assert_not_called()
        error_spy.assert_called_once_with(
            "Auto-detection Not Ready",
            "Set AHRS_ORIENTATION to 0, upload, reboot, and reconnect.",
        )

    def test_imu_poll_sample_does_not_disable_continue_after_estimation_completes(self, view_with_model) -> None:
        """
        The periodic IMU poll must not re-disable Continue once a run has completed.

        GIVEN: A completed estimation (wizard inactive) with IMU data still arriving
        WHEN: A new IMU sample is handled
        THEN: The Continue button remains enabled so the user can start a new estimation
        """
        view = view_with_model.view
        view._wizard_active = False
        view._continue_btn.configure(state="normal")

        view._handle_live_imu_sample((0.0, 0.0, -1000.0))

        assert str(view._continue_btn.cget("state")) == "normal"

    def test_completed_estimation_keeps_wizard_visible_and_shows_recommendation(self, view_with_model, mocker) -> None:
        """
        A completed estimation should keep the wizard UI visible and persist the recommendation text.

        GIVEN: The final capture step and a confident estimate
        WHEN: The user completes the last capture
        THEN: The auto-detect frame stays visible and the recommendation is shown below it
        """
        estimate = AhrsOrientationEstimate(
            best_code=2,
            best_name="Yaw90",
            match_score_percent=97.5,
            is_preset_match=True,
            custom_roll_deg=0.0,
            custom_pitch_deg=0.0,
            custom_yaw_deg=90.0,
        )
        view = view_with_model.view
        view._latest_imu = (0.0, 0.0, -1000.0)
        view._step_index = 2
        view._wizard_active = True

        view_with_model.model.record_sample.return_value = (True, "Captured RIGHT sample")
        view_with_model.model.estimate_orientation.return_value = (True, estimate, "Estimation complete")
        info_spy = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation.showinfo")

        view._on_continue()

        assert view._wizard_active is False
        assert view._wizard_frame.winfo_manager() == "pack"
        assert str(view._continue_btn.cget("state")) == "normal"
        assert view._recommendation_var.get() == (
            "AHRS_ORIENTATION was set to 2 (Yaw90). Match score: 97.5%. Press upload to apply the changes."
        )
        info_spy.assert_called_once()

    def test_custom_orientation_enables_custom_rotations_before_setting_angles(self, view_with_model) -> None:
        """
        Custom orientation should stage the enable flag and all custom values in the table.

        GIVEN: A low-match-score estimate with custom Euler angles
        WHEN: The custom-orientation option is applied
        THEN: CUST_ROT_ENABLE, the three CUST_ROT1 angles, and AHRS_ORIENTATION are updated
        """
        estimate = AhrsOrientationEstimate(
            best_code=0,
            best_name="None",
            match_score_percent=88.0,
            is_preset_match=False,
            custom_roll_deg=12.3,
            custom_pitch_deg=-4.5,
            custom_yaw_deg=67.8,
        )

        applied = view_with_model.view._apply_custom_orientation(estimate)

        assert applied is True
        view_with_model.parameter_editor.update_parameter_values_atomically.assert_called_once_with(
            {
                "CUST_ROT_ENABLE": "1",
                "CUST_ROT1_ROLL": "12.3",
                "CUST_ROT1_PITCH": "-4.5",
                "CUST_ROT1_YAW": "67.8",
                "AHRS_ORIENTATION": "101",
            },
            add_missing=True,
            include_range_check=False,
        )
        view_with_model.parameter_editor_table.repopulate_table.assert_called_once_with(
            show_only_differences=False,
            gui_complexity="simple",
        )

    def test_missing_imu_does_not_disable_restart_after_estimation(self, view_with_model) -> None:
        view = view_with_model.view
        view._wizard_active = False
        view._continue_btn.configure(state="normal")

        view._handle_no_live_imu_sample()

        assert str(view._continue_btn.cget("state")) == "normal"

    @pytest.mark.parametrize("exception_type", [InvalidParameterNameError, OperationNotPossibleError])
    def test_missing_custom_parameter_is_reported_without_crashing(self, view_with_model, exception_type) -> None:
        """Expected parameter-editor domain failures should produce a clean False result."""
        view_with_model.parameter_editor.add_parameter_to_current_file.side_effect = exception_type("unavailable")

        exists = view_with_model.view._ensure_parameter_exists("CUST_ROT_ENABLE")

        assert exists is False
