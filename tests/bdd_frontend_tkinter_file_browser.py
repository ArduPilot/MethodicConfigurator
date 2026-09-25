#!/usr/bin/env python3

"""
BDD tests for user-visible flight-controller file-browser workflows.

These scenarios exercise the browser's task boundaries and filesystem/remote
operation seams without requiring a live flight controller.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
from ardupilot_methodic_configurator.frontend_tkinter_file_browser import FileBrowserWindow
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations import (
    LocalFileEntry,
    LocalUploadPlan,
    RemoteDownloadPlan,
    _build_local_upload_plan,
    _build_remote_download_plan,
    _delete_remote_entries_worker,
    _download_remote_plan_worker,
    _upload_local_plan_worker,
)

if TYPE_CHECKING:
    from pathlib import Path

# pylint: disable=protected-access, redefined-outer-name


class SynchronousTaskRunner:  # pylint: disable=too-few-public-methods
    """Run a browser task synchronously while preserving its busy-state boundary."""

    active = False

    def start(self, task, on_progress, on_done) -> bool:
        """Execute the task and deliver either its result or its exception."""
        self.active = True
        try:
            try:
                result, error = task(on_progress or (lambda _current, _total: None)), None
            except Exception as exception:  # pylint: disable=broad-exception-caught
                result, error = None, exception
        finally:
            self.active = False
        on_done(result, error)
        return True


@pytest.fixture
def browser() -> FileBrowserWindow:
    """Provide the browser's user-facing workflow with injectable services."""
    window = FileBrowserWindow.__new__(FileBrowserWindow)
    window._task_runner = SynchronousTaskRunner()
    window.verify_transfers_var = MagicMock()
    window.verify_transfers_var.get.return_value = False
    window.last_selected_items = {"remote": None, "local": None}
    window._pending_entry_selection = {"remote": None, "local": None}
    window._panel_navigation_enabled = True
    window.root = MagicMock()
    window.ui = MagicMock()
    return window


def _run_background_operation(_title, _message, worker, completion) -> None:
    """Bridge a progress operation to the production worker/completion seam."""
    completion(*worker(lambda _current, _total: None))


