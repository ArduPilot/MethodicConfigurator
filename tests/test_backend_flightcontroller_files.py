#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_files.py.

This file focuses on MAVFTP file operations behavior including file uploads,
log downloads, and error handling for unavailable MAVFTP functionality.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from typing import Callable, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerFiles
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo


def _create_files_manager() -> FlightControllerFiles:
    """Helper to build a files manager with default mocks."""
    mock_conn_mgr = Mock()
    mock_conn_mgr.master = MagicMock()
    info = FlightControllerInfo()
    info.is_mavftp_supported = True
    mock_conn_mgr.info = info
    return FlightControllerFiles(connection_manager=mock_conn_mgr)


# pylint: disable=protected-access, too-few-public-methods


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
        callback = mock_mavftp.cmd_put.call_args.kwargs["progress_callback"]
        callback(0.42)
        assert progress_calls == [(42, 100)]

    def test_file_upload_reports_mavftp_error_code(self) -> None:
        """Upload reports MAVFTP errors when CreateFile fails."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_ret = MagicMock()
        mock_ret.error_code = 5
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mock_mavftp,
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

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=mock_mavftp,
        ):
            success = files_mgr.upload_file(
                local_filename="/tmp/test.param",  # noqa: S108
                remote_filename="@SYS/test.param",
            )

        assert success is False


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

    def test_log_download_fails_when_last_log_unknown(self) -> None:
        """
        Users receive clear failure when no log number is discoverable.

        GIVEN: MAVFTP connection is available but no discovery strategy succeeds
        WHEN: User requests the last flight log download
        THEN: Operation should stop gracefully with False
        AND: Actual download helper should never be invoked
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
                return_value=mock_mavftp,
            ),
            patch.object(files_mgr, "_get_last_log_number", return_value=None),
            patch.object(files_mgr, "_download_log_file") as mock_download,
        ):
            result = files_mgr.download_last_flight_log(local_filename="/tmp/last.BIN")  # noqa: S108

        assert result is False
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

        assert result is False
        mock_factory.assert_not_called()

    def test_log_download_fails_when_mavftp_instance_missing(self) -> None:
        """Download fails when MAVFTP creation returns None."""
        files_mgr = _create_files_manager()

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.create_mavftp_safe",
            return_value=None,
        ):
            result = files_mgr.download_last_flight_log(local_filename="/tmp/missing_instance.BIN")  # noqa: S108

        assert result is False

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
            patch.object(files_mgr, "_get_last_log_number", return_value=3),
            patch.object(files_mgr, "_download_log_file", side_effect=fake_download),
        ):
            result = files_mgr.download_last_flight_log(
                local_filename="/tmp/00000003.BIN",  # noqa: S108
                progress_callback=user_progress,
            )

        assert result is True
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

        assert result is False


