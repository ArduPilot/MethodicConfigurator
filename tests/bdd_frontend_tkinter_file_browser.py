#!/usr/bin/env python3

"""
User workflows for the MAVFTP file browser with an in-memory controller.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import posixpath
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
from ardupilot_methodic_configurator.frontend_tkinter_file_browser import FileBrowserWindow, _PanelState

if TYPE_CHECKING:
    from collections.abc import Callable

# pylint: disable=protected-access, redefined-outer-name


class Value:
    """The small part of a Tk variable used by the browser."""

    def __init__(self, value: str | bool) -> None:
        self.value = value

    def get(self) -> str | bool:
        return self.value

    def set(self, value: str | bool) -> None:
        self.value = value


class Widget:
    """Keep visible widget text and enabled state without a display server."""

    def __init__(self) -> None:
        self.text = ""
        self.enabled = True

    def configure(self, **options: str) -> None:
        self.text = options.get("text", self.text)
        if "state" in options:
            self.enabled = options["state"] != "disabled"

    def state(self, flags: list[str]) -> None:
        self.enabled = "disabled" not in flags


class Tree(Widget):
    """Hold the Treeview rows and selection that drive user actions."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[str, tuple[str, ...]] = {}
        self.selected: tuple[str, ...] = ()
        self.focused = ""
        self.headings: dict[str, Callable[[], None]] = {}

    def get_children(self, _parent: str = "") -> tuple[str, ...]:
        return tuple(self.rows)

    def delete(self, item_id: str) -> None:
        self.rows.pop(item_id)

    def insert(self, _parent: str, _position: str, *, iid: str, values: tuple[str, ...]) -> None:
        self.rows[iid] = values

    def item(self, item_id: str, option: str | None = None) -> tuple[str, ...] | dict[str, tuple[str, ...]]:
        return self.rows[item_id] if option == "values" else {"values": self.rows[item_id]}

    def selection(self) -> tuple[str, ...]:
        return self.selected

    def selection_set(self, item_id: str | list[str]) -> None:
        self.selected = tuple(item_id) if isinstance(item_id, list) else (item_id,)

    def focus(self, item_id: str | None = None) -> str:
        if item_id is not None:
            self.focused = item_id
        return self.focused

    def see(self, _item_id: str) -> None:
        return

    def heading(self, column: str, **options: object) -> None:
        command = options.get("command")
        if callable(command):
            self.headings[column] = command

    def move(self, item_id: str, _parent: str, position: int) -> None:
        rows = list(self.rows.items())
        row = next(row for row in rows if row[0] == item_id)
        rows.remove(row)
        rows.insert(position, row)
        self.rows = dict(rows)

    def names(self) -> list[str]:
        return [values[0] for values in self.rows.values()]

    def select_name(self, name: str) -> None:
        self.selected = (next(item_id for item_id, values in self.rows.items() if values[0] == name),)


class Progress:
    """Capture progress-window lifecycle while running real task code."""

    def __init__(self) -> None:
        self.updates: list[tuple[int, int]] = []
        self.destroyed = False

    def update_progress_bar(self, current: int, total: int) -> None:
        self.updates.append((current, total))

    def destroy(self) -> None:
        self.destroyed = True


class Ui:
    """Provide scripted dialog decisions and retain user-visible messages."""

    def __init__(self) -> None:
        self.yesno_answers: list[bool] = []
        self.string_answers: list[str | None] = []
        self.errors: list[tuple[str, str]] = []
        self.infos: list[tuple[str, str]] = []
        self.progress: list[Progress] = []

    def ask_yesno(self, _title: str, _message: str) -> bool:
        return self.yesno_answers.pop(0)

    def askstring(self, _title: str, _message: str, **_options: object) -> str | None:
        return self.string_answers.pop(0)

    def show_error(self, title: str, message: str) -> None:
        self.errors.append((title, message))

    def show_info(self, title: str, message: str) -> None:
        self.infos.append((title, message))

    def create_progress_window(self, *_args: object) -> Progress:
        progress = Progress()
        self.progress.append(progress)
        return progress


