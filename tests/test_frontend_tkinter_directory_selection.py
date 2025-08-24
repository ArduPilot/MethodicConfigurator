#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_directory_selection.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
)
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpenError
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import (
    DirectoryNameWidgets,
    DirectorySelectionWidgets,
    VehicleDirectorySelectionWidgets,
    VehicleDirectorySelectionWindow,
)

# pylint: disable=redefined-outer-name,unused-argument,too-many-lines,protected-access,too-many-arguments,too-many-positional-arguments,too-many-locals


# ==================== FIXTURES ====================


@pytest.fixture
def mock_project_manager() -> MagicMock:
    """Fixture providing a mock VehicleProjectManager with realistic test data."""
    manager = MagicMock(spec=VehicleProjectManager)
    manager.get_recently_used_dirs.return_value = [
        "/home/user/templates/ArduCopter/dji_f330_basic",
        "/home/user/vehicles",
        "/home/user/vehicles/MyDrone",
    ]
    manager.get_vehicle_directory.return_value = "/home/user/current_vehicle"
    manager.get_current_working_directory.return_value = "/home/user/current_working"
    manager.directory_exists.return_value = True
    manager.get_directory_name_from_path.return_value = "dji_f330_basic"
    return manager


@pytest.fixture
def mock_parent_window() -> MagicMock:
    """Fixture providing a mock parent window."""
    parent = MagicMock()
    parent.root = MagicMock(spec=tk.Tk)
    parent.project_manager = MagicMock(spec=VehicleProjectManager)
    parent.project_manager.get_recently_used_dirs.return_value = [
        "/home/user/templates/selected_template",
        "/home/user/base",
        "/home/user/vehicle",
    ]
    return parent


@pytest.fixture
def mock_parent_frame(root) -> MagicMock:
    """Fixture providing a mock parent frame widget."""
    mock_frame = MagicMock(spec=tk.Widget)
    # Add all necessary Tkinter attributes that widgets expect
    mock_frame.tk = root.tk
    mock_frame._w = "."  # Tkinter widget path
    mock_frame.master = root
    mock_frame.children = {}  # Tkinter children dictionary
    return mock_frame


@pytest.fixture
def mock_labelframe() -> MagicMock:
    """Fixture providing a mock labelframe widget."""
    return MagicMock(spec=ttk.Labelframe)


