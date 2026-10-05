#!/usr/bin/env python3

"""
Standalone startup behavior for the firmware upload window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable, Generator
from pathlib import Path
from queue import SimpleQueue
from threading import Event
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import frontend_tkinter_firmware_upload as firmware_upload
from ardupilot_methodic_configurator.backend_firmware_upload import FirmwareBoardInfo, FirmwareUploadCallbacks
from ardupilot_methodic_configurator.data_model_firmware_catalog import FirmwareRelease
from ardupilot_methodic_configurator.data_model_firmware_upload import (
    BootloaderInfo,
    FirmwareBootloaderRecoveryError,
    FirmwareCompatibilityError,
    FirmwareImage,
    FirmwareImageMetadata,
    FirmwareUploadCancelledError,
    UploadStage,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

# pylint: disable=protected-access,too-many-lines


class _HeadlessVariable:
    """Small variable substitute for firmware-window logic tests without Tcl/Tk."""

    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def _headless_firmware_window() -> firmware_upload.FirmwareUploadWindow:
    """Create a controller-only firmware window shell for display-free behavior tests."""
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.root.winfo_exists.return_value = True
    window.flight_controller = MagicMock()
    window.service = MagicMock(spec=firmware_upload.FirmwareUploadService)
    window.worker_launcher = MagicMock()
    window.events = SimpleQueue()
    window.cancelled = Event()
    window.releases = []
    window.board_id = None
    window.catalog_request_id = 0
    window.busy = False
    window.uploading = False
    window.connecting = False
    window.restart_required = False
    window.owns_connection = False
    window._connection_timer_id = None
    window._event_poll_id = None
    window._active_progress_stage = None
    window.vehicle_type = _HeadlessVariable()
    window.target = _HeadlessVariable()
    window.version = _HeadlessVariable()
    window.board_text = MagicMock()
    window.status = MagicMock()
    for name in (
        "connect_button",
        "refresh_button",
        "type_combo",
        "target_combo",
        "version_combo",
        "custom_button",
        "upload_button",
        "cancel_button",
    ):
        setattr(window, name, MagicMock())
    window.progress_bars = {
        stage: MagicMock()
        for stage in UploadStage
        if stage in {UploadStage.ERASING, UploadStage.PROGRAMMING, UploadStage.VERIFYING}
    }
    for indicator in window.progress_bars.values():
        indicator.cget.return_value = "determinate"
    return window


@pytest.mark.parametrize(("windowing_system", "height"), [("win32", 426), ("x11", 328), ("aqua", 328)])
def test_firmware_window_is_thirty_percent_taller_only_on_windows(windowing_system: str, height: int) -> None:
    """
    Only Windows gets extra room for firmware upload controls.

    GIVEN: A firmware window opening on a supported platform.
    WHEN: Its initial geometry is calculated.
    THEN: Windows height increases by 30 percent before DPI scaling; other platforms are unchanged.
    """

    def initialize_window(window: BaseWindow, _parent: object = None) -> None:
        window.root = MagicMock()
        window.root.tk.call.return_value = windowing_system
        window.main_frame = MagicMock()

    with (
        patch.object(BaseWindow, "__init__", new=initialize_window),
        patch.object(BaseWindow, "calculate_scaled_geometry", return_value="scaled") as geometry,
        patch.object(BaseWindow, "center_window_on_screen"),
        patch.object(firmware_upload.FirmwareUploadWindow, "_create_selection_widgets"),
        patch.object(firmware_upload.FirmwareUploadWindow, "_create_progress_bars"),
        patch.object(firmware_upload.FirmwareUploadWindow, "_add_window_tooltips"),
        patch.object(firmware_upload.FirmwareUploadWindow, "_refresh_board"),
        patch.object(firmware_upload.tk, "StringVar"),
        patch.object(firmware_upload.ttk, "LabelFrame"),
        patch.object(firmware_upload.ttk, "Label"),
        patch.object(firmware_upload.ttk, "Button"),
        patch.object(firmware_upload.ttk, "Frame"),
    ):
        service = MagicMock(spec=firmware_upload.FirmwareUploadService)
        workers: list[Callable[[], None]] = []
        window = firmware_upload.FirmwareUploadWindow(MagicMock(), service=service, worker_launcher=workers.append)

    geometry.assert_called_once_with(750, height)
    assert not window.restart_required
    assert window.service is service
    assert window.worker_launcher.__self__ is workers
    assert window.worker_launcher.__name__ == "append"
    assert not workers


def test_firmware_window_builds_help_action_without_a_display() -> None:
    """
    The firmware window exposes a help action that opens its published manual.

    GIVEN: A firmware window built with mocked widgets and no display server.
    WHEN: The user activates Help.
    THEN: The published firmware upload manual opens in the browser.
    """
    buttons: list[tuple[MagicMock, dict[str, object]]] = []

    def make_button(*_args: object, **kwargs: object) -> MagicMock:
        button = MagicMock()
        buttons.append((button, kwargs))
        return button

    def initialize_window(window: BaseWindow, _parent: object = None) -> None:
        window.root = MagicMock()
        window.root.tk.call.return_value = "x11"
        window.main_frame = MagicMock()

    with (
        patch.object(BaseWindow, "__init__", new=initialize_window),
        patch.object(BaseWindow, "calculate_scaled_geometry", return_value="scaled"),
        patch.object(BaseWindow, "center_window_on_screen"),
        patch.object(firmware_upload.ttk, "Frame", side_effect=lambda *_args, **_kwargs: MagicMock()),
        patch.object(firmware_upload.ttk, "LabelFrame", side_effect=lambda *_args, **_kwargs: MagicMock()),
        patch.object(firmware_upload.ttk, "Label", side_effect=lambda *_args, **_kwargs: MagicMock()),
        patch.object(firmware_upload.ttk, "Combobox", side_effect=lambda *_args, **_kwargs: MagicMock()),
        patch.object(firmware_upload.ttk, "Progressbar", side_effect=lambda *_args, **_kwargs: MagicMock()),
        patch.object(firmware_upload.ttk, "Button", side_effect=make_button),
        patch.object(firmware_upload.tk, "StringVar", side_effect=MagicMock),
        patch.object(firmware_upload, "show_tooltip"),
        patch.object(firmware_upload.FirmwareUploadWindow, "_refresh_board"),
        patch.object(firmware_upload, "webbrowser_open_url") as open_url,
    ):
        parent = MagicMock()
        parent.winfo_viewable.return_value = True
        window = firmware_upload.FirmwareUploadWindow(MagicMock(), parent=parent, service=MagicMock())

        help_action = cast(
            "Callable[[], None]", next(kwargs["command"] for _button, kwargs in buttons if kwargs.get("text") == "Help")
        )
        assert callable(help_action)
        help_action()

    open_url.assert_called_once_with("https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_firmware_upload.html")
    window.root.transient.assert_called_once_with(parent)
    assert window.help_button is not None


def test_window_refreshes_board_and_selects_a_matching_catalog_release_headlessly() -> None:
    """
    Connected-board data leads to only matching firmware choices being enabled.

    GIVEN: A connected board and a matching official release in the catalog.
    WHEN: The window refreshes the board and handles the catalog result.
    THEN: It selects the matching firmware and enables upload after version selection.
    """
    window = _headless_firmware_window()
    board = FirmwareBoardInfo(9, "fmuv3", "COM3", "Copter")
    window.service.connected_board_info.return_value = board
    release = FirmwareRelease(
        "Copter", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.apj", 9
    )
    window.service.releases_for_connected_board.return_value = [release]
    workers: list[Callable[[], None]] = []
    window.worker_launcher.side_effect = workers.append

    window._refresh_board()
    assert window.board_id == 9
    assert window.busy
    workers.pop()()
    event = window.events.get_nowait()
    window._handle_event(event)

    assert window.vehicle_type.get() == "Copter - multicopter"
    assert window.target.get() == "fmuv3"
    window.version.set(release.label)
    assert window._selected_release() is release
    window._version_selected()
    window.upload_button.configure.assert_called_with(state="normal")  # pylint: disable=no-member


def test_catalog_worker_reports_failures_and_stale_results_are_ignored() -> None:
    """
    Catalog failures reach the user, while responses for an older request are discarded.

    GIVEN: A catalog worker that fails and then a result from an earlier request.
    WHEN: Both events reach the window.
    THEN: Failure is reported without requiring restart and the stale result is ignored.
    """
    window = _headless_firmware_window()
    window.board_id = 9
    window.catalog_request_id = 3
    workers: list[Callable[[], None]] = []
    window.worker_launcher.side_effect = workers.append
    window.service.releases_for_connected_board.side_effect = RuntimeError("catalog offline")
    window.service.connected_board_info.return_value = FirmwareBoardInfo(9, "fmuv3", "COM3", "Copter")

    window.refresh_versions()
    workers.pop()()
    failure = window.events.get_nowait()
    with patch.object(firmware_upload.messagebox, "showerror") as showerror:
        window._handle_event(failure)
    assert failure == ("catalog_error", 4, "catalog offline")
    assert window.status.set.call_args.args == ("catalog offline",)
    showerror.assert_called_once_with(firmware_upload._("Firmware catalog error"), "catalog offline", parent=window.root)
    assert not window.restart_required
    assert not window.busy

    window._show_catalog = MagicMock()
    window._handle_event(("catalog", 2, []))
    window._show_catalog.assert_not_called()


def test_upload_worker_relays_confirmation_progress_status_and_failure_events() -> None:
    """
    A worker supplies callbacks that enqueue UI events and returns without touching Tk.

    GIVEN: A deferred worker whose upload emits callbacks and then fails.
    WHEN: The worker runs on the background launcher.
    THEN: Confirmation, progress, status, and error events are queued in order.
    """
    window = _headless_firmware_window()
    workers: list[Callable[[], None]] = []
    window.worker_launcher.side_effect = workers.append
    image = FirmwareImage(
        metadata=FirmwareImageMetadata(
            path=Path("firmware.apj"),
            board_id=9,
            image_size=1,
            extf_image_size=0,
            firmware_version="4.6.0",
            git_identity="abc1234",
            apj_sha256="abc",
        ),
        image=b"\0\0\0\0",
    )
    bootloader = BootloaderInfo(5, 9, 0, 2048)

    def upload(callbacks: FirmwareUploadCallbacks) -> None:
        assert callbacks.confirmation_requested is not None
        assert not callbacks.confirmation_requested(image, bootloader)
        assert callbacks.progress_callback is not None
        callbacks.progress_callback(UploadStage.PROGRAMMING, 1, 2)
        assert callbacks.status_callback is not None
        callbacks.status_callback("Preparing image")
        message = "flash failed"
        raise RuntimeError(message)

    window._start_upload("release", upload)
    with patch.object(Event, "wait", return_value=False):
        workers.pop()()
    events = [window.events.get_nowait() for _ in range(4)]
    confirmation, progress, status, failure = events
    assert confirmation[:4] == ("confirm", "release", "abc", 9)
    assert isinstance(confirmation[4], Event)
    assert not confirmation[4].is_set()
    assert confirmation[5] == []
    assert progress == ("progress", UploadStage.PROGRAMMING, 1, 2)
    assert status == ("status", "Preparing image")
    assert failure[0] == "error"
    assert isinstance(failure[1], RuntimeError)
    assert str(failure[1]) == "flash failed"


@pytest.mark.parametrize("board_present", [True, False])
def test_connection_monitor_marks_restart_only_after_idle_board_removal(board_present: bool) -> None:
    """
    The USB monitor records board removal only when the window is idle.

    GIVEN: An idle board that remains connected or disappears.
    WHEN: The periodic connection check runs.
    THEN: Restart is required only after removal and the next check is scheduled.
    """
    window = _headless_firmware_window()
    window.board_id = 9
    window.service.disconnect_if_serial_port_removed.return_value = not board_present
    window.flight_controller.master = object() if board_present else None
    window._refresh_board = MagicMock()

    window._monitor_connection()

    assert window.restart_required is (not board_present)
    if not board_present:
        window._refresh_board.assert_called_once_with()
    window.root.after.assert_called_once_with(1000, window._monitor_connection)


def test_connection_selector_shares_parent_interpreter_and_stops_refresh_on_close() -> None:
    """
    The firmware connection selector remains a child of the existing Tk interpreter.

    GIVEN: A visible parent window and an existing flight-controller connection.
    WHEN: The selector opens and then closes.
    THEN: It uses the parent interpreter and stops its refresh timer.
    """
    parent = MagicMock()
    parent.winfo_viewable.return_value = True
    controller = MagicMock()

    def initialize_window(window: BaseWindow, _parent: object) -> None:
        window.root = MagicMock()
        window.main_frame = MagicMock()

    with (
        patch.object(BaseWindow, "__init__", new=initialize_window),
        patch.object(BaseWindow, "calculate_scaled_geometry", return_value="scaled"),
        patch.object(firmware_upload.ttk, "LabelFrame", return_value=MagicMock()),
        patch.object(firmware_upload.ttk, "Button", return_value=MagicMock()),
        patch.object(firmware_upload, "ConnectionSelectionWidgets") as widgets,
        patch.object(firmware_upload, "_show_firmware_tooltip"),
    ):
        selector = firmware_upload._FirmwareConnectionSelector(parent, controller)
        selector.close()

    selector.root.transient.assert_called_once_with(parent)
    widgets.assert_called_once()
    widgets.return_value.stop_periodic_refresh.assert_called_once_with()
    selector.root.destroy.assert_called_once_with()


def test_connect_marks_restart_when_a_new_board_is_connected() -> None:
    """
    Connecting a board from the selector makes a fresh AMC session necessary.

    GIVEN: No active controller and a selector that connects one.
    WHEN: The selector closes.
    THEN: The window records the restart requirement and restores the prior grab.
    """
    window = _headless_firmware_window()
    window.flight_controller.master = None
    previous_grab = MagicMock()
    previous_grab.winfo_exists.return_value = True
    window.root.grab_current.return_value = previous_grab

    def connect_from_selector(_root: object) -> None:
        window.flight_controller.master = object()

    window.root.wait_window.side_effect = connect_from_selector
    window._refresh_board = MagicMock()
    selector_root = MagicMock()
    with patch.object(firmware_upload, "_FirmwareConnectionSelector") as selector:
        selector.return_value.root = selector_root
        window.connect()

    assert window.restart_required
    assert not window.connecting
    selector_root.grab_set.assert_called_once_with()
    previous_grab.grab_set.assert_called_once_with()
    window._refresh_board.assert_called_once_with()


def test_empty_catalog_clears_firmware_choices_and_finish_refreshes_the_board() -> None:
    """
    An empty catalog or disconnected board leaves no firmware selection enabled.

    GIVEN: An empty catalog followed by a disconnected board.
    WHEN: Catalog display and upload completion are handled.
    THEN: Firmware choices clear and the board status is refreshed.
    """
    window = _headless_firmware_window()
    window._show_catalog([])
    assert window.vehicle_type.get() == ""
    assert window.target.get() == ""
    assert window.version.get() == ""
    window.type_combo.configure.assert_called_with(values=[], state="disabled")  # pylint: disable=no-member

    window.board_id = 9
    window.service.connected_board_info.return_value = None
    window._finish("disconnected")
    assert not window.busy
    assert not window.uploading
    assert window.board_id is None
    assert window.status.set.call_args.args == ("disconnected",)


def test_progress_animation_switches_modes_and_clamps_measured_values() -> None:
    """
    Unknown progress is animated, then stops cleanly when measured progress returns.

    GIVEN: An erase operation with no estimate followed by measured progress over 100 percent.
    WHEN: Progress events update the bar.
    THEN: The bar animates, stops, and clamps its displayed value to 100.
    """
    window = _headless_firmware_window()
    progress_bar = window.progress_bars[UploadStage.ERASING]
    progress_bar.cget.return_value = "determinate"

    window._update_progress(UploadStage.ERASING, 0, 0)
    progress_bar.configure.assert_called_with(mode="indeterminate")
    progress_bar.start.assert_called_once_with(12)

    progress_bar.cget.return_value = "indeterminate"
    window._update_progress(UploadStage.ERASING, 120, 100)
    progress_bar.stop.assert_called_once_with()
    progress_bar.configure.assert_called_with(mode="determinate", value=100)


def test_missing_board_clears_choices_and_monitor_reschedules_closed_windows() -> None:
    """
    A lost board clears stale selections and the monitor avoids scheduling a destroyed window.

    GIVEN: The controller disconnects and the window is then destroyed while connecting.
    WHEN: Board refresh and periodic monitoring run.
    THEN: Stale choices clear and no callback is scheduled for the dead window.
    """
    window = _headless_firmware_window()
    window.board_id = 9
    window.service.connected_board_info.return_value = None
    window._refresh_board()
    assert window.board_id is None
    assert window.vehicle_type.get() == ""
    assert window.status.set.call_args.args == ("Connect a flight controller to detect its board",)

    window.root.winfo_exists.return_value = False
    window.board_id = 9
    window.connecting = True
    window.service.disconnect_if_serial_port_removed.reset_mock()
    window._monitor_connection()
    window.service.disconnect_if_serial_port_removed.assert_not_called()
    window.root.after.assert_not_called()


def test_accepted_official_upload_runs_successful_worker_and_enables_retry() -> None:
    """
    An accepted release runs through the service and a successful result enables safe retry.

    GIVEN: A selected release and an affirmative preparation confirmation.
    WHEN: The deferred upload worker completes successfully.
    THEN: The result requires restart and the matching release remains selectable.
    """
    window = _headless_firmware_window()
    release = FirmwareRelease(
        "Plane", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Plane/stable/fmuv3/arduplane.apj", 9
    )
    window.releases = [release]
    window.vehicle_type.set("Plane")
    window.target.set("fmuv3")
    window.version.set(release.label)
    window.board_id = 9
    window.service.connected_board_info.return_value = FirmwareBoardInfo(9, "fmuv3", "COM3", "Plane")
    workers: list[Callable[[], None]] = []
    window.worker_launcher.side_effect = workers.append
    with (
        patch.object(firmware_upload.messagebox, "askyesno", return_value=True) as ask_confirmation,
        patch.object(firmware_upload.messagebox, "showinfo") as show_info,
    ):
        window.start_upload()
        ask_confirmation.assert_called_once()
        assert ask_confirmation.call_args.args[0] == firmware_upload._("Upload ArduPilot firmware")
        assert release.label in ask_confirmation.call_args.args[1]
        assert ask_confirmation.call_args.kwargs["parent"] is window.root
        assert len(workers) == 1

        workers.pop()()
        done_event = window.events.get_nowait()
        assert done_event == ("done",)
        window._handle_event(done_event)

    window.service.upload_release.assert_called_once()
    upload_args, upload_kwargs = window.service.upload_release.call_args
    assert upload_args == (window.flight_controller, release)
    callbacks = upload_kwargs["callbacks"]
    assert isinstance(callbacks, FirmwareUploadCallbacks)
    assert callbacks.cancellation_requested is not None
    assert not callbacks.cancellation_requested()
    assert callbacks.confirmation_requested is not None
    assert callbacks.progress_callback is not None
    assert callbacks.status_callback is not None
    assert window.restart_required
    assert window.upload_button.configure.call_args.kwargs["state"] == "normal"  # pylint: disable=no-member
    show_info.assert_called_once()
    assert show_info.call_args.args[0] == firmware_upload._("Upload ArduPilot firmware")
    expected_status = firmware_upload._("Firmware upload completed and flight controller reconnected")
    expected_dialog = (
        expected_status + "\n\n" + firmware_upload._("Close this window and restart AMC before continuing configuration.")
    )
    assert window.status.set.call_args.args == (expected_status,)
    assert show_info.call_args.args[1] == expected_dialog
    assert show_info.call_args.kwargs["parent"] is window.root


def test_confirmation_event_releases_worker_even_when_dialog_fails() -> None:
    """
    A confirmation dialog failure rejects the flash and wakes its waiting worker.

    GIVEN: A worker waiting for a final decision and a dialog that raises.
    WHEN: The confirmation event is dispatched.
    THEN: The decision is rejected and the waiting event is released.
    """
    window = _headless_firmware_window()
    reply = Event()
    result: list[bool] = []
    with patch.object(firmware_upload.messagebox, "askyesno", side_effect=RuntimeError("dialog unavailable")):
        window._handle_event(("confirm", "release", "digest", 9, reply, result))
    assert reply.is_set()
    assert result == [False]
    assert window.status.set.call_args.args == ("dialog unavailable",)


def test_close_disconnects_owned_controller_and_cancels_pending_callbacks() -> None:
    """
    Closing an idle standalone window releases its controller and scheduled callbacks.

    GIVEN: An idle standalone window with two scheduled callbacks.
    WHEN: The user closes the window.
    THEN: The controller disconnects, callbacks are cancelled, and the window is destroyed.
    """
    window = _headless_firmware_window()
    window.owns_connection = True
    window._connection_timer_id = "connection-timer"
    window._event_poll_id = "event-poll"

    window.close()

    window.flight_controller.disconnect.assert_called_once_with()
    assert [call.args[0] for call in window.root.after_cancel.call_args_list] == ["connection-timer", "event-poll"]
    window.root.destroy.assert_called_once_with()


def test_idle_connection_actions_handle_busy_states_and_optional_grabs() -> None:
    """
    Busy actions return early and a closed parent is not re-grabbed after selection.

    GIVEN: An upload in progress followed by a selector whose parent closes.
    WHEN: Connection and upload actions are requested.
    THEN: Busy work is left alone and no destroyed parent receives a grab.
    """
    window = _headless_firmware_window()
    window.uploading = True
    with patch.object(firmware_upload, "_FirmwareConnectionSelector") as selector:
        window.connect()
    selector.assert_not_called()

    window.uploading = False
    window.flight_controller.master = object()
    window.root.grab_current.return_value = None
    window.root.winfo_exists.return_value = False
    window._refresh_board = MagicMock()
    with patch.object(firmware_upload, "_FirmwareConnectionSelector") as selector:
        selector.return_value.root = MagicMock()
        window.connect()
    window._refresh_board.assert_not_called()

    window._selected_release = MagicMock(return_value=None)
    window.start_upload()
    window.uploading = True
    window.service.connected_board_info.reset_mock()
    window.select_custom_firmware()
    window.service.connected_board_info.assert_not_called()


def test_event_status_and_erase_progress_disable_cancellation() -> None:
    """
    Status and erase events update the message and prevent cancellation after erase starts.

    GIVEN: A download status followed by an erase progress event.
    WHEN: The window handles both events.
    THEN: The current status is shown and cancellation is disabled during erase.
    """
    window = _headless_firmware_window()
    window._handle_event(("status", "Downloading image"))
    window.status.set.assert_called_with("Downloading image")

    window._handle_event(("progress", UploadStage.ERASING, 1, 0))
    window.cancel_button.configure.assert_called_with(state="disabled")
    window.progress_bars[UploadStage.ERASING].cget.return_value = "indeterminate"
    window._update_progress(UploadStage.ERASING, 1, 0)
    window.progress_bars[UploadStage.ERASING].start.assert_called_once_with(12)


def test_progress_cleanup_and_close_cover_idle_window_without_owned_callbacks() -> None:
    """
    Closing an embedded idle window leaves the shared controller connected.

    GIVEN: An embedded window with an animating progress bar.
    WHEN: Animation cleanup and close run.
    THEN: The bar stops and the shared controller remains connected.
    """
    window = _headless_firmware_window()
    progress_bar = window.progress_bars[UploadStage.ERASING]
    progress_bar.cget.return_value = "indeterminate"
    window._stop_progress_animations()
    progress_bar.stop.assert_called_once_with()

    window.close()
    window.flight_controller.disconnect.assert_not_called()
    window.root.after_cancel.assert_not_called()
    window.root.destroy.assert_called_once_with()


def test_default_worker_launcher_starts_a_daemon_thread() -> None:
    """
    Production work runs outside the Tk thread.

    GIVEN: The default worker launcher and a task.
    WHEN: The task is launched.
    THEN: A daemon thread starts with that task without executing it on the calling thread.
    """
    worker = MagicMock()
    with patch.object(firmware_upload, "Thread") as thread:
        firmware_upload._start_background_worker(worker)

    thread.assert_called_once_with(target=worker, daemon=True)
    thread.return_value.start.assert_called_once_with()
    worker.assert_not_called()


@pytest.mark.parametrize(
    ("event", "restart_required"),
    [
        (("done",), True),
        (("error", RuntimeError("upload failed")), True),
        (("error", FirmwareCompatibilityError("wrong board")), True),
        (("error", FirmwareBootloaderRecoveryError("recovery failed")), True),
        (("error", FirmwareUploadCancelledError("cancelled")), False),
    ],
)
def test_upload_result_selects_restart_or_return_to_amc(event: tuple, restart_required: bool) -> None:
    """
    Successful and failed uploads require restart, but safe cancellation does not.

    GIVEN: A firmware worker result.
    WHEN: The UI receives it.
    THEN: Closing the window requires restart only for success or failure.
    AND: Cancellation is presented as information rather than an upload failure.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.restart_required = False
    window._finish = MagicMock()
    with patch.object(firmware_upload, "messagebox") as dialogs:
        window._handle_event(event)

    assert window.restart_required is restart_required
    window.root.destroy.assert_not_called()
    if not restart_required:
        dialogs.showerror.assert_not_called()
        dialogs.showinfo.assert_called_once_with("Firmware upload cancelled", "cancelled", parent=window.root)
    else:
        dialog = dialogs.showinfo if event[0] == "done" else dialogs.showerror
        assert "restart AMC" in dialog.call_args.args[1]