class MemoryMavftp:  # pylint: disable=too-many-instance-attributes
    """Implement the browser's MAVFTP boundary with real byte content."""

    def __init__(self) -> None:
        self.directories = {"/", "/APM", "/APM/LOGS"}
        self.files: dict[str, bytes] = {}
        self.unreadable: set[str] = set()
        self.verification_failures: set[str] = set()
        self.mkdir_failures: dict[str, int] = {}
        self.download_failures: dict[str, int] = {}
        self.mkdir_attempts: list[str] = []
        self.download_attempts: list[str] = []
        self.upload_attempts: list[str] = []
        self.delete_attempts: list[str] = []

    def get_remote_files(self, directory: str) -> list[FlightControllerLogFile] | None:
        directory = posixpath.normpath(directory)
        if directory in self.unreadable:
            message = "MAVFTP listing denied"
            raise PermissionError(message)
        if directory not in self.directories:
            return None
        entries = [
            FlightControllerLogFile(posixpath.basename(path), path, 0, is_directory=True)
            for path in self.directories
            if path != directory and posixpath.dirname(path) == directory
        ]
        entries.extend(
            FlightControllerLogFile(posixpath.basename(path), path, len(content))
            for path, content in self.files.items()
            if posixpath.dirname(path) == directory
        )
        return sorted(entries, key=lambda entry: entry.name)

    def make_remote_directory(self, directory: str) -> bool:
        self.mkdir_attempts.append(directory)
        remaining = self.mkdir_failures.get(directory, 0)
        if remaining:
            self.mkdir_failures[directory] = remaining - 1
            return False
        if posixpath.dirname(directory) not in self.directories:
            return False
        self.directories.add(directory)
        return True

    def upload_file_to_fc(self, local: str, remote: str, progress: Callable[[int, int], None]) -> bool:
        self.upload_attempts.append(remote)
        if posixpath.dirname(remote) not in self.directories:
            return False
        content = Path(local).read_bytes()
        self.files[remote] = content
        progress(len(content), len(content))
        return True

    def download_remote_file(self, remote: str, local: str, progress: Callable[[int, int], None]) -> bool:
        self.download_attempts.append(remote)
        remaining = self.download_failures.get(remote, 0)
        if remaining:
            self.download_failures[remote] = remaining - 1
            return False
        content = self.files[remote]
        Path(local).write_bytes(content)
        progress(len(content), len(content))
        return True

    def verify_remote_file(self, remote: str, local: str) -> bool:
        return remote not in self.verification_failures and self.files[remote] == Path(local).read_bytes()

    def delete_remote_path(self, path: str, is_directory: bool) -> bool:
        self.delete_attempts.append(path)
        if is_directory:
            if any(posixpath.dirname(child) == path for child in self.directories | self.files.keys()):
                return False
            self.directories.remove(path)
        else:
            self.files.pop(path)
        return True

    def rename_remote_path(self, old: str, new: str) -> bool:
        if old not in self.files or new in self.files:
            return False
        self.files[new] = self.files.pop(old)
        return True


class SynchronousTaskRunner:  # pylint: disable=too-few-public-methods
    """Run production task and completion code while preserving the busy boundary."""

    def __init__(self) -> None:
        self.active = False

    def start(
        self,
        task: Callable[[Callable[[int, int], None]], object],
        on_progress: Callable | None,
        on_done: Callable,
    ) -> bool:
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
def browser(tmp_path: Path) -> FileBrowserWindow:
    """Create a browser with real operations and only external boundaries replaced."""
    window = FileBrowserWindow.__new__(FileBrowserWindow)
    window._task_runner = SynchronousTaskRunner()
    window._local_task_runner = SynchronousTaskRunner()
    window._local_refresh_request = None
    window._all_controls_locked = False
    window._panel_states = {"remote": _PanelState(), "local": _PanelState()}
    window.verify_transfers_var = Value(value=False)
    window.remote_directory_var = Value("/APM/LOGS")
    window.local_directory_var = Value(str(tmp_path))
    window._last_listed_remote_directory = None
    window.last_selected_panel = "remote"
    window._panel_navigation_enabled = True
    window.remote_entries = []
    window.local_entries = []
    window.remote_tree = Tree()
    window.local_tree = Tree()
    window.remote_directory_label = Widget()
    window.local_directory_label = Widget()
    window.remote_empty_state_label = Widget()
    window.local_empty_state_label = Widget()
    window.remote_parent_button = Widget()
    window.local_parent_button = Widget()
    window.download_button = Widget()
    window.upload_button = Widget()
    window.ui = Ui()
    window.parameter_editor = MemoryMavftp()
    window.root = object()
    return window


