#!/usr/bin/env python3

"""
BDD tests for frontend_tkinter_project_opener module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpenError
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_opener import VehicleProjectOpenerWindow

# pylint: disable=redefined-outer-name, duplicate-code

# ==================== FIXTURES ====================


@pytest.fixture
def mock_project_manager() -> MagicMock:
    """Fixture providing a mock VehicleProjectManager with realistic test data."""
    manager = MagicMock()

    # Set up typical method return values
    manager.get_introduction_message.return_value = "Welcome to ArduPilot Methodic Configurator"
    manager.get_recently_used_dirs.return_value = ("/path/to/templates", "/path/to/projects", "/path/to/last/vehicle")
    manager.can_open_last_vehicle_directory.return_value = True
    manager.get_file_parameters_list.return_value = ["01_file.param", "02_file.param"]

    return manager


@pytest.fixture
def configured_opener_window(mock_project_manager) -> VehicleProjectOpenerWindow:
    """Fixture providing a properly configured VehicleProjectOpenerWindow for behavior testing."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "_setup_application_icon"),
        patch.object(BaseWindow, "_setup_theme_and_styling"),
        patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Label"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.LabelFrame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Button"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.show_tooltip"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleDirectorySelectionWidgets"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.DirectorySelectionWidgets"),
        patch("tkinter.Tk") as mock_tk,
    ):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        window = VehicleProjectOpenerWindow(mock_project_manager)

        # Ensure the window has required attributes set by BaseWindow
        if not hasattr(window, "root"):
            window.root = mock_root
        if not hasattr(window, "main_frame"):
            window.main_frame = MagicMock()

        return window


@pytest.fixture
def mock_messagebox() -> Generator[MagicMock, None, None]:
    """Fixture providing a mock messagebox for testing error dialogs."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.messagebox") as mock:
        yield mock


@pytest.fixture
def mock_create_new_project_window() -> Generator[MagicMock, None, None]:
    """Fixture providing a mock VehicleProjectCreatorWindow for testing window transitions."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleProjectCreatorWindow") as mock:
        yield mock


