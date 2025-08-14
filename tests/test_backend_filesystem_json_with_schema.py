#!/usr/bin/env python3

"""
Test the FilesystemJSONWithSchema class for JSON file operations with schema validation.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from typing import Any
from unittest.mock import mock_open, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema

# pylint: disable=too-few-public-methods


class TestFilesystemJSONWithSchemaInitialization:
    """Test FilesystemJSONWithSchema initialization and basic setup."""

    def test_user_can_create_instance_with_valid_filenames(self) -> None:
        """
        User can create a FilesystemJSONWithSchema instance with valid filenames.

        GIVEN: A user needs to manage JSON files with schema validation
        WHEN: They create a FilesystemJSONWithSchema instance with json and schema filenames
        THEN: The instance should be created with proper attributes initialized
        """
        # Arrange & Act: User creates instance with valid filenames
        json_manager = FilesystemJSONWithSchema("test.json", "test_schema.json")

        # Assert: Instance created with correct attributes
        assert json_manager.json_filename == "test.json"
        assert json_manager.schema_filename == "test_schema.json"
        assert json_manager.data is None
        assert json_manager.schema is None


class TestSchemaLoading:
    """Test schema loading functionality and validation."""

    @pytest.fixture
    def valid_schema_data(self) -> dict[str, Any]:
        """Fixture providing a valid JSON schema for testing."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "settings": {"type": "object", "properties": {"enabled": {"type": "boolean"}}},
            },
            "required": ["name", "version"],
        }

    @pytest.fixture
    def json_manager(self) -> FilesystemJSONWithSchema:
        """Fixture providing a FilesystemJSONWithSchema instance for testing."""
        return FilesystemJSONWithSchema("test.json", "test_schema.json")

    def test_user_can_load_valid_schema_successfully(self, json_manager, valid_schema_data) -> None:
        """
        User can load a valid JSON schema file successfully.

        GIVEN: A user has a FilesystemJSONWithSchema instance and a valid schema file exists
        WHEN: They call load_schema()
        THEN: The schema should be loaded and cached for future use
        """
        # Arrange: Mock file system to return valid schema
        schema_path = "/mock/path/test_schema.json"
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.dirname",
                return_value="/mock/path",
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join", return_value=schema_path
            ),
            patch("builtins.open", mock_open(read_data=json.dumps(valid_schema_data))),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_debug") as mock_debug,
        ):
            # Act: User loads the schema
            result = json_manager.load_schema()

            # Assert: Schema loaded successfully and cached
            assert result == valid_schema_data
            assert json_manager.schema == valid_schema_data
            mock_debug.assert_called_once()

    def test_user_sees_cached_schema_on_subsequent_loads(self, json_manager, valid_schema_data) -> None:
        """
        User gets cached schema on subsequent load_schema calls without file I/O.

        GIVEN: A user has already loaded a schema successfully
        WHEN: They call load_schema() again
        THEN: The cached schema should be returned without reading the file again
        """
        # Arrange: Pre-cache the schema
        json_manager.schema = valid_schema_data

        # Act: User calls load_schema again
        with patch("builtins.open") as mock_file:
            result = json_manager.load_schema()

            # Assert: Cached schema returned, no file operations
            assert result == valid_schema_data
            mock_file.assert_not_called()

    def test_user_handles_missing_schema_file_gracefully(self, json_manager) -> None:
        """
        User receives empty dict when schema file is missing.

        GIVEN: A user has a FilesystemJSONWithSchema instance but schema file doesn't exist
        WHEN: They call load_schema()
        THEN: An empty dict should be returned and error logged
        """
        # Arrange: Mock file system to raise FileNotFoundError
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.dirname",
                return_value="/mock/path",
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/mock/path/test_schema.json",
            ),
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to load missing schema
            result = json_manager.load_schema()

            # Assert: Empty dict returned and error logged
            assert result == {}
            assert json_manager.schema is None  # Schema is not cached when file is missing
            mock_error.assert_called_once()

    def test_user_handles_invalid_json_schema_gracefully(self, json_manager) -> None:
        """
        User receives empty dict when schema file contains invalid JSON.

        GIVEN: A user has a FilesystemJSONWithSchema instance but schema file has invalid JSON
        WHEN: They call load_schema()
        THEN: An empty dict should be returned and error logged
        """
        # Arrange: Mock file system to return invalid JSON
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.dirname",
                return_value="/mock/path",
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/mock/path/test_schema.json",
            ),
            patch("builtins.open", mock_open(read_data="invalid json {")),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to load invalid JSON schema
            result = json_manager.load_schema()

            # Assert: Empty dict returned and error logged
            assert result == {}
            mock_error.assert_called_once()

    def test_user_sees_warning_for_invalid_schema_structure(self, json_manager) -> None:
        """
        User sees error logged when schema doesn't conform to JSON Schema meta-schema.

        GIVEN: A user has a schema file with invalid JSON Schema structure
        WHEN: They call load_schema()
        THEN: The schema should still load but an error should be logged about invalid structure
        """
        # Arrange: Invalid schema structure that will definitely fail meta-schema validation
        invalid_schema = {"type": "invalid_type_name"}  # 'invalid_type_name' is not a valid JSON Schema type
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.dirname",
                return_value="/mock/path",
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/mock/path/test_schema.json",
            ),
            patch("builtins.open", mock_open(read_data=json.dumps(invalid_schema))),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_debug"),
        ):
            # Act: User loads schema with invalid structure
            result = json_manager.load_schema()

            # Assert: Schema loaded but error logged about invalid structure
            assert result == invalid_schema
            assert json_manager.schema == invalid_schema
            # The implementation logs an error when the schema doesn't validate against meta-schema
            mock_error.assert_called_once()