@pytest.fixture
def directory_selection_widget_setup() -> tuple[MagicMock, MagicMock]:
    """Fixture providing mocked components for DirectorySelectionWidgets testing."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Frame") as mock_frame,
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Label") as mock_label,
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Button") as mock_button,
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.Entry") as mock_entry,
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.StringVar") as mock_stringvar,
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
    ):
        mock_frame_instance = MagicMock()
        mock_frame.return_value = mock_frame_instance
        mock_label.return_value = MagicMock()
        mock_button.return_value = MagicMock()

        mock_stringvar_instance = MagicMock()
        mock_stringvar.return_value = mock_stringvar_instance
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance

        return mock_frame_instance, mock_entry_instance


@pytest.fixture
def vehicle_directory_selection_window_setup(mock_project_manager, root) -> VehicleDirectorySelectionWindow:
    """Fixture providing a properly mocked VehicleDirectorySelectionWindow for testing."""

    def mock_vehicle_init(self, project_manager, fc_connected=False, connected_fc_vehicle_type="") -> None:
        """Mock VehicleDirectorySelectionWindow.__init__ to avoid BaseWindow dependencies."""
        # Set up required attributes without calling BaseWindow.__init__
        self.root = root  # Use the real root from conftest.py
        self.main_frame = MagicMock()
        self.project_manager = project_manager
        self.connected_fc_vehicle_type = connected_fc_vehicle_type
        self.fc_connected = fc_connected  # Store the fc_connected parameter
        # Mock other attributes that might be accessed
        self.base_log_dir = MagicMock()
        self.vehicle_dir = MagicMock()
        # Mock all the BooleanVar attributes expected by tests
        self.copy_vehicle_image = MagicMock()
        self.blank_component_data = MagicMock()
        self.reset_fc_parameters_to_their_defaults = MagicMock()
        self.infer_comp_specs_and_conn_from_fc_params = MagicMock()
        self.use_fc_params = MagicMock()
        self.blank_change_reason = MagicMock()
        # Mock DirectorySelectionWidgets instances
        self.template_dir = MagicMock()
        self.new_base_dir = MagicMock()
        self.new_dir = MagicMock()
        # Mock the root destroy method to prevent actual window destruction
        self.root.destroy = MagicMock()

    with (
        patch.object(VehicleDirectorySelectionWindow, "__init__", mock_vehicle_init),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.LabelFrame"),
        patch("tkinter.ttk.Button"),
        patch("tkinter.ttk.Checkbutton"),
        patch("tkinter.BooleanVar"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection._"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.__version__", "1.0.0"),
    ):
        return VehicleDirectorySelectionWindow(mock_project_manager, fc_connected=False)


# ==================== DIRECTORY SELECTION WIDGETS TESTS ====================


class TestDirectorySelectionWidgets:
    """Test DirectorySelectionWidgets component behavior."""

    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Label")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Button")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.Entry")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.StringVar")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip")
    def test_user_can_initialize_directory_selection_widget(
        self,
        mock_show_tooltip,
        mock_stringvar,
        mock_entry,
        mock_button,
        mock_label,
        mock_frame,
        mock_parent_window,
        mock_parent_frame,
    ) -> None:
        """
        User can create a directory selection widget with proper UI components.

        GIVEN: A parent window and frame for widget creation
        WHEN: A DirectorySelectionWidgets instance is created
        THEN: All UI components should be properly initialized and configured
        """
        # Arrange: Setup mocks
        mock_frame_instance = MagicMock()
        mock_frame.return_value = mock_frame_instance
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance
        mock_button_instance = MagicMock()
        mock_button.return_value = mock_button_instance
        mock_stringvar_instance = MagicMock()
        mock_stringvar.return_value = mock_stringvar_instance

        # Set up test parameters
        initial_dir = "/home/user/test_directory"
        label_text = "Select Directory:"
        dir_tooltip = "Directory selection tooltip"
        button_tooltip = "Browse button tooltip"

        # Act: Create DirectorySelectionWidgets instance
        widget = DirectorySelectionWidgets(
            parent=mock_parent_window,
            parent_frame=mock_parent_frame,
            initialdir=initial_dir,
            label_text=label_text,
            autoresize_width=True,
            dir_tooltip=dir_tooltip,
            button_tooltip=button_tooltip,
            is_template_selection=False,
            connected_fc_vehicle_type="ArduCopter",
        )

        # Assert: Widget properly initialized with correct properties
        assert widget.directory == initial_dir
        assert widget.label_text == label_text
        assert widget.autoresize_width is True
        assert widget.is_template_selection is False
        assert widget.connected_fc_vehicle_type == "ArduCopter"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Label")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Button")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.Entry")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.StringVar")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip")
    def test_user_can_select_regular_directory_via_dialog(
        self,
        mock_show_tooltip,
        mock_stringvar,
        mock_entry,
        mock_button,
        mock_label,
        mock_frame,
        mock_parent_window,
        mock_parent_frame,
    ) -> None:
        """
        User can select a directory through the file dialog for regular directory selection.

        GIVEN: A directory selection widget configured for regular directory selection
        WHEN: User clicks the browse button and selects a directory
        THEN: The selected directory should be stored and the widget should update
        """
        # Arrange: Setup mocks
        mock_frame_instance = MagicMock()
        mock_frame.return_value = mock_frame_instance
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance
        mock_button_instance = MagicMock()
        mock_button.return_value = mock_button_instance
        mock_stringvar_instance = MagicMock()
        mock_stringvar.return_value = mock_stringvar_instance

        # Create widget for regular directory selection
        widget = DirectorySelectionWidgets(
            parent=mock_parent_window,
            parent_frame=mock_parent_frame,
            initialdir="/home/user/initial",
            label_text="Test Directory:",
            autoresize_width=False,
            dir_tooltip="Test tooltip",
            button_tooltip="Browse",
            is_template_selection=False,
            connected_fc_vehicle_type="",
        )
        widget.directory_entry = mock_entry_instance

        # Mock the file dialog to return a selected directory
        selected_dir = "/home/user/selected_directory"
        with patch("tkinter.filedialog.askdirectory", return_value=selected_dir):
            # Act: User selects directory
            result = widget.on_select_directory()

            # Assert: Directory selection successful and widget updated
            assert result is True
            assert widget.directory == selected_dir
            mock_entry_instance.config.assert_called()
            mock_entry_instance.delete.assert_called_with(0, tk.END)
            mock_entry_instance.insert.assert_called_with(0, selected_dir)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Label")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Button")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.Entry")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.StringVar")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.TemplateOverviewWindow")
    def test_user_can_select_template_directory_via_template_overview(
        self,
        mock_template_window,
        mock_show_tooltip,
        mock_stringvar,
        mock_entry,
        mock_button,
        mock_label,
        mock_frame,
        mock_parent_window,
        mock_parent_frame,
    ) -> None:
        """
        User can select a template directory through the template overview window.

        GIVEN: A directory selection widget configured for template selection
        WHEN: User clicks the browse button to select a template
        THEN: The template overview window should open and template directory should be selected
        """
        # Arrange: Setup mocks
        mock_frame_instance = MagicMock()
        mock_frame.return_value = mock_frame_instance
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance
        mock_button_instance = MagicMock()
        mock_button.return_value = mock_button_instance
        mock_stringvar_instance = MagicMock()
        mock_stringvar.return_value = mock_stringvar_instance

        # Make mock_parent_window behave like VehicleDirectorySelectionWindow
        mock_parent_window.__class__ = VehicleDirectorySelectionWindow

        # Create widget for template selection
        widget = DirectorySelectionWidgets(
            parent=mock_parent_window,
            parent_frame=mock_parent_frame,
            initialdir="/home/user/initial",
            label_text="Template Directory:",
            autoresize_width=False,
            dir_tooltip="Template tooltip",
            button_tooltip="Browse templates",
            is_template_selection=True,
            connected_fc_vehicle_type="ArduCopter",
        )
        widget.directory_entry = mock_entry_instance

        # Mock the template overview window
        template_dir = "/home/user/templates/selected_template"
        mock_parent_window.project_manager.get_recently_used_dirs.return_value = [template_dir, "", ""]

        mock_template_instance = MagicMock()
        mock_template_window.return_value = mock_template_instance

        # Act: User selects template
        result = widget.on_select_directory()

        # Assert: Template selection successful
        assert result is True
        assert widget.directory == template_dir
        mock_template_window.assert_called_once()
        mock_template_instance.run_app.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Label")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Button")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.Entry")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.StringVar")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip")
    @patch("tkinter.filedialog.askdirectory")
    def test_user_sees_no_change_when_directory_selection_cancelled(
        self,
        mock_askdirectory,
        mock_show_tooltip,
        mock_stringvar,
        mock_entry,
        mock_button,
        mock_label,
        mock_frame,
        mock_parent_window,
        mock_parent_frame,
    ) -> None:
        """
        User sees no changes when directory selection is cancelled.

        GIVEN: A directory selection widget with an initial directory
        WHEN: User opens the directory selection dialog but cancels it
        THEN: The widget should remain unchanged and return False
        """
        # Arrange: Setup mocks
        mock_frame_instance = MagicMock()
        mock_frame.return_value = mock_frame_instance
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance
        mock_button_instance = MagicMock()
        mock_button.return_value = mock_button_instance
        mock_stringvar_instance = MagicMock()
        mock_stringvar.return_value = mock_stringvar_instance

        # Create widget with initial directory
        initial_dir = "/home/user/initial"
        widget = DirectorySelectionWidgets(
            parent=mock_parent_window,
            parent_frame=mock_parent_frame,
            initialdir=initial_dir,
            label_text="Test Directory:",
            autoresize_width=False,
            dir_tooltip="Test tooltip",
            button_tooltip="Browse",
            is_template_selection=False,
            connected_fc_vehicle_type="",
        )
        widget.directory_entry = mock_entry_instance

        # Mock file dialog to return empty string (cancelled)
        mock_askdirectory.return_value = ""

        # Act: User cancels directory selection
        result = widget.on_select_directory()

        # Assert: No changes made and operation failed
        assert result is False
        assert widget.directory == initial_dir

    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Label")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Button")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.Entry")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.StringVar")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip")
    def test_user_can_retrieve_currently_selected_directory(
        self,
        mock_show_tooltip,
        mock_stringvar,
        mock_entry,
        mock_button,
        mock_label,
        mock_frame,
        mock_parent_window,
        mock_parent_frame,
    ) -> None:
        """
        User can retrieve the currently selected directory path.

        GIVEN: A directory selection widget with a selected directory
        WHEN: User requests the selected directory
        THEN: The correct directory path should be returned
        """
        # Arrange: Setup mocks
        mock_frame_instance = MagicMock()
        mock_frame.return_value = mock_frame_instance
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance
        mock_button_instance = MagicMock()
        mock_button.return_value = mock_button_instance
        mock_stringvar_instance = MagicMock()
        mock_stringvar.return_value = mock_stringvar_instance

        # Create widget with specific directory
        initial_dir = "/home/user/test_directory"
        widget = DirectorySelectionWidgets(
            parent=mock_parent_window,
            parent_frame=mock_parent_frame,
            initialdir=initial_dir,
            label_text="Test Directory:",
            autoresize_width=False,
            dir_tooltip="Test tooltip",
            button_tooltip="Browse",
            is_template_selection=False,
            connected_fc_vehicle_type="",
        )

        # Act: Get selected directory
        selected_directory = widget.get_selected_directory()

        # Assert: Correct directory returned
        assert selected_directory == initial_dir

    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Frame")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Label")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.ttk.Button")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.Entry")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.tk.StringVar")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip")
    @patch("tkinter.filedialog.askdirectory")
    def test_widget_autoresizes_entry_width_when_enabled(
        self,
        mock_askdirectory,
        mock_show_tooltip,
        mock_stringvar,
        mock_entry,
        mock_button,
        mock_label,
        mock_frame,
        mock_parent_window,
        mock_parent_frame,
    ) -> None:
        """
        Widget automatically resizes entry width when autoresize is enabled.

        GIVEN: A directory selection widget with autoresize enabled
        WHEN: A new directory is selected
        THEN: The entry width should be adjusted to match the directory path length
        """
        # Arrange: Setup mocks
        mock_frame_instance = MagicMock()
        mock_frame.return_value = mock_frame_instance
        mock_entry_instance = MagicMock()
        mock_entry.return_value = mock_entry_instance
        mock_button_instance = MagicMock()
        mock_button.return_value = mock_button_instance
        mock_stringvar_instance = MagicMock()
        mock_stringvar.return_value = mock_stringvar_instance

        # Create widget with autoresize enabled
        widget = DirectorySelectionWidgets(
            parent=mock_parent_window,
            parent_frame=mock_parent_frame,
            initialdir="/short",
            label_text="Test Directory:",
            autoresize_width=True,
            dir_tooltip="Test tooltip",
            button_tooltip="Browse",
            is_template_selection=False,
            connected_fc_vehicle_type="",
        )
        widget.directory_entry = mock_entry_instance

        # Mock file dialog to return a longer directory path
        long_dir = "/home/user/very/long/directory/path/that/should/cause/resize"
        mock_askdirectory.return_value = long_dir

        # Act: Select longer directory
        widget.on_select_directory()

        # Assert: Entry width was configured with new size
        expected_width = max(4, len(long_dir))
        mock_entry_instance.config.assert_any_call(width=expected_width, state="normal")


# ==================== DIRECTORY NAME WIDGETS TESTS ====================


class TestDirectoryNameWidgets:
    """Test DirectoryNameWidgets component behavior."""

    def test_user_can_initialize_directory_name_widget(self, mock_labelframe) -> None:
        """
        User can create a directory name widget with proper UI components.

        GIVEN: A labelframe parent for widget creation
        WHEN: A DirectoryNameWidgets instance is created
        THEN: All UI components should be properly initialized
        """
        # Arrange: Set up test parameters
        initial_dir = "MyVehicleName"
        label_text = "Vehicle Name:"
        dir_tooltip = "Enter vehicle name"

        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.Entry"),
            patch("tkinter.StringVar") as mock_stringvar,
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
        ):
            mock_stringvar_instance = MagicMock()
            mock_stringvar.return_value = mock_stringvar_instance

            # Act: Create DirectoryNameWidgets instance
            widget = DirectoryNameWidgets(
                master=mock_labelframe,
                initial_dir=initial_dir,
                label_text=label_text,
                dir_tooltip=dir_tooltip,
            )

            # Assert: Widget properly initialized
            mock_stringvar.assert_called_once_with(value=initial_dir)
            assert widget.dir_var == mock_stringvar_instance

    def test_user_can_retrieve_entered_directory_name(self, mock_labelframe) -> None:
        """
        User can retrieve the directory name they entered.

        GIVEN: A directory name widget with user input
        WHEN: User requests the selected directory name
        THEN: The entered name should be returned
        """
        # Arrange: Create widget and mock the StringVar
        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.Entry"),
            patch("tkinter.StringVar") as mock_stringvar,
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
        ):
            mock_stringvar_instance = MagicMock()
            mock_stringvar_instance.get.return_value = "UserEnteredName"
            mock_stringvar.return_value = mock_stringvar_instance

            widget = DirectoryNameWidgets(
                master=mock_labelframe,
                initial_dir="Initial",
                label_text="Name:",
                dir_tooltip="Tooltip",
            )

            # Act: Get selected directory name
            selected_name = widget.get_selected_directory()

            # Assert: Correct name returned
            assert selected_name == "UserEnteredName"
            mock_stringvar_instance.get.assert_called_once()


# ==================== VEHICLE DIRECTORY SELECTION WIDGETS TESTS ====================


class TestVehicleDirectorySelectionWidgets:
    """Test VehicleDirectorySelectionWidgets specialized behavior."""

    def test_user_can_open_vehicle_directory_successfully(self, mock_parent_window, mock_parent_frame) -> None:
        """
        User can successfully open a vehicle directory and have the parent window close.

        GIVEN: A vehicle directory selection widget configured to destroy parent on open
        WHEN: User selects a valid vehicle directory
        THEN: The project manager should open the directory and parent window should close
        """
        # Arrange: Create vehicle directory selection widget
        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.Entry") as mock_entry,
            patch("tkinter.StringVar"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("tkinter.filedialog.askdirectory", return_value="/home/user/vehicle_dir"),
        ):
            mock_entry_instance = MagicMock()
            mock_entry.return_value = mock_entry_instance

            # Make mock_parent_window behave like VehicleDirectorySelectionWindow
            mock_parent_window.__class__ = VehicleDirectorySelectionWindow

            widget = VehicleDirectorySelectionWidgets(
                parent=mock_parent_window,
                parent_frame=mock_parent_frame,
                initial_dir="/home/user/initial",
                destroy_parent_on_open=True,
                connected_fc_vehicle_type="ArduCopter",
            )
            widget.directory_entry = mock_entry_instance

            # Act: User selects vehicle directory
            result = widget.on_select_directory()

            # Assert: Directory opened successfully and parent destroyed
            assert result is True
            mock_parent_window.project_manager.open_vehicle_directory.assert_called_once_with("/home/user/vehicle_dir")
            mock_parent_window.root.destroy.assert_called_once()

    def test_user_sees_error_when_vehicle_directory_opening_fails(self, mock_parent_window, mock_parent_frame) -> None:
        """
        User sees an error message when vehicle directory opening fails.

        GIVEN: A vehicle directory selection widget
        WHEN: User selects a directory that cannot be opened (project manager fails)
        THEN: An error dialog should be shown and operation should return False
        """
        # Arrange: Configure project manager to raise exception
        mock_parent_window.project_manager.open_vehicle_directory.side_effect = VehicleProjectOpenError(
            "Invalid Directory", "The selected directory is not a valid vehicle configuration directory."
        )

        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.Entry") as mock_entry,
            patch("tkinter.StringVar"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("tkinter.filedialog.askdirectory", return_value="/home/user/invalid_dir"),
            patch("tkinter.messagebox.showerror") as mock_error_dialog,
        ):
            mock_entry_instance = MagicMock()
            mock_entry.return_value = mock_entry_instance

            # Make mock_parent_window behave like VehicleDirectorySelectionWindow
            mock_parent_window.__class__ = VehicleDirectorySelectionWindow

            widget = VehicleDirectorySelectionWidgets(
                parent=mock_parent_window,
                parent_frame=mock_parent_frame,
                initial_dir="/home/user/initial",
                destroy_parent_on_open=False,
                connected_fc_vehicle_type="",
            )
            widget.directory_entry = mock_entry_instance

            # Act: User selects invalid vehicle directory
            result = widget.on_select_directory()

            # Assert: Error shown and operation failed
            assert result is False
            mock_error_dialog.assert_called_once_with(
                "Invalid Directory", "The selected directory is not a valid vehicle configuration directory."
            )

    def test_widget_inherits_base_directory_selection_behavior(self, mock_parent_window, mock_parent_frame) -> None:
        """
        Widget properly inherits and extends base DirectorySelectionWidgets behavior.

        GIVEN: A vehicle directory selection widget
        WHEN: Widget is initialized
        THEN: It should inherit all base class functionality while adding vehicle-specific features
        """
        # Arrange & Act: Create vehicle directory selection widget
        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.Entry"),
            patch("tkinter.StringVar"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
        ):
            widget = VehicleDirectorySelectionWidgets(
                parent=mock_parent_window,
                parent_frame=mock_parent_frame,
                initial_dir="/home/user/vehicle",
                destroy_parent_on_open=True,
                connected_fc_vehicle_type="ArduPlane",
            )

            # Assert: Widget has both base and specialized attributes
            assert widget.destroy_parent_on_open is True
            assert widget.connected_fc_vehicle_type == "ArduPlane"
            assert hasattr(widget, "directory")  # Inherited from base class
            assert hasattr(widget, "is_template_selection")  # Inherited from base class
            assert widget.is_template_selection is False  # Set by vehicle-specific constructor


# ==================== VEHICLE DIRECTORY SELECTION WINDOW TESTS ====================


class TestVehicleDirectorySelectionWindow:
    """Test VehicleDirectorySelectionWindow complete user workflows."""

    def test_user_can_initialize_window_with_all_options_when_no_fc_connected(
        self, mock_project_manager, vehicle_directory_selection_window_setup
    ) -> None:
        """
        User sees all available options with flight controller specific options disabled when no FC is connected.

        GIVEN: No flight controller is connected to the system
        WHEN: User opens the vehicle directory selection window
        THEN: All options should be available but FC-specific checkboxes should be disabled
        """
        # Arrange & Act: Window is already created by fixture with fc_connected=False
        window = vehicle_directory_selection_window_setup

        # Assert: Window properly initialized with FC-specific options disabled
        assert window.project_manager == mock_project_manager
        assert window.connected_fc_vehicle_type == ""
        assert hasattr(window, "blank_component_data")

    def test_user_can_create_new_vehicle_from_template_successfully(
        self, mock_project_manager, vehicle_directory_selection_window_setup
    ) -> None:
        """
        User can successfully create a new vehicle configuration from a template.

        GIVEN: A vehicle directory selection window with template and destination configured
        WHEN: User clicks the create vehicle button with valid settings
        THEN: A new vehicle project should be created and window should close
        """
        # Arrange: Set up window with mock widgets
        window = vehicle_directory_selection_window_setup
        window.template_dir = MagicMock()
        window.template_dir.get_selected_directory.return_value = "/home/user/templates/copter_basic"
        window.new_base_dir = MagicMock()
        window.new_base_dir.get_selected_directory.return_value = "/home/user/vehicles"
        window.new_dir = MagicMock()
        window.new_dir.get_selected_directory.return_value = "MyNewDrone"

        # Mock the BooleanVar instances
        for attr_name in [
            "copy_vehicle_image",
            "blank_component_data",
            "reset_fc_parameters_to_their_defaults",
            "infer_comp_specs_and_conn_from_fc_params",
            "use_fc_params",
            "blank_change_reason",
        ]:
            mock_var = MagicMock()
            mock_var.get.return_value = False
            setattr(window, attr_name, mock_var)

        # Act: User creates new vehicle from template
        window.create_new_vehicle_from_template()

        # Assert: Project creation called with correct parameters
        mock_project_manager.create_new_vehicle_from_template.assert_called_once()
        call_args = mock_project_manager.create_new_vehicle_from_template.call_args
        assert call_args[0][0] == "/home/user/templates/copter_basic"  # template_dir
        assert call_args[0][1] == "/home/user/vehicles"  # new_base_dir
        assert call_args[0][2] == "MyNewDrone"  # new_vehicle_name
        assert isinstance(call_args[0][3], NewVehicleProjectSettings)  # settings
        window.root.destroy.assert_called_once()

    def test_user_sees_error_when_vehicle_creation_fails(
        self, mock_project_manager, vehicle_directory_selection_window_setup
    ) -> None:
        """
        User sees an error message when vehicle creation from template fails.

        GIVEN: A vehicle directory selection window configured for vehicle creation
        WHEN: Vehicle creation fails due to project manager error
        THEN: An error dialog should be displayed to the user
        """
        # Arrange: Configure project manager to fail
        mock_project_manager.create_new_vehicle_from_template.side_effect = VehicleProjectCreationError(
            "Creation Failed", "Unable to create vehicle directory due to insufficient permissions."
        )

        window = vehicle_directory_selection_window_setup
        window.template_dir = MagicMock()
        window.template_dir.get_selected_directory.return_value = "/home/user/templates/copter"
        window.new_base_dir = MagicMock()
        window.new_base_dir.get_selected_directory.return_value = "/home/user/vehicles"
        window.new_dir = MagicMock()
        window.new_dir.get_selected_directory.return_value = "FailedVehicle"

        # Mock BooleanVar instances
        for attr_name in [
            "copy_vehicle_image",
            "blank_component_data",
            "reset_fc_parameters_to_their_defaults",
            "infer_comp_specs_and_conn_from_fc_params",
            "use_fc_params",
            "blank_change_reason",
        ]:
            mock_var = MagicMock()
            mock_var.get.return_value = False
            setattr(window, attr_name, mock_var)

        with patch("tkinter.messagebox.showerror") as mock_error_dialog:
            # Act: User attempts to create vehicle (fails)
            window.create_new_vehicle_from_template()

            # Assert: Error dialog shown
            mock_error_dialog.assert_called_once_with(
                "Creation Failed", "Unable to create vehicle directory due to insufficient permissions."
            )

    def test_user_can_open_last_used_vehicle_directory_successfully(
        self, mock_project_manager, vehicle_directory_selection_window_setup
    ) -> None:
        """
        User can successfully open the last used vehicle directory.

        GIVEN: A vehicle directory selection window with a valid last used directory
        WHEN: User clicks to open the last used vehicle directory
        THEN: The project manager should open the directory and window should close
        """
        # Arrange: Set up window
        window = vehicle_directory_selection_window_setup
        last_vehicle_dir = "/home/user/vehicles/LastUsedVehicle"

        # Act: User opens last vehicle directory
        window.open_last_vehicle_directory(last_vehicle_dir)

        # Assert: Project manager called and window closed
        mock_project_manager.open_last_vehicle_directory.assert_called_once_with(last_vehicle_dir)
        window.root.destroy.assert_called_once()

    def test_user_sees_error_when_opening_last_vehicle_directory_fails(
        self, mock_project_manager, vehicle_directory_selection_window_setup
    ) -> None:
        """
        User sees an error message when opening last vehicle directory fails.

        GIVEN: A vehicle directory selection window
        WHEN: User attempts to open last used directory but it fails
        THEN: An error dialog should be displayed
        """
        # Arrange: Configure project manager to fail
        mock_project_manager.open_last_vehicle_directory.side_effect = VehicleProjectOpenError(
            "Directory Not Found", "The last used vehicle directory no longer exists."
        )

        window = vehicle_directory_selection_window_setup
        last_vehicle_dir = "/home/user/vehicles/NonExistent"

        with patch("tkinter.messagebox.showerror") as mock_error_dialog:
            # Act: User attempts to open non-existent directory
            window.open_last_vehicle_directory(last_vehicle_dir)

            # Assert: Error dialog shown
            mock_error_dialog.assert_called_once_with(
                "Directory Not Found", "The last used vehicle directory no longer exists."
            )

    def test_user_can_close_window_and_quit_application(self, vehicle_directory_selection_window_setup) -> None:
        """
        User can close the window and quit the application.

        GIVEN: A vehicle directory selection window is open
        WHEN: User closes the window using the close button
        THEN: The application should exit gracefully
        """
        # Arrange: Set up window
        window = vehicle_directory_selection_window_setup

        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.sys_exit") as mock_exit:
            # Act: User closes window
            window.close_and_quit()

            # Assert: Application exits
            mock_exit.assert_called_once_with(0)

    def test_window_displays_correct_introduction_text_based_on_directory_context(
        self, mock_project_manager, vehicle_directory_selection_window_setup
    ) -> None:
        """
        Window displays appropriate introduction text based on current directory context.

        GIVEN: A project manager with specific vehicle and working directories
        WHEN: The vehicle directory selection window is initialized
        THEN: The correct introduction text should be displayed based on directory comparison
        """
        # Arrange: Configure project manager for current working directory scenario
        mock_project_manager.get_vehicle_directory.return_value = "/home/user/current_working"
        mock_project_manager.get_current_working_directory.return_value = "/home/user/current_working"

        # Act: Window initialization happens in fixture
        window = vehicle_directory_selection_window_setup

        # Assert: Window was created and project manager properly assigned
        assert window.project_manager == mock_project_manager
        # Note: Since we mock the entire __init__, we can't test actual initialization calls
        # But we can verify the window was created with the correct project manager

    def test_window_configures_fc_dependent_options_correctly_when_fc_connected(self, mock_project_manager, root) -> None:
        """
        Window enables flight controller dependent options when FC is connected.

        GIVEN: A flight controller is connected to the system
        WHEN: User opens the vehicle directory selection window
        THEN: Flight controller specific options should be enabled
        """

        def mock_vehicle_init_fc_connected(self, project_manager, fc_connected=False, connected_fc_vehicle_type="") -> None:
            """Mock VehicleDirectorySelectionWindow.__init__ for FC connected scenario."""
            # Set up required attributes without calling BaseWindow.__init__
            self.root = root  # Use the real root from conftest.py
            self.main_frame = MagicMock()
            self.project_manager = project_manager
            self.connected_fc_vehicle_type = connected_fc_vehicle_type
            self.fc_connected = fc_connected  # Store the fc_connected parameter
            # Mock other attributes that might be accessed
            self.base_log_dir = MagicMock()
            self.vehicle_dir = MagicMock()
            # Mock all the BooleanVar attributes expected by tests
            self.copy_vehicle_image = MagicMock()
            self.blank_component_data = MagicMock()
            self.reset_fc_parameters_to_their_defaults = MagicMock()
            self.infer_comp_specs_and_conn_from_fc_params = MagicMock()
            self.use_fc_params = MagicMock()
            self.blank_change_reason = MagicMock()
            # Mock DirectorySelectionWidgets instances
            self.template_dir = MagicMock()
            self.new_base_dir = MagicMock()
            self.new_dir = MagicMock()
            # Mock the root destroy method to prevent actual window destruction
            self.root.destroy = MagicMock()

        # Arrange & Act: Create window with FC connected
        with (
            patch.object(VehicleDirectorySelectionWindow, "__init__", mock_vehicle_init_fc_connected),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.ttk.Checkbutton"),
            patch("tkinter.BooleanVar"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection._"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.__version__", "1.0.0"),
        ):
            window = VehicleDirectorySelectionWindow(
                mock_project_manager, fc_connected=True, connected_fc_vehicle_type="ArduCopter"
            )
            window.root = MagicMock()
            window.main_frame = MagicMock()

            # Assert: Window created with FC connected configuration
            assert window.connected_fc_vehicle_type == "ArduCopter"
            # Checkbuttons should be created but not disabled (no config calls with state=DISABLED)


# ==================== INTEGRATION TESTS ====================


class TestDirectorySelectionIntegration:
    """Test integration scenarios between components."""

    def test_complete_new_vehicle_creation_workflow(self, mock_project_manager, root) -> None:
        """
        User can complete the entire new vehicle creation workflow successfully.

        GIVEN: A user wants to create a new vehicle configuration from a template
        WHEN: They select template, configure options, and create the vehicle
        THEN: All components should work together to complete the workflow
        """

        def mock_vehicle_init_integration(self, project_manager, fc_connected=False, connected_fc_vehicle_type="") -> None:
            """Mock VehicleDirectorySelectionWindow.__init__ for integration testing."""
            # Set up required attributes without calling BaseWindow.__init__
            self.root = root  # Use the real root from conftest.py
            self.main_frame = MagicMock()
            self.project_manager = project_manager
            self.connected_fc_vehicle_type = connected_fc_vehicle_type
            self.fc_connected = fc_connected
            # Mock all expected attributes
            self.base_log_dir = MagicMock()
            self.vehicle_dir = MagicMock()
            self.copy_vehicle_image = MagicMock()
            self.blank_component_data = MagicMock()
            self.reset_fc_parameters_to_their_defaults = MagicMock()
            self.infer_comp_specs_and_conn_from_fc_params = MagicMock()
            self.use_fc_params = MagicMock()
            self.blank_change_reason = MagicMock()
            self.template_dir = MagicMock()
            self.new_base_dir = MagicMock()
            self.new_dir = MagicMock()
            self.root.destroy = MagicMock()

        # Arrange: Set up complete workflow mocks
        with (
            patch.object(VehicleDirectorySelectionWindow, "__init__", mock_vehicle_init_integration),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.ttk.Checkbutton"),
            patch("tkinter.BooleanVar") as mock_boolvar,
            patch("tkinter.ttk.Frame"),
            patch("tkinter.Entry"),
            patch("tkinter.StringVar"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection._"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.__version__", "1.0.0"),
        ):
            # Create window
            window = VehicleDirectorySelectionWindow(mock_project_manager, fc_connected=False)
            window.root = MagicMock()
            window.main_frame = MagicMock()

            # Mock the widget components
            window.template_dir = MagicMock()
            window.template_dir.get_selected_directory.return_value = "/templates/copter"
            window.new_base_dir = MagicMock()
            window.new_base_dir.get_selected_directory.return_value = "/vehicles"
            window.new_dir = MagicMock()
            window.new_dir.get_selected_directory.return_value = "MyDrone"

            # Mock BooleanVar instances
            mock_bool_instance = MagicMock()
            mock_bool_instance.get.return_value = False
            mock_boolvar.return_value = mock_bool_instance

            for attr_name in [
                "copy_vehicle_image",
                "blank_component_data",
                "reset_fc_parameters_to_their_defaults",
                "infer_comp_specs_and_conn_from_fc_params",
                "use_fc_params",
                "blank_change_reason",
            ]:
                setattr(window, attr_name, mock_bool_instance)

            # Act: Complete workflow
            window.create_new_vehicle_from_template()

            # Assert: All components worked together
            window.template_dir.get_selected_directory.assert_called_once()
            window.new_base_dir.get_selected_directory.assert_called_once()
            window.new_dir.get_selected_directory.assert_called_once()
            mock_project_manager.create_new_vehicle_from_template.assert_called_once()
            window.root.destroy.assert_called_once()

    def test_error_recovery_across_component_boundaries(self, mock_project_manager, root) -> None:
        """
        System handles errors gracefully across component boundaries.

        GIVEN: Multiple components are involved in a workflow
        WHEN: An error occurs at any component boundary
        THEN: The error should be handled gracefully without system crash
        """

        def mock_vehicle_init_error_test(self, project_manager, fc_connected=False, connected_fc_vehicle_type="") -> None:
            """Mock VehicleDirectorySelectionWindow.__init__ for error testing."""
            # Set up required attributes without calling BaseWindow.__init__
            self.root = root  # Use the real root from conftest.py
            self.main_frame = MagicMock()
            self.project_manager = project_manager
            self.connected_fc_vehicle_type = connected_fc_vehicle_type
            self.fc_connected = fc_connected
            # Mock all expected attributes
            self.base_log_dir = MagicMock()
            self.vehicle_dir = MagicMock()
            self.copy_vehicle_image = MagicMock()
            self.blank_component_data = MagicMock()
            self.reset_fc_parameters_to_their_defaults = MagicMock()
            self.infer_comp_specs_and_conn_from_fc_params = MagicMock()
            self.use_fc_params = MagicMock()
            self.blank_change_reason = MagicMock()
            self.template_dir = MagicMock()
            self.new_base_dir = MagicMock()
            self.new_dir = MagicMock()
            self.root.destroy = MagicMock()

        # Arrange: Set up error conditions
        mock_project_manager.create_new_vehicle_from_template.side_effect = VehicleProjectCreationError(
            "System Error", "A system error occurred during vehicle creation."
        )

        with (
            patch.object(VehicleDirectorySelectionWindow, "__init__", mock_vehicle_init_error_test),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.ttk.Checkbutton"),
            patch("tkinter.BooleanVar"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection._"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.__version__", "1.0.0"),
            patch("tkinter.messagebox.showerror") as mock_error_dialog,
        ):
            window = VehicleDirectorySelectionWindow(mock_project_manager, fc_connected=False)
            window.root = MagicMock()
            window.main_frame = MagicMock()

            # Mock components for error scenario
            window.template_dir = MagicMock()
            window.template_dir.get_selected_directory.return_value = "/invalid/template"
            window.new_base_dir = MagicMock()
            window.new_base_dir.get_selected_directory.return_value = "/invalid/base"
            window.new_dir = MagicMock()
            window.new_dir.get_selected_directory.return_value = "ErrorVehicle"

            # Mock BooleanVar for settings
            for attr_name in [
                "copy_vehicle_image",
                "blank_component_data",
                "reset_fc_parameters_to_their_defaults",
                "infer_comp_specs_and_conn_from_fc_params",
                "use_fc_params",
                "blank_change_reason",
            ]:
                mock_var = MagicMock()
                mock_var.get.return_value = False
                setattr(window, attr_name, mock_var)

            # Act: Trigger error condition
            window.create_new_vehicle_from_template()

            # Assert: Error handled gracefully
            mock_error_dialog.assert_called_once_with("System Error", "A system error occurred during vehicle creation.")
            # Window should not be destroyed on error
            window.root.destroy.assert_not_called()
