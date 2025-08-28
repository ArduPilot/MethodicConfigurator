#!/usr/bin/env python3

"""
Tests for data_model_vehicle_project.py module.

This module tests the VehicleProjectManager class which provides a unified interface
for all vehicle project operations, acting as a facade that coordinates between
different data models.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
)
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpenError

# pylint: disable=protected-access


class TestVehicleProjectManagerInitialization:
    """Test VehicleProjectManager initialization and basic properties."""

    def test_user_can_initialize_project_manager_without_flight_controller(self) -> None:
        """
        User can create project manager without flight controller.

        GIVEN: A user wants to manage vehicle projects without a flight controller
        WHEN: User initializes VehicleProjectManager with only local filesystem
        THEN: Manager should be created with all internal components initialized
        """
        # Arrange: Create filesystem instance
        mock_filesystem = MagicMock(spec=LocalFilesystem)

        # Act: Initialize project manager without flight controller
        manager = VehicleProjectManager(mock_filesystem)

        # Assert: Manager is properly initialized
        assert manager._local_filesystem is mock_filesystem
        assert manager._flight_controller is None
        assert manager._creator is not None
        assert manager._opener is not None
        assert manager._settings is None
        assert manager.configuration_template == ""

    def test_user_can_initialize_project_manager_with_flight_controller(self) -> None:
        """
        User can create project manager with flight controller.

        GIVEN: A user wants to manage vehicle projects with a connected flight controller
        WHEN: User initializes VehicleProjectManager with filesystem and flight controller
        THEN: Manager should be created with flight controller reference stored
        """
        # Arrange: Create filesystem and flight controller instances
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_flight_controller = MagicMock()

        # Act: Initialize project manager with flight controller
        manager = VehicleProjectManager(mock_filesystem, mock_flight_controller)

        # Assert: Manager is properly initialized with flight controller
        assert manager._local_filesystem is mock_filesystem
        assert manager._flight_controller is mock_flight_controller
        assert manager._creator is not None
        assert manager._opener is not None


class TestDirectoryAndPathOperations:
    """Test directory and path related operations."""

    def test_user_can_get_recently_used_directories(self) -> None:
        """
        User can retrieve recently used directories.

        GIVEN: A project manager with stored directory preferences
        WHEN: User requests recently used directories
        THEN: Should return tuple of template, base, and vehicle directories
        """
        # Arrange: Mock filesystem and recently used directories
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(LocalFilesystem, "get_recently_used_dirs") as mock_get_dirs:
            mock_get_dirs.return_value = ("/templates", "/base", "/vehicle")

            # Act: Get recently used directories
            template_dir, new_base_dir, vehicle_dir = manager.get_recently_used_dirs()

            # Assert: Correct directories returned
            assert template_dir == "/templates"
            assert new_base_dir == "/base"
            assert vehicle_dir == "/vehicle"
            mock_get_dirs.assert_called_once()

    def test_user_can_get_current_working_directory(self) -> None:
        """
        User can get current working directory.

        GIVEN: A project manager in any state
        WHEN: User requests current working directory
        THEN: Should return the current working directory path
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(LocalFilesystem, "getcwd") as mock_getcwd:
            mock_getcwd.return_value = "/current/working/dir"

            # Act: Get current working directory
            result = manager.get_current_working_directory()

            # Assert: Correct directory returned
            assert result == "/current/working/dir"
            mock_getcwd.assert_called_once()

    def test_user_can_extract_directory_name_from_path(self) -> None:
        """
        User can extract directory name from full path.

        GIVEN: A project manager and a full path
        WHEN: User requests directory name extraction
        THEN: Should return just the directory name
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(LocalFilesystem, "get_directory_name_from_full_path") as mock_get_name:
            mock_get_name.return_value = "vehicle_name"

            # Act: Extract directory name
            result = manager.get_directory_name_from_path("/path/to/vehicle_name")

            # Assert: Correct name returned
            assert result == "vehicle_name"
            mock_get_name.assert_called_once_with("/path/to/vehicle_name")

    def test_user_can_check_if_directory_exists(self) -> None:
        """
        User can check if a directory exists.

        GIVEN: A project manager and a directory path
        WHEN: User checks if directory exists
        THEN: Should return boolean indicating existence
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(LocalFilesystem, "directory_exists") as mock_exists:
            mock_exists.return_value = True

            # Act: Check directory existence
            result = manager.directory_exists("/test/path")

            # Assert: Correct existence status returned
            assert result is True
            mock_exists.assert_called_once_with("/test/path")

    def test_user_can_validate_directory_name(self) -> None:
        """
        User can validate directory name.

        GIVEN: A project manager and a directory name
        WHEN: User validates directory name
        THEN: Should return boolean indicating validity
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(LocalFilesystem, "valid_directory_name") as mock_valid:
            mock_valid.return_value = True

            # Act: Validate directory name
            result = manager.valid_directory_name("valid_name")

            # Assert: Correct validation result returned
            assert result is True
            mock_valid.assert_called_once_with("valid_name")


class TestVehicleProjectCreation:
    """Test vehicle project creation operations."""

    def test_user_can_create_new_vehicle_from_template_successfully(self) -> None:
        """
        User can create new vehicle from template successfully.

        GIVEN: A project manager with valid template and settings
        WHEN: User creates new vehicle from template
        THEN: Should create vehicle directory and update manager state
        """
        # Arrange: Mock filesystem and components
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_flight_controller = MagicMock()
        mock_flight_controller.master = MagicMock()  # FC is connected
        manager = VehicleProjectManager(mock_filesystem, mock_flight_controller)

        # Mock the creator
        with patch.object(manager._creator, "create_new_vehicle_from_template") as mock_create:
            mock_create.return_value = "/new/vehicle/path"

            mock_settings = MagicMock(spec=NewVehicleProjectSettings)

            # Act: Create new vehicle from template
            result = manager.create_new_vehicle_from_template("/template/path", "/base/path", "NewVehicle", mock_settings)

            # Assert: Vehicle created successfully and state updated
            assert result == "/new/vehicle/path"
            assert manager._settings is mock_settings
            assert manager.configuration_template == "path"  # Directory name from template path
            mock_create.assert_called_once()
            # Check that the call includes the fc_connected flag
            call_args = mock_create.call_args
            assert call_args[0][:4] == ("/template/path", "/base/path", "NewVehicle", mock_settings)
            assert call_args[0][4] is True  # fc_connected flag

    def test_user_sees_error_when_vehicle_creation_fails(self) -> None:
        """
        User sees error when vehicle creation fails.

        GIVEN: A project manager with invalid settings
        WHEN: User attempts to create vehicle from template
        THEN: Should raise VehicleProjectCreationError
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Mock the creator to raise an exception
        with patch.object(manager._creator, "create_new_vehicle_from_template") as mock_create:
            mock_create.side_effect = VehicleProjectCreationError("Creation Error", "Creation failed")

            mock_settings = MagicMock(spec=NewVehicleProjectSettings)

            # Act & Assert: Creation should raise error
            with pytest.raises(VehicleProjectCreationError, match="Creation failed"):
                manager.create_new_vehicle_from_template("/template/path", "/base/path", "NewVehicle", mock_settings)


