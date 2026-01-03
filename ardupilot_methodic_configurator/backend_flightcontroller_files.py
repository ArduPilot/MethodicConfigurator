"""
Flight controller file operations using MAVFTP.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from typing import TYPE_CHECKING, Callable, ClassVar, Optional, Union

from pymavlink import mavutil

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp import create_mavftp_safe
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller_protocols import FlightControllerConnectionProtocol

# Conditionally import MAVFTP if available
try:
    from ardupilot_methodic_configurator.backend_mavftp import MAVFTP

    # from pymavlink import mavftp
    # MAVFTP = mavftp.MAVFTP
except ImportError:
    MAVFTP = None  # type: ignore[assignment,misc]


class FlightControllerFiles:
    """
    Handles file operations via MAVFTP protocol.

    This class manages all file transfer operations:
    - Uploading files to flight controller
    - Downloading files from flight controller
    - Finding and downloading last flight log
    - Directory listing and scanning
    """

    # MAVFTP timeout constants
    MAVFTP_FILE_OPERATION_TIMEOUT: ClassVar[int] = 10
    MAVFTP_FILE_OPERATION_TIMEOUT_SHORT: ClassVar[int] = 5

    def __init__(
        self,
        connection_manager: Optional["FlightControllerConnectionProtocol"] = None,
    ) -> None:
        """
        Initialize the file operations manager.

        Args:
            connection_manager: Connection manager to get master and info from

        """
        if connection_manager is None:
            msg = "connection_manager is required"
            raise ValueError(msg)
        self._connection_manager: FlightControllerConnectionProtocol = connection_manager

    @property
    def master(self) -> Optional[mavutil.mavlink_connection]:  # pyright: ignore[reportGeneralTypeIssues]
        """Get master connection."""
        return self._connection_manager.master

    @property
    def info(self) -> FlightControllerInfo:
        """Get flight controller info."""
        return self._connection_manager.info

    def upload_file(
        self, local_filename: str, remote_filename: str, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> bool:
        """
        Upload a file to the flight controller.

        Args:
            local_filename: Local file path to upload
            remote_filename: Remote file path on flight controller
            progress_callback: Optional callback function for progress updates (current, total)

        Returns:
            bool: True if upload was successful, False otherwise

        """
        if self.master is None:
            logging_error(_("No flight controller connection available for file upload"))
            return False

        mavftp_instance = create_mavftp_safe(self.master)
        if mavftp_instance is None:
            logging_error(_("MAVFTP is not available for file upload"))
            return False

        def put_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        try:
            mavftp_instance.cmd_put([local_filename, remote_filename], progress_callback=put_progress_callback)
            ret = mavftp_instance.process_ftp_reply("CreateFile", timeout=self.MAVFTP_FILE_OPERATION_TIMEOUT)
            if ret.error_code != 0:
                ret.display_message()
                return False
            logging_info(
                _("Successfully uploaded %(local)s to %(remote)s"), {"local": local_filename, "remote": remote_filename}
            )
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to upload file: %(error)s"), {"error": str(e)})
            return False

    def download_last_flight_log(
        self, local_filename: str, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> bool:
        """
        Download the last flight log from the flight controller.

        Args:
            local_filename: Local file path to save the downloaded log
            progress_callback: Optional callback function for progress updates (current, total)

        Returns:
            bool: True if download was successful, False otherwise

        """
        if self.master is None:
            error_msg = _("No flight controller connected")
            logging_error(error_msg)
            return False
        if not self.info.is_mavftp_supported:
            error_msg = _("MAVFTP is not supported by the flight controller")
            logging_error(error_msg)
            return False

        mavftp_instance = create_mavftp_safe(self.master)
        if mavftp_instance is None:
            logging_error(_("MAVFTP is not available for file download"))
            return False

        def get_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        try:
            # Try to get the last log number using different methods
            remote_filenumber = self._get_last_log_number(mavftp_instance)
            if remote_filenumber is None:
                return False

            return self._download_log_file(mavftp_instance, remote_filenumber, local_filename, get_progress_callback)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Error during flight log download: %(error)s"), {"error": str(e)})
            return False

    def _get_last_log_number(self, mavftp_instance: "MAVFTP") -> Optional[int]:  # pyright: ignore[reportInvalidTypeForm]
        """
        Get the last log number using multiple fallback methods.

        Args:
            mavftp_instance: MAVFTP object for file operations

        Returns:
            Optional[int]: Last log number, or None if not found

        """
        # Method 1: Try to get LASTLOG.TXT
        log_number = self._get_log_number_from_lastlog_txt(mavftp_instance)
        if log_number is not None:
            return log_number

        # Method 2: Try to list the logs directory and find the highest numbered log
        log_number = self._get_log_number_from_directory_listing(mavftp_instance)
        if log_number is not None:
            return log_number

        # Method 3: Try common log numbers (scan backwards from a reasonable max)
        log_number = self._get_log_number_by_scanning(mavftp_instance)
        if log_number is not None:
            return log_number

        logging_error(_("Could not determine the last log number using any method"))
        return None

    def _get_log_number_from_lastlog_txt(
        self,
        mavftp_instance: "MAVFTP",  # pyright: ignore[reportInvalidTypeForm]
    ) -> Optional[int]:
        """
        Try to get the log number from LASTLOG.TXT file.

        Args:
            mavftp_instance: MAVFTP object for file operations

        Returns:
            Optional[int]: Log number from LASTLOG.TXT, or None if not available

        """
        logging_info(_("Trying to get log number from LASTLOG.TXT"))
        try:
            temp_lastlog_file = "temp_lastlog.txt"
            mavftp_instance.cmd_get(["/APM/LOGS/LASTLOG.TXT", temp_lastlog_file])
            ret = mavftp_instance.process_ftp_reply("OpenFileRO", timeout=self.MAVFTP_FILE_OPERATION_TIMEOUT)
            if ret.error_code != 0:
                logging_warning(_("LASTLOG.TXT not available, trying alternative methods"))
                return None

            return self._extract_log_number_from_file(temp_lastlog_file)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to get log number from LASTLOG.TXT: %(error)s"), {"error": str(e)})
            return None

    def _get_log_number_from_directory_listing(
        self,
        mavftp_instance: "MAVFTP",  # pyright: ignore[reportInvalidTypeForm]
    ) -> Optional[int]:
        """
        Try to get the highest log number by listing the logs directory using MAVFTP.

        Args:
            mavftp_instance: MAVFTP object for file operations

        Returns:
            int: Highest log number from directory listing, or None if not found

        """
        logging_info(_("Trying to get log number from directory listing"))
        try:
            result = mavftp_instance.cmd_list(["/APM/LOGS/"])
            if not hasattr(result, "directory_listing") or not isinstance(result.directory_listing, dict):
                logging_error(_("No directory listing found in MAVFTPReturn"))
                return None
            highest = -1
            for name in result.directory_listing:
                # Typical log file names: 00000036.BIN, 00000037.BIN, etc.
                if name.endswith(".BIN") and name[:8].isdigit():
                    try:
                        log_num = int(name[:8])
                        highest = max(highest, log_num)
                    except ValueError:
                        continue
            if highest != -1:
                logging_info(_("Highest log number found: %(number)d"), {"number": highest})
                return highest
            logging_error(_("No log files found in directory listing"))
            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to get log number from directory listing: %(error)s"), {"error": str(e)})
            return None

    def _get_log_number_by_scanning(
        self,
        mavftp_instance: "MAVFTP",  # pyright: ignore[reportInvalidTypeForm]
    ) -> Optional[int]:
        """
        Try to find the last log using binary search for efficiency.

        Args:
            mavftp_instance: MAVFTP object for file operations

        Returns:
            Optional[int]: Highest log number found, or None if not found

        """
        logging_info(_("Trying to find log number using binary search"))
        try:
            # Binary search to find the highest log number
            low = 1
            high = 9999  # Reasonable upper bound for log numbers
            last_found = None

            while low <= high:
                mid = (low + high) // 2
                remote_filename = f"/APM/LOGS/{mid:08}.BIN"

                # Test if this log file exists
                temp_test_file = f"temp_test_{mid}.tmp"
                mavftp_instance.cmd_get([remote_filename, temp_test_file])
                # Must be > idle_detection_time (3.7s)
                ret = mavftp_instance.process_ftp_reply("OpenFileRO", timeout=self.MAVFTP_FILE_OPERATION_TIMEOUT_SHORT)

                # Clean up the temp file if it was created
                if os.path.exists(temp_test_file):
                    os.remove(temp_test_file)

                if ret.error_code == 0:
                    # File exists, search in upper half
                    last_found = mid
                    low = mid + 1
                    logging_debug(_("Log %(number)d exists, searching higher"), {"number": mid})
                else:
                    # File doesn't exist, search in lower half
                    high = mid - 1
                    logging_debug(_("Log %(number)d doesn't exist, searching lower"), {"number": mid})

            if last_found is not None:
                logging_info(_("Found highest log number using binary search: %(number)d"), {"number": last_found})
                return last_found

            logging_warning(_("No log files found using binary search"))
            return None

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to scan for log numbers using binary search: %(error)s"), {"error": str(e)})
            return None

    def _download_log_file(
        self,
        mavftp_instance: "MAVFTP",  # pyright: ignore[reportInvalidTypeForm]
        remote_filenumber: int,
        local_filename: str,
        get_progress_callback: Callable,
    ) -> bool:
        """
        Download the actual log file from the flight controller.

        Args:
            mavftp_instance: MAVFTP object for file operations
            remote_filenumber: Remote log file number to download
            local_filename: Local file path to save the downloaded log
            get_progress_callback: Callback function for progress updates

        Returns:
            bool: True if download was successful, False otherwise

        """
        remote_filename = f"/APM/LOGS/{remote_filenumber:08}.BIN"
        logging_info(_("Downloading flight log %(remote)s to %(local)s"), {"remote": remote_filename, "local": local_filename})

        try:
            # Download the actual log file
            mavftp_instance.cmd_get([remote_filename, local_filename], progress_callback=get_progress_callback)
            ret = mavftp_instance.process_ftp_reply("OpenFileRO", timeout=0)  # No timeout for large log files
            if ret.error_code != 0:
                logging_error(_("Failed to download flight log %(remote)s"), {"remote": remote_filename})
                ret.display_message()
                return False

            logging_info(_("Successfully downloaded flight log to %(local)s"), {"local": local_filename})
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to download log file: %(error)s"), {"error": str(e)})
            return False

    def _extract_log_number_from_file(self, temp_lastlog_file: str) -> Optional[int]:
        """
        Extract log number from LASTLOG.TXT file and clean up the temporary file.

        Args:
            temp_lastlog_file: Path to the file containing the log number

        Returns:
            Optional[int]: Log number from the file, or None if not found or parsing failed

        """
        try:
            with open(temp_lastlog_file, encoding="UTF-8") as file:
                file_contents = file.readline()
                return int(file_contents.strip())
        except (FileNotFoundError, ValueError) as e:
            logging_error(_("Could not extract last log file number from LASTLOG.TXT: %(error)s"), {"error": str(e)})
            return None
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_lastlog_file):
                os.remove(temp_lastlog_file)
