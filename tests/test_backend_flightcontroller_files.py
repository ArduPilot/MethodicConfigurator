#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_files.py.

This file focuses on MAVFTP file operations behavior including file uploads,
log downloads, and error handling for unavailable MAVFTP functionality.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import (
    FlightControllerFiles,
    LastLogDownloadResult,
    is_safe_local_entry_name,
)
from ardupilot_methodic_configurator.backend_mavftp import DirectoryEntry, FtpError
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo


def _create_files_manager() -> FlightControllerFiles:
    """Helper to build a files manager with default mocks."""
    mock_conn_mgr = Mock()
    mock_conn_mgr.master = MagicMock()
    info = FlightControllerInfo()
    info.is_mavftp_supported = True
    mock_conn_mgr.info = info
    return FlightControllerFiles(connection_manager=mock_conn_mgr)


# pylint: disable=protected-access, too-few-public-methods, too-many-lines


class TestFlightControllerFilesInitialization:
    """Test file operations manager initialization."""

    def test_cross_platform_local_entry_validation_rejects_windows_unsafe_names(self) -> None:
        """Remote names that Windows cannot safely create are never local targets."""
        for unsafe_name in ("C:evil.bin", "CON", "NUL.txt", "log.", "log ", "\x01log.bin"):
            assert not is_safe_local_entry_name(unsafe_name)

    def test_user_can_create_files_manager(self) -> None:
        """
        User can create files manager with required dependencies.

        GIVEN: Connection manager available
        WHEN: User creates files manager
        THEN: Manager should be initialized successfully
        AND: Dependencies should be stored
        """
        # Given: Mock connection manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()

        # When: Create files manager
        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        # Then: Manager initialized
        assert files_mgr is not None
        assert files_mgr.master is None
        assert files_mgr.info is not None

    def test_files_manager_requires_connection_manager(self) -> None:
        """
        Files manager requires connection manager dependency.

        GIVEN: Missing connection manager
        WHEN: User attempts to create files manager
        THEN: ValueError should be raised
        AND: Clear error message should be provided
        """
        # When/Then: Missing connection manager
        with pytest.raises(ValueError, match="connection_manager is required"):
            FlightControllerFiles(connection_manager=None)