class TestVehicleProjectOpening:
    """Test vehicle project opening operations."""

    def test_user_can_open_vehicle_directory_successfully(self) -> None:
        """
        User can open existing vehicle directory successfully.

        GIVEN: A project manager with valid vehicle directory
        WHEN: User opens vehicle directory
        THEN: Should open directory and return path
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Mock the opener
        with patch.object(manager._opener, "open_vehicle_directory") as mock_open:
            mock_open.return_value = "/opened/vehicle/path"

            # Act: Open vehicle directory
            result = manager.open_vehicle_directory("/vehicle/path")

            # Assert: Directory opened successfully
            assert result == "/opened/vehicle/path"
            mock_open.assert_called_once_with("/vehicle/path")

    def test_user_sees_error_when_vehicle_directory_opening_fails(self) -> None:
        """
        User sees error when vehicle directory opening fails.

        GIVEN: A project manager with invalid vehicle directory
        WHEN: User attempts to open vehicle directory
        THEN: Should raise VehicleProjectOpenError
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Mock the opener to raise an exception
        with patch.object(manager._opener, "open_vehicle_directory") as mock_open:
            mock_open.side_effect = VehicleProjectOpenError("Open Error", "Opening failed")

            # Act & Assert: Opening should raise error
            with pytest.raises(VehicleProjectOpenError, match="Opening failed"):
                manager.open_vehicle_directory("/invalid/path")

    def test_user_can_open_last_vehicle_directory_successfully(self) -> None:
        """
        User can open last used vehicle directory successfully.

        GIVEN: A project manager with last used vehicle directory
        WHEN: User opens last vehicle directory
        THEN: Should open directory and return path
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Mock the opener
        with patch.object(manager._opener, "open_last_vehicle_directory") as mock_open:
            mock_open.return_value = "/last/vehicle/path"

            # Act: Open last vehicle directory
            result = manager.open_last_vehicle_directory("/last/path")

            # Assert: Directory opened successfully
            assert result == "/last/vehicle/path"
            mock_open.assert_called_once_with("/last/path")

    def test_user_sees_error_when_opening_last_vehicle_directory_fails(self) -> None:
        """
        User sees error when opening last vehicle directory fails.

        GIVEN: A project manager with invalid last vehicle directory
        WHEN: User attempts to open last vehicle directory
        THEN: Should raise VehicleProjectOpenError
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Mock the opener to raise an exception
        with patch.object(manager._opener, "open_last_vehicle_directory") as mock_open:
            mock_open.side_effect = VehicleProjectOpenError("Last Open Error", "Last directory opening failed")

            # Act & Assert: Opening should raise error
            with pytest.raises(VehicleProjectOpenError, match="Last directory opening failed"):
                manager.open_last_vehicle_directory("/invalid/last/path")


