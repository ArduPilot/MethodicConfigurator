#!/usr/bin/env python3

"""
Behavior-driven tests for the accelerometer calibration Tkinter frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import MagicMock

from ardupilot_methodic_configurator.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel
from ardupilot_methodic_configurator.frontend_tkinter_accelerometer_calibration import AccelerometerCalibrationView

# pylint: disable=protected-access


class TestAccelerometerCalibrationView:  # pylint: disable=too-few-public-methods
    """Covers the Tkinter view widget behavior for the accelerometer calibration UI."""

    def test_on_deactivate_hides_active_wizard_and_restores_buttons(self, tk_root, mocker) -> None:
        """
        Deactivation should leave the view in a reusable state.

        GIVEN: A full calibration wizard is active
        WHEN: on_deactivate() is called
        THEN: The polling job is cancelled
        AND: The wizard is hidden and the top-level buttons are re-enabled
        """
        flight_controller = MagicMock()
        flight_controller.master = MagicMock()
        flight_controller.send_accel_calibration_full_start.return_value = (True, "")
        model = AccelerometerCalibrationDataModel(flight_controller)

        parent = ttk.Frame(tk_root)
        try:
            view = AccelerometerCalibrationView(parent, model, SimpleNamespace(root=tk_root))

            after_spy = mocker.patch.object(view, "after", return_value="after-id")
            after_cancel_spy = mocker.patch.object(view, "after_cancel")

            view._on_start_full_calibration()

            assert after_spy.called
            assert view._poll_job == "after-id"
            assert view._wizard_frame.winfo_manager() == "pack"
            assert str(view._simple_btn.cget("state")) == "disabled"
            assert str(view._level_btn.cget("state")) == "disabled"
            assert str(view._full_btn.cget("state")) == "disabled"

            view.on_deactivate()

            after_cancel_spy.assert_called_once_with("after-id")
            assert view._poll_job is None
            assert view._wizard_frame.winfo_manager() == ""
            assert str(view._simple_btn.cget("state")) == "normal"
            assert str(view._level_btn.cget("state")) == "normal"
            assert str(view._full_btn.cget("state")) == "normal"
        finally:
            parent.destroy()
