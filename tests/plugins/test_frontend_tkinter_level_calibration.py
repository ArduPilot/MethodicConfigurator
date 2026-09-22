#!/usr/bin/env python3

"""
Behavior-driven tests for the level calibration Tkinter plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from threading import Event
from time import monotonic
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration import LevelCalibrationView

# pytest injects fixtures by matching the test function parameter name.
# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def level_calibration_view(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Provide a real level-calibration view with its external UI effects isolated."""
    # pylint: disable=duplicate-code
    model = MagicMock(spec=LevelCalibrationDataModel)
    base_window = SimpleNamespace(
        root=tk_root,
        set_fc_operation_busy=MagicMock(),
        download_flight_controller_parameters=MagicMock(),
        parameter_editor=SimpleNamespace(
            fc_parameters={"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02},
            download_flight_controller_parameters=MagicMock(),
            refresh_current_step_fc_values=MagicMock(),
            update_parameters_from_fc_values=MagicMock(),
        ),
        repopulate_parameter_table=MagicMock(),
    )
    # pylint: enable=duplicate-code
    base_window.parameter_editor.download_flight_controller_parameters.return_value = (
        {"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02},
        {},
    )
    showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showinfo")
    showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showerror")
    showwarning = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showwarning")
    progress_window = mocker.MagicMock()
    mocker.patch(
        "ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.ProgressWindow",
        return_value=progress_window,
    )
    parent = ttk.Frame(tk_root)
    after = mocker.patch.object(LevelCalibrationView, "after", return_value="after-id")
    mocker.patch.object(LevelCalibrationView, "after_cancel")
    try:
        yield SimpleNamespace(
            view=LevelCalibrationView(parent, model, base_window),
            model=model,
            base_window=base_window,
            showinfo=showinfo,
            showerror=showerror,
            showwarning=showwarning,
            progress_window=progress_window,
            after=after,
        )
    finally:
        parent.destroy()


class TestLevelCalibrationView:
    """Test the user feedback displayed by the level calibration view."""

    def test_level_calibration_does_not_block_the_tk_callback(self, level_calibration_view) -> None:
        """
        A slow controller acknowledgement must not freeze the Tk event loop.

        GIVEN: Level calibration is waiting for a controller response
        WHEN: The user starts level calibration
        THEN: The button callback returns while the operation runs in the background
        """
        started = Event()
        release = Event()

        def blocked_calibration(**_kwargs: object) -> tuple[bool, str]:
            started.set()
            release.wait(timeout=1.0)
            return True, "Level calibration successful"

        level_calibration_view.model.start_level_calibration.side_effect = blocked_calibration

        start_time = monotonic()
        level_calibration_view.view._on_level_calibration()
        elapsed = monotonic() - start_time

        assert started.wait(timeout=0.2)
        assert elapsed < 0.2
        assert str(level_calibration_view.view._level_btn.cget("state")) == "disabled"

        release.set()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)

    def test_user_is_warned_to_calibrate_accelerometers_first(self, level_calibration_view) -> None:
        """
        The level-trim panel preserves the calibration-order prerequisite.

        GIVEN: The level-calibration panel is displayed
        WHEN: The user reads its instructions
        THEN: The panel says level trim must follow simple or full calibration
        """
        assert "Must be performed AFTER a Simple or Full calibration." in level_calibration_view.view._level_info_label.cget(
            "text"
        )

    def test_parameter_redownload_does_not_block_the_tk_poll(self, level_calibration_view) -> None:
        """A slow parameter readback remains off the Tk event loop."""
        started = Event()
        release = Event()

        def blocked_download(**_kwargs) -> tuple[dict[str, float], dict]:
            started.set()
            release.wait(timeout=1.0)
            return {"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02}, {}

        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration successful")
        level_calibration_view.base_window.parameter_editor.download_flight_controller_parameters.side_effect = (
            blocked_download
        )
        level_calibration_view.view._on_level_calibration()

        assert started.wait(timeout=0.2)
        start_time = monotonic()
        level_calibration_view.view._poll_level_calibration()
        elapsed = monotonic() - start_time

        assert elapsed < 0.2
        assert level_calibration_view.showinfo.call_count == 0
        level_calibration_view.base_window.parameter_editor.refresh_current_step_fc_values.assert_not_called()

        release.set()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()
        level_calibration_view.showinfo.assert_called_once_with("Calibration Result", "Level calibration successful")
        level_calibration_view.base_window.parameter_editor.refresh_current_step_fc_values.assert_called_once_with()

    def test_layout_matches_the_accelerometer_calibration_rows(self, level_calibration_view) -> None:
        """
        The level-calibration row uses the same button/text arrangement as accelerometer calibration.

        GIVEN: The level-calibration view is displayed
        WHEN: Its controls are laid out
        THEN: The button is left-aligned and the explanatory text fills the row on the right
        """
        button_pack = level_calibration_view.view._level_btn.pack_info()
        info_pack = level_calibration_view.view._level_info_label.pack_info()

        assert button_pack["side"] == "left"
        assert button_pack["padx"] == (8, 16)
        assert button_pack["anchor"] == "n"
        assert info_pack["side"] == "left"
        assert info_pack["fill"] == "x"
        assert info_pack["expand"] == 1
        assert info_pack["anchor"] == "w"

    def test_user_sees_success_when_level_trim_completes(self, level_calibration_view) -> None:
        """
        A successful calibration is presented as an informational result.

        GIVEN: The model completes the level trim successfully
        WHEN: The user selects Level Calibration
        THEN: The view shows the completion message without an error dialog
        """
        # Arrange (Given)
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration successful")

        # Act (When)
        level_calibration_view.view._on_level_calibration()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

        # Assert (Then)
        level_calibration_view.showinfo.assert_called_once_with("Calibration Result", "Level calibration successful")
        level_calibration_view.showerror.assert_not_called()
        level_calibration_view.showwarning.assert_not_called()
        level_calibration_view.base_window.download_flight_controller_parameters.assert_not_called()
        level_calibration_view.base_window.parameter_editor.download_flight_controller_parameters.assert_called_once_with(
            update_current_step_fc_values=False
        )
        level_calibration_view.base_window.parameter_editor.refresh_current_step_fc_values.assert_called_once_with()
        level_calibration_view.base_window.parameter_editor.update_parameters_from_fc_values.assert_called_once_with(
            {"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02}
        )
        level_calibration_view.base_window.repopulate_parameter_table.assert_called_once_with()

    def test_user_sees_error_when_level_trim_fails(self, level_calibration_view) -> None:
        """
        A failed calibration is presented as an actionable error.

        GIVEN: The model rejects the level trim
        WHEN: The user selects Level Calibration
        THEN: The view shows the failure message without a success dialog
        """
        # Arrange (Given)
        level_calibration_view.model.start_level_calibration.return_value = (False, "Vehicle is moving")

        # Act (When)
        level_calibration_view.view._on_level_calibration()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

        # Assert (Then)
        level_calibration_view.showerror.assert_called_once_with("Calibration Failed", "Vehicle is moving")
        level_calibration_view.showinfo.assert_not_called()

    def test_user_is_warned_and_stale_trim_values_are_not_staged_when_readback_returns_no_parameters(
        self, level_calibration_view
    ) -> None:
        """
        A failed readback must not turn cached, pre-calibration trim values into a success.

        GIVEN: The flight controller accepts level calibration but parameter readback returns no parameters
        WHEN: The background operation completes
        THEN: Calibration success is shown, the readback problem is warned about, and no values are staged
        """
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration successful")
        level_calibration_view.base_window.parameter_editor.download_flight_controller_parameters.return_value = ({}, {})

        level_calibration_view.view._on_level_calibration()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

        level_calibration_view.showinfo.assert_called_once_with("Calibration Result", "Level calibration successful")
        level_calibration_view.showwarning.assert_called_once_with(
            "Calibration Readback Failed",
            "Could not read calibrated parameters from the flight controller.",
        )
        level_calibration_view.base_window.parameter_editor.refresh_current_step_fc_values.assert_not_called()
        level_calibration_view.base_window.parameter_editor.update_parameters_from_fc_values.assert_not_called()

    def test_user_sees_calibration_success_and_a_useful_warning_when_readback_raises(self, level_calibration_view) -> None:
        """
        A readback exception after a successful trim is not a calibration failure.

        GIVEN: The controller accepts level calibration and readback raises an exception without text
        WHEN: The background operation completes
        THEN: Success is retained and the warning includes a non-empty exception representation
        """
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration successful")
        download_parameters = level_calibration_view.base_window.parameter_editor.download_flight_controller_parameters
        download_parameters.side_effect = ConnectionError()

        level_calibration_view.view._on_level_calibration()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

        level_calibration_view.showinfo.assert_called_once_with("Calibration Result", "Level calibration successful")
        level_calibration_view.showwarning.assert_called_once_with("Calibration Readback Failed", "ConnectionError()")
        level_calibration_view.showerror.assert_not_called()

    def test_modal_progress_locks_other_flight_controller_controls_until_background_operation_finishes(
        self, level_calibration_view
    ) -> None:
        """
        A background calibration keeps the shared MAVLink connection exclusive to that operation.

        GIVEN: A level calibration is waiting for the controller
        WHEN: The user starts it
        THEN: A modal progress window blocks other controls until the worker finishes
        """
        started = Event()
        release = Event()
        def blocked_calibration(**_kwargs: object) -> tuple[bool, str]:
            started.set()
            release.wait(timeout=1.0)
            return True, "Level calibration successful"

        level_calibration_view.model.start_level_calibration.side_effect = blocked_calibration
        level_calibration_view.view._on_level_calibration()

        assert started.wait(timeout=0.2)
        level_calibration_view.progress_window.progress_bar.configure.assert_called_once_with(mode="indeterminate")
        level_calibration_view.progress_window.progress_bar.start.assert_called_once_with(10)
        level_calibration_view.progress_window.progress_window.grab_set.assert_called_once_with()

        release.set()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

        level_calibration_view.progress_window.progress_bar.stop.assert_called_once_with()
        level_calibration_view.progress_window.progress_window.grab_release.assert_called_once_with()
        level_calibration_view.progress_window.destroy.assert_called_once_with()

    def test_progress_window_cannot_be_closed_while_calibration_is_running(self, level_calibration_view) -> None:
        """
        Closing the progress window must not release the calibration UI lock.

        GIVEN: Level calibration is running in the background
        WHEN: The progress window is configured
        THEN: Its window-manager close action is ignored
        """
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration successful")

        level_calibration_view.view._on_level_calibration()

        level_calibration_view.progress_window.progress_window.protocol.assert_called_once()
        protocol_name, protocol_handler = level_calibration_view.progress_window.progress_window.protocol.call_args.args
        assert protocol_name == "WM_DELETE_WINDOW"
        protocol_handler()
        level_calibration_view.progress_window.destroy.assert_not_called()

        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

    def test_user_can_request_cancellation_of_level_calibration(self, level_calibration_view) -> None:
        """The modal progress state exposes a cancellation action."""
        release = Event()

        def blocked_calibration(**_kwargs: object) -> tuple[bool, str]:
            release.wait(timeout=1.0)
            return True, "Level calibration successful"

        level_calibration_view.model.start_level_calibration.side_effect = blocked_calibration

        level_calibration_view.view._on_level_calibration()
        level_calibration_view.view._cancel_calibration()

        assert level_calibration_view.view._calibration_cancelled.is_set()
        release.set()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)

    def test_abort_failure_is_not_overwritten_by_generic_cancellation(self, level_calibration_view) -> None:
        """A failed FC abort must remain visible to the user."""
        started = Event()
        release = Event()

        def blocked_calibration(**_kwargs: object) -> tuple[bool, str]:
            started.set()
            release.wait(timeout=1.0)
            return False, "Failed to cancel calibration: link down"

        level_calibration_view.model.start_level_calibration.side_effect = blocked_calibration
        level_calibration_view.view._on_level_calibration()
        assert started.wait(timeout=0.2)

        level_calibration_view.view._cancel_calibration()
        release.set()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

        level_calibration_view.showerror.assert_called_once_with(
            "Calibration Failed", "Failed to cancel calibration: link down"
        )

    def test_destroy_keeps_fc_busy_until_a_running_worker_finishes(self, level_calibration_view, mocker) -> None:
        """Destroying the view must not release the shared link while its worker is alive."""
        started = Event()
        release = Event()

        def blocked_calibration(**_kwargs: object) -> tuple[bool, str]:
            started.set()
            release.wait(timeout=1.0)
            return False, "Cancelled"

        level_calibration_view.model.start_level_calibration.side_effect = blocked_calibration
        level_calibration_view.view._on_level_calibration()
        assert started.wait(timeout=0.2)

        level_calibration_view.view.destroy()

        level_calibration_view.base_window.set_fc_operation_busy.assert_called_once_with(busy=True)
        release.set()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._wait_for_worker_before_releasing_busy()
        level_calibration_view.base_window.set_fc_operation_busy.assert_has_calls(
            [mocker.call(busy=True), mocker.call(busy=False)]
        )

    def test_calibration_marks_the_application_busy_until_completion(self, level_calibration_view, mocker) -> None:
        """
        MacOS must disable other flight-controller controls while calibration owns the link.

        GIVEN: The application is running on macOS
        WHEN: Level calibration starts and completes
        THEN: The shared application busy state is enabled and released
        """
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration successful")

        level_calibration_view.view._on_level_calibration()

        level_calibration_view.base_window.set_fc_operation_busy.assert_called_once_with(busy=True)

        level_calibration_view.view._calibration_thread.join(timeout=1.0)
        level_calibration_view.view._poll_level_calibration()

        level_calibration_view.base_window.set_fc_operation_busy.assert_has_calls(
            [mocker.call(busy=True), mocker.call(busy=False)]
        )

    def test_progress_setup_failure_restores_the_calibration_button(self, level_calibration_view, mocker) -> None:
        """
        A progress-window setup failure must leave the plugin usable.

        GIVEN: Creating the progress window raises an exception
        WHEN: The user starts level calibration
        THEN: The button is restored and no orphaned polling job remains
        """
        mocker.patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.ProgressWindow",
            side_effect=RuntimeError("progress setup failed"),
        )

        level_calibration_view.view._on_level_calibration()

        assert str(level_calibration_view.view._level_btn.cget("state")) == "normal"
        assert level_calibration_view.view._calibration_thread is None
        assert level_calibration_view.view._calibration_poll_job is None
        level_calibration_view.after.assert_not_called()
        level_calibration_view.showerror.assert_called_once_with("Calibration Failed", "progress setup failed")

    def test_progress_grab_failure_restores_the_calibration_button(self, level_calibration_view, mocker) -> None:
        """
        A modal-grab failure must leave the plugin usable.

        GIVEN: The progress window cannot acquire the Tk grab
        WHEN: The user starts level calibration
        THEN: The button and application busy state are restored
        """
        level_calibration_view.progress_window.progress_window.grab_set.side_effect = RuntimeError("grab failed")

        level_calibration_view.view._on_level_calibration()

        assert str(level_calibration_view.view._level_btn.cget("state")) == "normal"
        assert level_calibration_view.view._calibration_thread is None
        assert level_calibration_view.view._calibration_poll_job is None
        level_calibration_view.base_window.set_fc_operation_busy.assert_has_calls(
            [mocker.call(busy=True), mocker.call(busy=False)]
        )
        level_calibration_view.showerror.assert_called_once_with("Calibration Failed", "grab failed")

    def test_destroy_prevents_a_worker_that_finishes_late_from_starting_a_parameter_readback(
        self, level_calibration_view
    ) -> None:
        """
        Leaving the plugin while calibration waits must not leave a new FC read operation behind.

        GIVEN: Level calibration is still waiting for its controller acknowledgement
        WHEN: The plugin is destroyed before that acknowledgement arrives
        THEN: The worker exits after calibration without beginning a parameter readback
        """
        started = Event()
        release = Event()

        def blocked_calibration(**_kwargs: object) -> tuple[bool, str]:
            started.set()
            release.wait(timeout=1.0)
            return True, "Level calibration successful"

        level_calibration_view.model.start_level_calibration.side_effect = blocked_calibration
        level_calibration_view.view._on_level_calibration()
        assert started.wait(timeout=0.2)

        level_calibration_view.view.destroy()
        release.set()
        level_calibration_view.view._calibration_thread.join(timeout=1.0)

        level_calibration_view.base_window.parameter_editor.download_flight_controller_parameters.assert_not_called()