class TestFilesystemStateManagement:
    """Test filesystem state management operations."""

    def test_user_can_get_current_vehicle_directory(self) -> None:
        """
        User can get current vehicle directory from filesystem.

        GIVEN: A project manager with filesystem containing vehicle directory
        WHEN: User requests current vehicle directory
        THEN: Should return filesystem's vehicle directory
        """
        # Arrange: Mock filesystem with vehicle directory
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_filesystem.vehicle_dir = "/current/vehicle"
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Get vehicle directory
        result = manager.get_vehicle_directory()

        # Assert: Correct vehicle directory returned
        assert result == "/current/vehicle"

    def test_user_can_store_recently_used_template_directories(self) -> None:
        """
        User can store recently used template and base directories.

        GIVEN: A project manager and template/base directories
        WHEN: User stores recently used template directories
        THEN: Should delegate to LocalFilesystem for storage
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(LocalFilesystem, "store_recently_used_template_dirs") as mock_store:
            # Act: Store template directories
            manager.store_recently_used_template_dirs("/template", "/base")

            # Assert: Storage delegated correctly
            mock_store.assert_called_once_with("/template", "/base")

    def test_user_can_store_recently_used_vehicle_directory(self) -> None:
        """
        User can store recently used vehicle directory.

        GIVEN: A project manager and vehicle directory
        WHEN: User stores recently used vehicle directory
        THEN: Should delegate to LocalFilesystem for storage
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir") as mock_store:
            # Act: Store vehicle directory
            manager.store_recently_used_vehicle_dir("/vehicle")

            # Assert: Storage delegated correctly
            mock_store.assert_called_once_with("/vehicle")


