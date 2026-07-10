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
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel
from ardupilot_methodic_configurator.frontend_tkinter_accelerometer_calibration import (
    AccelerometerCalibrationView,
    _create_accelerometer_calibration_view,
)

if TYPE_CHECKING:
    from collections.abc import Generator

# pylint: disable=protected-access,redefined-outer-name

_FRONTEND = "ardupilot_methodic_configurator.frontend_tkinter_accelerometer_calibration"


@pytest.fixture
def view_with_model(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """
    Fixture building a real view backed by a mock data model.

    The tkinter ``after``/``after_cancel`` scheduling is neutralised so the
    polling loop can be driven deterministically from the tests, and the
    blocking message boxes are patched so no dialog is ever shown.
    """
    model = MagicMock(spec=AccelerometerCalibrationDataModel)
    parent = ttk.Frame(tk_root)
    view = AccelerometerCalibrationView(parent, model, SimpleNamespace(root=tk_root))
    mocker.patch.object(view, "after", return_value="after-id")
    mocker.patch.object(view, "after_cancel")
    showinfo = mocker.patch(f"{_FRONTEND}.showinfo")
    showerror = mocker.patch(f"{_FRONTEND}.showerror")
    try:
        yield SimpleNamespace(view=view, model=model, showinfo=showinfo, showerror=showerror)
    finally:
        parent.destroy()


class TestSimpleAndLevelCalibrationButtons:
    """Test the always-visible simple and level calibration buttons."""

    def test_simple_calibration_success_shows_result_dialog(self, view_with_model) -> None:
        """
        A successful simple calibration informs the user with a result dialog.

        GIVEN: The data model reports a successful simple calibration
        WHEN: The user clicks Simple Calibration
        THEN: An informational result dialog is shown and no error is raised
        """
        view_with_model.model.start_simple_calibration.return_value = (True, "Calibration successful")

        view_with_model.view._on_simple_calibration()

        view_with_model.showinfo.assert_called_once()
        assert view_with_model.showinfo.call_args.args[1] == "Calibration successful"
        view_with_model.showerror.assert_not_called()

    def test_simple_calibration_failure_shows_error_dialog(self, view_with_model) -> None:
        """
        A failed simple calibration warns the user with an error dialog.

        GIVEN: The data model reports a failed simple calibration
        WHEN: The user clicks Simple Calibration
        THEN: An error dialog is shown and no result dialog is raised
        """
        view_with_model.model.start_simple_calibration.return_value = (False, "not connected")

        view_with_model.view._on_simple_calibration()

        view_with_model.showerror.assert_called_once()
        assert view_with_model.showerror.call_args.args[1] == "not connected"
        view_with_model.showinfo.assert_not_called()

    def test_level_calibration_success_shows_result_dialog(self, view_with_model) -> None:
        """
        A successful level calibration informs the user with a result dialog.

        GIVEN: The data model reports a successful level calibration
        WHEN: The user clicks Level Calibration
        THEN: An informational result dialog is shown and no error is raised
        """
        view_with_model.model.start_level_calibration.return_value = (True, "Level calibration successful")

        view_with_model.view._on_level_calibration()

        view_with_model.showinfo.assert_called_once()
        assert view_with_model.showinfo.call_args.args[1] == "Level calibration successful"
        view_with_model.showerror.assert_not_called()

    def test_level_calibration_failure_shows_error_dialog(self, view_with_model) -> None:
        """
        A failed level calibration warns the user with an error dialog.

        GIVEN: The data model reports a failed level calibration
        WHEN: The user clicks Level Calibration
        THEN: An error dialog is shown and no result dialog is raised
        """
        view_with_model.model.start_level_calibration.return_value = (False, "vehicle not level")

        view_with_model.view._on_level_calibration()

        view_with_model.showerror.assert_called_once()
        assert view_with_model.showerror.call_args.args[1] == "vehicle not level"
        view_with_model.showinfo.assert_not_called()


class TestFullCalibrationStart:
    """Test entering and failing to enter the 6-position wizard."""

    def test_starting_full_calibration_reveals_wizard_and_disables_top_buttons(self, view_with_model) -> None:
        """
        A successful start reveals the wizard and locks the top-level buttons.

        GIVEN: The data model accepts the full calibration start
        WHEN: The user clicks Full Calibration
        THEN: The wizard panel is shown, the top buttons are disabled and polling begins
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")

        view._on_start_full_calibration()

        assert view._wizard_frame.winfo_manager() == "pack"
        assert str(view._simple_btn.cget("state")) == "disabled"
        assert str(view._level_btn.cget("state")) == "disabled"
        assert str(view._full_btn.cget("state")) == "disabled"
        assert view._poll_job == "after-id"
        view_with_model.showerror.assert_not_called()

    def test_failing_to_start_full_calibration_shows_error_and_keeps_wizard_hidden(self, view_with_model) -> None:
        """
        A rejected start surfaces an error and never shows the wizard.

        GIVEN: The data model rejects the full calibration start
        WHEN: The user clicks Full Calibration
        THEN: An error dialog is shown, the wizard stays hidden and polling never starts
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (False, "link busy")

        view._on_start_full_calibration()

        view_with_model.showerror.assert_called_once()
        assert view._wizard_frame.winfo_manager() == ""
        assert view._poll_job is None


class TestFullCalibrationPolling:
    """Test the tkinter after() polling loop that drives the wizard."""

    def test_poll_tick_reschedules_itself_while_no_position_is_ready(self, view_with_model) -> None:
        """
        Polling keeps itself alive while the flight controller stays silent.

        GIVEN: The data model has no new position to report
        WHEN: A poll tick runs
        THEN: A new poll job is scheduled and the Continue button stays disabled
        """
        view = view_with_model.view
        view_with_model.model.poll_for_next_position.return_value = None

        view._poll_tick()

        assert view._poll_job == "after-id"
        assert str(view._continue_btn.cget("state")) == "disabled"

    def test_poll_tick_presents_requested_position_and_enables_continue(self, view_with_model) -> None:
        """
        A newly requested position is shown and the user can confirm it.

        GIVEN: The data model reports a new, non-terminal position
        WHEN: A poll tick runs
        THEN: The instruction label is updated and the Continue button is enabled
        """
        view = view_with_model.view
        view_with_model.model.poll_for_next_position.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        view_with_model.model.is_calibration_complete.return_value = False
        view_with_model.model.get_position_label.return_value = "Place vehicle LEVEL and click Continue"

        view._poll_tick()

        assert str(view._position_label.cget("text")) == "Place vehicle LEVEL and click Continue"
        assert str(view._continue_btn.cget("state")) == "normal"

    def test_poll_tick_ends_calibration_successfully_on_success_sentinel(self, view_with_model) -> None:
        """
        Reaching the success sentinel ends the wizard with a success dialog.

        GIVEN: The data model reports a completed, successful calibration
        WHEN: A poll tick runs
        THEN: The wizard is hidden and a success result dialog is shown
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view._on_start_full_calibration()
        view_with_model.model.poll_for_next_position.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS
        view_with_model.model.is_calibration_complete.return_value = True
        view_with_model.model.is_calibration_successful.return_value = True

        view._poll_tick()

        assert view._wizard_frame.winfo_manager() == ""
        view_with_model.showinfo.assert_called_once()

    def test_poll_tick_ends_calibration_with_failure_on_failure_sentinel(self, view_with_model) -> None:
        """
        Reaching the failure sentinel ends the wizard with a failure dialog.

        GIVEN: The data model reports a completed but failed calibration
        WHEN: A poll tick runs
        THEN: The wizard is hidden and a failure dialog is shown
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view._on_start_full_calibration()
        view_with_model.model.poll_for_next_position.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_FAILED
        view_with_model.model.is_calibration_complete.return_value = True
        view_with_model.model.is_calibration_successful.return_value = False

        view._poll_tick()

        assert view._wizard_frame.winfo_manager() == ""
        view_with_model.showerror.assert_called_once()


class TestFullCalibrationContinueAndCancel:
    """Test the Continue and Cancel wizard controls."""

    def test_continue_confirms_position_and_resumes_polling(self, view_with_model) -> None:
        """
        Confirming a position resumes the polling loop for the next step.

        GIVEN: The data model confirms the current position successfully
        WHEN: The user clicks Continue
        THEN: The Continue button is disabled again and polling resumes
        """
        view = view_with_model.view
        view_with_model.model.confirm_current_position.return_value = (True, "confirmed")

        view._on_continue()

        assert str(view._continue_btn.cget("state")) == "disabled"
        assert view._poll_job == "after-id"
        view_with_model.showerror.assert_not_called()

    def test_continue_failure_aborts_calibration_with_error(self, view_with_model) -> None:
        """
        A failed confirmation aborts the wizard and reports the error.

        GIVEN: The data model fails to confirm the current position
        WHEN: The user clicks Continue
        THEN: An error dialog is shown and the wizard is torn down
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view._on_start_full_calibration()
        view_with_model.model.confirm_current_position.return_value = (False, "command denied")

        view._on_continue()

        assert view_with_model.showerror.called
        assert view_with_model.showerror.call_args_list[0].args[1] == "command denied"
        assert view._wizard_frame.winfo_manager() == ""

    def test_cancel_stops_polling_hides_wizard_and_notifies_user(self, view_with_model) -> None:
        """
        Cancelling tears the wizard down and tells the user it was cancelled.

        GIVEN: An active full calibration wizard
        WHEN: The user clicks Cancel
        THEN: Polling stops, the wizard is hidden and a cancellation dialog is shown
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view._on_start_full_calibration()

        view._on_cancel_full_calibration()

        assert view._poll_job is None
        assert view._wizard_frame.winfo_manager() == ""
        assert str(view._simple_btn.cget("state")) == "normal"
        view_with_model.showerror.assert_called_once()
        assert view_with_model.showerror.call_args.args[1] == "Full accelerometer calibration was cancelled."


class TestPluginLifecycle:
    """Test the plugin lifecycle hooks that keep the view reusable."""

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

    def test_destroy_cancels_pending_poll_job(self, tk_root, mocker) -> None:
        """
        Destroying the view must cancel any in-flight poll job.

        GIVEN: A view with a scheduled poll job
        WHEN: destroy() is called
        THEN: The pending poll job is cancelled before the widget is torn down
        """
        flight_controller = MagicMock()
        flight_controller.master = MagicMock()
        flight_controller.send_accel_calibration_full_start.return_value = (True, "")
        model = AccelerometerCalibrationDataModel(flight_controller)

        parent = ttk.Frame(tk_root)
        view = AccelerometerCalibrationView(parent, model, SimpleNamespace(root=tk_root))
        mocker.patch.object(view, "after", return_value="after-id")
        after_cancel_spy = mocker.patch.object(view, "after_cancel")
        view._on_start_full_calibration()

        view.destroy()

        after_cancel_spy.assert_called_once_with("after-id")
        assert view._poll_job is None
        parent.destroy()


class TestPluginFactoryFunction:  # pylint: disable=too-few-public-methods
    """Test the module-level factory function used by the plugin registry."""

    def test_factory_builds_a_view_wired_to_the_given_parent_and_model(self, tk_root) -> None:
        """
        The factory produces a ready-to-use view bound to its collaborators.

        GIVEN: A parent frame, a data model and a base window
        WHEN: The plugin factory function is invoked
        THEN: It returns an AccelerometerCalibrationView wired to that model
        """
        model = MagicMock(spec=AccelerometerCalibrationDataModel)
        parent = ttk.Frame(tk_root)
        try:
            view = _create_accelerometer_calibration_view(parent, model, SimpleNamespace(root=tk_root))

            assert isinstance(view, AccelerometerCalibrationView)
            assert view.model is model
        finally:
            parent.destroy()