class TestDataValidation:
    """Test JSON data validation against schema."""

    @pytest.fixture
    def json_manager_with_schema(self) -> FilesystemJSONWithSchema:
        """Fixture providing a FilesystemJSONWithSchema instance with pre-loaded schema."""
        manager = FilesystemJSONWithSchema("test.json", "test_schema.json")
        manager.schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"name": {"type": "string"}, "version": {"type": "string"}, "enabled": {"type": "boolean"}},
            "required": ["name", "version"],
        }
        return manager

    def test_user_can_validate_correct_data_successfully(self, json_manager_with_schema) -> None:
        """
        User can validate JSON data that conforms to the schema.

        GIVEN: A user has valid JSON data that matches the loaded schema
        WHEN: They call validate_json_against_schema()
        THEN: The validation should pass with no error message
        """
        # Arrange: Valid data matching schema
        valid_data = {"name": "Test Application", "version": "1.0.0", "enabled": True}

        # Act: User validates correct data
        is_valid, error_message = json_manager_with_schema.validate_json_against_schema(valid_data)

        # Assert: Validation passes
        assert is_valid is True
        assert error_message == ""

    def test_user_sees_validation_errors_for_invalid_data(self, json_manager_with_schema) -> None:
        """
        User receives detailed error messages for data that doesn't match schema.

        GIVEN: A user has JSON data that violates the schema requirements
        WHEN: They call validate_json_against_schema()
        THEN: The validation should fail with a descriptive error message
        """
        # Arrange: Invalid data missing required field
        invalid_data = {
            "name": "Test Application"
            # Missing required "version" field
        }

        # Act: User validates invalid data
        is_valid, error_message = json_manager_with_schema.validate_json_against_schema(invalid_data)

        # Assert: Validation fails with descriptive error
        assert is_valid is False
        assert "Validation error" in error_message
        assert len(error_message) > 0

    def test_user_handles_validation_without_schema_gracefully(self) -> None:
        """
        User receives appropriate error when trying to validate without a loaded schema.

        GIVEN: A user has a FilesystemJSONWithSchema instance with no schema loaded
        WHEN: They call validate_json_against_schema()
        THEN: The validation should fail with a schema loading error message
        """
        # Arrange: Manager without schema
        json_manager = FilesystemJSONWithSchema("test.json", "test_schema.json")
        test_data = {"name": "test"}

        with patch.object(json_manager, "load_schema", return_value={}):
            # Act: User attempts validation without schema
            is_valid, error_message = json_manager.validate_json_against_schema(test_data)

            # Assert: Validation fails due to missing schema
            assert is_valid is False
            assert "Could not load validation schema" in error_message


