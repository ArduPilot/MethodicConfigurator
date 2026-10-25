#!/usr/bin/env python3

"""
Transfer popup scheduling and background-worker integration tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import gc
from collections.abc import Callable, Iterator
from pathlib import Path
from threading import Event, current_thread
from tkinter import ttk
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
from ardupilot_methodic_configurator.backend_flightcontroller_protocols import FileUploadCheckStatus, FileUploadResult
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.data_model_transfer_progress import TransferDirection, TransferPhase, TransferProgress
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations import (
    LocalUploadPlan,
    RemoteDownloadPlan,
    _download_remote_plan_worker,
    _upload_local_plan_worker,
)
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow
from ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test import MotorTestView
from tests.plugins.test_frontend_tkinter_motor_test import DummyBaseWindow, FakeMotorTestModel


class ManualScheduler:
    """Run scheduled callbacks explicitly without waiting for wall-clock time."""

    def __init__(self) -> None:
        self.pending: dict[str, Callable[[], None]] = {}
        self.sequence = 0

    def schedule(self, _milliseconds: int, callback: Callable[[], None]) -> str:
        """Return an identifier compatible with Tk's after/after_cancel boundary."""
        self.sequence += 1
        identifier = f"timer-{self.sequence}"
        self.pending[identifier] = callback
        return identifier

    def cancel(self, identifier: str) -> None:
        """Forget a pending callback when the popup cancels it."""
        self.pending.pop(identifier, None)

    def tick(self) -> None:
        """Deliver one scheduled callback on the calling UI thread."""
        identifier = next(iter(self.pending))
        self.pending.pop(identifier)()


@pytest.fixture(name="download_popup")
def _download_popup(tk_root, monkeypatch) -> Iterator[tuple[ProgressWindow, list[float], ManualScheduler]]:
    """Create actual widgets with an injected clock and controlled refresh scheduler."""
    # Collect expired Tk fixtures on their owning thread before any worker can trigger GC.
    gc.collect()
    clock = [0.0]
    window = ProgressWindow(tk_root, "Downloading", clock=lambda: clock[0])
    scheduler = ManualScheduler()
    monkeypatch.setattr(window.progress_window, "after", scheduler.schedule)
    monkeypatch.setattr(window.progress_window, "after_cancel", scheduler.cancel)
    window.enable_transfer_progress()
    yield window, clock, scheduler
    window.destroy()


def test_user_sees_the_eta_refresh_while_no_more_bytes_arrive(download_popup) -> None:
    """Given a stalled download, a timer refreshes rate and ETA without another packet."""
    window, clock, scheduler = download_popup
    clock[0] = 2
    window.update_transfer_progress(TransferProgress(1024 * 1024, 4 * 1024 * 1024))
    assert "512.0 KiB/s · About 0:06 remaining" in window.progress_label.cget("text")
    clock[0] = 122
    scheduler.tick()
    assert "8.4 KiB/s · About 6:06 remaining" in window.progress_label.cget("text")
    assert len(scheduler.pending) == 1


@pytest.mark.parametrize("size", [0, 1024])
def test_user_sees_verification_independently_of_byte_totals(download_popup, size: int) -> None:
    """Given a verified download, show its phase even when all files are empty."""
    window, clock, scheduler = download_popup
    clock[0] = 2
    window.update_transfer_progress(TransferProgress(size, size, TransferPhase.VERIFYING))
    assert "Verifying downloaded files…" in window.progress_label.cget("text")
    assert str(window.progress_bar["mode"]) == "determinate"
    assert window.progress_bar["value"] == window.progress_bar["maximum"]
    assert window.progress_window.winfo_exists()
    assert not scheduler.pending


def test_user_does_not_see_verification_until_the_worker_announces_it(download_popup) -> None:
    """Given all bytes received but publication unfinished, keep the downloading phase."""
    window, clock, scheduler = download_popup
    clock[0] = 2
    window.update_transfer_progress(TransferProgress(1024, 1024))
    assert "Verifying" not in window.progress_label.cget("text")
    assert "Download complete" not in window.progress_label.cget("text")
    assert len(scheduler.pending) == 1


