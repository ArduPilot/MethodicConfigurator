#!/usr/bin/env python3

"""
BDD-style tests for the backend_filesystem_program_settings.py file.

This file is part of ArduPilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import platform
from os import path as os_path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings

# pylint: disable=too-many-lines,protected-access,redefined-outer-name,too-few-public-methods


@pytest.fixture
def mock_file_operations() -> MagicMock:
    """Fixture providing mocked filesystem operations for path testing."""
    mock_ops = MagicMock()
    mock_ops.dirname.return_value = "/mock/app/dir"
    mock_ops.abspath.return_value = "/mock/app/dir/file"
    mock_ops.join.return_value = "/mock/app/dir/images/file.png"
    return mock_ops


@pytest.fixture
def mock_user_config() -> dict[str, str]:
    """Fixture providing mock user configuration directory paths."""
    return {
        "config_dir": "/mock/user/config",
        "settings_file": "/mock/user/config/settings.json",
    }


@pytest.fixture
def sample_program_settings() -> dict:
    """Fixture providing realistic program settings data for testing."""
    return {
        "Format version": 1,
        "directory_selection": {"template_dir": "/mock/template"},
        "display_usage_popup": {"component_editor": False, "parameter_editor": True},
        "auto_open_doc_in_browser": False,
        "motor_test_duration": 5.0,
        "motor_test_throttle_pct": 10,
    }


class TestApplicationResourcePaths:
    """Test user access to application resource file paths."""

    def test_user_can_get_application_icon_filepath(self, mock_file_operations) -> None:
        """
        User can retrieve the application icon filepath for GUI display.

        GIVEN: A user needs to display the application icon in the GUI
        WHEN: User requests the application icon filepath
        THEN: The correct path to ArduPilot_icon.png should be returned
        AND: The path should be properly constructed relative to application directory
        """
        # Arrange: Configure mock file operations
        with (
            patch("os.path.dirname", mock_file_operations.dirname),
            patch("os.path.abspath", mock_file_operations.abspath),
            patch("os.path.join") as mock_join,
        ):
            mock_join.return_value = "/mock/app/dir/images/ArduPilot_icon.png"

            # Act: Get application icon filepath
            result = ProgramSettings.application_icon_filepath()

            # Assert: Correct filepath is constructed and returned
            mock_file_operations.dirname.assert_called_once()
            # abspath might be called multiple times during import, so we check it was called
            assert mock_file_operations.abspath.called
            # Verify the correct arguments for join
            mock_join.assert_called_once_with("/mock/app/dir", "images", "ArduPilot_icon.png")
            assert result == "/mock/app/dir/images/ArduPilot_icon.png"

    def test_user_can_get_application_logo_filepath(self, mock_file_operations) -> None:
        """
        User can retrieve the application logo filepath for display in dialogs.

        GIVEN: A user needs to display the application logo in about dialog
        WHEN: User requests the application logo filepath
        THEN: The correct path to ArduPilot_logo.png should be returned
        AND: The path should be properly constructed relative to application directory
        """
        # Arrange: Configure mock file operations
        with (
            patch("os.path.dirname", mock_file_operations.dirname),
            patch("os.path.abspath", mock_file_operations.abspath),
            patch("os.path.join") as mock_join,
        ):
            mock_join.return_value = "/mock/app/dir/images/ArduPilot_logo.png"

            # Act: Get application logo filepath
            result = ProgramSettings.application_logo_filepath()

            # Assert: Correct filepath is constructed and returned
            mock_file_operations.dirname.assert_called_once()
            mock_file_operations.abspath.assert_called_once()
            mock_join.assert_called_once_with("/mock/app/dir", "images", "ArduPilot_logo.png")
            assert result == "/mock/app/dir/images/ArduPilot_logo.png"


class TestDirectoryManagement:
    """Test user directory creation and validation workflows."""

    def test_user_can_create_program_settings_instance(self) -> None:
        """
        User can instantiate ProgramSettings class for configuration management.

        GIVEN: A user needs to work with program settings
        WHEN: User creates a ProgramSettings instance
        THEN: The instance should be created successfully
        AND: Should be ready for configuration operations
        """
        # Arrange & Act: Create ProgramSettings instance
        settings = ProgramSettings()

        # Assert: Instance created successfully
        assert settings is not None
        assert isinstance(settings, ProgramSettings)

    def test_user_successfully_creates_new_vehicle_directory(self) -> None:
        """
        User can successfully create a new vehicle directory when path is available.

        GIVEN: A user wants to create a new vehicle directory
        WHEN: The target directory path does not exist and creation succeeds
        THEN: Directory should be created successfully
        AND: Empty string should be returned indicating success
        """
        # Arrange: Mock successful directory creation
        with (
            patch("os.path.exists", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_makedirs") as mock_makedirs,
        ):
            # Act: Create new vehicle directory
            result = ProgramSettings.create_new_vehicle_dir("/mock/new/vehicle/dir")

            # Assert: Directory created and success indicated
            mock_makedirs.assert_called_once_with("/mock/new/vehicle/dir", exist_ok=True)
            assert result == ""

    def test_user_gets_error_when_creating_existing_directory(self) -> None:
        """
        User receives error message when trying to create directory that already exists.

        GIVEN: A user attempts to create a new vehicle directory
        WHEN: The target directory already exists on the filesystem
        THEN: An error message should be returned instead of creating the directory
        """
        # Arrange: Mock directory already exists
        with patch("os.path.exists", return_value=True):
            # Act: Attempt to create existing directory
            result = ProgramSettings.create_new_vehicle_dir("/mock/existing/dir")

            # Assert: Error message is returned
            assert result != ""
            assert isinstance(result, str)

    def test_user_gets_error_when_directory_creation_fails(self) -> None:
        """
        User receives informative error when directory creation fails due to system error.

        GIVEN: A user attempts to create a new vehicle directory
        WHEN: Directory creation fails due to filesystem error (permissions, disk space, etc.)
        THEN: An error message containing the system error should be returned
        AND: The error should be logged for troubleshooting
        """
        # Arrange: Mock directory creation failure
        with (
            patch("os.path.exists", return_value=False),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_makedirs",
                side_effect=OSError("Permission denied"),
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_error") as mock_log_error,
        ):
            # Act: Attempt to create directory
            result = ProgramSettings.create_new_vehicle_dir("/mock/protected/dir")

            # Assert: Error is logged and message contains error details
            mock_log_error.assert_called_once()
            assert "Permission denied" in result

    def test_user_can_validate_directory_names_correctly(self) -> None:
        """
        User receives correct validation results for various directory name formats.

        GIVEN: A user needs to validate potential directory names
        WHEN: User checks various directory name formats
        THEN: Validation should correctly identify valid and invalid names
        AND: Platform-specific path separators should be handled appropriately
        """
        # Arrange & Act & Assert: Test various directory name patterns

        # Valid names should pass validation
        assert ProgramSettings.valid_directory_name("valid_dir_name-123") is True
        assert ProgramSettings.valid_directory_name("valid_dir_name") is True

        # Platform-specific path separators
        forward_slash_valid = ProgramSettings.valid_directory_name("valid_dir_name/")
        assert forward_slash_valid is (platform.system() != "Windows")

        backward_slash_valid = ProgramSettings.valid_directory_name("valid_dir_name\\")
        assert backward_slash_valid is (platform.system() == "Windows")

        # Invalid characters should fail validation
        assert ProgramSettings.valid_directory_name("invalid<dir>name") is False
        assert ProgramSettings.valid_directory_name("invalid*dir?name") is False


class TestUserConfigurationAccess:
    """Test user configuration directory access and settings management."""

    def test_user_can_access_existing_config_directory(self, mock_user_config) -> None:
        """
        User can successfully access their configuration directory when it exists.

        GIVEN: A user has a valid configuration directory on their system
        WHEN: User attempts to access their configuration settings
        THEN: The correct configuration directory path should be returned
        """
        # Arrange: Mock existing configuration directory
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.user_config_dir",
                return_value=mock_user_config["config_dir"],
            ),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            # Act: Access user configuration directory
            result = ProgramSettings._user_config_dir()

            # Assert: Correct directory path is returned
            assert result == mock_user_config["config_dir"]

    def test_user_gets_error_when_config_directory_missing(self) -> None:
        """
        User receives appropriate error when configuration directory doesn't exist.

        GIVEN: A user's configuration directory has been deleted or moved
        WHEN: User attempts to access their configuration settings
        THEN: A FileNotFoundError should be raised with helpful information
        """
        # Arrange: Mock missing configuration directory
        with (
            patch("platformdirs.user_config_dir", return_value="/missing/config"),
            patch("os.path.exists", return_value=False),
            pytest.raises(FileNotFoundError),
        ):
            # Act: Attempt to access missing configuration directory
            ProgramSettings._user_config_dir()

    def test_user_gets_error_when_config_path_is_not_directory(self) -> None:
        """
        User receives appropriate error when config path exists but is not a directory.

        GIVEN: A user's configuration path exists but is a file instead of directory
        WHEN: User attempts to access their configuration settings
        THEN: A NotADirectoryError should be raised
        """
        # Arrange: Mock configuration path as file instead of directory
        with (
            patch("platformdirs.user_config_dir", return_value="/path/to/file"),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
            pytest.raises(NotADirectoryError),
        ):
            # Act: Attempt to access configuration file as directory
            ProgramSettings._user_config_dir()

    def test_user_can_access_site_config_directory(self) -> None:
        """
        User can successfully access the site configuration directory when it exists.

        GIVEN: A user needs to access site-wide configuration templates
        WHEN: User attempts to access the site configuration directory
        THEN: The correct site configuration directory path should be returned
        """
        # Arrange: Mock existing site configuration directory
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.site_config_dir",
                return_value="/site/config/dir",
            ),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            # Act: Access site configuration directory
            result = ProgramSettings._site_config_dir()

            # Assert: Correct directory path is returned
            assert result == "/site/config/dir"

    def test_user_gets_error_when_site_config_directory_missing(self) -> None:
        """
        User receives appropriate error when site configuration directory doesn't exist.

        GIVEN: A user's site configuration directory has been deleted or corrupted
        WHEN: User attempts to access site configuration
        THEN: A FileNotFoundError should be raised with helpful information
        """
        # Arrange: Mock missing site configuration directory
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.site_config_dir",
                return_value="/missing/site/config",
            ),
            patch("os.path.exists", return_value=False),
            pytest.raises(FileNotFoundError, match="site configuration directory.*does not exist"),
        ):
            # Act: Attempt to access missing site configuration directory
            ProgramSettings._site_config_dir()

    def test_user_gets_error_when_site_config_path_is_not_directory(self) -> None:
        """
        User receives appropriate error when site config path exists but is not a directory.

        GIVEN: A user's site configuration path exists but is a file instead of directory
        WHEN: User attempts to access site configuration
        THEN: A NotADirectoryError should be raised
        """
        # Arrange: Mock site configuration path as file instead of directory
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.site_config_dir",
                return_value="/path/to/site/config/file",
            ),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
            pytest.raises(NotADirectoryError, match="path.*is not a directory"),
        ):
            # Act: Attempt to access site configuration file as directory
            ProgramSettings._site_config_dir()


class TestSettingsFileOperations:
    """Test user settings file reading and writing operations."""

    def test_user_can_load_existing_settings_file(self, mock_user_config, sample_program_settings) -> None:
        """
        User can successfully load their existing settings from configuration file.

        GIVEN: A user has a valid settings file with saved preferences
        WHEN: User starts the application and settings are loaded
        THEN: All saved settings should be loaded correctly
        AND: Any missing default settings should be added automatically
        """
        # Arrange: Mock existing settings file with realistic data
        expected_result = sample_program_settings.copy()
        # Add all missing defaults that would be added by _recursive_merge_defaults
        expected_result["annotate_docs_into_param_files"] = False  # Added by default
        expected_result["gui_complexity"] = "simple"  # Added by default

        # Update directory_selection with the defaults that would be merged in
        expected_result["directory_selection"]["new_base_dir"] = os_path.join(mock_user_config["config_dir"], "vehicles")
        expected_result["directory_selection"]["vehicle_dir"] = os_path.join(mock_user_config["config_dir"], "vehicles")

        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value=mock_user_config["config_dir"]),
            patch.object(ProgramSettings, "get_templates_base_dir", return_value="/app/templates"),
            patch("builtins.open", mock_open(read_data=json.dumps(sample_program_settings))),
        ):
            # Act: Load settings from file
            result = ProgramSettings._get_settings_as_dict()

            # Assert: All settings loaded correctly with defaults added
            assert result == expected_result

    def test_user_gets_default_settings_when_file_missing(self, mock_user_config) -> None:
        """
        User receives sensible default settings when configuration file doesn't exist.

        GIVEN: A user starts the application for the first time (no settings file)
        WHEN: Settings are loaded from a non-existent file
        THEN: Complete default configuration should be provided
        AND: All required settings sections should be present
        """
        # Arrange: Mock missing settings file
        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value=mock_user_config["config_dir"]),
            patch("os.path.join", return_value=mock_user_config["settings_file"]),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            # Act: Load settings from missing file
            result = ProgramSettings._get_settings_as_dict()

            # Assert: All required default settings are present
            assert "Format version" in result
            assert "directory_selection" in result
            assert "display_usage_popup" in result
            assert "component_editor" in result["display_usage_popup"]
            assert "parameter_editor" in result["display_usage_popup"]
            assert "auto_open_doc_in_browser" in result
            assert "annotate_docs_into_param_files" in result

    def test_user_gets_default_popup_settings_when_missing(self, mock_user_config) -> None:
        """
        User gets default popup settings when display_usage_popup section is incomplete.

        GIVEN: A user has settings file missing specific popup setting keys
        WHEN: User loads their settings
        THEN: Missing popup settings should be initialized with defaults
        AND: Each popup type should get appropriate default values
        """
        # Arrange: Mock settings file missing popup settings details
        incomplete_settings = {
            "Format version": 1,
            "display_usage_popup": {},  # Empty popup settings
        }

        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value=mock_user_config["config_dir"]),
            patch("os.path.join", return_value=mock_user_config["settings_file"]),
            patch("builtins.open", mock_open(read_data=json.dumps(incomplete_settings))),
        ):
            # Act: Load settings with missing popup details
            result = ProgramSettings._get_settings_as_dict()

            # Assert: Popup settings initialized with defaults
            assert result["display_usage_popup"]["component_editor"] is True
            assert result["display_usage_popup"]["parameter_editor"] is True

    def test_user_can_load_settings_from_file_directly(self, mock_user_config) -> None:  # pylint: disable=unused-argument
        """
        User can load settings from file using the file loading method.

        GIVEN: A user has a settings file with specific content
        WHEN: Settings are loaded directly from the file
        THEN: The exact file content should be returned
        """
        # Arrange: Mock settings file content
        file_content = {"test_setting": "test_value"}

        with patch("builtins.open", mock_open(read_data=json.dumps(file_content))):
            # Act: Load settings from file
            result = ProgramSettings._load_settings_from_file("/mock/settings.json")

            # Assert: File content loaded correctly
            assert result == file_content

    def test_user_gets_empty_dict_when_file_missing_during_direct_load(self) -> None:
        """
        User gets empty dictionary when loading settings from missing file.

        GIVEN: A user attempts to load settings from a non-existent file
        WHEN: The direct file loading method is called
        THEN: An empty dictionary should be returned
        """
        # Arrange: Mock missing file
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            # Act: Load settings from missing file
            result = ProgramSettings._load_settings_from_file("/missing/settings.json")

            # Assert: Empty dictionary returned
            assert result == {}

    def test_user_can_apply_default_settings_to_incomplete_settings(self) -> None:
        """
        User can apply default settings to an incomplete settings dictionary.

        GIVEN: A user has a partial settings dictionary missing required keys
        WHEN: Default settings are applied
        THEN: All missing keys should be added with appropriate defaults
        """
        # Arrange: Incomplete settings missing various keys and mock defaults
        incomplete_settings = {"existing_key": "existing_value"}

        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value="/mock/config"),
            patch.object(ProgramSettings, "get_templates_base_dir", return_value="/app/templates"),
        ):
            # Get the defaults from the actual method
            defaults = ProgramSettings._get_settings_defaults()

            # Act: Apply default settings using recursive merge
            result = ProgramSettings._recursive_merge_defaults(incomplete_settings, defaults)

            # Assert: All defaults added while preserving existing
            assert result["existing_key"] == "existing_value"  # Preserved
            assert result["Format version"] == 1  # Added
            assert "directory_selection" in result  # Added
            assert "display_usage_popup" in result  # Added
            assert result["display_usage_popup"]["component_editor"] is True  # Added
            assert result["display_usage_popup"]["parameter_editor"] is True  # Added
            assert result["auto_open_doc_in_browser"] is True  # Added
            assert result["annotate_docs_into_param_files"] is False  # Added

    def test_user_can_normalize_path_separators_for_platform(self) -> None:
        """
        User can normalize path separators to match the current platform.

        GIVEN: A user has file paths with mixed or incorrect separators
        WHEN: Path normalization is applied
        THEN: Separators should be corrected for the current platform
        """
        # Act & Assert: Test path normalization based on platform
        if platform.system() == "Windows":
            # Windows should use backslashes
            assert ProgramSettings._normalize_path_separators("C:/path/to/file") == "C:\\path\\to\\file"
            assert ProgramSettings._normalize_path_separators("C:\\path\\to\\file") == "C:\\path\\to\\file"
        else:
            # Unix-like should use forward slashes
            assert ProgramSettings._normalize_path_separators("C:\\path\\to\\file") == "C:/path/to/file"
            assert ProgramSettings._normalize_path_separators("C:/path/to/file") == "C:/path/to/file"

    def test_user_can_save_settings_to_file(self, mock_user_config) -> None:
        """
        User can successfully save their current settings to configuration file.

        GIVEN: A user has modified their application settings
        WHEN: Settings need to be persisted to disk
        THEN: Settings should be written to the configuration file in JSON format
        AND: File should be created with proper encoding
        """
        # Arrange: Mock settings data and file operations
        mock_settings = {"test_setting": "test_value"}

        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value=mock_user_config["config_dir"]),
            patch("os.path.join", return_value=mock_user_config["settings_file"]),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Act: Save settings to file
            ProgramSettings._set_settings_from_dict(mock_settings)

            # Assert: File is opened correctly and data is written
            mock_file.assert_called_once_with(mock_user_config["settings_file"], "w", encoding="utf-8")
            mock_file().write.assert_called()


class TestUsagePopupSettings:
    """Test user interface popup display preferences management."""

    def test_user_can_get_usage_popup_display_preferences(self) -> None:
        """
        User can check their preferences for displaying usage popup windows.

        GIVEN: A user has configured their popup display preferences
        WHEN: User interface needs to decide whether to show popup help
        THEN: Correct preference should be returned for each popup type
        AND: Unknown popup types should default to showing help
        """
        # Arrange: Mock user preferences for popup display
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {"display_usage_popup": {"component_editor": False, "parameter_editor": True}}

            # Act & Assert: Check specific popup preferences
            assert ProgramSettings.display_usage_popup("component_editor") is False
            assert ProgramSettings.display_usage_popup("parameter_editor") is True
            assert ProgramSettings.display_usage_popup("nonexistent_type") is True  # Default behavior

    def test_user_can_set_usage_popup_display_preferences(self) -> None:
        """
        User can modify their preferences for displaying usage popup windows.

        GIVEN: A user wants to change popup display preferences
        WHEN: User sets a preference for a specific popup type
        THEN: The setting should be saved with the new preference
        AND: Invalid popup types should be ignored for safety
        """
        # Arrange: Mock current settings and save functionality
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {"display_usage_popup": {"component_editor": True, "parameter_editor": True}}

            # Act: Set valid popup preference
            ProgramSettings.set_display_usage_popup("component_editor", value=False)

            # Assert: Settings are updated correctly
            mock_set_settings.assert_called_with(
                {"display_usage_popup": {"component_editor": False, "parameter_editor": True}}
            )

            # Act: Try to set invalid popup type
            mock_set_settings.reset_mock()
            ProgramSettings.set_display_usage_popup("nonexistent_type", value=False)

            # Assert: Invalid types are ignored
            mock_set_settings.assert_not_called()


class TestGenericSettingsAccess:
    """Test access to general settings in ProgramSettings."""

    def test_user_can_read_existing_settings_values(self) -> None:
        """
        User can retrieve values for any stored configuration setting.

        GIVEN: A user has various settings stored in their configuration
        WHEN: User requests specific setting values
        THEN: Correct values should be returned for existing settings
        AND: Default values should be returned for missing settings
        """
        # Arrange: Mock stored settings data
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {
                "Format version": 2,
                "auto_open_doc_in_browser": False,
                "motor_test_duration": 3.5,
                # Add primitive value directly to test line 304
                "primitive_dict": {},
            }

            # Act & Assert: Read various setting types
            assert ProgramSettings.get_setting("Format version") == 2
            assert ProgramSettings.get_setting("auto_open_doc_in_browser") is False
            assert ProgramSettings.get_setting("motor_test_duration") == 3.5
            assert ProgramSettings.get_setting("nonexistent_setting") is None
            # Test direct primitive value to cover line 304
            assert ProgramSettings.get_setting("primitive_dict") is None

    def test_user_can_write_setting_values(self) -> None:
        """
        User can save new values for any configuration setting.

        GIVEN: A user wants to update a configuration setting
        WHEN: User sets a new value for a valid setting
        THEN: The setting should be saved with the new value
        AND: Invalid settings should be ignored for safety
        """
        # Arrange: Mock settings operations and defaults
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings_dict,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
            patch.object(
                ProgramSettings,
                "_get_settings_defaults",
                return_value={
                    "Format version": 1,
                    "auto_open_doc_in_browser": True,
                    "annotate_docs_into_param_files": False,
                    "gui_complexity": "normal",
                    "motor_test_duration": 2.5,
                    "motor_test_throttle_pct": 10,
                },
            ),
        ):
            mock_get_settings_dict.return_value = {
                "Format version": 1,
                "auto_open_doc_in_browser": True,
                "annotate_docs_into_param_files": False,
                "gui_complexity": "normal",
                "motor_test_duration": 2.5,
                "motor_test_throttle_pct": 10,
            }

            # Act: Set valid setting value
            ProgramSettings.set_setting("gui_complexity", "simple")

            # Assert: Valid setting is updated and saved
            # pylint: disable=duplicate-code
            expected_settings = {
                "Format version": 1,
                "auto_open_doc_in_browser": True,
                "annotate_docs_into_param_files": False,
                "gui_complexity": "simple",
                "motor_test_duration": 2.5,
                "motor_test_throttle_pct": 10,
            }
            # pylint: enable=duplicate-code
            mock_set_settings.assert_called_with(expected_settings)

            # Act: Try to set invalid setting
            mock_set_settings.reset_mock()
            ProgramSettings.set_setting("invalid_setting", "value")

            # Assert: Invalid settings are ignored
            mock_set_settings.assert_not_called()

    def test_user_can_write_nested_setting_values(self) -> None:
        """
        User can update nested settings using hierarchical paths.

        GIVEN: A system with nested settings
        WHEN: User sets a value using a path like "directory_selection/template_dir"
        THEN: The setting should be updated correctly in the nested structure
        """
        # Arrange: Mock settings operations and defaults with nested structure
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings_dict,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings_dict.return_value = {
                "directory_selection": {
                    "template_dir": "/original/path",
                    "new_base_dir": "/base/dir",
                }
            }

            # Act: Set nested setting value
            ProgramSettings.set_setting("directory_selection/template_dir", "/new/path")

            # Assert: Nested setting is updated and saved
            expected_settings = {
                "directory_selection": {
                    "template_dir": "/new/path",
                    "new_base_dir": "/base/dir",
                }
            }
            mock_set_settings.assert_called_with(expected_settings)

    def test_user_gets_error_when_invalid_nested_path(self) -> None:
        """
        User gets error when trying to set a value with invalid nested path.

        GIVEN: A system with settings
        WHEN: User tries to set a value with a nonexistent parent path
        THEN: No setting should be updated and an error should be logged
        """
        # Arrange: Mock settings operations
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings_dict,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_error") as mock_logging_error,
        ):
            mock_get_settings_dict.return_value = {
                "directory_selection": {
                    "template_dir": "/original/path",
                }
            }

            # Act: Try to set nested setting with invalid parent path
            ProgramSettings.set_setting("nonexistent/template_dir", "/new/path")

            # Assert: Setting is not updated and error is logged
            mock_set_settings.assert_not_called()
            mock_logging_error.assert_called()

    def test_user_gets_error_when_invalid_nested_key(self) -> None:
        """
        User gets error when trying to set a value with valid parent but invalid key.

        GIVEN: A system with nested settings
        WHEN: User tries to set a value with a nonexistent key in a valid parent
        THEN: No setting should be updated and an error should be logged
        """
        # Arrange: Mock settings operations
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings_dict,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_error") as mock_logging_error,
        ):
            mock_get_settings_dict.return_value = {
                "directory_selection": {
                    "template_dir": "/original/path",
                }
            }

            # Act: Try to set nonexistent nested setting
            ProgramSettings.set_setting("directory_selection/nonexistent_key", "/new/path")

            # Assert: Setting is not updated and error is logged
            mock_set_settings.assert_not_called()
            mock_logging_error.assert_called()

    def test_user_gets_error_when_parent_not_dict(self) -> None:
        """
        User gets error when trying to set a nested path where parent is not a dictionary.

        GIVEN: A system with settings where a primitive value exists
        WHEN: User tries to treat a primitive value as a dictionary
        THEN: No setting should be updated and an error should be logged
        """
        # Arrange: Mock settings operations
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings_dict,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_error") as mock_logging_error,
        ):
            mock_get_settings_dict.return_value = {
                "primitive_value": "string",
            }

            # Act: Try to use primitive value as dictionary
            ProgramSettings.set_setting("primitive_value/some_key", "value")

            # Assert: Setting is not updated and error is logged
            mock_set_settings.assert_not_called()
            mock_logging_error.assert_called()


class TestMotorDiagramManagement:
    """Test motor diagram file management functionality in ProgramSettings."""

    def test_user_can_get_motor_diagram_filepath_for_existing_frame(self) -> None:
        """
        User can get the correct motor diagram filepath for existing frame configuration.

        GIVEN: A vehicle with quad X frame configuration (class=1, type=1)
        WHEN: User requests the motor diagram filepath
        THEN: The correct SVG filepath should be returned
        AND: The file should exist in the images directory
        """
        # Arrange: Mock file operations to simulate existing diagram
        mock_svg_path = "/app/images/m_01_01_quad_x.svg"

        with (
            patch("glob.glob", return_value=[mock_svg_path]),
            patch("os.path.exists", return_value=True),
        ):
            # Act: Get diagram filepath for quad X frame
            filepath, error_msg = ProgramSettings.motor_diagram_filepath(frame_class=1, frame_type=1)

            # Assert: Correct filepath is returned without error
            assert filepath == mock_svg_path
            assert error_msg == ""
            assert "m_01_01" in filepath
            assert filepath.endswith(".svg")

    def test_user_gets_default_diagram_when_specific_frame_not_found(self) -> None:
        """
        User gets default quad X diagram when specific frame diagram doesn't exist.

        GIVEN: A vehicle with an uncommon frame configuration
        WHEN: User requests motor diagram filepath for non-existent frame
        THEN: The default quad X diagram should be returned as fallback
        """
        # Arrange: Mock file operations with no specific match but default exists
        with (
            patch("glob.glob", return_value=[]),  # No specific match
            patch("os.path.exists", return_value=True),  # Default exists
        ):
            # Act: Get diagram filepath for uncommon frame
            filepath, error_msg = ProgramSettings.motor_diagram_filepath(frame_class=99, frame_type=99)

            # Assert: Error message indicates diagram not found
            assert filepath == ""
            assert error_msg != ""
            assert "not found" in error_msg

    def test_user_gets_first_file_when_multiple_diagrams_found(self) -> None:
        """
        User gets the first matching file when multiple diagram files exist.

        GIVEN: A system with multiple matching motor diagram files
        WHEN: User requests motor diagram filepath for a frame with multiple matches
        THEN: The first matching file should be returned with an error message
        """
        # Arrange: Mock file operations with multiple matches
        multiple_matches = ["/app/images/m_01_01_quad_x_v1.svg", "/app/images/m_01_01_quad_x_v2.svg"]

        with (
            patch("glob.glob", return_value=multiple_matches),  # Multiple matches
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_error") as mock_logging_error,
        ):
            # Act: Get diagram filepath
            filepath, error_msg = ProgramSettings.motor_diagram_filepath(frame_class=1, frame_type=1)

            # Assert: First match returned with error message
            assert filepath == multiple_matches[0]
            assert "Multiple motor diagrams found" in error_msg
            # Verify that logging_error was called (line 355)
            mock_logging_error.assert_called_once()

    def test_user_gets_empty_string_when_no_diagrams_exist(self) -> None:
        """
        User gets empty string when no motor diagrams exist at all.

        GIVEN: A system with no motor diagram files
        WHEN: User requests motor diagram filepath
        THEN: An empty string should be returned
        """
        # Arrange: Mock file operations with no diagrams existing
        with (
            patch("glob.glob", return_value=[]),  # No specific match
            patch("os.path.exists", return_value=False),  # No default either
        ):
            # Act: Get diagram filepath when no diagrams exist
            filepath, error_msg = ProgramSettings.motor_diagram_filepath(frame_class=1, frame_type=1)

            # Assert: Empty string is returned with error message
            assert filepath == ""
            assert error_msg != ""
            assert "not found" in error_msg

    def test_user_can_check_motor_diagram_existence(self) -> None:
        """
        User can check if motor diagram exists for specific frame configuration.

        GIVEN: A user wants to verify motor diagram availability
        WHEN: User checks if diagram exists for specific frame
        THEN: Boolean result should indicate diagram availability correctly
        """
        # Arrange: Mock diagram filepath and existence check
        with patch.object(ProgramSettings, "motor_diagram_filepath") as mock_filepath:
            # Act & Assert: Test when diagram exists
            # motor_diagram_filepath still returns a tuple (path, error_msg) as per its implementation
            mock_filepath.return_value = "/app/images/m_01_01_quad_x.svg", ""
            with patch("os.path.exists", return_value=True):
                assert ProgramSettings.motor_diagram_exists(1, 1) is True

            # Act & Assert: Test when diagram doesn't exist
            mock_filepath.return_value = "", "Not found"
            assert ProgramSettings.motor_diagram_exists(99, 99) is False

    def test_motor_diagram_filepath_works_in_compiled_executable(self) -> None:
        """
        Motor diagram filepath works correctly when running as compiled executable.

        GIVEN: Application running as compiled executable (frozen)
        WHEN: User requests motor diagram filepath
        THEN: Correct path relative to executable should be returned
        """
        # Arrange: Mock frozen application environment
        mock_svg_path = "/compiled/app/images/m_01_01_quad_x.svg"

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.getattr") as mock_getattr,
            patch("sys.executable", "/compiled/app/ardupilot_methodic_configurator.exe"),
            patch("os.path.dirname", return_value="/compiled/app"),
            patch("glob.glob", return_value=[mock_svg_path]),
        ):
            # Configure mock to return True for frozen attribute, False for others
            def getattr_side_effect(_obj: object, attr: str, default: object = None) -> object:
                if attr == "frozen":
                    return True
                return default if default is not None else False

            mock_getattr.side_effect = getattr_side_effect
            # Act: Get diagram filepath in compiled environment
            filepath, error_msg = ProgramSettings.motor_diagram_filepath(frame_class=1, frame_type=1)

            # Assert: Correct compiled app path is used
            assert filepath == mock_svg_path
            assert error_msg == ""


class TestTemplateDirectoryManagement:
    """Test template directory storage and retrieval functionality."""

    def test_user_can_get_recently_used_dirs_with_directory_creation(self) -> None:
        """
        User can retrieve recently used directories and system creates missing directories.

        GIVEN: A user requests their recently used directory paths
        WHEN: The default vehicles directory does not exist
        THEN: The vehicles directory should be created automatically
        AND: All three directory paths should be returned correctly
        """
        # Arrange: Mock missing vehicles directory that needs creation
        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value="/user/config"),
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_makedirs") as mock_makedirs,
        ):
            # Configure settings response
            mock_get_settings.return_value = {
                "directory_selection": {
                    "template_dir": "/saved/template",
                    "new_base_dir": "/saved/base",
                    "vehicle_dir": "/saved/vehicle",
                }
            }

            # Act: Get recently used directories
            template_dir, new_base_dir, vehicle_dir = ProgramSettings.get_recently_used_dirs()

            # Assert: Directory was created and paths returned correctly
            # Use os_path.join to create platform-appropriate path for assertion
            expected_path = os_path.join("/user/config", "vehicles")
            mock_makedirs.assert_called_once_with(expected_path, exist_ok=True)
            assert template_dir == "/saved/template"
            assert new_base_dir == "/saved/base"
            assert vehicle_dir == "/saved/vehicle"

    def test_user_can_store_template_directory(self) -> None:
        """
        User can store their preferred template directory for vehicle creation.

        GIVEN: A user selects a template directory for their projects
        WHEN: User stores the template directory path
        THEN: The directory path should be saved correctly with proper formatting
        """
        # Arrange: Mock setting operations
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
            patch.object(ProgramSettings, "get_templates_base_dir", return_value="/app/templates"),
            patch("os.path.join", return_value="/app/templates/Copter/QuadX"),
        ):
            mock_get_settings.return_value = {"directory_selection": {"template_dir": "/old/template"}}

            # Act: Store new template directory
            ProgramSettings.store_template_dir("Copter/QuadX")

            # Assert: Setting was called with correct structure
            mock_set_settings.assert_called_once()
            # Get the called arguments
            called_args = mock_set_settings.call_args[0][0]
            assert "directory_selection" in called_args
            # Path will be normalized for current platform
            expected_path = "/app/templates/Copter/QuadX"
            if platform.system() == "Windows":
                expected_path = "\\app\\templates\\Copter\\QuadX"
            assert called_args["directory_selection"]["template_dir"] == expected_path

    def test_user_can_store_recently_used_template_dirs(self) -> None:
        """
        User can store recently used template and base directories.

        GIVEN: A user has selected template and base directories for their projects
        WHEN: User stores these directory paths
        THEN: Both paths should be saved with proper normalization
        """
        # Arrange: Mock setting operations
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {"directory_selection": {}}

            # Act: Store recently used directories
            ProgramSettings.store_recently_used_template_dirs("/template/path", "/base/path")

            # Assert: Both paths saved with normalization
            mock_set_settings.assert_called_once()
            called_args = mock_set_settings.call_args[0][0]
            assert "template_dir" in called_args["directory_selection"]
            assert "new_base_dir" in called_args["directory_selection"]

    def test_user_can_store_recently_used_vehicle_dir(self) -> None:
        """
        User can store their recently used vehicle directory.

        GIVEN: A user has selected a vehicle directory for their projects
        WHEN: User stores the vehicle directory path
        THEN: The path should be saved with proper normalization
        """
        # Arrange: Mock setting operations
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {"directory_selection": {}}

            # Act: Store recently used vehicle directory
            ProgramSettings.store_recently_used_vehicle_dir("/vehicle/path")

            # Assert: Vehicle path saved with normalization
            mock_set_settings.assert_called_once()
            called_args = mock_set_settings.call_args[0][0]
            assert "vehicle_dir" in called_args["directory_selection"]


class TestGUIComplexitySettings:
    """Test GUI complexity preference management."""

    def test_user_can_manage_gui_complexity_setting(self) -> None:
        """
        User can control the GUI complexity level for interface simplification.

        GIVEN: A user wants to configure interface complexity
        WHEN: User gets and sets the GUI complexity preference
        THEN: The preference should be stored and retrieved correctly
        AND: Default value should be provided when setting doesn't exist
        """
        # Arrange: Mock setting operations and defaults
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
            patch.object(
                ProgramSettings,
                "_get_settings_defaults",
                return_value={
                    "Format version": 1,
                    "auto_open_doc_in_browser": True,
                    "annotate_docs_into_param_files": False,
                    "gui_complexity": "normal",
                    "motor_test_duration": 2.5,
                    "motor_test_throttle_pct": 10,
                },
            ),
        ):
            # Test getting existing setting
            mock_get_settings.return_value = {"gui_complexity": "simple"}
            complexity = ProgramSettings.get_setting("gui_complexity")
            assert complexity == "simple"

            # Test getting default when setting doesn't exist
            mock_get_settings.return_value = {}
            complexity = ProgramSettings.get_setting("gui_complexity")
            assert complexity is None  # Returns None for missing settings

            # Test setting GUI complexity
            mock_get_settings.return_value = {
                "Format version": 1,
                "auto_open_doc_in_browser": True,
                "annotate_docs_into_param_files": False,
                "gui_complexity": "normal",
                "motor_test_duration": 2.5,
                "motor_test_throttle_pct": 10,
            }
            ProgramSettings.set_setting("gui_complexity", "simple")
            # pylint: disable=duplicate-code
            expected_settings = {
                "Format version": 1,
                "auto_open_doc_in_browser": True,
                "annotate_docs_into_param_files": False,
                "gui_complexity": "simple",
                "motor_test_duration": 2.5,
                "motor_test_throttle_pct": 10,
            }
            # pylint: disable=duplicate-code
            mock_set_settings.assert_called_with(expected_settings)


class TestInternalConfigurationMethods:
    """Test internal configuration helper methods for complete coverage."""

    def test_get_templates_base_dir_uses_script_dir_on_linux(self) -> None:
        """
        Templates base directory uses script directory on non-Windows platforms (Linux/macOS).

        GIVEN: A non-Windows platform environment (Linux or macOS)
        WHEN: The templates base directory is requested
        THEN: The script directory should be used as the base
        """
        # Arrange: Mock non-Windows platform and paths
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.dirname") as mock_dirname,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.abspath") as mock_abspath,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.join") as mock_join,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_debug"),
        ):
            # Test for Linux platform
            mock_platform.return_value = "Linux"
            mock_abspath.return_value = "/path/to/backend_filesystem_program_settings.py"
            mock_dirname.return_value = "/path/to"
            mock_join.return_value = "/path/to/vehicle_templates"

            # Act: Get templates base directory
            result = ProgramSettings.get_templates_base_dir()

            # Assert: Non-Windows path logic is used correctly
            mock_dirname.assert_called_once_with("/path/to/backend_filesystem_program_settings.py")
            mock_join.assert_called_once_with("/path/to", "vehicle_templates")
            assert result == "/path/to/vehicle_templates"

    def test_get_templates_base_dir_uses_script_dir_on_macos(self) -> None:
        """
        Templates base directory uses script directory on macOS platform.

        GIVEN: A macOS platform environment
        WHEN: The templates base directory is requested
        THEN: The script directory should be used as the base
        """
        # Arrange: Mock macOS platform and paths
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.dirname") as mock_dirname,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.abspath") as mock_abspath,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.join") as mock_join,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_debug"),
        ):
            # Test for macOS platform (Darwin)
            mock_platform.return_value = "Darwin"
            mock_abspath.return_value = "/Applications/ArduPilot/backend_filesystem_program_settings.py"
            mock_dirname.return_value = "/Applications/ArduPilot"
            mock_join.return_value = "/Applications/ArduPilot/vehicle_templates"

            # Act: Get templates base directory
            result = ProgramSettings.get_templates_base_dir()

            # Assert: macOS path logic is used correctly (same as Linux - non-Windows)
            mock_dirname.assert_called_once_with("/Applications/ArduPilot/backend_filesystem_program_settings.py")
            mock_join.assert_called_once_with("/Applications/ArduPilot", "vehicle_templates")
            assert result == "/Applications/ArduPilot/vehicle_templates"

    def test_get_templates_base_dir_uses_site_config_on_windows(self) -> None:
        """
        Templates base directory uses site config directory on Windows.

        GIVEN: A Windows platform environment
        WHEN: The templates base directory is requested
        THEN: The site configuration directory should be used as the base
        """
        # Arrange: Mock Windows platform and site config
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform,
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings._site_config_dir"
            ) as mock_site_config,
        ):
            mock_platform.return_value = "Windows"
            mock_site_config.return_value = "C:\\Program Files\\App"

            # Act: Get templates base directory
            result = ProgramSettings.get_templates_base_dir()

            # Assert: Windows path logic is used correctly
            mock_site_config.assert_called_once()
            # Use os.path.join to handle platform-specific path separators
            expected_path = os_path.join("C:\\Program Files\\App", "vehicle_templates")
            assert result == expected_path
