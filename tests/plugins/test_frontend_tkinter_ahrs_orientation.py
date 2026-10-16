#!/usr/bin/env python3

"""
Behavior-driven tests for the AHRS orientation Tkinter frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterValueUpdateStatus,
)
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugins import frontend_tkinter_ahrs_orientation as frontend
from ardupilot_methodic_configurator.plugins.data_model_ahrs_orientation import (
    AhrsOrientationDataModel,
    AhrsOrientationEstimate,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation import AhrsOrientationView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_AHRS_ORIENTATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from pytest_mock import MockerFixture

    from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def diagnostics_orientation_view(tk_root) -> Generator[SimpleNamespace, None, None]:
    """Create a real wizard/model and timer, mocking only controller I/O and its host."""
    controller = MagicMock(fc_parameters={"AHRS_ORIENTATION": 0.0})
    model = AhrsOrientationDataModel(controller)
    parent = ttk.Frame(tk_root)
    host = SimpleNamespace(root=MagicMock(), navigation_lock=NavigationLock(), parameter_editor=MagicMock())
    host._connection_recovery = None
    host.root.winfo_exists.return_value = True
    view = AhrsOrientationView(parent, model, cast("BaseWindow", host))
    host.current_plugin_view = view
    try:
        yield SimpleNamespace(view=view, model=model, host=host)
    finally:
        view.destroy()
        parent.destroy()


def test_recovery_cancels_real_imu_polling_without_discarding_captured_poses(
    diagnostics_orientation_view: SimpleNamespace,
    pause_polling_plugin_for_recovery: Callable[[tk.Misc], Callable[[], None]],
    fire_tk_timer: Callable[[tk.Misc, str], None],
) -> None:
    """
    Preserve orientation progress while yielding actual polling to recovery.

    GIVEN: An orientation wizard with one captured pose and a pending IMU timer
    WHEN: The editor pauses and resumes its receiver for connection recovery
    THEN: All timers stop during the pause and one loop resumes with the pose intact
    """
    context = diagnostics_orientation_view
    view = context.view
    view.on_activate()
    view._handle_live_imu_sample((0.0, 0.0, -1000.0))
    view._on_continue()
    samples = dict(context.model._samples)
    assert view._imu_poll_job is not None

    resume = pause_polling_plugin_for_recovery(view)

    assert view._imu_poll_job is None
    assert view._latest_imu is None
    assert context.model._samples == samples
    resume()
    timer = view._imu_poll_job
    assert timer is not None
    resume()
    assert view._imu_poll_job == timer
    fire_tk_timer(view, timer)
    assert view._imu_poll_job is not None
    assert context.model._samples == samples


@pytest.mark.parametrize("popup_fails", [False, True])
def test_diagnostics_preserves_captured_orientation_poses_and_requires_fresh_imu(
    diagnostics_orientation_view: SimpleNamespace, popup_fails: bool
) -> None:
    """
    Pausing for diagnostics preserves a partially completed orientation workflow.

    GIVEN an orientation wizard with two captured poses,
    WHEN diagnostics closes normally or fails to open,
    THEN samples and progress remain intact and capture waits for fresh IMU telemetry.
    """
    view = diagnostics_orientation_view.view
    model = diagnostics_orientation_view.model
    view.on_activate()
    for sample in ((0.0, 0.0, -1000.0), (1000.0, 0.0, 0.0)):
        view._handle_live_imu_sample(sample)
        view._on_continue()
    assert view._step_index == 2
    initial_timer = view._imu_poll_job
    samples = dict(model._samples)
    instruction = view._wizard_instruction_var.get()

    def while_popup_open(*_args: object, **_kwargs: object) -> MagicMock:
        assert view._imu_poll_job is None
        assert initial_timer not in view.tk.call("after", "info")
        if popup_fails:
            error = "popup unavailable"
            raise RuntimeError(error)
        return MagicMock()

    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FlightControllerBannerWindow",
        side_effect=while_popup_open,
    ):
        if popup_fails:
            with pytest.raises(RuntimeError, match="popup unavailable"):
                ParameterEditorWindow.on_fc_banner_click(diagnostics_orientation_view.host)
        else:
            ParameterEditorWindow.on_fc_banner_click(diagnostics_orientation_view.host)

    assert view._wizard_active
    assert view._step_index == 2
    assert model._samples == samples
    assert view._wizard_instruction_var.get() == instruction
    assert view._latest_imu is None
    assert str(view._continue_btn.cget("state")) == "disabled"
    assert view._imu_poll_job is not None
    resumed_timer = view._imu_poll_job
    view.on_resume()
    assert view._imu_poll_job == resumed_timer
    view._handle_live_imu_sample((0.0, 1000.0, 0.0))
    assert str(view._continue_btn.cget("state")) == "normal"
    assert model.record_sample("RIGHT", view._latest_imu)[0]
    assert model.has_all_required_samples()


def test_closing_diagnostics_does_not_repeat_orientation_prerequisite_errors(
    diagnostics_orientation_view: SimpleNamespace,
) -> None:
    """
    A diagnostics round-trip is not another attempt to start orientation detection.

    GIVEN an orientation wizard blocked by unsupported prerequisites,
    WHEN diagnostics opens and closes,
    THEN it resumes polling without restarting detection or showing the same error again.
    """
    context = diagnostics_orientation_view
    context.model.flight_controller.fc_parameters = {"AHRS_ORIENTATION": 101.0}
    with (
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation.showerror") as show_error,
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FlightControllerBannerWindow"),
    ):
        context.view.on_activate()
        show_error.assert_called_once()
        show_error.reset_mock()
        ParameterEditorWindow.on_fc_banner_click(context.host)
        show_error.assert_not_called()
    assert not context.view._wizard_active
    assert context.view._imu_poll_job is not None


@pytest.fixture
def view_with_model(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Create a view with mocked collaborators and no active after() loop."""
    model = MagicMock(spec=AhrsOrientationDataModel)
    model.get_required_steps.return_value = ("LEVEL", "NOSE DOWN", "RIGHT")
    model.validate_detection_prerequisites.return_value = (True, "")

    parameter_editor = MagicMock()
    parameter_editor.current_step_parameters = {}
    parameter_editor.add_parameter_to_current_file.return_value = True
    parameter_editor.update_parameter_value.return_value = SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED)

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


