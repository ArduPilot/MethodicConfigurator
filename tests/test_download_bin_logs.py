#!/usr/bin/env python3

"""
BDD tests for flight-controller log-file listing and download workflows.

This file is part of ArduPilot Methodic Configurator.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, call, patch

from ardupilot_methodic_configurator.backend_flightcontroller_files import (
    FlightControllerFiles,
    FlightControllerLogFile,
)
from ardupilot_methodic_configurator.backend_mavftp import DirectoryEntry
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_download_bin_logs import DownloadBinLogsWindow
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow


def _files_manager() -> FlightControllerFiles:
    """Build a connected MAVFTP-capable file manager for unit tests."""
    connection_manager = MagicMock()
    connection_manager.master = MagicMock()
    connection_manager.info = FlightControllerInfo()
    connection_manager.info.is_mavftp_supported = True
    return FlightControllerFiles(connection_manager=connection_manager)


def _parameter_editor_model() -> ParameterEditor:
    """Build the minimum ParameterEditor state needed by log workflows."""
    model = ParameterEditor.__new__(ParameterEditor)
    model._flight_controller = MagicMock()  # pylint: disable=protected-access
    model._flight_controller.master = MagicMock()  # pylint: disable=protected-access
    model._flight_controller.info.is_mavftp_supported = True  # pylint: disable=protected-access
    return model


class TestFlightControllerLogListing:
    """Verify the user can browse all files in the remote log directory."""

    def test_user_sees_all_regular_files_in_default_log_directory(self) -> None:
        """
        The remote panel lists every regular file, not only numbered BIN logs.

        GIVEN: The FC log directory contains BIN, TXT, and other regular files
        WHEN: The application lists the default log directory
        THEN: All regular files are returned with their remote paths and sizes
        AND: Remote directories are not selectable files
        """
        files_manager = _files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(
            directory_listing=[
                DirectoryEntry("00000012.BIN", is_dir=False, size_b=120),
                DirectoryEntry("LASTLOG.TXT", is_dir=False, size_b=8),
                DirectoryEntry("notes.dat", is_dir=False, size_b=42),
                DirectoryEntry("subdirectory", is_dir=True, size_b=0),
            ]
        )

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            files = files_manager.list_bin_log_files()

        assert files == [
            FlightControllerLogFile(name="00000012.BIN", remote_path="/APM/LOGS/00000012.BIN", size_bytes=120),
            FlightControllerLogFile(name="LASTLOG.TXT", remote_path="/APM/LOGS/LASTLOG.TXT", size_bytes=8),
            FlightControllerLogFile(name="notes.dat", remote_path="/APM/LOGS/notes.dat", size_bytes=42),
        ]
        mavftp.cmd_list.assert_called_once_with(["/APM/LOGS/"])

    def test_user_can_browse_a_remote_directory_selected_in_the_remote_panel(self) -> None:
        """
        The remote destination selector controls which directory is listed.

        GIVEN: The user enters another absolute MAVFTP directory
        WHEN: The remote panel is refreshed
        THEN: The selected directory is passed to the flight-controller backend
        """
        files_manager = _files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(directory_listing=[])

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            files_manager.list_bin_log_files("/APM/LOGS/temperature")

        mavftp.cmd_list.assert_called_once_with(["/APM/LOGS/temperature/"])


class TestParameterEditorLogDownloadWorkflow:
    """Verify selected-file download behavior."""

    def test_user_can_download_multiple_selected_files_after_one_overwrite_confirmation(self) -> None:
        """
        A batch download asks once before replacing existing local files.

        GIVEN: Two remote files are selected and one local target already exists
        WHEN: The user confirms the overwrite prompt
        THEN: Both files are downloaded using their remote basenames
        AND: The overwrite callback is called exactly once
        """
        model = _parameter_editor_model()
        flight_controller = cast("Any", model._flight_controller)  # pylint: disable=protected-access
        local_download_directory = Path("C:/downloads")
        existing_target = local_download_directory / "LASTLOG.TXT"
        selected = [
            FlightControllerLogFile(name="LASTLOG.TXT", remote_path="/APM/LOGS/LASTLOG.TXT", size_bytes=10),
            FlightControllerLogFile(name="00000012.BIN", remote_path="/APM/LOGS/00000012.BIN", size_bytes=100),
        ]
        ask_overwrite = MagicMock(return_value=True)

        with (
            patch.object(Path, "is_dir", return_value=True),
            patch.object(Path, "exists", side_effect=[True, False]),
        ):
            result = model.download_selected_bin_logs_workflow(
                selected_files=selected,
                destination=str(local_download_directory),
                destination_is_directory=True,
                ask_overwrite=ask_overwrite,
                show_error=MagicMock(),
                show_info=MagicMock(),
            )

        assert result.successful == ("LASTLOG.TXT", "00000012.BIN")
        assert result.failed == ()
        ask_overwrite.assert_called_once()
        assert flight_controller.download_bin_log_file.call_count == 2
        flight_controller.download_bin_log_file.assert_any_call("/APM/LOGS/LASTLOG.TXT", str(existing_target), None)
        flight_controller.download_bin_log_file.assert_any_call(
            "/APM/LOGS/00000012.BIN", str(local_download_directory / "00000012.BIN"), None
        )

    def test_user_can_cancel_a_batch_before_any_existing_file_is_overwritten(self) -> None:
        """
        Declining the overwrite prompt cancels the whole batch.

        GIVEN: A selected batch contains an existing local target
        WHEN: The user declines the single overwrite prompt
        THEN: No remote file is downloaded
        """
        model = _parameter_editor_model()
        flight_controller = cast("Any", model._flight_controller)  # pylint: disable=protected-access
        local_download_directory = Path("C:/downloads")
        ask_overwrite = MagicMock(return_value=False)

        with (
            patch.object(Path, "is_dir", return_value=True),
            patch.object(Path, "exists", return_value=True),
        ):
            result = model.download_selected_bin_logs_workflow(
                selected_files=[
                    FlightControllerLogFile(name="LASTLOG.TXT", remote_path="/APM/LOGS/LASTLOG.TXT", size_bytes=10)
                ],
                destination=str(local_download_directory),
                destination_is_directory=True,
                ask_overwrite=ask_overwrite,
                show_error=MagicMock(),
                show_info=MagicMock(),
            )

        assert result.cancelled is True
        flight_controller.download_bin_log_file.assert_not_called()

    def test_batch_continues_after_a_failed_transfer_and_reports_each_file(self) -> None:
        """
        A failed remote file does not stop the remaining batch.

        GIVEN: The first selected remote file fails and the second succeeds
        WHEN: The batch download runs
        THEN: Both transfer attempts are made
        AND: The result summary identifies each file's outcome
        """
        model = _parameter_editor_model()
        flight_controller = cast("Any", model._flight_controller)  # pylint: disable=protected-access
        flight_controller.download_bin_log_file.side_effect = [False, True]
        show_error = MagicMock()
        selected = [
            FlightControllerLogFile("missing.BIN", "/APM/LOGS/missing.BIN", 10),
            FlightControllerLogFile("available.BIN", "/APM/LOGS/available.BIN", 20),
        ]

        with (
            patch.object(Path, "is_dir", return_value=True),
            patch.object(Path, "exists", return_value=False),
        ):
            result = model.download_selected_bin_logs_workflow(
                selected_files=selected,
                destination="C:/downloads",
                destination_is_directory=True,
                ask_overwrite=MagicMock(return_value=True),
                show_error=show_error,
                show_info=MagicMock(),
            )

        assert result.successful == ("available.BIN",)
        assert result.failed == ("missing.BIN",)
        assert flight_controller.download_bin_log_file.call_count == 2
        summary = show_error.call_args.args[1]
        assert "Failed: missing.BIN" in summary
        assert "Downloaded: available.BIN" in summary


class TestDownloadBinLogsWindow:
    """Verify the modal's remote destination selector behavior."""

    def test_remote_refresh_uses_the_selected_destination_directory(self) -> None:
        """
        Refreshing the remote panel uses the path shown in its selector.

        GIVEN: The modal's remote destination selector contains a path
        WHEN: The user presses Open/Refresh
        THEN: The parameter editor lists files from that exact path
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/temperature"
        window.parameter_editor = MagicMock()
        window.parameter_editor.get_bin_log_files.return_value = []
        window.tree = MagicMock()
        window.remote_directory_label = MagicMock()
        window.empty_state_label = MagicMock()
        window.download_button = MagicMock()
        window._populate_tree = MagicMock()  # pylint: disable=protected-access

        window.refresh_remote_files()

        window.parameter_editor.get_bin_log_files.assert_called_once_with("/APM/LOGS/temperature")

    def test_enter_in_remote_destination_refreshes_the_listing(self) -> None:
        """
        Enter in the remote destination entry performs Open/Refresh.

        GIVEN: The remote destination entry has keyboard focus
        WHEN: The user presses Enter
        THEN: The remote listing is refreshed
        AND: Tk stops processing the key event
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.refresh_remote_files = MagicMock()

        result = window._on_remote_directory_return()  # pylint: disable=protected-access

        window.refresh_remote_files.assert_called_once_with()
        assert result == "break"

    def test_select_all_ignores_parent_directory_entry(self) -> None:
        """
        Select all selects files without selecting the parent directory entry.

        GIVEN: The remote listing contains a parent-directory entry
        WHEN: The user presses Select all
        THEN: Every regular file row is selected
        AND: The `..` row is excluded
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.remote_files = [
            FlightControllerLogFile("..", "/APM/LOGS/..", 0),
            FlightControllerLogFile("one.BIN", "/APM/LOGS/one.BIN", 10),
            FlightControllerLogFile("two.BIN", "/APM/LOGS/two.BIN", 20),
        ]
        window.tree = MagicMock()
        window.download_button = MagicMock()
        window.tree.selection.return_value = ("1", "2")

        window.select_all_files()

        window.tree.selection_set.assert_called_once_with(["1", "2"])
        window.download_button.configure.assert_called_once_with(state="normal")

    def test_ctrl_a_selects_all_files(self) -> None:
        """
        Ctrl+A selects all files in the remote panel.

        GIVEN: The remote file Treeview has selectable files
        WHEN: The user presses Ctrl+A
        THEN: The same Select all behavior is invoked
        AND: Tk stops processing the shortcut
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.select_all_files = MagicMock()

        result = window._on_select_all_key()  # pylint: disable=protected-access

        window.select_all_files.assert_called_once_with()
        assert result == "break"

    def test_user_can_sort_remote_files_by_filename(self) -> None:
        """
        Clicking the filename heading sorts rows alphabetically.

        GIVEN: The remote panel contains files in an unsorted order
        WHEN: The filename heading is activated
        THEN: Rows are moved into case-insensitive filename order
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.sort_column = ""
        window.remote_files = [
            FlightControllerLogFile("zeta.BIN", "/APM/LOGS/zeta.BIN", 10),
            FlightControllerLogFile("Alpha.BIN", "/APM/LOGS/Alpha.BIN", 20),
            FlightControllerLogFile("middle.BIN", "/APM/LOGS/middle.BIN", 30),
        ]
        window.tree = MagicMock()
        window.tree.get_children.return_value = ("0", "1", "2")

        window._sort_by_column("name", reverse=False)  # pylint: disable=protected-access

        assert window.tree.move.call_args_list == [
            call("1", "", 0),
            call("2", "", 1),
            call("0", "", 2),
        ]

    def test_user_can_sort_remote_files_by_numeric_size(self) -> None:
        """
        Clicking the size heading sorts by bytes rather than formatted text.

        GIVEN: The remote panel contains files with sizes 100, 2, and 12 bytes
        WHEN: The size heading is activated
        THEN: Rows are moved in numeric size order
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.sort_column = ""
        window.remote_files = [
            FlightControllerLogFile("hundred.BIN", "/APM/LOGS/hundred.BIN", 100),
            FlightControllerLogFile("two.BIN", "/APM/LOGS/two.BIN", 2),
            FlightControllerLogFile("twelve.BIN", "/APM/LOGS/twelve.BIN", 12),
        ]
        window.tree = MagicMock()
        window.tree.get_children.return_value = ("0", "1", "2")

        window._sort_by_column("size", reverse=False)  # pylint: disable=protected-access

        assert window.tree.move.call_args_list == [
            call("1", "", 0),
            call("2", "", 1),
            call("0", "", 2),
        ]

    def test_single_selection_uses_a_save_file_selector_and_progress_callback(self) -> None:
        """
        Downloading one selected file asks for a complete local filename.

        GIVEN: The remote panel has one selected file
        WHEN: The user presses Download and chooses a local filename
        THEN: The save-file selector receives the remote basename
        AND: The workflow receives the progress-window callback
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        selected_file = FlightControllerLogFile(
            name="LASTLOG.TXT",
            remote_path="/APM/LOGS/LASTLOG.TXT",
            size_bytes=8,
        )
        window._selected_files = MagicMock(return_value=[selected_file])  # pylint: disable=protected-access
        window.ui = MagicMock()
        window.ui.asksaveasfilename.return_value = "C:/downloads/custom-name.txt"
        window.parameter_editor = MagicMock()
        window.root = MagicMock()
        progress_window = MagicMock()
        window.ui.create_progress_window.return_value = progress_window

        window.download_selected_files()

        window.ui.asksaveasfilename.assert_called_once()
        assert window.ui.asksaveasfilename.call_args.kwargs["initialfile"] == "LASTLOG.TXT"
        workflow_kwargs = window.parameter_editor.download_selected_bin_logs_workflow.call_args.kwargs
        assert workflow_kwargs["destination"] == "C:/downloads/custom-name.txt"
        assert workflow_kwargs["destination_is_directory"] is False
        assert workflow_kwargs["progress_callback"] is progress_window.update_progress_bar
        progress_window.destroy.assert_called_once()

    def test_multiple_selection_uses_a_directory_selector(self) -> None:
        """
        Downloading several selected files asks for one local directory.

        GIVEN: The remote panel has multiple selected files
        WHEN: The user presses Download and chooses a destination directory
        THEN: The directory selector is used instead of the save-file selector
        AND: The workflow receives the directory destination
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window._selected_files = MagicMock(  # pylint: disable=protected-access
            return_value=[
                FlightControllerLogFile("one.BIN", "/APM/LOGS/one.BIN", 10),
                FlightControllerLogFile("two.BIN", "/APM/LOGS/two.BIN", 20),
            ]
        )
        window.ui = MagicMock()
        window.ui.askdirectory.return_value = "C:/downloads"
        window.parameter_editor = MagicMock()
        window.root = MagicMock()
        progress_window = MagicMock()
        window.ui.create_progress_window.return_value = progress_window

        window.download_selected_files()

        window.ui.askdirectory.assert_called_once()
        window.ui.asksaveasfilename.assert_not_called()
        workflow_kwargs = window.parameter_editor.download_selected_bin_logs_workflow.call_args.kwargs
        assert workflow_kwargs["destination"] == "C:/downloads"
        assert workflow_kwargs["destination_is_directory"] is True
        progress_window.destroy.assert_called_once()

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

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.DownloadBinLogsWindow") as modal:
            editor.on_download_bin_logs_click()

        modal.assert_called_once_with(editor.root, editor.parameter_editor, editor.ui)