class TestFlightControllerFilesUpload:
    """Test file upload functionality via MAVFTP."""

    def test_file_upload_fails_without_connection(self) -> None:
        """
        File upload fails gracefully without connection.

        GIVEN: No flight controller connection
        WHEN: User attempts to upload file
        THEN: Operation should fail with False
        AND: Error should be logged appropriately
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        # When: Attempt upload
        success = files_mgr.upload_file(local_filename="/tmp/test.param", remote_filename="@SYS/test.param")  # noqa: S108

        # Then: Operation fails
        assert success is False

    def test_file_upload_fails_without_mavftp(self) -> None:
        """
        File upload fails when MAVFTP is not available.

        GIVEN: Connected flight controller without MAVFTP support
        WHEN: User attempts to upload file
        THEN: Operation should fail with False
        AND: Error should indicate MAVFTP unavailable
        """
        # Given: Connection but no MAVFTP
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        # When: Attempt upload with MAVFTP unavailable
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe", return_value=None):
            success = files_mgr.upload_file(local_filename="/tmp/test.param", remote_filename="@SYS/test.param")  # noqa: S108

        # Then: Operation fails
        assert success is False

    def test_user_can_upload_file_with_progress_callback(self) -> None:
        """
        User can upload file and receive progress updates.

        GIVEN: Connected flight controller with MAVFTP support
        WHEN: User uploads file with progress callback
        THEN: File should be uploaded successfully
        AND: Progress callback should be invoked
        """
        # Given: MAVFTP available
        mock_ret = MagicMock()
        mock_ret.error_code = 0

        mock_mavftp = MagicMock()
        mock_mavftp.cmd_put = MagicMock(return_value=MagicMock(error_code=0))
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_info = FlightControllerInfo()
        mock_info.is_mavftp_supported = True
        mock_conn_mgr.info = mock_info

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        progress_calls = []

        def progress_callback(current: int, total: int) -> None:
            progress_calls.append((current, total))

        # When: Upload file with mocked file existence
        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe", return_value=mock_mavftp
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/test.param",  # noqa: S108
                remote_filename="@SYS/test.param",
                progress_callback=progress_callback,
            )

        # Then: Upload successful
        assert success is True
        mock_mavftp.cmd_put.assert_called_once()
        mock_mavftp.process_ftp_reply.assert_called_once_with("put", timeout=files_mgr.MAVFTP_UPLOAD_TIMEOUT_BASE)
        callback = mock_mavftp.cmd_put.call_args.kwargs["progress_callback"]
        callback(0.42)
        assert progress_calls == [(42, 100)]

    def test_file_upload_reports_mavftp_error_code(self) -> None:
        """Upload reports MAVFTP errors when CreateFile fails."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_put.return_value = MagicMock(error_code=0)
        mock_ret = MagicMock()
        mock_ret.error_code = 5
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/test.param",  # noqa: S108
                remote_filename="@SYS/test.param",
            )

        assert success is False
        mock_ret.display_message.assert_called_once()

    def test_file_upload_handles_exceptions(self) -> None:
        """Upload gracefully handles unexpected exceptions."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_put.side_effect = RuntimeError("boom")

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/test.param",  # noqa: S108
                remote_filename="@SYS/test.param",
            )

        assert success is False

    def test_file_upload_creates_missing_remote_parent_directories(self) -> None:
        """
        File upload creates absolute remote parent directories before creating the file.

        GIVEN: A script upload target below /APM/Scripts
        WHEN: User uploads the file via MAVFTP
        THEN: Parent directories are created first
        AND: The file upload is attempted afterwards
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mkdir_ret = MagicMock(error_code=0)
        put_ret = MagicMock(error_code=0)
        mock_mavftp.cmd_mkdir.return_value = mkdir_ret
        mock_mavftp.cmd_list.return_value = SimpleNamespace(error_code=0, directory_listing=[])
        mock_mavftp.cmd_put.return_value = put_ret
        mock_mavftp.process_ftp_reply.return_value = put_ret

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/VTOL-quicktune.lua",  # noqa: S108
                remote_filename="/APM/Scripts/VTOL-quicktune.lua",
            )

        assert success is True
        mock_mavftp.cmd_mkdir.assert_any_call(["/APM"])
        mock_mavftp.cmd_mkdir.assert_any_call(["/APM/Scripts"])
        mock_mavftp.cmd_put.assert_called_once()

    def test_file_upload_treats_existing_remote_parent_directories_as_success(self) -> None:
        """Existing remote parent directories do not block file uploads."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mkdir_ret = MagicMock(error_code=8)
        put_ret = MagicMock(error_code=0)
        mock_mavftp.cmd_mkdir.return_value = mkdir_ret
        mock_mavftp.cmd_list.return_value = SimpleNamespace(error_code=0, directory_listing=[])
        mock_mavftp.cmd_put.return_value = put_ret
        mock_mavftp.process_ftp_reply.return_value = put_ret

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/VTOL-quicktune.lua",  # noqa: S108
                remote_filename="/APM/Scripts/VTOL-quicktune.lua",
            )

        assert success is True
        mock_mavftp.cmd_put.assert_called_once()

    def test_file_upload_reuses_verified_remote_parent_directories(self) -> None:
        """A multi-file upload does not relist the same existing parent directories."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_mkdir.return_value = MagicMock(error_code=FtpError.FileExists)
        mock_mavftp.cmd_list.return_value = SimpleNamespace(error_code=FtpError.Success, directory_listing=[])
        mock_mavftp.cmd_put.return_value = MagicMock(error_code=FtpError.Success)
        mock_mavftp.process_ftp_reply.return_value = MagicMock(error_code=FtpError.Success)

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            assert files_mgr.upload_file("/tmp/first.lua", "/APM/Scripts/first.lua")  # noqa: S108
            assert files_mgr.upload_file("/tmp/second.lua", "/APM/Scripts/second.lua")  # noqa: S108

        assert mock_mavftp.cmd_list.call_count == 2

    def test_upload_recreates_cached_parent_removed_by_another_client(self) -> None:
        """A definite missing-path reply invalidates cached parents and retries once."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        success = MagicMock(error_code=FtpError.Success)
        missing = MagicMock(error_code=FtpError.FileNotFound)
        mock_mavftp.cmd_mkdir.return_value = success
        mock_mavftp.cmd_put.side_effect = [success, missing, success]
        mock_mavftp.process_ftp_reply.return_value = success

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            assert files_mgr.upload_file("/tmp/first.lua", "/APM/Scripts/first.lua")  # noqa: S108
            assert files_mgr.upload_file("/tmp/second.lua", "/APM/Scripts/second.lua")  # noqa: S108

        assert mock_mavftp.cmd_mkdir.call_count == 4
        assert mock_mavftp.cmd_put.call_count == 3

    def test_upload_recreates_cached_parent_after_missing_createfile_reply(self) -> None:
        """The asynchronous CreateFile reply can also reveal a stale parent cache."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        success = MagicMock(error_code=FtpError.Success)
        missing = MagicMock(error_code=FtpError.FileNotFound)
        mock_mavftp.cmd_mkdir.return_value = success
        mock_mavftp.cmd_put.return_value = success
        mock_mavftp.process_ftp_reply.side_effect = [success, missing, success]

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            assert files_mgr.upload_file("/tmp/first.lua", "/APM/Scripts/first.lua")  # noqa: S108
            assert files_mgr.upload_file("/tmp/second.lua", "/APM/Scripts/second.lua")  # noqa: S108

        assert mock_mavftp.cmd_mkdir.call_count == 4
        assert mock_mavftp.cmd_put.call_count == 3

    def test_file_upload_retries_transient_remote_directory_listing_timeout(self) -> None:
        """A lost directory-listing reply does not abort an upload immediately."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_mkdir.return_value = MagicMock(error_code=FtpError.FileExists)
        mock_mavftp.cmd_list.side_effect = [
            SimpleNamespace(error_code=FtpError.RemoteReplyTimeout, directory_listing=None),
            SimpleNamespace(error_code=FtpError.Success, directory_listing=[]),
            SimpleNamespace(error_code=FtpError.Success, directory_listing=[]),
        ]
        mock_mavftp.cmd_put.return_value = MagicMock(error_code=FtpError.Success)
        mock_mavftp.process_ftp_reply.return_value = MagicMock(error_code=FtpError.Success)

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file("/tmp/retry.lua", "/APM/Scripts/retry.lua")  # noqa: S108

        assert success is True
        assert mock_mavftp.cmd_list.call_count == 3

    def test_file_upload_stops_when_remote_parent_directory_creation_fails(self) -> None:
        """Upload stops before CreateFile when a parent directory cannot be created."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mkdir_ret = MagicMock(error_code=9)
        mock_mavftp.cmd_mkdir.return_value = mkdir_ret

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/VTOL-quicktune.lua",  # noqa: S108
                remote_filename="/APM/Scripts/VTOL-quicktune.lua",
            )

        assert success is False
        mkdir_ret.display_message.assert_called_once()
        mock_mavftp.cmd_put.assert_not_called()

    def test_file_upload_does_not_create_remote_directories_when_local_file_is_missing(self) -> None:
        """Local validation runs before remote directory creation."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=False),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/missing.lua",  # noqa: S108
                remote_filename="/APM/Scripts/missing.lua",
            )

        assert success is False
        mock_mavftp.cmd_mkdir.assert_not_called()
        mock_mavftp.cmd_put.assert_not_called()
        mock_mavftp.process_ftp_reply.assert_not_called()

    def test_file_upload_stops_when_cmd_put_fails_synchronously(self) -> None:
        """Synchronous cmd_put failures are reported without waiting for a CreateFile reply."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_mkdir.return_value = MagicMock(error_code=0)
        put_ret = MagicMock(error_code=72)
        mock_mavftp.cmd_put.return_value = put_ret

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.isfile", return_value=True),
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/unreadable.lua",  # noqa: S108
                remote_filename="/APM/Scripts/unreadable.lua",
            )

        assert success is False
        put_ret.display_message.assert_called_once()
        mock_mavftp.process_ftp_reply.assert_not_called()


