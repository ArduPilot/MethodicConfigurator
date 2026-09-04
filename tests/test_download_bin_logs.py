#!/usr/bin/env python3
# pylint: disable=protected-access,too-many-lines,too-many-public-methods

"""
BDD tests for flight-controller log-file listing and download workflows.

This file is part of ArduPilot Methodic Configurator.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call, patch

from ardupilot_methodic_configurator.backend_flightcontroller_files import (
    FlightControllerFiles,
    FlightControllerLogFile,
)
from ardupilot_methodic_configurator.backend_mavftp import DirectoryEntry
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_download_bin_logs import (
    DownloadBinLogsWindow,
    LocalFileEntry,
)
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
                DirectoryEntry("flight log 01.BIN", is_dir=False, size_b=64),
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
            FlightControllerLogFile(
                name="flight log 01.BIN",
                remote_path="/APM/LOGS/flight log 01.BIN",
                size_bytes=64,
            ),
            FlightControllerLogFile(name="notes.dat", remote_path="/APM/LOGS/notes.dat", size_bytes=42),
        ]
        mavftp.cmd_list.assert_called_once_with(["/APM/LOGS/"])

    def test_remote_path_normalization_preserves_filename_whitespace(self) -> None:
        """Whitespace in a remote filename remains part of the MAVFTP path."""
        assert FlightControllerFiles._normalize_remote_path("/APM/LOGS/ flight log .BIN ") == ("/APM/LOGS/ flight log .BIN ")

    def test_explicit_download_preserves_filename_whitespace(self) -> None:
        """Downloading a remote filename with whitespace passes the exact path to MAVFTP."""
        files_manager = _files_manager()
        mavftp = MagicMock()
        mavftp.process_ftp_reply.return_value = SimpleNamespace(error_code=0)

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            assert files_manager.download_remote_file(
                "/APM/LOGS/ flight log .BIN ",
                "local flight log.bin",
            )

        mavftp.cmd_get.assert_called_once_with(
            ["/APM/LOGS/ flight log .BIN ", "local flight log.bin"],
            progress_callback=ANY,
        )

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

    def test_remote_browser_listing_includes_directories(self) -> None:
        """
        The remote browser displays both regular files and directories.

        GIVEN: MAVFTP returns a file and a subdirectory
        WHEN: The browser requests a generic remote listing
        THEN: Both entries are returned with directory metadata
        """
        files_manager = _files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(
            directory_listing=[
                DirectoryEntry("nested", is_dir=True, size_b=0),
                DirectoryEntry("log.bin", is_dir=False, size_b=42),
            ]
        )

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            entries = files_manager.list_remote_files("/APM/LOGS/")

        assert entries == [
            FlightControllerLogFile("nested", "/APM/LOGS/nested", 0, is_directory=True),
            FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 42),
        ]

    def test_remote_listing_failure_is_distinct_from_an_empty_directory(self) -> None:
        """A missing MAVFTP listing is reported as failure, not as an empty directory."""
        files_manager = _files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(directory_listing=None)

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            assert files_manager.list_remote_files() is None

    def test_remote_file_manager_supports_delete_rename_and_directory_creation(self) -> None:
        """
        Remote management operations delegate to MAVFTP safely.

        GIVEN: A connected MAVFTP-capable flight controller
        WHEN: Remote create, delete, and rename operations are requested
        THEN: The corresponding MAVFTP commands receive normalized paths
        """
        files_manager = _files_manager()
        mavftp = MagicMock()
        success = SimpleNamespace(error_code=0)
        mavftp.cmd_mkdir.return_value = success
        mavftp.cmd_rm.return_value = success
        mavftp.cmd_rmdir.return_value = success
        mavftp.cmd_rename.return_value = success

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            assert files_manager.make_remote_directory("/APM/LOGS/nested/")
            assert files_manager.delete_remote_path("/APM/LOGS/log.bin")
            assert files_manager.delete_remote_path("/APM/LOGS/nested", is_directory=True)
            assert files_manager.rename_remote_path("/APM/LOGS/old.bin", "/APM/LOGS/new.bin")

        mavftp.cmd_mkdir.assert_called_once_with(["/APM/LOGS/nested"])
        mavftp.cmd_rm.assert_called_once_with(["/APM/LOGS/log.bin"])
        mavftp.cmd_rmdir.assert_called_once_with(["/APM/LOGS/nested"])
        mavftp.cmd_rename.assert_called_once_with(["/APM/LOGS/old.bin", "/APM/LOGS/new.bin"])


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
        flight_controller = model._flight_controller  # pylint: disable=protected-access
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
        assert not result.failed
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
        flight_controller = model._flight_controller  # pylint: disable=protected-access
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
        flight_controller = model._flight_controller  # pylint: disable=protected-access
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

    def test_batch_rejects_duplicate_local_targets_before_transfer(self) -> None:
        """Duplicate selected basenames cannot cause one download to overwrite another."""
        model = _parameter_editor_model()
        flight_controller = model._flight_controller  # pylint: disable=protected-access
        show_error = MagicMock()
        selected = [
            FlightControllerLogFile("same.bin", "/APM/LOGS/one.bin", 10),
            FlightControllerLogFile("same.bin", "/APM/LOGS/two.bin", 20),
        ]

        with (
            patch.object(Path, "is_dir", return_value=True),
            patch.object(Path, "exists", return_value=False),
        ):
            result = model.download_selected_bin_logs_workflow(
                selected_files=selected,
                destination="C:/downloads",
                destination_is_directory=True,
                ask_overwrite=MagicMock(),
                show_error=show_error,
                show_info=MagicMock(),
            )

        assert result.failed == ("same.bin", "same.bin")
        flight_controller.download_bin_log_file.assert_not_called()
        show_error.assert_called_once()


class TestDownloadBinLogsWindow:
    """Verify the modal's remote destination selector behavior."""

    def test_local_panel_defaults_to_current_vehicle_directory(self) -> None:
        """The local browser starts in the vehicle directory used by the editor."""
        parameter_editor = MagicMock()
        parameter_editor.get_vehicle_directory.return_value = str(Path.cwd())

        assert DownloadBinLogsWindow._default_local_directory(parameter_editor) == str(Path.cwd())

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

    def test_backspace_navigates_to_parent_of_last_selected_remote_panel(self) -> None:
        """Backspace opens the remote parent directory when the remote panel was last selected."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.last_selected_panel = "remote"
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/nested/"
        window.refresh_remote_panel = MagicMock()

        result = window._on_backspace()  # pylint: disable=protected-access

        window.remote_directory_var.set.assert_called_once_with("/APM/LOGS")
        window.refresh_remote_panel.assert_called_once_with()
        assert result == "break"

    def test_backspace_navigates_to_parent_of_last_selected_local_panel(self) -> None:
        """Backspace opens the local parent directory when the local panel was last selected."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.last_selected_panel = "local"
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = "C:/logs/nested"
        window.refresh_local_panel = MagicMock()

        result = window._on_backspace()  # pylint: disable=protected-access

        window.local_directory_var.set.assert_called_once_with("C:\\logs")
        window.refresh_local_panel.assert_called_once_with()
        assert result == "break"

    def test_remote_parent_button_navigates_to_parent_directory(self) -> None:
        """The remote parent button navigates without creating a `..` tree row."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.remote_directory_var = MagicMock()
        window.remote_directory_var.get.return_value = "/APM/LOGS/nested/"
        window.refresh_remote_panel = MagicMock()

        window.navigate_remote_parent()

        window.remote_directory_var.set.assert_called_once_with("/APM/LOGS")
        window.refresh_remote_panel.assert_called_once_with()

    def test_local_parent_button_navigates_to_parent_directory(self) -> None:
        """The local parent button navigates to the filesystem parent."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.local_directory_var = MagicMock()
        window.local_directory_var.get.return_value = "C:/logs/nested"
        window.refresh_local_panel = MagicMock()

        window.navigate_local_parent()

        window.local_directory_var.set.assert_called_once_with("C:\\logs")
        window.refresh_local_panel.assert_called_once_with()

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

    def test_remote_download_plan_expands_directories_recursively(self) -> None:
        """
        A selected remote directory expands into nested local directories/files.

        GIVEN: A remote directory contains a nested directory and a file
        WHEN: A download plan is built
        THEN: Every remote file is mapped beneath the selected local directory
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.parameter_editor = MagicMock()
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        nested = FlightControllerLogFile("nested", "/APM/LOGS/folder/nested", 0, is_directory=True)
        leaf = FlightControllerLogFile("leaf.bin", "/APM/LOGS/folder/nested/leaf.bin", 12)
        window.parameter_editor.get_remote_files.side_effect = [[nested], [leaf]]

        directories, files = window._remote_download_plan(root, Path("C:/downloads/folder"))  # pylint: disable=protected-access

        assert directories == [Path("C:/downloads/folder"), Path("C:/downloads/folder/nested")]
        assert files == [(leaf, Path("C:/downloads/folder/nested/leaf.bin"))]

    def test_remote_download_plan_does_not_create_directory_when_listing_fails(self) -> None:
        """A failed recursive listing must not turn into a successful empty directory plan."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.parameter_editor = MagicMock()
        window.parameter_editor.get_remote_files.return_value = None
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        failures: list[str] = []

        directories, files = window._remote_download_plan(  # pylint: disable=protected-access
            root,
            Path("C:/downloads/folder"),
            failures,
        )

        assert not directories
        assert not files
        assert failures == ["/APM/LOGS/folder"]

    def test_local_upload_plan_expands_directories_recursively(self) -> None:
        """
        A selected local directory expands into remote directories/files.

        GIVEN: A local directory entry contains one nested file
        WHEN: An upload plan is built
        THEN: The remote directory and file paths preserve the hierarchy
        """
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        root_path = MagicMock()
        child_path = MagicMock()
        root_path.iterdir.return_value = [child_path]
        root_path.name = "folder"
        child_path.name = "leaf.bin"
        root_path.is_symlink.return_value = False
        child_path.is_symlink.return_value = False
        root_path.is_dir.return_value = True
        child_path.is_dir.return_value = False
        child_path.stat.return_value.st_size = 12
        entry = LocalFileEntry("folder", root_path, 0, is_directory=True)

        directories, files = window._local_upload_plan(entry, "/APM/LOGS/folder")  # pylint: disable=protected-access

        assert directories == ["/APM/LOGS/folder"]
        assert files == [(child_path, "/APM/LOGS/folder/leaf.bin", 12)]

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

    def test_select_all_local_entries_ignores_parent_directory(self) -> None:
        """The local Select all action does not select the parent-navigation row."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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
        window.ui.ask_yesno.return_value = True
        window._progress_window = MagicMock(return_value=MagicMock())  # pylint: disable=protected-access
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

        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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
        window._progress_window = MagicMock(return_value=MagicMock())  # pylint: disable=protected-access
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

    def test_remote_delete_only_removes_files_and_empty_directories(self) -> None:
        """Remote delete skips non-empty directories while continuing the batch."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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

        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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

        result = window._on_rename_key()  # pylint: disable=protected-access

        assert result == "break"
        window.ui.askstring.assert_called_once()
        window.parameter_editor.rename_remote_path.assert_called_once_with(
            "/APM/LOGS/old.bin",
            "/APM/LOGS/new.bin",
        )

    def test_f2_commits_an_inline_remote_rename(self) -> None:
        """F2 commits the edited name without opening a dialog when inline editing works."""
        entry = FlightControllerLogFile("old.bin", "/APM/LOGS/old.bin", 10)
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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
            "ardupilot_methodic_configurator.frontend_tkinter_download_bin_logs.ttk.Entry",
            return_value=editor,
        ):
            result = window._on_rename_key()  # pylint: disable=protected-access

        assert result == "break"
        editor.place.assert_called_once_with(x=1, y=2, width=100, height=20)
        editor.focus_set.assert_called_once_with()
        editor.bind.assert_any_call("<Return>", ANY)
        window.parameter_editor.rename_remote_path.assert_not_called()

        finish_result = window._finish_inline_rename("remote", entry, editor)  # pylint: disable=protected-access

        assert finish_result == "break"
        window.parameter_editor.rename_remote_path.assert_called_once_with(
            "/APM/LOGS/old.bin",
            "/APM/LOGS/new log.bin",
        )

    def test_f2_does_not_rename_a_stale_row_without_current_selection(self) -> None:
        """F2 refuses to act on a cached row after the current selection is gone."""
        entry = FlightControllerLogFile("new.bin", "/APM/LOGS/new.bin", 10)
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ()
        window.remote_entries = [entry]
        window.last_selected_panel = "remote"
        window.last_selected_items = {"remote": "0", "local": None}
        window.ui = MagicMock()
        window.parameter_editor = MagicMock()

        assert window._on_rename_key() == "break"  # pylint: disable=protected-access

        window.ui.askstring.assert_not_called()
        window.parameter_editor.rename_remote_path.assert_not_called()

    def test_remote_mutation_outside_log_directory_requires_warning_and_confirmation(self) -> None:
        """Remote deletion outside the log directory requires an explicit second confirmation."""
        entry = FlightControllerLogFile("params.bin", "/APM/params.bin", 10)
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.remote_entries = [entry]
        window.remote_tree = MagicMock()
        window.remote_tree.selection.return_value = ("0",)
        window.parameter_editor = MagicMock()
        window.parameter_editor.delete_remote_path.return_value = True
        window.ui = MagicMock()
        window.ui.ask_yesno.side_effect = [True, True]
        window.refresh_remote_panel = MagicMock()

        window.delete_selected_remote_entries()

        window.ui.show_warning.assert_called_once()
        assert window.ui.ask_yesno.call_count == 2
        window.parameter_editor.delete_remote_path.assert_called_once_with("/APM/params.bin", False)  # noqa: FBT003

    def test_remote_rename_uses_a_single_safe_new_name(self) -> None:
        """Remote rename uses the selected entry's parent directory."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
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

    def test_user_can_toggle_remote_filename_sort_direction(self) -> None:
        """Clicking the filename heading repeatedly alternates ascending and descending."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.remote_sort_column = ""
        window.remote_sort_reverse = False
        window.remote_entries = [
            FlightControllerLogFile("alpha.BIN", "/APM/LOGS/alpha.BIN", 10),
            FlightControllerLogFile("zeta.BIN", "/APM/LOGS/zeta.BIN", 20),
        ]
        window.remote_tree = MagicMock()
        window.remote_tree.get_children.return_value = ("0", "1")

        window._on_sort_heading("remote", "name")  # pylint: disable=protected-access
        window.remote_tree.move.reset_mock()
        window._on_sort_heading("remote", "name")  # pylint: disable=protected-access

        assert window.remote_sort_column == "name"
        assert window.remote_sort_reverse is True
        assert window.remote_tree.move.call_args_list == [
            call("1", "", 0),
            call("0", "", 1),
        ]

    def test_sorting_with_parent_entry_does_not_compare_strings_and_integers(self) -> None:
        """Sorting a navigable panel remains valid when the synthetic `..` row is present."""
        window = DownloadBinLogsWindow.__new__(DownloadBinLogsWindow)
        window.remote_sort_column = ""
        window.remote_sort_reverse = False
        window.remote_entries = [
            FlightControllerLogFile("..", "/APM/LOGS", 0, is_directory=True),
            FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 10),
        ]
        window.remote_tree = MagicMock()
        window.remote_tree.get_children.return_value = ("0", "1")

        window._on_sort_heading("remote", "name")  # pylint: disable=protected-access

        assert window.remote_tree.move.call_args_list == [
            call("0", "", 0),
            call("1", "", 1),
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
