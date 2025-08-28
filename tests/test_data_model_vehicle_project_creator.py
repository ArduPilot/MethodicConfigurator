#!/usr/bin/env python3

"""
Behavior-driven tests for vehicle project creation data model.

This file contains comprehensive BDD tests for the VehicleProjectCreator class
following the project's testing guidelines and behavior-driven development principles.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSetting,
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
    VehicleProjectCreator,
)

# pylint: disable=redefined-outer-name,unused-argument,too-few-public-methods

# ==================== FIXTURES ====================


# pylint: disable=duplicate-code
@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Fixture providing a mock LocalFilesystem with realistic test data."""
    filesystem = MagicMock(spec=LocalFilesystem)

    # Configure realistic file parameters dictionary
    filesystem.file_parameters = {
        "00_default.param": {"PARAM1": MagicMock(), "PARAM2": MagicMock()},
        "01_vehicle_setup.param": {"PARAM3": MagicMock(), "PARAM4": MagicMock()},
    }
    filesystem.vehicle_type = "ArduCopter"

    # Configure successful filesystem operations by default
    filesystem.create_new_vehicle_dir.return_value = ""
    filesystem.copy_template_files_to_new_vehicle_dir.return_value = ""
    filesystem.re_init.return_value = None

    return filesystem


# pylint: enable=duplicate-code


@pytest.fixture
def project_creator(mock_local_filesystem) -> VehicleProjectCreator:
    """Fixture providing a configured VehicleProjectCreator for behavior testing."""
    return VehicleProjectCreator(mock_local_filesystem)


@pytest.fixture
def default_settings() -> NewVehicleProjectSettings:
    """Fixture providing default project settings for testing."""
    return NewVehicleProjectSettings()


@pytest.fixture
def fc_dependent_settings() -> NewVehicleProjectSettings:
    """Fixture providing settings that require flight controller connection."""
    return NewVehicleProjectSettings(
        infer_comp_specs_and_conn_from_fc_params=True,
        use_fc_params=True,
        reset_fc_parameters_to_their_defaults=True,
    )


# ==================== TEST CLASSES ====================


class TestNewVehicleProjectSettingsValidation:
    """Test validation behavior for project settings."""

    def test_user_can_use_default_settings_without_fc_connection(self, default_settings) -> None:
        """
        User can use default project settings when no flight controller is connected.

        GIVEN: A user has default project settings configured
        WHEN: They validate settings without flight controller connection
        THEN: Validation should pass without errors
        """
        # Arrange: Default settings with no FC connection
        fc_connected = False

        # Act & Assert: Validation should pass
        default_settings.validate_fc_dependent_settings(fc_connected)

    def test_user_cannot_use_fc_dependent_settings_without_connection(self, fc_dependent_settings) -> None:
        """
        User receives validation errors when using FC-dependent settings without connection.

        GIVEN: A user configures settings that require flight controller connection
        WHEN: They validate settings without flight controller connected
        THEN: They should receive specific error messages for each FC-dependent setting
        """
        # Arrange: FC-dependent settings with no connection
        fc_connected = False

        # Act & Assert: Should raise error for FC parameter inference
        with pytest.raises(VehicleProjectCreationError) as exc_info:
            fc_dependent_settings.validate_fc_dependent_settings(fc_connected)

        assert "Flight Controller Connection" in exc_info.value.title
        # Check that the error message is one of the valid FC-dependent error messages
        error_message = exc_info.value.message
        expected_messages = [
            "infer component specifications",
            "reset FC parameters to defaults",
            "use FC parameters",
        ]
        assert any(expected_msg in error_message for expected_msg in expected_messages)

    def test_user_can_use_fc_dependent_settings_with_connection(self, fc_dependent_settings) -> None:
        """
        User can use FC-dependent settings when flight controller is connected.

        GIVEN: A user configures settings that require flight controller connection
        WHEN: They validate settings with flight controller connected
        THEN: Validation should pass without errors
        """
        # Arrange: FC-dependent settings with active connection
        fc_connected = True

        # Act & Assert: Validation should pass
        fc_dependent_settings.validate_fc_dependent_settings(fc_connected)

    def test_user_sees_specific_error_for_each_fc_dependent_setting(self) -> None:
        """
        User receives specific error messages for each type of FC-dependent setting.

        GIVEN: A user configures different types of FC-dependent settings
        WHEN: They validate settings without flight controller connected
        THEN: They should receive specific error messages for each setting type
        """
        # Arrange: Test each FC-dependent setting individually
        fc_connected = False

        # Test infer_comp_specs_and_conn_from_fc_params
        settings1 = NewVehicleProjectSettings(infer_comp_specs_and_conn_from_fc_params=True)
        with pytest.raises(VehicleProjectCreationError) as exc_info:
            settings1.validate_fc_dependent_settings(fc_connected)
        assert "infer component specifications" in exc_info.value.message

        # Test use_fc_params
        settings2 = NewVehicleProjectSettings(use_fc_params=True)
        with pytest.raises(VehicleProjectCreationError) as exc_info:
            settings2.validate_fc_dependent_settings(fc_connected)
        assert "use FC parameters" in exc_info.value.message

        # Test reset_fc_parameters_to_their_defaults
        settings3 = NewVehicleProjectSettings(reset_fc_parameters_to_their_defaults=True)
        with pytest.raises(VehicleProjectCreationError) as exc_info:
            settings3.validate_fc_dependent_settings(fc_connected)
        assert "reset FC parameters" in exc_info.value.message