@pytest.fixture
def orientation_dialogs(mocker: MockerFixture) -> SimpleNamespace:
    """Mock modal user interaction while retaining real wizard widgets."""
    return SimpleNamespace(
        error=mocker.patch.object(frontend, "showerror"),
        info=mocker.patch.object(frontend, "showinfo"),
        choose_custom=mocker.patch.object(frontend, "askyesno", return_value=True),
    )


@pytest.fixture
def final_orientation_capture(view_with_model: SimpleNamespace) -> SimpleNamespace:
    """Provide the final capture with a realistic low-confidence orientation estimate."""
    estimate = AhrsOrientationEstimate(
        best_code=0,
        best_name="None",
        match_score_percent=88.0,
        is_preset_match=False,
        custom_roll_deg=12.3,
        custom_pitch_deg=-4.5,
        custom_yaw_deg=67.8,
    )
    context = view_with_model
    context.view._wizard_active = True
    context.view._step_index = 2
    context.view._latest_imu = (0.0, 1000.0, 0.0)
    context.model.record_sample.return_value = (True, "Captured RIGHT sample")
    context.model.estimate_orientation.return_value = (True, estimate, "Estimation complete")
    return context


def test_disconnected_user_cannot_start_orientation_detection(
    view_with_model: SimpleNamespace, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Explain why detection cannot start while disconnected.

    GIVEN: The flight controller is disconnected
    WHEN: The user presses Continue
    THEN: Detection remains inactive and a connection error is shown
    """
    # Given: No active controller connection.
    view_with_model.model.is_connected.return_value = False

    # When: Attempt to begin capturing poses.
    view_with_model.view._continue_btn.configure(state="normal")
    view_with_model.view._continue_btn.invoke()

    # Then: No capture sequence is started.
    assert not view_with_model.view._wizard_active
    view_with_model.model.reset_sequence.assert_not_called()
    orientation_dialogs.error.assert_called_once_with("Not Connected", "Flight controller not connected")


def test_user_can_retry_a_failed_pose_capture(
    final_orientation_capture: SimpleNamespace, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Preserve progress when a pose cannot be captured.

    GIVEN: The last pose has no valid IMU sample
    WHEN: The user attempts capture
    THEN: The failure is explained and the same pose remains available for retry
    """
    # Given: Capture rejects the current IMU reading.
    context = final_orientation_capture
    context.model.record_sample.return_value = (False, "No fresh IMU sample")

    # When: Capture the last pose.
    context.view._on_continue()

    # Then: Failed capture does not finish or advance the wizard.
    assert context.view._wizard_active
    assert context.view._step_index == 2
    context.model.estimate_orientation.assert_not_called()
    orientation_dialogs.error.assert_called_once_with("Capture Failed", "No fresh IMU sample")


@pytest.mark.parametrize("successful_estimation", [True, False])
def test_user_sees_why_orientation_estimation_has_no_result(
    final_orientation_capture: SimpleNamespace, orientation_dialogs: SimpleNamespace, successful_estimation: bool
) -> None:
    """
    Report estimation failures without staging parameters.

    GIVEN: Captured poses yield no orientation estimate
    WHEN: The user finishes detection
    THEN: The reason remains visible and no parameter changes are staged
    """
    # Given: Estimation provides no usable result.
    context = final_orientation_capture
    context.model.estimate_orientation.return_value = (successful_estimation, None, "Poses are inconsistent")

    # When: Finish capture.
    context.view._on_continue()

    # Then: Failure feedback persists and the user may start again.
    assert not context.view._wizard_active
    assert context.view._recommendation_var.get() == "Poses are inconsistent"
    assert str(context.view._continue_btn.cget("state")) == "normal"
    context.parameter_editor.update_parameter_value.assert_not_called()
    orientation_dialogs.error.assert_called_once_with("Estimation Failed", "Poses are inconsistent")


def test_user_sees_when_a_preset_orientation_cannot_be_staged(
    final_orientation_capture: SimpleNamespace, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Explain a rejected preset parameter update.

    GIVEN: A confident preset estimate and an unavailable parameter editor
    WHEN: The user finishes detection
    THEN: No success is claimed and a parameter update error is displayed
    """
    # Given: A valid preset estimate but no parameter editor in the host.
    context = final_orientation_capture
    context.model.estimate_orientation.return_value = (
        True,
        AhrsOrientationEstimate(
            best_code=2,
            best_name="Yaw90",
            match_score_percent=97.5,
            is_preset_match=True,
            custom_roll_deg=0.0,
            custom_pitch_deg=0.0,
            custom_yaw_deg=90.0,
        ),
        "Estimated",
    )
    context.view.base_window.parameter_editor = None

    # When: Finish detection.
    context.view._on_continue()

    # Then: Failure appears both in the wizard and in the dialog.
    message = "Could not write AHRS_ORIENTATION into the parameter table."
    assert context.view._recommendation_var.get() == message
    orientation_dialogs.error.assert_called_once_with("Parameter Update Failed", message)
    orientation_dialogs.info.assert_not_called()


def test_user_can_accept_custom_orientation_after_a_low_confidence_estimate(
    final_orientation_capture: SimpleNamespace, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Offer and stage Custom 1 when a preset match is uncertain.

    GIVEN: A low-confidence estimate with custom Euler angles
    WHEN: The user accepts the custom orientation option
    THEN: Custom angles and the enable flag are staged and upload instructions are shown
    """
    # Given: Existing parameters can be updated without adding them again.
    context = final_orientation_capture
    context.parameter_editor.current_step_parameters = {
        name: object()
        for name in ("CUST_ROT_ENABLE", "AHRS_ORIENTATION", "CUST_ROT1_ROLL", "CUST_ROT1_PITCH", "CUST_ROT1_YAW")
    }

    # When: Finish capture and accept the custom option.
    context.view._on_continue()

    # Then: The recommendation reports the staged orientation accurately.
    orientation_dialogs.choose_custom.assert_called_once()
    assert "88.0%" in orientation_dialogs.choose_custom.call_args.args[1]
    assert context.view._recommendation_var.get() == (
        "Set CUST_ROT_ENABLE=1, Applied CUST_ROT1_ROLL=12.3, CUST_ROT1_PITCH=-4.5, "
        "CUST_ROT1_YAW=67.8 and set AHRS_ORIENTATION=101 (Custom 1). Upload the changes to use Custom 1 rotation."
    )
    context.parameter_editor.add_parameter_to_current_file.assert_not_called()
    context.parameter_editor.update_parameter_value.assert_any_call("AHRS_ORIENTATION", "101", include_range_check=False)
    context.parameter_editor_table.repopulate_table.assert_called_once()
    orientation_dialogs.info.assert_called_once_with("Custom Orientation Applied", context.view._recommendation_var.get())
    orientation_dialogs.error.assert_not_called()


@pytest.mark.parametrize("failure", ["missing_editor", "missing_parameter", "rejected_update"])
def test_user_sees_failure_when_custom_orientation_cannot_be_staged(
    final_orientation_capture: SimpleNamespace, orientation_dialogs: SimpleNamespace, failure: str
) -> None:
    """
    Report custom-orientation parameter failures.

    GIVEN: Required parameters cannot be accessed, added, or updated
    WHEN: The user accepts the custom orientation recommendation
    THEN: A failure is shown and no successful table refresh is performed
    """
    # Given: An unavailable dependency or a rejected parameter operation.
    context = final_orientation_capture
    if failure == "missing_editor":
        context.view.base_window.parameter_editor = None
    elif failure == "missing_parameter":
        context.parameter_editor.add_parameter_to_current_file.return_value = False
    else:
        context.parameter_editor.update_parameter_value.return_value = SimpleNamespace(status=ParameterValueUpdateStatus.ERROR)

    # When: Finish and accept custom orientation.
    context.view._on_continue()

    # Then: The staged-operation failure is visible and no success is reported.
    message = "Could not apply Custom 1 orientation parameters in the parameter table."
    assert context.view._recommendation_var.get() == message
    orientation_dialogs.error.assert_called_once_with("Parameter Update Failed", message)
    orientation_dialogs.info.assert_not_called()
    context.parameter_editor_table.repopulate_table.assert_not_called()


def test_user_can_decline_custom_orientation_and_capture_poses_again(
    final_orientation_capture: SimpleNamespace, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Restart detection when the user declines an uncertain result.

    GIVEN: An uncertain preset recommendation
    WHEN: The user declines Custom 1
    THEN: Detection starts at LEVEL again without staging parameter changes
    """
    # Given: The user prefers to repeat detection.
    context = final_orientation_capture
    orientation_dialogs.choose_custom.return_value = False

    # When: Complete detection and decline the custom option.
    context.view._on_continue()

    # Then: A fresh capture sequence is ready.
    assert context.view._wizard_active
    assert context.view._step_index == 0
    assert context.view._wizard_progress_var.get() == "Step 1/3: LEVEL"
    assert context.view._recommendation_var.get() == ""
    context.model.reset_sequence.assert_called_once_with()
    context.parameter_editor.update_parameter_value.assert_not_called()


def test_user_can_cancel_detection_and_start_a_fresh_sequence(
    diagnostics_orientation_view: SimpleNamespace, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Discard captured poses on explicit cancellation.

    GIVEN: An active detector with a captured LEVEL pose
    WHEN: The user presses Cancel and later reactivates the plugin
    THEN: Old poses are cleared and a fresh LEVEL sequence starts
    """
    # Given: Capture one pose using the real orientation model.
    context = diagnostics_orientation_view
    context.view.on_activate()
    context.view._handle_live_imu_sample((0.0, 0.0, -1000.0))
    context.view._continue_btn.invoke()
    assert context.view._step_index == 1

    # When: Cancel through the real button.
    context.view._cancel_btn.invoke()

    # Then: Captures and progress are reset.
    assert not context.view._wizard_active
    assert context.view._step_index == 0
    assert context.model._samples == {}
    assert context.view._wizard_progress_var.get() == ""
    assert context.view._wizard_instruction_var.get() == "Press Continue to start the auto-detection wizard."
    context.view.on_activate()
    assert context.view._wizard_progress_var.get() == "Step 1/3: LEVEL"
    orientation_dialogs.error.assert_not_called()


def test_hidden_orientation_plugin_stops_telemetry_and_disables_capture(diagnostics_orientation_view: SimpleNamespace) -> None:
    """
    Stop collecting telemetry when the plugin is hidden.

    GIVEN: An active plugin with an IMU polling timer
    WHEN: The user leaves the configuration step
    THEN: Its timer is removed and Continue cannot capture another pose
    """
    # Given: Detection is active with a scheduled real Tk timer.
    view = diagnostics_orientation_view.view
    view.on_activate()
    timer = view._imu_poll_job

    # When: Hide the plugin.
    view.on_deactivate()

    # Then: No timer or enabled capture action is left behind.
    assert view._imu_poll_job is None
    assert timer not in view.tk.call("after", "info")
    assert not view._wizard_active
    assert str(view._continue_btn.cget("state")) == "disabled"


def test_user_can_stage_a_detected_preset_from_three_real_pose_samples(
    diagnostics_orientation_view: SimpleNamespace, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Complete orientation estimation with the real pose-processing model.

    GIVEN: A controller mounted in the default orientation
    WHEN: The user captures LEVEL, NOSE DOWN and RIGHT poses
    THEN: AHRS_ORIENTATION=0 is staged and the user is instructed to upload it
    """
    # Given: Only controller I/O, table presentation and dialogs are mocked.
    context = diagnostics_orientation_view
    context.host.parameter_editor.update_parameter_value.return_value = SimpleNamespace(
        status=ParameterValueUpdateStatus.UPDATED
    )
    view = context.view
    view.on_activate()

    # When: Capture the three physical poses with real model validation and estimation.
    samples = ((0.0, 0.0, -1000.0), (-1000.0, 0.0, 0.0), (0.0, -1000.0, 0.0))
    for index, sample in enumerate(samples):
        view._handle_live_imu_sample(sample)
        view._continue_btn.invoke()
        if index == 0:
            # Re-showing an active plugin preserves the existing capture and timer.
            timer = view._imu_poll_job
            view.on_activate()
            assert view._imu_poll_job == timer
            assert view._wizard_progress_var.get() == "Step 2/3: NOSE DOWN"

    # Then: The real estimator's default-orientation result is staged successfully.
    assert not view._wizard_active
    assert context.model.has_all_required_samples()
    context.host.parameter_editor.update_parameter_value.assert_called_once_with(
        "AHRS_ORIENTATION", "0", include_range_check=False
    )
    assert "AHRS_ORIENTATION was set to 0" in view._recommendation_var.get()
    assert "Press upload to apply the changes." in view._recommendation_var.get()
    orientation_dialogs.info.assert_called_once_with("AHRS Orientation Estimate", view._recommendation_var.get())
    orientation_dialogs.error.assert_not_called()


def test_missing_live_imu_disables_capture_until_a_fresh_sample_arrives(diagnostics_orientation_view: SimpleNamespace) -> None:
    """
    Prevent capture from stale telemetry.

    GIVEN: An active orientation detector
    WHEN: No live sample is available and then a fresh one arrives
    THEN: Continue is disabled until the fresh sample arrives
    """
    # Given: Active detection.
    view = diagnostics_orientation_view.view
    view.on_activate()

    # When: Telemetry becomes unavailable.
    view._handle_no_live_imu_sample()

    # Then: Capture is gated on a fresh sample.
    assert str(view._continue_btn.cget("state")) == "disabled"
    view._handle_live_imu_sample((0.0, 0.0, -1000.0))
    assert str(view._continue_btn.cget("state")) == "normal"


def test_registered_orientation_plugin_creates_a_real_detector(
    tk_root: tk.Tk, mocker: MockerFixture, orientation_dialogs: SimpleNamespace
) -> None:
    """
    Construct an orientation assistant through the application registry.

    GIVEN: Registered orientation factories and a connected flight controller
    WHEN: The application creates and activates the plugin
    THEN: Its real data model starts a LEVEL capture sequence
    """
    # Given: An isolated registry and external controller I/O.
    factory = PluginFactory()
    mocker.patch.object(frontend, "plugin_factory", factory)
    context = PluginModelContext(MagicMock(fc_parameters={"AHRS_ORIENTATION": 0.0}), MagicMock(), MagicMock())
    parent = ttk.Frame(tk_root)

    # When: Create through registered factories.
    frontend.register_ahrs_orientation_plugin()
    model = factory.create_model(PLUGIN_AHRS_ORIENTATION, context)
    view = factory.create(PLUGIN_AHRS_ORIENTATION, parent, model, MagicMock())

    # Then: A real detector is ready for pose capture.
    assert isinstance(view, AhrsOrientationView)
    assert isinstance(model, AhrsOrientationDataModel)
    try:
        view.on_activate()
        assert view._wizard_progress_var.get() == "Step 1/3: LEVEL"
        assert view._imu_poll_job is not None
        orientation_dialogs.error.assert_not_called()
    finally:
        view.destroy()
        parent.destroy()


class TestAhrsOrientationViewUiSurface:
    """Static UI assertions for the simplified orientation helper."""

    def test_user_can_scroll_the_assistant_in_a_short_plugin_pane(self, tk_root: tk.Tk, mocker) -> None:
        """
        The orientation assistant remains reachable when the plugin pane is short.

        GIVEN: The assistant is taller than the available pane
        WHEN: The user scrolls to the bottom
        THEN: The lower controls come into view
        """
        model = MagicMock(spec=AhrsOrientationDataModel)
        model.get_required_steps.return_value = ("LEVEL", "NOSE DOWN", "RIGHT")
        mocker.patch.object(AhrsOrientationView, "_start_imu_polling")
        window = tk.Toplevel(tk_root)
        window.geometry("600x120+0+0")
        try:
            view = AhrsOrientationView(window, model, MagicMock())
            view.pack(fill="both", expand=True)
            tk_root.update()

            canvas = view._scroll_frame.canvas
            assert view._scroll_frame.view_port.winfo_reqheight() > canvas.winfo_height()
            canvas.yview_moveto(1)
            tk_root.update()

            assert canvas.yview()[0] > 0
            assert canvas.winfo_rooty() <= view._continue_btn.winfo_rooty()
            assert view._continue_btn.winfo_rooty() + view._continue_btn.winfo_height() <= (
                canvas.winfo_rooty() + canvas.winfo_height()
            )
        finally:
            window.destroy()

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
        assert view_with_model.parameter_editor.add_parameter_to_current_file.call_args_list == [
            (("CUST_ROT_ENABLE",),),
            (("AHRS_ORIENTATION",),),
            (("CUST_ROT1_ROLL",),),
            (("CUST_ROT1_PITCH",),),
            (("CUST_ROT1_YAW",),),
        ]
        assert view_with_model.parameter_editor.update_parameter_value.call_args_list == [
            (("CUST_ROT_ENABLE", "1"), {"include_range_check": False}),
            (("CUST_ROT1_ROLL", "12.3"), {"include_range_check": False}),
            (("CUST_ROT1_PITCH", "-4.5"), {"include_range_check": False}),
            (("CUST_ROT1_YAW", "67.8"), {"include_range_check": False}),
            (("AHRS_ORIENTATION", "101"), {"include_range_check": False}),
        ]
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
