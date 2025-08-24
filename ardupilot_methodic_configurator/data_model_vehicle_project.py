"""
Data model factory/container for vehicle project operations.

This file contains the unified interface for all vehicle project operations,
acting as a facade that coordinates between different data models and provides
a single point of contact for the frontend layer.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Optional

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreator,
)
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpener


class VehicleProjectManager:
    """
    Factory/Container for vehicle project operations.

    This class provides a unified interface for all vehicle project operations,
    coordinating between different data models and abstracting backend details
    from the frontend layer.
    """

    def __init__(self, local_filesystem: LocalFilesystem, flight_controller: Optional[object] = None) -> None:
        """
        Initialize the project manager.

        Args:
            local_filesystem: The filesystem interface for file operations
            flight_controller: Optional flight controller interface

        """
        self.local_filesystem = local_filesystem
        self.flight_controller = flight_controller
        self.creator = VehicleProjectCreator(local_filesystem)
        self.opener = VehicleProjectOpener(local_filesystem)
        self.settings: Optional[NewVehicleProjectSettings] = None  # It will be set if a new project is created successfully
        self.configuration_template: str = ""  # It will be set if a new project is created successfully

    # Directory and path operations
    def get_recently_used_dirs(self) -> tuple[str, str, str]:
        """
        Get the recently used template, base, and vehicle directories.

        Returns:
            Tuple of (template_dir, new_base_dir, vehicle_dir)

        """
        return LocalFilesystem.get_recently_used_dirs()

    def get_current_working_directory(self) -> str:
        """
        Get the current working directory.

        Returns:
            Current working directory path

        """
        return LocalFilesystem.getcwd()

    def get_directory_name_from_path(self, path: str) -> str:
        """
        Extract directory name from full path.

        Args:
            path: Full path to extract directory name from

        Returns:
            Directory name

        """
        return LocalFilesystem.get_directory_name_from_full_path(path)

    def directory_exists(self, directory_path: str) -> bool:
        """
        Check if a directory exists.

        Args:
            directory_path: Path to check

        Returns:
            True if directory exists, False otherwise

        """
        return LocalFilesystem.directory_exists(directory_path)

    def valid_directory_name(self, name: str) -> bool:
        """
        Check if a directory name is valid.

        Args:
            name: Directory name to validate

        Returns:
            True if valid, False otherwise

        """
        return LocalFilesystem.valid_directory_name(name)

    def new_vehicle_dir_path(self, base_dir: str, vehicle_name: str) -> str:
        """
        Generate the full path for a new vehicle directory.

        Args:
            base_dir: Base directory where vehicle directory will be created
            vehicle_name: Name of the vehicle directory

        Returns:
            Full path to the new vehicle directory

        """
        return LocalFilesystem.new_vehicle_dir(base_dir, vehicle_name)

    # Vehicle project creation operations
    def create_new_vehicle_from_template(
        self,
        template_dir: str,
        new_base_dir: str,
        new_vehicle_name: str,
        settings: NewVehicleProjectSettings,
    ) -> str:
        """
        Create a new vehicle configuration directory from a template.

        Args:
            template_dir: Path to the template directory
            new_base_dir: Base directory where the new vehicle directory will be created
            new_vehicle_name: Name for the new vehicle directory
            settings: Configuration settings for the new project

        Returns:
            The path to the newly created vehicle directory

        Raises:
            VehicleProjectCreationError: If creation fails for any reason

        """
        fc_connected = (
            self.flight_controller is not None
            and hasattr(self.flight_controller, "master")
            and self.flight_controller.master is not None
        )
        new_path = self.creator.create_new_vehicle_from_template(
            template_dir, new_base_dir, new_vehicle_name, settings, fc_connected
        )
        if new_path:
            self.settings = settings
            self.configuration_template = self.get_directory_name_from_path(template_dir)
        return new_path

    # Vehicle project opening operations
    def open_vehicle_directory(self, vehicle_dir: str) -> str:
        """
        Open an existing vehicle configuration directory.

        Args:
            vehicle_dir: Path to the vehicle directory to open

        Returns:
            The opened vehicle directory path

        Raises:
            VehicleProjectOpenError: If opening fails for any reason

        """
        return self.opener.open_vehicle_directory(vehicle_dir)

    def open_last_vehicle_directory(self, last_vehicle_dir: str) -> str:
        """
        Open the last used vehicle configuration directory.

        Args:
            last_vehicle_dir: Path to the last vehicle directory

        Returns:
            The opened vehicle directory path

        Raises:
            VehicleProjectOpenError: If opening fails for any reason

        """
        return self.opener.open_last_vehicle_directory(last_vehicle_dir)

    def get_flight_controller_vehicle_type(self) -> str:
        """
        Get the vehicle type from the connected flight controller.

        Returns:
            Vehicle type string, or empty string if not connected

        """
        if self.flight_controller is not None:
            # Assuming flight controller has a method to get vehicle type
            # This would need to be implemented based on the actual FlightController interface
            return getattr(self.flight_controller, "vehicle_type", "")
        return ""

    # Filesystem state management
    def get_vehicle_directory(self) -> str:
        """
        Get the current vehicle directory from the filesystem.

        Returns:
            Current vehicle directory path

        """
        return self.local_filesystem.vehicle_dir

    def store_recently_used_template_dirs(self, template_dir: str, base_dir: str) -> None:
        """
        Store recently used template and base directories.

        Args:
            template_dir: Template directory to store
            base_dir: Base directory to store

        """
        LocalFilesystem.store_recently_used_template_dirs(template_dir, base_dir)

    def store_recently_used_vehicle_dir(self, vehicle_dir: str) -> None:
        """
        Store recently used vehicle directory.

        Args:
            vehicle_dir: Vehicle directory to store

        """
        LocalFilesystem.store_recently_used_vehicle_dir(vehicle_dir)