class TestFlightControllerFilesDownload:
    """Test log file download functionality via MAVFTP."""

    def test_detailed_result_distinguishes_empty_logs_from_unavailable_listing(self) -> None:
        """Only an authoritative empty listing confirms that the FC has no logs."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe", return_value=mavftp),
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch.object(files_mgr, "_get_log_number_from_directory_listing", side_effect=[(None, True), (None, False)]),
            patch.object(files_mgr, "_get_log_number_by_scanning", return_value=None),
        ):
            assert files_mgr.download_last_flight_log("last.BIN") is LastLogDownloadResult.NO_LOGS
            assert files_mgr.download_last_flight_log("last.BIN") is LastLogDownloadResult.FAILED

    def test_detailed_result_reports_transfer_failure(self) -> None:
        """A known log that cannot be transferred is not an empty FC."""
        files_mgr = _create_files_manager()
        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=MagicMock(),
            ),
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=42),
            patch.object(files_mgr, "_download_log_file", return_value=False),
        ):
            assert files_mgr.download_last_flight_log("last.BIN") is LastLogDownloadResult.FAILED

    def test_log_download_fails_without_connection(self) -> None:
        """
        Log download fails gracefully without connection.

        GIVEN: No flight controller connection
        WHEN: User attempts to download last log
        THEN: Operation should return None
        AND: Error should be logged appropriately
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        # When: Attempt download
        result = files_mgr.download_last_flight_log(local_filename="/tmp/test.BIN")  # noqa: S108

        # Then: Operation fails
        assert result is LastLogDownloadResult.FAILED

    def test_log_download_fails_without_mavftp(self) -> None:
        """
        Log download fails when MAVFTP is not available.

        GIVEN: Connected flight controller without MAVFTP support
        WHEN: User attempts to download last log
        THEN: Operation should return None
        AND: Error should indicate MAVFTP unavailable
        """
        # Given: Connection but no MAVFTP
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        # When: Attempt download with MAVFTP unavailable
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe", return_value=None):
            result = files_mgr.download_last_flight_log(local_filename="/tmp/test.BIN")  # noqa: S108

        # Then: Operation fails
        assert result is LastLogDownloadResult.FAILED

    def test_user_can_download_last_log_with_progress_callback(self) -> None:
        """
        User can download last log file and receive progress updates.

        GIVEN: Connected flight controller with MAVFTP and logs available
        WHEN: User downloads last log with progress callback
        THEN: Log should be downloaded successfully
        AND: Progress callback should be invoked
        AND: Downloaded file path should be returned
        """
        # Given: MAVFTP available with logs
        mock_mavftp = MagicMock()

        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_info = FlightControllerInfo()
        mock_info.is_mavftp_supported = True
        mock_conn_mgr.info = mock_info

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        progress_calls = []

        def progress_callback(current: int, total: int) -> None:
            progress_calls.append((current, total))

        # When: Download log with mocked log number discovery
        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe", return_value=mock_mavftp
            ),
            patch.object(files_mgr, "_get_last_log_number", return_value=(42, False)),
            patch.object(files_mgr, "_download_log_file", return_value=True),
        ):
            result = files_mgr.download_last_flight_log(
                local_filename="/tmp/00000042.BIN",  # noqa: S108
                progress_callback=progress_callback,
            )

        # Then: Download successful
        assert result is LastLogDownloadResult.SUCCESS

    def test_log_download_fails_when_last_log_unknown(self) -> None:
        """
        Users receive clear failure when no log number is discoverable.

        GIVEN: MAVFTP connection is available but no discovery strategy succeeds
        WHEN: User requests the last flight log download
        THEN: Operation should report failure
        AND: Actual download helper should never be invoked
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch.object(files_mgr, "_get_last_log_number", return_value=(None, False)),
            patch.object(files_mgr, "_download_log_file") as mock_download,
        ):
            result = files_mgr.download_last_flight_log(local_filename="/tmp/last.BIN")  # noqa: S108

        assert result is LastLogDownloadResult.FAILED
        mock_download.assert_not_called()

    def test_log_download_fails_when_mavftp_not_supported(self) -> None:
        """Download fails immediately when MAVFTP is not supported."""
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        info = FlightControllerInfo()
        info.is_mavftp_supported = False
        mock_conn_mgr.info = info

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe") as mock_factory:
            result = files_mgr.download_last_flight_log(local_filename="/tmp/unsupported.BIN")  # noqa: S108

        assert result is LastLogDownloadResult.FAILED
        mock_factory.assert_not_called()

    def test_log_download_fails_when_mavftp_instance_missing(self) -> None:
        """Download fails when MAVFTP creation returns None."""
        files_mgr = _create_files_manager()

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=None,
        ):
            result = files_mgr.download_last_flight_log(local_filename="/tmp/missing_instance.BIN")  # noqa: S108

        assert result is LastLogDownloadResult.FAILED

    def test_log_download_invokes_progress_callback(self) -> None:
        """Progress callback receives updates from helper function."""
        files_mgr = _create_files_manager()
        progress_calls: list[tuple[int, int]] = []

        def user_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        def fake_download(_mavftp: MagicMock, _number: int, _local: str, callback: Callable[[float], None]) -> bool:
            callback(0.25)
            return True

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=MagicMock(),
            ),
            patch.object(files_mgr, "_get_last_log_number", return_value=(3, False)),
            patch.object(files_mgr, "_download_log_file", side_effect=fake_download),
        ):
            result = files_mgr.download_last_flight_log(
                local_filename="/tmp/00000003.BIN",  # noqa: S108
                progress_callback=user_progress,
            )

        assert result is LastLogDownloadResult.SUCCESS
        assert progress_calls == [(25, 100)]

    def test_log_download_handles_exceptions(self) -> None:
        """Download gracefully handles unexpected exceptions."""
        files_mgr = _create_files_manager()

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=MagicMock(),
            ),
            patch.object(files_mgr, "_get_last_log_number", side_effect=RuntimeError("fail")),
        ):
            result = files_mgr.download_last_flight_log(local_filename="/tmp/boom.BIN")  # noqa: S108

        assert result is LastLogDownloadResult.FAILED


class TestFlightControllerFilesLogDiscovery:
    """Test log discovery and its guarded probing fallback."""

    def test_empty_log_directory_does_not_probe_guessed_log_files(self) -> None:
        """An authoritative empty listing must not start slow per-file MAVFTP probes."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(error_code=FtpError.Success, directory_listing=[])

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mavftp,
            ),
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
        ):
            assert files_mgr.download_last_flight_log("last.BIN") is LastLogDownloadResult.NO_LOGS

        mavftp.cmd_list.assert_called_once_with(["/APM/LOGS/"])
        mavftp.cmd_get.assert_not_called()
        mavftp.process_ftp_reply.assert_not_called()

    @pytest.mark.parametrize(
        "listing",
        [
            SimpleNamespace(
                error_code=FtpError.Success,
                directory_listing=[DirectoryEntry("README.TXT", is_dir=False, size_b=0)],
            ),
            SimpleNamespace(error_code=FtpError.FileNotFound, directory_listing=None),
        ],
    )
    def test_confirmed_absence_of_bin_logs_skips_probing(self, listing: SimpleNamespace) -> None:
        """No .BIN entries or no log directory means there is nothing to probe."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = listing
        with patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None):
            assert files_mgr._get_last_log_number(mavftp) == (None, True)
        mavftp.cmd_get.assert_not_called()

    def test_bin_logs_in_listing_are_used_without_probing(self) -> None:
        """A valid listing finds the latest BIN directly, even without LASTLOG.TXT."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(
            error_code=FtpError.Success,
            directory_listing=[
                DirectoryEntry("00000036.BIN", is_dir=False, size_b=10),
                DirectoryEntry("00000037.BIN", is_dir=False, size_b=10),
            ],
        )
        with patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None):
            assert files_mgr._get_last_log_number(mavftp) == (37, False)
        mavftp.cmd_get.assert_not_called()

    def test_lastlog_txt_result_short_circuits_fallbacks(self) -> None:
        """
        System prefers LASTLOG.TXT before any fallback strategy.

        GIVEN: LASTLOG.TXT contains a valid log number
        WHEN: The system searches for the most recent log
        THEN: The reported number should come from LASTLOG.TXT
        AND: Alternative strategies must not execute
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=73),
            patch.object(files_mgr, "_get_log_number_from_directory_listing") as mock_dir,
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result == (73, False)
        mock_dir.assert_not_called()

    def test_probe_fallback_is_used_when_listing_is_unavailable(self) -> None:
        """Keep the probing fallback when directory listing cannot answer."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch.object(files_mgr, "_get_log_number_from_directory_listing", return_value=(None, False)),
            patch.object(files_mgr, "_get_log_number_by_scanning", return_value=88) as scan,
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result == (88, False)
        scan.assert_called_once_with(mock_mavftp)

    def test_probe_fallback_can_find_logs_when_listing_is_unavailable(self) -> None:
        """A broken listing still permits the original numbered-log fallback."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_list.return_value = SimpleNamespace(error_code=FtpError.RemoteReplyTimeout, directory_listing=None)
        requested: list[int] = []

        def get_log(args: list[str]) -> None:
            requested.append(int(args[0].rsplit("/", maxsplit=1)[-1].split(".", maxsplit=1)[0]))

        mavftp.cmd_get.side_effect = get_log
        mavftp.process_ftp_reply.side_effect = lambda *_args, **_kwargs: SimpleNamespace(
            error_code=FtpError.Success if requested[-1] <= 37 else FtpError.FileNotFound
        )
        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.exists", return_value=False),
        ):
            assert files_mgr._get_last_log_number(mavftp) == (37, False)

        assert requested

    def test_probe_fallback_has_a_total_time_budget(self) -> None:
        """An unavailable listing on an empty controller must not trigger a minute of probes."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.process_ftp_reply.return_value = SimpleNamespace(error_code=FtpError.FileNotFound)
        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.monotonic",
                side_effect=[0, 0, 5, 10, 15],
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.exists", return_value=False),
        ):
            assert files_mgr._get_log_number_by_scanning(mavftp) is None

        assert mavftp.cmd_get.call_count == 3
        assert all(
            call.kwargs["timeout"] <= files_mgr.MAVFTP_FILE_OPERATION_TIMEOUT_SHORT
            for call in mavftp.process_ftp_reply.call_args_list
        )

    def test_probe_fallback_removes_each_probe_temp_file(self) -> None:
        """A probe cleans up the local destination before returning to the caller."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.process_ftp_reply.return_value = SimpleNamespace(error_code=FtpError.FileNotFound)

        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.monotonic", side_effect=[0, 0, 100]),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.remove") as remove,
        ):
            assert files_mgr._get_log_number_by_scanning(mavftp) is None

        remove.assert_called_once_with("temp_test_5000.tmp")

    def test_probe_fallback_exhaustion_reports_no_logs(self) -> None:
        """A completed search with no successful probes returns no log number."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.process_ftp_reply.return_value = SimpleNamespace(error_code=FtpError.FileNotFound)

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_files.monotonic", return_value=0):
            result = files_mgr._get_log_number_by_scanning(mavftp)

        assert result is None
        assert mavftp.process_ftp_reply.call_count == 13

    def test_probe_fallback_swallows_probe_exceptions(self) -> None:
        """Unexpected MAVFTP probe failures are converted into an unavailable result."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_get.side_effect = RuntimeError("probe failed")

        assert files_mgr._get_log_number_by_scanning(mavftp) is None

    def test_directory_listing_returns_highest_numeric_log(self) -> None:
        """
        Directory listing uses the highest numeric BIN file.

        GIVEN: Mixed directory contents that include BIN files and noise
        WHEN: The system inspects the MAVFTP directory listing
        THEN: The highest BIN number should be returned
        AND: Non-BIN entries are skipped
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        class ListingResult:
            """Directory listing result."""

            def __init__(self) -> None:
                self.directory_listing: list[DirectoryEntry] = [
                    DirectoryEntry("00000005.BIN", is_dir=False, size_b=0),
                    DirectoryEntry("README.TXT", is_dir=False, size_b=0),
                    DirectoryEntry("00000012.BIN", is_dir=False, size_b=0),
                    DirectoryEntry("junk", is_dir=False, size_b=0),
                ]

        mock_mavftp.cmd_list.return_value = ListingResult()

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result == (12, True)

    def test_directory_listing_returns_none_when_listing_missing(self) -> None:
        """
        Directory listing gracefully fails when MAVFTP omits entries.

        GIVEN: MAVFTP returns an object without directory details
        WHEN: The system inspects the listing response
        THEN: No log number can be produced
        AND: None should be returned
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_list.return_value = MagicMock()

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result == (None, False)

    def test_directory_listing_skips_entries_that_raise_value_error(self) -> None:
        """Directory listing continues when parsing raises ValueError."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        class FakeName(str):
            """String subclass with misleading isdigit result."""

            __slots__ = ()

            def isdigit(self) -> bool:
                return True

        class ListingResult:
            """List the FTP directory contents."""

            def __init__(self) -> None:
                self.directory_listing: list[DirectoryEntry] = [
                    DirectoryEntry(FakeName("12BADVAL.BIN"), is_dir=False, size_b=0),
                    DirectoryEntry("00000099.BIN", is_dir=False, size_b=0),
                ]

        mock_mavftp.cmd_list.return_value = ListingResult()

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result == (99, True)

    def test_directory_listing_reports_when_no_logs_found(self) -> None:
        """Directory listing reports failure when no BIN files exist."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        class ListingResult:
            """List the FTP directory contents."""

            def __init__(self) -> None:
                self.directory_listing: list[DirectoryEntry] = [
                    DirectoryEntry("README.TXT", is_dir=False, size_b=0),
                    DirectoryEntry("notes.log", is_dir=False, size_b=0),
                ]

        mock_mavftp.cmd_list.return_value = ListingResult()

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result == (None, True)

    def test_directory_listing_handles_exceptions(self) -> None:
        """Directory listing helper handles unexpected exceptions."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_list.side_effect = RuntimeError("boom")

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result == (None, False)

    def test_directory_listing_used_when_lastlog_missing(self) -> None:
        """Directory listing result is used when LASTLOG.TXT is absent."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch.object(files_mgr, "_get_log_number_from_directory_listing", return_value=(91, True)),
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result == (91, False)

    def test_log_number_lookup_reports_failure_when_all_methods_fail(self) -> None:
        """Failure is reported when no strategy yields a log number."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch.object(files_mgr, "_get_log_number_from_directory_listing", return_value=(None, False)),
            patch.object(files_mgr, "_get_log_number_by_scanning", return_value=None),
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result == (None, False)


