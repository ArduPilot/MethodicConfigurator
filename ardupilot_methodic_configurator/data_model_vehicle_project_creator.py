"""
Data model for vehicle project creation.

This file contains the business logic for creating new vehicle configurations
from templates, separated from the GUI layer.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem


class VehicleProjectCreationError(Exception):
    """Exception raised when vehicle project creation fails."""

    def __init__(self, title: str, message: str) -> None:
        """
        Initialize the exception.

        Args:
            title: Short title for the error (e.g., "Vehicle template directory", "New vehicle directory")
            message: Detailed human-readable error message

        """
        super().__init__(message)
        self.title = title
        self.message = message


@dataclass
class NewVehicleProjectSettings:
    """Settings for creating a new vehicle project from a template."""

    # Configuration options
    blank_component_data: bool = False
    infer_comp_specs_and_conn_from_fc_params: bool = False
    use_fc_params: bool = False
    blank_change_reason: bool = False
    copy_vehicle_image: bool = False
    reset_fc_parameters_to_their_defaults: bool = False

    def validate_fc_dependent_settings(self, fc_connected: bool) -> None:
        """
        Validate settings that depend on flight controller connectivity.

        Args:
            fc_connected: Whether a flight controller is connected

        Raises:
            VehicleProjectCreationError: If FC-dependent settings are enabled without connection

        """
        if not fc_connected:
            if self.infer_comp_specs_and_conn_from_fc_params:
                raise VehicleProjectCreationError(
                    _("Flight Controller Connection"),
                    _("Cannot infer component specifications from FC parameters: no flight controller connected"),
                )
            if self.use_fc_params:
                raise VehicleProjectCreationError(
                    _("Flight Controller Connection"), _("Cannot use FC parameters: no flight controller connected")
                )
            if self.reset_fc_parameters_to_their_defaults:
                raise VehicleProjectCreationError(
                    _("Flight Controller Connection"),
                    _("Cannot reset FC parameters to defaults: no flight controller connected"),
                )


class VehicleProjectCreator:
    """Manages vehicle project creation operations."""

    def __init__(self, local_filesystem: LocalFilesystem) -> None:
        """
        Initialize the project creator.

        Args:
            local_filesystem: The filesystem interface for file operations

        """
        self.local_filesystem = local_filesystem
        self.configuration_template: str = ""

    def create_new_vehicle_from_template(
        self,
        template_dir: str,
        new_base_dir: str,
        new_vehicle_name: str,
        settings: NewVehicleProjectSettings,
        fc_connected: bool = False,
    ) -> str:
        """
        Create a new vehicle configuration directory from a template.

        Args:
            template_dir: Path to the template directory
            new_base_dir: Base directory where the new vehicle directory will be created
            new_vehicle_name: Name for the new vehicle directory
            settings: Configuration settings for the new project
            fc_connected: Whether a flight controller is connected

        Returns:
            The path to the newly created vehicle directory

        Raises:
            VehicleProjectCreationError: If creation fails for any reason

        """
        # Validate FC-dependent settings
        settings.validate_fc_dependent_settings(fc_connected)

        # Validate inputs
        self._validate_template_directory(template_dir)
        self._validate_new_vehicle_inputs(new_vehicle_name)

        # Create the new vehicle directory path
        new_vehicle_dir = LocalFilesystem.new_vehicle_dir(new_base_dir, new_vehicle_name)

        # Create the new vehicle directory
        error_msg = self.local_filesystem.create_new_vehicle_dir(new_vehicle_dir)
        if error_msg:
            raise VehicleProjectCreationError(_("New vehicle directory"), error_msg)

        # Copy template files to the new directory
        error_msg = self.local_filesystem.copy_template_files_to_new_vehicle_dir(
            template_dir,
            new_vehicle_dir,
            blank_change_reason=settings.blank_change_reason,
            copy_vehicle_image=settings.copy_vehicle_image,
        )
        if error_msg:
            raise VehicleProjectCreationError(_("Copying template files"), error_msg)

        # Update the local_filesystem with the new vehicle configuration directory
        self.local_filesystem.vehicle_dir = new_vehicle_dir

        # Initialize the filesystem with the new directory
        try:
            self.local_filesystem.re_init(new_vehicle_dir, self.local_filesystem.vehicle_type, settings.blank_component_data)
        except SystemExit as exp:
            raise VehicleProjectCreationError(
                _("Fatal error reading parameter files"), _("Fatal error reading parameter files: {exp}").format(exp=exp)
            ) from exp

        # Check if files were successfully created and loaded
        files = list(self.local_filesystem.file_parameters.keys())
        if not files:
            raise VehicleProjectCreationError(
                _("No parameter files found"), _("No intermediate parameter files found after creating vehicle from template")
            )

        # Store the successfully used directories for future use
        LocalFilesystem.store_recently_used_template_dirs(template_dir, new_base_dir)
        LocalFilesystem.store_recently_used_vehicle_dir(new_vehicle_dir)

        # Store the template name for reference
        self.configuration_template = LocalFilesystem.get_directory_name_from_full_path(template_dir)

        return new_vehicle_dir

    def _validate_template_directory(self, template_dir: str) -> None:
        """
        Validate the template directory.

        Args:
            template_dir: Path to the template directory

        Raises:
            VehicleProjectCreationError: If validation fails

        """
        if not template_dir:
            raise VehicleProjectCreationError(
                _("Vehicle template directory"), _("Vehicle template directory must not be empty")
            )

        if not LocalFilesystem.directory_exists(template_dir):
            raise VehicleProjectCreationError(
                _("Vehicle template directory"),
                _("Vehicle template directory {template_dir} does not exist").format(template_dir=template_dir),
            )

    def _validate_new_vehicle_inputs(self, new_vehicle_name: str) -> None:
        """
        Validate inputs for creating a new vehicle.

        Args:
            new_vehicle_name: Name for the new vehicle directory

        Raises:
            VehicleProjectCreationError: If validation fails

        """
        if not new_vehicle_name:
            raise VehicleProjectCreationError(_("New vehicle directory"), _("New vehicle name must not be empty"))

        if not LocalFilesystem.valid_directory_name(new_vehicle_name):
            raise VehicleProjectCreationError(
                _("New vehicle directory"),
                _("New vehicle name {new_vehicle_name} must not contain invalid characters").format(
                    new_vehicle_name=new_vehicle_name
                ),
            )

    def get_configuration_template(self) -> str:
        """
        Get the name of the template used for the last created vehicle.

        Returns:
            The template name, or empty string if no template was used

        """
        return self.configuration_template