@pytest.mark.parametrize("first_result", [("done",), ("error", RuntimeError("upload failed"))])
def test_cancelling_a_retry_does_not_clear_an_existing_restart_requirement(first_result: tuple) -> None:
    """
    A cancelled retry cannot make the application state valid again.

    GIVEN: A completed or failed upload.
    WHEN: A later upload is safely cancelled.
    THEN: Closing the window still requires restarting AMC.
    """
    child = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    child.root = MagicMock()
    child.restart_required = False
    child._finish = MagicMock()
    with patch.object(firmware_upload, "messagebox"):
        child._handle_event(first_result)
        child._handle_event(("error", FirmwareUploadCancelledError("cancelled")))
    assert child.restart_required


def test_catalog_failure_without_an_upload_does_not_require_restart() -> None:
    """
    Firmware catalog errors do not change the installed controller state.

    GIVEN: An idle window loading the catalog without attempting an upload.
    WHEN: The catalog download fails.
    THEN: Closing the window can return to AMC without restarting.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.catalog_request_id = 1
    window.uploading = False
    window.restart_required = False
    window._finish = MagicMock()
    with patch.object(firmware_upload, "messagebox") as dialogs:
        window._handle_event(("catalog_error", 1, "network error"))

    assert not window.restart_required
    dialogs.showerror.assert_called_once_with("Firmware catalog error", "network error", parent=window.root)


@pytest.mark.parametrize("window_exists", [True, False])
def test_polling_delivers_queued_events_in_order_and_only_reschedules_a_live_window(window_exists: bool) -> None:
    """
    Polling is independent of event presentation.

    GIVEN: Two queued worker events and a live or closed window.
    WHEN: The event queue is polled.
    THEN: Both events are dispatched in order and only a live window schedules another poll.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.events = SimpleQueue()
    events = [("status", "Preparing"), ("done",)]
    for event in events:
        window.events.put(event)
    window.root = MagicMock()
    window.root.winfo_exists.return_value = window_exists
    window._handle_event = MagicMock()

    window._poll_events()

    assert [call.args[0] for call in window._handle_event.call_args_list] == events
    assert window.events.empty()
    if window_exists:
        window.root.after.assert_called_once_with(100, window._poll_events)
    else:
        window.root.after.assert_not_called()


