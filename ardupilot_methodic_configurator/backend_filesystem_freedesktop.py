"""
Handles FreeDesktop.org compliance and desktop integration features.

This includes creating desktop entries for application launchers, managing startup
notifications according to the FreeDesktop Startup Notification specification,
and ensuring proper integration with Linux desktop environments.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
import subprocess
import tkinter as tk
from logging import debug as logging_debug
from logging import error as logging_error
from os import chmod as os_chmod
from os import environ as os_environ
from os import makedirs as os_makedirs
from os import name as os_name
from os import path as os_path
from shutil import which as shutil_which
from sys import platform as sys_platform
from typing import Optional, Union

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings


class FreeDesktop:
    """
    A class responsible for FreeDesktop.org compliance and desktop integration.

    This includes creating desktop entries for application launchers, managing startup
    notifications according to the FreeDesktop Startup Notification specification,
    and ensuring proper integration with Linux desktop environments.
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def _is_linux_system() -> bool:
        """Check if running on a Linux system."""
        return os_name == "posix" and sys_platform.startswith("linux")

    @staticmethod
    def _get_desktop_file_path() -> str:
        """Get the path where the desktop file should be created."""
        return os_path.expanduser("~/.local/share/applications/ardupilot_methodic_configurator.desktop")

    @staticmethod
    def _desktop_icon_exists(desktop_file_path: str) -> bool:
        """Check if the desktop icon already exists."""
        return os_path.exists(desktop_file_path)

    @staticmethod
    def _get_virtual_env_path() -> Optional[str]:
        """Get the virtual environment path from environment variables."""
        return os_environ.get("VIRTUAL_ENV")

    @staticmethod
    def _create_desktop_entry_content(venv_path: str, icon_path: str) -> str:
        """Create the desktop entry file content."""
        # Try to use python executable directly for better compatibility
        python_exe = os_path.join(venv_path, "bin", "python")
        if os_path.exists(python_exe):
            # Use python executable directly
            exec_cmd = f"{python_exe} -m ardupilot_methodic_configurator"
        else:
            # Fallback to bash -c method
            bash_path = shutil_which("bash") or "/bin/bash"
            activate_cmd = f"source {venv_path}/bin/activate && ardupilot_methodic_configurator"
            exec_cmd = f'{bash_path} -c "{activate_cmd}"'

        return f"""[Desktop Entry]
Version=1.0
Name=ArduPilot Methodic Configurator
Comment=A clear ArduPilot configuration sequence
Exec={exec_cmd}
Icon={icon_path}
Terminal=true
Type=Application
Categories=Development;
Keywords=ardupilot;arducopter;drone;parameters;configuration;scm
StartupWMClass=ArduPilotMethodicConfigurator
StartupNotify=true
"""

    @staticmethod
    def _ensure_applications_dir_exists(desktop_file_path: str) -> str:
        """Ensure the applications directory exists and return it."""
        apps_dir = os_path.dirname(desktop_file_path)
        os_makedirs(apps_dir, exist_ok=True)
        return apps_dir

    @staticmethod
    def _write_desktop_file(desktop_file_path: str, content: str) -> None:
        """Write the desktop file content to disk."""
        with open(desktop_file_path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _set_desktop_file_permissions(desktop_file_path: str) -> None:
        """Set appropriate permissions on the desktop file."""
        os_chmod(desktop_file_path, 0o644)

    @staticmethod
    def _update_desktop_database(apps_dir: str) -> None:
        """Update the desktop database if the command is available."""
        update_desktop_db_cmd = shutil_which("update-desktop-database")
        if update_desktop_db_cmd:
            subprocess.run([update_desktop_db_cmd, apps_dir], check=False, capture_output=True)  # noqa: S603

    @staticmethod
    def create_desktop_icon_if_needed() -> None:
        """
        Create a desktop icon for the application if running in a virtual environment and icon doesn't exist.

        This function detects if we're running in a virtual environment and creates a desktop
        entry that activates the venv and runs the application with the correct icon.
        """
        # Only create desktop icon on Linux systems
        if not FreeDesktop._is_linux_system():
            return

        # Check if desktop icon already exists
        desktop_file_path = FreeDesktop._get_desktop_file_path()
        if FreeDesktop._desktop_icon_exists(desktop_file_path):
            return

        # Check if we're in a virtual environment
        venv_path = FreeDesktop._get_virtual_env_path()
        if not venv_path:
            return

        # Find the icon path
        icon_path = ProgramSettings.application_icon_filepath()
        if not icon_path:
            return

        # Create the desktop entry content
        desktop_entry = FreeDesktop._create_desktop_entry_content(venv_path, icon_path)

        # Ensure the applications directory exists
        apps_dir = FreeDesktop._ensure_applications_dir_exists(desktop_file_path)

        # Write the desktop file
        try:
            FreeDesktop._write_desktop_file(desktop_file_path, desktop_entry)
            FreeDesktop._set_desktop_file_permissions(desktop_file_path)
            FreeDesktop._update_desktop_database(apps_dir)

        except (OSError, subprocess.SubprocessError):
            logging_error("Failed to create application launch desktop icon")

    @staticmethod
    def _get_desktop_startup_id() -> Union[str, None]:
        """
        Get the DESKTOP_STARTUP_ID environment variable.

        Returns:
            The startup ID string if set, None otherwise.

        """
        return os_environ.get("DESKTOP_STARTUP_ID")

    @staticmethod
    def _send_startup_notification_complete(startup_id: str) -> None:
        """
        Send the startup notification "remove" message to indicate the application has started.

        This implements the freedesktop.org startup notification protocol.

        Args:
            startup_id: The DESKTOP_STARTUP_ID that was passed to the application

        """
        if not startup_id:
            return

        # Validate startup_id to prevent shell injection (should only contain alphanumeric chars, hyphens, underscores)
        if not re.match(r"^[a-zA-Z0-9_-]+$", startup_id):
            logging_debug("Invalid startup_id format: %s", startup_id)
            return

        try:
            # Find the full path to xdg-startup-notify for security
            xdg_notify_path = shutil_which("xdg-startup-notify")
            if xdg_notify_path:
                # Try to use xdg-startup-notify if available (part of xdg-utils)
                result = subprocess.run(  # noqa: S603
                    [xdg_notify_path, "remove", startup_id], capture_output=True, timeout=1.0, check=False
                )
                if result.returncode == 0:
                    logging_debug("Sent startup notification completion for ID: %s", startup_id)
                else:
                    logging_debug("xdg-startup-notify failed: %s", result.stderr.decode().strip())
            else:
                logging_debug("xdg-startup-notify not found in PATH")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            # If xdg-startup-notify is not available or fails, try manual X11 approach
            FreeDesktop._send_startup_notification_x11(startup_id)

    @staticmethod
    def _send_startup_notification_x11(startup_id: str) -> None:
        """
        Send startup notification completion using direct X11 ClientMessage.

        Args:
            startup_id: The DESKTOP_STARTUP_ID that was passed to the application

        """
        if not tk:
            return

        try:
            # Create a temporary Tk instance to access X11 if we don't have one yet
            temp_root = tk.Tk()
            temp_root.withdraw()  # Hide the window

            # Try to send the message using Tk's send command
            # Format: "remove: ID=<startup_id>"
            message = f"remove: ID={startup_id}"

            # Use Tk's send command to broadcast to the root window
            # This is a bit of a hack, but Tk doesn't expose X11 messaging directly
            try:
                temp_root.eval(f"send -async . {{event generate . <<StartupComplete>> -data {{{message}}}}}")

                # Also try to use the X11 atoms if available
                # _NET_STARTUP_INFO is the atom we need to send
                temp_root.eval(f"send -async . {{wm command . _NET_STARTUP_INFO {{{message}}}}}")

            except Exception:  # pylint: disable=broad-exception-caught
                # If all else fails, just log that we tried
                logging_debug("Could not send X11 startup notification message")

            temp_root.destroy()

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_debug("Failed to send X11 startup notification: %s", e)

    @staticmethod
    def setup_startup_notification(main_window: tk.Tk) -> None:
        """
        Set up startup notification for the application.

        Checks for DESKTOP_STARTUP_ID and sends the completion message when the window is ready.

        Args:
            main_window: The main Tkinter window

        """
        if not FreeDesktop._is_linux_system():
            return
        startup_id = FreeDesktop._get_desktop_startup_id() or ""
        if startup_id:
            logging_debug("Startup notification ID: %s", startup_id)

            # Send the completion message after the window is mapped
            def on_map(event: tk.Event) -> None:
                if event and event.widget == main_window:
                    FreeDesktop._send_startup_notification_complete(startup_id)
                    # Remove the binding after first map
                    main_window.unbind("<Map>", on_map_handler)

            # Bind to the Map event to know when the window is first shown
            on_map_handler = main_window.bind("<Map>", on_map)

            # Also try to send immediately in case the window is already mapped
            if main_window.winfo_viewable():
                FreeDesktop._send_startup_notification_complete(startup_id)
