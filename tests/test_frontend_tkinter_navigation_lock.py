#!/usr/bin/env python3

"""
Behavior-driven tests for calibration navigation prevention.

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from tkinter import TclError, Toplevel, ttk
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration import AccelerometerCalibrationView
from ardupilot_methodic_configurator.plugins.frontend_tkinter_compass_calibration import CompassCalibrationView
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import (
    begin_calibration_navigation_lock,
    end_calibration_navigation_lock,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration import LevelCalibrationView
from ardupilot_methodic_configurator.plugins.frontend_tkinter_rc_calibration import RCCalibrationView

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def navigation_controls(root) -> Generator[SimpleNamespace, None, None]:
    """Provide real controls, including an unavailable action and a readonly selector."""
    frame = ttk.Frame(root)
    button = ttk.Button(frame)
    unavailable = ttk.Button(frame, state="disabled")
    selector = ttk.Combobox(frame, state="readonly")
    navigation_lock = NavigationLock()
    for widget in (button, unavailable, selector):
        navigation_lock.register(widget)
    yield SimpleNamespace(lock=navigation_lock, frame=frame, button=button, unavailable=unavailable, selector=selector)
    frame.destroy()


def test_navigation_is_restored_only_after_every_operation_finishes(navigation_controls) -> None:
    """
    Independent owners cannot prematurely unlock one another's controls.

    GIVEN: Available, unavailable, and readonly navigation controls
    WHEN: Two owners lock them and release their locks independently
    THEN: Controls stay disabled until both finish and their original states survive
    """
    controls = navigation_controls
    first, second = object(), object()
    controls.lock.acquire(first)
    controls.lock.acquire(first)
    controls.lock.acquire(second)
    controls.lock.release(object())
    controls.lock.release(first)
    assert controls.lock.locked
    assert all(widget.instate(("disabled",)) for widget in (controls.button, controls.unavailable, controls.selector))

    controls.lock.release(second)
    controls.lock.release(second)

    assert not controls.lock.locked
    assert not controls.button.instate(("disabled",))
    assert controls.unavailable.instate(("disabled",))
    assert controls.selector.instate(("readonly", "!disabled"))


def test_new_controls_are_locked_and_destroyed_controls_do_not_break_restoration(navigation_controls) -> None:
    """
    Layout changes and teardown are safe during a busy operation.

    GIVEN: Navigation is locked and a previously registered widget is destroyed
    WHEN: Another control is registered before the operation finishes
    THEN: The new control stays locked and restoration tolerates the destroyed control
    """
    controls = navigation_controls
    owner = object()
    controls.lock.acquire(owner)
    controls.button.destroy()
    new_button = ttk.Button(controls.frame)
    controls.lock.register(new_button)
    controls.lock.register(new_button)
    assert new_button.instate(("disabled",))

    controls.lock.release(owner)

    assert not new_button.instate(("disabled",))
    assert not controls.lock.locked


def test_a_calibration_cannot_start_while_another_operation_is_busy(navigation_controls) -> None:
    """
    Reentrant calibration clicks cannot send competing commands.

    GIVEN: A calibration owns the host's navigation lock
    WHEN: Another calibration or the same calibration tries to start again
    THEN: Both attempts are refused and cannot release the original owner's lock
    """
    host = SimpleNamespace(navigation_lock=navigation_controls.lock)
    first, second = object(), object()
    assert begin_calibration_navigation_lock(host, first)
    assert not begin_calibration_navigation_lock(host, second)
    assert not begin_calibration_navigation_lock(host, first)
    end_calibration_navigation_lock(host, second)
    assert navigation_controls.lock.locked
    end_calibration_navigation_lock(host, first)
    assert not navigation_controls.lock.locked


@pytest.mark.parametrize("gui_complexity", ["simple", "normal"])
@pytest.mark.parametrize("connected", [False, True])
def test_every_requested_editor_control_is_locked_and_restored(root, mocker, gui_complexity: str, connected: bool) -> None:
    """
    The complete editor navigation surface is disabled during calibration.

    GIVEN: A simple or normal editor, connected or disconnected
    WHEN: Calibration locks and unlocks the real header and footer controls
    THEN: Every requested button and selector is locked, with initial availability restored
    """
    module = "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor"
    window = ParameterEditorWindow.__new__(ParameterEditorWindow)
    window.root = root
    window.main_frame = ttk.Frame(root)
    window.navigation_lock = NavigationLock()
    window.gui_complexity = gui_complexity
    window.parameter_editor = MagicMock()
    window.parameter_editor.current_file = "14_calibration.param"
    window.parameter_editor.parameter_files.return_value = ["14_calibration.param"]
    window.parameter_editor.is_fc_connected = connected
    window.parameter_editor.is_mavftp_supported = connected
    window.parameter_editor.is_configuration_step_optional.return_value = False
    window.parameter_editor.get_previous_non_optional_file.return_value = None
    mocker.patch(f"{module}.VehicleDirectorySelectionWidgets")
    mocker.patch(f"{module}.ParameterEditorTable")
    mocker.patch(f"{module}.show_tooltip")
    mocker.patch.object(window, "legend_frame")
    mocker.patch.object(window, "put_image_in_label", return_value=ttk.Label(window.main_frame))

    try:
        window._create_conf_widgets("test")
        window._create_parameter_area_widgets()

        def descendants(parent) -> list:
            return [child for widget in parent.winfo_children() for child in [widget, *descendants(widget)]]

        buttons = [widget for widget in descendants(window.main_frame) if isinstance(widget, ttk.Button)]
        expected_commands = {
            window.on_skip_click,
            window.on_previous_click,
            window.on_upload_selected_click,
            window.on_upload_selected_and_stay_click,
            window.on_download_bin_logs_click,
            window.on_compare_and_upload_parameter_file_click,
            window.on_export_parameters_click,
            window.on_fc_banner_click,
            window.on_zip_vehicle_for_forum_help_click,
            window.on_analyse_log_click,
            window.on_edit_vehicle_components_click,
        }
        assert len(buttons) == len(expected_commands)
        assert len({button.cget("command") for button in buttons}) == len(expected_commands)
        widgets = [*buttons, window.file_selection_combobox]
        initial_states = [widget.state() for widget in widgets]
        window.navigation_lock.acquire(window)
        assert all(widget.instate(("disabled",)) for widget in widgets)
        window._update_skip_button_state()
        window._update_previous_button_state()
        assert all(widget.instate(("disabled",)) for widget in widgets)

        window.navigation_lock.release(window)

        assert [widget.state() for widget in widgets] == initial_states
    finally:
        window.main_frame.destroy()


@pytest.mark.parametrize(
    "action",
    [
        "on_skip_click",
        "on_previous_click",
        "on_upload_selected_click",
        "on_upload_selected_and_stay_click",
        "on_download_bin_logs_click",
        "on_compare_and_upload_parameter_file_click",
        "on_export_parameters_click",
        "on_fc_banner_click",
        "on_zip_vehicle_for_forum_help_click",
        "on_analyse_log_click",
        "on_edit_vehicle_components_click",
    ],
)
def test_queued_editor_actions_cannot_bypass_calibration_lock(action: str) -> None:
    """
    Disabling widgets is backed by callback guards.

    GIVEN: A locked editor with no collaborators needed for navigation
    WHEN: A queued action is invoked directly during calibration
    THEN: It returns before accessing the data model, writing files, or opening dialogs
    """
    window = ParameterEditorWindow.__new__(ParameterEditorWindow)
    window.navigation_lock = NavigationLock()
    window.navigation_lock.acquire(window)

    getattr(window, action)()

    assert window.navigation_lock.locked


def test_queued_step_selection_and_external_upload_cannot_bypass_calibration_lock() -> None:
    """
    Reentrant combobox events and upload dialogs cannot change calibration context.

    GIVEN: A calibration owns the editor and a queued selection points elsewhere
    WHEN: Selection, log-report navigation, or an external upload callback runs
    THEN: Selection resets to the current step and uploads are refused
    """
    window = ParameterEditorWindow.__new__(ParameterEditorWindow)
    window.navigation_lock = NavigationLock()
    window.navigation_lock.acquire(window)
    window.parameter_editor = SimpleNamespace(current_file="14_calibration.param")
    window.file_selection_combobox = MagicMock()

    window.on_param_file_combobox_change(None, forced=True)
    window._navigate_to_config_step("15_next.param")
    upload = MagicMock()
    assert not window._upload_params({}, upload)

    window.file_selection_combobox.set.assert_called_once_with("14_calibration.param")
    upload.assert_not_called()


@pytest.fixture
def calibration_view(navigation_controls, mocker) -> SimpleNamespace:
    """Provide display-independent calibration views using the real shared lock."""
    host = SimpleNamespace(
        navigation_lock=navigation_controls.lock,
        parameter_editor=SimpleNamespace(fc_parameters={}),
        download_flight_controller_parameters=MagicMock(return_value=({}, {})),
        repopulate_parameter_table=MagicMock(),
    )
    mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration.showinfo")
    mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration.showerror")
    mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showinfo")
    mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showerror")
    mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_compass_calibration.messagebox.showerror")

    def create(view_type: type) -> object:
        view = object.__new__(view_type)
        view.base_window = host
        view.model = MagicMock()
        view._simple_btn = MagicMock()
        view._full_btn = MagicMock()
        view._level_btn = MagicMock()
        view._start_btn = MagicMock()
        view._finish_btn = MagicMock()
        view._cancel_btn = MagicMock()
        view._status_label = MagicMock()
        view._position_label = MagicMock()
        view._continue_btn = MagicMock()
        view._wizard_frame = MagicMock()
        if view_type is RCCalibrationView:
            view.channel_bars = MagicMock()
            view.stick_preview = MagicMock()
            view.craft_preview = MagicMock()
        view._calibration_in_progress = False
        view._calibration_active = False
        view._poll_job = None
        view.after = MagicMock(return_value="after-id")
        view.after_cancel = MagicMock()
        view.winfo_toplevel = MagicMock()
        return view

    return SimpleNamespace(create=create, host=host, controls=navigation_controls)


@pytest.mark.parametrize("succeeded", [False, True])
def test_simple_calibration_locks_command_and_readback_then_restores_controls(calibration_view, succeeded: bool) -> None:
    """
    Simple calibration remains exclusive through successful or failed-ACK readback.

    GIVEN: A connected controller and available navigation
    WHEN: Simple calibration sends its command and reads back the result
    THEN: Navigation is locked in both callbacks and restored afterwards
    """
    fixture = calibration_view
    view = fixture.create(AccelerometerCalibrationView)

    def command() -> tuple[bool, str]:
        assert fixture.host.navigation_lock.locked
        assert fixture.controls.button.instate(("disabled",))
        return succeeded, "result"

    def download(**_kwargs) -> tuple[dict, dict]:
        assert fixture.host.navigation_lock.locked
        return {}, {}

    view.model.start_simple_calibration.side_effect = command
    fixture.host.download_flight_controller_parameters.side_effect = download
    view._on_simple_calibration()

    assert not fixture.host.navigation_lock.locked
    assert not fixture.controls.button.instate(("disabled",))


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel", "readback_error"])
def test_full_accelerometer_wizard_keeps_navigation_locked_until_finished(calibration_view, outcome: str) -> None:
    """
    The asynchronous wizard owns navigation through readback or cancellation.

    GIVEN: A full accelerometer calibration is started
    WHEN: It completes, fails, is cancelled, or its readback raises an error
    THEN: Navigation stays disabled while running and is reliably restored
    """
    fixture = calibration_view
    view = fixture.create(AccelerometerCalibrationView)
    view.model.start_full_calibration.return_value = True, ""
    view.model.cancel_full_calibration.return_value = True, ""
    view._on_start_full_calibration()
    assert fixture.host.navigation_lock.locked

    def download(**_kwargs) -> tuple[dict, dict]:
        assert fixture.host.navigation_lock.locked
        if outcome == "readback_error":
            message = "readback unavailable"
            raise OSError(message)
        return {}, {}

    fixture.host.download_flight_controller_parameters.side_effect = download
    if outcome == "cancel":
        view._on_cancel_full_calibration()
    elif outcome == "readback_error":
        with pytest.raises(OSError, match="readback unavailable"):
            view._end_full_calibration(success=True)
    else:
        view._end_full_calibration(success=outcome == "success")

    assert not fixture.host.navigation_lock.locked
    assert not fixture.controls.button.instate(("disabled",))


def test_full_accelerometer_wizard_is_hidden_before_readback(calibration_view) -> None:
    """The cancelable wizard is gone while successful readback still owns navigation."""
    fixture = calibration_view
    view = fixture.create(AccelerometerCalibrationView)
    view.model.start_full_calibration.return_value = True, ""
    view._on_start_full_calibration()

    def download(**_kwargs) -> tuple[dict, dict]:
        view._wizard_frame.pack_forget.assert_called_once()
        assert view._simple_btn.configure.call_args_list[-1].kwargs["state"] == "disabled"
        assert view._full_btn.configure.call_args_list[-1].kwargs["state"] == "disabled"
        assert view._cancel_btn.configure.call_args_list[-1].kwargs["state"] == "disabled"
        assert fixture.host.navigation_lock.locked
        return {}, {}

    fixture.host.download_flight_controller_parameters.side_effect = download
    view._end_full_calibration(success=True)

    assert not fixture.host.navigation_lock.locked

    view._start_full_calibration()

    assert view._cancel_btn.configure.call_args_list[-1].kwargs["state"] == "normal"


def test_full_accelerometer_cancel_stops_polling_before_showing_result(calibration_view, mocker) -> None:
    """A nested modal event loop cannot run a queued calibration poll after Cancel."""
    fixture = calibration_view
    view = fixture.create(AccelerometerCalibrationView)
    view._poll_job = "pending-poll"
    view.model.cancel_full_calibration.return_value = True, "cancelled"
    showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration.showinfo")
    showinfo.side_effect = lambda *_args: view.after_cancel.assert_called_once_with("pending-poll")

    view._on_cancel_full_calibration()

    view.after_cancel.assert_called_once_with("pending-poll")
    showinfo.assert_called_once()


@pytest.mark.parametrize(
    ("view_type", "start_method", "backend_start"),
    [
        (AccelerometerCalibrationView, "_on_simple_calibration", "start_simple_calibration"),
        (AccelerometerCalibrationView, "_on_start_full_calibration", "start_full_calibration"),
        (LevelCalibrationView, "_on_level_calibration", "start_level_calibration"),
        (CompassCalibrationView, "_begin_calibration", "start_calibration"),
        (RCCalibrationView, "_on_start_calibration", "start_calibration"),
    ],
)
def test_calibration_start_errors_release_navigation(
    calibration_view, view_type, start_method: str, backend_start: str
) -> None:
    """
    A startup exception never leaves the editor permanently disabled.

    GIVEN: Any supported calibration and a controller whose startup raises an error
    WHEN: The calibration attempts to start
    THEN: The command sees the lock and the error path releases it
    """
    fixture = calibration_view
    view = fixture.create(view_type)

    def fail() -> None:
        assert fixture.host.navigation_lock.locked
        message = "command unavailable"
        raise OSError(message)

    getattr(view.model, backend_start).side_effect = fail
    with pytest.raises(OSError, match="command unavailable"):
        getattr(view, start_method)()
    assert not fixture.host.navigation_lock.locked


@pytest.mark.parametrize("finish_method", ["_on_finish_calibration", "_on_cancel_calibration"])
@pytest.mark.parametrize("succeeded", [False, True])
def test_rc_calibration_keeps_navigation_locked_until_save_or_cancel(
    calibration_view, finish_method: str, succeeded: bool
) -> None:
    """
    RC calibration owns navigation while collecting and saving channel extremes.

    GIVEN: A successfully started RC calibration
    WHEN: The user saves or cancels it
    THEN: Navigation remains locked during the backend operation and is restored
    """
    fixture = calibration_view
    view = fixture.create(RCCalibrationView)
    view.model.start_calibration.return_value = True, ""
    view._on_start_calibration()
    assert fixture.host.navigation_lock.locked

    def finish() -> tuple[bool, str]:
        assert fixture.host.navigation_lock.locked
        return succeeded, "Calibration result"

    def refresh_markers(_channels) -> None:
        assert fixture.host.navigation_lock.locked

    view.channel_bars.update_calibration.side_effect = refresh_markers

    view.model.finish_calibration.side_effect = finish
    view.model.cancel_calibration.side_effect = finish
    getattr(view, finish_method)()
    assert not fixture.host.navigation_lock.locked
    view.channel_bars.update_calibration.assert_called()
    if finish_method == "_on_finish_calibration":
        view._finish_btn.configure.assert_called_with(state="disabled" if succeeded else "normal")


def test_level_calibration_keeps_navigation_locked_through_trim_readback(calibration_view) -> None:
    """
    Level trim uses the same lock as the other asynchronous calibrations.

    GIVEN: A level calibration waiting for a controller acknowledgment
    WHEN: The acknowledgment succeeds and trim values are downloaded
    THEN: Navigation is locked through readback and restored afterwards
    """
    fixture = calibration_view
    view = fixture.create(LevelCalibrationView)
    view.model.start_level_calibration.return_value = True, ""
    view._on_level_calibration()
    assert fixture.host.navigation_lock.locked

    def download(**_kwargs) -> tuple[dict, dict]:
        assert fixture.host.navigation_lock.locked
        return {}, {}

    fixture.host.download_flight_controller_parameters.side_effect = download
    view.model.poll_level_calibration.return_value = True, "done"
    view._poll_level_calibration()

    assert not fixture.host.navigation_lock.locked


def test_compass_popup_releases_navigation_only_when_the_popup_closes(calibration_view, mocker) -> None:
    """
    A non-modal compass popup cannot leave navigation available while calibrating.

    GIVEN: A compass calibration with an active progress popup
    WHEN: A child widget is destroyed and then the popup itself is destroyed
    THEN: Only the popup destruction releases the calibration lock
    """
    fixture = calibration_view
    view = fixture.create(CompassCalibrationView)
    view.model.start_calibration.return_value = True, ""
    popup = mocker.patch(
        "ardupilot_methodic_configurator.plugins.frontend_tkinter_compass_calibration.CompassCalibrationPopup"
    ).return_value
    view._begin_calibration()
    assert fixture.host.navigation_lock.locked
    popup.root.bind.assert_called_once_with("<Destroy>", view._on_calibration_popup_destroyed, add="+")

    view._on_calibration_popup_destroyed(SimpleNamespace(widget=object()))
    assert fixture.host.navigation_lock.locked
    view._on_calibration_popup_destroyed(SimpleNamespace(widget=popup.root))

    assert not fixture.host.navigation_lock.locked


def test_unlock_tolerates_tk_teardown(navigation_controls, mocker) -> None:
    """
    A closing Tk interpreter cannot prevent logical lock release.

    GIVEN: An operation owns navigation and widget access starts failing during teardown
    WHEN: The operation releases its lock
    THEN: Tk errors are tolerated and the host no longer reports busy
    """
    controls = navigation_controls
    owner = object()
    controls.lock.acquire(owner)
    mocker.patch.object(controls.selector, "state", side_effect=TclError("application destroyed"))

    controls.lock.release(owner)

    assert not controls.lock.locked


@pytest.mark.parametrize(
    ("view_type", "start_method", "backend_start"),
    [
        (AccelerometerCalibrationView, "_on_start_full_calibration", "start_full_calibration"),
        (LevelCalibrationView, "_on_level_calibration", "start_level_calibration"),
        (CompassCalibrationView, "_begin_calibration", "start_calibration"),
        (RCCalibrationView, "_on_start_calibration", "start_calibration"),
    ],
)
def test_refused_calibration_start_restores_navigation(
    calibration_view, view_type, start_method: str, backend_start: str
) -> None:
    """
    Expected startup failures do not strand the editor in a busy state.

    GIVEN: A controller refuses to start a calibration
    WHEN: The user starts the requested calibration
    THEN: Navigation returns to its previous state without an active session
    """
    fixture = calibration_view
    view = fixture.create(view_type)
    getattr(view.model, backend_start).return_value = False, "not connected"

    getattr(view, start_method)()

    assert not fixture.host.navigation_lock.locked
    assert not fixture.controls.button.instate(("disabled",))


@pytest.mark.parametrize(
    ("view_type", "callback", "backend_method"),
    [
        (AccelerometerCalibrationView, "_poll_tick", "poll_for_next_position"),
        (AccelerometerCalibrationView, "_on_continue", "confirm_current_position"),
        (LevelCalibrationView, "_poll_level_calibration", "poll_level_calibration"),
        (RCCalibrationView, "_on_finish_calibration", "finish_calibration"),
        (RCCalibrationView, "_on_cancel_calibration", "cancel_calibration"),
    ],
)
def test_calibration_callback_errors_restore_navigation(
    calibration_view, view_type, callback: str, backend_method: str
) -> None:
    """
    Exceptions in asynchronous completion callbacks cannot strand navigation.

    GIVEN: A running calibration with navigation locked
    WHEN: A polling, confirmation, save, or cancel callback raises an error
    THEN: The callback releases its navigation lock while preserving the error
    """
    fixture = calibration_view
    view = fixture.create(view_type)
    view._calibration_in_progress = True
    view._calibration_active = True
    fixture.host.navigation_lock.acquire(view)
    getattr(view.model, backend_method).side_effect = OSError("controller unavailable")

    with pytest.raises(OSError, match="controller unavailable"):
        getattr(view, callback)()

    assert not fixture.host.navigation_lock.locked


@pytest.mark.parametrize(
    "view_type",
    [AccelerometerCalibrationView, LevelCalibrationView, CompassCalibrationView, RCCalibrationView],
)
def test_destroying_a_calibration_view_releases_its_navigation_lock(calibration_view, mocker, view_type) -> None:
    """
    Forced plugin teardown releases ownership even if backend cleanup fails.

    GIVEN: An active calibration owns navigation
    WHEN: Its view is destroyed and cancellation or poll cleanup raises an error
    THEN: Navigation is restored and the widget's parent destroy is still called
    """
    fixture = calibration_view
    view = fixture.create(view_type)
    view._calibration_in_progress = True
    view._calibration_active = True
    view._calibration_popup = None
    view._instructions_popup = None
    fixture.host.navigation_lock.acquire(view)
    parent_destroy = mocker.patch.object(view_type.__bases__[0], "destroy")
    if view_type is AccelerometerCalibrationView:
        mocker.patch.object(view, "_stop_polling", side_effect=OSError("cleanup unavailable"))
    elif view_type is LevelCalibrationView:
        view.model.abort_level_calibration.side_effect = OSError("cleanup unavailable")
    else:
        mocker.patch.object(view, "_stop_polling", create=True)
        view.model.cancel_calibration.side_effect = OSError("cleanup unavailable")

    with pytest.raises(OSError, match="cleanup unavailable"):
        view.destroy()

    assert not fixture.host.navigation_lock.locked
    parent_destroy.assert_called_once()


def test_real_compass_popup_destruction_releases_navigation(calibration_view, root, mocker) -> None:
    """
    Real Tk destruction events end compass lock ownership without an event-loop pump.

    GIVEN: Compass calibration owns a real progress toplevel
    WHEN: A child is destroyed and then its toplevel is destroyed
    THEN: Navigation stays locked for the child and is restored for the toplevel
    """
    fixture = calibration_view
    view = fixture.create(CompassCalibrationView)
    view.model.start_calibration.return_value = True, ""
    popup_root = Toplevel(root)
    popup_root.withdraw()
    child = ttk.Frame(popup_root)
    mocker.patch(
        "ardupilot_methodic_configurator.plugins.frontend_tkinter_compass_calibration.CompassCalibrationPopup",
        return_value=SimpleNamespace(root=popup_root),
    )
    try:
        view._begin_calibration()
        child.destroy()
        assert fixture.host.navigation_lock.locked

        popup_root.destroy()

        assert not fixture.host.navigation_lock.locked
    finally:
        if popup_root.winfo_exists():
            popup_root.destroy()