def test_event_presentation_failure_does_not_stop_future_polling() -> None:
    """
    A presentation failure is not mistaken for an empty event queue.

    GIVEN: A queued event whose handler raises.
    WHEN: The queue is polled.
    THEN: The error propagates and the live window still schedules its next poll.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.events = SimpleQueue()
    window.events.put(("done",))
    window.root = MagicMock()
    window._handle_event = MagicMock(side_effect=RuntimeError("dialog failed"))

    with pytest.raises(RuntimeError, match="dialog failed"):
        window._poll_events()

    window.root.after.assert_called_once_with(100, window._poll_events)


@pytest.mark.parametrize("action", ["official", "local_picker", "local_confirmation"])
def test_declining_upload_preparation_leaves_amc_open(action: str) -> None:
    """
    Merely selecting firmware does not invalidate AMC state.

    GIVEN: An idle firmware window.
    WHEN: The user cancels the file picker or declines initial confirmation.
    THEN: No upload starts and closing the window does not require restart.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.busy = False
    window.uploading = False
    window.restart_required = False
    window.flight_controller = MagicMock()
    window.service = MagicMock()
    window._selected_release = MagicMock(return_value=MagicMock())
    window._start_upload = MagicMock()
    with (
        patch.object(
            firmware_upload.filedialog, "askopenfilename", return_value="" if action == "local_picker" else "test.apj"
        ),
        patch.object(firmware_upload.messagebox, "askyesno", return_value=False),
    ):
        if action == "official":
            window.start_upload()
        else:
            window.select_custom_firmware()

    window._start_upload.assert_not_called()
    assert not window.restart_required


