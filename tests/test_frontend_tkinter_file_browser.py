#!/usr/bin/env python3

"""
Window behavior for the two-panel MAVFTP/local-file browser.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import sys
import time
import tkinter as tk
import typing
from pathlib import Path
from threading import Event, Thread, current_thread
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile, LastLogDownloadResult
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_file_browser import FileBrowserWindow
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations import (
    LocalFileEntry,
    RemoteDownloadPlan,
    RemoteDownloadPreflight,
    _local_target_conflicts,
)
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow

# pylint: disable=too-many-lines, too-few-public-methods, too-many-public-methods, protected-access


def _run_tk_until(tk_root: tk.Tk, condition: typing.Callable[[], bool]) -> None:
    """Process Tk events until a predicate succeeds or the operation times out."""
    deadline = time.monotonic() + 2
    while not condition() and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(0.01)


def _join_worker(thread: Thread | None) -> None:
    """Join a worker thread when one is still active during test cleanup."""
    if thread is not None:
        thread.join(timeout=2)


class ImmediateTaskRunner:
    """Run browser work without Tk in unit tests; model the completion boundary."""

    active = False

    def start(self, task, on_progress, on_done) -> bool:
        """Deliver a result or failure and permit follow-up work from completion."""
        if self.active:
            return False
        self.active = True
        try:
            result, error = task(on_progress or (lambda _current, _total: None)), None
        except Exception as exception:  # pylint: disable=broad-exception-caught
            result, error = None, exception
        self.active = False
        on_done(result, error)
        return True


def _bare_window() -> FileBrowserWindow:
    """Create a Tk-independent window with an explicitly injected task runner."""
    window = FileBrowserWindow.__new__(FileBrowserWindow)
    window._task_runner = ImmediateTaskRunner()
    window.verify_transfers_var = MagicMock()
    window.verify_transfers_var.get.return_value = False
    return window


class TestFileBrowserWindow:
    """Verify browser interactions, lifecycle, and backend dispatch."""

    def test_constructor_accepts_an_injected_task_runner(self, tk_root: tk.Tk) -> None:
        """Tests can provide a runner without mutating the constructed window."""
        runner = ImmediateTaskRunner()
        parameter_editor = MagicMock()
        parameter_editor.get_vehicle_directory.return_value = str(Path.cwd())
        window = FileBrowserWindow(tk_root, parameter_editor, MagicMock(), task_runner=runner)
        try:
            assert window._task_runner is runner
            assert not window.verify_transfers_var.get()
            assert window.verify_checkbox.winfo_exists()
        finally:
            with contextlib.suppress(tk.TclError):
                window.root.grab_release()
                window.root.destroy()

    def test_initial_refresh_populates_local_panel_before_starting_remote_task(self) -> None:
        """The local panel is populated before remote work locks the browser."""
        window = _bare_window()
        window.refresh_local_panel = MagicMock()
        window.refresh_remote_panel = MagicMock()
        calls = MagicMock()
        calls.attach_mock(window.refresh_local_panel, "refresh_local")
        calls.attach_mock(window.refresh_remote_panel, "refresh_remote")

        window._refresh_initial_panels()

        assert calls.mock_calls == [
            call.refresh_local(),
            call.refresh_remote(("/APM/", "/")),
        ]

    def test_action_layout_and_help_link(self, tk_root: tk.Tk) -> None:
        """Primary transfers precede secondary controls; Help opens the MAVFTP guide."""
        parameter_editor = MagicMock()
        parameter_editor.get_vehicle_directory.return_value = str(Path.cwd())
        window = FileBrowserWindow(tk_root, parameter_editor, MagicMock(), task_runner=ImmediateTaskRunner())
        try:
            assert window.root.title() == "Flight-controller files"
            for widget, row, column, span in (
                (window.download_button, 0, 0, 2),
                (window.upload_button, 0, 2, 2),
                (window.verify_checkbox, 1, 0, 1),
                (window.last_log_button, 1, 1, 1),
                (window.help_button, 1, 2, 1),
                (window.close_button, 1, 3, 1),
            ):
                grid = widget.grid_info()
                assert (grid["row"], grid["column"], grid["columnspan"]) == (row, column, span)
            with patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.webbrowser_open_url") as open_url:
                window.help_button.invoke()
            open_url.assert_called_once_with("https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_MAVFTP.html")
        finally:
            with contextlib.suppress(tk.TclError):
                window.root.grab_release()
                window.root.destroy()

    def test_local_panel_defaults_to_current_vehicle_directory(self) -> None:
        """The local browser starts in the vehicle directory used by the editor."""
        parameter_editor = MagicMock()
        parameter_editor.get_vehicle_directory.return_value = str(Path.cwd())

        assert FileBrowserWindow._default_local_directory(parameter_editor) == str(Path.cwd())

    def test_remote_mtime_missing_from_older_firmware_is_shown_as_unsupported(self) -> None:
        """Remote entries without MAVFTP timestamps are marked as unsupported."""
        assert FileBrowserWindow._format_modified_time(None, unsupported_when_missing=True) == "Unsupported"

    @pytest.mark.parametrize(
        ("panel", "modified_text"),
        [("remote", "Unsupported"), ("local", "")],
    )
    def test_populating_one_panel_resets_only_its_tree_and_sort(self, panel: str, modified_text: str) -> None:
        """The paired panels share row rendering but retain distinct timestamp and selection rules."""
        window = _bare_window()
        window.remote_entries = [FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)]
        window.local_entries = [LocalFileEntry("log.bin", Path("log.bin"), 12)]
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window.remote_empty_state_label = MagicMock()
        window.local_empty_state_label = MagicMock()
        window._update_transfer_buttons = MagicMock()
        window.last_selected_items = {"remote": "old-remote", "local": "old-local"}
        window.remote_sort_column = "size"
        window.local_sort_column = "size"
        window.remote_sort_reverse = True
        window.local_sort_reverse = True
        tree = window.remote_tree if panel == "remote" else window.local_tree
        other_tree = window.local_tree if panel == "remote" else window.remote_tree
        tree.get_children.return_value = ("old-row",)

        if panel == "remote":
            window._populate_remote_tree()
        else:
            window._populate_local_tree()

        tree.delete.assert_called_once_with("old-row")
        assert tree.insert.call_args.kwargs["values"] == ("log.bin", "File", "12 B", modified_text)
        other_tree.insert.assert_not_called()
        assert window.last_selected_items[panel] is None
        other_panel = "local" if panel == "remote" else "remote"
        assert window.last_selected_items[other_panel] == f"old-{other_panel}"
        assert getattr(window, f"{panel}_sort_column") == ""
        assert getattr(window, f"{panel}_sort_reverse") is False
        assert getattr(window, f"{other_panel}_sort_column") == "size"
        assert getattr(window, f"{other_panel}_sort_reverse") is True
        window._update_transfer_buttons.assert_called_once_with()

    def test_initial_remote_listing_falls_back_from_missing_log_directory(self) -> None:
        """Startup falls back to /APM when the default log directory is absent."""
        window = _bare_window()
        current_directory = "/APM/LOGS/"
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.side_effect = lambda: current_directory

        def set_directory(directory: str) -> None:
            nonlocal current_directory
            current_directory = directory

        window.remote_directory_var.set.side_effect = set_directory
        window.parameter_editor = MagicMock()
        window.parameter_editor.get_remote_files.side_effect = [FileNotFoundError("/APM/LOGS/"), []]
        window.remote_directory_label = MagicMock()
        window._populate_remote_tree = MagicMock()
        window._update_parent_navigation_buttons = MagicMock()
        window.ui = MagicMock()
        window.refresh_remote_panel(("/APM/", "/"))

        assert window.parameter_editor.get_remote_files.call_args_list == [
            call("/APM/LOGS/"),
            call("/APM/"),
        ]
        window.remote_directory_var.set.assert_called_once_with("/APM/")
        assert window.remote_entries == []
        window.ui.show_error.assert_not_called()

    def test_operation_controls_use_ttk_state_flags(self) -> None:
        """Treeviews use ttk state flags instead of an unsupported `state` option."""
        window = _bare_window()
        controls = {
            "remote_directory_entry": MagicMock(),
            "remote_parent_button": MagicMock(),
            "remote_tree": MagicMock(),
            "local_directory_entry": MagicMock(),
            "local_parent_button": MagicMock(),
            "local_tree": MagicMock(),
            "download_button": MagicMock(),
            "upload_button": MagicMock(),
            "last_log_button": MagicMock(),
        }
        for name, control in controls.items():
            setattr(window, name, control)

        window._set_operation_controls_state("disabled")

        for control in controls.values():
            control.state.assert_called_once_with(["disabled"])
            control.configure.assert_not_called()

    def test_last_log_without_logs_does_not_report_disconnected_fc(self) -> None:
        """A live MAVFTP link need not have downloaded parameters or flight logs."""
        window = _bare_window()
        window._controls_locked = MagicMock(return_value=False)
        window.parameter_editor = MagicMock()
        window.parameter_editor.is_fc_connected = False
        window.parameter_editor.is_fc_link_connected = True
        window.parameter_editor.is_mavftp_supported = True
        window.parameter_editor.download_last_flight_log.return_value = LastLogDownloadResult.NO_LOGS
        window.ui = MagicMock()
        window.ui.asksaveasfilename.return_value = "last.BIN"
        window._show_summary = MagicMock()
        window.refresh_local_panel = MagicMock()

        def run_operation(_title, _message, worker, completion) -> None:
            completion(*worker(lambda _current, _total: None))

        window._start_background_operation = MagicMock(side_effect=run_operation)

        window.download_last_flight_log()

        window.ui.show_error.assert_called_once_with(
            "Download error",
            "No flight logs found on the flight controller.",
        )
        window.parameter_editor.download_last_flight_log.assert_called_once()
        window._show_summary.assert_not_called()

    def test_last_log_transfer_failure_does_not_claim_empty_controller(self) -> None:
        """A failed transfer is reported differently from a confirmed empty log listing."""
        window = _bare_window()
        window._controls_locked = MagicMock(return_value=False)
        window.parameter_editor = MagicMock()
        window.parameter_editor.is_fc_link_connected = True
        window.parameter_editor.is_mavftp_supported = True
        window.parameter_editor.download_last_flight_log.return_value = LastLogDownloadResult.FAILED
        window.ui = MagicMock()
        window.ui.asksaveasfilename.return_value = "last.BIN"
        window._start_background_operation = MagicMock(
            side_effect=lambda _title, _message, worker, completion: completion(*worker(lambda _current, _total: None))
        )

        window.download_last_flight_log()

        window.ui.show_error.assert_called_once_with(
            "Download error", "Could not download the flight log; check the console for details."
        )

    def test_fc_link_connection_does_not_require_downloaded_parameters(self) -> None:
        """The file browser can operate before parameter download completes."""
        editor = ParameterEditor.__new__(ParameterEditor)
        editor._flight_controller = MagicMock(master=object(), fc_parameters={})

        assert not editor.is_fc_connected
        assert editor.is_fc_link_connected
        editor._flight_controller.master = None
        assert not editor.is_fc_link_connected

    def test_parameter_editor_preserves_last_log_outcome(self) -> None:
        """The model forwards the outcome rather than reducing it to a bool."""
        editor = ParameterEditor.__new__(ParameterEditor)
        editor._flight_controller = MagicMock()
        editor._flight_controller.download_last_flight_log.return_value = LastLogDownloadResult.NO_LOGS

        assert editor.download_last_flight_log("last.BIN") is LastLogDownloadResult.NO_LOGS
        editor._flight_controller.download_last_flight_log.assert_called_once_with("last.BIN", None)

    def test_last_log_without_fc_still_reports_disconnected(self) -> None:
        """An absent MAVLink connection is rejected before the save dialog."""
        window = _bare_window()
        window._controls_locked = MagicMock(return_value=False)
        window.parameter_editor = MagicMock()
        window.parameter_editor.is_fc_link_connected = False
        window.ui = MagicMock()

        window.download_last_flight_log()

        window.ui.show_error.assert_called_once_with("Error", "No flight controller connected")
        window.ui.asksaveasfilename.assert_not_called()

    def test_last_log_without_mavftp_stops_before_save_dialog(self) -> None:
        """The browser owns the unsupported-MAVFTP guard formerly in the model workflow."""
        window = _bare_window()
        window._controls_locked = MagicMock(return_value=False)
        window.parameter_editor = MagicMock()
        window.parameter_editor.is_fc_link_connected = True
        window.parameter_editor.is_mavftp_supported = False
        window.ui = MagicMock()

        window.download_last_flight_log()

        window.ui.show_error.assert_called_once_with("Error", "MAVFTP is not supported by the flight controller")
        window.ui.asksaveasfilename.assert_not_called()
        window.parameter_editor.download_last_flight_log.assert_not_called()

    def test_last_log_cancelled_save_dialog_does_not_download(self) -> None:
        """Cancellation remains silent in the one supported UI flow."""
        window = _bare_window()
        window._controls_locked = MagicMock(return_value=False)
        window.parameter_editor = MagicMock()
        window.parameter_editor.is_fc_link_connected = True
        window.parameter_editor.is_mavftp_supported = True
        window.ui = MagicMock()
        window.ui.asksaveasfilename.return_value = ""

        window.download_last_flight_log()

        window.parameter_editor.download_last_flight_log.assert_not_called()
        window.ui.show_error.assert_not_called()
        window.ui.show_info.assert_not_called()

    def test_last_log_success_still_shows_summary_and_refreshes(self) -> None:
        """A successful last-log transfer retains the normal completion UI."""
        window = _bare_window()
        window._controls_locked = MagicMock(return_value=False)
        window.parameter_editor = MagicMock()
        window.parameter_editor.is_fc_link_connected = True
        window.parameter_editor.is_mavftp_supported = True
        window.parameter_editor.download_last_flight_log.return_value = LastLogDownloadResult.SUCCESS
        window.ui = MagicMock()
        window.ui.asksaveasfilename.return_value = "last.BIN"
        window._show_summary = MagicMock()
        window.refresh_local_panel = MagicMock()

        def run_operation(_title, _message, worker, completion) -> None:
            completion(*worker(lambda _current, _total: None))

        window._start_background_operation = MagicMock(side_effect=run_operation)

        window.download_last_flight_log()

        window.ui.show_error.assert_not_called()
        window._show_summary.assert_called_once_with("Download summary", ["last.BIN"], [])
        window.refresh_local_panel.assert_called_once_with()

    def test_remote_listing_uses_worker_thread_and_tk_polling(self) -> None:
        """Remote listing results are applied by the Tk polling seam."""

        class FakeMisc:  # pylint: disable=too-few-public-methods
            """Minimal Tk root substitute for the worker-thread test."""

            def __init__(self) -> None:
                self.after = MagicMock()

        window = _bare_window()
        window.root = FakeMisc()
        window._task_runner = BackgroundTaskRunner(window.root.after)
        window.close_button = MagicMock()
        completion = MagicMock()

        assert window._start_remote_task(lambda: "result", completion)
        window.close_button.configure.assert_called_with(state="disabled")
        assert window._task_runner.thread is not None
        window._task_runner.thread.join(timeout=2)
        window._task_runner.poll()

        completion.assert_called_once_with("result", None)
        window.close_button.configure.assert_called_with(state="normal")

    def test_rejected_remote_task_restores_controls(self) -> None:
        """A runner that cannot start a task must not leave the browser locked."""
        window = _bare_window()
        window._task_runner = MagicMock(active=False)
        window._task_runner.start.return_value = False
        window.close_button = MagicMock()
        window._set_remote_controls_state = MagicMock()
        completion = MagicMock()

        assert not window._start_remote_task(lambda: None, completion)

        assert window._set_remote_controls_state.call_args_list == [call("disabled"), call("normal")]
        assert window.close_button.configure.call_args_list == [call(state="disabled"), call(state="normal")]
        completion.assert_not_called()

    def test_real_tk_window_builds_widgets_and_polls_worker_threads(self, tk_root: tk.Tk) -> None:
        """The production constructor uses worker threads without touching Tk off-thread."""
        listing_started = Event()
        release_listing = Event()
        parameter_editor = MagicMock()
        parameter_editor.get_vehicle_directory.return_value = str(Path.cwd() / "tests")

        def get_remote_files(_directory: str) -> list[FlightControllerLogFile]:
            listing_started.set()
            assert release_listing.wait(timeout=2)
            return []

        parameter_editor.get_remote_files.side_effect = get_remote_files
        ui = MagicMock()
        progress_window = MagicMock()
        ui.create_progress_window.return_value = progress_window
        window = FileBrowserWindow(tk_root, parameter_editor, ui)
        completion = MagicMock()

        try:
            _run_tk_until(window.root, listing_started.is_set)
            assert listing_started.is_set()
            assert window._task_runner.active
            assert window.close_button.instate(["disabled"])

            release_listing.set()
            _run_tk_until(window.root, lambda: not window._task_runner.active)
            assert not window._task_runner.active
            assert window.remote_empty_state_label.cget("text") == "No entries found in this directory."

            def worker(report_progress) -> tuple[list[str], list[str]]:
                report_progress(1, 1)
                return ["done"], []

            window._start_background_operation("title", "message", worker, completion)
            _run_tk_until(window.root, lambda: not window._task_runner.active)

            completion.assert_called_once_with(["done"], [])
            progress_window.update_progress_bar.assert_called_once_with(1, 1)
        finally:
            release_listing.set()
            _join_worker(window._task_runner.thread)
            with contextlib.suppress(tk.TclError):
                window.root.grab_release()
            with contextlib.suppress(tk.TclError):
                window.root.destroy()

    def test_close_is_disabled_during_remote_listing(self) -> None:
        """The browser stays open and explains why it cannot close during a listing."""
        window = _bare_window()
        window._task_runner.active = True
        window.root = MagicMock()
        window.ui = MagicMock()

        window._on_close()

        window.root.destroy.assert_not_called()
        window.ui.show_error.assert_called_once_with(
            "Transfer error",
            "Another file operation is already in progress.",
        )

    def test_close_destroys_idle_browser_and_notifies_parent(self) -> None:
        """The Close action still releases an idle browser."""
        window = _bare_window()
        window.root = MagicMock()
        window._closed_callback = MagicMock()

        window._on_close()

        window.root.destroy.assert_called_once_with()
        window._closed_callback.assert_called_once_with()

    def test_remote_task_reports_a_late_mavftp_error(self) -> None:
        """The original connection failure reaches the completion callback."""
        window = _bare_window()
        window._task_runner = ImmediateTaskRunner()
        completion = MagicMock()
        window.close_button = MagicMock()

        def fail() -> None:
            message = "link lost"
            raise RuntimeError(message)

        window._start_remote_task(fail, completion)

        _result, error = completion.call_args.args
        assert isinstance(error, RuntimeError)

    def test_local_refresh_repopulates_while_remote_listing_is_in_flight(self, tmp_path: Path) -> None:
        """A remote listing must not discard a local directory refresh request."""
        new_file = tmp_path / "new.bin"
        new_file.write_bytes(b"new")
        window = _bare_window()
        window._task_runner.active = True
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = str(tmp_path)
        window.local_directory_label = MagicMock()
        window.local_empty_state_label = MagicMock()
        window._populate_local_tree = MagicMock()
        window._select_pending_entry = MagicMock()
        window._update_parent_navigation_buttons = MagicMock()
        window.ui = MagicMock()

        window.refresh_local_panel()

        assert [entry.name for entry in window.local_entries] == ["new.bin"]
        window._populate_local_tree.assert_called_once_with()
        window.local_directory_label.configure.assert_called_once_with(text=f"Local files in {tmp_path}")

    def test_failed_remote_task_reconciles_transfer_buttons(self) -> None:
        """A failed remote listing restores buttons based on the current local selection."""
        window = _bare_window()
        window.close_button = MagicMock()
        window._update_parent_navigation_buttons = MagicMock()
        window.local_entries = [LocalFileEntry("local.bin", Path("local.bin"), 1)]
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.upload_button = MagicMock()

        def fail() -> None:
            message = "listing failed"
            raise RuntimeError(message)

        window._start_remote_task(fail, MagicMock())

        window.upload_button.configure.assert_called_once_with(state="normal")
        window._update_parent_navigation_buttons.assert_called_once_with()

    @pytest.mark.skipif(
        sys.platform in {"win32", "darwin"},
        reason="tk_popup enters a modal native menu loop on Windows/macOS",
    )
    def test_context_menu_invokes_command_before_deferred_destroy(self) -> None:
        """A real Tk menu command still runs when Unmap destroys the menu."""
        try:
            root = tk.Tk()
        except tk.TclError as error:
            pytest.skip(f"real Tk display unavailable: {error}")
        root.geometry("320x200")
        tree = ttk.Treeview(root)
        tree.pack(fill=tk.BOTH, expand=True)
        root.update()
        menu = tk.Menu(tree, tearoff=False)
        command_fired: list[bool] = []
        window = _bare_window()
        window.remote_tree = tree
        window.local_tree = tree
        window.last_selected_items = {"remote": None, "local": None}
        window._update_transfer_buttons = MagicMock()
        window.create_new_local_directory = lambda: command_fired.append(True)

        try:
            with patch(
                "ardupilot_methodic_configurator.frontend_tkinter_file_browser.tk.Menu",
                return_value=menu,
            ):
                window._show_context_menu(
                    SimpleNamespace(y=1, x_root=20, y_root=20),
                    remote=False,
                )
            root.update()
            menu.activate(0)
            root.tk.call("tk::MenuInvoke", str(menu), 0)
            root.update()
            assert command_fired == [True]
            assert root.tk.call("winfo", "exists", str(menu)) == 0
        finally:
            root.destroy()

    def test_mutating_tree_bindings_are_ignored_while_controls_are_disabled(self) -> None:
        """Keyboard mutation handlers cannot race an all-controls operation."""
        window = _bare_window()
        window._task_runner.active = True
        window.last_selected_panel = "local"
        window.delete_selected_local_entries = MagicMock()
        window.delete_selected_remote_entries = MagicMock()
        window._start_inline_rename = MagicMock()
        window.local_tree = MagicMock()
        window.remote_tree = MagicMock()

        assert window._on_delete_key(SimpleNamespace(widget=window.local_tree)) == "break"
        assert window._on_rename_key(SimpleNamespace(widget=window.local_tree)) == "break"
        window.delete_selected_local_entries.assert_not_called()
        window.delete_selected_remote_entries.assert_not_called()
        window._start_inline_rename.assert_not_called()

        locked_window = _bare_window()
        locked_window._task_runner.active = True
        locked_window.local_tree = MagicMock()
        locked_window.local_tree.selection.return_value = ("0",)
        locked_window.local_entries = [LocalFileEntry("local.bin", Path("local.bin"), 1)]
        locked_window.ui = MagicMock()
        locked_window._delete_local_entry = MagicMock()
        locked_window.delete_selected_local_entries()
        locked_window.ui.ask_yesno.assert_not_called()
        locked_window._delete_local_entry.assert_not_called()

    def test_remote_download_preflight_runs_filesystem_conflicts_off_tk_thread(self, tk_root: tk.Tk, tmp_path: Path) -> None:
        """Local target conflict checks run in the remote-task worker."""
        runner = BackgroundTaskRunner(MagicMock())
        parameter_editor = MagicMock()
        parameter_editor.get_vehicle_directory.return_value = str(tmp_path)
        window = FileBrowserWindow(tk_root, parameter_editor, MagicMock(), task_runner=runner)
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 1)
        window.remote_entries = [entry]
        window.remote_tree.insert("", "end", iid="0", values=(entry.name,))
        window.remote_tree.selection_set("0")
        window.local_directory_var.set(str(tmp_path))
        conflict_threads: list[str] = []

        def conflicts(plan: RemoteDownloadPlan) -> tuple[list[Path], list[Path]]:
            conflict_threads.append(current_thread().name)
            return _local_target_conflicts(plan)

        window._start_background_operation = MagicMock()
        try:
            with patch(
                "ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations._local_target_conflicts",
                side_effect=conflicts,
            ):
                window.download_selected_remote_entries()
                assert runner.thread is not None
                runner.thread.join(timeout=2)
                runner.poll()
        finally:
            with contextlib.suppress(tk.TclError):
                window.root.grab_release()
                window.root.destroy()

        window._start_background_operation.assert_called_once()
        assert conflict_threads
        assert conflict_threads[0] != "MainThread"

    def test_duplicate_download_targets_are_reported_before_transfer(self, tmp_path: Path) -> None:
        """The browser stops before transfer when preflight finds duplicate targets."""
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 1)
        target = tmp_path / entry.name
        window = _bare_window()
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0",)
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = str(tmp_path)
        window.parameter_editor = MagicMock()
        window.ui = MagicMock()
        window._start_remote_task = MagicMock()

        window.download_selected_remote_entries()

        completion = window._start_remote_task.call_args.args[1]
        plan = RemoteDownloadPlan((), ((entry, target),))
        completion(RemoteDownloadPreflight(plan, (target,), ()), None)

        title, message = window.ui.show_error.call_args.args
        assert title == "Download error"
        assert "Several selected entries map to the same local target:" in message
        assert str(target) in message
        window.parameter_editor.download_remote_file.assert_not_called()

    def test_summary_cap_keeps_failures_visible(self) -> None:
        """Successful entries cannot hide failures."""
        window = _bare_window()
        window.ui = MagicMock()
        succeeded = [f"success-{index}" for index in range(window.MAX_SUMMARY_ENTRIES)]

        window._show_summary("Summary", succeeded, ["failed.bin"])

        message = window.ui.show_error.call_args.args[1]
        assert "Failed: failed.bin" in message

    def test_background_operation_uses_worker_thread_and_tk_polling(self) -> None:
        """Transfer results and progress are applied by the Tk polling seam."""

        class FakeMisc:
            """Minimal Tk root substitute for the worker-thread test."""

            def __init__(self) -> None:
                self.after = MagicMock()

        window = _bare_window()
        window.root = FakeMisc()
        window._task_runner = BackgroundTaskRunner(window.root.after)
        window.close_button = MagicMock()
        window.ui = MagicMock()
        window.ui.create_progress_window.return_value = MagicMock()
        completion = MagicMock()

        def worker(report_progress) -> tuple[list[str], list[str]]:
            report_progress(1, 1)
            return ["done"], []

        window._start_background_operation("title", "message", worker, completion)
        window.close_button.configure.assert_called_with(state="disabled")
        assert window._task_runner.thread is not None
        window._task_runner.thread.join(timeout=2)
        window._task_runner.poll()

        completion.assert_called_once_with(["done"], [])
        window.close_button.configure.assert_called_with(state="normal")

    def test_rejected_background_operation_restores_controls_and_closes_progress(self) -> None:
        """A rejected transfer leaves no orphan progress window or disabled controls."""
        window = _bare_window()
        window._task_runner = MagicMock(active=False)
        window._task_runner.start.return_value = False
        window._set_operation_controls_state = MagicMock()
        window.close_button = MagicMock()
        window.ui = MagicMock()
        progress = MagicMock()
        window._progress_window = MagicMock(return_value=progress)
        completion = MagicMock()

        window._start_background_operation("title", "message", lambda _report: ([], []), completion)

        assert window._set_operation_controls_state.call_args_list == [call("disabled"), call("normal")]
        assert window.close_button.configure.call_args_list == [call(state="disabled"), call(state="normal")]
        progress.destroy.assert_called_once()
        completion.assert_not_called()
        window.ui.show_error.assert_called_once_with("Transfer error", "Another file operation is already in progress.")

    def test_background_operation_reports_when_controls_are_locked(self) -> None:
        """A rejected operation reports its reason instead of disappearing silently."""
        window = _bare_window()
        window._task_runner.active = True
        window.ui = MagicMock()

        started = window._start_background_operation("title", "message", lambda _report: ([], []), MagicMock())

        assert started is False
        window.ui.show_error.assert_called_once_with("Transfer error", "Another file operation is already in progress.")

    def test_transfer_buttons_are_enabled_only_for_selected_entries(self) -> None:
        """
        Download and upload controls follow the selections in their respective panels.

        GIVEN: The remote and local panels contain files and directories
        WHEN: The user selects nothing or selects entries in either panel
        THEN: Only the transfer action with selectable entries is enabled
        """
        window = _bare_window()
        window.remote_entries = [FlightControllerLogFile("remote", "/APM/LOGS/remote", 0, is_directory=True)]
        window.local_entries = [LocalFileEntry("local", Path("local"), 0, is_directory=True)]
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window.download_button = MagicMock()
        window.upload_button = MagicMock()

        window.remote_tree.selection.return_value = ()
        window.local_tree.selection.return_value = ()
        window._update_transfer_buttons()
        window.download_button.configure.assert_called_once_with(state="disabled")
        window.upload_button.configure.assert_called_once_with(state="disabled")

        window.download_button.configure.reset_mock()
        window.upload_button.configure.reset_mock()
        window.remote_tree.selection.return_value = ("0",)
        window._update_transfer_buttons()
        window.download_button.configure.assert_called_once_with(state="normal")
        window.upload_button.configure.assert_called_once_with(state="disabled")

        window.download_button.configure.reset_mock()
        window.upload_button.configure.reset_mock()
        window.remote_tree.selection.return_value = ()
        window.local_tree.selection.return_value = ("0",)
        window._update_transfer_buttons()
        window.download_button.configure.assert_called_once_with(state="disabled")
        window.upload_button.configure.assert_called_once_with(state="normal")

    def test_busy_refresh_navigation_and_button_updates_leave_controls_untouched(self, tmp_path: Path) -> None:
        """A running operation owns control state while local data may refresh."""
        window = _bare_window()
        window._task_runner.active = True
        window.remote_parent_button = MagicMock()
        window.local_parent_button = MagicMock()
        window.download_button = MagicMock()
        window.upload_button = MagicMock()
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/nested"
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = str(tmp_path)
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window._selected_remote_entries = MagicMock(return_value=[FlightControllerLogFile("remote", "/remote", 1)])
        window._selected_local_entries = MagicMock(return_value=[LocalFileEntry("local", Path("local"), 1)])
        window.ui = MagicMock()
        window.refresh_remote_panel = MagicMock()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser._local_directory_entries") as local_entries:
            window._update_parent_navigation_buttons()
            window._update_transfer_buttons()
            window._populate_local_tree = MagicMock()
            window._select_pending_entry = MagicMock()
            window._update_parent_navigation_buttons = MagicMock()
            window.local_directory_label = MagicMock()
            window.refresh_local_panel()
            window.navigate_remote_parent()
            window.navigate_local_parent()

        window.remote_parent_button.configure.assert_not_called()
        window.local_parent_button.configure.assert_not_called()
        window.download_button.configure.assert_not_called()
        window.upload_button.configure.assert_not_called()
        local_entries.assert_called_once_with(tmp_path)
        window.remote_directory_var.set.assert_not_called()
        window.local_directory_var.set.assert_not_called()
        window.refresh_remote_panel.assert_not_called()

    def test_failed_remote_listing_keeps_previous_directory_header(self) -> None:
        """A listing error must not label old rows as belonging to the failed directory."""
        window = _bare_window()
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/subdir"
        window.remote_directory_label = MagicMock()
        window.remote_entries = [FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 1)]
        window._populate_remote_tree = MagicMock()
        window._update_parent_navigation_buttons = MagicMock()
        window.parameter_editor = MagicMock()
        window.parameter_editor.get_remote_files.side_effect = RuntimeError("permission denied")
        window.ui = MagicMock()

        window.refresh_remote_panel()

        assert call(text="Remote files in /APM/LOGS/subdir") not in window.remote_directory_label.configure.call_args_list
        assert window.remote_entries == [FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 1)]
        window._populate_remote_tree.assert_not_called()
        window.ui.show_error.assert_called_once()

    def test_backspace_navigates_to_parent_of_last_selected_remote_panel(self) -> None:
        """Backspace opens the remote parent directory when the remote panel was last selected."""
        window = _bare_window()
        window.last_selected_panel = "remote"
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/nested/"
        window.refresh_remote_panel = MagicMock()

        result = window._on_backspace()

        window.remote_directory_var.set.assert_called_once_with("/APM/LOGS")
        window.refresh_remote_panel.assert_called_once_with()
        assert result == "break"

    def test_backspace_navigates_to_parent_of_last_selected_local_panel(self) -> None:
        """Backspace opens the local parent directory when the local panel was last selected."""
        window = _bare_window()
        window.last_selected_panel = "local"
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = "C:/logs/nested"
        window.refresh_local_panel = MagicMock()

        result = window._on_backspace()

        window.local_directory_var.set.assert_called_once_with(str(Path("C:/logs/nested").expanduser().parent))
        window.refresh_local_panel.assert_called_once_with()
        assert result == "break"

    def test_arrow_keys_focus_panel_and_select_first_entry_when_needed(self) -> None:
        """Arrow keys focus the requested panel and select its first entry if empty."""
        window = _bare_window()
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window.remote_tree.selection.return_value = ()
        window.local_tree.selection.return_value = ()
        window.remote_tree.get_children.return_value = ("0", "1")
        window.local_tree.get_children.return_value = ("0", "1")
        window.remote_tree.item.return_value = ("remote.bin", "File", "1 B", "")
        window.local_tree.item.return_value = ("local.bin", "File", "1 B", "")
        window.last_selected_items = {"remote": None, "local": None}
        window._update_transfer_buttons = MagicMock()

        assert window._on_left_arrow() == "break"
        window.remote_tree.focus_set.assert_called_once_with()
        window.remote_tree.selection_set.assert_called_once_with("0")
        window.remote_tree.focus.assert_called_once_with("0")
        assert window.last_selected_panel == "remote"

        assert window._on_right_arrow() == "break"
        window.local_tree.focus_set.assert_called_once_with()
        window.local_tree.selection_set.assert_called_once_with("0")
        window.local_tree.focus.assert_called_once_with("0")
        assert window.last_selected_panel == "local"

    def test_arrow_keys_are_ignored_while_rename_editor_is_active(self) -> None:
        """Arrow keys remain available for editing a filename during rename."""
        window = _bare_window()
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window._panel_navigation_enabled = False

        assert window._on_left_arrow() == ""
        assert window._on_right_arrow() == ""
        window.remote_tree.focus_set.assert_not_called()
        window.local_tree.focus_set.assert_not_called()

    def test_arrow_keys_do_not_navigate_while_a_directory_entry_has_focus(self) -> None:
        """Arrow keys edit directory fields instead of changing the active panel."""
        window = _bare_window()
        window._focus_panel = MagicMock()
        directory_entry = MagicMock(spec=ttk.Entry)

        assert window._on_left_arrow(SimpleNamespace(widget=directory_entry)) == ""
        assert window._on_right_arrow(SimpleNamespace(widget=directory_entry)) == ""
        window._focus_panel.assert_not_called()

    def test_window_binds_arrow_keys_before_a_panel_has_focus(self) -> None:
        """The FTP window handles arrows even when neither Treeview has initial focus."""
        window = _bare_window()
        window.root = MagicMock()

        window._bind_panel_navigation()

        window.root.bind.assert_any_call("<Left>", window._on_left_arrow)
        window.root.bind.assert_any_call("<Right>", window._on_right_arrow)

    def test_open_selected_local_file_uses_default_windows_application(self) -> None:
        """Opening a local file delegates to Windows file associations."""
        path = Path("log.txt")
        window = _bare_window()
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.local_entries = [LocalFileEntry("log.txt", path, 3)]

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.os.startfile", create=True) as startfile,
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.sys.platform", "win32"),
        ):
            window.open_selected_local_file()

        startfile.assert_called_once_with(str(path))

    def test_double_click_opens_clicked_local_file_not_previous_selection(self) -> None:
        """The widget binding runs before Treeview updates selection on the second click."""
        path = Path("clicked.txt")
        window = _bare_window()
        window.local_tree = MagicMock()
        window.local_tree.identify_row.return_value = "1"
        window.local_tree.selection.return_value = ("0",)
        window.local_entries = [
            LocalFileEntry("previous.txt", Path("previous.txt"), 3),
            LocalFileEntry(path.name, path, 3),
        ]

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.os.startfile", create=True) as startfile,
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.sys.platform", "win32"),
        ):
            window._on_local_double_click(SimpleNamespace(y=12))

        startfile.assert_called_once_with(str(path))

    def test_double_click_local_directory_navigates_without_launching(self) -> None:
        """Directory navigation remains distinct from file opening."""
        path = Path("folder")
        window = _bare_window()
        window.local_tree = MagicMock()
        window.local_tree.identify_row.return_value = "0"
        window.local_entries = [LocalFileEntry(path.name, path, 0, is_directory=True)]
        window.local_directory_var = MagicMock()
        window.refresh_local_panel = MagicMock()
        window._open_local_file = MagicMock()

        window._on_local_double_click(SimpleNamespace(y=12))

        window.local_directory_var.set.assert_called_once_with(str(path))
        window.refresh_local_panel.assert_called_once_with()
        window._open_local_file.assert_not_called()

    def test_double_click_local_file_ignores_blank_rows_and_busy_window(self) -> None:
        """A busy browser or empty row does not launch applications."""
        window = _bare_window()
        window.local_tree = MagicMock()
        window.local_entries = [LocalFileEntry("log.txt", Path("log.txt"), 3)]
        window._open_local_file = MagicMock()
        window.local_tree.identify_row.return_value = ""

        window._on_local_double_click(SimpleNamespace(y=12))
        window.local_tree.identify_row.return_value = "0"
        window._task_runner.active = True
        window._on_local_double_click(SimpleNamespace(y=12))

        window._open_local_file.assert_not_called()

    def test_open_selected_local_file_uses_the_posix_default_application(self) -> None:
        """Opening a local file delegates to the POSIX desktop opener."""
        path = Path("log.txt")
        window = _bare_window()
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.local_entries = [LocalFileEntry("log.txt", path, 3)]

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.sys.platform", "linux"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.subprocess.Popen") as popen,
        ):
            window.open_selected_local_file()

        popen.assert_called_once_with(["xdg-open", str(path.resolve())], start_new_session=True)

    def test_open_selected_local_file_does_not_pass_a_dash_prefixed_name_as_an_option(self) -> None:
        """POSIX openers receive a resolved path when the filename starts with a dash."""
        path = Path("--help")
        window = _bare_window()
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.local_entries = [LocalFileEntry(path.name, path, 3)]

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.sys.platform", "linux"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.subprocess.Popen") as popen,
        ):
            window.open_selected_local_file()

        popen.assert_called_once_with(["xdg-open", str(path.resolve())], start_new_session=True)

    def test_f5_refreshes_the_panel_receiving_the_key_event(self) -> None:
        """F5 refreshes the remote or local panel that has keyboard focus."""
        window = _bare_window()
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window.refresh_remote_panel = MagicMock()
        window.refresh_local_panel = MagicMock()

        remote_event = SimpleNamespace(widget=window.remote_tree)
        assert window._on_refresh_key(remote_event) == "break"
        window.refresh_remote_panel.assert_called_once_with()
        window.refresh_local_panel.assert_not_called()

        local_event = SimpleNamespace(widget=window.local_tree)
        assert window._on_refresh_key(local_event) == "break"
        window.refresh_local_panel.assert_called_once_with()

    def test_remote_parent_button_navigates_to_parent_directory(self) -> None:
        """The remote parent button navigates without creating a `..` tree row."""
        window = _bare_window()
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/nested/"
        window.refresh_remote_panel = MagicMock()

        window.navigate_remote_parent()

        window.remote_directory_var.set.assert_called_once_with("/APM/LOGS")
        window.refresh_remote_panel.assert_called_once_with()

    def test_local_parent_button_navigates_to_parent_directory(self) -> None:
        """The local parent button navigates to the filesystem parent."""
        window = _bare_window()
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = "C:/logs/nested"
        window.refresh_local_panel = MagicMock()

        window.navigate_local_parent()

        window.local_directory_var.set.assert_called_once_with(str(Path("C:/logs/nested").expanduser().parent))
        window.refresh_local_panel.assert_called_once_with()

    def test_select_all_local_entries_ignores_parent_directory(self) -> None:
        """The local Select all action does not select the parent-navigation row."""
        window = _bare_window()
        window.local_tree = MagicMock()
        window.local_tree.get_children.return_value = ("0", "1")
        window.local_tree.item.side_effect = [
            ("..", "Directory", ""),
            ("file.bin", "File", "12 B"),
        ]

        window.select_all_local_entries()

        window.local_tree.selection_set.assert_called_once_with(["1"])

    def test_remote_download_execution_continues_after_one_file_fails(self) -> None:
        """A failed remote transfer does not stop the remaining selected files."""
        window = _bare_window()
        first = FlightControllerLogFile("first.bin", "/APM/LOGS/first.bin", 10)
        second = FlightControllerLogFile("second.bin", "/APM/LOGS/second.bin", 20)
        window.remote_entries = [first, second]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0", "1")
        window.local_directory_var = MagicMock()
        local_directory = Path.cwd()
        window.local_directory_var.get.return_value = str(local_directory)
        window.parameter_editor = MagicMock()
        window.parameter_editor.download_remote_file.side_effect = [False, True]
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = False
        window._progress_window = MagicMock(return_value=MagicMock())
        window.refresh_local_panel = MagicMock()

        window.download_selected_remote_entries()

        assert window.parameter_editor.download_remote_file.call_count == 2
        assert window.parameter_editor.download_remote_file.call_args_list[0].args[:2] == (
            "/APM/LOGS/first.bin",
            str(local_directory / "first.bin"),
        )
        assert window.parameter_editor.download_remote_file.call_args_list[1].args[:2] == (
            "/APM/LOGS/second.bin",
            str(local_directory / "second.bin"),
        )
        window.ui.show_error.assert_called_once()
        window.refresh_local_panel.assert_called_once_with()

    def test_retry_downloads_only_failed_files(self, tmp_path: Path) -> None:
        """Successful files are never transferred a second time after retry."""
        window = _bare_window()
        first = FlightControllerLogFile("first.bin", "/APM/LOGS/first.bin", 10)
        second = FlightControllerLogFile("second.bin", "/APM/LOGS/second.bin", 20)
        window.remote_entries = [first, second]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0", "1")
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = str(tmp_path)
        window.parameter_editor = MagicMock()
        window.parameter_editor.download_remote_file.side_effect = [True, False, True]
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window._progress_window = MagicMock(return_value=MagicMock())
        window.refresh_local_panel = MagicMock()

        window.download_selected_remote_entries()

        paths = [call_args.args[0] for call_args in window.parameter_editor.download_remote_file.call_args_list]
        assert paths == [first.remote_path, second.remote_path, second.remote_path]
        window.ui.ask_yesno.assert_called_once()
        window.ui.show_info.assert_called_once()

    def test_failed_download_is_retried_at_most_once(self, tmp_path: Path) -> None:
        """A persistent transfer failure cannot create an endless retry loop."""
        window = _bare_window()
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0",)
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = str(tmp_path)
        window.parameter_editor = MagicMock()
        window.parameter_editor.download_remote_file.return_value = False
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window._progress_window = MagicMock(return_value=MagicMock())
        window.refresh_local_panel = MagicMock()

        window.download_selected_remote_entries()

        assert window.parameter_editor.download_remote_file.call_count == 2
        window.ui.ask_yesno.assert_called_once()
        assert window.ui.show_error.call_count == 2

    def test_retry_uploads_only_failed_files(self, tmp_path: Path) -> None:
        """An explicitly accepted retry keeps successful upload entries completed."""
        window = _bare_window()
        first = LocalFileEntry("first.bin", tmp_path / "first.bin", 10)
        second = LocalFileEntry("second.bin", tmp_path / "second.bin", 20)
        window.local_entries = [first, second]
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0", "1")
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/"
        window.parameter_editor = MagicMock()
        window.parameter_editor.upload_file_to_fc.side_effect = [True, False, True]
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window._progress_window = MagicMock(return_value=MagicMock())
        window.refresh_remote_panel = MagicMock()

        window.upload_selected_local_entries()

        paths = [call_args.args[1] for call_args in window.parameter_editor.upload_file_to_fc.call_args_list]
        assert paths == ["/APM/LOGS/first.bin", "/APM/LOGS/second.bin", "/APM/LOGS/second.bin"]
        assert window.ui.ask_yesno.call_count == 2  # initial upload confirmation, then retry
        window.ui.show_info.assert_called_once()

    def test_retry_upload_is_not_lost_when_refresh_starts_a_remote_listing(self) -> None:
        """An accepted upload retry starts before its refresh can lock the runner."""
        window = _bare_window()
        entry = LocalFileEntry("only.bin", Path("only.bin"), 10)
        window.local_entries = [entry]
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/"
        window.parameter_editor = MagicMock()
        window.parameter_editor.upload_file_to_fc.side_effect = [False, True]
        window.ui = MagicMock()
        window.ui.ask_yesno.side_effect = [True, True]
        window._progress_window = MagicMock(return_value=MagicMock())

        def refresh_and_hold_runner() -> None:
            window._task_runner.active = True

        window.refresh_remote_panel = refresh_and_hold_runner

        window.upload_selected_local_entries()

        assert window.parameter_editor.upload_file_to_fc.call_count == 2

    def test_verified_download_is_labeled_in_summary(self, tmp_path: Path) -> None:
        """The checkbox verifies completed files, and the summary says verified."""
        window = _bare_window()
        window.verify_transfers_var.get.return_value = True
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0",)
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = str(tmp_path)
        window.parameter_editor = MagicMock()
        window.parameter_editor.download_remote_file.return_value = True
        window.parameter_editor.verify_remote_file.return_value = True
        window.ui = MagicMock()
        window._progress_window = MagicMock(return_value=MagicMock())
        window.refresh_local_panel = MagicMock()

        window.download_selected_remote_entries()

        window.parameter_editor.verify_remote_file.assert_called_once_with(entry.remote_path, str(tmp_path / entry.name))
        assert "Verified: /APM/LOGS/log.bin" in window.ui.show_info.call_args.args[1]

    def test_skipped_verification_is_not_claimed_verified(self) -> None:
        """Generated files retain an explicit not-verified status in the summary."""
        window = _bare_window()
        window.ui = MagicMock()
        window._show_summary("Download summary", ["/@SYS/threads.txt"], [], {"/@SYS/threads.txt": None})
        assert "Not verified: /@SYS/threads.txt" in window.ui.show_info.call_args.args[1]
        window._show_summary("Download summary", [], ["/APM/LOGS/log.bin"], {"/APM/LOGS/log.bin": False})
        assert "Not verified: /APM/LOGS/log.bin" in window.ui.show_error.call_args.args[1]

    def test_local_upload_execution_creates_directories_and_uploads_files_recursively(self) -> None:
        """Uploading a local directory preserves its hierarchy on the FC."""
        local_root = MagicMock()
        nested = MagicMock()
        leaf = MagicMock()
        local_root.iterdir.return_value = [nested]
        local_root.is_dir.return_value = True
        local_root.is_symlink.return_value = False
        local_root.name = "folder"
        nested.iterdir.return_value = [leaf]
        nested.is_dir.return_value = True
        nested.is_symlink.return_value = False
        nested.name = "nested"
        leaf.is_dir.return_value = False
        leaf.is_symlink.return_value = False
        leaf.name = "leaf log.bin"
        leaf.stat.return_value.st_size = 7

        window = _bare_window()
        window.local_entries = [LocalFileEntry("folder", local_root, 0, is_directory=True)]
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/"
        window.parameter_editor = MagicMock()
        window.parameter_editor.make_remote_directory.return_value = True
        window.parameter_editor.upload_file_to_fc.return_value = True
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window._progress_window = MagicMock(return_value=MagicMock())
        window.refresh_remote_panel = MagicMock()

        window.upload_selected_local_entries()

        assert window.parameter_editor.make_remote_directory.call_args_list == [
            call("/APM/LOGS/folder"),
            call("/APM/LOGS/folder/nested"),
        ]
        window.parameter_editor.upload_file_to_fc.assert_called_once()
        assert window.parameter_editor.upload_file_to_fc.call_args.args[:2] == (
            str(leaf),
            "/APM/LOGS/folder/nested/leaf log.bin",
        )
        window.refresh_remote_panel.assert_called_once_with()

    def test_unreadable_local_directory_is_failed_without_creating_remote_directory(self) -> None:
        """An unreadable selected directory is neither silently successful nor uploaded empty."""
        local_root = MagicMock()
        local_root.iterdir.side_effect = PermissionError("denied")
        entry = LocalFileEntry("folder", local_root, 0, is_directory=True)
        window = _bare_window()
        window.local_entries = [entry]
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/"
        window.parameter_editor = MagicMock()
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window.root = MagicMock()

        window.upload_selected_local_entries()

        window.parameter_editor.make_remote_directory.assert_not_called()
        window.parameter_editor.upload_file_to_fc.assert_not_called()
        window.ui.show_error.assert_called_once()

    def test_remote_delete_only_removes_files_and_empty_directories(self) -> None:
        """Remote delete skips non-empty directories while continuing the batch."""
        window = _bare_window()
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        empty = FlightControllerLogFile("empty", "/APM/LOGS/empty", 0, is_directory=True)
        child = FlightControllerLogFile("leaf.bin", "/APM/LOGS/folder/leaf.bin", 10)
        file_entry = FlightControllerLogFile("file.bin", "/APM/LOGS/file.bin", 10)
        window.remote_entries = [root, empty, file_entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0", "1", "2")
        window.parameter_editor = MagicMock()
        window.parameter_editor.get_remote_files.side_effect = [[child], []]
        window.parameter_editor.delete_remote_path.return_value = True
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window.refresh_remote_panel = MagicMock()

        window.delete_selected_remote_entries()

        assert window.parameter_editor.delete_remote_path.call_args_list == [
            call("/APM/LOGS/empty", True),  # noqa: FBT003
            call("/APM/LOGS/file.bin", False),  # noqa: FBT003
        ]
        window.ui.show_error.assert_called_once()
        window.refresh_remote_panel.assert_called_once_with()

    def test_remote_delete_does_not_delete_directory_when_listing_fails(self) -> None:
        """A failed directory listing never authorizes a remote directory deletion."""
        window = _bare_window()
        entry = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0",)
        window.parameter_editor = MagicMock()
        window.parameter_editor.get_remote_files.return_value = None
        window.parameter_editor.delete_remote_path.return_value = True
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window.refresh_remote_panel = MagicMock()

        window.delete_selected_remote_entries()

        window.parameter_editor.delete_remote_path.assert_not_called()
        window.ui.show_error.assert_called_once()

    def test_local_delete_removes_files_and_empty_directories(self) -> None:
        """Local delete uses unlink/rmdir and continues across multiple selections."""
        local_root = MagicMock()
        local_file = MagicMock()

        window = _bare_window()
        window.local_entries = [
            LocalFileEntry("folder", local_root, 0, is_directory=True),
            LocalFileEntry("file.bin", local_file, 10),
        ]
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0", "1")
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window.refresh_local_panel = MagicMock()

        window.delete_selected_local_entries()

        local_root.rmdir.assert_called_once_with()
        local_file.unlink.assert_called_once_with()
        window.refresh_local_panel.assert_called_once_with()

    def test_f2_falls_back_to_name_dialog_when_inline_editor_is_unavailable(self) -> None:
        """F2 uses the dialog fallback when the selected row cannot be edited inline."""
        entry = FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 10)
        window = _bare_window()
        window.last_selected_panel = "remote"
        window.last_selected_items = {"remote": "0", "local": None}
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.bbox.return_value = ()
        window.remote_tree.selection.return_value = ("0",)
        window.ui = MagicMock()
        window.ui.askstring.return_value = "new.bin"
        window.root = MagicMock()
        window.parameter_editor = MagicMock()
        window.parameter_editor.rename_remote_path.return_value = True
        window.refresh_remote_panel = MagicMock()

        result = window._on_rename_key()

        assert result == "break"
        window.ui.askstring.assert_called_once()
        window.parameter_editor.rename_remote_path.assert_called_once_with(
            "/APM/LOGS/old.bin",
            "/APM/LOGS/new.bin",
        )

    def test_f2_commits_an_inline_remote_rename(self) -> None:
        """F2 commits the edited name without opening a dialog when inline editing works."""
        entry = FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 10)
        window = _bare_window()
        window.remote_tree = MagicMock()
        window.remote_tree.bbox.return_value = (1, 2, 100, 20)
        window.remote_tree.selection.return_value = ("0",)
        window.remote_entries = [entry]
        window.last_selected_panel = "remote"
        window.last_selected_items = {"remote": "0", "local": None}
        window.ui = MagicMock()
        window.parameter_editor = MagicMock()
        window.parameter_editor.rename_remote_path.return_value = True
        window.refresh_remote_panel = MagicMock()
        editor = MagicMock()
        editor.get.return_value = "new log.bin"

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_file_browser.ttk.Entry",
            return_value=editor,
        ):
            result = window._on_rename_key()

        assert result == "break"
        assert window._panel_navigation_enabled is False
        editor.place.assert_called_once_with(x=1, y=2, width=100, height=20)
        editor.focus_set.assert_called_once_with()
        editor.bind.assert_any_call("<Return>", ANY)
        window.parameter_editor.rename_remote_path.assert_not_called()

        assert window._on_left_arrow() == ""
        editor.focus_set.assert_called_once_with()

        finish_result = window._finish_inline_rename("remote", entry, editor)

        assert finish_result == "break"
        assert window._panel_navigation_enabled is True
        window.parameter_editor.rename_remote_path.assert_called_once_with(
            "/APM/LOGS/old.bin",
            "/APM/LOGS/new log.bin",
        )

    def test_focus_out_commits_an_inline_rename(self) -> None:
        """Leaving an inline editor commits the edited name instead of discarding it."""
        entry = FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 10)
        window = _bare_window()
        window.remote_tree = MagicMock()
        window.remote_tree.bbox.return_value = (1, 2, 100, 20)
        window._panel_navigation_enabled = True
        window.ui = MagicMock()
        window.parameter_editor = MagicMock()
        window.parameter_editor.rename_remote_path.return_value = True
        window.refresh_remote_panel = MagicMock()
        editor = MagicMock()
        editor.get.return_value = "new.bin"

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_file_browser.ttk.Entry",
            return_value=editor,
        ):
            window._start_inline_rename("remote", "0", entry)

        focus_out = next(bind_call.args[1] for bind_call in editor.bind.call_args_list if bind_call.args[0] == "<FocusOut>")
        assert window._panel_navigation_enabled is False

        assert focus_out(SimpleNamespace()) == "break"
        editor.destroy.assert_called_once_with()
        assert window._panel_navigation_enabled is True
        window.parameter_editor.rename_remote_path.assert_called_once_with(
            "/APM/LOGS/old.bin",
            "/APM/LOGS/new.bin",
        )

    def test_focus_out_without_a_name_change_does_not_rename(self) -> None:
        """Losing focus without editing a name is a no-op."""
        entry = FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 10)
        window = _bare_window()
        window._panel_navigation_enabled = False
        window.ui = MagicMock()
        window._rename_entry = MagicMock()
        editor = MagicMock()
        editor.get.return_value = entry.name

        assert window._finish_inline_rename("remote", entry, editor) == "break"

        editor.destroy.assert_called_once_with()
        window._rename_entry.assert_not_called()
        window.ui.show_error.assert_not_called()
        assert window._panel_navigation_enabled is True

    def test_f2_does_not_rename_a_stale_row_without_current_selection(self) -> None:
        """F2 refuses to act on a cached row after the current selection is gone."""
        entry = FlightControllerLogFile("new.bin", "/APM/LOGS/new.bin", 10)
        window = _bare_window()
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ()
        window.remote_entries = [entry]
        window.last_selected_panel = "remote"
        window.last_selected_items = {"remote": "0", "local": None}
        window.ui = MagicMock()
        window.parameter_editor = MagicMock()

        assert window._on_rename_key() == "break"

        window.ui.askstring.assert_not_called()
        window.parameter_editor.rename_remote_path.assert_not_called()

    def test_remote_mutation_outside_log_directory_uses_its_regular_confirmation_only(self) -> None:
        """Remote deletion outside the log directory has no additional scope prompt."""
        entry = FlightControllerLogFile("params.bin", "/APM/params.bin", 10)
        window = _bare_window()
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0",)
        window.parameter_editor = MagicMock()
        window.parameter_editor.delete_remote_path.return_value = True
        window.ui = MagicMock()
        window.ui.ask_yesno.return_value = True
        window.refresh_remote_panel = MagicMock()

        window.delete_selected_remote_entries()

        window.ui.show_warning.assert_not_called()
        window.ui.ask_yesno.assert_called_once()
        window.parameter_editor.delete_remote_path.assert_called_once_with("/APM/params.bin", False)  # noqa: FBT003

    def test_context_menu_selects_clicked_local_row_and_offers_new_directory(self) -> None:
        """Right-clicking either panel offers creating a directory in that panel."""
        window = _bare_window()
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window.local_tree.identify_row.return_value = "3"
        window.local_tree.selection.return_value = ()
        window.local_entries = [LocalFileEntry("local.txt", Path("local.txt"), 10)]
        window.last_selected_items = {"remote": None, "local": None}
        window._update_transfer_buttons = MagicMock()
        menu = MagicMock()
        event = MagicMock()
        event.y = 12
        event.x_root = 100
        event.y_root = 200

        with patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.tk.Menu", return_value=menu):
            result = window._show_context_menu(event, remote=False)

        assert result == "break"
        assert window.last_selected_panel == "local"
        assert window.last_selected_items["local"] == "3"
        window.local_tree.selection_set.assert_called_once_with("3")
        window.local_tree.focus.assert_called_once_with("3")
        assert menu.add_command.call_args_list == [
            call(label="New directory", command=window.create_new_local_directory),
            call(label="Open", command=window.open_selected_local_file, state="disabled"),
        ]
        menu.tk_popup.assert_called_once_with(100, 200)
        menu.grab_release.assert_called_once_with()

    def test_context_menu_survives_popup_return_until_it_is_unmapped(self) -> None:
        """The X11 popup remains available after ``tk_popup`` returns."""

        class FakeMenu:
            """Minimal menu double that records popup lifecycle callbacks."""

            def __init__(self) -> None:
                self.bindings: dict[str, object] = {}
                self.destroyed = False

            def add_command(self, **_kwargs: object) -> None:
                pass

            def bind(self, sequence: str, callback: object, **_kwargs: str) -> None:
                self.bindings[sequence] = callback

            def tk_popup(self, _x: int, _y: int) -> None:
                pass

            def grab_release(self) -> None:
                pass

            def after_idle(self, callback: object) -> None:
                typing.cast("typing.Callable[[], None]", callback)()

            def destroy(self) -> None:
                self.destroyed = True

        window = _bare_window()
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window.local_tree.identify_row.return_value = ""
        window.last_selected_items = {"remote": None, "local": None}
        window._update_transfer_buttons = MagicMock()
        menu = FakeMenu()
        event = MagicMock()
        event.y = 12
        event.x_root = 100
        event.y_root = 200

        with patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.tk.Menu", return_value=menu):
            window._show_context_menu(event, remote=False)

        assert menu.destroyed is False
        assert "<Unmap>" in menu.bindings

        callback = typing.cast("typing.Callable[[object], None]", menu.bindings["<Unmap>"])
        callback(MagicMock())
        assert menu.destroyed is True

    def test_new_remote_directory_can_be_created_outside_the_log_directory(self) -> None:
        """Creating a remote directory uses the displayed path without a log-scope warning."""
        window = _bare_window()
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM"
        window.parameter_editor = MagicMock()
        window.parameter_editor.make_remote_directory.return_value = True
        window.ui = MagicMock()
        window.ui.askstring.return_value = "custom"
        window.root = MagicMock()
        window._progress_window = MagicMock(return_value=MagicMock())
        window.refresh_remote_panel = MagicMock()

        window.create_new_remote_directory()

        window.parameter_editor.make_remote_directory.assert_called_once_with("/APM/custom")
        window.ui.show_warning.assert_not_called()
        window.refresh_remote_panel.assert_called_once_with()

    def test_new_local_directory_is_created_in_the_displayed_directory(self, tmp_path: Path) -> None:
        """Creating a local directory refreshes the local panel after it succeeds."""
        window = _bare_window()
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = str(tmp_path)
        window.ui = MagicMock()
        window.ui.askstring.return_value = "new-folder"
        window.root = MagicMock()
        window.refresh_local_panel = MagicMock()

        window.create_new_local_directory()

        assert (tmp_path / "new-folder").is_dir()
        window.refresh_local_panel.assert_called_once_with()

    def test_new_directory_is_selected_after_the_panel_refresh(self) -> None:
        """A successfully created directory is selected and revealed after refreshing."""
        window = _bare_window()
        window.remote_entries = [
            FlightControllerLogFile("existing", "/APM/existing", 0, is_directory=True),
            FlightControllerLogFile("new-folder", "/APM/new-folder", 0, is_directory=True),
        ]
        window.remote_tree = MagicMock()
        window.local_tree = MagicMock()
        window.last_selected_items = {"remote": None, "local": None}
        window._pending_entry_selection = {"remote": None, "local": None}
        window._update_transfer_buttons = MagicMock()

        window._select_entry_after_refresh("remote", "new-folder")
        window._select_pending_entry("remote")

        window.remote_tree.selection_set.assert_called_once_with("1")
        window.remote_tree.focus.assert_called_once_with("1")
        window.remote_tree.see.assert_called_once_with("1")
        assert window.last_selected_panel == "remote"
        assert window.last_selected_items["remote"] == "1"

    def test_remote_rename_uses_a_single_safe_new_name(self) -> None:
        """Remote rename uses the selected entry's parent directory."""
        window = _bare_window()
        entry = FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 10)
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0",)
        window.ui = MagicMock()
        window.ui.askstring.return_value = "new.bin"
        window.root = MagicMock()
        window.parameter_editor = MagicMock()
        window.parameter_editor.rename_remote_path.return_value = True
        window.refresh_remote_panel = MagicMock()

        window.rename_selected_remote_entry()

        window.parameter_editor.rename_remote_path.assert_called_once_with(
            "/APM/LOGS/old.bin",
            "/APM/LOGS/new.bin",
        )
        window.refresh_remote_panel.assert_called_once_with()

    def test_local_rename_uses_a_single_safe_new_name(self) -> None:
        """Local rename changes only the selected entry name."""
        old_path = MagicMock()
        target_path = MagicMock()
        old_path.with_name.return_value = target_path
        target_path.exists.return_value = False
        window = _bare_window()
        entry = LocalFileEntry("old.bin", old_path, 7)
        window.local_entries = [entry]
        window.local_tree = MagicMock()
        window.local_tree.selection.return_value = ("0",)
        window.ui = MagicMock()
        window.ui.askstring.return_value = "new.bin"
        window.root = MagicMock()
        window.refresh_local_panel = MagicMock()

        window.rename_selected_local_entry()

        old_path.rename.assert_called_once_with(target_path)
        window.refresh_local_panel.assert_called_once_with()

    def test_user_can_toggle_remote_filename_sort_direction(self) -> None:
        """Clicking the filename heading repeatedly alternates ascending and descending."""
        window = _bare_window()
        window.remote_sort_column = ""
        window.remote_sort_reverse = False
        window.remote_entries = [
            FlightControllerLogFile("alpha.BIN", "/APM/LOGS/alpha.BIN", 10),
            FlightControllerLogFile("zeta.BIN", "/APM/LOGS/zeta.BIN", 20),
        ]
        window.remote_tree = MagicMock()
        window.remote_tree.get_children.return_value = ("0", "1")

        window._on_sort_heading("remote", "name")
        window.remote_tree.move.reset_mock()
        window._on_sort_heading("remote", "name")

        assert window.remote_sort_column == "name"
        assert window.remote_sort_reverse is True
        assert window.remote_tree.move.call_args_list == [
            call("1", "", 0),
            call("0", "", 1),
        ]

    def test_sorting_with_parent_entry_does_not_compare_strings_and_integers(self) -> None:
        """Sorting a navigable panel remains valid when the synthetic `..` row is present."""
        window = _bare_window()
        window.remote_sort_column = ""
        window.remote_sort_reverse = False
        window.remote_entries = [
            FlightControllerLogFile("..", "/APM/LOGS", 0, is_directory=True),
            FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 10),
        ]
        window.remote_tree = MagicMock()
        window.remote_tree.get_children.return_value = ("0", "1")

        window._on_sort_heading("remote", "name")

        assert window.remote_tree.move.call_args_list == [
            call("0", "", 0),
            call("1", "", 1),
        ]

    def test_parameter_editor_button_opens_the_log_download_modal(self) -> None:
        """
        The renamed Parameter Editor button opens the new modal.

        GIVEN: A configured Parameter Editor window
        WHEN: The user clicks Download .bin log file(s)
        THEN: A modal is opened with the editor model and UI services
        """
        editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
        editor.root = MagicMock()
        editor.parameter_editor = MagicMock()
        editor.ui = MagicMock()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FileBrowserWindow") as modal:
            editor.on_download_bin_logs_click()

        modal.assert_called_once_with(editor.root, editor.parameter_editor, editor.ui)
        editor.ui.create_progress_window.assert_not_called()
        editor.parameter_editor.download_last_flight_log.assert_not_called()