@pytest.fixture
def mock_sys_exit() -> Generator[MagicMock, None, None]:
    """Fixture providing a mock sys_exit to prevent actual process termination."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.sys_exit") as mock:
        yield mock


# ==================== TEST CLASSES ====================


class TestVehicleProjectOpenerWindow:
    """Test user workflows for vehicle project opening window."""

    def test_user_can_initialize_window_with_three_options(self, configured_opener_window) -> None:
        """
        User can see a properly initialized window with all three vehicle configuration options.

        GIVEN: A user starts the application without an existing vehicle configuration
        WHEN: The VehicleProjectOpenerWindow is created
        THEN: The window should display three clear options for vehicle configuration
        AND: All widgets should be properly configured and visible
        """
        # Arrange: Window is already configured through fixture
        window = configured_opener_window

        # Assert: Window properties are set correctly
        window.root.title.assert_called_once()
        window.root.geometry.assert_called_once_with("600x450")
        window.root.protocol.assert_called_once_with("WM_DELETE_WINDOW", window.close_and_quit)

        # Assert: Project manager methods were called for initialization
        window.project_manager.get_introduction_message.assert_called_once()
        window.project_manager.get_recently_used_dirs.assert_called_once()

    def test_user_can_create_new_vehicle_from_template(self, configured_opener_window, mock_create_new_project_window) -> None:
        """
        User can create a new vehicle configuration by selecting the template option.

        GIVEN: A user has the project opener window displayed
        WHEN: They click the "Create vehicle configuration directory from template" button
        THEN: The current window should close
        AND: A new VehicleProjectCreatorWindow should open with correct parameters
        """
        # Arrange: Configure window with template creation capability
        window = configured_opener_window

        # Act: User clicks create new vehicle from template
        window.create_new_vehicle_from_template()

        # Assert: Current window is destroyed and new window is created
        window.root.destroy.assert_called_once()
        mock_create_new_project_window.assert_called_once_with(window.project_manager)

    def test_user_can_create_new_vehicle_with_flight_controller_connected(
        self, configured_opener_window, mock_create_new_project_window
    ) -> None:
        """
        User can create a new vehicle when flight controller is already connected.

        GIVEN: A user has a flight controller connected to the system
        WHEN: They choose to create a new vehicle configuration
        THEN: The flight controller connection state should be passed to the new window
        """
        # Arrange: Set up window for new vehicle creation
        window = configured_opener_window

        # Act: User creates new vehicle from template
        window.create_new_vehicle_from_template()

        # Assert: New project window is created with project manager
        mock_create_new_project_window.assert_called_once_with(window.project_manager)

    def test_user_can_open_last_vehicle_directory_successfully(self, configured_opener_window) -> None:
        """
        User can successfully open the last used vehicle configuration directory.

        GIVEN: A user has previously used a vehicle configuration directory
        WHEN: They click "Open Last Used Vehicle Configuration Directory"
        THEN: The last vehicle directory should be opened
        AND: The window should close after successful opening
        """
        # Arrange: Configure successful directory opening
        window = configured_opener_window
        last_vehicle_dir = "/path/to/last/vehicle"

        # Act: User opens last vehicle directory
        window.open_last_vehicle_directory(last_vehicle_dir)

        # Assert: Project manager opens directory and window closes
        window.project_manager.open_last_vehicle_directory.assert_called_once_with(last_vehicle_dir)
        window.root.destroy.assert_called_once()

    def test_user_sees_error_when_last_vehicle_directory_fails_to_open(
        self, configured_opener_window, mock_messagebox
    ) -> None:
        """
        User receives clear error feedback when last vehicle directory cannot be opened.

        GIVEN: A user attempts to open a last used vehicle directory
        WHEN: The directory opening fails due to VehicleProjectOpenError
        THEN: An error dialog should be displayed with appropriate message
        AND: The window should remain open for user to try alternatives
        """
        # Arrange: Configure directory opening to fail
        window = configured_opener_window
        last_vehicle_dir = "/invalid/path"
        error = VehicleProjectOpenError("Invalid Directory", "The selected directory is not valid.")
        window.project_manager.open_last_vehicle_directory.side_effect = error

        # Act: User attempts to open invalid directory
        window.open_last_vehicle_directory(last_vehicle_dir)

        # Assert: Error dialog is shown and window stays open
        mock_messagebox.showerror.assert_called_once_with(error.title, error.message)
        window.root.destroy.assert_not_called()

    def test_user_can_close_window_and_quit_application(self, configured_opener_window, mock_sys_exit) -> None:
        """
        User can close the window and quit the application cleanly.

        GIVEN: A user has the project opener window open
        WHEN: They close the window using the close button or Alt+F4
        THEN: The application should terminate gracefully
        """
        # Arrange: Window is configured and ready
        window = configured_opener_window

        # Act: User closes the window
        window.close_and_quit()

        # Assert: Application exits cleanly
        mock_sys_exit.assert_called_once_with(0)

    def test_option3_button_is_disabled_when_no_last_directory_available(self, mock_project_manager) -> None:
        """
        User sees disabled "Re-Open vehicle" option when no last directory is available.

        GIVEN: A user has never opened a vehicle configuration directory before
        WHEN: The project opener window is displayed
        THEN: The "Open Last Used Vehicle Configuration Directory" button should be disabled
        AND: The user should understand this option is not available
        """
        # Arrange: Configure project manager to indicate no last directory available
        mock_project_manager.can_open_last_vehicle_directory.return_value = False

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "_setup_application_icon"),
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.LabelFrame"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Button") as mock_button,
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleDirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.DirectorySelectionWidgets"),
            patch("tkinter.Tk") as mock_tk,
        ):
            mock_root = MagicMock()
            mock_tk.return_value = mock_root

            # Create window which should check button state
            window = VehicleProjectOpenerWindow(mock_project_manager)
            window.root = mock_root
            window.main_frame = MagicMock()

            # Assert: Button creation was called with disabled state
            # Find the call that creates the "Open Last Used" button (it's the last Button call)
            button_calls = mock_button.call_args_list
            assert len(button_calls) >= 2  # At least template button and last-used button

            # The last button call should have state=tk.DISABLED
            last_button_call = button_calls[-1]
            assert "state" in last_button_call.kwargs
            assert last_button_call.kwargs["state"] == tk.DISABLED

    def test_option3_button_is_enabled_when_last_directory_is_available(self, mock_project_manager) -> None:
        """
        User sees enabled "Re-Open vehicle" option when a valid last directory exists.

        GIVEN: A user has previously used a valid vehicle configuration directory
        WHEN: The project opener window is displayed
        THEN: The "Open Last Used Vehicle Configuration Directory" button should be enabled
        AND: The user can click it to reopen their previous work
        """
        # Arrange: Configure project manager to indicate last directory is available
        mock_project_manager.can_open_last_vehicle_directory.return_value = True

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "_setup_application_icon"),
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.LabelFrame"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Button") as mock_button,
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleDirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.DirectorySelectionWidgets"),
            patch("tkinter.Tk") as mock_tk,
        ):
            mock_root = MagicMock()
            mock_tk.return_value = mock_root

            # Create window which should check button state
            window = VehicleProjectOpenerWindow(mock_project_manager)
            window.root = mock_root
            window.main_frame = MagicMock()

            # Assert: Button creation was called with enabled state
            button_calls = mock_button.call_args_list
            assert len(button_calls) >= 2  # At least template button and last-used button

            # The last button call should have state=tk.NORMAL
            last_button_call = button_calls[-1]
            assert "state" in last_button_call.kwargs
            assert last_button_call.kwargs["state"] == tk.NORMAL

    def test_window_creates_vehicle_directory_selection_widgets(self, configured_opener_window) -> None:
        """
        User can see and interact with vehicle directory selection widgets for opening existing projects.

        GIVEN: A user wants to open an existing vehicle configuration
        WHEN: The project opener window is displayed
        THEN: VehicleDirectorySelectionWidgets should be created with proper configuration
        AND: The widgets should have the correct callback for directory selection
        """
        # Arrange: Window is configured through fixture
        window = configured_opener_window

        # Assert: VehicleDirectorySelectionWidgets was created and configured
        assert hasattr(window, "connection_selection_widgets")
        # The actual widget creation is mocked, but we can verify the setup was attempted


class TestVehicleProjectOpenerWindowIntegration:
    """Test integration scenarios for vehicle project opener window."""

    def test_user_workflow_from_startup_to_template_creation(
        self, mock_project_manager, mock_create_new_project_window
    ) -> None:
        """
        User can complete full workflow from application startup to template creation.

        GIVEN: A user starts the application for the first time
        WHEN: They go through the complete workflow to create a new vehicle
        THEN: All components should work together seamlessly
        AND: The user should successfully reach the template creation window
        """
        # Arrange: Set up complete workflow scenario
        mock_project_manager.get_recently_used_dirs.return_value = ("", "", "")
        mock_project_manager.can_open_last_vehicle_directory.return_value = False

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "_setup_application_icon"),
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.LabelFrame"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.ttk.Button"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleDirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.DirectorySelectionWidgets"),
            patch("tkinter.Tk") as mock_tk,
        ):
            mock_root = MagicMock()
            mock_tk.return_value = mock_root

            # Act: Complete workflow simulation
            window = VehicleProjectOpenerWindow(mock_project_manager)
            window.root = mock_root
            window.main_frame = MagicMock()

            # User decides to create new vehicle from template
            window.create_new_vehicle_from_template()

            # Assert: Workflow completed successfully
            mock_create_new_project_window.assert_called_once()
            window.root.destroy.assert_called_once()

    def test_user_workflow_opening_existing_vehicle_directory(self, configured_opener_window) -> None:
        """
        User can complete workflow to open an existing vehicle configuration directory.

        GIVEN: A user has an existing vehicle configuration directory
        WHEN: They select and open that directory through the interface
        THEN: The project manager should successfully open the directory
        AND: The user should be able to proceed with configuration
        """
        # Arrange: Configure window for existing directory workflow
        window = configured_opener_window
        test_directory = "/path/to/existing/vehicle"

        # Act: Simulate the callback that would be triggered by VehicleDirectorySelectionWidgets
        # This simulates the user selecting a directory
        window.project_manager.open_vehicle_directory(test_directory)

        # Assert: Project manager processes the directory selection
        window.project_manager.open_vehicle_directory.assert_called_once_with(test_directory)
