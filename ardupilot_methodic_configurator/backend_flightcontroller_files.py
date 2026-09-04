"""
Flight controller file operations using MAVFTP.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import posixpath
from collections.abc import Callable
from dataclasses import dataclass
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from typing import TYPE_CHECKING, ClassVar, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp import create_mavftp_safe
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller_protocols import (
        FlightControllerConnectionProtocol,
        MavlinkConnection,
    )
    from ardupilot_methodic_configurator.backend_mavftp import MAVFTP as MAVFTPType  # noqa: N811

from ardupilot_methodic_configurator.backend_mavftp import MAVFTP, FtpError


@dataclass(frozen=True)
class FlightControllerLogFile:
    """A regular file exposed by a flight-controller directory listing."""

    name: str
    remote_path: str
    size_bytes: int
    is_directory: bool = False


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
    DEFAULT_LOG_DIRECTORY: ClassVar[str] = "/APM/LOGS/"

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
    def master(self) -> Optional["MavlinkConnection"]:
        """Get master connection."""
        return self._connection_manager.master

    @property
    def info(self) -> FlightControllerInfo:
        """Get flight controller info."""
        return self._connection_manager.info

    def upload_file(  # noqa: PLR0911 # pylint: disable=too-many-return-statements
        self, local_filename: str, remote_filename: str, progress_callback: Callable[[int, int], None] | None = None
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
            if not os.path.isfile(local_filename):
                logging_error(_("Local file does not exist or is not a regular file: %(local)s"), {"local": local_filename})
                return False

            if not self._ensure_remote_directory_exists(mavftp_instance, remote_filename):
                return False

            put_ret = mavftp_instance.cmd_put([local_filename, remote_filename], progress_callback=put_progress_callback)
            if put_ret.error_code != FtpError.Success:
                put_ret.display_message()
                return False

            ret = mavftp_instance.process_ftp_reply("CreateFile", timeout=self.MAVFTP_FILE_OPERATION_TIMEOUT)
            if ret.error_code != FtpError.Success:
                ret.display_message()
                return False
            logging_info(
                _("Successfully uploaded %(local)s to %(remote)s"), {"local": local_filename, "remote": remote_filename}
            )
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            try:
                mavftp_instance.cmd_cancel()
            except Exception:  # pylint: disable=broad-exception-caught
                logging_debug("Could not cancel failed MAVFTP upload", exc_info=True)
            logging_error(_("Failed to upload file: %(error)s"), {"error": str(e)})
            return False

    def _ensure_remote_directory_exists(self, mavftp_instance: "MAVFTPType", remote_filename: str) -> bool:
        """
        Ensure all parent directories for a remote MAVFTP file path exist.

        ArduPilot's MAVFTP CreateFile operation fails with "file/directory not found" when the parent
        directory is missing. Create every absolute parent directory before uploading, after normalizing
        the path, and treat "already exists" as success.
        """
        parent_directories = self._remote_parent_directories(remote_filename)
        if not parent_directories:
            return True

        for current_dir in parent_directories:
            ret = mavftp_instance.cmd_mkdir([current_dir])
            if ret.error_code not in {FtpError.Success, FtpError.FileExists}:
                ret.display_message()
                logging_error(_("Failed to create remote directory %(directory)s"), {"directory": current_dir})
                return False
        return True

    @staticmethod
    def _remote_parent_directories(remote_filename: str) -> list[str]:
        """Return the absolute parent directories that should exist for a remote file path."""
        remote_dir = posixpath.dirname(remote_filename)
        remote_dir = posixpath.normpath(remote_dir)
        if not remote_dir or remote_dir in {".", "/"} or not remote_dir.startswith("/"):
            return []

        current_dir = ""
        parent_directories: list[str] = []
        for part in remote_dir.strip("/").split("/"):
            if not part:
                continue
            current_dir = f"{current_dir}/{part}"
            parent_directories.append(current_dir)
        return parent_directories

    def download_last_flight_log(
        self, local_filename: str, progress_callback: Callable[[int, int], None] | None = None
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

    @classmethod
    def _normalize_remote_path(cls, remote_path: str, *, directory: bool = False) -> str:
        """Normalize and validate an absolute MAVFTP path."""
        if not isinstance(remote_path, str) or not remote_path.strip():
            msg = _("Remote path must not be empty")
            raise ValueError(msg)

        # Do not strip the path itself: leading/trailing spaces can be valid
        # filename characters on the flight controller. Only whitespace-only
        # paths are rejected above.
        path = remote_path.replace("\\", "/")
        if not path.startswith("/"):
            msg = _("Remote path must be absolute")
            raise ValueError(msg)

        if ".." in path.split("/"):
            msg = _("Remote path must not contain parent-directory segments")
            raise ValueError(msg)

        normalized = posixpath.normpath(path)
        if not normalized.startswith("/"):
            msg = _("Remote path must be absolute")
            raise ValueError(msg)

        if directory:
            return normalized if normalized == "/" else f"{normalized}/"
        return normalized

    @classmethod
    def _remote_child_path(cls, remote_directory: str, filename: str) -> str:
        """Build a safe remote path for a direct child of a remote directory."""
        if (
            not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or posixpath.basename(filename) != filename
        ):
            msg = _("Remote directory entries must be regular file names")
            raise ValueError(msg)
        directory = cls._normalize_remote_path(remote_directory, directory=True)
        return posixpath.join(directory, filename)

    def list_remote_files(self, remote_directory: str = DEFAULT_LOG_DIRECTORY) -> list[FlightControllerLogFile]:  # noqa: PLR0911
        """List regular files and directories in a remote directory."""
        if self.master is None:
            logging_error(_("No flight controller connected"))
            return []
        if not self.info.is_mavftp_supported:
            logging_error(_("MAVFTP is not supported by the flight controller"))
            return []

        try:
            normalized_directory = self._normalize_remote_path(remote_directory, directory=True)
        except ValueError as error:
            logging_error(_("Invalid remote directory: %(error)s"), {"error": str(error)})
            return []

        mavftp_instance = create_mavftp_safe(self.master)
        if mavftp_instance is None:
            logging_error(_("MAVFTP is not available for file listing"))
            return []

        try:
            result = mavftp_instance.cmd_list([normalized_directory])
            listing = getattr(result, "directory_listing", None)
            if not isinstance(listing, list):
                logging_error(_("No directory listing found in MAVFTPReturn"))
                return []

            entries: list[FlightControllerLogFile] = []
            for entry in listing:
                try:
                    remote_path = self._remote_child_path(normalized_directory, entry.name)
                except ValueError:
                    logging_warning(_("Skipping invalid remote directory entry: %(name)s"), {"name": entry.name})
                    continue
                entries.append(
                    FlightControllerLogFile(
                        entry.name,
                        remote_path,
                        max(0, int(entry.size_b)),
                        bool(entry.is_dir),
                    )
                )
            return entries
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to list remote directory: %(error)s"), {"error": str(error)})
            return []

    def list_bin_log_files(self, remote_directory: str = DEFAULT_LOG_DIRECTORY) -> list[FlightControllerLogFile]:
        """
        List all regular files in a remote directory.

        The historical method name is retained because this operation is launched
        by the .bin-log UI, but the listing intentionally accepts every regular
        file returned by MAVFTP.
        """
        return [entry for entry in self.list_remote_files(remote_directory) if not entry.is_directory]

    def make_remote_directory(self, remote_directory: str) -> bool:
        """Create a remote directory, treating an existing directory as success."""
        if self.master is None or not self.info.is_mavftp_supported:
            return False
        try:
            normalized_directory = self._normalize_remote_path(remote_directory, directory=True)
        except ValueError as error:
            logging_error(_("Invalid remote directory: %(error)s"), {"error": str(error)})
            return False
        if normalized_directory == "/":
            return True

        mavftp_instance = create_mavftp_safe(self.master)
        if mavftp_instance is None:
            return False
        try:
            result = mavftp_instance.cmd_mkdir([normalized_directory.rstrip("/")])
            return result.error_code in {FtpError.Success, FtpError.FileExists}
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to create remote directory: %(error)s"), {"error": str(error)})
            return False

    def delete_remote_path(self, remote_path: str, is_directory: bool = False) -> bool:
        """Delete a remote file or an empty remote directory."""
        if self.master is None or not self.info.is_mavftp_supported:
            return False
        try:
            normalized_path = self._normalize_remote_path(remote_path)
            if normalized_path == "/":
                raise ValueError(_("The remote root cannot be deleted"))
        except ValueError as error:
            logging_error(_("Invalid remote path: %(error)s"), {"error": str(error)})
            return False

        mavftp_instance = create_mavftp_safe(self.master)
        if mavftp_instance is None:
            return False
        try:
            result = (
                mavftp_instance.cmd_rmdir([normalized_path]) if is_directory else mavftp_instance.cmd_rm([normalized_path])
            )
            return result.error_code == FtpError.Success
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to delete remote path: %(error)s"), {"error": str(error)})
            return False

    def rename_remote_path(self, remote_path: str, new_remote_path: str) -> bool:
        """Rename a remote file or directory."""
        if self.master is None or not self.info.is_mavftp_supported:
            return False
        try:
            normalized_old_path = self._normalize_remote_path(remote_path)
            normalized_new_path = self._normalize_remote_path(new_remote_path)
            if normalized_old_path == "/" or normalized_new_path == "/":
                raise ValueError(_("The remote root cannot be renamed"))
        except ValueError as error:
            logging_error(_("Invalid remote path: %(error)s"), {"error": str(error)})
            return False

        mavftp_instance = create_mavftp_safe(self.master)
        if mavftp_instance is None:
            return False
        try:
            result = mavftp_instance.cmd_rename([normalized_old_path, normalized_new_path])
            return result.error_code == FtpError.Success
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to rename remote path: %(error)s"), {"error": str(error)})
            return False

    def download_bin_log_file(
        self,
        remote_path: str,
        local_filename: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> bool:
        """Download one explicitly selected remote file."""
        if self.master is None:
            logging_error(_("No flight controller connected"))
            return False
        if not self.info.is_mavftp_supported:
            logging_error(_("MAVFTP is not supported by the flight controller"))
            return False

        try:
            normalized_remote_path = self._normalize_remote_path(remote_path)
        except ValueError as error:
            logging_error(_("Invalid remote file: %(error)s"), {"error": str(error)})
            return False

        mavftp_instance = create_mavftp_safe(self.master)
        if mavftp_instance is None:
            logging_error(_("MAVFTP is not available for file download"))
            return False

        def get_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        return self._download_remote_file(
            mavftp_instance,
            normalized_remote_path,
            local_filename,
            get_progress_callback,
        )

    def download_remote_file(
        self,
        remote_path: str,
        local_filename: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> bool:
        """Download one explicitly selected remote regular file."""
        return self.download_bin_log_file(remote_path, local_filename, progress_callback)

    def _get_last_log_number(self, mavftp_instance: "MAVFTP") -> int | None:  # pyright: ignore[reportInvalidTypeForm]
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
    ) -> int | None:
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
            if ret.error_code != FtpError.Success:
                logging_warning(_("LASTLOG.TXT not available, trying alternative methods"))
                return None

            return self._extract_log_number_from_file(temp_lastlog_file)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to get log number from LASTLOG.TXT: %(error)s"), {"error": str(e)})
            return None

    def _get_log_number_from_directory_listing(
        self,
        mavftp_instance: "MAVFTP",  # pyright: ignore[reportInvalidTypeForm]
    ) -> int | None:
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
            listing = getattr(result, "directory_listing", None)
            if not isinstance(listing, list):
                logging_error(_("No directory listing found in MAVFTPReturn"))
                return None
            highest = -1
            for entry in listing:
                name = entry.name
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
    ) -> int | None:
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

                if ret.error_code == FtpError.Success:
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
        return self._download_remote_file(
            mavftp_instance,
            remote_filename,
            local_filename,
            get_progress_callback,
        )

    def _download_remote_file(
        self,
        mavftp_instance: "MAVFTP",  # pyright: ignore[reportInvalidTypeForm]
        remote_filename: str,
        local_filename: str,
        get_progress_callback: Callable,
    ) -> bool:
        """Download an explicitly named remote file through MAVFTP."""
        logging_info(_("Downloading flight log %(remote)s to %(local)s"), {"remote": remote_filename, "local": local_filename})

        try:
            # Download the actual log file
            mavftp_instance.cmd_get([remote_filename, local_filename], progress_callback=get_progress_callback)
            ret = mavftp_instance.process_ftp_reply("OpenFileRO", timeout=0)  # No timeout for large log files
            if ret.error_code != FtpError.Success:
                logging_error(_("Failed to download flight log %(remote)s"), {"remote": remote_filename})
                ret.display_message()
                return False

            logging_info(_("Successfully downloaded flight log to %(local)s"), {"local": local_filename})
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            try:
                mavftp_instance.cmd_cancel()
            except Exception:  # pylint: disable=broad-exception-caught
                logging_debug("Could not cancel failed MAVFTP download", exc_info=True)
            logging_error(_("Failed to download log file: %(error)s"), {"error": str(e)})
            return False

    def _extract_log_number_from_file(self, temp_lastlog_file: str) -> int | None:
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