class TestProjectSettingsProperties:
    """Test project settings property access."""

    def test_user_can_access_reset_fc_parameters_property_when_settings_exist(self) -> None:
        """
        User can access reset FC parameters property when settings exist.

        GIVEN: A project manager with settings configured
        WHEN: User accesses reset_fc_parameters_to_their_defaults property
        THEN: Should return the setting value from project settings
        """
        # Arrange: Mock filesystem and settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        mock_settings = MagicMock(spec=NewVehicleProjectSettings)
        mock_settings.reset_fc_parameters_to_their_defaults = True
        manager._settings = mock_settings

        # Act: Access property
        result = manager.reset_fc_parameters_to_their_defaults

        # Assert: Correct value returned
        assert result is True

    def test_user_gets_false_for_reset_fc_parameters_when_no_settings(self) -> None:
        """
        User gets False for reset FC parameters when no settings exist.

        GIVEN: A project manager without settings configured
        WHEN: User accesses reset_fc_parameters_to_their_defaults property
        THEN: Should return False
        """
        # Arrange: Mock filesystem without settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Access property
        result = manager.reset_fc_parameters_to_their_defaults

        # Assert: False returned for missing settings
        assert result is False

    def test_user_can_access_blank_component_data_property_when_settings_exist(self) -> None:
        """
        User can access blank component data property when settings exist.

        GIVEN: A project manager with settings configured
        WHEN: User accesses blank_component_data property
        THEN: Should return the setting value from project settings
        """
        # Arrange: Mock filesystem and settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        mock_settings = MagicMock(spec=NewVehicleProjectSettings)
        mock_settings.blank_component_data = True
        manager._settings = mock_settings

        # Act: Access property
        result = manager.blank_component_data

        # Assert: Correct value returned
        assert result is True

    def test_user_gets_false_for_blank_component_data_when_no_settings(self) -> None:
        """
        User gets False for blank component data when no settings exist.

        GIVEN: A project manager without settings configured
        WHEN: User accesses blank_component_data property
        THEN: Should return False
        """
        # Arrange: Mock filesystem without settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Access property
        result = manager.blank_component_data

        # Assert: False returned for missing settings
        assert result is False

    def test_user_can_access_infer_comp_specs_property_when_settings_exist(self) -> None:
        """
        User can access infer component specs property when settings exist.

        GIVEN: A project manager with settings configured
        WHEN: User accesses infer_comp_specs_and_conn_from_fc_params property
        THEN: Should return the setting value from project settings
        """
        # Arrange: Mock filesystem and settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        mock_settings = MagicMock(spec=NewVehicleProjectSettings)
        mock_settings.infer_comp_specs_and_conn_from_fc_params = True
        manager._settings = mock_settings

        # Act: Access property
        result = manager.infer_comp_specs_and_conn_from_fc_params

        # Assert: Correct value returned
        assert result is True

    def test_user_gets_false_for_infer_comp_specs_when_no_settings(self) -> None:
        """
        User gets False for infer component specs when no settings exist.

        GIVEN: A project manager without settings configured
        WHEN: User accesses infer_comp_specs_and_conn_from_fc_params property
        THEN: Should return False
        """
        # Arrange: Mock filesystem without settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Access property
        result = manager.infer_comp_specs_and_conn_from_fc_params

        # Assert: False returned for missing settings
        assert result is False

    def test_user_can_access_use_fc_params_property_when_settings_exist(self) -> None:
        """
        User can access use FC params property when settings exist.

        GIVEN: A project manager with settings configured
        WHEN: User accesses use_fc_params property
        THEN: Should return the setting value from project settings
        """
        # Arrange: Mock filesystem and settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        mock_settings = MagicMock(spec=NewVehicleProjectSettings)
        mock_settings.use_fc_params = True
        manager._settings = mock_settings

        # Act: Access property
        result = manager.use_fc_params

        # Assert: Correct value returned
        assert result is True

    def test_user_gets_false_for_use_fc_params_when_no_settings(self) -> None:
        """
        User gets False for use FC params when no settings exist.

        GIVEN: A project manager without settings configured
        WHEN: User accesses use_fc_params property
        THEN: Should return False
        """
        # Arrange: Mock filesystem without settings
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Access property
        result = manager.use_fc_params

        # Assert: False returned for missing settings
        assert result is False


