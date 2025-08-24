#!/usr/bin/env python3

"""
Behavior-driven tests for vehicle project opening data model.

This file contains comprehensive BDD tests for the VehicleProjectOpener class
following the project's testing guidelines and behavior-driven development principles.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import (
    VehicleProjectOpener,
    VehicleProjectOpenError,
)

# pylint: disable=redefined-outer-name,unused-argument,protected-access

# ==================== FIXTURES ====================


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
    filesystem.allow_editing_template_files = False

    # Configure vehicle components filesystem
    filesystem.vehicle_components_fs = MagicMock()
    filesystem.vehicle_components_fs.json_filename = "vehicle_components.json"

    # Configure successful filesystem operations by default
    filesystem.vehicle_configuration_files_exist.return_value = True
    filesystem.re_init.return_value = None

    return filesystem


@pytest.fixture
def project_opener(mock_local_filesystem) -> VehicleProjectOpener:
    """Fixture providing a configured VehicleProjectOpener for behavior testing."""
    return VehicleProjectOpener(mock_local_filesystem)


# ==================== TEST CLASSES ====================


class TestVehicleProjectOpenErrorException:
    """Test the custom exception behavior."""

    def test_exception_stores_title_and_message_correctly(self) -> None:
        """
        Exception correctly stores title and message for user feedback.

        GIVEN: A vehicle project opening operation fails
        WHEN: A VehicleProjectOpenError is raised with title and message
        THEN: The exception should store both values for display to user
        """
        # Arrange: Error details
        title = "Invalid Directory"
        message = "The selected directory does not contain required files"

        # Act: Create exception
        error = VehicleProjectOpenError(title, message)

        # Assert: Exception stores values correctly
        assert error.title == title
        assert error.message == message
        assert str(error) == message


class TestLastVehicleDirectoryOpening:
    """Test opening the last used vehicle directory."""

    def test_user_can_open_last_vehicle_directory_successfully(self, project_opener, mock_local_filesystem) -> None:
        """
        User can successfully open the last used vehicle directory.

        GIVEN: A user has a valid last vehicle directory path
        WHEN: They attempt to open the last vehicle directory
        THEN: The directory should be opened and filesystem initialized
        AND: The vehicle directory path should be returned
        """
        # Arrange: Valid last vehicle directory
        last_vehicle_dir = "/path/to/last/vehicle"

        # Act: Open last vehicle directory
        result = project_opener.open_last_vehicle_directory(last_vehicle_dir)

        # Assert: Directory opened successfully
        assert result == last_vehicle_dir
        assert mock_local_filesystem.vehicle_dir == last_vehicle_dir
        mock_local_filesystem.re_init.assert_called_once_with(last_vehicle_dir, mock_local_filesystem.vehicle_type)

    def test_user_sees_error_when_no_last_directory_provided(self, project_opener) -> None:
        """
        User receives error when no last vehicle directory is available.

        GIVEN: A user attempts to open the last vehicle directory
        WHEN: No last vehicle directory path is available (empty string)
        THEN: They should receive a specific error about no directory found
        """
        # Arrange: Empty last vehicle directory
        last_vehicle_dir = ""

        # Act & Assert: Should raise error about no directory found
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_last_vehicle_directory(last_vehicle_dir)

        assert "No Last Vehicle Directory Found" in exc_info.value.title
        assert "No last opened vehicle configuration directory was found" in exc_info.value.message

    def test_user_sees_error_when_filesystem_initialization_fails(self, project_opener, mock_local_filesystem) -> None:
        """
        User receives error when filesystem initialization fails for last directory.

        GIVEN: A user attempts to open the last vehicle directory
        WHEN: The filesystem re-initialization raises SystemExit
        THEN: They should receive a specific error about parameter file reading
        """
        # Arrange: Valid directory but filesystem initialization failure
        last_vehicle_dir = "/path/to/last/vehicle"
        mock_local_filesystem.re_init.side_effect = SystemExit("Critical filesystem error")

        # Act & Assert: Should raise error about parameter file reading
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_last_vehicle_directory(last_vehicle_dir)

        assert "Fatal error reading parameter files" in exc_info.value.title
        assert "Critical filesystem error" in exc_info.value.message

    def test_user_sees_error_when_no_parameter_files_found_in_last_directory(
        self, project_opener, mock_local_filesystem
    ) -> None:
        """
        User receives error when no parameter files found in last vehicle directory.

        GIVEN: A user attempts to open the last vehicle directory
        WHEN: The directory contains no parameter files
        THEN: They should receive a specific error about missing parameter files
        """
        # Arrange: Valid directory but no parameter files
        last_vehicle_dir = "/path/to/last/vehicle"
        mock_local_filesystem.file_parameters = {}

        # Act & Assert: Should raise error about missing parameter files
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_last_vehicle_directory(last_vehicle_dir)

        assert "No parameter files found" in exc_info.value.title
        assert last_vehicle_dir in exc_info.value.message
        assert "No intermediate parameter files found" in exc_info.value.message

    def test_user_sees_error_when_parameter_files_dict_is_none(self, project_opener, mock_local_filesystem) -> None:
        """
        User receives error when parameter files dictionary is None.

        GIVEN: A user attempts to open the last vehicle directory
        WHEN: The filesystem returns None for file_parameters
        THEN: They should receive a specific error about missing parameter files
        """
        # Arrange: Valid directory but None parameter files
        last_vehicle_dir = "/path/to/last/vehicle"
        mock_local_filesystem.file_parameters = None

        # Act & Assert: Should raise error about missing parameter files
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_last_vehicle_directory(last_vehicle_dir)

        assert "No parameter files found" in exc_info.value.title
        assert last_vehicle_dir in exc_info.value.message


class TestVehicleDirectoryOpening:
    """Test opening specific vehicle directories."""

    def test_user_can_open_existing_vehicle_directory_successfully(self, project_opener, mock_local_filesystem) -> None:
        """
        User can successfully open an existing vehicle directory.

        GIVEN: A user selects a valid vehicle directory
        WHEN: They attempt to open the directory
        THEN: The directory should be opened and filesystem initialized
        AND: The directory should be stored as recently used
        AND: The vehicle directory path should be returned
        """
        # Arrange: Valid vehicle directory
        vehicle_dir = "/path/to/vehicle/directory"

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir") as mock_store:
            # Act: Open vehicle directory
            result = project_opener.open_vehicle_directory(vehicle_dir)

            # Assert: Directory opened successfully
            assert result == vehicle_dir
            assert mock_local_filesystem.vehicle_dir == vehicle_dir
            mock_local_filesystem.re_init.assert_called_once_with(vehicle_dir, mock_local_filesystem.vehicle_type)
            mock_store.assert_called_once_with(vehicle_dir)

    def test_user_cannot_open_directory_without_required_files(self, project_opener, mock_local_filesystem) -> None:
        """
        User receives error when directory doesn't contain required files.

        GIVEN: A user selects a directory that doesn't contain vehicle configuration files
        WHEN: They attempt to open the directory
        THEN: They should receive a specific error about missing required files
        """
        # Arrange: Directory without required files
        vehicle_dir = "/path/to/invalid/directory"
        mock_local_filesystem.vehicle_configuration_files_exist.return_value = False

        # Act & Assert: Should raise error about missing required files
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_vehicle_directory(vehicle_dir)

        assert "Invalid Vehicle Directory Selected" in exc_info.value.title
        assert "vehicle_components.json" in exc_info.value.message
        assert "\\d\\d_*\\.param" in exc_info.value.message

    def test_user_cannot_edit_template_directory_when_editing_disabled(self, project_opener, mock_local_filesystem) -> None:
        """
        User receives error when attempting to edit template directory with editing disabled.

        GIVEN: A user selects a directory in the vehicle_templates folder
        WHEN: Template editing is disabled and they attempt to open it
        THEN: They should receive a warning about not editing template files
        """
        # Arrange: Template directory with editing disabled
        vehicle_dir = "/path/to/vehicle_templates/ArduCopter/template"
        mock_local_filesystem.allow_editing_template_files = False

        # Act & Assert: Should raise error about template editing
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_vehicle_directory(vehicle_dir)

        assert "Invalid Vehicle Directory Selected" in exc_info.value.title
        assert "Please do not edit the files provided 'vehicle_templates' directory" in exc_info.value.message

    def test_user_can_edit_template_directory_when_editing_enabled(self, project_opener, mock_local_filesystem) -> None:
        """
        User can open template directory when template editing is enabled.

        GIVEN: A user selects a directory in the vehicle_templates folder
        WHEN: Template editing is enabled and they attempt to open it
        THEN: The directory should open successfully
        """
        # Arrange: Template directory with editing enabled
        vehicle_dir = "/path/to/vehicle_templates/ArduCopter/template"
        mock_local_filesystem.allow_editing_template_files = True

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir"):
            # Act: Open template directory
            result = project_opener.open_vehicle_directory(vehicle_dir)

            # Assert: Directory opened successfully
            assert result == vehicle_dir
            assert mock_local_filesystem.vehicle_dir == vehicle_dir

    def test_user_sees_error_when_filesystem_initialization_fails_for_directory(
        self, project_opener, mock_local_filesystem
    ) -> None:
        """
        User receives error when filesystem initialization fails for selected directory.

        GIVEN: A user selects a valid vehicle directory
        WHEN: The filesystem re-initialization raises SystemExit
        THEN: They should receive a specific error about parameter file reading
        """
        # Arrange: Valid directory but filesystem initialization failure
        vehicle_dir = "/path/to/vehicle/directory"
        mock_local_filesystem.re_init.side_effect = SystemExit("Critical initialization error")

        # Act & Assert: Should raise error about parameter file reading
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_vehicle_directory(vehicle_dir)

        assert "Fatal error reading parameter files" in exc_info.value.title
        assert "Critical initialization error" in exc_info.value.message

    def test_user_sees_error_when_no_parameter_files_found_in_directory(self, project_opener, mock_local_filesystem) -> None:
        """
        User receives error when no parameter files found in selected directory.

        GIVEN: A user selects a valid vehicle directory
        WHEN: The directory contains no parameter files after initialization
        THEN: They should receive a specific error about missing parameter files
        """
        # Arrange: Valid directory but no parameter files after initialization
        vehicle_dir = "/path/to/vehicle/directory"
        mock_local_filesystem.file_parameters = {}

        # Act & Assert: Should raise error about missing parameter files
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener.open_vehicle_directory(vehicle_dir)

        assert "No parameter files found" in exc_info.value.title
        assert vehicle_dir in exc_info.value.message
        assert "No intermediate parameter files found" in exc_info.value.message

    def test_recently_used_directory_is_stored_after_successful_opening(self, project_opener, mock_local_filesystem) -> None:
        """
        User's recently used directory is stored after successful directory opening.

        GIVEN: A user successfully opens a vehicle directory
        WHEN: The opening process completes successfully
        THEN: The directory should be stored as recently used for future access
        """
        # Arrange: Valid vehicle directory
        vehicle_dir = "/path/to/vehicle/directory"

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir") as mock_store:
            # Act: Open vehicle directory
            project_opener.open_vehicle_directory(vehicle_dir)

            # Assert: Directory stored as recently used
            mock_store.assert_called_once_with(vehicle_dir)


class TestVehicleDirectoryValidation:
    """Test vehicle directory validation behavior."""

    def test_validation_passes_for_valid_directory(self, project_opener, mock_local_filesystem) -> None:
        """
        Validation passes for a valid vehicle directory.

        GIVEN: A user provides a valid vehicle directory path
        WHEN: The directory validation is performed
        THEN: No exception should be raised
        """
        # Arrange: Valid directory setup
        vehicle_dir = "/path/to/valid/vehicle"

        with patch.object(LocalFilesystem, "directory_exists", return_value=True):
            # Act & Assert: Validation should pass without exception
            project_opener._validate_existing_directory(vehicle_dir)

    def test_validation_fails_for_empty_directory_path(self, project_opener) -> None:
        """
        Validation fails when directory path is empty.

        GIVEN: A user provides an empty directory path
        WHEN: The directory validation is performed
        THEN: They should receive a specific error about empty directory
        """
        # Arrange: Empty directory path
        vehicle_dir = ""

        # Act & Assert: Should raise error about empty directory
        with pytest.raises(VehicleProjectOpenError) as exc_info:
            project_opener._validate_existing_directory(vehicle_dir)

        assert "Vehicle directory" in exc_info.value.title
        assert "must not be empty" in exc_info.value.message

    def test_validation_fails_for_nonexistent_directory(self, project_opener, mock_local_filesystem) -> None:
        """
        Validation fails when directory does not exist.

        GIVEN: A user provides a path to a non-existent directory
        WHEN: The directory validation is performed
        THEN: They should receive a specific error about directory not existing
        """
        # Arrange: Non-existent directory
        vehicle_dir = "/path/to/nonexistent/directory"

        with patch.object(LocalFilesystem, "directory_exists", return_value=False):
            # Act & Assert: Should raise error about directory not existing
            with pytest.raises(VehicleProjectOpenError) as exc_info:
                project_opener._validate_existing_directory(vehicle_dir)

            assert "Vehicle directory" in exc_info.value.title
            assert "does not exist" in exc_info.value.message
            assert vehicle_dir in exc_info.value.message

    def test_validation_fails_for_directory_without_configuration_files(self, project_opener, mock_local_filesystem) -> None:
        """
        Validation fails when directory lacks required configuration files.

        GIVEN: A user provides a path to a directory without vehicle configuration files
        WHEN: The directory validation is performed
        THEN: They should receive a specific error about missing configuration files
        """
        # Arrange: Directory without configuration files
        vehicle_dir = "/path/to/incomplete/directory"
        mock_local_filesystem.vehicle_configuration_files_exist.return_value = False

        with patch.object(LocalFilesystem, "directory_exists", return_value=True):
            # Act & Assert: Should raise error about missing configuration files
            with pytest.raises(VehicleProjectOpenError) as exc_info:
                project_opener._validate_existing_directory(vehicle_dir)

            assert "Invalid Vehicle Directory" in exc_info.value.title
            assert "vehicle_components.json" in exc_info.value.message
            assert "\\d\\d_*\\.param" in exc_info.value.message


class TestVehicleProjectOpenerIntegration:
    """Test integrated vehicle project opening workflows."""

    def test_user_can_open_different_types_of_vehicle_directories(self, project_opener, mock_local_filesystem) -> None:
        """
        User can open different types of vehicle directories successfully.

        GIVEN: A user has different types of vehicle directories available
        WHEN: They open each type of directory
        THEN: All should open successfully with proper configuration
        """
        # Arrange: Different vehicle directory types
        directories = [
            "/vehicles/my_quadcopter",
            "/projects/custom_plane",
            "/configs/racing_drone",
        ]

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir"):
            for vehicle_dir in directories:
                # Act: Open each directory
                result = project_opener.open_vehicle_directory(vehicle_dir)

                # Assert: Each directory opens successfully
                assert result == vehicle_dir
                assert mock_local_filesystem.vehicle_dir == vehicle_dir

    def test_user_workflow_from_last_directory_to_new_directory(self, project_opener, mock_local_filesystem) -> None:
        """
        User can successfully transition from opening last directory to opening new directory.

        GIVEN: A user first opens their last used directory
        WHEN: They then decide to open a different directory
        THEN: Both operations should succeed and update the filesystem accordingly
        """
        # Arrange: Last directory and new directory
        last_dir = "/vehicles/last_used"
        new_dir = "/vehicles/different_project"

        # Act: Open last directory first
        result1 = project_opener.open_last_vehicle_directory(last_dir)
        assert result1 == last_dir

        # Reset mock to track new calls
        mock_local_filesystem.re_init.reset_mock()

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir") as mock_store:
            # Act: Open new directory
            result2 = project_opener.open_vehicle_directory(new_dir)

            # Assert: New directory opened and stored
            assert result2 == new_dir
            assert mock_local_filesystem.vehicle_dir == new_dir
            mock_store.assert_called_once_with(new_dir)

    def test_error_recovery_workflow_after_failed_directory_opening(self, project_opener, mock_local_filesystem) -> None:
        """
        User can recover from failed directory opening and try again.

        GIVEN: A user attempts to open an invalid directory and gets an error
        WHEN: They then attempt to open a valid directory
        THEN: The second attempt should succeed despite the previous failure
        """
        # Arrange: Invalid directory followed by valid directory
        invalid_dir = "/path/to/invalid"
        valid_dir = "/path/to/valid"

        # First attempt should fail
        mock_local_filesystem.vehicle_configuration_files_exist.return_value = False

        with pytest.raises(VehicleProjectOpenError):
            project_opener.open_vehicle_directory(invalid_dir)

        # Second attempt should succeed
        mock_local_filesystem.vehicle_configuration_files_exist.return_value = True

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir"):
            result = project_opener.open_vehicle_directory(valid_dir)

            # Assert: Valid directory opened successfully
            assert result == valid_dir
            assert mock_local_filesystem.vehicle_dir == valid_dir

    def test_filesystem_state_consistency_across_multiple_operations(self, project_opener, mock_local_filesystem) -> None:
        """
        Filesystem state remains consistent across multiple directory operations.

        GIVEN: A user performs multiple directory opening operations
        WHEN: Each operation completes
        THEN: The filesystem state should be consistent and up-to-date
        """
        # Arrange: Multiple directories to open
        directories = [
            "/vehicles/project1",
            "/vehicles/project2",
            "/vehicles/project3",
        ]

        with patch.object(LocalFilesystem, "store_recently_used_vehicle_dir"):
            for i, vehicle_dir in enumerate(directories):
                # Act: Open directory
                result = project_opener.open_vehicle_directory(vehicle_dir)

                # Assert: Filesystem state is correct for current directory
                assert result == vehicle_dir
                assert mock_local_filesystem.vehicle_dir == vehicle_dir

                # Verify re_init was called with correct parameters
                expected_calls = i + 1
                assert mock_local_filesystem.re_init.call_count == expected_calls

                # Check the most recent call was with correct parameters
                last_call = mock_local_filesystem.re_init.call_args_list[-1]
                assert last_call[0] == (vehicle_dir, mock_local_filesystem.vehicle_type)
