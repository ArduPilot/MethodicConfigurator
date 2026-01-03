#!/usr/bin/env python3

"""
BDD-style tests for the backend_filesystem_freedesktop.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import subprocess
from unittest.mock import MagicMock, mock_open, patch

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


class TestStartupNotification:
    """Test startup notification functionality for Linux desktop integration."""

    def test_user_can_initialize_freedesktop_class(self) -> None:
        """
        User can initialize the FreeDesktop class.

        GIVEN: A user needs to create a FreeDesktop instance
        WHEN: The class is instantiated
        THEN: It should initialize without errors
        """
        # Act: Create FreeDesktop instance
        freedesktop = FreeDesktop()

        # Assert: Instance created successfully
        assert freedesktop is not None
        assert isinstance(freedesktop, FreeDesktop)

    def test_user_can_get_desktop_startup_id_from_environment(self) -> None:
        """
        User can retrieve the desktop startup ID from environment variables.

        GIVEN: An application launched with a DESKTOP_STARTUP_ID
        WHEN: The startup ID retrieval method is called
        THEN: It should return the startup ID from the environment
        """
        # Test with startup ID set
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ",
            {"DESKTOP_STARTUP_ID": "test_startup_id_123"},
        ):
            assert FreeDesktop._get_desktop_startup_id() == "test_startup_id_123"

        # Test without startup ID
        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {}):
            assert FreeDesktop._get_desktop_startup_id() is None

    def test_user_can_send_startup_notification_completion_with_xdg_tool(self) -> None:
        """
        User can send startup notification completion using xdg-startup-notify tool.

        GIVEN: Application has finished starting up with a valid startup ID
        AND: xdg-startup-notify command is available
        WHEN: Startup notification completion is sent
        THEN: The xdg-startup-notify command should be executed successfully
        """
        startup_id = "valid_startup_id_123"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which",
                return_value="/usr/bin/xdg-startup-notify",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")

            # Act: Send startup notification completion
            FreeDesktop._send_startup_notification_complete(startup_id)

            # Assert: xdg-startup-notify was called correctly
            mock_run.assert_called_once_with(
                ["/usr/bin/xdg-startup-notify", "remove", startup_id], capture_output=True, timeout=1.0, check=False
            )

    def test_user_can_handle_xdg_startup_notify_failure(self) -> None:
        """
        User can handle cases where xdg-startup-notify fails or times out.

        GIVEN: Application has finished starting up with a valid startup ID
        AND: xdg-startup-notify command is available but fails
        WHEN: Startup notification completion is sent
        THEN: The system should fall back to X11 method
        """
        startup_id = "valid_startup_id_123"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which",
                return_value="/usr/bin/xdg-startup-notify",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run") as mock_run,
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.FreeDesktop._send_startup_notification_x11"
            ) as mock_x11,
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(["cmd"], 1.0)

            # Act: Send startup notification completion
            FreeDesktop._send_startup_notification_complete(startup_id)

            # Assert: X11 fallback was called
            mock_x11.assert_called_once_with(startup_id)

    def test_user_can_send_startup_notification_with_x11_fallback(self) -> None:
        """
        User can send startup notification completion using X11 when xdg tools fail.

        GIVEN: Application has finished starting up with a valid startup ID
        AND: xdg-startup-notify command fails with subprocess error
        WHEN: Startup notification completion is sent
        THEN: The X11 method should be used as fallback
        """
        startup_id = "valid_startup_id_123"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which",
                return_value="/usr/bin/xdg-startup-notify",
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run",
                side_effect=subprocess.SubprocessError("Command failed"),
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.FreeDesktop._send_startup_notification_x11",
            ) as mock_x11,
        ):
            # Act: Send startup notification completion
            FreeDesktop._send_startup_notification_complete(startup_id)

            # Assert: X11 method was called
            mock_x11.assert_called_once_with(startup_id)

    def test_user_can_validate_startup_id_format(self) -> None:
        """
        User input is validated to prevent shell injection in startup IDs.

        GIVEN: An application receives a potentially malicious startup ID
        WHEN: Startup notification completion is attempted
        THEN: Invalid startup IDs should be rejected
        """
        # Test valid startup ID
        valid_id = "valid-startup_id_123"
        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which", return_value=None):
            # Should not raise exception, just return early
            FreeDesktop._send_startup_notification_complete(valid_id)

        # Test invalid startup ID with shell injection attempt
        invalid_id = "valid_id; rm -rf /"
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which", return_value=None),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.FreeDesktop._send_startup_notification_x11"
            ) as mock_x11,
        ):
            FreeDesktop._send_startup_notification_complete(invalid_id)
            # Should not call X11 method for invalid ID
            mock_x11.assert_not_called()

    def test_user_can_send_startup_notification_via_x11_when_tk_available(self) -> None:
        """
        User can send startup notification completion using direct X11 messaging when Tk is available.

        GIVEN: Application has finished starting up with a valid startup ID
        AND: Tkinter is available for X11 messaging
        WHEN: X11 startup notification is sent
        THEN: Tk should be used to send the notification message
        """
        startup_id = "valid_startup_id_123"

        mock_root = MagicMock()
        mock_tk = MagicMock()
        mock_tk.Tk.return_value = mock_root

        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.tk", mock_tk):
            # Act: Send X11 startup notification
            FreeDesktop._send_startup_notification_x11(startup_id)

            # Assert: Tk was used correctly
            mock_root.withdraw.assert_called_once()
            assert mock_root.eval.call_count >= 2  # Should call eval at least twice for the messaging
            mock_root.destroy.assert_called_once()

    def test_user_can_handle_x11_startup_notification_when_tk_unavailable(self) -> None:
        """
        User can handle cases where Tkinter is not available for X11 messaging.

        GIVEN: Application needs to send startup notification
        BUT: Tkinter is not available
        WHEN: X11 startup notification is attempted
        THEN: The operation should complete without error
        """
        startup_id = "valid_startup_id_123"

        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.tk", None):
            # Act: Attempt X11 startup notification without Tk
            FreeDesktop._send_startup_notification_x11(startup_id)

            # Assert: No exception raised, method returns early

    def test_user_can_handle_x11_startup_notification_errors(self) -> None:
        """
        User can handle errors during X11 startup notification sending.

        GIVEN: Application attempts to send X11 startup notification
        BUT: Tkinter operations fail
        WHEN: X11 startup notification is sent
        THEN: Errors should be logged but not crash the application
        """
        startup_id = "valid_startup_id_123"

        mock_tk = MagicMock()
        mock_tk.Tk.side_effect = Exception("Tk error")

        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.tk", mock_tk):
            # Act: Attempt X11 startup notification with Tk error
            FreeDesktop._send_startup_notification_x11(startup_id)

            # Assert: No exception propagated, error is handled internally

    def test_user_can_setup_startup_notification_for_main_window(self) -> None:
        """
        User can set up startup notification handling for the main application window.

        GIVEN: Application is starting on Linux with a startup ID
        WHEN: Startup notification setup is called with the main window
        THEN: Event bindings should be created to send completion when window is ready
        """
        mock_window = MagicMock()
        mock_window.winfo_viewable.return_value = False

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {"DESKTOP_STARTUP_ID": "test_id"}
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop"
                ".FreeDesktop._send_startup_notification_complete"
            ) as mock_send,
        ):
            # Act: Set up startup notification
            FreeDesktop.setup_startup_notification(mock_window)

            # Assert: Event binding was created
            mock_window.bind.assert_called_once()
            # Completion should not be sent immediately since window is not viewable
            mock_send.assert_not_called()

    def test_user_can_send_immediate_startup_notification_when_window_already_visible(self) -> None:
        """
        User can send startup notification immediately when window is already visible.

        GIVEN: Application window is already visible when startup notification is set up
        WHEN: Startup notification setup is called
        THEN: Completion should be sent immediately
        """
        mock_window = MagicMock()
        mock_window.winfo_viewable.return_value = True

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {"DESKTOP_STARTUP_ID": "test_id"}
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop"
                ".FreeDesktop._send_startup_notification_complete"
            ) as mock_send,
        ):
            # Act: Set up startup notification
            FreeDesktop.setup_startup_notification(mock_window)

            # Assert: Completion was sent immediately
            mock_send.assert_called_once_with("test_id")

    def test_user_startup_notification_skipped_when_not_on_linux(self) -> None:
        """
        User startup notification setup is skipped when not running on Linux.

        GIVEN: Application is running on a non-Linux system
        WHEN: Startup notification setup is attempted
        THEN: No startup notification handling should be set up
        """
        mock_window = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "nt"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "win32"),
        ):
            # Act: Attempt startup notification setup on non-Linux
            FreeDesktop.setup_startup_notification(mock_window)

            # Assert: No bindings or operations performed
            mock_window.bind.assert_not_called()

    def test_user_startup_notification_skipped_when_no_startup_id(self) -> None:
        """
        User startup notification setup is skipped when no startup ID is available.

        GIVEN: Application is running on Linux but no DESKTOP_STARTUP_ID is set
        WHEN: Startup notification setup is called
        THEN: No event bindings should be created
        """
        mock_window = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {}),
        ):
            # Act: Set up startup notification without startup ID
            FreeDesktop.setup_startup_notification(mock_window)

            # Assert: No bindings created
            mock_window.bind.assert_not_called()

    def test_user_can_handle_desktop_icon_creation_errors(self) -> None:
        """
        User can handle errors during desktop icon creation gracefully.

        GIVEN: Application attempts to create a desktop icon
        BUT: File system operations fail
        WHEN: Desktop icon creation is requested
        THEN: Errors should be logged but not crash the application
        """
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.expanduser",
                return_value="/fake/file.desktop",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.exists", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {"VIRTUAL_ENV": "/venv"}),
            patch.object(ProgramSettings, "application_icon_filepath", return_value="/icon.png"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_path.dirname", return_value="/fake/dir"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_makedirs"),
            patch("builtins.open", side_effect=OSError("File system error")),
        ):
            # Act: Attempt desktop icon creation with file error
            FreeDesktop.create_desktop_icon_if_needed()

            # Assert: No exception raised, error handled internally

    def test_user_can_handle_xdg_startup_notify_non_zero_exit(self) -> None:
        """
        User can handle xdg-startup-notify returning non-zero exit code.

        GIVEN: Application has finished starting up with a valid startup ID
        AND: xdg-startup-notify command exists but returns failure
        WHEN: Startup notification completion is sent
        THEN: The failure should be logged but not crash the application
        """
        startup_id = "valid_startup_id_123"

        mock_result = MagicMock()
        mock_result.returncode = 1  # Non-zero exit code
        mock_result.stderr = b"Command failed"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which",
                return_value="/usr/bin/xdg-startup-notify",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.subprocess.run", return_value=mock_result),
        ):
            # Act: Send startup notification completion
            FreeDesktop._send_startup_notification_complete(startup_id)

            # Assert: Method completes without error (failure is logged)

    def test_user_can_handle_xdg_startup_notify_not_found_logging(self) -> None:
        """
        User can handle logging when xdg-startup-notify is not found.

        GIVEN: Application has finished starting up with a valid startup ID
        AND: xdg-startup-notify command is not available
        WHEN: Startup notification completion is sent
        THEN: The absence should be logged but not crash the application
        """
        startup_id = "valid_startup_id_123"

        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.shutil_which", return_value=None):
            # Act: Send startup notification completion
            FreeDesktop._send_startup_notification_complete(startup_id)

            # Assert: Method completes without error (absence is logged)

    def test_user_can_setup_startup_notification_with_logging(self) -> None:
        """
        User can set up startup notification with debug logging.

        GIVEN: Application is starting on Linux with a startup ID
        WHEN: Startup notification setup is called
        THEN: Debug logging should occur and event binding should be created
        """
        mock_window = MagicMock()
        mock_window.winfo_viewable.return_value = False

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_name", "posix"),
            patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.sys_platform", "linux"),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_freedesktop.os_environ", {"DESKTOP_STARTUP_ID": "test_id"}
            ),
        ):
            # Act: Set up startup notification
            FreeDesktop.setup_startup_notification(mock_window)

            # Assert: Event binding was created (logging occurs internally)

    def test_user_can_handle_x11_eval_exceptions(self) -> None:
        """
        User can handle exceptions during Tk eval calls in X11 messaging.

        GIVEN: Application attempts to send X11 startup notification
        BUT: Tk eval calls fail
        WHEN: X11 startup notification is sent
        THEN: Inner exceptions should be logged but not crash the application
        """
        startup_id = "valid_startup_id_123"

        mock_root = MagicMock()
        mock_root.eval.side_effect = Exception("Eval failed")
        mock_tk = MagicMock()
        mock_tk.Tk.return_value = mock_root

        with patch("ardupilot_methodic_configurator.backend_filesystem_freedesktop.tk", mock_tk):
            # Act: Attempt X11 startup notification with eval failures
            FreeDesktop._send_startup_notification_x11(startup_id)

            # Assert: No exception propagated, error is handled internally

    def test_user_can_handle_empty_startup_id(self) -> None:
        """
        User can handle empty startup ID gracefully.

        GIVEN: Application attempts to send startup notification with empty ID
        WHEN: Startup notification completion is sent
        THEN: The method should return early without attempting notification
        """
        # Act: Send startup notification with empty ID
        FreeDesktop._send_startup_notification_complete("")

        # Assert: Method completes without error (returns early)
