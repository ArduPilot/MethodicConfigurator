#!/usr/bin/env python3

"""
Flight-controller file-browser listing and management tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerFiles, FlightControllerLogFile
from ardupilot_methodic_configurator.backend_mavftp import DirectoryEntry, FtpError
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

# pylint: disable=protected-access


def _files_manager() -> FlightControllerFiles:
    """Build a connected MAVFTP-capable file manager for unit tests."""
    connection_manager = MagicMock()
    connection_manager.master = MagicMock()
    connection_manager.info = FlightControllerInfo()
    connection_manager.info.is_mavftp_supported = True
    return FlightControllerFiles(connection_manager=connection_manager)


class TestFlightControllerLogListing:
    """Verify the user can browse all files in the remote log directory."""

    def test_legacy_bin_aliases_are_not_exposed(self) -> None:
        """The generic browser API replaces the misleading BIN-specific aliases."""
        for api in (FlightController, FlightControllerFiles):
            assert not hasattr(api, "list_bin_log_files")
            assert not hasattr(api, "download_bin_log_file")

    def test_remote_file_verification_compares_local_and_vehicle_crc(self) -> None:
        """CRC mismatch is not reported as a verified transfer."""
        files_manager = _files_manager()
        mavftp = MagicMock()
        mavftp.local_file_crc.return_value = 0x12345678
        mavftp.last_crc = 0x12345678
        mavftp.cmd_crc.return_value = SimpleNamespace(error_code=FtpError.Success)
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            assert files_manager.verify_remote_file("/APM/LOGS/log.bin", "log.bin") is True
            mavftp.last_crc = 0x87654321
            assert files_manager.verify_remote_file("/APM/LOGS/log.bin", "log.bin") is False
        assert mavftp.cmd_crc.call_count == 2

    def test_generated_sys_file_is_not_claimed_verified(self) -> None:
        """Dynamic @SYS files are explicitly skipped rather than marked verified."""
        files_manager = _files_manager()
        assert files_manager.verify_remote_file("/@SYS/threads.txt", "threads.txt") is None
        assert files_manager.verify_remote_file("/param.pck?withdefaults=1", "params.pck") is None

    def test_controller_lists_remote_entries_through_file_manager(self) -> None:
        """The controller forwards the generic directory listing unchanged."""
        controller = FlightController.__new__(FlightController)
        controller._files_manager = MagicMock()
        file_entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        directory = FlightControllerLogFile("nested", "/APM/LOGS/nested", 0, is_directory=True)
        controller._files_manager.list_remote_files.return_value = [directory, file_entry]

        assert controller.list_remote_files("/APM/LOGS/") == [directory, file_entry]
        controller._files_manager.list_remote_files.assert_called_once_with("/APM/LOGS/")

    def test_controller_downloads_remote_file_through_file_manager(self) -> None:
        """The controller forwards explicit file downloads to the backend."""
        controller = FlightController.__new__(FlightController)
        controller._files_manager = MagicMock()
        controller._files_manager.download_remote_file.return_value = True
        assert controller.download_remote_file("/APM/LOGS/log.bin", "log.bin")
        controller._files_manager.download_remote_file.assert_called_once_with("/APM/LOGS/log.bin", "log.bin", None)

    def test_user_sees_files_and_directories_in_default_log_directory(self) -> None:
        """
        The remote panel lists every entry, not only numbered BIN logs.

        GIVEN: The FC log directory contains BIN, TXT, and other regular files
        WHEN: The application lists the default log directory
        THEN: All files and directories are returned with their remote paths and sizes
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
            files = files_manager.list_remote_files()

        assert files == [
            FlightControllerLogFile(name="00000012.BIN", remote_path="/APM/LOGS/00000012.BIN", size_bytes=120),
            FlightControllerLogFile(name="LASTLOG.TXT", remote_path="/APM/LOGS/LASTLOG.TXT", size_bytes=8),
            FlightControllerLogFile(
                name="flight log 01.BIN",
                remote_path="/APM/LOGS/flight log 01.BIN",
                size_bytes=64,
            ),
            FlightControllerLogFile(name="notes.dat", remote_path="/APM/LOGS/notes.dat", size_bytes=42),
            FlightControllerLogFile(
                name="subdirectory", remote_path="/APM/LOGS/subdirectory", size_bytes=0, is_directory=True
            ),
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
            files_manager.list_remote_files("/APM/LOGS/temperature")

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
                DirectoryEntry("nested", is_dir=True, size_b=0, mtime=1_725_000_000),
                DirectoryEntry("log.bin", is_dir=False, size_b=42, mtime=1_725_000_100),
            ]
        )

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            entries = files_manager.list_remote_files("/APM/LOGS/")

        assert entries == [
            FlightControllerLogFile("nested", "/APM/LOGS/nested", 0, is_directory=True, modified_at=1_725_000_000),
            FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 42, modified_at=1_725_000_100),
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

    def test_missing_remote_directory_raises_file_not_found(self) -> None:
        """A missing remote path is distinguishable from other MAVFTP failures."""
        files_manager = _files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(error_code=FtpError.FileNotFound)

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mavftp,
            ),
            pytest.raises(FileNotFoundError, match=r"^/APM/LOGS/$"),
        ):
            files_manager.list_remote_files("/APM/LOGS/")

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
