#!/usr/bin/env python3

"""
Unit tests for compass calibration frontend internals.

These tests focus on helper behavior, geometry, and telemetry handling that
would be too detailed for the smoke-style frontend test file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_compass_calibration import (
    CompassCalibrationInstructionsPopup,
    CompassCalibrationPopup,
    CompassCalibrationView,
)

# pylint: disable=protected-access, redefined-outer-name, too-few-public-methods


@pytest.fixture
def instructions_popup() -> CompassCalibrationInstructionsPopup:
    """Fixture providing a lightweight instructions popup shell."""
    popup = object.__new__(CompassCalibrationInstructionsPopup)
    popup.canvas = MagicMock()
    popup.configure = MagicMock()
    popup.wm_attributes = MagicMock()
    popup._draw_rounded_rect = MagicMock()
    popup._resize_and_center = MagicMock()
    popup.destroy = MagicMock()
    popup.lift = MagicMock()
    popup.focus_force = MagicMock()
    popup.grab_set = MagicMock()
    popup.transient = MagicMock()
    popup.overrideredirect = MagicMock()
    return popup


@pytest.fixture
def progress_popup() -> CompassCalibrationPopup:
    """Fixture providing a minimally configured popup for helper-level tests."""
    popup = object.__new__(CompassCalibrationPopup)
    popup._timer_id = "after-id"
    popup._polls_without_updates = 0
    popup._no_telemetry_warning_emitted = False
    popup._expected_compass_ids = [0, 1]
    popup._bg_color = "#202020"
    popup.model = MagicMock()
    popup.model.get_progress = MagicMock()
    popup.model.get_active_compass_ids = MagicMock(return_value=[0, 1])
    popup.model.cancel_calibration = MagicMock(return_value=(True, ""))
    popup.model.finish_calibration = MagicMock()
    popup.after_cancel = MagicMock()
    popup.after = MagicMock(return_value="new-after-id")
    popup.destroy = MagicMock()
    popup.progress_bars = {0: MagicMock(), 1: MagicMock()}
    popup.completion_status = {0: False, 1: False}
    popup.rows_container = MagicMock()
    popup.hint_label = MagicMock()
    popup.configure = MagicMock()
    popup._resize_and_center = MagicMock()
    popup.update_idletasks = MagicMock()
    popup.minsize = MagicMock()
    popup.geometry = MagicMock()
    popup._start_move = MagicMock()
    popup._do_move = MagicMock()
    popup._stop_polling = MagicMock()
    return popup


@pytest.fixture
def calibration_view() -> CompassCalibrationView:
    """Fixture providing a lightweight calibration view shell."""
    # pylint: disable=duplicate-code
    view = object.__new__(CompassCalibrationView)
    view.model = MagicMock()
    view.winfo_toplevel = MagicMock(return_value=MagicMock())
    view._instructions_popup = None
    view._calibration_popup = None
    return view
    # pylint: enable=duplicate-code


class TestCompassCalibrationInstructionsPopupInternals:
    """Verify the popup layout helpers and geometry calculations."""

    def test_user_sees_the_instructions_layout_rendered_as_expected(
        self, instructions_popup: CompassCalibrationInstructionsPopup
    ) -> None:
        """
        The instructions popup lays out its card, text, and button.

        GIVEN: A constructed instructions popup
        WHEN: The layout helper runs
        THEN: The content canvas receives the expected geometry and widgets
        """
        popup = instructions_popup
        canvas = MagicMock()
        label = MagicMock()
        button = MagicMock()
        label.winfo_reqwidth.return_value = 260
        label.winfo_reqheight.return_value = 100
        button.winfo_reqwidth.return_value = 120
        button.winfo_reqheight.return_value = 32

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.tk.Canvas", return_value=canvas),
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.tk.Label", return_value=label),
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Button", return_value=button),
        ):
            popup._setup_ui()

        popup.configure.assert_called_once_with(bg="#fffef0")
        canvas.pack.assert_called_once_with(fill="both", expand=True)
        canvas.configure.assert_called_once_with(width=320, height=200)
        popup._draw_rounded_rect.assert_any_call((0, 0, 320, 200), radius=22, fill="#ffffe0", outline="")
        popup._draw_rounded_rect.assert_any_call((3, 3, 317, 197), radius=19, fill="", outline="#d8d8a0", width=1)
        assert popup._width == 320
        assert popup._height == 200

    def test_user_sees_the_rounded_card_polygon_drawn(self) -> None:
        """
        The rounded rectangle helper draws a smooth polygon on the canvas.

        GIVEN: The instructions canvas is available
        WHEN: The rounded rectangle helper is called
        THEN: The helper returns the polygon id from Tk
        """
        popup = object.__new__(CompassCalibrationInstructionsPopup)
        popup.canvas = MagicMock()
        popup.canvas.create_polygon.return_value = 123

        result = popup._draw_rounded_rect((0, 0, 10, 20), radius=4, fill="blue")

        assert result == 123
        popup.canvas.create_polygon.assert_called_once()

    def test_user_sees_the_instructions_popup_centered_on_the_parent(self) -> None:
        """
        The popup centers itself on top of its parent window.

        GIVEN: A parent window with known position and size
        WHEN: The resize helper runs
        THEN: The popup geometry uses the computed center coordinates
        """
        popup = object.__new__(CompassCalibrationInstructionsPopup)
        popup._width = 320
        popup._height = 192
        popup.update_idletasks = MagicMock()
        popup._parent = MagicMock()
        popup._parent.winfo_rootx.return_value = 100
        popup._parent.winfo_rooty.return_value = 200
        popup._parent.winfo_width.return_value = 500
        popup._parent.winfo_height.return_value = 400
        popup.geometry = MagicMock()

        popup._resize_and_center()

        popup.geometry.assert_called_once_with("320x192+190+304")


class TestCompassCalibrationPopupInternals:  # pylint: disable=too-many-public-methods
    """Verify popup helper logic for styles, rows, and telemetry polling."""

    def test_user_sees_the_progress_popup_destroy_cancel_polling_before_closing(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        Destroying the popup stops polling before the window closes.

        GIVEN: The popup has an active timer
        WHEN: destroy is called
        THEN: The polling callback is cleared before Tk destroys the window
        """
        popup = progress_popup

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.tk.Toplevel.destroy") as mock_destroy:
            CompassCalibrationPopup.destroy(popup)

        popup._stop_polling.assert_called_once()
        mock_destroy.assert_called_once()

    def test_user_sees_the_progress_popup_style_configured(self) -> None:
        """
        The popup configures the progress bar styles used by the calibration view.

        GIVEN: A popup instance
        WHEN: The style helper runs
        THEN: The base and completed progressbar styles are configured
        """
        popup = object.__new__(CompassCalibrationPopup)
        popup.cget = MagicMock(return_value="#202020")
        style = MagicMock()
        style.lookup.return_value = ""

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Style", return_value=style):
            popup._setup_style()

        assert popup._bg_color == "#202020"
        style.lookup.assert_any_call("TFrame", "background")
        style.configure.assert_any_call("Horizontal.TProgressbar", borderwidth=0, thickness=24)
        style.configure.assert_any_call(
            "Done.Horizontal.TProgressbar",
            background="#8fbc8f",
            borderwidth=0,
            thickness=24,
            troughcolor=style.lookup.return_value,
        )

    def test_user_sees_the_progress_popup_layout_created(self) -> None:
        """
        The popup builds its title bar, hint label, and cancel control.

        GIVEN: A popup instance with a configured background color
        WHEN: The UI setup helper runs
        THEN: The expected widgets are created and packed
        """
        popup = object.__new__(CompassCalibrationPopup)
        popup._bg_color = "#202020"
        popup.configure = MagicMock()
        popup._start_move = MagicMock()
        popup._do_move = MagicMock()
        popup._on_cancel = MagicMock()

        outer_frame = MagicMock()
        title_bar = MagicMock()
        content_frame = MagicMock()
        bars_frame = MagicMock()
        rows_container = MagicMock()
        title_label = MagicMock()
        hint_label = MagicMock()
        cancel_button = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.tk.Frame",
                side_effect=[outer_frame, title_bar],
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Frame",
                side_effect=[content_frame, bars_frame, rows_container],
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.tk.Label", return_value=title_label),
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Label", return_value=hint_label),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Button", return_value=cancel_button
            ),
        ):
            popup._setup_ui()

        popup.configure.assert_called_once_with(bg="#202020")
        outer_frame.pack.assert_called_once_with(fill="both", expand=True)
        title_bar.pack.assert_called_once_with(fill="x", side="top")
        content_frame.pack.assert_called_once_with(fill="both", expand=True, padx=20, pady=20)
        hint_label.pack.assert_called_once_with(pady=(0, 10))
        cancel_button.pack.assert_called_once_with(pady=(15, 0))
        assert popup.hint_label is hint_label
        assert popup.rows_container is rows_container
        assert popup.cancel_button is cancel_button

    def test_user_can_cancel_calibration_from_the_popup(self) -> None:
        """
        The cancel action stops polling and closes the popup when the backend accepts it.

        GIVEN: Calibration is running
        WHEN: The user clicks Cancel
        THEN: The backend cancel request is sent and the popup closes
        """
        popup = object.__new__(CompassCalibrationPopup)
        popup._timer_id = "after-id"
        popup.after_cancel = MagicMock()
        popup.after = MagicMock(return_value="new-after-id")
        popup.destroy = MagicMock()
        popup.model = MagicMock()
        popup.model.cancel_calibration = MagicMock(return_value=(True, ""))
        popup.model.finish_calibration = MagicMock()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showinfo") as mock_info:
            popup._on_cancel()

        popup.after_cancel.assert_called_once_with("after-id")
        popup.model.cancel_calibration.assert_called_once()
        popup.model.finish_calibration.assert_called_once()
        mock_info.assert_called_once()
        popup.destroy.assert_called_once()

    def test_user_sees_backend_rejection_when_cancel_fails(self) -> None:
        """
        The popup keeps polling when the backend rejects cancel.

        GIVEN: The backend refuses to cancel calibration
        WHEN: The user clicks Cancel
        THEN: An error dialog is shown and polling resumes
        """
        popup = object.__new__(CompassCalibrationPopup)
        popup._timer_id = "after-id"
        popup.after_cancel = MagicMock()
        popup.after = MagicMock(return_value="new-after-id")
        popup.destroy = MagicMock()
        popup.model = MagicMock()
        popup.model.cancel_calibration = MagicMock(return_value=(False, "Cancel rejected"))
        popup.model.finish_calibration = MagicMock()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showerror") as mock_error:
            popup._on_cancel()

        mock_error.assert_called_once_with("Failed to Cancel", "Cancel rejected", parent=popup)
        popup.after_cancel.assert_called_once_with("after-id")
        popup.after.assert_called_once_with(100, popup._check_progress)
        popup.destroy.assert_not_called()

    def test_user_sees_progress_updates_when_telemetry_arrives(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        Progress telemetry updates the visible progress bar.

        GIVEN: The backend emits a MAG_CAL_PROGRESS packet
        WHEN: The popup polls progress
        THEN: The matching progress bar becomes determinate and shows the percentage
        """
        popup = progress_popup
        progress_bar = MagicMock()
        popup.progress_bars = {0: progress_bar}
        popup.completion_status = {0: False}
        popup.model.get_progress.return_value = [{"type": "PROGRESS", "compass_id": 0, "status": 1, "completion_pct": 33}]

        popup._check_progress()

        progress_bar.stop.assert_called_once()
        progress_bar.configure.assert_any_call(mode="determinate")
        progress_bar.__setitem__.assert_called_with("value", 33)
        popup.after.assert_called_once_with(100, popup._check_progress)
        popup.destroy.assert_not_called()

    def test_user_sees_completion_when_status_text_reports_reboot_required(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        A terminal status text should still complete the workflow.

        GIVEN: ArduPilot reports that calibration is finished and reboot is required
        WHEN: The popup polls progress
        THEN: The popup marks the compass complete and closes
        """
        popup = progress_popup
        progress_bar = MagicMock()
        popup.progress_bars = {0: progress_bar}
        popup.completion_status = {0: False}
        popup.model.get_progress.return_value = [
            {"type": "STATUS_TEXT", "compass_id": 0, "status": 2, "text": "Compass calibrated requires reboot"}
        ]

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showinfo") as mock_info:
            popup._check_progress()

        assert popup.completion_status[0] is True
        progress_bar.stop.assert_called_once()
        progress_bar.configure.assert_any_call(mode="determinate")
        progress_bar.configure.assert_any_call(style="Done.Horizontal.TProgressbar")
        mock_info.assert_called_once()
        popup.model.finish_calibration.assert_called_once()
        popup.destroy.assert_called_once()

    def test_user_sees_failure_when_report_cannot_be_saved(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        A failed report prompts cancellation and an error message.

        GIVEN: A compass reports calibration failure
        WHEN: The popup polls progress
        THEN: The backend is asked to cancel and the popup closes on success
        """
        popup = progress_popup
        progress_bar = MagicMock()
        popup.progress_bars = {0: progress_bar}
        popup.completion_status = {0: False}
        popup.model.get_progress.return_value = [{"type": "REPORT", "compass_id": 0, "status": 2, "saved": False}]
        popup.model.cancel_calibration.return_value = (True, "")

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showerror") as mock_error:
            popup._check_progress()

        popup._stop_polling.assert_called_once()
        popup.model.cancel_calibration.assert_called_once()
        popup.model.finish_calibration.assert_called_once()
        mock_error.assert_called_once()
        popup.destroy.assert_called_once()

    def test_user_sees_progress_text_when_only_statustext_arrives(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        Status text should still update the user-facing hint.

        GIVEN: The FC emits calibration-related STATUSTEXT but no progress packet
        WHEN: The popup polls progress
        THEN: The hint label shows the latest status text
        """
        popup = progress_popup
        popup.progress_bars = {0: MagicMock()}
        popup.completion_status = {0: False}
        popup.model.get_progress.return_value = [
            {"type": "STATUS_TEXT", "compass_id": 0, "status": 6, "text": "Mag(0) good orientation: 12 21.2"}
        ]

        popup._check_progress()

        popup.hint_label.configure.assert_called_once_with(text="Mag(0) good orientation: 12 21.2")
        popup.destroy.assert_not_called()

    def test_user_sees_expected_compass_ids_loaded_and_sorted(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        The popup normalizes the expected compass ids before polling begins.

        GIVEN: The model reports active compass ids out of order
        WHEN: The helper loads them
        THEN: The ids are returned as a sorted unique list
        """
        popup = progress_popup
        popup.model.get_active_compass_ids.return_value = [3, 1, 2, 1]

        assert popup._load_expected_compass_ids() == [1, 2, 3]

    def test_user_sees_no_expected_compasses_when_model_raises(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        The popup falls back to waiting for telemetry when the model cannot answer.

        GIVEN: The model raises while being queried for active compasses
        WHEN: The helper loads expected ids
        THEN: No ids are preloaded
        """
        popup = progress_popup
        popup.model.get_active_compass_ids.side_effect = RuntimeError("boom")

        assert popup._load_expected_compass_ids() == []

    def test_user_sees_no_expected_compasses_when_model_returns_unexpected_type(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        The popup ignores unexpected model return values instead of crashing.

        GIVEN: The model returns a non-iterable compass list
        WHEN: The helper loads expected ids
        THEN: The popup falls back to telemetry discovery
        """
        popup = progress_popup
        popup.model.get_active_compass_ids.return_value = "not-a-list"

        assert popup._load_expected_compass_ids() == []

    def test_user_sees_placeholder_rows_created_for_expected_compasses(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        The popup pre-creates rows for the compasses the model already knows about.

        GIVEN: The popup already knows the active compass ids
        WHEN: Placeholder rows are precreated
        THEN: A row is requested for each expected compass
        """
        popup = progress_popup
        popup._create_progress_row = MagicMock()

        popup._precreate_progress_rows()

        assert popup._create_progress_row.call_args_list == [((0,), {}), ((1,), {})]

    def test_user_sees_no_placeholder_rows_when_no_active_compasses_are_known(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        The popup waits for telemetry when the model has no known compass ids.

        GIVEN: The model does not provide active compass ids
        WHEN: Placeholder rows are created
        THEN: No rows are created yet
        """
        popup = progress_popup
        popup._expected_compass_ids = []
        popup._create_progress_row = MagicMock()

        popup._precreate_progress_rows()

        popup._create_progress_row.assert_not_called()

    def test_user_can_create_and_reuse_progress_rows_for_compasses(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        The popup creates a row once and returns the same row on later requests.

        GIVEN: A compass id has not yet been rendered
        WHEN: The row helper is called twice
        THEN: The row is created only once and reused afterwards
        """
        popup = progress_popup
        row = MagicMock()
        progress_bar = MagicMock()
        progress_bar.start = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Frame", return_value=row),
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Label"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Progressbar",
                return_value=progress_bar,
            ),
        ):
            first = popup._create_progress_row(7)
            second = popup._create_progress_row(7)

        assert first is progress_bar
        assert second is progress_bar
        row.pack.assert_called_once_with(fill="x", pady=8)
        progress_bar.start.assert_called_once_with(10)
        assert popup.progress_bars[7] is progress_bar
        assert popup.completion_status[7] is False

    def test_user_can_drag_the_popup_window(self) -> None:
        """
        The popup tracks drag origin and updates its geometry accordingly.

        GIVEN: The user drags the custom title bar
        WHEN: The move helpers run
        THEN: The popup geometry is updated relative to the drag origin
        """
        popup = object.__new__(CompassCalibrationPopup)
        popup._drag_x = 0
        popup._drag_y = 0
        popup._start_move(MagicMock(x=12, y=18))
        popup.winfo_x = MagicMock(return_value=100)
        popup.winfo_y = MagicMock(return_value=200)
        popup.geometry = MagicMock()

        popup._do_move(MagicMock(x=30, y=40))

        assert popup._drag_x == 12
        assert popup._drag_y == 18
        popup.geometry.assert_called_once_with("+118+222")

    def test_user_sees_the_progress_popup_resized_and_centered_on_the_parent(self) -> None:
        """
        The popup sizes itself and centers over the main window.

        GIVEN: A known parent geometry
        WHEN: The resize helper runs
        THEN: The popup applies a centered geometry string
        """
        popup = object.__new__(CompassCalibrationPopup)
        popup.update_idletasks = MagicMock()
        popup.minsize = MagicMock()
        popup.winfo_reqwidth = MagicMock(return_value=640)
        popup.winfo_reqheight = MagicMock(return_value=360)
        popup.geometry = MagicMock()
        popup._parent = MagicMock()
        popup._parent.winfo_rootx.return_value = 50
        popup._parent.winfo_rooty.return_value = 75
        popup._parent.winfo_width.return_value = 800
        popup._parent.winfo_height.return_value = 600

        popup._resize_and_center()

        popup.minsize.assert_called_once_with(560, 320)
        popup.geometry.assert_any_call("640x360")
        popup.geometry.assert_any_call("640x360+130+195")

    def test_user_sees_a_telemetry_warning_after_long_silence(self, progress_popup: CompassCalibrationPopup) -> None:
        """
        The popup warns when no progress telemetry arrives for a long time.

        GIVEN: The model keeps returning no progress updates
        WHEN: The popup polls fifty times
        THEN: A warning is logged once and polling continues
        """
        popup = progress_popup
        popup.model.get_progress.return_value = []
        popup._timer_id = None
        popup.after = MagicMock(return_value="next-after-id")

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.logging_warning") as mock_warning:
            for _ in range(50):
                popup._check_progress()

        mock_warning.assert_called_once()
        assert popup._polls_without_updates == 50
        assert popup._no_telemetry_warning_emitted is True
        assert popup.after.call_count == 50

    def test_user_sees_generic_status_text_without_creating_a_progress_row(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        Generic status text should update the hint without inventing a compass row.

        GIVEN: The FC emits calibration-related STATUSTEXT before MAG_CAL_PROGRESS
        WHEN: The popup polls progress
        THEN: The hint label is updated and no progress row is created yet
        """
        popup = progress_popup
        popup.progress_bars = {}
        popup.completion_status = {}
        popup._create_progress_row = MagicMock()
        popup.model.get_progress.return_value = [{"type": "STATUS_TEXT", "status": 6, "text": "Calibration running"}]

        popup._check_progress()

        popup._create_progress_row.assert_not_called()
        popup.hint_label.configure.assert_called_once_with(text="Calibration running")

    def test_user_sees_completion_when_generic_status_text_reports_reboot_required(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        A generic terminal status text should finish all precreated compasses.

        GIVEN: The FC emits the reboot-required message without a compass id
        WHEN: The popup polls progress
        THEN: All known compasses are marked complete and the popup closes
        """
        popup = progress_popup
        progress_bar_0 = MagicMock()
        progress_bar_1 = MagicMock()
        popup.progress_bars = {0: progress_bar_0, 1: progress_bar_1}
        popup.completion_status = {0: False, 1: False}
        popup.model.get_progress.return_value = [
            {"type": "STATUS_TEXT", "status": 2, "text": "Compass calibrated requires reboot"}
        ]

        with patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.messagebox.showinfo") as mock_info:
            popup._check_progress()

        assert popup.completion_status == {0: True, 1: True}
        progress_bar_0.stop.assert_called_once()
        progress_bar_1.stop.assert_called_once()
        mock_info.assert_called_once()
        popup.model.finish_calibration.assert_called_once()
        popup.destroy.assert_called_once()

    def test_user_sees_completion_when_multiple_compasses_finish_through_mixed_signals(
        self, progress_popup: CompassCalibrationPopup
    ) -> None:
        """
        The popup closes only after every compass reports completion.

        GIVEN: One compass completes via terminal status text and another via report telemetry
        WHEN: The popup polls progress
        THEN: Both compasses are marked complete and the popup closes once
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
        popup.after_cancel.assert_called_once_with("after-id")
        popup.model.finish_calibration.assert_called_once()
        mock_info.assert_called_once()
        popup.destroy.assert_called_once()


class TestCompassCalibrationViewInternals:
    """Verify view setup helpers without exercising the whole workflow."""

    def test_user_sees_the_view_layout_created_with_a_start_button(self, calibration_view: CompassCalibrationView) -> None:
        """
        The view creates and packs its start button.

        GIVEN: A view instance
        WHEN: The UI setup helper runs
        THEN: A start button is created and packed
        """
        popup = calibration_view
        frame = MagicMock()
        button = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Frame", return_value=frame),
            patch("ardupilot_methodic_configurator.frontend_tkinter_compass_calibration.ttk.Button", return_value=button),
        ):
            popup._setup_ui()

        frame.pack.assert_called_once_with(fill="x", expand=False, padx=10, pady=10)
        button.pack.assert_called_once_with(pady=5)
        assert popup.start_button is button