class TestVehicleProjectCreatorValidation:
    """Test input validation behavior for vehicle project creation."""

    def test_user_cannot_create_project_with_empty_template_directory(self, project_creator, default_settings) -> None:
        """
        User receives validation error when template directory is empty.

        GIVEN: A user attempts to create a vehicle project
        WHEN: They provide an empty template directory path
        THEN: They should receive a specific error about template directory
        """
        # Arrange: Empty template directory
        template_dir = ""
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "valid_name"

        # Act & Assert: Should raise validation error
        with pytest.raises(VehicleProjectCreationError) as exc_info:
            project_creator.create_new_vehicle_from_template(template_dir, new_base_dir, new_vehicle_name, default_settings)

        assert "Vehicle template directory" in exc_info.value.title
        assert "must not be empty" in exc_info.value.message

    def test_user_cannot_create_project_with_nonexistent_template_directory(self, project_creator, default_settings) -> None:
        """
        User receives validation error when template directory does not exist.

        GIVEN: A user attempts to create a vehicle project
        WHEN: They provide a non-existent template directory path
        THEN: They should receive a specific error about directory existence
        """
        # Arrange: Non-existent template directory
        template_dir = "/nonexistent/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "valid_name"

        with patch.object(LocalFilesystem, "directory_exists", return_value=False):
            # Act & Assert: Should raise validation error
            with pytest.raises(VehicleProjectCreationError) as exc_info:
                project_creator.create_new_vehicle_from_template(
                    template_dir, new_base_dir, new_vehicle_name, default_settings
                )

            assert "Vehicle template directory" in exc_info.value.title
            assert "does not exist" in exc_info.value.message
            assert template_dir in exc_info.value.message

    def test_user_cannot_create_project_with_empty_vehicle_name(self, project_creator, default_settings) -> None:
        """
        User receives validation error when vehicle name is empty.

        GIVEN: A user attempts to create a vehicle project
        WHEN: They provide an empty vehicle name
        THEN: They should receive a specific error about vehicle name
        """
        # Arrange: Valid template directory but empty vehicle name
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = ""

        with patch.object(LocalFilesystem, "directory_exists", return_value=True):
            # Act & Assert: Should raise validation error
            with pytest.raises(VehicleProjectCreationError) as exc_info:
                project_creator.create_new_vehicle_from_template(
                    template_dir, new_base_dir, new_vehicle_name, default_settings
                )

            assert "New vehicle directory" in exc_info.value.title
            assert "must not be empty" in exc_info.value.message

    def test_user_cannot_create_project_with_invalid_vehicle_name(self, project_creator, default_settings) -> None:
        """
        User receives validation error when vehicle name contains invalid characters.

        GIVEN: A user attempts to create a vehicle project
        WHEN: They provide a vehicle name with invalid characters
        THEN: They should receive a specific error about invalid characters
        """
        # Arrange: Valid template directory but invalid vehicle name
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "invalid/name*with?chars"

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=False),
        ):
            # Act & Assert: Should raise validation error
            with pytest.raises(VehicleProjectCreationError) as exc_info:
                project_creator.create_new_vehicle_from_template(
                    template_dir, new_base_dir, new_vehicle_name, default_settings
                )

            assert "New vehicle directory" in exc_info.value.title
            assert "invalid characters" in exc_info.value.message
            assert new_vehicle_name in exc_info.value.message