def test_closing_during_upload_waits_for_the_result() -> None:
    """
    An in-progress upload cannot be dismissed.

    GIVEN: A running upload with an owned controller connection.
    WHEN: The user closes the firmware window.
    THEN: The window and connection remain alive until the result arrives.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.uploading = True
    window.owns_connection = True
    window.flight_controller = MagicMock()
    with patch.object(firmware_upload.messagebox, "showinfo") as dialog:
        window.close()

    window.root.destroy.assert_not_called()
    window.flight_controller.disconnect.assert_not_called()
    dialog.assert_called_once()


@pytest.mark.parametrize(
    ("arguments", "device", "baudrate", "reboot_time"),
    [
        ([], "", 115200, 8),
        (["--device", "/dev/ttyUSB0", "--baudrate", "57600", "--reboot-time", "12"], "/dev/ttyUSB0", 57600, 12),
    ],
)
def test_standalone_connects_on_startup_with_cli_options(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str], device: str, baudrate: int, reboot_time: int
) -> None:
    """Given default or explicit FC options, startup connects before opening the upload window."""
    monkeypatch.setattr("sys.argv", ["firmware-upload", *arguments])
    with (
        patch.object(firmware_upload, "FlightController") as controller_class,
        patch.object(firmware_upload, "FirmwareUploadWindow") as window_class,
        patch.object(firmware_upload, "configure_standalone_logging"),
    ):
        controller = controller_class.return_value
        controller.connect.return_value = ""

        firmware_upload.main()

    controller_class.assert_called_once_with(reboot_time=reboot_time, baudrate=baudrate)
    controller.connect.assert_called_once_with(device)
    window_class.assert_called_once_with(controller)
    window_class.return_value.root.mainloop.assert_called_once_with()
    controller.disconnect.assert_called_once_with()


def test_standalone_releases_controller_when_connection_is_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a cancelled connection attempt, startup leaves no window or open controller."""
    monkeypatch.setattr("sys.argv", ["firmware-upload"])
    with (
        patch.object(firmware_upload, "FlightController") as controller_class,
        patch.object(firmware_upload, "FirmwareUploadWindow") as window_class,
        patch.object(firmware_upload, "connect_standalone_flight_controller", return_value=False),
        patch.object(firmware_upload, "configure_standalone_logging"),
    ):
        firmware_upload.main()

    window_class.assert_not_called()
    controller_class.return_value.disconnect.assert_called_once_with()


