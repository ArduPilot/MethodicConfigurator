#!/usr/bin/env python3

"""
Unit tests for compass calibration frontend internals.

These tests focus on small non-visual behaviors that can be exercised safely
without opening a real Tk window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_compass_calibration import (
    CompassCalibrationPopup,
    CompassCalibrationView,
    CompassCalibrationWindow,
)

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def calibration_popup() -> CompassCalibrationPopup:
    """Fixture providing a minimally configured popup for cancel-flow testing."""
    popup = object.__new__(CompassCalibrationPopup)
    popup._timer_id = "after-id"
    popup.model = MagicMock()
    popup.model.cancel_calibration.return_value = (True, "")
    popup.after_cancel = MagicMock()
    popup.after = MagicMock(return_value="new-after-id")
    popup._check_progress = MagicMock()
    popup.destroy = MagicMock()
    return popup


@pytest.fixture
def progress_popup() -> CompassCalibrationPopup:
    """Fixture providing a minimally configured popup for progress-flow testing."""
    popup = object.__new__(CompassCalibrationPopup)
    popup._timer_id = "after-id"
    popup._expected_compass_ids = [0, 1]
    popup._polls_without_updates = 0
    popup.model = MagicMock()
    popup.model.get_progress = MagicMock()
    popup.model.get_active_compass_ids = MagicMock(return_value=[0, 1])
    popup.model.cancel_calibration = MagicMock()
    popup.model.finish_calibration = MagicMock()
    popup.after_cancel = MagicMock()
    popup.after = MagicMock(return_value="new-after-id")
    popup.destroy = MagicMock()
    popup.progress_bars = {0: MagicMock(), 1: MagicMock()}
    popup.completion_status = {0: False, 1: False}
    popup.rows_container = MagicMock()
    popup.hint_label = MagicMock()
    popup.update_idletasks = MagicMock()
    popup._resize_and_center = MagicMock()
    return popup


@pytest.fixture
def calibration_window() -> CompassCalibrationWindow:
    """Fixture providing a minimally configured standalone window for close-flow testing."""
    window = object.__new__(CompassCalibrationWindow)
    window.model = MagicMock()
    window.root = MagicMock()
    return window


@pytest.fixture
def calibration_view() -> CompassCalibrationView:
    """Fixture providing a minimally configured view for start-flow testing."""
    view = object.__new__(CompassCalibrationView)
    view.model = MagicMock()
    view.winfo_toplevel = MagicMock(return_value=MagicMock())
    return view


class TestCompassCalibrationPopupCancelFlow:
    """Verify cancel behavior handles backend failure and success correctly."""

    def test_user_can_close_the_popup_after_a_successful_cancel(self, calibration_popup: CompassCalibrationPopup) -> None:
        """
        The popup closes cleanly after the backend accepts the cancel request.

        GIVEN: Compass calibration is active and the backend cancel request succeeds
        WHEN: The user cancels calibration from the popup
        THEN: The polling timer is cleared
        AND: The popup is dismissed
        AND: A confirmation message is shown
        """
        # Arrange: the popup starts in an active polling state
        popup = calibration_popup

        # Act: the user cancels calibration
        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showinfo") as mock_info:
            popup._on_cancel()

        # Assert: the popup stops polling and closes
        popup.after_cancel.assert_called_once_with("after-id")
        popup.model.cancel_calibration.assert_called_once()
        mock_info.assert_called_once()
        popup.destroy.assert_called_once()
        assert popup._timer_id is None

    def test_user_sees_an_error_when_cancel_is_rejected(self, calibration_popup: CompassCalibrationPopup) -> None:
        """
        The popup reports a backend cancel failure without closing.

        GIVEN: Compass calibration is active and the backend rejects the cancel request
        WHEN: The user clicks Cancel
        THEN: An error dialog is shown
        AND: Polling is resumed so the calibration state can continue updating
        AND: The popup remains open
        """
        # Arrange: make cancel fail
        popup = calibration_popup
        popup.model.cancel_calibration.return_value = (False, "Cancel rejected")

        # Act: the user cancels calibration
        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showerror") as mock_error:
            popup._on_cancel()

        # Assert: the popup stays open and polling resumes
        popup.after_cancel.assert_called_once_with("after-id")
        popup.model.cancel_calibration.assert_called_once()
        mock_error.assert_called_once()
        popup.after.assert_called_once_with(100, popup._check_progress)
        popup.destroy.assert_not_called()
        assert popup._timer_id == "new-after-id"


class TestCompassCalibrationPopupProgressFlow:
    """Verify progress handling for completion and failure paths."""

    def test_user_sees_completion_when_all_compasses_finish(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        The popup marks the calibration complete once every compass reports success.

        GIVEN: Two compasses have reported successful completion
        WHEN: The popup polls progress
        THEN: The calibrating state is cleared
        AND: A success dialog is shown
        AND: The popup closes
        """
        # Arrange: both compasses have finished successfully
        popup = progress_popup
        popup.model.get_progress.return_value = [
            {"type": "REPORT", "compass_id": 0, "status": 4, "saved": True},
            {"type": "REPORT", "compass_id": 1, "status": 4, "saved": True},
        ]

        # Act
        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showinfo") as mock_info:
            popup._check_progress()

        # Assert
        popup.model.finish_calibration.assert_called_once()
        popup.after_cancel.assert_called_once_with("after-id")
        mock_info.assert_called_once()
        popup.destroy.assert_called_once()

    def test_user_keeps_popup_open_when_failure_cannot_be_cancelled(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        The popup stays open if the calibration failure cannot be canceled cleanly.

        GIVEN: A compass reports failure and the cancel command is rejected
        WHEN: The popup polls progress
        THEN: An error dialog is shown
        AND: Polling is resumed instead of closing the popup
        """
        # Arrange: cancellation fails after a failed report
        popup = progress_popup
        popup.model.get_progress.return_value = [{"type": "REPORT", "compass_id": 0, "status": 2, "saved": False}]
        popup.model.cancel_calibration.return_value = (False, "Cancel rejected")

        # Act
        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showerror") as mock_error:
            popup._check_progress()

        # Assert
        popup.after_cancel.assert_called_once_with("after-id")
        popup.model.cancel_calibration.assert_called_once()
        popup.model.finish_calibration.assert_not_called()
        mock_error.assert_called_once()
        popup.destroy.assert_not_called()
        popup.after.assert_called_once_with(100, popup._check_progress)
        assert popup._timer_id == "new-after-id"

    def test_user_sees_status_text_feedback_when_only_statustext_arrives(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        The popup surfaces calibration status text even when no progress packets arrive.

        GIVEN: The FC emits calibration-related STATUSTEXT messages but no MAG_CAL_PROGRESS packet
        WHEN: The popup polls progress
        THEN: The hint label is updated with the latest status text
        AND: The popup remains open
        """
        popup = progress_popup
        popup.model.get_progress.return_value = [
            {"type": "STATUS_TEXT", "compass_id": 0, "status": 6, "text": "Mag(0) good orientation: 12 21.2"}
        ]

        popup._check_progress()

        popup.hint_label.configure.assert_called_once_with(text="Mag(0) good orientation: 12 21.2")
        popup.destroy.assert_not_called()

    def test_user_sees_a_progress_row_created_from_status_text(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        Status text should still reveal the compass row even if no progress packet has arrived.

        GIVEN: The FC emits calibration-related STATUSTEXT before MAG_CAL_PROGRESS
        WHEN: The popup polls progress
        THEN: A progress row is created for the compass
        AND: The hint label still shows the latest status text
        """
        popup = progress_popup
        popup.progress_bars = {}
        popup._create_progress_row = MagicMock()
        popup.model.get_progress.return_value = [
            {"type": "STATUS_TEXT", "compass_id": 0, "status": 6, "text": "Mag(0) good orientation: 12 21.2"}
        ]

        popup._check_progress()

        popup._create_progress_row.assert_called_once_with(0)
        popup.hint_label.configure.assert_called_once_with(text="Mag(0) good orientation: 12 21.2")
        popup.destroy.assert_not_called()

    def test_user_sees_completion_when_calibration_status_text_requires_reboot(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        The popup should finish when ArduPilot reports that calibration is done and a reboot is required.

        GIVEN: The FC emits the terminal STATUSTEXT instead of MAG_CAL_REPORT
        WHEN: The popup polls progress
        THEN: The compass row is marked complete
        AND: The popup closes after the model is marked finished
        """
        popup = progress_popup
        popup.progress_bars = {0: MagicMock()}
        popup.completion_status = {0: False}
        popup.model.get_progress.return_value = [
            {"type": "STATUS_TEXT", "compass_id": 0, "status": 2, "text": "Compass calibrated requires reboot"}
        ]

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showinfo") as mock_info:
            popup._check_progress()

        assert popup.completion_status[0] is True
        popup.progress_bars[0].stop.assert_called_once()
        popup.progress_bars[0].configure.assert_any_call(mode="determinate")
        popup.progress_bars[0].configure.assert_any_call(style="Done.Horizontal.TProgressbar")
        mock_info.assert_called_once()
        popup.destroy.assert_called_once()

    def test_user_sees_completion_when_multiple_compasses_finish_through_mixed_signals(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        The popup should wait until all active compasses complete, even if they finish via different signals.

        GIVEN: One compass completes via terminal STATUSTEXT and another via MAG_CAL_REPORT
        WHEN: The popup polls progress
        THEN: Both compasses are marked complete
        AND: The popup closes only after all compasses are done
        """
        popup = progress_popup
        popup.progress_bars = {0: MagicMock(), 1: MagicMock()}
        popup.completion_status = {0: False, 1: False}
        popup.model.get_progress.return_value = [
            {"type": "STATUS_TEXT", "compass_id": 0, "status": 2, "text": "Compass calibrated requires reboot"},
            {"type": "REPORT", "compass_id": 1, "status": 4, "saved": True},
        ]

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showinfo") as mock_info:
            popup._check_progress()

        assert popup.completion_status == {0: True, 1: True}
        popup.progress_bars[0].stop.assert_called_once()
        popup.progress_bars[1].stop.assert_called_once()
        popup.progress_bars[0].configure.assert_any_call(style="Done.Horizontal.TProgressbar")
        popup.progress_bars[1].configure.assert_any_call(style="Done.Horizontal.TProgressbar")
        mock_info.assert_called_once()
        popup.destroy.assert_called_once()


class TestCompassCalibrationWindowClose:
    """Verify the standalone window performs best-effort cleanup on close."""

    def test_user_can_close_the_window_while_calibration_is_active(self, calibration_window: CompassCalibrationWindow) -> None:
        """
        Closing the standalone window cancels calibration when a session is active.

        GIVEN: Compass calibration is currently running
        WHEN: The user closes the standalone window
        THEN: The backend cancel request is sent
        AND: The window is destroyed
        """
        # Arrange: simulate an active calibration session
        window = calibration_window
        window.model._is_calibrating = True
        window.model.cancel_calibration = MagicMock(return_value=(True, ""))

        # Act: close the window
        window.on_close()

        # Assert: cleanup happens before the window disappears
        window.model.cancel_calibration.assert_called_once()
        window.root.destroy.assert_called_once()

    def test_user_can_close_the_window_without_canceling_when_idle(self, calibration_window: CompassCalibrationWindow) -> None:
        """
        Closing the standalone window should not send a cancel request when idle.

        GIVEN: Compass calibration is not running
        WHEN: The user closes the standalone window
        THEN: No cancel request is sent
        AND: The window is destroyed
        """
        # Arrange: idle window state
        window = calibration_window
        window.model._is_calibrating = False
        window.model.cancel_calibration = MagicMock()

        # Act: close the window
        window.on_close()

        # Assert: no cancel request is needed while idle
        window.model.cancel_calibration.assert_not_called()
        window.root.destroy.assert_called_once()


class TestCompassCalibrationViewStartFlow:
    """Verify the view keeps popup instances alive long enough to be used."""

    def test_user_can_open_the_instructions_popup(self, calibration_view: CompassCalibrationView) -> None:
        """
        The start button keeps a reference to the instructions dialog.

        GIVEN: The user clicks the compass calibration button
        WHEN: The view opens the instructions popup
        THEN: The popup is created with the toplevel window as parent
        AND: The view stores a reference to it
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
        The view keeps a reference to the live calibration dialog.

        GIVEN: Compass calibration starts successfully
        WHEN: The progress popup is opened
        THEN: The popup is created with the toplevel window as parent
        AND: The view stores a reference to it
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