class TestVehicleProjectCreationWorkflow:
    """Test complete vehicle project creation workflows."""

    def test_user_can_create_vehicle_project_from_template_successfully(
        self, project_creator, mock_local_filesystem, default_settings
    ) -> None:
        """
        User can successfully create a new vehicle project from a template.

        GIVEN: A user has valid template directory and project settings
        WHEN: They create a new vehicle project
        THEN: The project should be created successfully with proper directory structure
        AND: Template files should be copied to the new directory
        AND: The filesystem should be initialized with the new configuration
        """
        # Arrange: Valid inputs and successful filesystem operations
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "MyQuadcopter"
        expected_vehicle_dir = "/valid/base/dir/MyQuadcopter"

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
            patch.object(LocalFilesystem, "store_recently_used_template_dirs"),
            patch.object(LocalFilesystem, "store_recently_used_vehicle_dir"),
            patch.object(LocalFilesystem, "get_directory_name_from_full_path", return_value="QuadCopter_Template"),
        ):
            # Act: Create new vehicle project
            result_dir = project_creator.create_new_vehicle_from_template(
                template_dir, new_base_dir, new_vehicle_name, default_settings
            )

            # Assert: Vehicle project created successfully
            assert result_dir == expected_vehicle_dir

            # Verify filesystem operations were called correctly
            mock_local_filesystem.create_new_vehicle_dir.assert_called_once_with(expected_vehicle_dir)
            mock_local_filesystem.copy_template_files_to_new_vehicle_dir.assert_called_once_with(
                template_dir,
                expected_vehicle_dir,
                blank_change_reason=default_settings.blank_change_reason,
                copy_vehicle_image=default_settings.copy_vehicle_image,
            )

            # Verify filesystem initialization
            mock_local_filesystem.re_init.assert_called_once_with(
                expected_vehicle_dir, mock_local_filesystem.vehicle_type, default_settings.blank_component_data
            )

            # Verify vehicle_dir was updated
            assert mock_local_filesystem.vehicle_dir == expected_vehicle_dir

    def test_user_sees_error_when_vehicle_directory_creation_fails(
        self, project_creator, mock_local_filesystem, default_settings
    ) -> None:
        """
        User receives specific error when vehicle directory creation fails.

        GIVEN: A user attempts to create a vehicle project
        WHEN: The filesystem fails to create the vehicle directory
        THEN: They should receive a specific error about directory creation
        """
        # Arrange: Valid inputs but directory creation failure
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "MyQuadcopter"
        expected_vehicle_dir = "/valid/base/dir/MyQuadcopter"
        creation_error = "Permission denied creating directory"

        mock_local_filesystem.create_new_vehicle_dir.return_value = creation_error

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
        ):
            # Act & Assert: Should raise error about directory creation
            with pytest.raises(VehicleProjectCreationError) as exc_info:
                project_creator.create_new_vehicle_from_template(
                    template_dir, new_base_dir, new_vehicle_name, default_settings
                )

            assert "New vehicle directory" in exc_info.value.title
            assert creation_error in exc_info.value.message

    def test_user_sees_error_when_template_file_copying_fails(
        self, project_creator, mock_local_filesystem, default_settings
    ) -> None:
        """
        User receives specific error when template file copying fails.

        GIVEN: A user attempts to create a vehicle project
        WHEN: The filesystem fails to copy template files
        THEN: They should receive a specific error about file copying
        """
        # Arrange: Valid inputs but file copying failure
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "MyQuadcopter"
        expected_vehicle_dir = "/valid/base/dir/MyQuadcopter"
        copying_error = "Access denied copying template files"

        mock_local_filesystem.copy_template_files_to_new_vehicle_dir.return_value = copying_error

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
        ):
            # Act & Assert: Should raise error about file copying
            with pytest.raises(VehicleProjectCreationError) as exc_info:
                project_creator.create_new_vehicle_from_template(
                    template_dir, new_base_dir, new_vehicle_name, default_settings
                )

            assert "Copying template files" in exc_info.value.title
            assert copying_error in exc_info.value.message

    def test_user_sees_error_when_filesystem_initialization_fails(
        self, project_creator, mock_local_filesystem, default_settings
    ) -> None:
        """
        User receives specific error when filesystem initialization fails.

        GIVEN: A user attempts to create a vehicle project
        WHEN: The filesystem initialization raises SystemExit
        THEN: They should receive a specific error about parameter file reading
        """
        # Arrange: Valid inputs but filesystem initialization failure
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "MyQuadcopter"
        expected_vehicle_dir = "/valid/base/dir/MyQuadcopter"

        mock_local_filesystem.re_init.side_effect = SystemExit("Critical parameter file error")

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
        ):
            # Act & Assert: Should raise error about parameter file reading
            with pytest.raises(VehicleProjectCreationError) as exc_info:
                project_creator.create_new_vehicle_from_template(
                    template_dir, new_base_dir, new_vehicle_name, default_settings
                )

            assert "Fatal error reading parameter files" in exc_info.value.title
            assert "Critical parameter file error" in exc_info.value.message

    def test_user_sees_error_when_no_parameter_files_found_after_creation(
        self, project_creator, mock_local_filesystem, default_settings
    ) -> None:
        """
        User receives specific error when no parameter files are found after creation.

        GIVEN: A user attempts to create a vehicle project
        WHEN: No parameter files are found after successful creation
        THEN: They should receive a specific error about missing parameter files
        """
        # Arrange: Valid inputs but no parameter files after creation
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "MyQuadcopter"
        expected_vehicle_dir = "/valid/base/dir/MyQuadcopter"

        mock_local_filesystem.file_parameters = {}  # No parameter files

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
        ):
            # Act & Assert: Should raise error about missing parameter files
            with pytest.raises(VehicleProjectCreationError) as exc_info:
                project_creator.create_new_vehicle_from_template(
                    template_dir, new_base_dir, new_vehicle_name, default_settings
                )

            assert "No parameter files found" in exc_info.value.title
            assert "No intermediate parameter files found" in exc_info.value.message

    def test_user_can_create_project_with_custom_settings(self, project_creator, mock_local_filesystem) -> None:
        """
        User can create vehicle project with custom settings for different options.

        GIVEN: A user configures custom project settings
        WHEN: They create a new vehicle project with those settings
        THEN: The settings should be properly applied during creation
        """
        # Arrange: Custom settings with specific options
        custom_settings = NewVehicleProjectSettings(
            blank_component_data=True,
            blank_change_reason=True,
            copy_vehicle_image=True,
        )
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "CustomQuadcopter"
        expected_vehicle_dir = "/valid/base/dir/CustomQuadcopter"

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
            patch.object(LocalFilesystem, "store_recently_used_template_dirs"),
            patch.object(LocalFilesystem, "store_recently_used_vehicle_dir"),
            patch.object(LocalFilesystem, "get_directory_name_from_full_path", return_value="Custom_Template"),
        ):
            # Act: Create vehicle project with custom settings
            result_dir = project_creator.create_new_vehicle_from_template(
                template_dir, new_base_dir, new_vehicle_name, custom_settings
            )

            # Assert: Custom settings were applied
            assert result_dir == expected_vehicle_dir

            # Verify copy operation used custom settings
            mock_local_filesystem.copy_template_files_to_new_vehicle_dir.assert_called_once_with(
                template_dir,
                expected_vehicle_dir,
                blank_change_reason=True,
                copy_vehicle_image=True,
            )

            # Verify filesystem initialization used custom settings
            mock_local_filesystem.re_init.assert_called_once()
            call_args = mock_local_filesystem.re_init.call_args
            assert call_args[0] == (expected_vehicle_dir, mock_local_filesystem.vehicle_type, True)

    def test_user_can_create_project_with_fc_connection(
        self, project_creator, mock_local_filesystem, fc_dependent_settings
    ) -> None:
        """
        User can create vehicle project with FC-dependent settings when FC is connected.

        GIVEN: A user has flight controller connected and FC-dependent settings
        WHEN: They create a new vehicle project
        THEN: The project should be created successfully with FC integration
        """
        # Arrange: Valid inputs with FC connection
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "FCConnectedQuad"
        expected_vehicle_dir = "/valid/base/dir/FCConnectedQuad"
        fc_connected = True

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
            patch.object(LocalFilesystem, "store_recently_used_template_dirs"),
            patch.object(LocalFilesystem, "store_recently_used_vehicle_dir"),
            patch.object(LocalFilesystem, "get_directory_name_from_full_path", return_value="FC_Template"),
        ):
            # Act: Create vehicle project with FC connection
            result_dir = project_creator.create_new_vehicle_from_template(
                template_dir, new_base_dir, new_vehicle_name, fc_dependent_settings, fc_connected
            )

            # Assert: Project created successfully with FC settings
            assert result_dir == expected_vehicle_dir
            mock_local_filesystem.create_new_vehicle_dir.assert_called_once_with(expected_vehicle_dir)

    def test_recently_used_directories_are_stored_after_successful_creation(
        self, project_creator, mock_local_filesystem, default_settings
    ) -> None:
        """
        User's recently used directories are stored after successful project creation.

        GIVEN: A user successfully creates a vehicle project
        WHEN: The creation process completes
        THEN: The template and vehicle directories should be stored as recently used
        AND: The configuration template name should be available for reference
        """
        # Arrange: Valid inputs for successful creation
        template_dir = "/valid/template/dir"
        new_base_dir = "/valid/base/dir"
        new_vehicle_name = "MyQuadcopter"
        expected_vehicle_dir = "/valid/base/dir/MyQuadcopter"

        with (
            patch.object(LocalFilesystem, "directory_exists", return_value=True),
            patch.object(LocalFilesystem, "valid_directory_name", return_value=True),
            patch.object(LocalFilesystem, "new_vehicle_dir", return_value=expected_vehicle_dir),
            patch.object(LocalFilesystem, "store_recently_used_template_dirs") as mock_store_template,
            patch.object(LocalFilesystem, "store_recently_used_vehicle_dir") as mock_store_vehicle,
        ):
            # Act: Create vehicle project
            project_creator.create_new_vehicle_from_template(template_dir, new_base_dir, new_vehicle_name, default_settings)

            # Assert: Recently used directories were stored
            mock_store_template.assert_called_once_with(template_dir, new_base_dir)
            mock_store_vehicle.assert_called_once_with(expected_vehicle_dir)


