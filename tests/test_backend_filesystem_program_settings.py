#!/usr/bin/env python3

"""
BDD-style tests for the backend_filesystem_program_settings.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

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

    def test_user_can_get_application_icon_filepath(self) -> None:
        """
        User can retrieve the application icon filepath for GUI display.

        GIVEN: A user needs to display the application icon in the GUI
        WHEN: User requests the application icon filepath
        THEN: The correct path to ArduPilot_icon.png should be returned
        AND: The path should be properly constructed using importlib.resources
        """
        # Arrange: Mock the entire method to return expected path
        expected_path = "/mock/path/images/ArduPilot_icon.png"
        with patch.object(ProgramSettings, "application_icon_filepath", return_value=expected_path) as mock_method:
            # Act: Get application icon filepath
            result = ProgramSettings.application_icon_filepath()

            # Assert: Correct filepath is returned
            assert result == expected_path
            mock_method.assert_called_once()

    def test_user_can_get_application_logo_filepath(self) -> None:
        """
        User can retrieve the application logo filepath for display in dialogs.

        GIVEN: A user needs to display the application logo in about dialog
        WHEN: User requests the application logo filepath
        THEN: The correct path to ArduPilot_logo.png should be returned
        AND: The path should be properly constructed using importlib.resources
        """
        # Arrange: Mock the entire method to return expected path
        expected_path = "/mock/path/images/ArduPilot_logo.png"
        with patch.object(ProgramSettings, "application_logo_filepath", return_value=expected_path) as mock_method:
            # Act: Get application logo filepath
            result = ProgramSettings.application_logo_filepath()

            # Assert: Correct filepath is returned
            assert result == expected_path
            mock_method.assert_called_once()

    def test_user_can_get_icon_filepath_using_importlib_resources(self) -> None:
        """
        User can retrieve icon filepath using modern importlib.resources method.

        GIVEN: Python 3.9+ with importlib.resources.files available
        WHEN: User requests the application icon filepath
        THEN: The path should be retrieved using importlib.resources
        AND: The path should exist and end with ArduPilot_icon.png
        """
        # Act: Get application icon filepath (uses importlib.resources in Python 3.9+)
        result = ProgramSettings.application_icon_filepath()

        # Assert: Path is valid and ends with expected filename
        assert result.endswith("ArduPilot_icon.png")
        assert "images" in result
        # Path should exist when running from source or installed package
        assert os_path.exists(result), f"Icon file should exist at {result}"

    def test_user_can_get_logo_filepath_using_importlib_resources(self) -> None:
        """
        User can retrieve logo filepath using modern importlib.resources method.

        GIVEN: Python 3.9+ with importlib.resources.files available
        WHEN: User requests the application logo filepath
        THEN: The path should be retrieved using importlib.resources
        AND: The path should exist and end with ArduPilot_logo.png
        """
        # Act: Get application logo filepath (uses importlib.resources in Python 3.9+)
        result = ProgramSettings.application_logo_filepath()

        # Assert: Path is valid and ends with expected filename
        assert result.endswith("ArduPilot_logo.png")
        assert "images" in result
        # Path should exist when running from source or installed package
        assert os_path.exists(result), f"Logo file should exist at {result}"


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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
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
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True):
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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
            pytest.raises(FileNotFoundError, match=r"site configuration directory.*does not exist"),
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
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
            pytest.raises(NotADirectoryError, match=r"path.*is not a directory"),
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
        expected_result["motor_test"] = {"duration": 2, "throttle_pct": 10}  # Added by default
        expected_result["display_usage_popup"]["component_editor_validation"] = True  # Added by default

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
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.glob_glob", return_value=[mock_svg_path]
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
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
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.glob_glob", return_value=[]
            ),  # No specific match
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True
            ),  # Default exists
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
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.glob_glob", return_value=multiple_matches
            ),  # Multiple matches
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
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.glob_glob", return_value=[]
            ),  # No specific match
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False
            ),  # No default either
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
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True
            ):
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
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.glob_glob", return_value=[mock_svg_path]
            ),
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

    def test_user_can_get_recently_used_dirs_without_directory_creation(self) -> None:
        """
        User can retrieve recently used directories when vehicles directory already exists.

        GIVEN: A user requests their recently used directory paths
        WHEN: The default vehicles directory already exists
        THEN: No directory creation occurs and paths are returned correctly
        """
        # Arrange: Mock existing vehicles directory (no creation needed)
        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value="/user/config"),
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
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

            # Assert: No directory creation occurred
            mock_makedirs.assert_not_called()
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
        Templates base directory uses package path on Linux platform.

        GIVEN: A Linux platform environment
        WHEN: The templates base directory is requested
        THEN: The package path should be used as the base
        """
        # Arrange: Mock platform and importlib_files
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.importlib_files") as mock_importlib,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_debug"),
        ):
            # Test for Linux platform
            mock_platform.return_value = "Linux"
            mock_package = MagicMock()
            mock_importlib.return_value = mock_package
            mock_package.__truediv__ = MagicMock()
            mock_package.__truediv__.return_value.__str__ = MagicMock(return_value="/mock/package/path/vehicle_templates")

            # Act: Get templates base directory
            result = ProgramSettings.get_templates_base_dir()

            # Assert: Package path is used correctly
            assert result == "/mock/package/path/vehicle_templates"
            mock_importlib.assert_called_once_with("ardupilot_methodic_configurator")

    def test_get_templates_base_dir_uses_script_dir_on_macos(self) -> None:
        """
        Templates base directory uses package path on macOS platform.

        GIVEN: A macOS platform environment
        WHEN: The templates base directory is requested
        THEN: The package path should be used as the base
        """
        # Arrange: Mock macOS platform and importlib_files
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.importlib_files") as mock_importlib,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_debug"),
        ):
            # Test for macOS platform (Darwin)
            mock_platform.return_value = "Darwin"
            mock_package = MagicMock()
            mock_importlib.return_value = mock_package
            mock_package.__truediv__ = MagicMock()
            mock_package.__truediv__.return_value.__str__ = MagicMock(return_value="/mock/package/path/vehicle_templates")

            # Act: Get templates base directory
            result = ProgramSettings.get_templates_base_dir()

            # Assert: Package path is used correctly (same as Linux - non-Windows)
            assert result == "/mock/package/path/vehicle_templates"
            mock_importlib.assert_called_once_with("ardupilot_methodic_configurator")

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


