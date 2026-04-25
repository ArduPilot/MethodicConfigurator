"""
Data model factory/container for vehicle project operations.

This file contains the unified interface for all vehicle project operations,
acting as a facade that coordinates between different data models and provides
a single point of contact for the frontend layer.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import TYPE_CHECKING, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_par_dict import is_within_tolerance
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import NewVehicleProjectSettings, VehicleProjectCreator
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpener

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class VehicleProjectManager:  # pylint: disable=too-many-public-methods
    """
    Factory/Container for vehicle project operations.

    This class provides a unified interface for all vehicle project operations,
    coordinating between different data models and abstracting backend details
    from the frontend layer.
    """

    def __init__(self, local_filesystem: LocalFilesystem, flight_controller: Optional["FlightController"] = None) -> None:
        """
        Initialize the project manager.

        Args:
            local_filesystem: The filesystem interface for file operations
            flight_controller: Optional flight controller interface

        """
        self._local_filesystem = local_filesystem
        self._flight_controller = flight_controller
        self._creator = VehicleProjectCreator(local_filesystem)
        self._opener = VehicleProjectOpener(local_filesystem)
        self._settings: Optional[NewVehicleProjectSettings] = None  # It will be set if a new project is created successfully
        self.configuration_template: str = ""  # It will be set if a new project is created successfully

    # Directory and path operations
    def get_recently_used_dirs(self) -> tuple[str, str, str]:
        """
        Get the recently used template, base, and vehicle directories.

        Returns:
            Tuple of (template_dir, new_base_dir, vehicle_dir)

        """
        return LocalFilesystem.get_recently_used_dirs()

    def get_recent_vehicle_dirs(self) -> list[str]:
        """
        Get the list of recently opened vehicle directories.

        Returns:
            List of recent vehicle directory paths, ordered from most recent to oldest.
            Returns empty list if no history exists.

        """
        return LocalFilesystem.get_recent_vehicle_dirs()

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
        fc_connected = self.is_flight_controller_connected()
        new_path = self._creator.create_new_vehicle_from_template(
            template_dir, new_base_dir, new_vehicle_name, settings, fc_connected, self.fc_parameters()
        )
        if new_path:
            self._settings = settings
            self.configuration_template = self.get_directory_name_from_path(template_dir)
            # History updates belong in the manager/facade layer so they are
            # performed consistently for both project creation and opening.
            self.store_recently_used_template_dirs(template_dir, new_base_dir)
            self.open_vehicle_directory(new_path)
        return new_path

    def create_new_vehicle_from_bin_log(self, bin_file: str) -> str:
        """
        Create a new vehicle configuration directory from an ArduPilot .bin log file.

        The vehicle type and firmware version are extracted from the .bin file itself.
        The project is based on the matching empty_{major}.{minor}.x template, uses the
        extracted current parameter values for template substitution, replaces the
        template's 00_default.param with the extracted defaults snapshot, and exports any
        remaining parameters missing from the AMC files into a final import file.

        Args:
            bin_file: Path to the ArduPilot .bin log file

        Returns:
            The created vehicle directory path

        Raises:
            VehicleProjectCreationError: If creation, extraction, or template lookup fails

        """
        firmware_info = self._creator.extract_firmware_version_from_bin_log(bin_file)
        vehicle_type = firmware_info[0]
        fw_version = f"{firmware_info[1]}.{firmware_info[2]}.{firmware_info[3]}"
        template_dir = self._creator.template_dir_for_bin_import(vehicle_type, firmware_info[1], firmware_info[2])
        default_params, current_params = self._creator.extract_param_files_from_bin_log(bin_file)
        fc_parameters = {name: param.value for name, param in current_params.items()}
        settings = NewVehicleProjectSettings(
            blank_change_reason=True,
            infer_comp_specs_and_conn_from_fc_params=True,
            use_fc_params=True,
        )

        new_path = self._creator.create_new_vehicle_from_template(
            template_dir,
            str(LocalFilesystem.get_vehicles_default_dir()),
            self._creator.vehicle_name_from_bin_log(bin_file),
            settings,
            fc_connected=False,
            fc_parameters=fc_parameters,
        )

        # Point the filesystem at the new vehicle directory before any reads or writes.
        # write_param_default_values_to_file() and compound_params() rely on vehicle_dir,
        # so re_init() must be called here to avoid accidentally operating on the previously-open project.
        # Set fw_version first so re_init() does not override it with the template's placeholder version.
        self._local_filesystem.fw_version = fw_version
        self._local_filesystem.re_init(new_path, vehicle_type)
        # Persist the correct firmware version and type into vehicle_components.json so subsequent
        # re_init calls (and the user when they inspect the project) see the actual recorded firmware.
        self._local_filesystem.set_fc_fw_version_and_type_in_components_json(fw_version, vehicle_type, new_path)

        self._local_filesystem.write_param_default_values_to_file(default_params)

        # Build the baseline from log-extracted defaults plus compounded AMC step files.
        # This avoids exporting params that merely match 00_default.param but are absent
        # from the numbered step files.
        compounded_step_params, _first_config_step = self._local_filesystem.compound_params(skip_default=True)
        baseline_params = default_params.deep_copy()
        baseline_params.update(compounded_step_params)

        if imported_params := current_params.get_missing_or_different(baseline_params, is_within_tolerance):
            self._local_filesystem.export_to_param(
                imported_params,
                self._creator.next_import_filename(new_path),
                annotate_doc=False,
            )
            self._local_filesystem.re_init(new_path, vehicle_type)

        if self._flight_controller is not None:
            self._flight_controller.fc_parameters = fc_parameters

        # Open the vehicle directory only after all file modifications are complete and filesystem state is synced.
        # This ensures the UI/session operates on the authoritative filesystem state, not stale in-memory cache.
        # Also note: infer_comp_specs_and_conn_from_fc_params and use_fc_params are reused for log-derived params
        # because the semantics align: we're supplying external parameter values for template substitution.
        self.open_vehicle_directory(new_path)

        # Update manager state only after the whole import succeeds so that a failure in any preceding step
        # (including open_vehicle_directory) does not leave the manager in a partially-updated state and
        # does not pollute the recently-used template history with an incomplete project.
        self._settings = settings
        self.configuration_template = self.get_directory_name_from_path(template_dir)
        self.store_recently_used_template_dirs(template_dir, str(LocalFilesystem.get_vehicles_default_dir()))

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
        result = self._opener.open_vehicle_directory(vehicle_dir)
        # update history whenever a directory is opened successfully
        self.store_recently_used_vehicle_dir(result)
        return result

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
        result = self._opener.open_last_vehicle_directory(last_vehicle_dir)
        # update history whenever a directory is opened successfully
        self.store_recently_used_vehicle_dir(result)
        return result

    # Filesystem state management
    def get_vehicle_directory(self) -> str:
        """
        Get the current vehicle directory from the filesystem.

        Returns:
            Current vehicle directory path

        """
        return self._local_filesystem.vehicle_dir

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

    @property
    def reset_fc_parameters_to_their_defaults(self) -> bool:
        """Reset FC parameters to their defaults when a project is created."""
        return self._settings is not None and self._settings.reset_fc_parameters_to_their_defaults

    @property
    def blank_component_data(self) -> bool:
        """Whether to create blank component data when a project is created."""
        return self._settings is not None and self._settings.blank_component_data

    @property
    def infer_comp_specs_and_conn_from_fc_params(self) -> bool:
        """Whether to infer component specifications and connections from flight controller parameters."""
        return self._settings is not None and self._settings.infer_comp_specs_and_conn_from_fc_params

    @property
    def use_fc_params(self) -> bool:
        """Whether to use flight controller parameters values instead of template values when creating a project."""
        return self._settings is not None and self._settings.use_fc_params

    # Flight controller operations
    def is_flight_controller_connected(self) -> bool:
        """
        Check if a flight controller is currently connected.

        Returns:
            True if flight controller is connected, False otherwise

        """
        return (
            self._flight_controller is not None
            and hasattr(self._flight_controller, "master")
            and self._flight_controller.master is not None
        )

    def fc_parameters(self) -> Optional[dict[str, float]]:
        """
        Return the flight controller's parameter dictionary if available.

        Returns:
            Dictionary of FC parameters if a flight controller is connected or --device=file was used,
            or None if no flight controller is connected or params.param was empty or invalid.

        """
        if self._flight_controller is None:
            return None
        return self._flight_controller.fc_parameters

    def can_open_last_vehicle_directory(self, last_vehicle_dir: str) -> bool:
        """
        Check if the last used vehicle directory can be opened.

        Args:
            last_vehicle_dir: Path to the last vehicle directory

        Returns:
            True if the directory exists and can be opened, False otherwise

        """
        return bool(last_vehicle_dir and self.directory_exists(last_vehicle_dir))

    def get_introduction_message(self) -> str:
        """
        Get the appropriate introduction message based on current project state.

        Returns:
            introduction message

        """
        if self.get_vehicle_directory() == self.get_current_working_directory():
            return _("No intermediate parameter files found\nin current working directory.")
        return _("No intermediate parameter files found\nin the --vehicle-dir specified directory.")

    def get_file_parameters_list(self) -> list[str]:
        """
        Get the list of intermediate parameter files.

        Returns:
            List of intermediate parameter file names

        """
        return list(self._local_filesystem.file_parameters.keys())

    def get_default_vehicle_name(self) -> str:
        """
        Get the default name for a new vehicle directory.

        Returns:
            Default vehicle name

        """
        return _("MyVehicleName")

    def get_vehicle_type(self) -> str:
        """
        Get the vehicle type.

        Returns:
            Vehicle type

        """
        return self._local_filesystem.vehicle_type