@pytest.mark.parametrize("external", [False, True])
def test_user_can_close_the_popup_without_leaving_a_refresh_callback(download_popup, external: bool) -> None:
    """Given a refreshing popup, both explicit and external destruction cancel its timer."""
    window, _clock, scheduler = download_popup
    (window.progress_window.destroy if external else window.destroy)()
    assert not scheduler.pending


def test_user_gets_only_one_timer_after_repeated_progress_updates(download_popup) -> None:
    """Given packet-rate updates, replace the pending refresh rather than accumulate timers."""
    window, _clock, scheduler = download_popup
    for received in range(20):
        window.update_transfer_progress(TransferProgress(received, 100))
    assert len(scheduler.pending) == 1
    window.update_transfer_progress(TransferProgress(100, 100, TransferPhase.FINISHED))
    assert "Download complete" in window.progress_label.cget("text")
    assert not scheduler.pending


def test_user_sees_unknown_size_then_determinate_progress_when_it_is_resolved(download_popup) -> None:
    """Given an unknown size, show rate without ETA until a known total arrives."""
    window, clock, _scheduler = download_popup
    clock[0] = 2
    window.update_transfer_progress(TransferProgress(2048, None))
    assert "1.0 KiB/s · Remaining time unknown" in window.progress_label.cget("text")
    assert str(window.progress_bar["mode"]) == "indeterminate"
    window.update_transfer_progress(TransferProgress(2048, 4096))
    assert "About 0:02 remaining" in window.progress_label.cget("text")
    assert str(window.progress_bar["mode"]) == "determinate"


def test_user_sees_animation_when_a_known_batch_total_becomes_unknown(download_popup) -> None:
    """An unresolved file size restores a visible animation after byte-count progress."""
    window, _clock, _scheduler = download_popup
    window.update_transfer_progress(TransferProgress(1024 * 1024, 4 * 1024 * 1024))
    window.update_transfer_progress(TransferProgress(1024 * 1024, None))
    assert str(window.progress_bar["mode"]) == "indeterminate"
    assert window.progress_bar["maximum"] == 100
    window.progress_bar.step(25)
    assert 0 < window.progress_bar["value"] < window.progress_bar["maximum"]
    window.update_transfer_progress(TransferProgress(1024 * 1024, 8 * 1024 * 1024))
    assert str(window.progress_bar["mode"]) == "determinate"
    assert window.progress_bar["maximum"] == 8 * 1024 * 1024
    assert window.progress_bar["value"] == 1024 * 1024


def test_user_sees_unknown_size_animation_continue_across_updates_and_refreshes(download_popup) -> None:
    """Given an unknown total, packet updates and estimate refreshes preserve the animation."""
    window, clock, scheduler = download_popup
    maximum = window.progress_bar["maximum"]
    assert maximum > 1
    window.progress_bar.step(17)
    value = window.progress_bar["value"]
    clock[0] = 2
    window.update_transfer_progress(TransferProgress(2048, None))
    assert window.progress_bar["maximum"] == maximum
    assert window.progress_bar["value"] == value
    assert "1.0 KiB/s" in window.progress_label.cget("text")
    clock[0] = 4
    scheduler.tick()
    assert window.progress_bar["maximum"] == maximum
    assert window.progress_bar["value"] == value
    assert "0.5 KiB/s" in window.progress_label.cget("text")


@pytest.mark.parametrize(("remaining_seconds", "duration"), [(61, "1:01"), (3600, "1:00:00")])
def test_user_sees_readable_remaining_minutes_and_hours(remaining_seconds: int, duration: str) -> None:
    """Given a numerical estimate, formatting needs no widgets or patched clock."""
    message = ProgressWindow._transfer_message(  # pylint: disable=protected-access
        TransferProgress(1024, 1024 * (remaining_seconds + 1)), 1
    )
    assert f"About {duration} remaining" in message