def test_connect_selector_shares_firmware_window_and_closes_without_disconnect() -> None:
    """Given a running firmware window, its connection selector closes without stopping the owner."""
    root = tk.Tk()
    root.withdraw()
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = root
    window.flight_controller = MagicMock()
    window.connect_button = MagicMock()
    window.uploading = False
    window.connecting = False
    try:
        root.grab_set()
        with (
            patch.object(root, "wait_window") as wait_window,
            patch.object(firmware_upload, "ConnectionSelectionWidgets", create=True),
            patch.object(firmware_upload.FirmwareUploadWindow, "_refresh_board"),
        ):
            window.connect()
            selector_root = wait_window.call_args.args[0]
            assert isinstance(selector_root, tk.Toplevel)
            assert selector_root.tk is root.tk
            assert root.grab_current() is root
            selector_root.destroy()
            assert root.winfo_exists()
            window.flight_controller.disconnect.assert_not_called()
    finally:
        root.destroy()


def test_firmware_window_can_be_embedded_under_an_existing_tk_root() -> None:
    """Given an application owner, firmware upload opens as its child and preserves the owner's FC."""
    owner = tk.Tk()
    owner.withdraw()
    controller = MagicMock()
    try:
        with patch.object(firmware_upload.FirmwareUploadService, "connected_board_info", return_value=None):
            window = firmware_upload.FirmwareUploadWindow(controller, parent=owner)
        assert isinstance(window.service, firmware_upload.FirmwareUploadService)
        assert window.worker_launcher is firmware_upload._start_background_worker
        assert isinstance(window.root, tk.Toplevel)
        assert window.root.tk is owner.tk
        window.close()
        assert owner.winfo_exists()
        controller.disconnect.assert_not_called()
    finally:
        owner.destroy()


@pytest.mark.parametrize(("installed_type", "selected_index"), [("Copter", 0), ("Heli", 1)])
def test_catalog_widgets_render_model_choices_and_require_explicit_version_selection(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow, installed_type: str, selected_index: int
) -> None:
    """
    The frontend renders catalog choices without implicitly selecting firmware.

    GIVEN: An installed Copter variant and two catalog firmware types.
    WHEN: The catalog is displayed and the user changes firmware type.
    THEN: Model choices are rendered, the installed type is preferred, and the version choice is reset.
    """
    window = connected_firmware_window
    releases = [
        FirmwareRelease(
            "Copter", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.apj", 9
        ),
        FirmwareRelease(
            "Copter", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter-heli.apj", 9
        ),
    ]
    window.service.connected_board_info = MagicMock(return_value=FirmwareBoardInfo(9, "fmuv3", "COM3", installed_type))
    window._show_catalog(releases)
    selected = releases[selected_index]
    assert window.type_combo.cget("values") == ("Copter - heli", "Copter - multicopter")
    assert window.vehicle_type.get() == selected.firmware_type_label
    assert window.target_combo.cget("values") == ("fmuv3",)
    assert window.target.get() == "fmuv3"
    assert window.version_combo.cget("values") == (selected.label,)
    assert not window.version.get()
    assert str(window.upload_button.cget("state")) == "disabled"

    window.version.set(selected.label)
    window._version_selected()
    assert window._selected_release() is selected
    assert str(window.upload_button.cget("state")) == "normal"

    window.vehicle_type.set(releases[1 - selected_index].firmware_type_label)
    window._update_targets()
    assert not window.version.get()
    assert window._selected_release() is None
    assert str(window.upload_button.cget("state")) == "disabled"