class TestNewVehicleProjectSettingsMetadata:
    """Test metadata access and class methods for project settings."""

    def test_user_can_get_specific_setting_metadata_with_fc_connected(self) -> None:
        """
        User can retrieve metadata for specific settings when FC is connected.

        GIVEN: A user has flight controller connected
        WHEN: They retrieve metadata for a specific setting
        THEN: The metadata should show the setting as enabled
        """
        # Arrange: FC-dependent setting with connection
        setting_name = "use_fc_params"
        fc_connected = True

        # Act: Get setting metadata
        metadata = NewVehicleProjectSettings.get_setting_metadata(setting_name, fc_connected)

        # Assert: Setting should be enabled
        assert metadata.enabled is True
        assert "Use parameter values from connected FC" in metadata.label
        assert "flight controller is connected" in metadata.tooltip

    def test_user_can_get_specific_setting_metadata_with_fc_disconnected(self) -> None:
        """
        User can retrieve metadata for specific settings when FC is disconnected.

        GIVEN: A user has no flight controller connected
        WHEN: They retrieve metadata for an FC-dependent setting
        THEN: The metadata should show the setting as disabled
        """
        # Arrange: FC-dependent setting without connection
        setting_name = "reset_fc_parameters_to_their_defaults"
        fc_connected = False

        # Act: Get setting metadata
        metadata = NewVehicleProjectSettings.get_setting_metadata(setting_name, fc_connected)

        # Assert: Setting should be disabled
        assert metadata.enabled is False
        assert "Reset flight controller parameters" in metadata.label

    def test_user_gets_error_for_invalid_setting_name(self) -> None:
        """
        User receives KeyError when requesting metadata for non-existent setting.

        GIVEN: A user requests metadata for an invalid setting
        WHEN: They call get_setting_metadata with unknown setting name
        THEN: They should receive a KeyError
        """
        # Arrange: Invalid setting name
        invalid_setting = "nonexistent_setting"
        fc_connected = True

        # Act & Assert: Should raise KeyError
        with pytest.raises(KeyError):
            NewVehicleProjectSettings.get_setting_metadata(invalid_setting, fc_connected)

    def test_user_can_get_all_settings_metadata_with_fc_connected(self) -> None:
        """
        User can retrieve metadata for all settings when FC is connected.

        GIVEN: A user has flight controller connected
        WHEN: They retrieve metadata for all settings
        THEN: All FC-dependent settings should be enabled
        """
        # Arrange: FC connected
        fc_connected = True

        # Act: Get all settings metadata
        all_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected)

        # Assert: All settings should be present and FC-dependent ones enabled
        assert len(all_metadata) == 6  # All settings should be present
        assert all_metadata["use_fc_params"].enabled is True
        assert all_metadata["reset_fc_parameters_to_their_defaults"].enabled is True
        assert all_metadata["infer_comp_specs_and_conn_from_fc_params"].enabled is True
        assert all_metadata["copy_vehicle_image"].enabled is True  # Non-FC dependent

    def test_user_can_get_all_settings_metadata_with_fc_disconnected(self) -> None:
        """
        User can retrieve metadata for all settings when FC is disconnected.

        GIVEN: A user has no flight controller connected
        WHEN: They retrieve metadata for all settings
        THEN: FC-dependent settings should be disabled, others enabled
        """
        # Arrange: FC disconnected
        fc_connected = False

        # Act: Get all settings metadata
        all_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected)

        # Assert: FC-dependent settings disabled, others enabled
        assert all_metadata["use_fc_params"].enabled is False
        assert all_metadata["reset_fc_parameters_to_their_defaults"].enabled is False
        assert all_metadata["infer_comp_specs_and_conn_from_fc_params"].enabled is False
        assert all_metadata["copy_vehicle_image"].enabled is True  # Non-FC dependent
        assert all_metadata["blank_component_data"].enabled is True  # Non-FC dependent

    def test_user_can_check_if_specific_setting_is_enabled(self) -> None:
        """
        User can check if a specific setting should be enabled based on FC connection.

        GIVEN: A user wants to check setting availability
        WHEN: They check if a setting is enabled for given FC connection state
        THEN: The result should reflect FC dependency and connection status
        """
        # Arrange: Test different settings and connection states
        test_cases = [
            ("use_fc_params", True, True),  # FC-dependent, connected = enabled
            ("use_fc_params", False, False),  # FC-dependent, disconnected = disabled
            ("copy_vehicle_image", True, True),  # Non-FC-dependent, connected = enabled
            ("copy_vehicle_image", False, True),  # Non-FC-dependent, disconnected = enabled
        ]

        for setting_name, fc_connected, expected_enabled in test_cases:
            # Act: Check if setting is enabled
            is_enabled = NewVehicleProjectSettings.is_setting_enabled(setting_name, fc_connected)

            # Assert: Enabled state should match expectations
            assert is_enabled == expected_enabled

    def test_user_can_get_enabled_state_for_all_settings(self) -> None:
        """
        User can get enabled state for all settings at once.

        GIVEN: A user wants to know which settings are available
        WHEN: They get the settings state for given FC connection
        THEN: They should receive a dictionary of all setting states
        """
        # Arrange: FC connected
        fc_connected = True

        # Act: Get all settings state
        settings_state = NewVehicleProjectSettings.get_settings_state(fc_connected)

        # Assert: All settings should be present and appropriately enabled
        assert len(settings_state) == 6
        assert all(isinstance(enabled, bool) for enabled in settings_state.values())
        assert settings_state["use_fc_params"] is True  # FC-dependent with connection
        assert settings_state["copy_vehicle_image"] is True  # Always enabled

    def test_user_can_get_default_values_for_all_settings(self) -> None:
        """
        User can retrieve default values for all settings.

        GIVEN: A user wants to know the default configuration
        WHEN: They retrieve default values for settings
        THEN: They should receive the correct default values from dataclass
        """
        # Act: Get default values
        defaults = NewVehicleProjectSettings.get_default_values()

        # Assert: Defaults should match dataclass field defaults
        assert defaults["copy_vehicle_image"] is False
        assert defaults["blank_component_data"] is False
        assert defaults["reset_fc_parameters_to_their_defaults"] is False
        assert defaults["infer_comp_specs_and_conn_from_fc_params"] is False
        assert defaults["use_fc_params"] is False
        assert defaults["blank_change_reason"] is False

    def test_user_can_get_fc_dependent_error_message(self) -> None:
        """
        User can retrieve specific error messages for FC-dependent settings.

        GIVEN: A user wants to understand why an FC-dependent setting is unavailable
        WHEN: They request the error message for that setting
        THEN: They should receive a descriptive error message
        """
        # Arrange: FC-dependent settings
        test_cases = [
            ("use_fc_params", "use FC parameters"),
            ("reset_fc_parameters_to_their_defaults", "reset FC parameters"),
            ("infer_comp_specs_and_conn_from_fc_params", "infer component specifications"),
        ]

        for setting_name, expected_text in test_cases:
            # Act: Get error message
            error_message = NewVehicleProjectSettings.get_fc_dependent_error_message(setting_name)

            # Assert: Error message should be descriptive
            assert expected_text in error_message
            assert "no flight controller connected" in error_message

    def test_user_gets_error_for_non_fc_dependent_error_message(self) -> None:
        """
        User receives KeyError when requesting error message for non-FC-dependent setting.

        GIVEN: A user requests error message for non-FC-dependent setting
        WHEN: They call get_fc_dependent_error_message with non-FC setting
        THEN: They should receive a KeyError
        """
        # Arrange: Non-FC-dependent setting
        non_fc_setting = "copy_vehicle_image"

        # Act & Assert: Should raise KeyError
        with pytest.raises(KeyError):
            NewVehicleProjectSettings.get_fc_dependent_error_message(non_fc_setting)

    def test_user_can_check_if_setting_is_fc_dependent(self) -> None:
        """
        User can check if a setting requires flight controller connection.

        GIVEN: A user wants to know if a setting requires FC connection
        WHEN: They check if a setting is FC-dependent
        THEN: They should get correct dependency information
        """
        # Arrange: Test FC-dependent and non-FC-dependent settings
        fc_dependent_cases = [
            ("use_fc_params", True),
            ("reset_fc_parameters_to_their_defaults", True),
            ("infer_comp_specs_and_conn_from_fc_params", True),
            ("copy_vehicle_image", False),
            ("blank_component_data", False),
            ("blank_change_reason", False),
        ]

        for setting_name, expected_dependency in fc_dependent_cases:
            # Act: Check FC dependency
            is_fc_dependent = NewVehicleProjectSettings.is_fc_dependent_setting(setting_name)

            # Assert: Dependency should match expectations
            assert is_fc_dependent == expected_dependency