class ControlledDownload:
    """A transfer fake that pauses at download and verification boundaries."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.ui_thread = current_thread()
        self.bytes_ready = Event()
        self.allow_download = Event()
        self.crc_ready = Event()
        self.allow_crc = Event()

    def download(self, _remote: str, local: str, report: Callable[[int, int], None]) -> bool:
        """Write real local bytes and pause the worker before publication completes."""
        assert current_thread() is not self.ui_thread
        Path(local).write_bytes(b"x" * self.size)
        report(self.size, self.size)
        self.bytes_ready.set()
        assert self.allow_download.wait(2)
        return True

    def verify(self, _remote: str, _local: str) -> bool:
        """Keep verification in flight until the GUI has rendered its phase."""
        assert current_thread() is not self.ui_thread
        self.crc_ready.set()
        assert self.allow_crc.wait(2)
        return True

    def release(self) -> None:
        """Unblock the worker even if a test assertion fails."""
        self.allow_download.set()
        self.allow_crc.set()


@pytest.mark.parametrize("direction", list(TransferDirection))
@pytest.mark.parametrize("empty", [False, True])
def test_background_transfer_and_verification_update_the_real_popup_only_on_tk(
    download_popup, tmp_path: Path, empty: bool, direction: TransferDirection
) -> None:
    """Given a real worker and popup, render snapshots on Tk and close only after verification."""
    window, clock, scheduler = download_popup
    runner = BackgroundTaskRunner(MagicMock())
    controlled = ControlledDownload(0 if empty else 1024)
    deliveries: list[TransferProgress] = []
    entry = FlightControllerLogFile("log.bin", "/log.bin", controlled.size)
    done = MagicMock(side_effect=lambda _result, _error: window.destroy())

    def task(report: Callable[[TransferProgress], None]) -> object:
        if direction is TransferDirection.UPLOAD:
            return _upload_local_plan_worker(
                LocalUploadPlan((), ((tmp_path / entry.name, entry.remote_path, controlled.size),)),
                MagicMock(),
                lambda local, remote, callback: controlled.download(remote, local, callback),
                report,
                verify_remote_file=controlled.verify,
            )
        return _download_remote_plan_worker(
            RemoteDownloadPlan((), ((entry, tmp_path / entry.name),)),
            tmp_path,
            controlled.download,
            report,
            verify_remote_file=controlled.verify,
        )

    def render(progress: TransferProgress) -> None:
        assert current_thread() is controlled.ui_thread
        deliveries.append(progress)
        window.update_transfer_progress(progress)

    try:
        assert runner.start(task, render, done)
        assert controlled.bytes_ready.wait(2)
        clock[0] = 2
        runner.poll()
        assert deliveries[-1].phase is TransferPhase.TRANSFERRING
        controlled.allow_download.set()
        assert controlled.crc_ready.wait(2)
        runner.poll()
        assert deliveries[-1] == TransferProgress(controlled.size, controlled.size, TransferPhase.VERIFYING, direction)
        expected = "Verifying uploaded files…" if direction is TransferDirection.UPLOAD else "Verifying downloaded files…"
        assert expected in window.progress_label.cget("text")
        assert window.progress_window.winfo_exists()
        assert not scheduler.pending
        done.assert_not_called()
        controlled.allow_crc.set()
        assert runner.thread is not None
        runner.thread.join(2)
        assert not runner.thread.is_alive()
        runner.poll()
        assert deliveries[-1] == TransferProgress(controlled.size, controlled.size, TransferPhase.FINISHED, direction)
        assert done.call_args.args[1] is None
        assert done.call_args.args[0].verification == {entry.remote_path: True}
        assert done.call_args.args[0].files_succeeded == [entry.remote_path]
        assert not done.call_args.args[0].files_failed
        assert not done.call_args.args[0].other_failed
        assert not window.progress_window.winfo_exists()
        assert not scheduler.pending
    finally:
        controlled.release()
        if runner.thread is not None:
            runner.thread.join(2)


@pytest.mark.parametrize("direction", list(TransferDirection))
def test_user_sees_direction_and_estimates_during_a_stalled_transfer(download_popup, direction: TransferDirection) -> None:
    """Given either transfer direction, report bytes, average rate, and a live ETA."""
    window, clock, scheduler = download_popup
    window.enable_transfer_progress(direction)
    clock[0] = 2
    window.update_transfer_progress(TransferProgress(1024 * 1024, 4 * 1024 * 1024, direction=direction))
    verb = "Uploaded" if direction is TransferDirection.UPLOAD else "Downloaded"
    assert f"{verb} 1.0 of 4.0 MiB" in window.progress_label.cget("text")
    assert "512.0 KiB/s · About 0:06 remaining" in window.progress_label.cget("text")
    clock[0] = 122
    scheduler.tick()
    assert "8.4 KiB/s · About 6:06 remaining" in window.progress_label.cget("text")


def _observe_configured_upload(editor, clock, events, observations) -> None:
    """Observe real Tk timer delivery while the transfer thread waits for permission."""
    try:
        popup = editor.file_upload_progress_window
        # Centering the popup can deliver timers before construction finishes.
        # Keep observing until transport starts, but stop after upload cleanup.
        if popup is None:
            if not events.started.is_set():
                editor.root.after(10, _observe_configured_upload, editor, clock, events, observations)
            return
        assert editor.navigation_lock.locked
        assert observations["button"].instate(("disabled",))
        if events.started.is_set() and "started" not in observations:
            assert popup.progress_bar["value"] == 0
            observations["started"] = True
            clock[0] = 10
            events.first_ack.set()
        elif "started" in observations and "initial_rate" not in observations and popup.progress_bar["value"] == 1024:
            observations["initial_rate"] = popup.progress_label.cget("text")
            assert "0.1 KiB/s · About 0:30 remaining" in observations["initial_rate"]
            clock[0] = 122
        elif "initial_rate" in observations and "6:06 remaining" in popup.progress_label.cget("text"):
            observations["stalled_rate"] = popup.progress_label.cget("text")
            events.finish.set()
            return
        editor.root.after(10, _observe_configured_upload, editor, clock, events, observations)
    except Exception as error:  # pylint: disable=broad-exception-caught
        observations["error"] = error
        events.first_ack.set()
        events.finish.set()


def _configured_upload_editor(root, tmp_path: Path, mode: str) -> tuple[ParameterEditorWindow, dict[str, Any]]:
    """Use the real editor workflow, runner, lock, and widgets with a controlled transport."""
    # Collect expired Tk fixtures on their owning thread before any worker can trigger GC.
    gc.collect()
    clock = [0.0]
    events = SimpleNamespace(started=Event(), first_ack=Event(), finish=Event())
    observations = {"ui_thread": current_thread(), "remote": b"", "errors": [], "retries": []}
    source = tmp_path / "script.lua"
    source.write_bytes(b"x" * 4096)
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor._connection_recovery = None  # pylint: disable=protected-access
    editor.root = root
    editor.navigation_lock = NavigationLock()
    editor.file_upload_progress_window = None
    editor.current_plugin_view = None
    editor._configured_upload_active = False  # pylint: disable=protected-access
    editor._close_after_configured_upload = False  # pylint: disable=protected-access
    editor._close_pending = False  # pylint: disable=protected-access
    observations["button"] = ttk.Button(root, text="Next")
    editor.navigation_lock.register(observations["button"])

    def transport(local: str, remote: str, report: Callable[[int, int], None]) -> FileUploadResult:
        assert current_thread() is not observations["ui_thread"]
        assert remote == "/script.lua"
        events.started.set()
        assert events.first_ack.wait(3)
        report(1024, 4096)
        assert events.finish.wait(3)
        if mode == "exception":
            message = "link failed"
            raise RuntimeError(message)
        if mode == "failure":
            return FileUploadResult.UPLOAD_FAILED
        observations["remote"] = Path(local).read_bytes()
        report(4096, 4096)
        return FileUploadResult.UPLOADED

    def create_popup(parent, title, message, **_options) -> ProgressWindow:
        assert current_thread() is observations["ui_thread"]
        # Exercise observation before popup assignment without pumping Tk events.
        _observe_configured_upload(editor, clock, events, observations)
        popup = ProgressWindow(parent, title, message, clock=lambda: clock[0])
        observations["popup"] = popup
        return popup

    def show_error(title: str, message: str) -> None:
        assert current_thread() is observations["ui_thread"]
        observations["errors"].append((title, message))

    def decline_retry(_title: str, _message: str) -> bool:
        assert not editor.navigation_lock.locked
        assert not observations["popup"].progress_window.winfo_exists()
        observations["retries"].append(True)
        return False

    filesystem = SimpleNamespace(
        vehicle_configuration_file_size=lambda local: Path(local).stat().st_size,
        get_upload_files=lambda _step: [(str(source), "/script.lua")],
        get_download_files=lambda _step: [],
        get_eval_variables=dict,
    )
    controller = SimpleNamespace(
        master=object(),
        check_file_upload=lambda _remote, _local: FileUploadCheckStatus.NEEDS_UPLOAD,
        upload_file_if_needed=transport,
    )
    editor.parameter_editor = ParameterEditor("step.param", controller, filesystem)
    editor.ui = SimpleNamespace(
        create_progress_window=create_popup,
        ask_yesno=lambda *_args: current_thread() is observations["ui_thread"],
        show_error=show_error,
        show_warning=show_error,
        ask_retry_cancel=decline_retry,
    )
    return editor, observations


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_user_gets_live_configured_upload_estimates_and_safe_cleanup(root, tmp_path: Path, mode: str) -> None:
    """
    Keep configured-upload estimates accurate and responsive through completion or failure.

    GIVEN: A configured file and a transport that pauses before its first ACK and during transfer.
    WHEN: The real configured-upload workflow runs while Tk services its timers.
    THEN: Estimates include initial delay, refresh during stalls, and release controls and widgets on every outcome.
    """
    # Share the session root across outcomes: Python 3.14 on Windows can fail
    # to initialize Tcl when repeatedly creating and destroying interpreters.
    editor, observations = _configured_upload_editor(root, tmp_path, mode)
    result = editor._should_upload_file_to_fc("step.param")  # pylint: disable=protected-access
    assert "error" not in observations, observations.get("error")
    assert "6:06 remaining" in observations["stalled_rate"]
    assert result is (mode == "success")
    assert observations["remote"] == (b"x" * 4096 if mode == "success" else b"")
    assert bool(observations["errors"]) is (mode != "success")
    assert observations["retries"] == ([] if mode == "success" else [True])
    assert not editor.navigation_lock.locked
    assert not observations["button"].instate(("disabled",))
    assert editor.file_upload_progress_window is None
    assert not observations["popup"].progress_window.winfo_exists()
    assert observations["popup"]._transfer_refresh_id is None  # pylint: disable=protected-access
    observations["button"].destroy()


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
def test_configured_upload_honors_close_after_transport(root, monkeypatch, mode: str) -> None:
    """
    Closing waits for transport completion, failure, or an exception.

    GIVEN: A step transition has removed the outgoing plugin and started an upload.
    WHEN: The user closes the editor while transport is running.
    THEN: Saving and quitting wait until the worker finishes and releases navigation.
    """
    gc.collect()
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor._connection_recovery = None  # pylint: disable=protected-access
    editor.root = root
    editor.navigation_lock = NavigationLock()
    editor.file_upload_progress_window = None
    editor._configured_upload_active = False  # pylint: disable=protected-access
    editor._close_after_configured_upload = False  # pylint: disable=protected-access
    editor._close_pending = False  # pylint: disable=protected-access
    editor.current_plugin_view = None
    save = MagicMock()
    quit_application = MagicMock()
    monkeypatch.setattr(editor, "_commit_focused_edit_and_offer_save", save)
    monkeypatch.setattr(root, "quit", quit_application)

    def report(_current: int, _total: int) -> None:
        editor.close_connection_and_quit()
        editor.close_connection_and_quit()
        quit_application.assert_not_called()
        save.assert_not_called()

    def task(_report: Callable[[int, int], None]) -> FileUploadResult:
        quit_application.assert_not_called()
        if mode == "exception":
            message = "link failed"
            raise RuntimeError(message)
        return FileUploadResult.UPLOADED if mode == "success" else FileUploadResult.UPLOAD_FAILED

    if mode == "exception":
        with pytest.raises(RuntimeError, match="link failed"):
            editor._run_configured_file_upload(task, 1024, report)  # pylint: disable=protected-access
    else:
        result = editor._run_configured_file_upload(task, 1024, report)  # pylint: disable=protected-access
        assert result is (FileUploadResult.UPLOADED if mode == "success" else FileUploadResult.UPLOAD_FAILED)
    assert not editor.navigation_lock.locked
    assert not editor._configured_upload_active  # pylint: disable=protected-access
    root.update_idletasks()
    save.assert_called_once_with()
    quit_application.assert_called_once_with()


@pytest.fixture(name="outgoing_motor_upload")
def _outgoing_motor_upload(root, monkeypatch) -> Iterator[SimpleNamespace]:
    """Start a step transition with real motor widgets and a configured-upload popup."""
    gc.collect()
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor._connection_recovery = None  # pylint: disable=protected-access
    editor.root = root
    host = DummyBaseWindow(root)
    editor.navigation_lock = NavigationLock()
    editor.gui_complexity = "normal"
    editor.dpi_scaling_factor = 1.0
    editor.current_plugin = {"name": "motor_test", "placement": "top"}
    editor.parameter_area_paned = None
    editor.parameter_editor = MagicMock(spec=ParameterEditor)
    editor.parameter_editor.current_file = "motors.param"
    editor.parameter_editor.get_plugin.return_value = editor.current_plugin
    editor.parameter_editor.get_instructions_popup.return_value = None
    editor.file_selection_combobox = ttk.Combobox(root, values=("motors.param", "next.param"))
    editor.file_selection_combobox.set("next.param")
    editor.documentation_frame = MagicMock()
    editor.ui = MagicMock()
    for method in (
        "write_changes_to_intermediate_parameter_file",
        "_update_progress_bar_from_file",
        "repopulate_parameter_table",
        "_update_skip_button_state",
        "_update_previous_button_state",
        "_update_inline_component_editor",
    ):
        monkeypatch.setattr(editor, method, MagicMock())
    editor.file_upload_progress_window = None
    editor._configured_upload_active = False  # pylint: disable=protected-access
    editor._close_after_configured_upload = False  # pylint: disable=protected-access
    editor._close_pending = False  # pylint: disable=protected-access
    model = FakeMotorTestModel()
    parent = ttk.Frame(root)
    editor.parameter_area_container = parent
    top_container = ttk.Frame(parent)
    plugin_parent = ttk.Frame(top_container)
    view = MotorTestView(plugin_parent, model, host)
    editor.current_plugin_view = view

    def load_plugin(container, _plugin) -> None:
        editor.current_plugin_view = MotorTestView(container, model, host)

    monkeypatch.setattr(editor, "_load_plugin", load_plugin)
    # Ready-label timers are unrelated to link ownership and would outlive this view.
    monkeypatch.setattr(MotorTestView, "_schedule_ready_reset", lambda *_args: None)
    monkeypatch.setattr("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.askyesno", lambda *_args: True)
    popup = ProgressWindow(root, "Uploading file", "Uploaded {} of {} bytes")
    popup.enable_transfer_progress(TransferDirection.UPLOAD)
    editor.file_upload_progress_window = popup
    yield SimpleNamespace(editor=editor, view=view, model=model, popup=popup)
    if editor.current_plugin_view is not None:
        editor.current_plugin_view.destroy()
    if view.winfo_exists():
        view.destroy()
    editor.file_selection_combobox.destroy()
    parent.destroy()
    popup.destroy()


@pytest.mark.parametrize("mode", ["success", "failure", "exception"])
@pytest.mark.parametrize("same_plugin", [True, False], ids=["same-plugin", "different-plugin"])
def test_outgoing_motor_buttons_and_shortcuts_cannot_interrupt_configured_upload(  # noqa: PLR0915 # pylint: disable=too-many-locals,too-many-statements
    outgoing_motor_upload: SimpleNamespace, mode: str, same_plugin: bool
) -> None:
    """
    Outgoing motor actions leave the link exclusive while the modal upload wait processes events.

    GIVEN: A motor plugin is active when the user selects another configuration step.
    WHEN: The step workflow uploads a file while Tk dispatches events.
    THEN: The outgoing controls, shortcuts and timer are gone before transport starts,
    an inline edit cannot load a plugin, and the resulting step gets a working replacement.
    """
    editor, view, model, popup = (
        outgoing_motor_upload.editor,
        outgoing_motor_upload.view,
        outgoing_motor_upload.model,
        outgoing_motor_upload.popup,
    )
    root = editor.root
    if not same_plugin:
        editor.parameter_editor.get_plugin.return_value = {"name": "custom_motor_test", "placement": "top"}
    editor._updating_inline_editor = False  # pylint: disable=protected-access
    editor.inline_component_editor = MagicMock()
    editor.inline_component_editor.get_component_data.return_value = {"Components": {"Battery": {}}}
    started, finish = Event(), Event()
    observations: dict[str, Any] = {}
    ui_thread = current_thread()
    bindings = list(view._keyboard_bindings)  # pylint: disable=protected-access

    def interact() -> None:
        if not started.is_set():
            root.after(10, interact)
            return
        try:
            observations["locked"] = editor.navigation_lock.locked
            # Focus-out/Return from the previous step's inline editor can run inside wait_variable.
            editor._on_component_data_changed()  # pylint: disable=protected-access
            observations["plugin_stays_inactive"] = editor.current_plugin_view is None
            editor.parameter_editor.update_vehicle_components.assert_called_once_with({"Battery": {}})
            observations["deactivation_stops"] = model.stop_calls
            observations["outgoing_exists"] = bool(view.winfo_exists())
            observations["timer_cancelled"] = view._timer_id is None  # pylint: disable=protected-access
            observations["shortcuts_removed"] = all(
                not root.tk.call("info", "commands", binding_id) for _sequence, binding_id in bindings
            )
            observations["single"] = list(model.single_motor_calls)
            observations["all"] = model.all_motor_runs
            observations["sequence"] = model.sequence_runs
            observations["emergency"] = model.emergency_runs
        except Exception as error:  # pylint: disable=broad-exception-caught
            observations["error"] = error
        finally:
            finish.set()

    def task(_report: Callable[[int, int], None]) -> FileUploadResult:
        assert current_thread() is not ui_thread
        started.set()
        assert finish.wait(3)
        if mode == "exception":
            message = "link failed"
            raise RuntimeError(message)
        return FileUploadResult.UPLOADED if mode == "success" else FileUploadResult.UPLOAD_FAILED

    def report(current: int, total: int) -> None:
        popup.update_transfer_progress(TransferProgress(current, total, direction=TransferDirection.UPLOAD))

    def change_step(selected_file: str, *_args, **_kwargs) -> tuple[str, bool]:
        observations["removed_before_workflow"] = editor.current_plugin_view is None
        editor.parameter_editor.current_file = selected_file
        result = editor._run_configured_file_upload(task, 1024, report)  # pylint: disable=protected-access
        assert result is (FileUploadResult.UPLOADED if mode == "success" else FileUploadResult.UPLOAD_FAILED)
        return selected_file, True

    editor.parameter_editor.handle_param_file_change_workflow.side_effect = change_step
    root.after(0, interact)
    try:
        if mode == "exception":
            with pytest.raises(RuntimeError, match="link failed"):
                editor.on_param_file_combobox_change(None)
        else:
            editor.on_param_file_combobox_change(None)
        assert "error" not in observations, observations.get("error")
        assert observations == {
            "locked": True,
            "plugin_stays_inactive": True,
            "deactivation_stops": 1,
            "removed_before_workflow": True,
            "outgoing_exists": False,
            "timer_cancelled": True,
            "shortcuts_removed": True,
            "single": [],
            "all": 0,
            "sequence": 0,
            "emergency": 0,
        }
        assert not editor.navigation_lock.locked
        assert not popup.progress_window.winfo_exists()
        assert editor.current_plugin_view is not view
        editor.current_plugin_view.motor_buttons[0].invoke()
        assert model.single_motor_calls == [(0, 1)]
    finally:
        finish.set()
