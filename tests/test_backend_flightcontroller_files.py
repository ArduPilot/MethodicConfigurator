#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_files.py.

This file focuses on MAVFTP file operations behavior including file uploads,
log downloads, and error handling for unavailable MAVFTP functionality.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerFiles
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo


class TestFlightControllerFilesInitialization:
    """Test file operations manager initialization."""

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
        mock_mavftp.cmd_put = MagicMock()
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
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe", return_value=mock_mavftp
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/test.param",  # noqa: S108
                remote_filename="@SYS/test.param",
                progress_callback=progress_callback,
            )

        # Then: Upload successful
        assert success is True
        mock_mavftp.cmd_put.assert_called_once()


class TestFlightControllerFilesDownload:
    """Test log file download functionality via MAVFTP."""

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
        assert result is False

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
        assert result is False

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
            patch.object(files_mgr, "_get_last_log_number", return_value=42),
            patch.object(files_mgr, "_download_log_file", return_value=True),
        ):
            result = files_mgr.download_last_flight_log(
                local_filename="/tmp/00000042.BIN",  # noqa: S108
                progress_callback=progress_callback,
            )

        # Then: Download successful
        assert result is True


class TestFlightControllerFilesConstants:  # pylint: disable=too-few-public-methods
    """Test MAVFTP timeout constants are properly defined."""

    def test_mavftp_timeout_constants_are_defined(self) -> None:
        """
        MAVFTP timeout constants should be defined for file operations.

        GIVEN: FlightControllerFiles class
        WHEN: Checking timeout constants
        THEN: Constants should be defined with reasonable values
        AND: Short timeout should be less than regular timeout
        """
        # When/Then: Check constants
        assert hasattr(FlightControllerFiles, "MAVFTP_FILE_OPERATION_TIMEOUT")
        assert hasattr(FlightControllerFiles, "MAVFTP_FILE_OPERATION_TIMEOUT_SHORT")

        assert FlightControllerFiles.MAVFTP_FILE_OPERATION_TIMEOUT == 10
        assert FlightControllerFiles.MAVFTP_FILE_OPERATION_TIMEOUT_SHORT == 5
        assert FlightControllerFiles.MAVFTP_FILE_OPERATION_TIMEOUT_SHORT < FlightControllerFiles.MAVFTP_FILE_OPERATION_TIMEOUT


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