class TestFlightControllerDirectoryCreation:
    """Test safe handling of already-existing remote paths."""

    def test_existing_regular_file_is_not_accepted_as_a_directory(self) -> None:
        """A FileExists reply must be verified before upload planning proceeds."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_mkdir.return_value = SimpleNamespace(error_code=FtpError.FileExists)
        mavftp.cmd_list.return_value = SimpleNamespace(error_code=FtpError.FileNotFound, directory_listing=None)

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            assert not files_mgr.make_remote_directory("/APM/LOGS/already-a-file")

        mavftp.cmd_list.assert_called_once_with(["/APM/LOGS/already-a-file/"])

    def test_existing_empty_directory_is_accepted_after_verification(self) -> None:
        """An empty directory yields a successful empty MAVFTP listing."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_mkdir.return_value = SimpleNamespace(error_code=FtpError.FileExists)
        mavftp.cmd_list.return_value = SimpleNamespace(error_code=FtpError.Success, directory_listing=[])

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            assert files_mgr.make_remote_directory("/APM/LOGS/existing")

        mavftp.cmd_list.assert_called_once_with(["/APM/LOGS/existing/"])

    def test_upload_parent_creation_rejects_a_file_occupying_the_parent_name(self) -> None:
        """Recursive uploads stop before trying to put a child below a regular file."""
        files_mgr = _create_files_manager()
        mavftp = MagicMock()
        mavftp.cmd_mkdir.return_value = MagicMock(error_code=FtpError.FileExists)
        mavftp.cmd_list.return_value = SimpleNamespace(error_code=FtpError.FileNotFound, directory_listing=None)

        assert not files_mgr._ensure_remote_directory_exists(mavftp, "/APM/LOGS/file.bin")

        mavftp.cmd_list.assert_called_once_with(["/APM"])


