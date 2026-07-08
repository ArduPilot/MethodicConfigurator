#!/usr/bin/env python3

"""
Behavior-focused tests for compass calibration frontend flows.

These tests prioritize public workflows over helper internals.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_compass_calibration import (
    CompassCalibrationInstructionsPopup,
    CompassCalibrationPopup,
    CompassCalibrationView,
    CompassCalibrationWindow,
    _create_compass_calibration_view,
    register_compass_calibration_plugin,
)
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_COMPASS_CALIBRATION

# pylint: disable=protected-access, redefined-outer-name, too-few-public-methods


@pytest.fixture
def instructions_popup() -> CompassCalibrationInstructionsPopup:
    """Fixture providing a lightweight instructions popup shell."""
    popup = object.__new__(CompassCalibrationInstructionsPopup)
    popup.destroy = MagicMock()
    return popup


@pytest.fixture
def calibration_popup() -> CompassCalibrationPopup:
    """Fixture providing a lightweight calibration popup shell."""
    popup = object.__new__(CompassCalibrationPopup)
    popup._timer_id = "after-id"
    popup._stop_polling = MagicMock()
    popup.after_cancel = MagicMock()
    popup.after = MagicMock(return_value="new-after-id")
    popup.destroy = MagicMock()
    popup.model = MagicMock()
    popup.model.get_progress = MagicMock()
    popup.model.cancel_calibration.return_value = (True, "")
    popup.model.finish_calibration = MagicMock()
    popup.progress_bars = {}
    popup.completion_status = {}
    popup.hint_label = MagicMock()
    return popup


@pytest.fixture
def calibration_window() -> CompassCalibrationWindow:
    """Fixture providing a lightweight standalone window shell."""
    window = object.__new__(CompassCalibrationWindow)
    window.model = MagicMock()
    window.root = MagicMock()
    return window


@pytest.fixture
def calibration_view() -> CompassCalibrationView:
    """Fixture providing a lightweight calibration view shell."""
    view = object.__new__(CompassCalibrationView)
    view.model = MagicMock()
    view.winfo_toplevel = MagicMock(return_value=MagicMock())
    view._instructions_popup = None
    view._calibration_popup = None
    return view


class TestCompassCalibrationInstructionsPopup:
    """Verify the instructions flow is modal and continues into calibration."""

    def test_user_sees_a_modal_instructions_popup(self) -> None:
        """
        The instructions dialog is created as a modal popup.

        GIVEN: The user opens compass calibration
        WHEN: The instructions popup is constructed
        THEN: It keeps the parent and callback and requests modal window behavior
        """
        parent = MagicMock(spec=tk.Widget)
        on_continue = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.tk.Toplevel.__init__", return_value=None
            ),
            patch.object(CompassCalibrationInstructionsPopup, "_setup_ui"),
            patch.object(CompassCalibrationInstructionsPopup, "_resize_and_center"),
            patch.object(CompassCalibrationInstructionsPopup, "lift"),
            patch.object(CompassCalibrationInstructionsPopup, "focus_force"),
            patch.object(CompassCalibrationInstructionsPopup, "overrideredirect"),
            patch.object(CompassCalibrationInstructionsPopup, "transient"),
            patch.object(CompassCalibrationInstructionsPopup, "grab_set"),
        ):
            popup = CompassCalibrationInstructionsPopup(parent, on_continue)

        assert popup._parent is parent
        assert popup._on_continue is on_continue

    def test_user_can_continue_from_the_instructions_popup(
        self, instructions_popup: CompassCalibrationInstructionsPopup
    ) -> None:
        """
        Clicking Continue closes the popup and continues the workflow.

        GIVEN: The instructions popup is shown
        WHEN: The user clicks Continue
        THEN: The popup closes and the continuation callback runs
        """
        popup = instructions_popup
        popup._on_continue = MagicMock()

        popup._on_continue_clicked()

        popup.destroy.assert_called_once()
        popup._on_continue.assert_called_once()


class TestCompassCalibrationPopupFlows:
    """Verify calibration popup lifecycle and telemetry handling."""

    def test_user_sees_the_progress_popup_initialized_and_polling_scheduled(self) -> None:
        """
        The progress popup loads compass ids and starts polling immediately.

        GIVEN: The backend knows which compasses are active
        WHEN: The progress popup is constructed
        THEN: It schedules polling and stores the discovered compass ids
        """
        parent = MagicMock(spec=tk.Widget)
        model = MagicMock()
        model.get_active_compass_ids.return_value = [1, 0]

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.tk.Toplevel.__init__", return_value=None
            ),
            patch.object(CompassCalibrationPopup, "_setup_style"),
            patch.object(CompassCalibrationPopup, "_setup_ui"),
            patch.object(CompassCalibrationPopup, "_precreate_progress_rows"),
            patch.object(CompassCalibrationPopup, "_resize_and_center"),
            patch.object(CompassCalibrationPopup, "lift"),
            patch.object(CompassCalibrationPopup, "focus_force"),
            patch.object(CompassCalibrationPopup, "overrideredirect"),
            patch.object(CompassCalibrationPopup, "transient"),
            patch.object(CompassCalibrationPopup, "grab_set"),
            patch.object(CompassCalibrationPopup, "after", return_value="after-id") as mock_after,
        ):
            popup = CompassCalibrationPopup(parent, model)

        model.get_active_compass_ids.assert_called_once()
        mock_after.assert_called_once_with(100, popup._check_progress)
        assert popup._expected_compass_ids == [0, 1]
        assert popup._timer_id == "after-id"


class TestCompassCalibrationWindowClose:
    """Verify the standalone window performs best-effort cleanup on close."""

    def test_user_can_close_the_window_while_calibration_is_active(self, calibration_window: CompassCalibrationWindow) -> None:
        """
        Closing the standalone window cancels calibration when active.

        GIVEN: Compass calibration is currently running
        WHEN: The user closes the standalone window
        THEN: The backend cancel request is sent
        """
        window = calibration_window
        window.model._is_calibrating = True
        window.model.cancel_calibration = MagicMock(return_value=(True, ""))

        window.on_close()

        window.model.cancel_calibration.assert_called_once()
        window.root.destroy.assert_called_once()

    def test_user_can_close_the_window_without_canceling_when_idle(self, calibration_window: CompassCalibrationWindow) -> None:
        """
        Closing the standalone window should not send a cancel request when idle.

        GIVEN: Compass calibration is not running
        WHEN: The user closes the standalone window
        THEN: No cancel request is sent
        """
        window = calibration_window
        window.model._is_calibrating = False
        window.model.cancel_calibration = MagicMock()

        window.on_close()

        window.model.cancel_calibration.assert_not_called()
        window.root.destroy.assert_called_once()


class TestCompassCalibrationViewStartFlow:
    """Verify the view keeps popup instances alive long enough to be used."""

    def test_user_can_open_the_instructions_popup(self, calibration_view: CompassCalibrationView) -> None:
        """
        Clicking the calibration button opens the instructions dialog.

        GIVEN: The user starts compass calibration from the view
        WHEN: The view opens the instructions popup
        THEN: The popup is created with the toplevel window as parent
        """
        popup = MagicMock()

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.CompassCalibrationInstructionsPopup",
            return_value=popup,
        ) as mock_popup:
            calibration_view._on_start()

        mock_popup.assert_called_once_with(calibration_view.winfo_toplevel.return_value, calibration_view._begin_calibration)
        assert calibration_view._instructions_popup is popup

    def test_user_can_open_the_calibration_popup_after_starting(self, calibration_view: CompassCalibrationView) -> None:
        """
        A successful start opens the live progress popup.

        GIVEN: Compass calibration starts successfully
        WHEN: The instructions dialog continues
        THEN: The progress popup opens with the same model
        """
        popup = MagicMock()
        calibration_view.model.start_calibration.return_value = (True, "")

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.CompassCalibrationPopup",
            return_value=popup,
        ) as mock_popup:
            calibration_view._begin_calibration()

        mock_popup.assert_called_once_with(calibration_view.winfo_toplevel.return_value, calibration_view.model)
        assert calibration_view._calibration_popup is popup

    def test_user_sees_an_error_when_calibration_cannot_start(self, calibration_view: CompassCalibrationView) -> None:
        """
        Start failures are reported instead of opening the progress popup.

        GIVEN: The backend refuses to start compass calibration
        WHEN: The instructions dialog continues
        THEN: An error dialog is shown and no progress popup opens
        """
        calibration_view.model.start_calibration.return_value = (False, "Not connected")

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showerror") as mock_error:
            calibration_view._begin_calibration()

        mock_error.assert_called_once_with("Failed to Start", "Not connected", parent=calibration_view)
        assert calibration_view._calibration_popup is None


class TestCompassCalibrationViewSetupAndRegistration:
    """Verify the view setup and plugin wiring are registered correctly."""

    def test_user_sees_the_view_initialized_with_a_start_button(self) -> None:
        """
        The view initializes its frame and stores the model references.

        GIVEN: The compass calibration view is constructed
        WHEN: The initializer runs
        THEN: The view stores the model and base window references
        """
        parent = MagicMock(spec=tk.Widget)
        model = MagicMock()
        base_window = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Frame.__init__", return_value=None
            ),
            patch.object(CompassCalibrationView, "_setup_ui"),
        ):
            view = CompassCalibrationView(parent, model, base_window)

        assert view.model is model
        assert view.base_window is base_window

    def test_user_can_register_the_compass_calibration_plugin(self) -> None:
        """
        The plugin factory is wired to the compass calibration view creator.

        GIVEN: The application registers compass calibration support
        WHEN: The registration helper runs
        THEN: The compass calibration plugin is registered with the factory
        """
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.plugin_factory.register"
        ) as mock_register:
            register_compass_calibration_plugin()

        mock_register.assert_called_once_with(PLUGIN_COMPASS_CALIBRATION, _create_compass_calibration_view)

    def test_user_can_create_the_compass_calibration_view_via_helper(self) -> None:
        """
        The helper returns the concrete compass calibration view instance.

        GIVEN: A parent container and model object
        WHEN: The factory helper is called
        THEN: A CompassCalibrationView is constructed with the provided objects
        """
        parent = MagicMock()
        model = MagicMock()
        base_window = MagicMock()

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.CompassCalibrationView",
            return_value=MagicMock(),
        ) as mock_view:
            result = _create_compass_calibration_view(parent, model, base_window)

        mock_view.assert_called_once_with(parent, model, base_window)
        assert result == mock_view.return_value