class TestJSONDataLoading:
    """Test JSON data file loading functionality."""

    @pytest.fixture
    def json_manager_with_schema(self) -> FilesystemJSONWithSchema:
        """Fixture providing a FilesystemJSONWithSchema instance with schema for validation."""
        manager = FilesystemJSONWithSchema("config.json", "schema.json")
        manager.schema = {"type": "object", "properties": {"name": {"type": "string"}, "settings": {"type": "object"}}}
        return manager

    def test_user_can_load_valid_json_data_successfully(self, json_manager_with_schema) -> None:
        """
        User can load valid JSON data file that passes schema validation.

        GIVEN: A user has a valid JSON data file that conforms to the schema
        WHEN: They call load_json_data() with the directory path
        THEN: The data should be loaded, validated, and cached
        """
        # Arrange: Valid JSON data
        valid_data = {"name": "Test Config", "settings": {"debug": True}}
        data_dir = "/test/directory"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/config.json",
            ),
            patch("builtins.open", mock_open(read_data=json.dumps(valid_data))),
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
        ):
            # Act: User loads JSON data
            result = json_manager_with_schema.load_json_data(data_dir)

            # Assert: Data loaded and cached successfully
            assert result == valid_data
            assert json_manager_with_schema.data == valid_data

    def test_user_loads_invalid_data_with_warning_logged(self, json_manager_with_schema) -> None:
        """
        User can load JSON data that fails schema validation but receives warning.

        GIVEN: A user has a JSON data file that doesn't conform to the schema
        WHEN: They call load_json_data()
        THEN: The data should still be loaded for debugging but validation error logged
        """
        # Arrange: Invalid data that fails schema validation
        invalid_data = {"name": 123}  # Name should be string, not number
        data_dir = "/test/directory"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/config.json",
            ),
            patch("builtins.open", mock_open(read_data=json.dumps(invalid_data))),
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(False, "Type error")),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User loads invalid JSON data
            result = json_manager_with_schema.load_json_data(data_dir)

            # Assert: Data loaded but error logged
            assert result == invalid_data
            assert json_manager_with_schema.data == invalid_data
            mock_error.assert_called_once()

    def test_user_handles_missing_json_file_gracefully(self, json_manager_with_schema) -> None:
        """
        User receives empty dict when JSON data file doesn't exist.

        GIVEN: A user tries to load data from a directory without the JSON file
        WHEN: They call load_json_data()
        THEN: An empty dict should be returned and debug message logged
        """
        # Arrange: Directory without the JSON file
        data_dir = "/test/directory"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/config.json",
            ),
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_debug") as mock_debug,
        ):
            # Act: User attempts to load from missing file
            result = json_manager_with_schema.load_json_data(data_dir)

            # Assert: Empty dict returned and debug logged
            assert result == {}
            assert json_manager_with_schema.data == {}
            mock_debug.assert_called_once()

    def test_user_handles_corrupted_json_file_gracefully(self, json_manager_with_schema) -> None:
        """
        User receives empty dict when JSON file contains invalid JSON syntax.

        GIVEN: A user has a JSON file with corrupted/invalid JSON syntax
        WHEN: They call load_json_data()
        THEN: An empty dict should be returned and error logged
        """
        # Arrange: Corrupted JSON file
        data_dir = "/test/directory"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/config.json",
            ),
            patch("builtins.open", mock_open(read_data="{ invalid json syntax")),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to load corrupted JSON
            result = json_manager_with_schema.load_json_data(data_dir)

            # Assert: Empty dict returned and error logged
            assert result == {}
            assert json_manager_with_schema.data == {}
            mock_error.assert_called_once()