class TestFlightControllerDirectoryCacheInvalidation:
    """Cache invalidation must survive uncertain remote mutations."""

    @pytest.mark.parametrize("operation", ["delete", "rename"])
    def test_uncertain_remote_mutation_invalidates_verified_directories(self, operation: str) -> None:
        """A failed or lost mutation reply must not make a stale directory look verified."""
        files_mgr = _create_files_manager()
        files_mgr._verified_remote_directories.add("/APM/LOGS")
        mavftp = MagicMock()
        uncertain_reply = SimpleNamespace(error_code=FtpError.RemoteReplyTimeout)
        if operation == "delete":
            mavftp.cmd_rm.return_value = uncertain_reply
        else:
            mavftp.cmd_rename.return_value = uncertain_reply

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mavftp,
        ):
            if operation == "delete":
                assert not files_mgr.delete_remote_path("/APM/LOGS/stale.bin")
            else:
                assert not files_mgr.rename_remote_path("/APM/LOGS/old.bin", "/APM/LOGS/new.bin")

        assert files_mgr._verified_remote_directories == set()


class TestFlightControllerFilesDownloadHelpers:
    """Test helper utilities for downloading logs."""

    def test_remote_parent_directory_helper_normalizes_paths(self) -> None:
        """
        Remote parent directory helper should collapse redundant segments.

        GIVEN: A remote path containing duplicate separators and a dot segment
        WHEN: The helper derives the parent directories
        THEN: Only normalized absolute parents should be returned
        """
        parents = FlightControllerFiles._remote_parent_directories("/APM//Scripts/./VTOL-quicktune.lua")

        assert parents == ["/APM", "/APM/Scripts"]

    def test_remote_parent_directory_helper_returns_noops_for_root_paths(self) -> None:
        """Root and relative paths should not trigger mkdir calls."""
        assert FlightControllerFiles._remote_parent_directories("/") == []  # pylint: disable=use-implicit-booleaness-not-comparison
        assert FlightControllerFiles._remote_parent_directories("Scripts/VTOL-quicktune.lua") == []  # pylint: disable=use-implicit-booleaness-not-comparison

    def test_download_log_file_reports_mavftp_errors(self) -> None:
        """
        Download helper reports MAVFTP failures to the caller.

        GIVEN: MAVFTP rejects the requested log download
        WHEN: The helper executes the download workflow
        THEN: The operation should fail with False
        AND: The MAVFTP error message should be surfaced
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_ret = MagicMock()
        mock_ret.error_code = 1
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        result = files_mgr._download_log_file(
            mavftp_instance=mock_mavftp,
            remote_filenumber=9,
            local_filename="/tmp/00000009.BIN",  # noqa: S108
            get_progress_callback=lambda *_args: None,
        )

        assert result is False
        mock_ret.display_message.assert_called_once()

    def test_download_log_file_succeeds_with_progress_updates(self) -> None:
        """
        Download helper streams progress before reporting success.

        GIVEN: MAVFTP accepts the download request
        WHEN: The helper transfers the desired BIN file
        THEN: The call should return True
        AND: The caller should receive progress callbacks
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_ret = MagicMock()
        mock_ret.error_code = 0
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        def _progress_callback(current: int, total: int) -> None:
            del current, total

        result = files_mgr._download_log_file(
            mavftp_instance=mock_mavftp,
            remote_filenumber=10,
            local_filename="/tmp/00000010.BIN",  # noqa: S108
            get_progress_callback=_progress_callback,
        )

        assert result is True
        mock_mavftp.cmd_get.assert_called_once()
        assert mock_mavftp.cmd_get.call_args.kwargs["progress_callback"] is _progress_callback

    def test_extract_log_number_reads_value_and_cleans_file(self, tmp_path: Path) -> None:
        """
        LASTLOG extractor reads value and cleans up temporary file.

        GIVEN: LASTLOG.TXT contains a trailing newline with the last log number
        WHEN: The extractor parses the file
        THEN: The number should be returned as int
        AND: The temporary file should be removed afterward
        """
        files_mgr = _create_files_manager()
        temp_file = tmp_path / "lastlog.txt"
        temp_file.write_text("57\n", encoding="UTF-8")

        result = files_mgr._extract_log_number_from_file(str(temp_file))

        assert result == 57
        assert not temp_file.exists()