class TestFileBrowserUserWorkflows:
    """Describe the file-browser behaviors users rely on during MAVFTP work."""

    def test_user_can_browse_local_directory_while_remote_listing_is_running(
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """
        A local browse request remains visible while a remote listing is busy.

        GIVEN: The remote panel is loading and the user chooses a new local directory
        WHEN: The local panel is refreshed before the remote listing completes
        THEN: The local header, rows, and cached entries describe the chosen directory
        AND: The in-flight task still owns the navigation and transfer controls
        """
        old_directory = tmp_path / "old"
        new_directory = tmp_path / "new"
        old_directory.mkdir()
        new_directory.mkdir()
        (old_directory / "old.bin").write_bytes(b"old")
        (new_directory / "new.bin").write_bytes(b"new")

        browser._task_runner.active = True
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(new_directory)
        browser.local_directory_label = MagicMock()
        browser.local_empty_state_label = MagicMock()
        browser.local_tree = MagicMock()
        browser.local_tree.get_children.return_value = ()
        browser.remote_tree = MagicMock()
        browser.download_button = MagicMock()
        browser.upload_button = MagicMock()

        browser.refresh_local_panel()

        assert [entry.name for entry in browser.local_entries] == ["new.bin"]
        assert browser.local_directory_label.configure.call_args.kwargs["text"] == (f"Local files in {new_directory}")
        assert browser.local_tree.insert.call_args.kwargs["values"][0] == "new.bin"
        browser.download_button.configure.assert_not_called()
        browser.upload_button.configure.assert_not_called()

    def test_user_is_told_when_remote_directory_has_no_listing(self, browser: FileBrowserWindow) -> None:
        """
        A missing remote listing does not masquerade as a successful empty refresh.

        GIVEN: The remote panel shows rows from a previously listed directory
        WHEN: MAVFTP returns no listing for the requested directory
        THEN: An error is shown
        AND: The header does not identify the stale rows as the failed directory
        """
        browser.remote_directory_var = MagicMock()
        browser.remote_directory_var.get.return_value = "/APM/LOGS/unreadable"
        browser.remote_directory_label = MagicMock()
        browser.remote_entries = [FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 1)]
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.get_remote_files.return_value = None

        browser.refresh_remote_panel()

        browser.ui.show_error.assert_called_once()
        assert browser.remote_entries == [FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 1)]
        assert all(
            call.kwargs.get("text") != "Remote files in /APM/LOGS/unreadable"
            for call in browser.remote_directory_label.configure.call_args_list
        )

    def test_user_is_told_when_local_directory_disappears(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """
        A local browse error leaves the user with an actionable error.

        GIVEN: The current local directory path no longer exists
        WHEN: The user refreshes the local panel
        THEN: The browser reports a local directory error without changing cached rows
        """
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(tmp_path / "removed")
        browser.local_empty_state_label = MagicMock()
        browser.local_entries = [LocalFileEntry("old.bin", tmp_path / "old.bin", 1)]

        browser.refresh_local_panel()

        browser.ui.show_error.assert_called_once()
        assert browser.local_entries == [LocalFileEntry("old.bin", tmp_path / "old.bin", 1)]

    def test_user_is_told_when_local_directory_cannot_be_read(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """
        A filesystem read failure is reported instead of clearing the panel silently.

        GIVEN: The selected local directory exists but cannot be enumerated
        WHEN: The user refreshes the local panel
        THEN: The filesystem error is shown and the previous cache remains available
        """
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(tmp_path)
        browser.local_empty_state_label = MagicMock()
        browser.local_entries = [LocalFileEntry("old.bin", tmp_path / "old.bin", 1)]

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_file_browser._local_directory_entries",
            side_effect=OSError("permission denied"),
        ):
            browser.refresh_local_panel()

        browser.ui.show_error.assert_called_once()
        assert browser.local_entries == [LocalFileEntry("old.bin", tmp_path / "old.bin", 1)]

    def test_user_can_navigate_and_choose_a_local_directory(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """
        Both local navigation controls refresh the selected directory.

        GIVEN: The local panel is open in a nested directory
        WHEN: The user navigates to its parent and then chooses another directory
        THEN: Each action updates the destination and refreshes the local panel
        """
        nested = tmp_path / "nested"
        nested.mkdir()
        chosen = tmp_path / "chosen"
        chosen.mkdir()
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(nested)
        browser.refresh_local_panel = MagicMock()

        browser.navigate_local_parent()
        browser.ui.askdirectory.return_value = str(chosen)
        browser.choose_local_directory()

        assert browser.local_directory_var.set.call_args_list[0].args == (str(tmp_path),)
        assert browser.local_directory_var.set.call_args_list[1].args == (str(chosen),)
        assert browser.refresh_local_panel.call_count == 2

    def test_failed_upload_directory_is_recovered_by_one_retry(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """
        A retry that creates a failed directory clears the stale failure summary.

        GIVEN: A selected local directory whose remote mkdir fails once
        WHEN: The user accepts the offered retry and the mkdir then succeeds
        THEN: The final summary reports the directory and file as successful
        AND: No stale directory failure remains
        """
        folder = tmp_path / "folder"
        folder.mkdir()
        (folder / "a.bin").write_bytes(b"a")
        browser.local_entries = [LocalFileEntry("folder", folder, 0, is_directory=True)]
        browser.local_tree = MagicMock()
        browser.local_tree.selection.return_value = ("0",)
        browser.remote_directory_var = MagicMock()
        browser.remote_directory_var.get.return_value = "/APM/LOGS/"
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.make_remote_directory.side_effect = [False, True]
        browser.parameter_editor.upload_file_to_fc.return_value = True
        browser.ui.ask_yesno.side_effect = [True, True]
        browser._start_background_operation = MagicMock(side_effect=_run_background_operation)
        browser.refresh_remote_panel = MagicMock()

        browser.upload_selected_local_entries()

        assert browser.parameter_editor.make_remote_directory.call_count == 2
        assert browser.parameter_editor.upload_file_to_fc.call_count == 1
        assert browser.ui.ask_yesno.call_count == 2
        assert "/APM/LOGS/folder" in browser.ui.show_info.call_args.args[1]
        assert "/APM/LOGS/folder/a.bin" in browser.ui.show_info.call_args.args[1]
        assert "Failed: /APM/LOGS/folder" not in browser.ui.show_info.call_args.args[1]

    def test_failed_download_file_is_recovered_without_stale_directory_failure(
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """
        A retry after a failed recursive download preserves directory success.

        GIVEN: A selected remote directory containing one file
        WHEN: The file transfer fails once and the user accepts one retry
        THEN: The final download summary contains the directory and file as successes
        AND: The local panel is refreshed after the operation
        """
        browser.remote_entries = [FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)]
        browser.remote_tree = MagicMock()
        browser.remote_tree.selection.return_value = ("0",)
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(tmp_path)
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.get_remote_files.return_value = [
            FlightControllerLogFile("a.bin", "/APM/LOGS/folder/a.bin", 1)
        ]
        browser.parameter_editor.download_remote_file.side_effect = [False, True]
        browser.ui.ask_yesno.return_value = True
        browser._start_background_operation = MagicMock(side_effect=_run_background_operation)
        browser.refresh_local_panel = MagicMock()

        browser.download_selected_remote_entries()

        assert browser.parameter_editor.download_remote_file.call_count == 2
        assert browser.ui.show_info.call_count == 1
        assert "/APM/LOGS/folder/a.bin" in browser.ui.show_info.call_args.args[1]
        assert browser.refresh_local_panel.call_count == 2

    def test_user_cannot_delete_remote_directory_after_listing_exception(self, browser: FileBrowserWindow) -> None:
        """
        A failed directory listing never authorizes a destructive delete.

        GIVEN: The user selects a remote directory
        WHEN: MAVFTP raises while checking whether it is empty
        THEN: The delete is reported as failed
        AND: No remote delete request is sent
        """
        browser.remote_entries = [FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)]
        browser.remote_tree = MagicMock()
        browser.remote_tree.selection.return_value = ("0",)
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.get_remote_files.side_effect = RuntimeError("listing failed")
        browser.ui.ask_yesno.return_value = True
        browser._start_background_operation = MagicMock(side_effect=_run_background_operation)
        browser.refresh_remote_panel = MagicMock()

        browser.delete_selected_remote_entries()

        browser.parameter_editor.delete_remote_path.assert_not_called()
        browser.ui.show_error.assert_called_once()

    def test_user_can_create_local_and_remote_directories(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """
        Directory creation reports success and refreshes the relevant panel.

        GIVEN: The user is viewing valid local and remote destination directories
        WHEN: The user creates one directory in each panel
        THEN: Both operations report success and request a refreshed listing
        """
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(tmp_path)
        browser.remote_directory_var = MagicMock()
        browser.remote_directory_var.get.return_value = "/APM/LOGS/"
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.make_remote_directory.return_value = True
        browser.ui.askstring.side_effect = ["local-folder", "remote-folder"]
        browser._start_background_operation = MagicMock(side_effect=_run_background_operation)
        browser.refresh_local_panel = MagicMock()
        browser.refresh_remote_panel = MagicMock()

        browser.create_new_local_directory()
        browser.create_new_remote_directory()

        assert (tmp_path / "local-folder").is_dir()
        browser.parameter_editor.make_remote_directory.assert_called_once_with("/APM/LOGS/remote-folder")
        assert browser.ui.show_info.call_count == 2
        browser.refresh_local_panel.assert_called_once_with()
        browser.refresh_remote_panel.assert_called_once_with()

    def test_browser_rejects_busy_empty_and_unsafe_transfer_requests(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """
        Transfer commands remain safe when the browser state is not actionable.

        GIVEN: The browser is busy, has no selection, or has an unsafe destination
        WHEN: The user tries transfer, delete, or directory-creation commands
        THEN: No backend operation starts
        AND: Invalid destinations receive an explanatory error
        """
        browser._task_runner.active = True
        browser.upload_selected_local_entries()
        browser.download_selected_remote_entries()
        browser.delete_selected_remote_entries()
        browser.create_new_remote_directory()
        browser.create_new_local_directory()

        browser._task_runner.active = False
        browser.local_entries = []
        browser.local_tree = MagicMock()
        browser.local_tree.selection.return_value = ()
        browser.remote_tree = MagicMock()
        browser.remote_tree.selection.return_value = ()
        browser.remote_directory_var = MagicMock()
        browser.remote_directory_var.get.return_value = "/APM/LOGS/"
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(tmp_path)
        browser.parameter_editor = MagicMock()

        browser.upload_selected_local_entries()
        browser.local_entries = [LocalFileEntry("file.bin", tmp_path / "file.bin", 1)]
        browser.local_tree.selection.return_value = ("0",)
        browser.remote_directory_var.get.return_value = "../unsafe"
        browser.upload_selected_local_entries()

        browser.download_selected_remote_entries()
        browser.remote_entries = [FlightControllerLogFile("file.bin", "/APM/LOGS/file.bin", 1)]
        browser.remote_tree.selection.return_value = ("0",)
        browser.local_directory_var.get.return_value = str(tmp_path / "removed")
        browser.download_selected_remote_entries()

        assert browser.parameter_editor.upload_file_to_fc.call_count == 0
        assert browser.parameter_editor.download_remote_file.call_count == 0
        assert browser.parameter_editor.delete_remote_path.call_count == 0
        assert browser.ui.show_error.call_count == 2

    def test_directory_creation_validates_names_destinations_and_failures(
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """
        Directory creation validates user input before changing local or remote state.

        GIVEN: The user enters empty, unsafe, invalid, existing, or unwritable targets
        WHEN: Local and remote directory creation is requested
        THEN: Unsafe requests are rejected before any backend call
        AND: Filesystem and remote creation failures are reported
        """
        browser.root = MagicMock()
        browser.remote_directory_var = MagicMock()
        browser.remote_directory_var.get.side_effect = ["relative", "/APM/LOGS/"]
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.make_remote_directory.return_value = False
        browser.ui.askstring.side_effect = [
            None,
            "../bad",
            "remote-folder",
            "remote-folder-2",
            "local-folder",
            "../bad",
            "existing",
            "blocked",
        ]
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.side_effect = [str(tmp_path / "missing"), str(tmp_path), str(tmp_path), str(tmp_path)]
        (tmp_path / "existing").mkdir()

        browser.create_new_remote_directory()
        browser.create_new_remote_directory()
        browser.create_new_remote_directory()
        browser.create_new_remote_directory()
        browser.create_new_local_directory()
        browser.create_new_local_directory()
        browser.create_new_local_directory()
        with patch("pathlib.Path.mkdir", side_effect=OSError("permission denied")):
            browser.create_new_local_directory()

        assert browser.parameter_editor.make_remote_directory.call_count == 1
        assert browser.ui.show_error.call_count == 7

    def test_remote_directory_creation_failure_is_reported_without_refresh(self, browser: FileBrowserWindow) -> None:
        """
        A remote mkdir failure does not make the directory appear successful.

        GIVEN: The user requests a valid remote directory name
        WHEN: MAVFTP rejects the directory creation
        THEN: A creation error is shown
        AND: The remote listing is not refreshed as if the directory existed
        """
        browser.root = MagicMock()
        browser.remote_directory_var = MagicMock()
        browser.remote_directory_var.get.return_value = "/APM/LOGS/"
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.make_remote_directory.return_value = False
        browser.ui.askstring.return_value = "new-folder"
        browser._start_background_operation = MagicMock(side_effect=_run_background_operation)
        browser.refresh_remote_panel = MagicMock()

        browser.create_new_remote_directory()

        browser.ui.show_error.assert_called_once()
        browser.refresh_remote_panel.assert_not_called()

    def test_user_can_rename_and_delete_local_entries(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """
        Local rename and delete keep the visible filesystem and summaries in sync.

        GIVEN: The local panel selects one file and the user tries invalid and valid names
        WHEN: The user renames the file and then deletes it
        THEN: Unsafe and conflicting names are rejected
        AND: The valid rename and delete change the filesystem and refresh the panel
        """
        original = tmp_path / "original.bin"
        original.write_bytes(b"data")
        existing = tmp_path / "existing.bin"
        existing.write_bytes(b"keep")
        browser.local_directory_var = MagicMock()
        browser.local_directory_var.get.return_value = str(tmp_path)
        browser.local_tree = MagicMock()
        browser.local_tree.selection.return_value = ("0",)
        browser.local_entries = [LocalFileEntry("original.bin", original, 4)]
        browser.refresh_local_panel = MagicMock()
        browser.ui.askstring.side_effect = ["../unsafe", "renamed.bin", "existing.bin"]
        browser.ui.ask_yesno.return_value = True

        browser.rename_selected_local_entry()
        browser.rename_selected_local_entry()
        browser.rename_selected_local_entry()
        browser.local_entries = [LocalFileEntry("renamed.bin", tmp_path / "renamed.bin", 4)]
        browser.delete_selected_local_entries()

        assert not original.exists()
        assert not (tmp_path / "renamed.bin").exists()
        assert existing.exists()
        assert browser.ui.show_error.call_count == 2
        assert browser.ui.show_info.call_count == 2
        assert browser.refresh_local_panel.call_count == 2

        with patch("pathlib.Path.rename", side_effect=OSError("read-only filesystem")):
            assert browser._rename_local_entry(LocalFileEntry("existing.bin", existing, 4), "failed.bin") is False
        browser.ui.show_error.assert_called_with("Rename error", "read-only filesystem")

    def test_user_can_rename_and_delete_remote_entries(self, browser: FileBrowserWindow) -> None:
        """
        Remote rename and delete use MAVFTP results before refreshing the panel.

        GIVEN: One remote file is selected
        WHEN: The user rejects an unsafe rename, then retries a failed and a successful rename,
        AND: deletes the selected remote file
        THEN: Each outcome is reported and the remote panel is refreshed after completed work
        """
        entry = FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 12)
        browser.remote_entries = [entry]
        browser.remote_tree = MagicMock()
        browser.remote_tree.selection.return_value = ("0",)
        browser.parameter_editor = MagicMock()
        browser.parameter_editor.rename_remote_path.side_effect = [False, True]
        browser.parameter_editor.delete_remote_path.return_value = True
        browser.ui.askstring.side_effect = ["../unsafe", "failed.bin", "renamed.bin"]
        browser.ui.ask_yesno.return_value = True
        browser._start_background_operation = MagicMock(side_effect=_run_background_operation)
        browser.refresh_remote_panel = MagicMock()

        browser.rename_selected_remote_entry()
        browser.rename_selected_remote_entry()
        browser.rename_selected_remote_entry()
        browser.delete_selected_remote_entries()

        assert browser.parameter_editor.rename_remote_path.call_count == 2
        browser.parameter_editor.delete_remote_path.assert_called_once_with(entry.remote_path, False)  # noqa: FBT003
        assert browser.ui.show_error.call_count == 2
        assert browser.ui.show_info.call_count == 2
        assert browser.refresh_remote_panel.call_count == 2

    def test_keyboard_navigation_and_double_clicks_follow_the_selected_panel(  # noqa: PLR0915  # pylint: disable=too-many-statements
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """
        Keyboard and pointer navigation operate on the panel the user interacted with.

        GIVEN: Both panels contain a parent row and usable entries
        WHEN: The user clicks, selects, double-clicks, focuses, and invokes panel shortcuts
        THEN: Directory double-clicks navigate while file double-clicks open files
        AND: Delete/rename/select-all shortcuts are routed to the active panel
        """
        remote_directory = FlightControllerLogFile("logs", "/APM/LOGS/logs", 0, is_directory=True)
        remote_file = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 4)
        local_directory = tmp_path / "folder"
        local_directory.mkdir()
        local_file = tmp_path / "log.bin"
        local_file.write_bytes(b"log")
        browser.remote_entries = [remote_directory, remote_file]
        browser.local_entries = [
            LocalFileEntry("folder", local_directory, 0, is_directory=True),
            LocalFileEntry("log.bin", local_file, 3),
        ]
        browser.remote_tree = MagicMock()
        browser.local_tree = MagicMock()
        browser.remote_tree.identify_row.return_value = "0"
        browser.local_tree.identify_row.side_effect = ["0", "1", "1"]
        browser.remote_tree.selection.return_value = ("0",)
        browser.local_tree.selection.return_value = ("1",)
        browser.remote_tree.focus.return_value = "0"
        browser.local_tree.focus.return_value = "1"
        browser.remote_directory_var = MagicMock()
        browser.local_directory_var = MagicMock()
        browser.refresh_remote_panel = MagicMock()
        browser.refresh_local_panel = MagicMock()
        browser._open_local_file = MagicMock()
        browser.delete_selected_remote_entries = MagicMock()
        browser.delete_selected_local_entries = MagicMock()
        browser._start_inline_rename = MagicMock()
        browser._update_transfer_buttons = MagicMock()
        browser.remote_tree.get_children.return_value = ("0", "1")
        browser.remote_tree.item.side_effect = lambda item_id, _option: ("..",) if item_id == "0" else ("logs",)
        browser.local_tree.get_children.return_value = ("0", "1")
        browser.local_tree.item.side_effect = lambda item_id, _option: ("folder",) if item_id == "0" else ("log.bin",)

        event = MagicMock(y=10, widget=browser.remote_tree)
        browser._on_remote_double_click(event)
        browser._remember_panel_from_click("remote", event)
        browser._remember_panel_from_selection("remote")
        browser._on_delete_key(event)
        browser._on_rename_key(event)
        browser.select_all_remote_entries()
        browser._on_select_all_key(MagicMock(widget=browser.remote_tree))

        local_event = MagicMock(y=10, widget=browser.local_tree)
        browser._on_local_double_click(local_event)
        browser._on_local_double_click(local_event)
        browser._remember_panel_from_click("local", local_event)
        browser._remember_panel_from_selection("local")
        browser._on_delete_key(local_event)
        browser._on_rename_key(local_event)
        browser.select_all_local_entries()
        browser._on_select_all_key(local_event)

        browser._focus_panel("remote")
        browser.remote_tree.selection.return_value = ()
        browser.remote_tree.item.side_effect = [{"values": ("..",)}, {"values": ("logs",)}]
        browser._focus_panel("remote")
        browser.navigate_remote_parent = MagicMock()
        browser._on_backspace(MagicMock(widget=browser.remote_tree))
        browser.navigate_local_parent = MagicMock()
        browser._on_backspace(MagicMock(widget=browser.local_tree))

        assert browser.remote_directory_var.set.call_count == 1
        assert browser.local_directory_var.set.call_count == 1
        browser._open_local_file.assert_called_once()
        assert browser.remote_tree.selection_set.call_count >= 2
        assert browser.local_tree.selection_set.call_count >= 1

    def test_user_can_sort_and_review_mixed_file_browser_entries(self, browser: FileBrowserWindow) -> None:
        """
        Sorting and rendering preserve meaningful values for files and directories.

        GIVEN: A panel contains parent, directory, and file entries with varied metadata
        WHEN: The user sorts by size, modified time, type, and name
        THEN: The browser moves rows using the corresponding stable keys
        AND: Unsupported, missing, and malformed timestamps render safely
        """
        entries = [
            FlightControllerLogFile("..", "/", 0, is_directory=True),
            FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True, modified_at=None),
            FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12, modified_at=1),
        ]
        browser.remote_entries = entries
        browser.remote_tree = MagicMock()
        browser.remote_tree.get_children.return_value = ("0", "1", "2")
        browser.remote_sort_column = ""
        browser.remote_sort_reverse = False

        browser._sort_panel_by_column("remote", "size", False)  # noqa: FBT003
        browser._sort_panel_by_column("remote", "modified", False)  # noqa: FBT003
        browser._sort_panel_by_column("remote", "type", False)  # noqa: FBT003
        browser._sort_panel_by_column("remote", "name", True)  # noqa: FBT003
        browser._reset_tree_headings(browser.remote_tree, "remote")

        for call_args in browser.remote_tree.heading.call_args_list:
            command = call_args.kwargs.get("command")
            if command is not None:
                command()
                break

        assert FileBrowserWindow._format_modified_time(-1) == "-"
        assert FileBrowserWindow._format_modified_time(float("inf")) == "-"
        assert FileBrowserWindow._format_modified_time(None, unsupported_when_missing=True) == "Unsupported"
        assert FileBrowserWindow._panel_sort_key(entries, "bad", "name") == (0, 0, "")
        assert FileBrowserWindow._first_selectable_tree_item(MagicMock(get_children=MagicMock(return_value=()))) is None

    def test_transfer_engine_reports_mavftp_and_filesystem_failures_without_aborting(  # pylint: disable=too-many-locals
        self, tmp_path: Path
    ) -> None:
        """
        Transfer planning and execution keep failures attributable to their entries.

        GIVEN: Remote listings, local directories, transfers, and verification can fail independently
        WHEN: The user starts mixed upload/download/delete work
        THEN: Unsafe, unavailable, and failed operations become retryable results
        AND: One failure does not abort the remaining batch
        """
        destination = tmp_path / "destination"
        destination.mkdir()
        unsafe = FlightControllerLogFile("../unsafe", "/APM/LOGS/../unsafe", 1)
        assert _build_remote_download_plan([unsafe], destination, MagicMock()).failed == (unsafe.remote_path,)

        broken_directory = FlightControllerLogFile("broken", "/APM/LOGS/broken", 0, is_directory=True)
        listing = MagicMock(side_effect=RuntimeError("MAVFTP listing failed"))
        assert _build_remote_download_plan([broken_directory], destination, listing).failed == (broken_directory.remote_path,)

        file_entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 5)
        blocked_target = destination / "blocked"
        blocked_target.write_text("not a directory", encoding="utf-8")
        blocked_plan = RemoteDownloadPlan(
            (blocked_target,),
            ((file_entry, blocked_target / file_entry.name),),
        )
        succeeded, failed = _download_remote_plan_worker(blocked_plan, destination, 5, MagicMock(), MagicMock())
        assert not succeeded
        assert failed == [str(blocked_target), file_entry.remote_path]

        mkdir_error_plan = RemoteDownloadPlan((destination / "mkdir-error",), ())
        with patch("pathlib.Path.mkdir", side_effect=OSError("disk full")):
            _succeeded, mkdir_failures = _download_remote_plan_worker(
                mkdir_error_plan, destination, 0, MagicMock(), MagicMock()
            )
        assert mkdir_failures == [str(destination / "mkdir-error")]

        download_error = MagicMock(side_effect=RuntimeError("download failed"))
        valid_plan = RemoteDownloadPlan((), ((file_entry, destination / file_entry.name),))
        _succeeded, download_failures = _download_remote_plan_worker(valid_plan, destination, 5, download_error, MagicMock())
        assert download_failures == [file_entry.remote_path]

        verify_error = MagicMock(side_effect=RuntimeError("CRC unavailable"))
        _succeeded, verification_failures = _download_remote_plan_worker(
            valid_plan,
            destination,
            5,
            MagicMock(return_value=True),
            MagicMock(),
            verify_remote_file=verify_error,
        )
        assert verification_failures == [file_entry.remote_path]

        local_file = destination / "upload.bin"
        local_file.write_bytes(b"upload")
        upload_plan = LocalUploadPlan(
            ("/APM/LOGS/folder",),
            ((local_file, "/APM/LOGS/folder/upload.bin", 6),),
        )
        _succeeded, upload_failures = _upload_local_plan_worker(
            upload_plan, 6, MagicMock(side_effect=RuntimeError("mkdir failed")), MagicMock(), MagicMock()
        )
        assert upload_failures == ["/APM/LOGS/folder", "/APM/LOGS/folder/upload.bin"]

        verification_results: dict[str, bool | None] = {}
        _succeeded, upload_verification_failures = _upload_local_plan_worker(
            LocalUploadPlan((), ((local_file, "/APM/LOGS/upload.bin", 6),)),
            6,
            MagicMock(return_value=True),
            MagicMock(return_value=True),
            MagicMock(),
            verify_remote_file=MagicMock(side_effect=RuntimeError("CRC unavailable")),
            verification_results=verification_results,
        )
        assert upload_verification_failures == ["/APM/LOGS/upload.bin"]
        assert verification_results["/APM/LOGS/upload.bin"] is False

        unreadable = LocalFileEntry("unreadable", destination / "unreadable", 0, is_directory=True)
        with patch("pathlib.Path.iterdir", side_effect=OSError("permission denied")):
            plan = _build_local_upload_plan([unreadable], "/APM/LOGS")
        assert plan.failed == ("/APM/LOGS/unreadable",)

        remote_directory = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        remote_file = FlightControllerLogFile("file.bin", "/APM/LOGS/file.bin", 1)
        succeeded, delete_failures = _delete_remote_entries_worker(
            [remote_directory, remote_file],
            MagicMock(side_effect=RuntimeError("listing failed")),
            MagicMock(return_value=False),
        )
        assert not succeeded
        assert delete_failures == [remote_directory.remote_path, remote_file.remote_path]
