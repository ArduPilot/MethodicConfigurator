"""
Data model for vehicle project creation.

This file contains the business logic for creating new vehicle configurations
from templates, separated from the GUI layer.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import MISSING, dataclass, fields
from typing import ClassVar, NamedTuple

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


class NewVehicleProjectSetting(NamedTuple):
    """New vehicle project option setting and metadata."""

    label: str
    tooltip: str
    enabled: bool = True


@dataclass
class NewVehicleProjectSettings:
    """Settings for creating a new vehicle project from a template."""

    # Configuration options
    copy_vehicle_image: bool = False
    blank_component_data: bool = False
    reset_fc_parameters_to_their_defaults: bool = False
    infer_comp_specs_and_conn_from_fc_params: bool = False
    use_fc_params: bool = False
    blank_change_reason: bool = False

    @classmethod
    def _get_dataclass_defaults(cls) -> dict[str, bool]:
        """Get default values from dataclass field definitions."""
        defaults = {}
        for field in fields(cls):
            if field.default is not MISSING:
                defaults[field.name] = field.default
        return defaults

    # Base metadata for each setting (enabled state will be updated dynamically)
    # Note: defaults are derived from dataclass field defaults to avoid duplication
    _BASE_SETTINGS_METADATA: ClassVar[dict[str, NewVehicleProjectSetting]] = {
        "copy_vehicle_image": NewVehicleProjectSetting(
            label=_("Copy vehicle image from template"),
            tooltip=_(
                "Copy the vehicle.jpg image file from the template directory to the new vehicle directory\n"
                "if it exists. This image helps identify the vehicle configuration."
            ),
            enabled=True,
        ),
        "blank_component_data": NewVehicleProjectSetting(
            label=_("Blank component data"),
            tooltip=_("Create a new blank vehicle configuration, with no component data from the template."),
            enabled=True,
        ),
        "reset_fc_parameters_to_their_defaults": NewVehicleProjectSetting(
            label=_(
                "Reset flight controller parameters to their defaults. "
                "WARNING: This will delete all parameters stored on the flight controller."
            ),
            tooltip=_(
                "Reset the flight controller parameters to their default values when creating a new vehicle configuration.\n"
                "Helps avoid issues caused by incorrect or incompatible parameter settings."
            ),
            enabled=True,  # Will be updated based on FC connection
        ),
        "infer_comp_specs_and_conn_from_fc_params": NewVehicleProjectSetting(
            label=_("Infer component specifications and FC connections from FC parameters, not from template files"),
            tooltip=_(
                "When creating a new vehicle configuration, extract component specifications\n"
                "and connection information directly from the connected flight controller\n"
                "instead of using the specifications defined in the template files.\n"
                "This helps ensure the configuration accurately matches your actual hardware.\n"
                "But you will not see the information from the correctly configured vehicle template.\n\n"
            )
            + _("This option is only available when a flight controller is connected."),
            enabled=True,  # Will be updated based on FC connection
        ),
        "use_fc_params": NewVehicleProjectSetting(
            label=_("Use parameter values from connected FC, not from template files"),
            tooltip=_(
                "Use the parameter values from the connected flight controller instead of the\n"
                "template files when creating a new vehicle configuration directory from a template.\n"
                "Only makes sense if your FC has already been correctly configured.\n\n"
            )
            + _("This option is only available when a flight controller is connected."),
            enabled=True,  # Will be updated based on FC connection
        ),
        "blank_change_reason": NewVehicleProjectSetting(
            label=_("Blank parameter change reason"),
            tooltip=_("Do not use the parameters change reason from the template."),
            enabled=True,
        ),
    }

    # Settings that require flight controller connection
    _FC_DEPENDENT_SETTINGS: ClassVar[set[str]] = {
        "reset_fc_parameters_to_their_defaults",
        "infer_comp_specs_and_conn_from_fc_params",
        "use_fc_params",
    }

    # Error messages for FC-dependent settings
    _FC_DEPENDENT_ERROR_MESSAGES: ClassVar[dict[str, str]] = {
        "reset_fc_parameters_to_their_defaults": _("Cannot reset FC parameters to defaults: no flight controller connected"),
        "infer_comp_specs_and_conn_from_fc_params": _(
            "Cannot infer component specifications from FC parameters: no flight controller connected"
        ),
        "use_fc_params": _("Cannot use FC parameters: no flight controller connected"),
    }

    @classmethod
    def get_setting_metadata(cls, setting_name: str, fc_connected: bool = True) -> NewVehicleProjectSetting:
        """
        Get metadata for a specific setting with enabled state based on FC connection.

        Args:
            setting_name: Name of the setting
            fc_connected: Whether flight controller is connected

        Returns:
            SettingMetadata for the setting with appropriate enabled state

        Raises:
            KeyError: If setting name is not found

        """
        base_metadata = cls._BASE_SETTINGS_METADATA[setting_name]

        # Update enabled state based on FC connection for FC-dependent settings
        enabled = fc_connected if setting_name in cls._FC_DEPENDENT_SETTINGS else base_metadata.enabled

        return NewVehicleProjectSetting(label=base_metadata.label, tooltip=base_metadata.tooltip, enabled=enabled)

    @classmethod
    def get_all_settings_metadata(cls, fc_connected: bool = True) -> dict[str, NewVehicleProjectSetting]:
        """
        Get metadata for all settings with enabled states based on FC connection.

        Args:
            fc_connected: Whether flight controller is connected

        Returns:
            Dictionary of all settings metadata with appropriate enabled states

        """
        return {name: cls.get_setting_metadata(name, fc_connected) for name in cls._BASE_SETTINGS_METADATA}

    @classmethod
    def is_setting_enabled(cls, setting_name: str, fc_connected: bool) -> bool:
        """
        Check if a setting should be enabled based on FC connection state.

        Args:
            setting_name: Name of the setting
            fc_connected: Whether flight controller is connected

        Returns:
            True if setting should be enabled, False otherwise

        """
        metadata = cls.get_setting_metadata(setting_name, fc_connected)
        return metadata.enabled

    @classmethod
    def get_settings_state(cls, fc_connected: bool) -> dict[str, bool]:
        """
        Get the enabled state for all settings based on FC connection.

        Args:
            fc_connected: Whether flight controller is connected

        Returns:
            Dictionary mapping setting names to their enabled state

        """
        return {name: cls.is_setting_enabled(name, fc_connected) for name in cls._BASE_SETTINGS_METADATA}

    @classmethod
    def get_default_values(cls) -> dict[str, bool]:
        """
        Get the default values for all settings.

        Returns:
            Dictionary mapping setting names to their default values

        """
        return cls._get_dataclass_defaults()

    @classmethod
    def get_fc_dependent_error_message(cls, setting_name: str) -> str:
        """
        Get the error message for an FC-dependent setting.

        Args:
            setting_name: Name of the setting

        Returns:
            Error message for the setting

        Raises:
            KeyError: If setting is not FC-dependent

        """
        return cls._FC_DEPENDENT_ERROR_MESSAGES[setting_name]

    @classmethod
    def validate_fc_dependent_setting(cls, setting_name: str, setting_value: bool, fc_connected: bool) -> None:
        """
        Validate a single FC-dependent setting.

        Args:
            setting_name: Name of the setting
            setting_value: Current value of the setting
            fc_connected: Whether flight controller is connected

        Raises:
            VehicleProjectCreationError: If FC-dependent setting is enabled without connection

        """
        if setting_name in cls._FC_DEPENDENT_SETTINGS and setting_value and not fc_connected:
            error_message = cls.get_fc_dependent_error_message(setting_name)
            raise VehicleProjectCreationError(_("Flight Controller Connection"), error_message)

    @classmethod
    def is_fc_dependent_setting(cls, setting_name: str) -> bool:
        """
        Check if a setting requires flight controller connection.

        Args:
            setting_name: Name of the setting

        Returns:
            True if setting requires FC connection, False otherwise

        """
        return setting_name in cls._FC_DEPENDENT_SETTINGS

    def validate_fc_dependent_settings(self, fc_connected: bool) -> None:
        """
        Validate settings that depend on flight controller connectivity.

        Args:
            fc_connected: Whether a flight controller is connected

        Raises:
            VehicleProjectCreationError: If FC-dependent settings are enabled without connection

        """
        # Get all field values as a dictionary
        settings_dict = {
            "copy_vehicle_image": self.copy_vehicle_image,
            "blank_component_data": self.blank_component_data,
            "reset_fc_parameters_to_their_defaults": self.reset_fc_parameters_to_their_defaults,
            "infer_comp_specs_and_conn_from_fc_params": self.infer_comp_specs_and_conn_from_fc_params,
            "use_fc_params": self.use_fc_params,
            "blank_change_reason": self.blank_change_reason,
        }

        # Validate each FC-dependent setting
        for setting_name, setting_value in settings_dict.items():
            if self.__class__.is_fc_dependent_setting(setting_name):
                self.__class__.validate_fc_dependent_setting(setting_name, setting_value, fc_connected)

    def adjust_for_fc_connection(self, fc_connected: bool) -> "NewVehicleProjectSettings":
        """
        Return a copy of settings adjusted for flight controller connection state.

        Args:
            fc_connected: Whether a flight controller is connected

        Returns:
            New NewVehicleProjectSettings instance with adjusted values

        """
        if fc_connected:
            return self  # No adjustment needed

        # Create adjusted settings dictionary
        adjusted_settings = {
            "copy_vehicle_image": self.copy_vehicle_image,
            "blank_component_data": self.blank_component_data,
            "reset_fc_parameters_to_their_defaults": self.reset_fc_parameters_to_their_defaults,
            "infer_comp_specs_and_conn_from_fc_params": self.infer_comp_specs_and_conn_from_fc_params,
            "use_fc_params": self.use_fc_params,
            "blank_change_reason": self.blank_change_reason,
        }

        # Disable FC-dependent settings when FC is not connected
        for setting_name in adjusted_settings:
            if self.__class__.is_fc_dependent_setting(setting_name):
                adjusted_settings[setting_name] = False

        return NewVehicleProjectSettings(**adjusted_settings)


class VehicleProjectCreator:  # pylint: disable=too-few-public-methods
    """Manages vehicle project creation operations."""

    def __init__(self, local_filesystem: LocalFilesystem) -> None:
        """
        Initialize the project creator.

        Args:
            local_filesystem: The filesystem interface for file operations

        """
        self.local_filesystem = local_filesystem

    def create_new_vehicle_from_template(  # pylint: disable=too-many-arguments, too-many-positional-arguments
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
