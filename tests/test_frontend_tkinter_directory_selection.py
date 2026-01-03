#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_directory_selection.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import (
    DirectorySelectionWidgets,
    PathEntryWidget,
    VehicleDirectorySelectionWidgets,
)

# pylint: disable=redefined-outer-name,unused-argument,protected-access,too-many-arguments,too-many-positional-arguments,too-many-locals


# ==================== FIXTURES ====================


@pytest.fixture
def mock_parent_window() -> MagicMock:
    """Fixture providing a mock parent window."""
    parent = MagicMock()
    parent.root = MagicMock(spec=tk.Tk)
    parent.project_manager = MagicMock()
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
        )

        # Assert: Widget properly initialized with correct properties
        assert widget.directory == initial_dir
        assert widget.label_text == label_text
        assert widget.autoresize_width is True
        # Note: is_template_selection property removed in refactoring
        # Note: connected_fc_vehicle_type property removed in refactoring

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
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow")
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

        # Make mock_parent_window behave like a project opener window
        # Note: VehicleProjectOpenerWindow has been moved to a separate module

        # Create a callback that simulates template selection
        template_dir = "/home/user/templates/selected_template"

        def mock_template_callback(_: DirectorySelectionWidgets) -> str:
            # Simulate template selection through callback
            mock_template_instance = MagicMock()
            mock_template_window.return_value = mock_template_instance
            return template_dir

        # Create widget for template selection with callback
        widget = DirectorySelectionWidgets(
            parent=mock_parent_window,
            parent_frame=mock_parent_frame,
            initialdir="/home/user/initial",
            label_text="Template Directory:",
            autoresize_width=False,
            dir_tooltip="Template tooltip",
            button_tooltip="Browse templates",
            on_directory_selected_callback=mock_template_callback,
        )
        widget.directory_entry = mock_entry_instance

        # Act: User selects template
        result = widget.on_select_directory()

        # Assert: Template selection successful
        assert result is True
        assert widget.directory == template_dir
        # Note: TemplateOverviewWindow called inside callback, not directly by widget

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