class TestFileBrowserUserWorkflows:
    """Check results users can see and bytes that MAVFTP would transfer."""

    def test_local_browse_works_during_remote_listing(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """A remote task leaves local browsing available without unlocking transfer controls."""
        local = tmp_path / "vehicle"
        local.mkdir()
        (local / "flight.bin").write_bytes(b"flight")
        browser.local_directory_var.set(str(local))
        browser.download_button.enabled = False
        browser.upload_button.enabled = False
        browser._task_runner.active = True

        browser.refresh_local_panel()

        assert browser.local_tree.names() == ["flight.bin"]
        assert browser.local_directory_label.text == f"Local files in {local}"
        assert not browser.download_button.enabled
        assert not browser.upload_button.enabled

    def test_failed_remote_listing_preserves_rows_and_upload_destination(self, browser: FileBrowserWindow) -> None:
        """A listing error restores the last directory whose rows are on screen."""
        browser.parameter_editor.files["/APM/LOGS/old.bin"] = b"old"
        browser.refresh_remote_panel()
        browser.parameter_editor.unreadable.add("/APM/LOGS/blocked")
        browser.remote_directory_var.set("/APM/LOGS/blocked")

        browser.refresh_remote_panel()

        assert browser.remote_tree.names() == ["old.bin"]
        assert browser.remote_directory_var.get() == "/APM/LOGS"
        assert browser.remote_directory_label.text == "Remote files in /APM/LOGS"
        assert browser.ui.errors == [("Remote directory error", "MAVFTP listing denied")]

    def test_missing_remote_listing_preserves_last_successful_directory(self, browser: FileBrowserWindow) -> None:
        """A MAVFTP None response is an error, not an empty directory."""
        browser.parameter_editor.files["/APM/LOGS/old.bin"] = b"old"
        browser.refresh_remote_panel()
        browser.remote_directory_var.set("/APM/LOGS/missing")

        browser.refresh_remote_panel()

        assert browser.remote_tree.names() == ["old.bin"]
        assert browser.remote_directory_var.get() == "/APM/LOGS"
        assert browser.ui.errors == [("Remote directory error", "Could not list the remote directory.")]

    def test_missing_local_directory_keeps_existing_rows(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """A deleted local destination does not replace cached rows with an empty listing."""
        (tmp_path / "old.bin").write_bytes(b"old")
        browser.refresh_local_panel()
        browser.local_directory_var.set(str(tmp_path / "removed"))

        browser.refresh_local_panel()

        assert browser.local_tree.names() == ["old.bin"]
        assert browser.ui.errors == [("Local directory error", "The selected local directory does not exist.")]

    def test_upload_retry_creates_remote_tree_and_clears_directory_failure(
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """A failed mkdir is retried, and file bytes appear at the expected MAVFTP path."""
        folder = tmp_path / "folder"
        nested = folder / "nested"
        nested.mkdir(parents=True)
        (nested / "a.bin").write_bytes(b"ArduPilot log")
        browser.parameter_editor.mkdir_failures["/APM/LOGS/folder"] = 1
        browser.ui.yesno_answers = [True, True]  # Confirm upload, then retry.
        browser.refresh_local_panel()
        browser.local_tree.select_name("folder")

        browser.upload_selected_local_entries()

        assert browser.parameter_editor.mkdir_attempts.count("/APM/LOGS/folder") == 2
        assert browser.parameter_editor.files["/APM/LOGS/folder/nested/a.bin"] == b"ArduPilot log"
        assert browser.parameter_editor.upload_attempts == ["/APM/LOGS/folder/nested/a.bin"]
        assert "Failed: /APM/LOGS/folder" in browser.ui.errors[0][1]
        assert "Failed:" not in browser.ui.infos[-1][1]
        assert "Succeeded: /APM/LOGS/folder/nested/a.bin" in browser.ui.infos[-1][1]
        assert all(progress.destroyed for progress in browser.ui.progress)

    def test_download_retry_writes_file_and_preserves_directory_success(
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """A failed first transfer is retried once and writes the expected local bytes."""
        browser.parameter_editor.directories.add("/APM/LOGS/folder")
        remote = "/APM/LOGS/folder/a.bin"
        browser.parameter_editor.files[remote] = b"downloaded log"
        browser.parameter_editor.download_failures[remote] = 1
        browser.ui.yesno_answers = [True]
        browser.refresh_remote_panel()
        browser.remote_tree.select_name("folder")

        browser.download_selected_remote_entries()

        assert (tmp_path / "folder" / "a.bin").read_bytes() == b"downloaded log"
        assert browser.parameter_editor.download_attempts == [remote, remote]
        assert f"Failed: {remote}" in browser.ui.errors[0][1]
        assert "Succeeded: /APM/LOGS/folder/a.bin" in browser.ui.infos[-1][1]
        assert "Failed:" not in browser.ui.infos[-1][1]
        assert browser.local_tree.names() == ["folder"]

    def test_declined_download_overwrite_keeps_existing_bytes(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """Preflight asks before replacing a local file and honours a refusal."""
        remote = "/APM/LOGS/log.bin"
        browser.parameter_editor.files[remote] = b"remote"
        (tmp_path / "log.bin").write_bytes(b"local")
        browser.ui.yesno_answers = [False]
        browser.refresh_remote_panel()
        browser.remote_tree.select_name("log.bin")

        browser.download_selected_remote_entries()

        assert (tmp_path / "log.bin").read_bytes() == b"local"
        assert browser.parameter_editor.download_attempts == []
        assert browser.ui.errors == []

    def test_failed_crc_is_reported_even_after_upload_writes_bytes(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """A transferred file does not appear verified when MAVFTP checksum fails."""
        remote = "/APM/LOGS/log.bin"
        (tmp_path / "log.bin").write_bytes(b"log")
        browser.parameter_editor.verification_failures.add(remote)
        browser.verify_transfers_var.set(True)
        browser.ui.yesno_answers = [True, False]  # Confirm upload, decline retry.
        browser.refresh_local_panel()
        browser.local_tree.select_name("log.bin")

        browser.upload_selected_local_entries()

        assert browser.parameter_editor.files[remote] == b"log"
        assert browser.parameter_editor.upload_attempts == [remote]
        assert f"Not verified: {remote}" in browser.ui.errors[-1][1]

    def test_unreadable_remote_directory_cannot_be_deleted(self, browser: FileBrowserWindow) -> None:
        """MAVFTP listing failure leaves the remote directory untouched."""
        remote = "/APM/LOGS/folder"
        browser.parameter_editor.directories.add(remote)
        browser.refresh_remote_panel()
        browser.remote_tree.select_name("folder")
        browser.parameter_editor.unreadable.add(remote)
        browser.ui.yesno_answers = [True]

        browser.delete_selected_remote_entries()

        assert remote in browser.parameter_editor.directories
        assert browser.parameter_editor.delete_attempts == []
        assert f"Failed: {remote}" in browser.ui.errors[-1][1]

    def test_nonempty_remote_directory_cannot_be_deleted(self, browser: FileBrowserWindow) -> None:
        """MAVFTP never receives rmdir while a directory still contains a log."""
        remote = "/APM/LOGS/folder"
        browser.parameter_editor.directories.add(remote)
        browser.parameter_editor.files[f"{remote}/log.bin"] = b"log"
        browser.ui.yesno_answers = [True]
        browser.refresh_remote_panel()
        browser.remote_tree.select_name("folder")

        browser.delete_selected_remote_entries()

        assert remote in browser.parameter_editor.directories
        assert browser.parameter_editor.delete_attempts == []
        assert f"Failed: {remote}" in browser.ui.errors[-1][1]

    def test_local_create_rename_delete_changes_filesystem(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """Local actions refresh rows and keep the real filesystem in sync."""
        (tmp_path / "original.bin").write_bytes(b"original")
        browser.ui.string_answers = ["new-folder", "renamed.bin"]
        browser.ui.yesno_answers = [True]
        browser.refresh_local_panel()

        browser.create_new_local_directory()
        browser.local_tree.select_name("original.bin")
        browser.rename_selected_local_entry()
        browser.local_tree.select_name("renamed.bin")
        browser.delete_selected_local_entries()

        assert (tmp_path / "new-folder").is_dir()
        assert not (tmp_path / "original.bin").exists()
        assert not (tmp_path / "renamed.bin").exists()
        assert browser.local_tree.names() == ["new-folder"]
        assert browser.ui.errors == []
        assert [title for title, _message in browser.ui.infos] == [
            "New directory summary",
            "Rename summary",
            "Local delete summary",
        ]

    def test_remote_create_rename_delete_changes_mavftp_state(self, browser: FileBrowserWindow) -> None:
        """Remote actions update the next MAVFTP listing and the stored bytes."""
        browser.parameter_editor.files["/APM/LOGS/old.bin"] = b"log"
        browser.ui.string_answers = ["new-folder", "renamed.bin"]
        browser.ui.yesno_answers = [True]
        browser.refresh_remote_panel()

        browser.create_new_remote_directory()
        browser.remote_tree.select_name("old.bin")
        browser.rename_selected_remote_entry()
        browser.remote_tree.select_name("renamed.bin")
        browser.delete_selected_remote_entries()

        assert "/APM/LOGS/new-folder" in browser.parameter_editor.directories
        assert browser.parameter_editor.files == {}
        assert browser.remote_tree.names() == ["new-folder"]
        assert browser.ui.errors == []
        assert [title for title, _message in browser.ui.infos] == [
            "New directory summary",
            "Rename summary",
            "Remote delete summary",
        ]

    def test_upload_uses_the_remote_directory_currently_shown_in_the_panel(
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """Typing a different path without listing it cannot redirect an upload."""
        (tmp_path / "log.bin").write_bytes(b"log")
        browser.parameter_editor.directories.add("/APM/SCRIPTS")
        browser.parameter_editor.files["/APM/LOGS/old.bin"] = b"old"
        browser.refresh_remote_panel()
        browser.refresh_local_panel()
        browser.local_tree.select_name("log.bin")
        browser.remote_directory_var.set("/APM/SCRIPTS")
        browser.ui.yesno_answers = [True]

        browser.upload_selected_local_entries()

        assert browser.parameter_editor.upload_attempts == ["/APM/LOGS/log.bin"]
        assert browser.parameter_editor.files["/APM/LOGS/log.bin"] == b"log"
        assert "/APM/SCRIPTS/log.bin" not in browser.parameter_editor.files
        assert browser.remote_directory_label.text == "Remote files in /APM/LOGS/"
        assert browser.remote_tree.names() == ["log.bin", "old.bin"]

    def test_remote_directory_is_created_under_the_directory_currently_shown(self, browser: FileBrowserWindow) -> None:
        """Typing a different path cannot redirect the New directory action."""
        browser.refresh_remote_panel()
        browser.remote_directory_var.set("/APM")
        browser.ui.string_answers = ["newdir"]

        browser.create_new_remote_directory()

        assert browser.parameter_editor.mkdir_attempts == ["/APM/LOGS/newdir"]
        assert "/APM/LOGS/newdir" in browser.parameter_editor.directories
        assert "/APM/newdir" not in browser.parameter_editor.directories
        assert browser.remote_directory_var.get() == "/APM/LOGS/"
        assert browser.remote_directory_label.text == "Remote files in /APM/LOGS/"

    def test_invalid_upload_destination_never_reaches_mavftp(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """An unsafe destination rejects the transfer before reading local bytes."""
        (tmp_path / "log.bin").write_bytes(b"log")
        browser.refresh_local_panel()
        browser.local_tree.select_name("log.bin")
        browser.remote_directory_var.set("/APM/LOGS/../../etc")

        browser.upload_selected_local_entries()

        assert browser.parameter_editor.upload_attempts == []
        assert browser.parameter_editor.files == {}
        assert browser.ui.errors == [("Upload error", "Remote path must not contain parent-directory segments")]

    def test_unsafe_directory_names_do_not_change_local_or_remote_tree(
        self, browser: FileBrowserWindow, tmp_path: Path
    ) -> None:
        """A name containing a parent component is rejected on both sides."""
        browser.ui.string_answers = ["../outside", "../outside"]
        browser.refresh_local_panel()
        browser.refresh_remote_panel()

        browser.create_new_local_directory()
        browser.create_new_remote_directory()

        assert not (tmp_path.parent / "outside").exists()
        assert browser.local_tree.names() == []
        assert browser.remote_tree.names() == []
        assert browser.parameter_editor.mkdir_attempts == []
        assert [title for title, _message in browser.ui.errors] == ["New directory error", "New directory error"]

    def test_local_rename_collision_keeps_both_files(self, browser: FileBrowserWindow, tmp_path: Path) -> None:
        """Renaming over an existing local entry reports an error and preserves bytes."""
        (tmp_path / "first.bin").write_bytes(b"first")
        (tmp_path / "second.bin").write_bytes(b"second")
        browser.ui.string_answers = ["second.bin"]
        browser.refresh_local_panel()
        browser.local_tree.select_name("first.bin")

        browser.rename_selected_local_entry()

        assert (tmp_path / "first.bin").read_bytes() == b"first"
        assert (tmp_path / "second.bin").read_bytes() == b"second"
        assert browser.local_tree.names() == ["first.bin", "second.bin"]
        assert browser.ui.errors[0][0] == "Rename error"

    def test_sorting_moves_visible_rows_by_size(self, browser: FileBrowserWindow) -> None:
        """The size heading orders actual rendered rows, then reverses on a second click."""
        browser.parameter_editor.files["/APM/LOGS/small.bin"] = b"a"
        browser.parameter_editor.files["/APM/LOGS/large.bin"] = b"larger"
        browser.refresh_remote_panel()

        browser.remote_tree.headings["size"]()
        assert browser.remote_tree.names() == ["small.bin", "large.bin"]
        browser.remote_tree.headings["size"]()
        assert browser.remote_tree.names() == ["large.bin", "small.bin"]