class TestNewVehicleProjectSettingsAdjustment:
    """Test settings adjustment for flight controller connection state."""

    def test_user_gets_same_settings_when_fc_connected(self) -> None:
        """
        User receives unchanged settings when FC is connected.

        GIVEN: A user has settings configured and FC is connected
        WHEN: They adjust settings for FC connection state
        THEN: The settings should remain unchanged
        """
        # Arrange: Settings with FC connection
        original_settings = NewVehicleProjectSettings(
            use_fc_params=True,
            reset_fc_parameters_to_their_defaults=True,
            copy_vehicle_image=True,
        )
        fc_connected = True

        # Act: Adjust settings for FC connection
        adjusted_settings = original_settings.adjust_for_fc_connection(fc_connected)

        # Assert: Settings should be the same object (no adjustment needed)
        assert adjusted_settings is original_settings

    def test_user_gets_adjusted_settings_when_fc_disconnected(self) -> None:
        """
        User receives adjusted settings with FC-dependent options disabled when FC is disconnected.

        GIVEN: A user has FC-dependent settings configured but FC is disconnected
        WHEN: They adjust settings for FC connection state
        THEN: FC-dependent settings should be disabled, others preserved
        """
        # Arrange: Settings with FC-dependent options enabled but no FC connection
        original_settings = NewVehicleProjectSettings(
            use_fc_params=True,
            reset_fc_parameters_to_their_defaults=True,
            infer_comp_specs_and_conn_from_fc_params=True,
            copy_vehicle_image=True,
            blank_component_data=True,
        )
        fc_connected = False

        # Act: Adjust settings for FC connection
        adjusted_settings = original_settings.adjust_for_fc_connection(fc_connected)

        # Assert: FC-dependent settings disabled, others preserved
        assert adjusted_settings is not original_settings  # New instance created
        assert adjusted_settings.use_fc_params is False
        assert adjusted_settings.reset_fc_parameters_to_their_defaults is False
        assert adjusted_settings.infer_comp_specs_and_conn_from_fc_params is False
        assert adjusted_settings.copy_vehicle_image is True  # Non-FC-dependent preserved
        assert adjusted_settings.blank_component_data is True  # Non-FC-dependent preserved