class TestJSONDataSaving:
    """Test JSON data file saving functionality and error handling."""

    @pytest.fixture
    def json_manager_with_schema(self) -> FilesystemJSONWithSchema:
        """Fixture providing a FilesystemJSONWithSchema instance with schema for validation."""
        manager = FilesystemJSONWithSchema("output.json", "schema.json")
        manager.schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "count": {"type": "integer"}},
            "required": ["name"],
        }
        return manager

    def test_user_can_save_valid_data_successfully(self, json_manager_with_schema) -> None:
        """
        User can save valid JSON data that passes schema validation.

        GIVEN: A user has valid data that conforms to the schema
        WHEN: They call save_json_data() with the data and directory
        THEN: The data should be validated and saved successfully
        """
        # Arrange: Valid data and directory
        valid_data = {"name": "Test Output", "count": 42}
        data_dir = "/output/directory"

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/output/directory/output.json",
            ),
            patch("builtins.open", mock_open()) as mock_file,
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.json_dumps",
                return_value='{"name": "Test Output", "count": 42}',
            ) as mock_dumps,
        ):
            # Act: User saves valid data
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: Data saved successfully
            assert error_occurred is False
            assert error_message == ""
            mock_file.assert_called_once_with("/output/directory/output.json", "w", encoding="utf-8", newline="\n")
            mock_dumps.assert_called_once_with(valid_data, indent=4)

    def test_user_cannot_save_invalid_data(self, json_manager_with_schema) -> None:
        """
        User receives error when trying to save data that fails schema validation.

        GIVEN: A user has data that doesn't conform to the schema
        WHEN: They call save_json_data()
        THEN: The save should fail with validation error and no file operations
        """
        # Arrange: Invalid data missing required field
        invalid_data = {"count": 42}  # Missing required "name" field
        data_dir = "/output/directory"

        with (
            patch.object(
                json_manager_with_schema, "validate_json_against_schema", return_value=(False, "Missing required field")
            ),
            patch("builtins.open") as mock_file,
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to save invalid data
            error_occurred, error_message = json_manager_with_schema.save_json_data(invalid_data, data_dir)

            # Assert: Save fails with validation error
            assert error_occurred is True
            assert "Cannot save invalid JSON data" in error_message
            assert "Missing required field" in error_message
            mock_file.assert_not_called()
            mock_error.assert_called_once()

    def test_user_handles_missing_directory_error(self, json_manager_with_schema) -> None:
        """
        User receives appropriate error when target directory doesn't exist.

        GIVEN: A user tries to save data to a non-existent directory
        WHEN: They call save_json_data()
        THEN: A FileNotFoundError should be handled with descriptive message
        """
        # Arrange: Valid data but non-existent directory
        valid_data = {"name": "Test"}
        data_dir = "/nonexistent/directory"

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/nonexistent/directory/output.json",
            ),
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to save to missing directory
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: Appropriate error returned
            assert error_occurred is True
            assert "Directory '/nonexistent/directory' not found" in error_message
            mock_error.assert_called_once()

    def test_user_handles_permission_denied_error(self, json_manager_with_schema) -> None:
        """
        User receives appropriate error when lacking write permissions.

        GIVEN: A user tries to save data to a directory without write permissions
        WHEN: They call save_json_data()
        THEN: A PermissionError should be handled with descriptive message
        """
        # Arrange: Valid data but no write permissions
        valid_data = {"name": "Test"}
        data_dir = "/protected/directory"

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/protected/directory/output.json",
            ),
            patch("builtins.open", side_effect=PermissionError),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to save without permissions
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: Permission error handled appropriately
            assert error_occurred is True
            assert "Permission denied when writing to file" in error_message
            mock_error.assert_called_once()

    def test_user_handles_directory_instead_of_file_error(self, json_manager_with_schema) -> None:
        """
        User receives appropriate error when target path is a directory.

        GIVEN: A user tries to save to a path that is a directory, not a file
        WHEN: They call save_json_data()
        THEN: An IsADirectoryError should be handled with descriptive message
        """
        # Arrange: Target path is a directory
        valid_data = {"name": "Test"}
        data_dir = "/test/directory"

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/output.json",
            ),
            patch("builtins.open", side_effect=IsADirectoryError),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to save to directory path
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: Directory error handled appropriately
            assert error_occurred is True
            assert "is a directory, not a file" in error_message
            mock_error.assert_called_once()

    def test_user_handles_os_error_gracefully(self, json_manager_with_schema) -> None:
        """
        User receives appropriate error for general OS-level errors.

        GIVEN: A user encounters an OS-level error during file operations
        WHEN: They call save_json_data()
        THEN: The OSError should be handled with descriptive message
        """
        # Arrange: OS error during file operations
        valid_data = {"name": "Test"}
        data_dir = "/test/directory"
        os_error = OSError("Disk full")

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/output.json",
            ),
            patch("builtins.open", side_effect=os_error),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User encounters OS error
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: OS error handled appropriately
            assert error_occurred is True
            assert "OS error when writing to file" in error_message
            assert "Disk full" in error_message
            mock_error.assert_called_once()

    def test_user_handles_json_serialization_errors(self, json_manager_with_schema) -> None:
        """
        User receives appropriate error when data cannot be serialized to JSON.

        GIVEN: A user tries to save data that cannot be JSON serialized
        WHEN: They call save_json_data()
        THEN: Serialization errors should be handled with descriptive messages
        """
        # Arrange: Data that causes JSON serialization error
        valid_data = {"name": "Test"}
        data_dir = "/test/directory"

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/output.json",
            ),
            patch("builtins.open", mock_open()),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.json_dumps",
                side_effect=TypeError("Object not serializable"),
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to save non-serializable data
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: Serialization error handled appropriately
            assert error_occurred is True
            assert "Type error when serializing data to JSON" in error_message
            mock_error.assert_called_once()

    def test_user_handles_json_value_errors(self, json_manager_with_schema) -> None:
        """
        User receives appropriate error when JSON serialization raises ValueError.

        GIVEN: A user tries to save data that causes JSON serialization ValueError
        WHEN: They call save_json_data()
        THEN: ValueError should be handled with descriptive message
        """
        # Arrange: Data that causes JSON serialization ValueError
        valid_data = {"name": "Test"}
        data_dir = "/test/directory"

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/output.json",
            ),
            patch("builtins.open", mock_open()),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.json_dumps",
                side_effect=ValueError("Circular reference in data"),
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User attempts to save data causing ValueError
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: ValueError handled appropriately
            assert error_occurred is True
            assert "Value error when serializing data to JSON" in error_message
            assert "Circular reference in data" in error_message
            mock_error.assert_called_once()

    def test_user_handles_unexpected_errors_gracefully(self, json_manager_with_schema) -> None:
        """
        User receives appropriate error for unexpected exceptions.

        GIVEN: A user encounters an unexpected error during save operations
        WHEN: They call save_json_data()
        THEN: The unexpected error should be caught and handled gracefully
        """
        # Arrange: Unexpected error
        valid_data = {"name": "Test"}
        data_dir = "/test/directory"
        unexpected_error = RuntimeError("Unexpected error")

        with (
            patch.object(json_manager_with_schema, "validate_json_against_schema", return_value=(True, "")),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                return_value="/test/directory/output.json",
            ),
            patch("builtins.open", side_effect=unexpected_error),
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error") as mock_error,
        ):
            # Act: User encounters unexpected error
            error_occurred, error_message = json_manager_with_schema.save_json_data(valid_data, data_dir)

            # Assert: Unexpected error handled gracefully
            assert error_occurred is True
            assert "Unexpected error saving data to file" in error_message
            assert "Unexpected error" in error_message
            mock_error.assert_called_once()