class TestFlightControllerFilesLogDiscovery:
    """Test LASTLOG, directory listing, and scanning behaviors."""

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
            patch.object(files_mgr, "_get_log_number_by_scanning") as mock_scan,
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result == 73
        mock_dir.assert_not_called()
        mock_scan.assert_not_called()

    def test_binary_search_used_when_prior_methods_fail(self) -> None:
        """
        Binary search is used after LASTLOG and directory listing fail.

        GIVEN: LASTLOG.TXT and directory listings provide no clues
        WHEN: The system hunts for the last log number
        THEN: Binary search should provide the answer
        AND: The returned value should match the binary search discovery
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch.object(files_mgr, "_get_log_number_from_directory_listing", return_value=None),
            patch.object(files_mgr, "_get_log_number_by_scanning", return_value=88) as mock_scan,
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result == 88
        mock_scan.assert_called_once_with(mock_mavftp)

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
                self.directory_listing: dict[str, dict[str, object]] = {
                    "00000005.BIN": {},
                    "README.TXT": {},
                    "00000012.BIN": {},
                    "junk": {},
                }

        mock_mavftp.cmd_list.return_value = ListingResult()

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result == 12

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

        assert result is None

    def test_binary_search_returns_highest_log_number(self) -> None:
        """
        Binary search converges on the highest available log number.

        GIVEN: MAVFTP responds with success for files up to a known number
        WHEN: The system performs its binary search strategy
        THEN: The discovered number matches the highest available log
        AND: Search terminates without errors
        """
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        highest = 37
        state: dict[str, Optional[int]] = {"last": None}

        def record_request(args: list[str], progress_callback: Optional[Callable[[int, int], None]] = None) -> None:
            del progress_callback
            remote_filename = args[0]
            state["last"] = int(remote_filename.split("/")[-1].split(".")[0])

        def build_reply(*_args: object, **_kwargs: object) -> MagicMock:
            ret = MagicMock()
            last = state["last"]
            if last is None:
                ret.error_code = 1
            elif last <= highest:
                ret.error_code = 0
            else:
                ret.error_code = 5
            return ret

        mock_mavftp.cmd_get.side_effect = record_request
        mock_mavftp.process_ftp_reply.side_effect = build_reply

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.exists",
            return_value=False,
        ):
            result = files_mgr._get_log_number_by_scanning(mock_mavftp)

        assert result == 37

    def test_binary_search_removes_temp_files_when_present(self) -> None:
        """Binary search cleans temp files when they exist."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        highest = 2
        state: dict[str, Optional[int]] = {"last": None}

        def record_request(args: list[str], *_: object, **__: object) -> None:
            remote_filename = args[0]
            state["last"] = int(remote_filename.split("/")[-1].split(".")[0])

        def build_reply(*_args: object, **_kwargs: object) -> MagicMock:
            ret = MagicMock()
            last = state["last"]
            ret.error_code = 0 if last is not None and last <= highest else 5
            return ret

        mock_mavftp.cmd_get.side_effect = record_request
        mock_mavftp.process_ftp_reply.side_effect = build_reply

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.exists",
                return_value=True,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_files.os.remove") as mock_remove,
        ):
            result = files_mgr._get_log_number_by_scanning(mock_mavftp)

        assert result == 2
        mock_remove.assert_called()

    def test_binary_search_reports_none_when_no_files_found(self) -> None:
        """Binary search reports None when no files respond."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_ret = MagicMock()
        mock_ret.error_code = 5
        mock_mavftp.process_ftp_reply.return_value = mock_ret

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_files.os.path.exists",
            return_value=False,
        ):
            result = files_mgr._get_log_number_by_scanning(mock_mavftp)

        assert result is None

    def test_binary_search_handles_exceptions(self) -> None:
        """Binary search helper handles unexpected exceptions."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_get.side_effect = RuntimeError("boom")

        result = files_mgr._get_log_number_by_scanning(mock_mavftp)

        assert result is None

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
                self.directory_listing: dict[str, dict[str, object]] = {
                    FakeName("12BADVAL.BIN"): {},
                    "00000099.BIN": {},
                }

        mock_mavftp.cmd_list.return_value = ListingResult()

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result == 99

    def test_directory_listing_reports_when_no_logs_found(self) -> None:
        """Directory listing reports failure when no BIN files exist."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        class ListingResult:
            """List the FTP directory contents."""

            def __init__(self) -> None:
                self.directory_listing: dict[str, dict[str, object]] = {"README.TXT": {}, "notes.log": {}}

        mock_mavftp.cmd_list.return_value = ListingResult()

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result is None

    def test_directory_listing_handles_exceptions(self) -> None:
        """Directory listing helper handles unexpected exceptions."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()
        mock_mavftp.cmd_list.side_effect = RuntimeError("boom")

        result = files_mgr._get_log_number_from_directory_listing(mock_mavftp)

        assert result is None

    def test_directory_listing_used_when_lastlog_missing(self) -> None:
        """Directory listing result is used when LASTLOG.TXT is absent."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch.object(files_mgr, "_get_log_number_from_directory_listing", return_value=91),
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result == 91

    def test_log_number_lookup_reports_failure_when_all_methods_fail(self) -> None:
        """Failure is reported when no strategy yields a log number."""
        files_mgr = _create_files_manager()
        mock_mavftp = MagicMock()

        with (
            patch.object(files_mgr, "_get_log_number_from_lastlog_txt", return_value=None),
            patch.object(files_mgr, "_get_log_number_from_directory_listing", return_value=None),
            patch.object(files_mgr, "_get_log_number_by_scanning", return_value=None),
        ):
            result = files_mgr._get_last_log_number(mock_mavftp)

        assert result is None


class TestFlightControllerFilesDownloadHelpers:
    """Test helper utilities for downloading logs."""

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