def test_ambiguous_detected_board_leaves_target_and_upload_unselected(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
) -> None:
    """A board name shared by several catalog targets requires an explicit target choice."""
    window = connected_firmware_window
    releases = [
        FirmwareRelease(
            "Copter",
            "4.6.0",
            "OFFICIAL",
            target,
            f"https://firmware.ardupilot.org/Copter/stable/{target}/arducopter.apj",
            9,
        )
        for target in ("CubeBlack", "fmuv3")
    ]
    window.service.connected_board_info = MagicMock(return_value=FirmwareBoardInfo(9, "CubeBlack, fmuv3", "COM3", "Copter"))

    window._show_catalog(releases)

    assert window.target_combo.cget("values") == ("CubeBlack", "fmuv3")
    assert not window.target.get()
    assert not window.version.get()
    assert str(window.version_combo.cget("state")) == "disabled"
    assert str(window.upload_button.cget("state")) == "disabled"


def test_progress_stage_is_translated_before_it_is_displayed() -> None:
    """A bootloader progress event shows a readable translated stage."""
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.status = MagicMock()
    window.cancel_button = MagicMock()
    window._update_progress = MagicMock()
    with patch.object(firmware_upload, "_", side_effect=lambda value: f"translated {value}"):
        window._handle_event(("progress", UploadStage.ENTERING_BOOTLOADER, 0, 1))

    window.status.set.assert_called_once_with("translated Firmware upload: translated Entering bootloader")


def test_user_can_select_a_local_apj_for_the_connected_board() -> None:
    """The file picker passes the chosen local APJ to the custom upload path."""
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.busy = True  # The online catalog may still be loading.
    window.uploading = False
    window.root = MagicMock()
    window.flight_controller = MagicMock()
    window.service = MagicMock()
    window.service.connected_board_info.return_value = FirmwareBoardInfo(50, "ExampleBoard", "/dev/ttyACM0", "Copter")
    window._start_upload = MagicMock()

    with (
        patch.object(firmware_upload.filedialog, "askopenfilename", return_value="/firmware/custom.apj") as picker,
        patch.object(firmware_upload.messagebox, "askyesno", return_value=True),
    ):
        window.select_custom_firmware()

    assert picker.call_args.kwargs["filetypes"][0][1] == "*.apj"
    label, upload = window._start_upload.call_args.args
    assert label == str(firmware_upload.Path("/firmware/custom.apj"))
    callbacks = FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True)
    upload(callbacks)
    window.service.upload_custom_file.assert_called_once_with(
        window.flight_controller, firmware_upload.Path("/firmware/custom.apj"), callbacks=callbacks
    )