class TestFlightControllerOperations:
    """Test flight controller related operations."""

    def test_user_can_check_flight_controller_connection_when_connected(self) -> None:
        """
        User can check flight controller connection when connected.

        GIVEN: A project manager with connected flight controller
        WHEN: User checks flight controller connection
        THEN: Should return True
        """
        # Arrange: Mock filesystem and connected flight controller
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_flight_controller = MagicMock()
        mock_flight_controller.master = MagicMock()  # Connected
        manager = VehicleProjectManager(mock_filesystem, mock_flight_controller)

        # Act: Check connection
        result = manager.is_flight_controller_connected()

        # Assert: Connection detected
        assert result is True

    def test_user_can_check_flight_controller_connection_when_disconnected(self) -> None:
        """
        User can check flight controller connection when disconnected.

        GIVEN: A project manager with disconnected flight controller
        WHEN: User checks flight controller connection
        THEN: Should return False
        """
        # Arrange: Mock filesystem and disconnected flight controller
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_flight_controller = MagicMock()
        mock_flight_controller.master = None  # Disconnected
        manager = VehicleProjectManager(mock_filesystem, mock_flight_controller)

        # Act: Check connection
        result = manager.is_flight_controller_connected()

        # Assert: No connection detected
        assert result is False

    def test_user_can_check_flight_controller_connection_when_no_controller(self) -> None:
        """
        User can check flight controller connection when no controller exists.

        GIVEN: A project manager without flight controller
        WHEN: User checks flight controller connection
        THEN: Should return False
        """
        # Arrange: Mock filesystem without flight controller
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Check connection
        result = manager.is_flight_controller_connected()

        # Assert: No connection detected
        assert result is False

    def test_user_can_check_if_last_vehicle_directory_can_be_opened_when_exists(self) -> None:
        """
        User can check if last vehicle directory can be opened when it exists.

        GIVEN: A project manager with existing last vehicle directory
        WHEN: User checks if last vehicle directory can be opened
        THEN: Should return True
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(manager, "directory_exists") as mock_exists:
            mock_exists.return_value = True

            # Act: Check if can open last directory
            result = manager.can_open_last_vehicle_directory("/existing/path")

            # Assert: Can open existing directory
            assert result is True
            mock_exists.assert_called_once_with("/existing/path")

    def test_user_can_check_if_last_vehicle_directory_can_be_opened_when_not_exists(self) -> None:
        """
        User can check if last vehicle directory can be opened when it doesn't exist.

        GIVEN: A project manager with non-existing last vehicle directory
        WHEN: User checks if last vehicle directory can be opened
        THEN: Should return False
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(manager, "directory_exists") as mock_exists:
            mock_exists.return_value = False

            # Act: Check if can open last directory
            result = manager.can_open_last_vehicle_directory("/nonexistent/path")

            # Assert: Cannot open non-existent directory
            assert result is False
            mock_exists.assert_called_once_with("/nonexistent/path")

    def test_user_can_check_if_last_vehicle_directory_can_be_opened_when_empty_path(self) -> None:
        """
        User can check if last vehicle directory can be opened when path is empty.

        GIVEN: A project manager with empty last vehicle directory path
        WHEN: User checks if last vehicle directory can be opened
        THEN: Should return False
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Check if can open empty path
        result = manager.can_open_last_vehicle_directory("")

        # Assert: Cannot open empty path
        assert result is False


class TestIntroductionMessageAndFileOperations:
    """Test introduction message generation and file operations."""

    def test_user_gets_working_directory_message_when_in_current_directory(self) -> None:
        """
        User gets working directory message when in current directory.

        GIVEN: A project manager where vehicle directory equals working directory
        WHEN: User requests introduction message
        THEN: Should return current working directory message
        """
        # Arrange: Mock filesystem with equal directories
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_filesystem.vehicle_dir = "/working/dir"
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(manager, "get_current_working_directory") as mock_getcwd:
            mock_getcwd.return_value = "/working/dir"

            # Act: Get introduction message
            result = manager.get_introduction_message()

            # Assert: Current working directory message returned
            assert "current working directory" in result

    def test_user_gets_vehicle_dir_message_when_in_different_directory(self) -> None:
        """
        User gets vehicle dir message when in different directory.

        GIVEN: A project manager where vehicle directory differs from working directory
        WHEN: User requests introduction message
        THEN: Should return vehicle directory specified message
        """
        # Arrange: Mock filesystem with different directories
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_filesystem.vehicle_dir = "/vehicle/dir"
        manager = VehicleProjectManager(mock_filesystem)

        with patch.object(manager, "get_current_working_directory") as mock_getcwd:
            mock_getcwd.return_value = "/working/dir"

            # Act: Get introduction message
            result = manager.get_introduction_message()

            # Assert: Vehicle directory specified message returned
            assert "--vehicle-dir specified directory" in result

    def test_user_can_get_file_parameters_list(self) -> None:
        """
        User can get list of intermediate parameter files.

        GIVEN: A project manager with filesystem containing parameter files
        WHEN: User requests file parameters list
        THEN: Should return list of parameter file names
        """
        # Arrange: Mock filesystem with parameter files
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_filesystem.file_parameters = {
            "01_first.param": {},
            "02_second.param": {},
            "03_third.param": {},
        }
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Get file parameters list
        result = manager.get_file_parameters_list()

        # Assert: Correct list of parameter files returned
        assert len(result) == 3
        assert "01_first.param" in result
        assert "02_second.param" in result
        assert "03_third.param" in result

    def test_user_can_get_default_vehicle_name(self) -> None:
        """
        User can get default name for new vehicle directory.

        GIVEN: A project manager in any state
        WHEN: User requests default vehicle name
        THEN: Should return localized default vehicle name
        """
        # Arrange: Mock filesystem
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        # Act: Get default vehicle name
        result = manager.get_default_vehicle_name()

        # Assert: Default name returned (should be translatable)
        assert result == "MyVehicleName"  # This should be localized in actual use


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    def test_user_can_complete_new_vehicle_creation_workflow(self) -> None:
        """
        User can complete full new vehicle creation workflow.

        GIVEN: A project manager with all components configured
        WHEN: User completes vehicle creation from template to storage
        THEN: Should create vehicle, update state, and store preferences
        """
        # Arrange: Mock all components
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_flight_controller = MagicMock()
        mock_flight_controller.master = MagicMock()
        manager = VehicleProjectManager(mock_filesystem, mock_flight_controller)

        with (
            patch.object(manager._creator, "create_new_vehicle_from_template") as mock_create,
            patch.object(LocalFilesystem, "store_recently_used_template_dirs") as mock_store_template,
            patch.object(LocalFilesystem, "store_recently_used_vehicle_dir") as mock_store_vehicle,
        ):
            mock_create.return_value = "/new/vehicle/MyVehicle"
            mock_settings = MagicMock(spec=NewVehicleProjectSettings)

            # Act: Complete workflow
            vehicle_path = manager.create_new_vehicle_from_template(
                "/templates/ArduCopter", "/vehicles", "MyVehicle", mock_settings
            )
            manager.store_recently_used_template_dirs("/templates/ArduCopter", "/vehicles")
            manager.store_recently_used_vehicle_dir(vehicle_path)

            # Assert: Complete workflow executed
            assert vehicle_path == "/new/vehicle/MyVehicle"
            assert manager._settings is mock_settings
            assert manager.configuration_template == "ArduCopter"
            mock_create.assert_called_once()
            mock_store_template.assert_called_once_with("/templates/ArduCopter", "/vehicles")
            mock_store_vehicle.assert_called_once_with("/new/vehicle/MyVehicle")

    def test_user_can_complete_vehicle_opening_workflow(self) -> None:
        """
        User can complete full vehicle opening workflow.

        GIVEN: A project manager with existing vehicle directory
        WHEN: User completes vehicle opening and preference storage
        THEN: Should open vehicle and store preferences
        """
        # Arrange: Mock all components
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        manager = VehicleProjectManager(mock_filesystem)

        with (
            patch.object(manager._opener, "open_vehicle_directory") as mock_open,
            patch.object(LocalFilesystem, "store_recently_used_vehicle_dir") as mock_store,
        ):
            mock_open.return_value = "/opened/vehicle/path"

            # Act: Complete workflow
            vehicle_path = manager.open_vehicle_directory("/vehicle/path")
            manager.store_recently_used_vehicle_dir(vehicle_path)

            # Assert: Complete workflow executed
            assert vehicle_path == "/opened/vehicle/path"
            mock_open.assert_called_once_with("/vehicle/path")
            mock_store.assert_called_once_with("/opened/vehicle/path")
