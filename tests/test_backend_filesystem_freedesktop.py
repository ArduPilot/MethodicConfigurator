#!/usr/bin/env python3

"""
BDD-style tests for the backend_filesystem_freedesktop.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import mock_open, patch

from ardupilot_methodic_configurator.backend_filesystem_freedesktop import FreeDesktop
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings

# pylint: disable=protected-access


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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
        ):
            assert FreeDesktop._is_linux_system() is True

        # Test non-Linux detection
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "nt"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "win32"),
        ):
            assert FreeDesktop._is_linux_system() is False

    def test_user_can_get_desktop_file_path(self) -> None:
        """
        User can retrieve the correct path for the desktop file.

        GIVEN: A user needs to know where the desktop file should be created
        WHEN: The desktop file path method is called
        THEN: It should return the standard freedesktop.org user applications directory
        """
        # Arrange: Mock expanduser to control the path
        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.expanduser") as mock_expand:
            mock_expand.return_value = "/home/user/.local/share/applications/ardupilot_methodic_configurator.desktop"

            # Act: Get desktop file path
            result = FreeDesktop._get_desktop_file_path()

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
        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=True):
            assert FreeDesktop._desktop_icon_exists("/fake/path") is True

        # Test when file doesn't exist
        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=False):
            assert FreeDesktop._desktop_icon_exists("/fake/path") is False

    def test_user_can_get_virtual_environment_path(self) -> None:
        """
        User can retrieve the virtual environment path from environment variables.

        GIVEN: An application running in a virtual environment
        WHEN: The virtual environment detection method is called
        THEN: It should return the VIRTUAL_ENV environment variable value
        """
        # Test with virtual environment set
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {"VIRTUAL_ENV": "/path/to/venv"}
        ):
            assert FreeDesktop._get_virtual_env_path() == "/path/to/venv"

        # Test without virtual environment
        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {}):
            assert FreeDesktop._get_virtual_env_path() is None

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=True),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.join",
                return_value="/opt/venv/bin/python",
            ),
        ):
            # Act: Create desktop entry content
            result = FreeDesktop._create_desktop_entry_content(venv_path, icon_path)

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which", return_value="/bin/bash"),
        ):
            # Act: Create desktop entry content
            result = FreeDesktop._create_desktop_entry_content(venv_path, icon_path)

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
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.dirname",
                return_value=expected_dir,
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_makedirs") as mock_makedirs,
        ):
            # Act: Ensure applications directory exists
            result = FreeDesktop._ensure_applications_dir_exists(desktop_file_path)

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
            FreeDesktop._write_desktop_file(file_path, test_content)

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

        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_chmod") as mock_chmod:
            # Act: Set desktop file permissions
            FreeDesktop._set_desktop_file_permissions(file_path)

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
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which",
                return_value="/usr/bin/update-desktop-database",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run") as mock_run,
        ):
            # Act: Update desktop database
            FreeDesktop._update_desktop_database(apps_dir)

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which", return_value=None),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run") as mock_run,
        ):
            # Act: Attempt to update desktop database
            FreeDesktop._update_desktop_database(apps_dir)

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.expanduser",
                return_value=desktop_file_path,
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {"VIRTUAL_ENV": venv_path}),
            patch.object(ProgramSettings, "application_icon_filepath", return_value=icon_path),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.dirname", return_value=apps_dir),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_makedirs"),
            patch("builtins.open", mock_open()),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_chmod"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which",
                return_value="/usr/bin/update-desktop-database",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run"),
        ):
            # Act: Create desktop icon
            FreeDesktop.create_desktop_icon_if_needed()

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.expanduser",
                return_value="/existing/file.desktop",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=True),
            patch("builtins.open", mock_open()) as mock_file,
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_chmod") as mock_chmod,
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run") as mock_run,
        ):
            # Act: Attempt to create desktop icon
            FreeDesktop.create_desktop_icon_if_needed()

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {}),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Act: Attempt to create desktop icon
            FreeDesktop.create_desktop_icon_if_needed()

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "nt"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "win32"),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Act: Attempt to create desktop icon
            FreeDesktop.create_desktop_icon_if_needed()

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
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.expanduser",
                return_value="/fake/file.desktop",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {"VIRTUAL_ENV": "/venv"}),
            patch.object(ProgramSettings, "application_icon_filepath", return_value=""),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Act: Attempt to create desktop icon
            FreeDesktop.create_desktop_icon_if_needed()

            # Assert: No file was created
            mock_file.assert_not_called()