class TestFilesystemJSONWithSchemaIntegration:
    """Test complete workflows and integration scenarios."""

    def test_user_completes_full_workflow_successfully(self) -> None:
        """
        User can complete a full workflow of loading schema, validating, and saving data.

        GIVEN: A user needs to manage JSON configuration with schema validation
        WHEN: They perform the complete workflow of schema loading, data validation, and saving
        THEN: All operations should work together seamlessly
        """
        # Arrange: Set up complete workflow scenario
        schema_data = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"app_name": {"type": "string"}, "version": {"type": "number"}},
            "required": ["app_name"],
        }
        config_data = {"app_name": "Test App", "version": 1.5}

        json_manager = FilesystemJSONWithSchema("config.json", "config_schema.json")

        with (
            # Mock schema loading
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.dirname", return_value="/app"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.os_path.join",
                side_effect=lambda *args: "/".join(args),
            ),
            patch(
                "builtins.open",
                side_effect=[
                    mock_open(read_data=json.dumps(schema_data)).return_value,  # Schema file
                    mock_open().return_value,  # Data file for saving
                ],
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.json_dumps",
                return_value='{"app_name": "Test App", "version": 1.5}',
            ) as mock_dumps,
            patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_debug"),
        ):
            # Act: User performs complete workflow
            # 1. Load schema
            loaded_schema = json_manager.load_schema()

            # 2. Validate data
            is_valid, error_msg = json_manager.validate_json_against_schema(config_data)

            # 3. Save data
            error_occurred, save_error_msg = json_manager.save_json_data(config_data, "/config/dir")

            # Assert: Complete workflow successful
            assert loaded_schema == schema_data
            assert is_valid is True
            assert error_msg == ""
            assert error_occurred is False
            assert save_error_msg == ""
            mock_dumps.assert_called_once_with(config_data, indent=4)

    def test_user_workflow_fails_gracefully_on_invalid_data(self) -> None:
        """
        User workflow fails gracefully when data doesn't match schema.

        GIVEN: A user has valid schema but invalid data
        WHEN: They attempt the validation and save workflow
        THEN: The workflow should fail at validation with clear error messages
        """
        # Arrange: Valid schema but invalid data
        schema_data = {"type": "object", "properties": {"required_field": {"type": "string"}}, "required": ["required_field"]}
        invalid_data = {"wrong_field": "value"}

        json_manager = FilesystemJSONWithSchema("config.json", "schema.json")
        json_manager.schema = schema_data

        # Act: User attempts workflow with invalid data
        is_valid, validation_error = json_manager.validate_json_against_schema(invalid_data)

        with patch("ardupilot_methodic_configurator.backend_filesystem_json_with_schema.logging_error"):
            error_occurred, save_error = json_manager.save_json_data(invalid_data, "/config/dir")

        # Assert: Workflow fails gracefully with clear errors
        assert is_valid is False
        assert "Validation error" in validation_error
        assert error_occurred is True
        assert "Cannot save invalid JSON data" in save_error
