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
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
    VehicleProjectCreator,
)

# pylint: disable=redefined-outer-name,unused-argument

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
        assert "infer component specifications" in exc_info.value.message

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