class TestFlightControllerFilesLastlogTxt:
    """Test behaviors around LASTLOG.TXT lookups."""

    def test_lastlog_txt_returns_value_when_available(self) -> None:
        """LASTLOG helper returns parsed number when MAVFTP succeeds."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_ret = MagicMock()
        mock_ret.error_code = 0
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        with patch.object(files_mgr, "_extract_log_number_from_file", return_value=55) as mock_extract:
            result = files_mgr._get_log_number_from_lastlog_txt(mock_mavftp)

        assert result == 55
        mock_mavftp.cmd_get.assert_called_once()
        mock_extract.assert_called_once()

    def test_lastlog_txt_returns_none_when_file_missing(self) -> None:
        """LASTLOG helper returns None when MAVFTP reports error."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_ret = MagicMock()
        mock_ret.error_code = 2
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        result = files_mgr._get_log_number_from_lastlog_txt(mock_mavftp)

        assert result is None

    def test_lastlog_txt_handles_exceptions(self) -> None:
        """LASTLOG helper handles unexpected exceptions."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_get.side_effect = RuntimeError("boom")

        result = files_mgr._get_log_number_from_lastlog_txt(mock_mavftp)

        assert result is None

    def test_extract_log_number_handles_invalid_content(self, tmp_path: Path) -> None:
        """
        LASTLOG extractor handles invalid files gracefully.

        GIVEN: LASTLOG.TXT contains unreadable content
        WHEN: The extractor attempts to parse it
        THEN: None should be returned
        AND: The temporary file should still be removed
        """
        files_mgr = _create_files_manager()
        temp_file = tmp_path / "bad_lastlog.txt"
        temp_file.write_text("not-a-number", encoding="UTF-8")

        result = files_mgr._extract_log_number_from_file(str(temp_file))

        assert result is None
        assert not temp_file.exists()

    def test_download_log_file_handles_exceptions(self) -> None:
        """Download helper handles unexpected exceptions from MAVFTP."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_get.side_effect = RuntimeError("boom")

        result = files_mgr._download_log_file(
            mavftp_instance=mock_mavftp,
            remote_filenumber=11,
            local_filename="/tmp/00000011.BIN",  # noqa: S108
            get_progress_callback=lambda *_: None,
        )

        assert result is False


