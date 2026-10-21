#!/usr/bin/env python3

"""
Behavior-driven tests for the level calibration Tkinter plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable, Generator
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.plugins import frontend_tkinter_level_calibration as frontend
from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration import LevelCalibrationView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_LEVEL_CALIBRATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext

# pytest injects fixtures by matching the test function parameter name.
# pylint: disable=redefined-outer-name,protected-access


def test_failed_level_trim_preserves_unchanged_staged_values_without_a_display(mocker) -> None:
    """A rejected trim cannot overwrite edits when the FC values stay unchanged."""
    view = object.__new__(LevelCalibrationView)
    view._level_btn = MagicMock()
    editor = SimpleNamespace(
        fc_parameters={"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02},
        current_step_parameters={"AHRS_TRIM_X": MagicMock(), "AHRS_TRIM_Y": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
        find_other_steps_with_stale_calibration_values=MagicMock(return_value=[]),
    )
    view.base_window = SimpleNamespace(parameter_editor=editor, repopulate_parameter_table=MagicMock())

    view.base_window.download_flight_controller_parameters = MagicMock()
    showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showerror")

    view._finish_level_calibration(success=False, message="Command failed", command_sent=True)

    editor.update_parameters_from_fc_values.assert_not_called()
    assert showerror.call_args.args[1] == "Command failed"


@pytest.fixture
def level_calibration_view(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Provide a real level-calibration view with its external UI effects isolated."""
    # pylint: disable=duplicate-code
    model = MagicMock(spec=LevelCalibrationDataModel)
    base_window = SimpleNamespace(
        root=tk_root,
        download_flight_controller_parameters=MagicMock(),
        parameter_editor=SimpleNamespace(
            fc_parameters={"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02},
            current_step_parameters={"AHRS_TRIM_X": MagicMock(), "AHRS_TRIM_Y": MagicMock()},
            update_parameters_from_fc_values=MagicMock(),
            find_other_steps_with_stale_calibration_values=MagicMock(return_value=[]),
        ),
        repopulate_parameter_table=MagicMock(),
    )
    # pylint: enable=duplicate-code
    showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showinfo")
    showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showerror")
    parent = ttk.Frame(tk_root)
    view = LevelCalibrationView(parent, model, base_window)
    after = mocker.patch.object(view, "after", return_value="after-id")
    after_cancel = mocker.patch.object(view, "after_cancel")
    try:
        yield SimpleNamespace(
            view=view,
            model=model,
            base_window=base_window,
            showinfo=showinfo,
            showerror=showerror,
            after=after,
            after_cancel=after_cancel,
        )
    finally:
        parent.destroy()


class TestLevelCalibrationView:
    """Test the user feedback displayed by the level calibration view."""

    def test_recovery_cancels_the_real_trim_timer_and_resumes_the_pending_result(
        self,
        level_calibration_view: SimpleNamespace,
        mocker: MockerFixture,
        pause_polling_plugin_for_recovery: Callable[[tk.Misc], Callable[[], None]],
        fire_tk_timer: Callable[[tk.Misc, str], None],
    ) -> None:
        """
        Preserve an active trim while recovery owns reception.

        GIVEN: A level trim with a real pending Tk timer
        WHEN: The editor pauses and resumes it through the recovery entry point
        THEN: Polling stops during the pause and resumes without starting a new calibration
        """
        context = level_calibration_view
        mocker.stop(context.after)
        mocker.stop(context.after_cancel)
        context.model.start_level_calibration.return_value = (True, "")
        context.model.poll_level_calibration.return_value = None
        view = context.view
        view._on_level_calibration()
        assert view._poll_job is not None

        resume = pause_polling_plugin_for_recovery(view)

        assert view._poll_job is None
        context.model.poll_level_calibration.assert_not_called()
        resume()
        timer = view._poll_job
        assert timer is not None
        resume()
        assert view._poll_job == timer
        fire_tk_timer(view, timer)
        context.model.poll_level_calibration.assert_called_once_with()
        context.model.start_level_calibration.assert_called_once_with()
        assert view._poll_job is not None

    def test_recovery_pause_only_reschedules_an_active_calibration(self, level_calibration_view) -> None:
        """GIVEN no running trim, WHEN recovery yields and restores reception, THEN no calibration poll is scheduled."""
        fixture = level_calibration_view
        fixture.view.on_suspend()
        fixture.view.on_resume()
        fixture.after.assert_not_called()

    def test_recovery_resume_restores_a_pending_calibration_poll(self, level_calibration_view) -> None:
        """GIVEN a suspended trim poll, WHEN reception resumes, THEN the trim continues polling."""
        fixture = level_calibration_view
        fixture.view._calibration_in_progress = True
        fixture.view._poll_job = "pending-poll"

        fixture.view.on_suspend()
        fixture.view.on_resume()

        fixture.after_cancel.assert_called_once_with("pending-poll")
        fixture.after.assert_called_once()
        assert fixture.view._poll_job == "after-id"

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
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration started")
        level_calibration_view.model.poll_level_calibration.return_value = (True, "Level calibration successful")

        # Act (When)
        level_calibration_view.view._on_level_calibration()
        level_calibration_view.view._poll_level_calibration()

        # Assert (Then)
        level_calibration_view.showinfo.assert_called_once_with("Calibration Result", "Level calibration successful")
        level_calibration_view.showerror.assert_not_called()
        level_calibration_view.base_window.download_flight_controller_parameters.assert_called_once_with(redownload=True)
        level_calibration_view.base_window.parameter_editor.update_parameters_from_fc_values.assert_called_once_with(
            {"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02}
        )
        level_calibration_view.base_window.repopulate_parameter_table.assert_called_once_with()

    def test_successful_level_trim_warns_when_readback_fails(self, level_calibration_view) -> None:
        """A successful ACK must not hide a failed parameter readback or stage cached trims."""
        fixture = level_calibration_view
        fixture.model.start_level_calibration.return_value = (True, "Level calibration started")
        fixture.model.poll_level_calibration.return_value = (True, "Level calibration successful")
        fixture.base_window.download_flight_controller_parameters.return_value = ({}, {})
        editor = fixture.base_window.parameter_editor

        fixture.view._on_level_calibration()
        fixture.view._poll_level_calibration()

        fixture.showinfo.assert_called_once_with(
            "Calibration Result",
            "Level calibration successful\nCould not download the new calibration values.",
        )
        editor.update_parameters_from_fc_values.assert_not_called()
        editor.find_other_steps_with_stale_calibration_values.assert_not_called()
        fixture.base_window.repopulate_parameter_table.assert_called_once_with()

    def test_level_trim_waits_for_ack_using_after_polls(self, level_calibration_view) -> None:
        """The button handler returns promptly and schedules a non-blocking ACK poll."""
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration started")
        level_calibration_view.model.poll_level_calibration.return_value = None

        level_calibration_view.view._on_level_calibration()

        level_calibration_view.model.start_level_calibration.assert_called_once_with()
        level_calibration_view.model.poll_level_calibration.assert_not_called()
        level_calibration_view.after.assert_called_once_with(100, level_calibration_view.view._poll_level_calibration)
        assert level_calibration_view.view._level_btn.instate(["disabled"])

        level_calibration_view.view._poll_level_calibration()

        level_calibration_view.model.poll_level_calibration.assert_called_once_with()
        level_calibration_view.after.assert_called_with(100, level_calibration_view.view._poll_level_calibration)
        level_calibration_view.showinfo.assert_not_called()

    def test_user_is_told_which_stale_step_needs_review_after_level_trim(self, level_calibration_view) -> None:
        """GIVEN stale trims in another step, WHEN calibration succeeds, THEN identify the step to review."""
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration started")
        level_calibration_view.model.poll_level_calibration.return_value = (True, "Level calibration successful")
        editor = level_calibration_view.base_window.parameter_editor
        editor.find_other_steps_with_stale_calibration_values.return_value = ["16_accelerometer_calibration.param"]

        level_calibration_view.view._on_level_calibration()
        level_calibration_view.view._poll_level_calibration()

        editor.find_other_steps_with_stale_calibration_values.assert_called_once_with(
            {"AHRS_TRIM_X": 0.01, "AHRS_TRIM_Y": 0.02}
        )
        level_calibration_view.showinfo.assert_called_once_with(
            "Calibration Result",
            "Level calibration successful\nReview stale AHRS trim values in: 16_accelerometer_calibration.param",
        )

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

        # Assert (Then)
        level_calibration_view.showerror.assert_called_once_with("Calibration Failed", "Vehicle is moving")
        level_calibration_view.showinfo.assert_not_called()

    def test_user_cannot_start_a_second_level_trim_while_the_first_is_running(self, level_calibration_view) -> None:
        """Re-entrant clicks cannot start another trim while the async poll is active."""
        view = level_calibration_view.view

        def run_calibration() -> tuple[bool, str]:
            assert view._level_btn.instate(["disabled"])
            view._on_level_calibration()
            return True, "Level calibration started"

        level_calibration_view.model.start_level_calibration.side_effect = run_calibration
        level_calibration_view.model.poll_level_calibration.return_value = (True, "Level calibration successful")

        view._on_level_calibration()
        view._poll_level_calibration()

        level_calibration_view.model.start_level_calibration.assert_called_once_with()
        assert view._level_btn.instate(["!disabled"])
        level_calibration_view.showinfo.assert_called_once_with("Calibration Result", "Level calibration successful")

    def test_destroyed_level_button_is_not_reconfigured_after_calibration(self, level_calibration_view) -> None:
        """A late calibration completion tolerates its button having been destroyed."""
        level_calibration_view.view._level_btn.destroy()

        level_calibration_view.view._finish_level_calibration(success=False, message="Flight controller timed out")

        level_calibration_view.showerror.assert_called_once_with("Calibration Failed", "Flight controller timed out")

    def test_destroy_aborts_an_active_calibration(self, level_calibration_view) -> None:
        """Switching steps must release the backend session and cancel its poll."""
        view = level_calibration_view.view
        level_calibration_view.model.start_level_calibration.return_value = (True, "started")
        view._on_level_calibration()

        view.destroy()

        level_calibration_view.after_cancel.assert_called_once_with("after-id")
        level_calibration_view.model.abort_level_calibration.assert_called_once_with()

    def test_destroy_removes_view_when_abort_raises(self, level_calibration_view) -> None:
        """A dead transport during backend cleanup must not leave the Tk frame alive."""
        view = level_calibration_view.view
        level_calibration_view.model.start_level_calibration.return_value = (True, "started")
        level_calibration_view.model.abort_level_calibration.side_effect = OSError("serial link disappeared")
        view._on_level_calibration()

        with pytest.raises(OSError, match="serial link disappeared"):
            view.destroy()

        assert not view.winfo_exists()

    def test_failed_ack_reads_back_changed_trim_and_warns(self, level_calibration_view) -> None:
        """A lost ACK can follow a saved trim, which must be copied and reported."""
        fixture = level_calibration_view
        fixture.model.start_level_calibration.return_value = (True, "started")
        fixture.model.poll_level_calibration.return_value = (False, "Acknowledgment timed out")
        editor = fixture.base_window.parameter_editor

        def download(*, redownload: bool, response_timeout: float) -> None:
            assert redownload
            assert response_timeout == 2.0
            editor.fc_parameters["AHRS_TRIM_X"] = 0.04

        fixture.base_window.download_flight_controller_parameters.side_effect = download
        fixture.view._on_level_calibration()
        fixture.view._poll_level_calibration()

        editor.update_parameters_from_fc_values.assert_called_once_with({"AHRS_TRIM_X": 0.04})
        assert "AHRS_TRIM_X" in fixture.showerror.call_args.args[1]


def test_level_calibration_cannot_interrupt_another_vehicle_operation(level_calibration_view: SimpleNamespace) -> None:
    """
    Preserve the shared navigation lock during a competing operation.

    GIVEN: Another vehicle operation owns the navigation lock
    WHEN: The user requests level calibration
    THEN: Calibration does not start and the existing lock remains owned
    """
    # Given: A real lock owned by a different operation.
    context = level_calibration_view
    lock = NavigationLock()
    owner = object()
    lock.acquire(owner)
    context.base_window.navigation_lock = lock
    # When: Try to start level calibration.
    context.view._on_level_calibration()
    # Then: No backend command or control-state transition occurs.
    context.model.start_level_calibration.assert_not_called()
    assert lock.locked
    assert not context.view._calibration_in_progress
    assert context.view._level_btn.instate(["!disabled"])
    lock.release(owner)


def test_level_calibration_releases_navigation_when_polling_raises(level_calibration_view: SimpleNamespace) -> None:
    """
    Recover navigation after a telemetry failure while polling.

    GIVEN: An active asynchronous calibration
    WHEN: Controller polling raises a transport error
    THEN: The error propagates and navigation and calibration controls are restored
    """
    # Given: A real lock and a failing controller-I/O boundary.
    context = level_calibration_view
    context.base_window.navigation_lock = NavigationLock()
    context.model.start_level_calibration.return_value = (True, "Started")
    context.model.poll_level_calibration.side_effect = OSError("Connection lost")
    context.view._on_level_calibration()
    # When / Then: Restore UI state even when the backend raises.
    with pytest.raises(OSError, match="Connection lost"):
        context.view._poll_level_calibration()
    assert not context.base_window.navigation_lock.locked
    assert not context.view._calibration_in_progress
    assert context.view._level_btn.instate(["!disabled"])
    context.model.poll_level_calibration.reset_mock()
    context.view._poll_level_calibration()
    context.model.poll_level_calibration.assert_not_called()


def test_failed_level_ack_explains_unconfirmed_trim_and_stale_steps(level_calibration_view: SimpleNamespace) -> None:
    """
    Explain ambiguous calibration results after a failed acknowledgment.

    GIVEN: A failed ACK with a changed cached trim and failed readback
    WHEN: Calibration results are presented
    THEN: The user sees both stale-step guidance and the unconfirmed-save warning
    """
    # Given: One trim changed, but controller readback cannot confirm the result.
    context = level_calibration_view
    editor = context.base_window.parameter_editor

    def download(**_kwargs: object) -> tuple[dict[str, float], dict[str, float]]:
        editor.fc_parameters["AHRS_TRIM_X"] = 0.04
        return {}, {}

    context.base_window.download_flight_controller_parameters.side_effect = download
    editor.find_other_steps_with_stale_calibration_values.return_value = ["14_hardware.param"]
    # When: Present a failed command that was actually sent.
    context.view._finish_level_calibration(success=False, message="ACK timed out", command_sent=True)
    # Then: No ambiguous result is presented as confirmed success.
    message = context.showerror.call_args.args[1]
    assert "AHRS_TRIM_X" in message
    assert "Review stale AHRS trim values in: 14_hardware.param" in message
    assert "Could not confirm whether the trim values were saved." in message
    context.showinfo.assert_not_called()


def test_registered_level_plugin_builds_the_trim_controls(
    level_calibration_view: SimpleNamespace, mocker: MockerFixture
) -> None:
    """
    Create the level-trim workflow from registered application dependencies.

    GIVEN: A controller and isolated plugin registry
    WHEN: The application creates the registered model and view
    THEN: The level-trim control is available with the correct controller dependency
    """
    # Given: Isolate registration from the application-wide registry.
    factory = PluginFactory()
    mocker.patch.object(frontend, "plugin_factory", factory)
    controller = MagicMock()
    context = PluginModelContext(controller, MagicMock(), MagicMock())
    # When: Instantiate through both registered factories.
    frontend.register_level_calibration_plugin()
    model = factory.create_model(PLUGIN_LEVEL_CALIBRATION, context)
    view = factory.create(
        PLUGIN_LEVEL_CALIBRATION, level_calibration_view.view.master, model, level_calibration_view.base_window
    )
    # Then: The real view offers level calibration.
    assert isinstance(view, LevelCalibrationView)
    assert isinstance(model, LevelCalibrationDataModel)
    try:
        assert model.flight_controller is controller
        assert view._level_btn.instate(["!disabled"])
    finally:
        view.destroy()
