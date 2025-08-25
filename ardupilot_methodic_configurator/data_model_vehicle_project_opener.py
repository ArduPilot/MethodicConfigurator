"""
Data model for vehicle project opening.

This file contains the business logic for opening existing vehicle configurations,
separated from the GUI layer.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem


class VehicleProjectOpenError(Exception):
    """Exception raised when opening a vehicle project fails."""

    def __init__(self, title: str, message: str) -> None:
        """
        Initialize the exception.

        Args:
            title: Short title for the error (e.g., "No Last Vehicle Directory Found", "Invalid Vehicle Directory")
            message: Detailed human-readable error message

        """
        super().__init__(message)
        self.title = title
        self.message = message


class VehicleProjectOpener:
    """Manages vehicle project opening operations."""

    def __init__(self, local_filesystem: LocalFilesystem) -> None:
        """
        Initialize the project opener.

        Args:
            local_filesystem: The filesystem interface for file operations

        """
        self.local_filesystem = local_filesystem

    def open_last_vehicle_directory(self, last_vehicle_dir: str) -> str:
        """
        Open the last used vehicle configuration directory.

        Args:
            last_vehicle_dir: Path to the last used vehicle directory

        Returns:
            The path to the opened vehicle directory

        Raises:
            VehicleProjectOpenError: If opening fails for any reason

        """
        if not last_vehicle_dir:
            raise VehicleProjectOpenError(
                _("No Last Vehicle Directory Found"),
                _("No last opened vehicle configuration directory was found.\nPlease select a directory manually."),
            )

        # Update the filesystem with the vehicle directory
        self.local_filesystem.vehicle_dir = last_vehicle_dir

        # Initialize the filesystem with the directory
        try:
            self.local_filesystem.re_init(last_vehicle_dir, self.local_filesystem.vehicle_type)
        except SystemExit as exp:
            raise VehicleProjectOpenError(
                _("Fatal error reading parameter files"), _("Fatal error reading parameter files: {exp}").format(exp=exp)
            ) from exp

        # Check if files were successfully loaded
        if not self.local_filesystem.file_parameters:
            raise VehicleProjectOpenError(
                _("No parameter files found"),
                _("No intermediate parameter files found in the selected directory: {last_vehicle_dir}").format(
                    last_vehicle_dir=last_vehicle_dir
                ),
            )

        files = list(self.local_filesystem.file_parameters.keys())
        if not files:
            raise VehicleProjectOpenError(
                _("No parameter files found"),
                _("No intermediate parameter files found in the selected directory: {last_vehicle_dir}").format(
                    last_vehicle_dir=last_vehicle_dir
                ),
            )

        return last_vehicle_dir

    def open_vehicle_directory(self, vehicle_dir: str) -> str:
        """
        Open an existing vehicle configuration directory.

        Args:
            vehicle_dir: Path to the vehicle directory to open

        Returns:
            The path to the opened vehicle directory

        Raises:
            VehicleProjectOpenError: If opening fails for any reason

        """
        # Validate directory contains required files
        if not self.local_filesystem.vehicle_configuration_files_exist(vehicle_dir):
            filename = self.local_filesystem.vehicle_components_fs.json_filename
            error_msg = _("Selected directory must contain files matching \\d\\d_*\\.param and a {filename} file").format(
                filename=filename
            )
            raise VehicleProjectOpenError(_("Invalid Vehicle Directory Selected"), error_msg)

        # Check if it's a template directory (should not be edited)
        if "vehicle_templates" in vehicle_dir and not self.local_filesystem.allow_editing_template_files:
            raise VehicleProjectOpenError(
                _("Invalid Vehicle Directory Selected"),
                _(
                    "Please do not edit the files provided 'vehicle_templates' directory\n"
                    "as those are used as a template for new vehicles"
                ),
            )

        # Update the filesystem with the vehicle directory
        self.local_filesystem.vehicle_dir = vehicle_dir

        # Initialize the filesystem with the directory
        try:
            self.local_filesystem.re_init(vehicle_dir, self.local_filesystem.vehicle_type)
        except SystemExit as exp:
            raise VehicleProjectOpenError(
                _("Fatal error reading parameter files"), _("Fatal error reading parameter files: {exp}").format(exp=exp)
            ) from exp

        # Check if files were successfully loaded
        if not self.local_filesystem.file_parameters:
            raise VehicleProjectOpenError(
                _("No parameter files found"),
                _("No intermediate parameter files found in the selected directory: {vehicle_dir}").format(
                    vehicle_dir=vehicle_dir
                ),
            )

        files = list(self.local_filesystem.file_parameters.keys())
        if not files:
            raise VehicleProjectOpenError(
                _("No parameter files found"),
                _("No intermediate parameter files found in the selected directory: {vehicle_dir}").format(
                    vehicle_dir=vehicle_dir
                ),
            )

        LocalFilesystem.store_recently_used_vehicle_dir(vehicle_dir)
        return vehicle_dir

    def _validate_existing_directory(self, vehicle_dir: str) -> None:
        """
        Validate an existing vehicle directory.

        Args:
            vehicle_dir: Path to the vehicle directory to validate

        Raises:
            VehicleProjectOpenError: If validation fails

        """
        if not vehicle_dir:
            raise VehicleProjectOpenError(_("Vehicle directory"), _("Vehicle directory must not be empty"))

        if not LocalFilesystem.directory_exists(vehicle_dir):
            raise VehicleProjectOpenError(
                _("Vehicle directory"), _("Vehicle directory {vehicle_dir} does not exist").format(vehicle_dir=vehicle_dir)
            )

        if not self.local_filesystem.vehicle_configuration_files_exist(vehicle_dir):
            filename = self.local_filesystem.vehicle_components_fs.json_filename
            error_msg = _("Selected directory must contain files matching \\d\\d_*\\.param and a {filename} file").format(
                filename=filename
            )
            raise VehicleProjectOpenError(_("Invalid Vehicle Directory"), error_msg)