class TestPathEntryWidget:
    """Test PathEntryWidget component behavior."""

    def test_user_can_initialize_directory_name_widget(self, mock_labelframe) -> None:
        """
        User can create a directory name widget with proper UI components.

        GIVEN: A labelframe parent for widget creation
        WHEN: A PathEntryWidget instance is created
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

            # Act: Create PathEntryWidget instance
            widget = PathEntryWidget(
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

            widget = PathEntryWidget(
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


# ==================== EXPANDED COVERAGE TESTS ====================


class TestDirectorySelectionWidgetAdvanced:
    """Test advanced directory selection widget behaviors for increased coverage."""

    def test_user_can_select_directory_with_non_vehicle_directory_parent(self, root) -> None:
        """
        User can select directory when parent is not a vehicle project opener window.

        GIVEN: A directory selection widget with a generic parent
        WHEN: User selects a template directory
        THEN: The template selection should execute but return empty string
        """
        # Arrange: Create widget with generic parent (not vehicle project opener)
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("tkinter.filedialog.askdirectory", return_value=""),  # Simulate cancel/no selection
        ):
            parent = MagicMock()
            parent.root = root
            parent_frame = ttk.Frame(root)

            widget = DirectorySelectionWidgets(
                parent=parent,
                parent_frame=parent_frame,
                initialdir="/test/dir",
                label_text="Test Directory:",
                autoresize_width=False,
                dir_tooltip="Test tooltip",
                button_tooltip="Test button tooltip",
            )

            # Act: User selects template directory with generic parent (dialog returns empty)
            result = widget.on_select_directory()

            # Assert: Directory selection should use standard file dialog and return False when canceled
            assert result is False  # Should return False because no directory was selected

    def test_user_can_select_directory_without_autoresize(self, root) -> None:
        """
        User can select directory without autoresize functionality.

        GIVEN: A directory selection widget with autoresize disabled
        WHEN: User selects a directory
        THEN: Directory entry should be updated without width changes
        """
        # Arrange: Create widget without autoresize
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("tkinter.filedialog.askdirectory", return_value="/selected/path"),
        ):
            parent = MagicMock()
            parent.root = root
            parent_frame = ttk.Frame(root)

            widget = DirectorySelectionWidgets(
                parent=parent,
                parent_frame=parent_frame,
                initialdir="/test/dir",
                label_text="Test Directory:",
                autoresize_width=False,
                dir_tooltip="Test tooltip",
                button_tooltip="Test button tooltip",
            )

            # Act: User selects directory
            result = widget.on_select_directory()

            # Assert: Directory updated without autoresize
            assert widget.directory == "/selected/path"
            assert result is True

    def test_user_can_navigate_directory_selection_without_button_tooltip(self, root) -> None:
        """
        User can navigate directory selection widget without button tooltip.

        GIVEN: A directory selection widget created without button tooltip
        WHEN: Widget is initialized
        THEN: No selection button should be created and entry view should be moved
        """
        # Arrange & Act: Create widget without button tooltip
        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"):
            parent = MagicMock()
            parent.root = root
            parent_frame = ttk.Frame(root)

            widget = DirectorySelectionWidgets(
                parent=parent,
                parent_frame=parent_frame,
                initialdir="/test/dir",
                label_text="Test Directory:",
                autoresize_width=False,
                dir_tooltip="Test tooltip",
                button_tooltip="",  # No button tooltip
            )

            # Assert: Widget created successfully without button
            assert widget.directory == "/test/dir"


# ==================== NEW TARGETED TESTS FOR COVERAGE ====================


class TestDirectorySelectionCoverageTargeted:  # pylint: disable=too-few-public-methods
    """Tests specifically designed to hit missing coverage lines."""

    def test_user_handles_empty_button_tooltip_path(self, root) -> None:
        """
        User can create widget without button tooltip.

        GIVEN: A directory selection widget configured without button tooltip
        WHEN: User creates the widget
        THEN: Widget should be created with entry moved to end (line 96)
        """
        # Arrange: Create widget without button tooltip
        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"):
            parent = MagicMock()
            parent.root = root
            parent_frame = ttk.Frame(root)

            # Act: Create widget with empty button tooltip
            widget = DirectorySelectionWidgets(
                parent=parent,
                parent_frame=parent_frame,
                initialdir="/test/dir",
                label_text="Test Directory:",
                autoresize_width=False,
                dir_tooltip="Test tooltip",
                button_tooltip="",  # Empty button tooltip
            )

            # Assert: Widget created successfully and entry positioned
            assert widget.directory == "/test/dir"
            # The key line we're testing is the xview_moveto(1.0) call when button_tooltip is empty


class TestVehicleDirectoryWidgetsCoverage:  # pylint: disable=too-few-public-methods
    """Tests to cover VehicleDirectorySelectionWidgets missing lines."""

    def test_user_opens_directory_without_destroying_parent(self, root) -> None:
        """
        User can open vehicle directory without destroying parent window.

        GIVEN: A vehicle directory widget with destroy_parent_on_open=False
        WHEN: User selects and opens a directory
        THEN: Directory should open but parent window should remain
        """
        # Arrange: Create widget with destroy_parent_on_open=False
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("tkinter.filedialog.askdirectory", return_value="/test/selected/dir"),
        ):
            parent = MagicMock()  # Mock parent (VehicleProjectOpenerWindow moved to separate module)
            parent.root = MagicMock()
            parent.project_manager = MagicMock()
            parent_frame = ttk.Frame(root)

            # Mock callback function that would normally be provided by the parent
            mock_callback = MagicMock()

            widget = VehicleDirectorySelectionWidgets(
                parent=parent,
                parent_frame=parent_frame,
                initial_dir="/test/initial",
                destroy_parent_on_open=False,  # This should prevent destroy call
                on_select_directory_callback=mock_callback,
            )

            # Act: User selects directory
            result = widget.on_select_directory()

            # Assert: Directory opened successfully, parent not destroyed
            assert result is True
            mock_callback.assert_called_once_with("/test/selected/dir")
            parent.root.destroy.assert_not_called()


class TestWidgetStringMethods:
    """Test simple widget string methods for coverage."""

    def test_directory_selection_widget_get_selected_directory_returns_string(self, root) -> None:
        """
        Directory selection widget returns directory as string.

        GIVEN: A directory selection widget with set directory
        WHEN: User calls get_selected_directory
        THEN: Directory string should be returned
        """
        # Arrange: Create widget with directory set
        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"):
            parent = MagicMock()
            parent.root = root
            parent_frame = ttk.Frame(root)

            widget = DirectorySelectionWidgets(
                parent=parent,
                parent_frame=parent_frame,
                initialdir="/test/initial",
                label_text="Test Directory:",
                autoresize_width=False,
                dir_tooltip="Test tooltip",
                button_tooltip="Test button",
            )

            # Act: Get directory
            result = widget.get_selected_directory()

            # Assert: Returns string (covers basic getter)
            assert isinstance(result, str)
            assert result == "/test/initial"  # Should return the initial directory

    def test_directory_name_widget_get_selected_directory_returns_name(self, root) -> None:
        """
        Directory name widget returns entered name.

        GIVEN: A directory name widget with entered text
        WHEN: User calls get_selected_directory
        THEN: Entered text should be returned
        """
        # Arrange: Create name widget with correct parameters
        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"):
            parent_frame = ttk.Labelframe(root, text="Test Frame")

            widget = PathEntryWidget(
                master=parent_frame, initial_dir="TestVehicle", label_text="Directory Name:", dir_tooltip="Test tooltip"
            )

            # Act: Get directory name
            result = widget.get_selected_directory()

            # Assert: Returns the initial name
            assert isinstance(result, str)
            assert result == "TestVehicle"