@pytest.mark.parametrize("connected", [True, False])
def test_board_rendering_only_updates_loaded_identity_and_connection_controls(connected: bool) -> None:
    """
    Rendering a board does not perform I/O or change operation status.

    GIVEN: Loaded board information or no connected controller.
    WHEN: The board display is rendered directly.
    THEN: Identity and connection controls reflect it without fetching or clearing a catalog.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    for name in ("board_text", "connect_button", "refresh_button", "custom_button", "status"):
        setattr(window, name, MagicMock())
    window.service = MagicMock()
    window.worker_launcher = MagicMock()
    window.refresh_versions = MagicMock()
    window._clear_catalog = MagicMock()
    board_info = FirmwareBoardInfo(50, "ExampleBoard", "/dev/ttyACM1", "Copter") if connected else None

    window._render_board(board_info)

    assert window.board_id == (50 if connected else None)
    expected_label = (
        firmware_upload._("{board_name} (APJ board ID {board_id}) — {device}").format(
            board_name="ExampleBoard", board_id=50, device="/dev/ttyACM1"
        )
        if connected
        else firmware_upload._("No flight controller connected")
    )
    cast("MagicMock", window.board_text.set).assert_called_once_with(expected_label)
    cast("MagicMock", window.connect_button.configure).assert_called_once_with(state="disabled" if connected else "normal")
    cast("MagicMock", window.refresh_button.configure).assert_called_once_with(  # pylint: disable=no-member
        state="normal" if connected else "disabled"
    )
    cast("MagicMock", window.custom_button.configure).assert_called_once_with(  # pylint: disable=no-member
        state="normal" if connected else "disabled"
    )
    window.status.set.assert_not_called()
    assert not window.service.mock_calls
    window.worker_launcher.assert_not_called()
    window.refresh_versions.assert_not_called()
    window._clear_catalog.assert_not_called()


@pytest.mark.parametrize("board_state", ["unchanged", "reenumerated", "different", "disconnected"])
def test_finishing_upload_renders_board_without_fetching_a_catalog_or_replacing_result_status(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
    pending_workers: list[Callable[[], None]],
    board_state: str,
) -> None:
    """
    Upload completion renders connection changes without launching new work.

    GIVEN: A selected release and a board that stays connected, moves, changes identity, or disappears.
    WHEN: The upload finishes.
    THEN: The board display updates, stale choices are cleared, and no catalog task starts.
    """
    window = connected_firmware_window
    pending_workers.clear()
    release = FirmwareRelease(
        "Copter", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.apj", 9
    )
    window._show_catalog([release])
    window.version.set(release.label)
    window.busy = True
    window.uploading = True
    board_info = None
    if board_state != "disconnected":
        board_info = FirmwareBoardInfo(
            50 if board_state == "different" else 9, "fmuv3", "COM3" if board_state == "unchanged" else "COM13", "Copter"
        )
    service = cast("MagicMock", window.service)
    service.connected_board_info.return_value = board_info
    window._finish("Firmware upload completed")

    assert not window.busy
    assert not window.uploading
    assert window.status.get() == "Firmware upload completed"
    assert not pending_workers
    service.releases_for_connected_board.assert_not_called()
    assert window.board_id == (board_info.board_id if board_info is not None else None)
    if board_info is None:
        assert window.board_text.get() == firmware_upload._("No flight controller connected")
    else:
        assert board_info.device in window.board_text.get()
    valid_selection = board_state in {"unchanged", "reenumerated"}
    assert bool(window.releases) is valid_selection
    assert bool(window.version.get()) is valid_selection
    assert str(window.upload_button.cget("state")) == ("normal" if valid_selection else "disabled")


@pytest.mark.parametrize(("request_id", "uploading"), [(1, False), (1, True), (2, True)])
def test_old_or_busy_catalog_result_cannot_interrupt_custom_upload(request_id: int, uploading: bool) -> None:
    """Superseded manifest responses and responses received during upload are ignored."""
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.catalog_request_id = 2
    window.uploading = uploading
    window._show_catalog = MagicMock()
    window._finish = MagicMock()
    window._handle_event(("catalog", request_id, []))
    window._handle_event(("catalog_error", request_id, "network error"))

    window._show_catalog.assert_not_called()
    window._finish.assert_not_called()


def test_completed_progress_bar_keeps_its_value_when_next_stage_starts() -> None:
    """Given a completed erase, starting program keeps erase at 100 percent."""
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    erase_bar = MagicMock()
    erase_bar.cget.return_value = "determinate"
    program_bar = MagicMock()
    program_bar.cget.return_value = "determinate"
    window.progress_bars = {UploadStage.ERASING: erase_bar, UploadStage.PROGRAMMING: program_bar}
    window._active_progress_stage = UploadStage.ERASING

    window._update_progress(UploadStage.PROGRAMMING, 1, 10)

    erase_bar.stop.assert_not_called()
    program_bar.configure.assert_called_with(mode="determinate", value=10)


def test_progress_is_clamped_to_progressbar_range() -> None:
    """Given an out of range callback, the visible progress stays between zero and 100."""
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    indicator = MagicMock()
    indicator.cget.return_value = "determinate"
    window.progress_bars = {UploadStage.PROGRAMMING: indicator}
    window._active_progress_stage = UploadStage.PROGRAMMING

    window._update_progress(UploadStage.PROGRAMMING, 110, 100)

    indicator.configure.assert_called_with(mode="determinate", value=100)


def test_confirmation_dialog_failure_releases_worker_and_reports_error() -> None:
    """Given a confirmation dialog error, the worker is released and the UI keeps polling."""
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    window.status = MagicMock()
    reply = Event()
    result: list[bool] = []
    with patch.object(firmware_upload.messagebox, "askyesno", side_effect=RuntimeError("dialog failed")):
        window._handle_confirmation("Example release", "digest", 50, reply, result)

    assert reply.is_set()
    assert result == [False]
    window.status.set.assert_called_with("dialog failed")
    window.root.after.assert_not_called()


@pytest.mark.parametrize("accepted", [True, False])
def test_final_confirmation_delivers_the_decision_and_releases_the_worker(accepted: bool) -> None:
    """
    Final confirmation always supplies a decision to the waiting worker.

    GIVEN: An identified board awaiting permission to flash.
    WHEN: The user accepts or declines final confirmation.
    THEN: The worker receives that decision and is released without scheduling timers.
    """
    window = firmware_upload.FirmwareUploadWindow.__new__(firmware_upload.FirmwareUploadWindow)
    window.root = MagicMock()
    reply = Event()
    result: list[bool] = []
    with patch.object(firmware_upload.messagebox, "askyesno", return_value=accepted) as prompt:
        window._handle_event(("confirm", "Example release", "digest", 50, reply, result))

    assert reply.is_set()
    assert result == [accepted]
    assert "Example release" in prompt.call_args.args[1]
    assert "50" in prompt.call_args.args[1]
    assert "digest" in prompt.call_args.args[1]
    window.root.after.assert_not_called()


def test_upload_worker_stops_waiting_when_confirmation_ui_does_not_reply(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow, pending_workers: list[Callable[[], None]]
) -> None:
    """Given an unresponsive confirmation UI, the upload worker eventually declines the flash."""
    window = connected_firmware_window
    pending_workers.clear()  # Discard the initial catalog task without running it.
    confirmations: list[bool] = []

    def upload(callbacks: FirmwareUploadCallbacks) -> BootloaderInfo:
        assert callbacks.confirmation_requested is not None
        accepted = callbacks.confirmation_requested(MagicMock(), MagicMock())
        confirmations.append(accepted)
        if not accepted:
            message = "firmware upload was not confirmed"
            raise FirmwareUploadCancelledError(message)
        return BootloaderInfo(5, 9, 0, 2048)

    window._start_upload("Example release", upload)
    assert len(pending_workers) == 1
    with patch.object(Event, "wait", return_value=False) as wait:
        pending_workers.pop()()

    wait.assert_called_once_with(timeout=300)
    assert confirmations == [False]
    assert window.events.get_nowait()[0] == "confirm"
    error = window.events.get_nowait()
    assert error[0] == "error"
    assert isinstance(error[1], FirmwareUploadCancelledError)


@pytest.fixture(name="pending_workers")
def pending_workers_fixture() -> list[Callable[[], None]]:
    """Hold submitted tasks until the test explicitly runs them."""
    return []


@pytest.fixture(name="connected_firmware_window")
def firmware_window_fixture(
    pending_workers: list[Callable[[], None]],
) -> Generator[firmware_upload.FirmwareUploadWindow, None, None]:
    """Build the real firmware UI around a controller without a physical serial device."""
    owner = tk.Tk()
    owner.withdraw()
    controller = SimpleNamespace(
        master=object(),
        comport_device="COM3",
        info=SimpleNamespace(apj_board_id=9, firmware_type="fmuv3", vehicle_type="ArduCopter"),
        get_serial_ports=MagicMock(return_value=[SimpleNamespace(device="COM3")]),
        disconnect=MagicMock(),
    )

    def disconnect() -> None:
        controller.master = None

    controller.disconnect.side_effect = disconnect
    service = MagicMock(spec=firmware_upload.FirmwareUploadService, wraps=firmware_upload.FirmwareUploadService())
    with (
        patch("tkinter.Misc.update"),
        patch("tkinter.Misc.update_idletasks"),
    ):
        window = firmware_upload.FirmwareUploadWindow(
            controller, parent=owner, service=service, worker_launcher=pending_workers.append
        )
        try:
            yield window
        finally:
            window.uploading = False
            if window.root.winfo_exists():
                window.close()
            owner.destroy()


@pytest.mark.parametrize("catalog_fails", [False, True])
def test_catalog_task_uses_the_injected_service_and_waits_for_ui_delivery(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
    pending_workers: list[Callable[[], None]],
    catalog_fails: bool,
) -> None:
    """
    Catalog loading can be executed deterministically without networking or threads.

    GIVEN: A firmware window with an injected service and deferred worker launcher.
    WHEN: Its catalog task runs and the UI receives the result.
    THEN: The service is called only when the task runs, and the UI becomes idle only on delivery.
    """
    window = connected_firmware_window
    service = cast("MagicMock", window.service)
    if catalog_fails:
        service.releases_for_connected_board.side_effect = RuntimeError("catalog unavailable")
    else:
        service.releases_for_connected_board.return_value = []
    assert window.busy
    assert len(pending_workers) == 1
    service.releases_for_connected_board.assert_not_called()

    pending_workers.pop(0)()

    service.releases_for_connected_board.assert_called_once_with(9)
    assert window.busy
    assert not window.restart_required
    event = window.events.get_nowait()
    assert event[0] == ("catalog_error" if catalog_fails else "catalog")
    with patch.object(firmware_upload.messagebox, "showerror") as error_dialog:
        window._handle_event(event)

    assert not window.busy
    assert not window.restart_required
    assert error_dialog.call_count == int(catalog_fails)


@pytest.mark.parametrize("source", ["official", "local"])
def test_upload_sources_use_the_injected_service_and_deferred_launcher(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
    pending_workers: list[Callable[[], None]],
    source: str,
) -> None:
    """
    Official and local firmware share the injected scheduling boundary.

    GIVEN: A connected window with a fake upload service and a deferred worker launcher.
    WHEN: The user starts an upload and its deferred task runs.
    THEN: The selected source receives callbacks and completion is rendered only on UI delivery.
    """
    window = connected_firmware_window
    service = cast("MagicMock", window.service)
    pending_workers.clear()
    release = FirmwareRelease(
        "Copter", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.apj", 9
    )
    window._show_catalog([release])
    window.version.set(release.label)
    window._version_selected()
    service.upload_release.return_value = BootloaderInfo(5, 9, 0, 2048)
    service.upload_custom_file.return_value = BootloaderInfo(5, 9, 0, 2048)
    with (
        patch.object(firmware_upload.messagebox, "askyesno", return_value=True),
        patch.object(firmware_upload.filedialog, "askopenfilename", return_value="custom.apj"),
    ):
        if source == "official":
            window.upload_button.invoke()
        else:
            window.custom_button.invoke()
    service.upload_release.assert_not_called()
    service.upload_custom_file.assert_not_called()
    assert window.uploading
    assert not window.restart_required
    assert len(pending_workers) == 1

    pending_workers.pop(0)()

    upload = service.upload_release if source == "official" else service.upload_custom_file
    upload.assert_called_once()
    expected_source = release if source == "official" else firmware_upload.Path("custom.apj")
    assert upload.call_args.args == (window.flight_controller, expected_source)
    callbacks = upload.call_args.kwargs["callbacks"]
    assert callbacks.confirmation_requested is not None
    assert callbacks.cancellation_requested() is False
    window.cancelled.set()
    assert callbacks.cancellation_requested() is True
    assert callbacks.progress_callback is not None
    assert callbacks.status_callback is not None
    assert window.uploading  # Worker completion alone must not touch Tk state.
    assert not window.restart_required
    event = window.events.get_nowait()
    assert event == ("done",)
    with patch.object(firmware_upload.messagebox, "showinfo"):
        window._handle_event(event)

    assert not window.uploading
    assert window.restart_required


@pytest.mark.parametrize("cancelled", [False, True])
def test_injected_worker_relays_progress_status_and_typed_failure_without_touching_tk(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
    pending_workers: list[Callable[[], None]],
    cancelled: bool,
) -> None:
    """
    Worker events preserve their order and failure type until UI delivery.

    GIVEN: An upload emitting status, progress, and a failure or safe cancellation.
    WHEN: The deferred worker runs.
    THEN: Events are queued in order and the typed result controls restart only when rendered.
    """
    window = connected_firmware_window
    pending_workers.clear()
    error = FirmwareUploadCancelledError("cancelled") if cancelled else RuntimeError("upload failed")

    def upload(callbacks: FirmwareUploadCallbacks) -> BootloaderInfo:
        assert callbacks.status_callback is not None
        assert callbacks.progress_callback is not None
        callbacks.status_callback("Preparing")
        callbacks.progress_callback(UploadStage.IDENTIFYING, 1, 1)
        raise error

    window._start_upload("Example release", upload)
    pending_workers.pop(0)()

    assert window.uploading
    assert not window.restart_required
    assert window.events.get_nowait() == ("status", "Preparing")
    assert window.events.get_nowait() == ("progress", UploadStage.IDENTIFYING, 1, 1)
    result = window.events.get_nowait()
    assert result[0] == "error"
    assert result[1] is error
    with patch.object(firmware_upload, "messagebox"):
        window._handle_event(result)

    assert not window.uploading
    assert window.restart_required is not cancelled


def test_usb_removal_waits_for_window_close_before_exiting_amc(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
) -> None:
    """
    Losing a detected board waits for the user before AMC exits.

    GIVEN: A connected board.
    WHEN: Its USB serial port disappears.
    THEN: AMC is marked to exit, the Cancel button remains disabled, and the window stays open.
    """
    window = connected_firmware_window
    window.flight_controller.get_serial_ports.return_value = []
    window.root.after_cancel(window._connection_timer_id)

    window._monitor_connection()

    window.flight_controller.disconnect.assert_called_once_with()
    assert window.flight_controller.master is None
    assert window.restart_required
    assert window.root.winfo_exists()
    assert str(window.cancel_button.cget("state")) == "disabled"

    window.close()

    assert not window.root.winfo_exists()


@pytest.mark.parametrize("operation", ["uploading", "connecting"])
def test_usb_monitor_leaves_connection_alone_during_owned_operations(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow, operation: str
) -> None:
    """
    Connection monitoring does not interfere with bootloader or connection selection.

    GIVEN: The bootloader or connection selector owns the connection.
    WHEN: The USB monitor runs while the serial port is absent.
    THEN: It does not disconnect the board or interrupt the operation.
    """
    window = connected_firmware_window
    setattr(window, operation, True)
    window.flight_controller.get_serial_ports.return_value = []
    window.root.after_cancel(window._connection_timer_id)

    window._monitor_connection()

    window.flight_controller.get_serial_ports.assert_not_called()
    window.flight_controller.disconnect.assert_not_called()
    assert window.board_id == 9
    assert window._connection_timer_id is not None


def test_usb_monitor_preserves_catalog_while_board_remains_connected(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
) -> None:
    """
    A present USB board retains its ongoing catalog request.

    GIVEN: A connected board whose catalog is downloading.
    WHEN: A periodic serial-port check finds the board.
    THEN: It neither restarts the catalog download nor releases the connection.
    """
    window = connected_firmware_window
    request_id = window.catalog_request_id
    window.root.after_cancel(window._connection_timer_id)

    window._monitor_connection()

    assert window.catalog_request_id == request_id
    assert window.busy
    window.flight_controller.disconnect.assert_not_called()


def test_closing_firmware_window_cancels_usb_monitor(
    connected_firmware_window: firmware_upload.FirmwareUploadWindow,
) -> None:
    """
    Closing an embedded upload window cancels its connection monitor.

    GIVEN: An embedded firmware window with a pending USB check.
    WHEN: The user closes the window.
    THEN: The check is cancelled and the shared controller remains connected.
    """
    window = connected_firmware_window
    timer_id = window._connection_timer_id

    window.close()

    assert window._connection_timer_id is None
    assert timer_id not in window.root.tk.call("after", "info")
    window.flight_controller.disconnect.assert_not_called()