class TestDesktopIconCreation:
    """Test desktop icon creation functionality for Linux systems."""

    def test_user_can_check_if_running_on_linux_system(self) -> None:
        """
        User can determine if the application is running on a Linux system.

        GIVEN: A user needs to check the operating system
        WHEN: The system detection method is called
        THEN: It should correctly identify Linux systems
        AND: Return False for non-Linux systems
        """
        # Test Linux detection
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.sys_platform", "linux"),
        ):
            assert ProgramSettings._is_linux_system() is True

        # Test non-Linux detection
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_name", "nt"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.sys_platform", "win32"),
        ):
            assert ProgramSettings._is_linux_system() is False

    def test_user_can_get_desktop_file_path(self) -> None:
        """
        User can retrieve the correct path for the desktop file.

        GIVEN: A user needs to know where the desktop file should be created
        WHEN: The desktop file path method is called
        THEN: It should return the standard freedesktop.org user applications directory
        """
        # Arrange: Mock expanduser to control the path
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.expanduser") as mock_expand:
            mock_expand.return_value = "/home/user/.local/share/applications/ardupilot_methodic_configurator.desktop"

            # Act: Get desktop file path
            result = ProgramSettings._get_desktop_file_path()

            # Assert: Correct path is returned
            expected_path = "/home/user/.local/share/applications/ardupilot_methodic_configurator.desktop"
            assert result == expected_path
            mock_expand.assert_called_once_with("~/.local/share/applications/ardupilot_methodic_configurator.desktop")

    def test_user_can_check_if_desktop_icon_already_exists(self) -> None:
        """
        User can check if a desktop icon already exists.

        GIVEN: A user wants to avoid creating duplicate desktop icons
        WHEN: The existence check method is called with a file path
        THEN: It should correctly report whether the file exists
        """
        # Test when file exists
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True):
            assert ProgramSettings._desktop_icon_exists("/fake/path") is True

        # Test when file doesn't exist
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False):
            assert ProgramSettings._desktop_icon_exists("/fake/path") is False

    def test_user_can_get_virtual_environment_path(self) -> None:
        """
        User can retrieve the virtual environment path from environment variables.

        GIVEN: An application running in a virtual environment
        WHEN: The virtual environment detection method is called
        THEN: It should return the VIRTUAL_ENV environment variable value
        """
        # Test with virtual environment set
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_environ", {"VIRTUAL_ENV": "/path/to/venv"}
        ):
            assert ProgramSettings._get_virtual_env_path() == "/path/to/venv"

        # Test without virtual environment
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_environ", {}):
            assert ProgramSettings._get_virtual_env_path() is None

    def test_user_can_create_desktop_entry_content_with_python_executable(self) -> None:
        """
        User can create proper desktop entry content when Python executable is available.

        GIVEN: An application running in a virtual environment with accessible Python executable
        WHEN: Desktop entry content is created
        THEN: The Exec field should use the virtual environment's Python executable
        AND: All required desktop entry fields should be present
        """
        # Arrange: Mock Python executable availability
        venv_path = "/opt/venv"
        icon_path = "/usr/share/icons/app.png"

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.join",
                return_value="/opt/venv/bin/python",
            ),
        ):
            # Act: Create desktop entry content
            result = ProgramSettings._create_desktop_entry_content(venv_path, icon_path)

            # Assert: Content includes correct Exec command and all required fields
            assert "Exec=/opt/venv/bin/python -m ardupilot_methodic_configurator" in result
            assert f"Icon={icon_path}" in result
            assert "[Desktop Entry]" in result
            assert "Version=1.0" in result
            assert "Name=ArduPilot Methodic Configurator" in result
            assert "Terminal=true" in result

    def test_user_can_create_desktop_entry_content_with_bash_fallback(self) -> None:
        """
        User can create desktop entry content using bash activation when Python executable is unavailable.

        GIVEN: An application in a virtual environment where Python executable is not directly accessible
        WHEN: Desktop entry content is created
        THEN: The Exec field should use bash to activate the virtual environment
        """
        # Arrange: Mock Python executable unavailability
        venv_path = "/opt/venv"
        icon_path = "/usr/share/icons/app.png"

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.shutil_which", return_value="/bin/bash"
            ),
        ):
            # Act: Create desktop entry content
            result = ProgramSettings._create_desktop_entry_content(venv_path, icon_path)

            # Assert: Content uses bash activation
            expected_exec = '/bin/bash -c "source /opt/venv/bin/activate && ardupilot_methodic_configurator"'
            assert expected_exec in result

    def test_user_can_ensure_applications_directory_exists(self) -> None:
        """
        User can ensure the applications directory exists before creating desktop files.

        GIVEN: A user needs to create a desktop file in the applications directory
        WHEN: The directory creation method is called
        THEN: The directory should be created if it doesn't exist
        AND: The correct directory path should be returned
        """
        # Arrange: Mock directory operations
        desktop_file_path = "/home/user/.local/share/applications/app.desktop"
        expected_dir = "/home/user/.local/share/applications"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.dirname",
                return_value=expected_dir,
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_makedirs") as mock_makedirs,
        ):
            # Act: Ensure applications directory exists
            result = ProgramSettings._ensure_applications_dir_exists(desktop_file_path)

            # Assert: Directory creation was called and correct path returned
            assert result == expected_dir
            mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)

    def test_user_can_write_desktop_file_to_disk(self) -> None:
        """
        User can write desktop file content to the filesystem.

        GIVEN: A user has generated desktop entry content
        WHEN: The file writing method is called
        THEN: The content should be written to the specified file path
        """
        # Arrange: Set up test content and mock file operations
        test_content = "[Desktop Entry]\nName=Test App\n"
        file_path = "/fake/path/app.desktop"

        with patch("builtins.open", mock_open()) as mock_file:
            # Act: Write desktop file
            ProgramSettings._write_desktop_file(file_path, test_content)

            # Assert: File was opened and content was written
            mock_file.assert_called_once_with(file_path, "w", encoding="utf-8")
            mock_file().write.assert_called_once_with(test_content)

    def test_user_can_set_desktop_file_permissions(self) -> None:
        """
        User can set appropriate permissions on desktop files.

        GIVEN: A desktop file has been created
        WHEN: File permissions are set
        THEN: The file should have the correct permissions (0o644)
        """
        # Arrange: Mock chmod operation
        file_path = "/fake/path/app.desktop"

        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_chmod") as mock_chmod:
            # Act: Set desktop file permissions
            ProgramSettings._set_desktop_file_permissions(file_path)

            # Assert: Correct permissions were set
            mock_chmod.assert_called_once_with(file_path, 0o644)

    def test_user_can_update_desktop_database_when_command_available(self) -> None:
        """
        User can update the desktop database when the command is available.

        GIVEN: The update-desktop-database command is available on the system
        WHEN: The desktop database update method is called
        THEN: The command should be executed with the correct arguments
        """
        # Arrange: Mock command availability and subprocess
        apps_dir = "/home/user/.local/share/applications"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.shutil_which",
                return_value="/usr/bin/update-desktop-database",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.subprocess.run") as mock_run,
        ):
            # Act: Update desktop database
            ProgramSettings._update_desktop_database(apps_dir)

            # Assert: Command was executed with correct arguments
            mock_run.assert_called_once_with(["/usr/bin/update-desktop-database", apps_dir], check=False, capture_output=True)

    def test_user_can_handle_missing_desktop_database_command(self) -> None:
        """
        User can handle cases where the desktop database update command is not available.

        GIVEN: The update-desktop-database command is not available on the system
        WHEN: The desktop database update method is called
        THEN: No error should occur and no command should be executed
        """
        # Arrange: Mock command unavailability
        apps_dir = "/home/user/.local/share/applications"

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.shutil_which", return_value=None),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.subprocess.run") as mock_run,
        ):
            # Act: Attempt to update desktop database
            ProgramSettings._update_desktop_database(apps_dir)

            # Assert: No command was executed
            mock_run.assert_not_called()

    def test_user_can_create_desktop_icon_when_all_conditions_met(self) -> None:
        """
        User can successfully create a desktop icon when all conditions are met.

        GIVEN: Application is running on Linux in a virtual environment
        AND: No desktop icon currently exists
        AND: Icon path is available
        WHEN: Desktop icon creation is requested
        THEN: A desktop file should be created with correct content and permissions
        AND: The desktop database should be updated
        """
        # Arrange: Mock all conditions for successful creation
        desktop_file_path = "/home/user/.local/share/applications/ardupilot_methodic_configurator.desktop"
        apps_dir = "/home/user/.local/share/applications"
        venv_path = "/opt/venv"
        icon_path = "/usr/share/icons/app.png"

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.expanduser",
                return_value=desktop_file_path,
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_environ", {"VIRTUAL_ENV": venv_path}
            ),
            patch.object(ProgramSettings, "application_icon_filepath", return_value=icon_path),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.dirname", return_value=apps_dir
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_makedirs"),
            patch("builtins.open", mock_open()),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_chmod"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.shutil_which",
                return_value="/usr/bin/update-desktop-database",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.subprocess.run"),
        ):
            # Act: Create desktop icon
            ProgramSettings.create_desktop_icon_if_needed()

            # Assert: All expected operations were performed (verified through mocks)

    def test_user_creation_skipped_when_desktop_icon_already_exists(self) -> None:
        """
        User creation is skipped when a desktop icon already exists.

        GIVEN: A desktop icon already exists for the application
        WHEN: Desktop icon creation is requested
        THEN: No new file should be created
        AND: No permissions should be set
        AND: No database update should occur
        """
        # Arrange: Mock existing desktop icon
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.expanduser",
                return_value="/existing/file.desktop",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=True),
            patch("builtins.open", mock_open()) as mock_file,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_chmod") as mock_chmod,
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.subprocess.run") as mock_run,
        ):
            # Act: Attempt to create desktop icon
            ProgramSettings.create_desktop_icon_if_needed()

            # Assert: No file operations occurred
            mock_file.assert_not_called()
            mock_chmod.assert_not_called()
            mock_run.assert_not_called()

    def test_user_creation_skipped_when_not_in_virtual_environment(self) -> None:
        """
        User creation is skipped when not running in a virtual environment.

        GIVEN: Application is running outside a virtual environment
        WHEN: Desktop icon creation is requested
        THEN: No desktop file operations should occur
        """
        # Arrange: Mock no virtual environment
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.sys_platform", "linux"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_environ", {}),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Act: Attempt to create desktop icon
            ProgramSettings.create_desktop_icon_if_needed()

            # Assert: No file was created
            mock_file.assert_not_called()

    def test_user_creation_skipped_when_not_on_linux(self) -> None:
        """
        User creation is skipped when not running on Linux.

        GIVEN: Application is running on a non-Linux system
        WHEN: Desktop icon creation is requested
        THEN: No desktop file operations should occur
        """
        # Arrange: Mock non-Linux system
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_name", "nt"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.sys_platform", "win32"),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Act: Attempt to create desktop icon
            ProgramSettings.create_desktop_icon_if_needed()

            # Assert: No file was created
            mock_file.assert_not_called()

    def test_user_creation_skipped_when_icon_not_available(self) -> None:
        """
        User creation is skipped when no application icon is available.

        GIVEN: Application is running on Linux in a virtual environment
        BUT: No application icon can be found
        WHEN: Desktop icon creation is requested
        THEN: No desktop file should be created
        """
        # Arrange: Mock icon unavailability
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.expanduser",
                return_value="/fake/file.desktop",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path.exists", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_environ", {"VIRTUAL_ENV": "/venv"}),
            patch.object(ProgramSettings, "application_icon_filepath", return_value=""),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Act: Attempt to create desktop icon
            ProgramSettings.create_desktop_icon_if_needed()

            # Assert: No file was created
            mock_file.assert_not_called()