class TestFlightControllerFilesConstants:
    """Test MAVFTP timeout constants are properly defined."""

    def test_mavftp_timeout_constants_are_defined(self) -> None:
        """
        MAVFTP timeout constants should be defined for file operations.

        GIVEN: FlightControllerFiles class
        WHEN: Checking timeout constants
        THEN: Constants should be defined with reasonable values
        """
        # When/Then: Check constants
        assert hasattr(FlightControllerFiles, "MAVFTP_FILE_OPERATION_TIMEOUT")

        assert FlightControllerFiles.MAVFTP_FILE_OPERATION_TIMEOUT == 10

    def test_upload_timeout_increases_for_large_files(self, tmp_path: Path) -> None:
        """Large uploads receive more time than the minimum upload deadline."""
        files_mgr = _create_files_manager()
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"x" * (1024 * 100))

        assert files_mgr._upload_timeout(str(large_file)) == 40


class TestFlightControllerFilesPropertyDelegation:
    """Test property delegation to connection manager."""

    def test_master_property_delegates_to_connection_manager(self) -> None:
        """
        Master property correctly delegates to connection manager.

        GIVEN: Files manager with connection manager
        WHEN: Accessing master property
        THEN: Connection manager's master should be returned
        """
        # Given: Connection with master
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        # When: Access master
        retrieved_master = files_mgr.master

        # Then: Correct master returned
        assert retrieved_master is mock_master

    def test_info_property_delegates_to_connection_manager(self) -> None:
        """
        Info property correctly delegates to connection manager.

        GIVEN: Files manager with connection manager
        WHEN: Accessing info property
        THEN: Connection manager's info should be returned
        """
        # Given: Connection with info
        mock_info = FlightControllerInfo()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = mock_info

        files_mgr = FlightControllerFiles(connection_manager=mock_conn_mgr)

        # When: Access info
        retrieved_info = files_mgr.info

        # Then: Correct info returned
        assert retrieved_info is mock_info