class TestVehicleProjectCreationErrorHandling:
    """Test error handling and edge cases for vehicle project creation."""

    def test_vehicle_project_creation_error_stores_title_and_message(self) -> None:
        """
        VehicleProjectCreationError stores both title and message correctly.

        GIVEN: A user encounters a project creation error
        WHEN: The error is raised with title and message
        THEN: Both title and message should be accessible
        """
        # Arrange: Error details
        error_title = "Template Directory Error"
        error_message = "Template directory does not exist or is not accessible"

        # Act: Create error
        error = VehicleProjectCreationError(error_title, error_message)

        # Assert: Error should store both title and message
        assert error.title == error_title
        assert error.message == error_message
        assert str(error) == error_message  # Exception message


class TestNewVehicleProjectSettingsTuple:
    """Test NewVehicleProjectSetting named tuple functionality."""

    def test_user_can_create_setting_tuple_with_all_fields(self) -> None:
        """
        User can create setting metadata tuple with all required fields.

        GIVEN: A user wants to define setting metadata
        WHEN: They create a NewVehicleProjectSetting with all fields
        THEN: All fields should be accessible
        """
        # Arrange: Setting metadata
        label = "Test Setting"
        tooltip = "This is a test setting for validation"
        enabled = True

        # Act: Create setting tuple
        setting = NewVehicleProjectSetting(label, tooltip, enabled)

        # Assert: All fields should be accessible
        assert setting.label == label
        assert setting.tooltip == tooltip
        assert setting.enabled == enabled

    def test_user_can_create_setting_tuple_with_default_enabled(self) -> None:
        """
        User can create setting metadata tuple with default enabled state.

        GIVEN: A user wants to define setting metadata without specifying enabled state
        WHEN: They create a NewVehicleProjectSetting with only label and tooltip
        THEN: The enabled state should default to True
        """
        # Arrange: Setting metadata without enabled state
        label = "Default Enabled Setting"
        tooltip = "This setting defaults to enabled"

        # Act: Create setting tuple with default enabled
        setting = NewVehicleProjectSetting(label, tooltip)

        # Assert: Enabled should default to True
        assert setting.label == label
        assert setting.tooltip == tooltip
        assert setting.enabled is True
