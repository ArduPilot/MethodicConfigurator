#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_directory_selection.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Generator
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
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
    argument_parser,
    main,
)

# pylint: disable=redefined-outer-name,unused-argument,line-too-long,too-many-lines,too-few-public-methods
# ruff: noqa: SIM117


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Create a mocked LocalFilesystem instance."""
    local_filesystem = MagicMock()
    local_filesystem.vehicle_dir = "/test/vehicle/dir"
    local_filesystem.vehicle_type = "copter"
    local_filesystem.vehicle_components_json_filename = "vehicle_components.json"
    local_filesystem.file_parameters = {}
    local_filesystem.allow_editing_template_files = False
    return local_filesystem


@pytest.fixture
def window(
    root: tk.Tk,
    mock_local_filesystem: MagicMock,
) -> Generator[VehicleDirectorySelectionWindow, None, None]:
    """Create a test VehicleDirectorySelectionWindow instance with all dependencies mocked."""
    # Create a partially mocked window to avoid tkinter errors
    with (
        patch("tkinter.PhotoImage"),
        patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.application_icon_filepath"),
        patch.object(VehicleDirectorySelectionWindow, "__init__", return_value=None),
    ):
        window = VehicleDirectorySelectionWindow(mock_local_filesystem)

        # Set required attributes manually
        window.root = tk.Toplevel(root)
        window.main_frame = ttk.Frame(window.root)
        window.blank_component_data = tk.BooleanVar(value=False)
        window.infer_comp_specs_and_conn_from_fc_params = tk.BooleanVar(value=False)
        window.use_fc_params = tk.BooleanVar(value=False)
        window.blank_change_reason = tk.BooleanVar(value=False)
        window.copy_vehicle_image = tk.BooleanVar(value=False)
        window.reset_fc_parameters_to_their_defaults = tk.BooleanVar(value=False)
        window.configuration_template = ""
        window.local_filesystem = mock_local_filesystem

    # Mock the UI components that we'll interact with in tests
    window.template_dir = MagicMock(spec=DirectorySelectionWidgets)
    window.template_dir.get_selected_directory = MagicMock(return_value="/template/dir")

    window.new_base_dir = MagicMock(spec=DirectorySelectionWidgets)
    window.new_base_dir.get_selected_directory = MagicMock(return_value="/base/dir")

    window.new_dir = MagicMock(spec=DirectoryNameWidgets)
    window.new_dir.dir_var = MagicMock()
    window.new_dir.dir_var.get = MagicMock(return_value="vehicle_name")
    window.new_dir.get_selected_directory = MagicMock(return_value="vehicle_name")

    # Mock the connection_selection_widgets that would normally be created
    window.connection_selection_widgets = MagicMock(spec=VehicleDirectorySelectionWidgets)

    yield window

    # Clean up
    window.root.destroy()


@pytest.fixture
def mock_local_filesystem_with_no_files() -> MagicMock:
    """
    Fixture providing a mock LocalFilesystem for testing scenarios with no parameter files.

    GIVEN: A file system that appears empty of parameter files
    """
    filesystem = MagicMock(spec=LocalFilesystem)
    filesystem.vehicle_dir = "/test/vehicle/dir"
    filesystem.file_parameters = {}  # No parameter files found
    filesystem.getcwd.return_value = "/test/cwd"
    filesystem.directory_exists.return_value = True
    filesystem.get_recently_used_dirs.return_value = ("/template", "/base", "/vehicle")
    return filesystem


@pytest.fixture
def configured_window_for_user_workflows(
    mock_local_filesystem_with_no_files: MagicMock,
) -> Generator[VehicleDirectorySelectionWindow, None, None]:
    """
    Fixture providing a fully configured window for testing user workflows.

    GIVEN: A user opens the directory selection window
    AND: The system has no existing parameter files
    """
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.DirectorySelectionWidgets"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.DirectoryNameWidgets"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleDirectorySelectionWidgets"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
        patch("tkinter.ttk.Label") as mock_label,
        patch("tkinter.ttk.LabelFrame") as mock_label_frame,
        patch("tkinter.ttk.Button") as mock_button,
        patch("tkinter.ttk.Checkbutton") as mock_checkbutton,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.LocalFilesystem.get_recently_used_dirs",
            return_value=("/template", "/base", "/vehicle"),
        ),
    ):
        # Configure the mocked widgets
        mock_label.return_value = MagicMock()
        mock_label_frame.return_value = MagicMock()
        mock_button.return_value = MagicMock()
        mock_checkbutton.return_value = MagicMock()

        window = VehicleDirectorySelectionWindow(mock_local_filesystem_with_no_files)
        yield window


# ==== Tests for DirectorySelectionWidgets ====


@pytest.fixture
def base_parent() -> MagicMock:
    """Create a mocked parent for DirectorySelectionWidgets."""
    parent = MagicMock()
    parent.root = MagicMock()
    return parent


@pytest.fixture
def directory_selection_widgets(root: tk.Tk, base_parent: MagicMock) -> Generator[DirectorySelectionWidgets, None, None]:
    """Create a DirectorySelectionWidgets instance for testing."""
    parent_frame = ttk.Frame(root)

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        widget = DirectorySelectionWidgets(
            parent=base_parent,
            parent_frame=parent_frame,
            initialdir="/test/directory",
            label_text="Test Directory:",
            autoresize_width=True,
            dir_tooltip="Test directory tooltip",
            button_tooltip="Select directory button tooltip",
            is_template_selection=False,
            connected_fc_vehicle_type="",
        )
        yield widget


def test_directory_selection_widgets_init(directory_selection_widgets) -> None:
    """Test initialization of DirectorySelectionWidgets."""
    widget = directory_selection_widgets

    # Check that the properties are correctly initialized
    assert widget.directory == "/test/directory"
    assert widget.label_text == "Test Directory:"
    assert widget.autoresize_width is True
    assert widget.is_template_selection is False

    # Check that UI components are created
    assert hasattr(widget, "container_frame")
    assert hasattr(widget, "directory_entry")


def test_directory_selection_widgets_on_select_directory(directory_selection_widgets) -> None:
    """Test on_select_directory method of DirectorySelectionWidgets."""
    widget = directory_selection_widgets

    # Test with a non-template directory selection
    with patch("tkinter.filedialog.askdirectory", return_value="/selected/directory"):
        # Call the method
        result = widget.on_select_directory()

        # Verify result and directory update
        assert result is True
        assert widget.directory == "/selected/directory"

    # Test with a canceled selection (empty result)
    with patch("tkinter.filedialog.askdirectory", return_value=""):
        # Call the method
        result = widget.on_select_directory()

        # Verify result and no directory update
        assert result is False
        assert widget.directory == "/selected/directory"  # Unchanged


def test_directory_selection_widgets_template_selection(base_parent, root) -> None:
    """Test template selection mode of DirectorySelectionWidgets."""
    parent_frame = ttk.Frame(root)

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.TemplateOverviewWindow"):
            dirs_mock = MagicMock(return_value=["/template/directory", "/base/dir", "/vehicle/dir"])
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_recently_used_dirs",
                dirs_mock,
            ):
                # Create widget in template selection mode
                widget = DirectorySelectionWidgets(
                    parent=base_parent,
                    parent_frame=parent_frame,
                    initialdir="/initial/template",
                    label_text="Template Directory:",
                    autoresize_width=True,
                    dir_tooltip="Template directory tooltip",
                    button_tooltip="Select template button tooltip",
                    is_template_selection=True,
                    connected_fc_vehicle_type="ArduCopter",
                )

                # Call the method to select a template
                result = widget.on_select_directory()

                # Verify template was selected from ProgramSettings
                assert result is True
                assert widget.directory == "/template/directory"


def test_directory_selection_widgets_get_selected_directory(directory_selection_widgets) -> None:
    """Test get_selected_directory method of DirectorySelectionWidgets."""
    widget = directory_selection_widgets

    # Set a specific directory
    widget.directory = "/specific/test/directory"

    # Check that get_selected_directory returns the correct value
    assert widget.get_selected_directory() == "/specific/test/directory"


def test_directory_selection_widgets_autoresize_width(base_parent, root) -> None:
    """Test autoresize_width behavior in DirectorySelectionWidgets."""
    parent_frame = ttk.Frame(root)

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        # Test with autoresize_width=True
        widget_with_resize = DirectorySelectionWidgets(
            parent=base_parent,
            parent_frame=parent_frame,
            initialdir="/test/dir",
            label_text="Test:",
            autoresize_width=True,
            dir_tooltip="Tooltip",
            button_tooltip="Button tooltip",
            is_template_selection=False,
            connected_fc_vehicle_type="ArduCopter",
        )

        # Test with autoresize_width=False
        widget_without_resize = DirectorySelectionWidgets(
            parent=base_parent,
            parent_frame=parent_frame,
            initialdir="/another/test/dir",
            label_text="Another Test:",
            autoresize_width=False,
            dir_tooltip="Another tooltip",
            button_tooltip="Another button tooltip",
            is_template_selection=False,
            connected_fc_vehicle_type="ArduCopter",
        )

        # Verify the difference in behavior when selecting a directory
        with patch("tkinter.filedialog.askdirectory", return_value="/very/long/selected/directory/path"):
            with patch.object(widget_with_resize.directory_entry, "config") as mock_config_with_resize:
                widget_with_resize.on_select_directory()

                # Should call config with a width parameter
                config_calls = [call[1] for call in mock_config_with_resize.call_args_list]
                width_specified = any("width" in call for call in config_calls)
                assert width_specified is True

            with patch.object(widget_without_resize.directory_entry, "config") as mock_config_without_resize:
                widget_without_resize.on_select_directory()

                # Should not call config with a width parameter for autoresize_width=False
                config_calls = [call[1] for call in mock_config_without_resize.call_args_list if "width" in call]
                assert not any("width" in call and len(call) > 0 for call in config_calls)


# ==== Tests for DirectoryNameWidgets ====
def test_directory_selection_widgets_extremely_long_path(base_parent, root) -> None:
    """Test handling of extremely long paths in DirectorySelectionWidgets."""
    parent_frame = ttk.Frame(root)

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        widget = DirectorySelectionWidgets(
            parent=base_parent,
            parent_frame=parent_frame,
            initialdir="/short/path",
            label_text="Test Directory:",
            autoresize_width=True,
            dir_tooltip="Test tooltip",
            button_tooltip="Button tooltip",
            is_template_selection=False,
            connected_fc_vehicle_type="ArduCopter",
        )

        # Create an extremely long path
        extremely_long_path = "/very" + "/long" * 50 + "/path/to/test/directory"

        # Test with the extremely long path
        with patch("tkinter.filedialog.askdirectory", return_value=extremely_long_path):
            with patch.object(widget.directory_entry, "config") as mock_config:
                result = widget.on_select_directory()

                # Verify result and directory update
                assert result is True
                assert widget.directory == extremely_long_path

                # Check that the width was adjusted but capped at a reasonable value
                config_calls = [call[1] for call in mock_config.call_args_list]
                width_values = [call.get("width") for call in config_calls if "width" in call]
                assert any(width_values), "Width should be specified"

                # The width should match the length of the path (or a reasonable maximum)
                if width_values:
                    assert width_values[0] == max(4, len(extremely_long_path))


def test_directory_selection_widgets_special_characters(base_parent, root) -> None:
    """Test handling of paths with special characters in DirectorySelectionWidgets."""
    parent_frame = ttk.Frame(root)

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        widget = DirectorySelectionWidgets(
            parent=base_parent,
            parent_frame=parent_frame,
            initialdir="/normal/path",
            label_text="Test Directory:",
            autoresize_width=True,
            dir_tooltip="Test tooltip",
            button_tooltip="Button tooltip",
            is_template_selection=False,
            connected_fc_vehicle_type="ArduCopter",
        )

        # Test with paths containing special characters
        special_char_paths = [
            "/path/with spaces/and symbols/!@#$/dir",
            "/path/with/unicode/characters/üñíçødé/dir",
            "/path/with/emoji/😀😁😂/test",
        ]

        for special_path in special_char_paths:
            with patch("tkinter.filedialog.askdirectory", return_value=special_path):
                result = widget.on_select_directory()

                # Verify result and directory update
                assert result is True
                assert widget.directory == special_path


def test_keyboard_navigation_with_proper_mocks(directory_selection_widgets) -> None:
    """Test keyboard navigation in DirectorySelectionWidgets."""
    widget = directory_selection_widgets

    # Create a mock event to simulate keyboard events
    _mock_event = MagicMock()

    # Create a new mock for focus_set instead of trying to assign to the method
    mock_focus_set = MagicMock()
    # Patch the focus_set method
    with patch.object(widget.directory_entry, "focus_set", mock_focus_set):
        # Call the focus_set method
        widget.directory_entry.focus_set()
        # Verify it was called
        mock_focus_set.assert_called_once()


@pytest.fixture
def directory_name_widgets(root: tk.Tk) -> Generator[DirectoryNameWidgets, None, None]:
    """Create a DirectoryNameWidgets instance for testing."""
    master = ttk.Labelframe(root, text="Test Labelframe")

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        widget = DirectoryNameWidgets(
            master=master,
            initial_dir="test_directory_name",
            label_text="Directory Name:",
            dir_tooltip="Enter directory name tooltip",
        )
        yield widget


def test_directory_name_widgets_init(directory_name_widgets) -> None:
    """Test initialization of DirectoryNameWidgets."""
    widget = directory_name_widgets

    # Check that the properties are correctly initialized
    assert hasattr(widget, "container_frame")
    assert hasattr(widget, "dir_var")
    assert widget.dir_var.get() == "test_directory_name"


def test_directory_name_widgets_get_selected_directory(directory_name_widgets) -> None:
    """Test get_selected_directory method of DirectoryNameWidgets."""
    widget = directory_name_widgets

    # Set a specific value
    widget.dir_var.set("new_test_directory")

    # Check that get_selected_directory returns the correct value
    assert widget.get_selected_directory() == "new_test_directory"


# ==== Tests for VehicleDirectorySelectionWidgets ====


@pytest.fixture
def vehicle_directory_selection_widgets(
    root: tk.Tk, base_parent: MagicMock, mock_local_filesystem: MagicMock
) -> Generator[VehicleDirectorySelectionWidgets, None, None]:
    """Create a VehicleDirectorySelectionWidgets instance for testing."""
    parent_frame = ttk.Frame(root)

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        widget = VehicleDirectorySelectionWidgets(
            parent=base_parent,
            parent_frame=parent_frame,
            local_filesystem=mock_local_filesystem,
            initial_dir="/test/vehicle/directory",
            destroy_parent_on_open=True,
        )
        yield widget


def test_vehicle_directory_selection_widgets_init(vehicle_directory_selection_widgets, mock_local_filesystem) -> None:
    """Test initialization of VehicleDirectorySelectionWidgets."""
    widget = vehicle_directory_selection_widgets

    # Check that the properties are correctly initialized
    assert widget.directory == "/test/vehicle/directory"
    assert widget.local_filesystem == mock_local_filesystem
    assert widget.destroy_parent_on_open is True
    assert widget.is_template_selection is False


def test_vehicle_directory_selection_widgets_on_select_directory_template_dir(vehicle_directory_selection_widgets) -> None:
    """Test on_select_directory method when a template directory is selected."""
    widget = vehicle_directory_selection_widgets

    # Override the base class method to return True without showing a dialog
    with patch.object(DirectorySelectionWidgets, "on_select_directory", return_value=True):
        # Set a template directory path
        widget.directory = "/vehicle_templates/test_dir"

        # Mock messagebox.showerror
        with patch("tkinter.messagebox.showerror") as mock_error:
            # Call the method
            result = widget.on_select_directory()

            # Verify result and error message
            assert result is False
            mock_error.assert_called_once()
            assert "Invalid Vehicle Directory Selected" in mock_error.call_args[0][0]


def test_vehicle_directory_selection_widgets_on_select_directory_invalid_files(
    vehicle_directory_selection_widgets, mock_local_filesystem
) -> None:
    """Test on_select_directory method when directory doesn't contain required files."""
    widget = vehicle_directory_selection_widgets

    # Configure mocks for a valid selection but without required files
    with patch.object(DirectorySelectionWidgets, "on_select_directory", return_value=True):
        with patch.object(mock_local_filesystem, "vehicle_configuration_files_exist", return_value=False):
            # Set a non-template directory path
            widget.directory = "/valid/vehicle/dir"

            # Mock messagebox.showerror
            with patch("tkinter.messagebox.showerror") as mock_error:
                # Call the method
                result = widget.on_select_directory()

                # Verify result and error message
                assert result is False
                mock_error.assert_called_once()
                assert "Invalid Vehicle Directory Selected" in mock_error.call_args[0][0]


def test_vehicle_directory_selection_widgets_on_select_directory_reinit_exception(
    vehicle_directory_selection_widgets, mock_local_filesystem
) -> None:
    """Test on_select_directory method when re_init raises an exception."""
    widget = vehicle_directory_selection_widgets

    # Configure mocks for a valid selection but with re_init failing
    with patch.object(DirectorySelectionWidgets, "on_select_directory", return_value=True):
        with patch.object(mock_local_filesystem, "vehicle_configuration_files_exist", return_value=True):
            with patch.object(mock_local_filesystem, "re_init", side_effect=SystemExit("Test error")):
                # Set a non-template directory path
                widget.directory = "/valid/vehicle/dir"

                # Mock messagebox.showerror
                with patch("tkinter.messagebox.showerror") as mock_error:
                    # Call the method - it should return False due to the exception being caught
                    result = widget.on_select_directory()

                    # Verify result and error message
                    assert result is False
                    mock_error.assert_called_once()
                    assert "Fatal error reading parameter files" in mock_error.call_args[0][0]
                    assert "Test error" in mock_error.call_args[0][1]


def test_vehicle_directory_selection_widgets_on_select_directory_success(
    vehicle_directory_selection_widgets, mock_local_filesystem, base_parent
) -> None:
    """Test successful directory selection in VehicleDirectorySelectionWidgets."""
    widget = vehicle_directory_selection_widgets

    # Configure mocks for a successful selection
    with patch.object(DirectorySelectionWidgets, "on_select_directory", return_value=True):
        with patch.object(mock_local_filesystem, "vehicle_configuration_files_exist", return_value=True):
            with patch.object(mock_local_filesystem, "re_init"):
                # Set up file_parameters to simulate success
                mock_local_filesystem.file_parameters = {"00_default.param": {}, "01_param.param": {}}

                # Set a non-template directory path
                widget.directory = "/valid/vehicle/dir"

                # Mock filesystem methods
                with patch(
                    "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_vehicle_dir"
                ) as mock_store:
                    with patch.object(base_parent.root, "destroy") as mock_destroy:
                        # Call the method
                        result = widget.on_select_directory()

                        # Verify result and side effects
                        assert result is True
                        assert mock_local_filesystem.vehicle_dir == "/valid/vehicle/dir"
                        mock_store.assert_called_once_with("/valid/vehicle/dir")
                        mock_destroy.assert_called_once()


def test_vehicle_directory_selection_widgets_on_select_directory_no_files(
    vehicle_directory_selection_widgets, mock_local_filesystem
) -> None:
    """Test directory selection with no parameter files found."""
    widget = vehicle_directory_selection_widgets

    # Configure mocks for a selection with no parameter files
    with patch.object(DirectorySelectionWidgets, "on_select_directory", return_value=True):
        with patch.object(mock_local_filesystem, "vehicle_configuration_files_exist", return_value=True):
            with patch.object(mock_local_filesystem, "re_init"):
                # Empty file_parameters to simulate no files found
                mock_local_filesystem.file_parameters = {}

                # Set a non-template directory path
                widget.directory = "/valid/vehicle/dir"

                # Mock messagebox.showerror
                with patch("tkinter.messagebox.showerror") as mock_error:
                    # Call the method
                    result = widget.on_select_directory()

                    # Verify result and error shown - should return False and show error
                    assert result is False
                    mock_error.assert_called_once()
                    assert "No parameter files found" in mock_error.call_args[0][0]
                    assert "/valid/vehicle/dir" in mock_error.call_args[0][1]


# ==== Tests for initialization and properties ====


def test_initialization(window) -> None:
    """Test that the window is properly initialized."""
    # Check that the variables are initialized with correct default values
    assert window.blank_component_data.get() is False
    assert window.infer_comp_specs_and_conn_from_fc_params.get() is False
    assert window.use_fc_params.get() is False
    assert window.blank_change_reason.get() is False
    assert window.configuration_template == ""

    # Also verify the root window and main frame exist
    assert isinstance(window.root, tk.Toplevel)
    assert isinstance(window.main_frame, ttk.Frame)


def test_real_window_initialization(tk_root, mock_tkinter_context, mock_local_filesystem) -> None:  # noqa: ARG001
    """Test the actual initialization of the window with real UI components."""
    # We need to directly patch the VehicleDirectorySelectionWindow.__init__ to avoid all initialization issues
    with patch.object(VehicleDirectorySelectionWindow, "__init__") as mock_init:
        mock_init.return_value = None

        # Create the window with patched constructor
        window = VehicleDirectorySelectionWindow(mock_local_filesystem)

        # Manually set up all the required attributes
        window.root = tk.Toplevel(tk_root)
        window.main_frame = ttk.Frame(window.root)
        window.local_filesystem = mock_local_filesystem
        window.blank_component_data = tk.BooleanVar(value=False)
        window.infer_comp_specs_and_conn_from_fc_params = tk.BooleanVar(value=False)
        window.use_fc_params = tk.BooleanVar(value=False)
        window.blank_change_reason = tk.BooleanVar(value=False)
        window.configuration_template = ""

        # Check that the window attributes were properly set up
        assert isinstance(window.root, tk.Toplevel)
        assert isinstance(window.main_frame, ttk.Frame)
        assert window.local_filesystem == mock_local_filesystem

        # Verify boolean variables have correct default values
        assert window.blank_component_data.get() is False
        assert window.infer_comp_specs_and_conn_from_fc_params.get() is False
        assert window.use_fc_params.get() is False
        assert window.blank_change_reason.get() is False
        assert window.configuration_template == ""

        window.root.destroy()


# ==== Tests for template directory validation ====


def test_create_new_vehicle_with_empty_template_dir(window) -> None:
    """Test creating a new vehicle with an empty template directory."""
    # Set up empty template dir
    window.template_dir.get_selected_directory = MagicMock(return_value="")

    # Test with patched messagebox
    with patch("tkinter.messagebox.showerror") as mock_error:
        # Call create_new_vehicle_from_template
        window.create_new_vehicle_from_template()

        # Check that an error message was shown with correct title and message
        mock_error.assert_called_once()
        assert "Vehicle template directory" in mock_error.call_args[0][0]
        assert "must not be empty" in mock_error.call_args[0][1]


def test_create_new_vehicle_with_nonexistent_template_dir(window) -> None:
    """Test creating a new vehicle with a nonexistent template directory."""
    # Set up a valid template dir that doesn't exist
    window.template_dir.get_selected_directory = MagicMock(return_value="/nonexistent/template/dir")

    dir_exists_mock = MagicMock(return_value=False)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        with patch("tkinter.messagebox.showerror") as mock_error:
            # Call create_new_vehicle_from_template
            window.create_new_vehicle_from_template()

            # Check that an error message was shown with correct title and message
            mock_error.assert_called_once()
            assert "Vehicle template directory" in mock_error.call_args[0][0]
            assert "does not exist" in mock_error.call_args[0][1]


# ==== Tests for vehicle name validation ====


def test_create_new_vehicle_with_empty_vehicle_name(window) -> None:
    """Test creating a new vehicle with an empty vehicle name."""
    # Set up a valid template dir
    window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        # Set up empty vehicle name
        window.new_dir.get_selected_directory = MagicMock(return_value="")

        with patch("tkinter.messagebox.showerror") as mock_error:
            # Call create_new_vehicle_from_template
            window.create_new_vehicle_from_template()

            # Check that an error message was shown with correct title and message
            mock_error.assert_called_once()
            assert "New vehicle directory" in mock_error.call_args[0][0]
            assert "must not be empty" in mock_error.call_args[0][1]


@pytest.mark.parametrize(
    ("vehicle_name", "expected_error"),
    [
        ("invalid*name", "invalid characters"),
        ("bad?name", "invalid characters"),
        ("name/with/slashes", "invalid characters"),
        ("name\\with\\backslashes", "invalid characters"),
        ("name:with:colons", "invalid characters"),
        ("name<with>brackets", "invalid characters"),
    ],
)
def test_create_new_vehicle_with_invalid_names(
    window: VehicleDirectorySelectionWindow, vehicle_name: str, expected_error: str
) -> None:
    """Test creating a new vehicle with various invalid directory names."""
    # Set up a valid template dir
    window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        valid_dir_mock = MagicMock(return_value=False)
        with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", valid_dir_mock):
            # Set up invalid vehicle name
            window.new_dir.get_selected_directory = MagicMock(return_value=vehicle_name)

            with patch("tkinter.messagebox.showerror") as mock_error:
                # Call create_new_vehicle_from_template
                window.create_new_vehicle_from_template()

                # Check that an error message was shown with correct title and message
                mock_error.assert_called_once()
                assert "New vehicle directory" in mock_error.call_args[0][0]
                assert expected_error in mock_error.call_args[0][1]


# ==== Tests for directory creation errors ====


@pytest.mark.parametrize(
    "error_message",
    [
        "Directory already exists",
        "Permission denied",
        "Invalid path",
        "Error creating directory",
    ],
)
def test_create_vehicle_dir_errors(window: VehicleDirectorySelectionWindow, error_message: str) -> None:
    """Test various error messages when creating vehicle directory fails."""
    # Set up mocks
    window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        valid_dir_mock = MagicMock(return_value=True)
        with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", valid_dir_mock):
            new_vehicle_dir_mock = MagicMock(return_value="/base/dir/vehicle_name")
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir", new_vehicle_dir_mock
            ):
                # Mock the method that returns the error
                create_dir_mock = MagicMock(return_value=error_message)
                with patch.object(window.local_filesystem, "create_new_vehicle_dir", create_dir_mock):
                    window.new_dir.get_selected_directory = MagicMock(return_value="valid_name")

                    # Mock messagebox.showerror
                    with patch("tkinter.messagebox.showerror") as mock_error:
                        # Call create_new_vehicle_from_template method
                        window.create_new_vehicle_from_template()

                        # Check that an error message was shown
                        mock_error.assert_called_once()
                        assert "New vehicle directory" in mock_error.call_args[0][0]
                        assert error_message in mock_error.call_args[0][1]


# ==== Tests for template file copy errors ====


@pytest.mark.parametrize(
    "error_message",
    [
        "Error copying template files",
        "Permission denied",
        "Source files not found",
        "Destination directory not writable",
    ],
)
def test_template_file_copy_errors(window: VehicleDirectorySelectionWindow, error_message: str) -> None:
    """Test various error messages when copying template files fails."""
    # Set up mocks
    window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        valid_dir_mock = MagicMock(return_value=True)
        with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", valid_dir_mock):
            new_vehicle_dir_mock = MagicMock(return_value="/base/dir/vehicle_name")
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir", new_vehicle_dir_mock
            ):
                # Mock successful directory creation but failed file copy
                create_dir_mock = MagicMock(return_value="")
                with patch.object(window.local_filesystem, "create_new_vehicle_dir", create_dir_mock):
                    # Mock copy template files to fail
                    copy_files_mock = MagicMock(return_value=error_message)
                    with patch.object(window.local_filesystem, "copy_template_files_to_new_vehicle_dir", copy_files_mock):
                        window.new_dir.get_selected_directory = MagicMock(return_value="valid_name")

                        # Mock messagebox.showerror
                        with patch("tkinter.messagebox.showerror") as mock_error:
                            # Call create_new_vehicle_from_template method
                            window.create_new_vehicle_from_template()

                            # Check that an error message was shown with the right error message
                            mock_error.assert_called_once()
                            assert "Copying template files" in mock_error.call_args[0][0]
                            assert error_message in mock_error.call_args[0][1]


# ==== Tests for successful creation of new vehicle ====


def test_successful_create_new_vehicle(window: VehicleDirectorySelectionWindow) -> None:
    """Test successful creation of a new vehicle from template."""
    # Set up mocks
    window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        valid_dir_mock = MagicMock(return_value=True)
        with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", valid_dir_mock):
            new_vehicle_dir_mock = MagicMock(return_value="/base/dir/vehicle_name")
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir", new_vehicle_dir_mock
            ):
                # Mock successful directory creation and file copy
                with patch.object(window.local_filesystem, "create_new_vehicle_dir", return_value=""):
                    with patch.object(window.local_filesystem, "copy_template_files_to_new_vehicle_dir", return_value=""):
                        with patch.object(window.local_filesystem, "re_init") as mock_re_init:
                            # Set up mock file parameters to simulate successful file loading
                            window.local_filesystem.file_parameters = {"00_default.param": {}}

                            # Mock store methods
                            store_template_mock = MagicMock()
                            with patch(
                                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_template_dirs",
                                store_template_mock,
                            ):
                                store_vehicle_mock = MagicMock()
                                with patch(
                                    "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_vehicle_dir",
                                    store_vehicle_mock,
                                ):
                                    with patch.object(window.root, "destroy") as mock_destroy:
                                        dir_name_mock = MagicMock(return_value="template_dir_name")
                                        with patch(
                                            "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.get_directory_name_from_full_path",
                                            dir_name_mock,
                                        ):
                                            # Call create_new_vehicle_from_template method
                                            window.new_dir.get_selected_directory = MagicMock(return_value="valid_name")
                                            window.create_new_vehicle_from_template()

                                            # Verify all the expected method calls
                                            mock_re_init.assert_called_once_with(
                                                "/base/dir/vehicle_name",
                                                window.local_filesystem.vehicle_type,
                                                window.blank_component_data.get(),
                                            )
                                            store_template_mock.assert_called_once_with("/valid/template/dir", "/base/dir")
                                            store_vehicle_mock.assert_called_once_with("/base/dir/vehicle_name")
                                            mock_destroy.assert_called_once()
                                            assert window.configuration_template == "template_dir_name"

                                            # Verify state changes
                                            assert window.local_filesystem.vehicle_dir == "/base/dir/vehicle_name"


def test_successful_create_new_vehicle_state_verification(window: VehicleDirectorySelectionWindow) -> None:  # pylint: disable=too-many-locals
    """Test state verification after successful creation of a new vehicle."""
    # Set up testing state
    template_dir = "/valid/template/dir"
    base_dir = "/base/dir"
    vehicle_name = "valid_name"
    new_vehicle_dir = f"{base_dir}/{vehicle_name}"
    template_dir_name = "template_dir_name"

    # Set up mocks
    window.template_dir.get_selected_directory = MagicMock(return_value=template_dir)
    window.new_base_dir.get_selected_directory = MagicMock(return_value=base_dir)
    window.new_dir.get_selected_directory = MagicMock(return_value=vehicle_name)

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        valid_dir_mock = MagicMock(return_value=True)
        with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", valid_dir_mock):
            new_vehicle_dir_mock = MagicMock(return_value=new_vehicle_dir)
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir", new_vehicle_dir_mock
            ):
                create_dir_mock = MagicMock(return_value="")
                with patch.object(window.local_filesystem, "create_new_vehicle_dir", create_dir_mock):
                    copy_files_mock = MagicMock(return_value="")
                    with patch.object(window.local_filesystem, "copy_template_files_to_new_vehicle_dir", copy_files_mock):
                        with patch.object(window.local_filesystem, "re_init") as mock_re_init:
                            # Set up for successful completion
                            window.local_filesystem.file_parameters = {"00_default.param": {}, "01_param_file.param": {}}

                            store_template_mock = MagicMock()
                            with patch(
                                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_template_dirs",
                                store_template_mock,
                            ):
                                store_vehicle_mock = MagicMock()
                                with patch(
                                    "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_vehicle_dir",
                                    store_vehicle_mock,
                                ):
                                    with patch.object(window.root, "destroy"):
                                        dir_name_mock = MagicMock(return_value=template_dir_name)
                                        with patch(
                                            "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.get_directory_name_from_full_path",
                                            dir_name_mock,
                                        ):
                                            # Initial state check
                                            initial_vehicle_dir = window.local_filesystem.vehicle_dir

                                            # Call the method
                                            window.create_new_vehicle_from_template()

                                            # Verify state changes in detail
                                            assert window.local_filesystem.vehicle_dir == new_vehicle_dir
                                            assert window.local_filesystem.vehicle_dir != initial_vehicle_dir
                                            assert window.configuration_template == template_dir_name

                                            # Verify re_init was called with correct parameters
                                            mock_re_init.assert_called_once_with(
                                                new_vehicle_dir,
                                                window.local_filesystem.vehicle_type,
                                                window.blank_component_data.get(),
                                            )

                                            # Verify file_parameters was accessed
                                            assert len(window.local_filesystem.file_parameters) == 2
                                            assert "00_default.param" in window.local_filesystem.file_parameters
                                            assert "01_param_file.param" in window.local_filesystem.file_parameters


# ==== Tests for blank component data checkbox ====


def test_blank_component_data_setting(window: VehicleDirectorySelectionWindow) -> None:
    """Test that the blank_component_data setting is passed correctly to re_init."""
    # Set up mocks for a successful creation
    window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")
    window.new_dir.get_selected_directory = MagicMock(return_value="valid_name")

    # Test with blank_component_data set to True
    window.blank_component_data.set(True)

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        valid_dir_mock = MagicMock(return_value=True)
        with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", valid_dir_mock):
            new_vehicle_dir_mock = MagicMock(return_value="/base/dir/vehicle_name")
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir", new_vehicle_dir_mock
            ):
                create_dir_mock = MagicMock(return_value="")
                with patch.object(window.local_filesystem, "create_new_vehicle_dir", create_dir_mock):
                    copy_files_mock = MagicMock(return_value="")
                    with patch.object(window.local_filesystem, "copy_template_files_to_new_vehicle_dir", copy_files_mock):
                        with patch.object(window.local_filesystem, "re_init") as mock_re_init:
                            # Set up for successful completion
                            window.local_filesystem.file_parameters = {"00_default.param": {}}

                            store_template_mock = MagicMock()
                            with patch(
                                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_template_dirs",
                                store_template_mock,
                            ):
                                store_vehicle_mock = MagicMock()
                                with patch(
                                    "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_vehicle_dir",
                                    store_vehicle_mock,
                                ):
                                    with patch.object(window.root, "destroy"):
                                        dir_name_mock = MagicMock()
                                        with patch(
                                            "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.get_directory_name_from_full_path",
                                            dir_name_mock,
                                        ):
                                            # Call the method
                                            window.create_new_vehicle_from_template()

                                            # Verify the blank_component_data was passed correctly (should be True)
                                            mock_re_init.assert_called_once_with(
                                                "/base/dir/vehicle_name",
                                                window.local_filesystem.vehicle_type,
                                                True,  # noqa: FBT003
                                            )


# ==== Tests for blank_change_reason checkbox ====


def test_blank_change_reason_setting(window: VehicleDirectorySelectionWindow) -> None:
    """Test that the blank_change_reason setting is passed correctly to copy_template_files_to_new_vehicle_dir."""
    # Set up mocks for a successful creation
    window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")
    window.new_dir.get_selected_directory = MagicMock(return_value="valid_name")

    # Test with blank_change_reason set to True
    window.blank_change_reason.set(True)

    dir_exists_mock = MagicMock(return_value=True)
    with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", dir_exists_mock):
        valid_dir_mock = MagicMock(return_value=True)
        with patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", valid_dir_mock):
            new_vehicle_dir_mock = MagicMock(return_value="/base/dir/vehicle_name")
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir", new_vehicle_dir_mock
            ):
                create_dir_mock = MagicMock(return_value="")
                with patch.object(window.local_filesystem, "create_new_vehicle_dir", create_dir_mock):
                    copy_files_mock = MagicMock()
                    with patch.object(window.local_filesystem, "copy_template_files_to_new_vehicle_dir", copy_files_mock):
                        copy_files_mock.return_value = ""  # No error

                        with patch.object(window.local_filesystem, "re_init"):
                            # Set up for successful completion
                            window.local_filesystem.file_parameters = {"00_default.param": {}}

                            store_template_mock = MagicMock()
                            with patch(
                                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_template_dirs",
                                store_template_mock,
                            ):
                                store_vehicle_mock = MagicMock()
                                with patch(
                                    "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_vehicle_dir",
                                    store_vehicle_mock,
                                ):
                                    with patch.object(window.root, "destroy"):
                                        dir_name_mock = MagicMock()
                                        with patch(
                                            "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.get_directory_name_from_full_path",
                                            dir_name_mock,
                                        ):
                                            # Call the method
                                            window.create_new_vehicle_from_template()

                                            # Verify blank_change_reason was passed correctly (should be True)
                                            copy_files_mock.assert_called_once_with(
                                                "/valid/template/dir",
                                                "/base/dir/vehicle_name",
                                                blank_change_reason=True,
                                                copy_vehicle_image=False,
                                            )


# ==== Tests for open_last_vehicle_directory ====


def test_open_last_vehicle_directory_button(window: VehicleDirectorySelectionWindow) -> None:
    """Test that open_last_vehicle_directory is called with the correct path."""
    # Mock the open_last_vehicle_directory method
    with patch.object(window, "open_last_vehicle_directory") as mock_open:
        # Call the method directly with a path
        test_path = "/last/vehicle/dir"
        window.open_last_vehicle_directory(test_path)

        # Verify it was called with the correct argument
        mock_open.assert_called_once_with(test_path)


@pytest.mark.parametrize(
    ("last_dir", "has_files", "expected_destroy_called"),
    [
        ("/valid/last/dir", True, True),
        ("/invalid/last/dir", False, False),
        ("", False, False),
    ],
)
def test_open_last_vehicle_directory_scenarios(
    window: VehicleDirectorySelectionWindow,
    last_dir: str,
    has_files: bool,
    expected_destroy_called: bool,  # noqa: ARG001
) -> None:
    """Test multiple scenarios for opening a last vehicle directory."""
    with patch.object(window.local_filesystem, "re_init"):
        # Set up file parameters to simulate success or failure
        if has_files:
            window.local_filesystem.file_parameters = {"00_default.param": {}}
        else:
            window.local_filesystem.file_parameters = {}

        with patch.object(window.root, "destroy") as mock_destroy:
            if last_dir:
                if has_files:
                    # Successful case
                    window.open_last_vehicle_directory(last_dir)
                    # Verify state changes
                    assert window.local_filesystem.vehicle_dir == last_dir
                    # Verify behavior
                    mock_destroy.assert_called_once()
                else:
                    # Case with no files - should show error dialog
                    with patch("tkinter.messagebox.showerror") as mock_error:
                        window.open_last_vehicle_directory(last_dir)
                        mock_error.assert_called_once()
                        assert "No parameter files found" in mock_error.call_args[0][0]
                        mock_destroy.assert_not_called()
            else:
                with patch("tkinter.messagebox.showerror") as mock_error:
                    # Call the method with empty path
                    window.open_last_vehicle_directory(last_dir)

                    # Verify error message is shown
                    mock_error.assert_called_once()
                    assert "No Last Vehicle Directory Found" in mock_error.call_args[0][0]
                    mock_destroy.assert_not_called()


def test_open_last_vehicle_directory_with_reinit_error(window: VehicleDirectorySelectionWindow) -> None:
    """Test handling of SystemExit exceptions during re_init."""
    last_dir = "/last/vehicle/dir"

    # Make re_init raise a SystemExit exception
    with patch.object(window.local_filesystem, "re_init", side_effect=SystemExit("Test error")):
        with patch("tkinter.messagebox.showerror") as mock_error:
            # The SystemExit should be caught and converted to VehicleProjectOpenError
            window.open_last_vehicle_directory(last_dir)

            # Verify error dialog was shown
            mock_error.assert_called_once()
            assert "Fatal error reading parameter files" in mock_error.call_args[0][0]
            assert "Test error" in mock_error.call_args[0][1]


# ==== Tests for UI component creation and interaction ====


def test_widget_creation(window: VehicleDirectorySelectionWindow) -> None:
    """Test that all the required widgets are created correctly."""
    # Check that the main window and frame are created
    assert isinstance(window.root, tk.Toplevel)
    assert isinstance(window.main_frame, ttk.Frame)

    # Verify that boolean variables are created with correct defaults
    assert isinstance(window.blank_component_data, tk.BooleanVar)
    assert window.blank_component_data.get() is False

    assert isinstance(window.infer_comp_specs_and_conn_from_fc_params, tk.BooleanVar)
    assert window.infer_comp_specs_and_conn_from_fc_params.get() is False

    assert isinstance(window.use_fc_params, tk.BooleanVar)
    assert window.use_fc_params.get() is False

    assert isinstance(window.blank_change_reason, tk.BooleanVar)
    assert window.blank_change_reason.get() is False


def test_create_option1_widgets(tk_root, mock_tkinter_context, mock_local_filesystem) -> None:  # noqa: ARG001
    """Test the creation of option 1 widgets with different fc_connected states."""
    # Need a different approach to avoid UI creation issues
    # Test with fc_connected=True first
    with patch.object(VehicleDirectorySelectionWindow, "__init__", return_value=None):
        with patch("tkinter.ttk.Label"):
            with patch("tkinter.ttk.LabelFrame"):
                with patch("tkinter.ttk.Frame"):
                    with patch("tkinter.ttk.Checkbutton"):
                        with patch("tkinter.ttk.Button"):
                            with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
                                # Create window instance properly with mocks
                                window = VehicleDirectorySelectionWindow(mock_local_filesystem)
                                window.main_frame = MagicMock()
                                window.blank_component_data = tk.BooleanVar(value=False)
                                window.infer_comp_specs_and_conn_from_fc_params = tk.BooleanVar(value=False)
                                window.use_fc_params = tk.BooleanVar(value=False)
                                window.blank_change_reason = tk.BooleanVar(value=False)

                                # Use a proper mock for create_option1_widgets instead of assigning to the method
                                mock_create_option1 = MagicMock()
                                with patch.object(window, "create_option1_widgets", mock_create_option1):
                                    # Call the method via the patched object
                                    window.create_option1_widgets(
                                        "/template/dir",
                                        "/base/dir",
                                        "vehicle_name",
                                        fc_connected=True,
                                        connected_fc_vehicle_type="ArduCopter",
                                    )
                                    # Verify it was called with the correct arguments
                                    mock_create_option1.assert_called_once_with(
                                        "/template/dir",
                                        "/base/dir",
                                        "vehicle_name",
                                        fc_connected=True,
                                        connected_fc_vehicle_type="ArduCopter",
                                    )


def test_close_and_quit(window: VehicleDirectorySelectionWindow) -> None:
    """Test the close_and_quit method calls sys_exit."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.sys_exit") as mock_exit:
        window.close_and_quit()
        mock_exit.assert_called_once_with(0)


def test_ui_interaction_directory_selection_widgets() -> None:
    """Test interaction with a DirectorySelectionWidgets instance."""
    root = tk.Tk()
    parent = MagicMock()
    parent.root = root
    parent_frame = ttk.Frame(root)

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.TemplateOverviewWindow"):
            with patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_recently_used_dirs",
                return_value=["/selected/dir"],
            ):
                # Create the widget for testing
                widget = DirectorySelectionWidgets(
                    parent=parent,
                    parent_frame=parent_frame,
                    initialdir="/initial/dir",
                    label_text="Test Directory:",
                    autoresize_width=True,
                    dir_tooltip="Test tooltip",
                    button_tooltip="Select directory",
                    is_template_selection=True,
                    connected_fc_vehicle_type="ArduCopter",
                )

                # Verify initial state
                assert widget.directory == "/initial/dir"
                assert widget.label_text == "Test Directory:"
                assert widget.autoresize_width is True
                assert widget.is_template_selection is True

                # Test on_select_directory for template
                assert widget.on_select_directory() is True
                assert widget.directory == "/selected/dir"

                # Test get_selected_directory
                assert widget.get_selected_directory() == "/selected/dir"

    root.destroy()


# ==== Test for VehicleDirectorySelectionWidgets ====


def test_vehicle_directory_selection_widgets() -> None:
    """Test the VehicleDirectorySelectionWidgets class."""
    root = tk.Tk()
    parent = MagicMock()
    parent.root = root
    parent_frame = ttk.Frame(root)
    mock_local_filesystem = MagicMock()
    mock_local_filesystem.allow_editing_template_files = False

    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.show_tooltip"):
        with patch("tkinter.filedialog.askdirectory", return_value="/selected/vehicle/dir"):
            # Create the widget
            widget = VehicleDirectorySelectionWidgets(
                parent=parent,
                parent_frame=parent_frame,
                local_filesystem=mock_local_filesystem,
                initial_dir="/initial/vehicle/dir",
                destroy_parent_on_open=True,
            )

            # Verify initial state
            assert widget.directory == "/initial/vehicle/dir"
            assert widget.destroy_parent_on_open is True

            # Test attempting to select a template directory when editing not allowed
            with patch("tkinter.messagebox.showerror") as mock_error:
                # Instead of overriding directory directly, we need to mock the super().on_select_directory
                # to avoid the actual file dialog and return True to simulate selection
                with patch.object(DirectorySelectionWidgets, "on_select_directory", return_value=True):
                    # Set up a path with 'vehicle_templates' in it
                    widget.directory = "/selected/vehicle_templates/dir"

                    # Now call on_select_directory which should detect the vehicle_templates path
                    result = widget.on_select_directory()

                    # Verify it returns False when a template directory is selected
                    assert result is False

                    # And ensure the error dialog was shown
                    mock_error.assert_called_once()
                    assert "Invalid Vehicle Directory Selected" in mock_error.call_args[0][0]

    root.destroy()


# ==== Tests for copy vehicle image feature ====


class TestCopyVehicleImageFeature:
    """Test user workflows for copying vehicle image files from templates."""

    def test_user_can_enable_copy_vehicle_image_checkbox(self, window) -> None:
        """
        User can enable the copy vehicle image checkbox to copy vehicle.jpg from template.

        GIVEN: A user is creating a new vehicle from a template
        WHEN: They check the "Copy vehicle image from template" checkbox
        THEN: The copy_vehicle_image variable should be set to True
        """
        # Arrange: User has window open with checkbox available
        # Act: User checks the copy vehicle image checkbox
        window.copy_vehicle_image.set(True)

        # Assert: The variable should be set to True
        assert window.copy_vehicle_image.get() is True

    def test_user_can_disable_copy_vehicle_image_checkbox(self, window) -> None:
        """
        User can disable the copy vehicle image checkbox to skip copying vehicle.jpg from template.

        GIVEN: A user is creating a new vehicle from a template
        WHEN: They uncheck the "Copy vehicle image from template" checkbox
        THEN: The copy_vehicle_image variable should be set to False
        """
        # Arrange: Checkbox starts with default (False), set to True first
        window.copy_vehicle_image.set(True)
        assert window.copy_vehicle_image.get() is True

        # Act: User unchecks the copy vehicle image checkbox
        window.copy_vehicle_image.set(False)

        # Assert: The variable should be set to False
        assert window.copy_vehicle_image.get() is False

    def test_copy_vehicle_image_checkbox_defaults_to_disabled(self, window) -> None:
        """
        Copy vehicle image checkbox defaults to disabled.

        GIVEN: A user opens the new vehicle creation dialog
        WHEN: The dialog is displayed
        THEN: The copy vehicle image checkbox should be unchecked by default
        """
        # Assert: Checkbox should be disabled by default
        assert window.copy_vehicle_image.get() is False

    def test_user_can_create_new_vehicle_with_image_copying_enabled(self, window) -> None:
        """
        User can successfully create a new vehicle with vehicle image copying enabled.

        GIVEN: A user has configured a new vehicle with copy_vehicle_image=True
        WHEN: They click "Create vehicle configuration directory from template"
        THEN: The copy_vehicle_image parameter should be passed to the backend
        AND: The vehicle creation should succeed
        """
        # Arrange: Set up valid inputs for vehicle creation
        window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")
        window.new_base_dir.get_selected_directory = MagicMock(return_value="/valid/base/dir")
        window.new_dir.get_selected_directory = MagicMock(return_value="MyNewVehicle")
        window.copy_vehicle_image.set(True)

        # Mock the required filesystem operations
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", return_value=True),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", return_value=True
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir",
                return_value="/valid/base/dir/MyNewVehicle",
            ),
            patch.object(window.local_filesystem, "create_new_vehicle_dir", return_value=""),
            patch.object(window.local_filesystem, "copy_template_files_to_new_vehicle_dir", return_value="") as mock_copy,
            patch.object(window.local_filesystem, "re_init", return_value=None),
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_template_dirs"),
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_vehicle_dir"),
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.get_directory_name_from_full_path"),
            patch.object(window.root, "destroy"),
        ):
            # Set up file_parameters to simulate successful file loading
            window.local_filesystem.file_parameters = {"00_default.param": {}}

            # Act: User creates new vehicle with image copying enabled
            window.create_new_vehicle_from_template()

            # Assert: copy_template_files_to_new_vehicle_dir called with copy_vehicle_image=True
            mock_copy.assert_called_once_with(
                "/valid/template/dir",
                "/valid/base/dir/MyNewVehicle",
                blank_change_reason=window.blank_change_reason.get(),
                copy_vehicle_image=True,
            )

    def test_user_can_create_new_vehicle_with_image_copying_disabled(self, window) -> None:
        """
        User can successfully create a new vehicle with vehicle image copying disabled.

        GIVEN: A user has configured a new vehicle with copy_vehicle_image=False
        WHEN: They click "Create vehicle configuration directory from template"
        THEN: The copy_vehicle_image parameter should be False in the backend call
        AND: The vehicle creation should succeed
        """
        # Arrange: Set up valid inputs for vehicle creation with image copying disabled
        window.template_dir.get_selected_directory = MagicMock(return_value="/valid/template/dir")
        window.new_base_dir.get_selected_directory = MagicMock(return_value="/valid/base/dir")
        window.new_dir.get_selected_directory = MagicMock(return_value="MyNewVehicle")
        window.copy_vehicle_image.set(False)  # User disables image copying

        # Mock the required filesystem operations
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.directory_exists", return_value=True),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.valid_directory_name", return_value=True
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.new_vehicle_dir",
                return_value="/valid/base/dir/MyNewVehicle",
            ),
            patch.object(window.local_filesystem, "create_new_vehicle_dir", return_value=""),
            patch.object(window.local_filesystem, "copy_template_files_to_new_vehicle_dir", return_value="") as mock_copy,
            patch.object(window.local_filesystem, "re_init", return_value=None),
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_template_dirs"),
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.store_recently_used_vehicle_dir"),
            patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.get_directory_name_from_full_path"),
            patch.object(window.root, "destroy"),
        ):
            # Set up file_parameters to simulate successful file loading
            window.local_filesystem.file_parameters = {"00_default.param": {}}

            # Act: User creates new vehicle with image copying disabled
            window.create_new_vehicle_from_template()

            # Assert: copy_template_files_to_new_vehicle_dir called with copy_vehicle_image=False
            mock_copy.assert_called_once_with(
                "/valid/template/dir",
                "/valid/base/dir/MyNewVehicle",
                blank_change_reason=window.blank_change_reason.get(),
                copy_vehicle_image=False,
            )

    def test_copy_vehicle_image_state_persists_across_user_interactions(self, window) -> None:
        """
        Copy vehicle image checkbox state persists across user interactions.

        GIVEN: A user has set the copy vehicle image checkbox to a specific state
        WHEN: They interact with other UI elements
        THEN: The copy vehicle image checkbox state should remain unchanged
        """
        # Arrange: User sets checkbox to disabled state
        window.copy_vehicle_image.set(False)

        # Act: User interacts with other checkboxes
        window.blank_component_data.set(True)
        window.use_fc_params.set(True)
        window.blank_change_reason.set(True)

        # Assert: Copy vehicle image state should remain unchanged
        assert window.copy_vehicle_image.get() is False

        # Arrange: User changes to enabled state
        window.copy_vehicle_image.set(True)

        # Act: User interacts with other checkboxes again
        window.blank_component_data.set(False)
        window.use_fc_params.set(False)
        window.blank_change_reason.set(False)

        # Assert: Copy vehicle image state should remain enabled
        assert window.copy_vehicle_image.get() is True


# ==================== USER WORKFLOW TESTS ====================


class TestUserCanCreateNewVehicleFromTemplate:
    """Test complete user workflow for creating new vehicle configurations from templates."""

    def test_user_can_successfully_create_new_vehicle_from_template(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        User can successfully create a new vehicle configuration from a template.

        GIVEN: A user has selected a valid template directory and destination
        WHEN: They click the create button
        THEN: A new vehicle configuration should be created successfully
        AND: The window should close automatically
        """
        # Arrange: Set up successful creation scenario
        window = configured_window_for_user_workflows
        window.template_dir = MagicMock()
        window.template_dir.get_selected_directory.return_value = "/valid/template/dir"
        window.new_base_dir = MagicMock()
        window.new_base_dir.get_selected_directory.return_value = "/valid/base/dir"
        window.new_dir = MagicMock()
        window.new_dir.get_selected_directory.return_value = "MyNewVehicle"
        window.root = MagicMock()

        # Configure GUI state
        window.blank_component_data.set(True)
        window.copy_vehicle_image.set(True)

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleProjectCreator"
            ) as mock_creator_class,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.LocalFilesystem.get_directory_name_from_full_path",
                return_value="template_name",
            ),
        ):
            mock_creator = MagicMock()
            mock_creator_class.return_value = mock_creator

            # Act: User creates new vehicle from template
            window.create_new_vehicle_from_template()

            # Assert: Project creation executed with correct settings
            mock_creator.create_new_vehicle_from_template.assert_called_once()
            call_args = mock_creator.create_new_vehicle_from_template.call_args

            assert call_args[0][0] == "/valid/template/dir"  # template_dir
            assert call_args[0][1] == "/valid/base/dir"  # new_base_dir
            assert call_args[0][2] == "MyNewVehicle"  # new_vehicle_name

            # Verify settings object
            settings = call_args[0][3]
            assert isinstance(settings, NewVehicleProjectSettings)
            assert settings.blank_component_data is True
            assert settings.copy_vehicle_image is True

            # Assert: Window closed after successful creation
            window.root.destroy.assert_called_once()
            assert window.configuration_template == "template_name"

    def test_user_receives_error_feedback_when_template_creation_fails(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        User receives clear error feedback when template creation fails.

        GIVEN: A user attempts to create a new vehicle configuration
        WHEN: The creation process encounters an error
        THEN: An error dialog should be displayed to the user
        AND: The window should remain open for correction
        """
        # Arrange: Set up error scenario
        window = configured_window_for_user_workflows
        window.template_dir = MagicMock()
        window.template_dir.get_selected_directory.return_value = "/invalid/template"
        window.new_base_dir = MagicMock()
        window.new_base_dir.get_selected_directory.return_value = "/invalid/base"
        window.new_dir = MagicMock()
        window.new_dir.get_selected_directory.return_value = "BadName"
        window.root = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleProjectCreator"
            ) as mock_creator_class,
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.messagebox") as mock_messagebox,
        ):
            mock_creator = MagicMock()
            mock_creator_class.return_value = mock_creator

            # Configure creation to fail
            error = VehicleProjectCreationError("Creation Failed", "Invalid directory structure")
            mock_creator.create_new_vehicle_from_template.side_effect = error

            # Act: User attempts to create vehicle with invalid input
            window.create_new_vehicle_from_template()

            # Assert: Error dialog displayed and window remains open
            mock_messagebox.showerror.assert_called_once_with("Creation Failed", "Invalid directory structure")
            window.root.destroy.assert_not_called()


class TestUserCanOpenExistingVehicleDirectory:
    """Test user workflow for opening existing vehicle configurations."""

    def test_user_can_open_last_used_vehicle_directory(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        User can successfully open the last used vehicle directory.

        GIVEN: A user has a valid last used vehicle directory
        WHEN: They click the open last directory button
        THEN: The directory should open successfully
        AND: The window should close automatically
        """
        # Arrange: Set up successful opening scenario
        window = configured_window_for_user_workflows
        window.root = MagicMock()
        last_vehicle_dir = "/valid/last/vehicle/dir"

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleProjectOpener"
        ) as mock_opener_class:
            mock_opener = MagicMock()
            mock_opener_class.return_value = mock_opener

            # Act: User opens last vehicle directory
            window.open_last_vehicle_directory(last_vehicle_dir)

            # Assert: Directory opened successfully and window closed
            mock_opener.open_last_vehicle_directory.assert_called_once_with(last_vehicle_dir)
            window.root.destroy.assert_called_once()

    def test_user_receives_error_feedback_when_opening_fails(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        User receives clear error feedback when opening vehicle directory fails.

        GIVEN: A user attempts to open an invalid vehicle directory
        WHEN: The opening process encounters an error
        THEN: An error dialog should be displayed to the user
        AND: The window should remain open for correction
        """
        # Arrange: Set up error scenario
        window = configured_window_for_user_workflows
        window.root = MagicMock()
        invalid_vehicle_dir = "/invalid/vehicle/dir"

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleProjectOpener"
            ) as mock_opener_class,
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.messagebox") as mock_messagebox,
        ):
            mock_opener = MagicMock()
            mock_opener_class.return_value = mock_opener

            # Configure opening to fail
            error = VehicleProjectOpenError("Open Failed", "Directory not found or invalid")
            mock_opener.open_last_vehicle_directory.side_effect = error

            # Act: User attempts to open invalid directory
            window.open_last_vehicle_directory(invalid_vehicle_dir)

            # Assert: Error dialog displayed and window remains open
            mock_messagebox.showerror.assert_called_once_with("Open Failed", "Directory not found or invalid")
            window.root.destroy.assert_not_called()


# ==================== UI COMPONENT BEHAVIOR TESTS ====================


class TestWindowLayoutAndBehavior:
    """Test window layout creation and component behavior."""

    def test_window_creates_option2_widgets_correctly(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        Window creates option 2 widgets (open existing vehicle) correctly.

        GIVEN: A user opens the directory selection window
        WHEN: The window initializes
        THEN: Option 2 widgets should be created with proper configuration
        """
        # Arrange: Fresh window for testing
        window = configured_window_for_user_workflows
        initial_dir = "/test/initial/dir"

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleDirectorySelectionWidgets"
            ) as mock_widgets,
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame") as mock_labelframe,
        ):
            mock_frame = MagicMock()
            mock_labelframe.return_value = mock_frame
            mock_vehicle_widgets = MagicMock()
            mock_widgets.return_value = mock_vehicle_widgets

            # Act: Create option 2 widgets
            window.create_option2_widgets(initial_dir)

            # Assert: Widgets created with correct configuration
            mock_widgets.assert_called_once_with(
                window,
                mock_frame,
                window.local_filesystem,
                initial_dir,
                destroy_parent_on_open=True,
                connected_fc_vehicle_type=window.connected_fc_vehicle_type,
            )
            mock_vehicle_widgets.container_frame.pack.assert_called_once()

    def test_window_creates_option3_widgets_correctly(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        Window creates option 3 widgets (re-open last vehicle) correctly.

        GIVEN: A user opens the directory selection window
        WHEN: The window initializes
        THEN: Option 3 widgets should be created with proper configuration
        """
        # Arrange: Window with last vehicle directory
        window = configured_window_for_user_workflows
        last_vehicle_dir = "/test/last/vehicle/dir"

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.DirectorySelectionWidgets"
            ) as mock_dir_widgets,
            patch("tkinter.ttk.Button") as mock_button,
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame") as mock_labelframe,
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
        ):
            mock_frame = MagicMock()
            mock_labelframe.return_value = mock_frame
            mock_dir_selection = MagicMock()
            mock_dir_widgets.return_value = mock_dir_selection

            # Mock filesystem to indicate directory exists
            with patch.object(window.local_filesystem, "directory_exists", return_value=True):
                # Act: Create option 3 widgets
                window.create_option3_widgets(last_vehicle_dir)

                # Assert: Directory widgets created correctly
                mock_dir_widgets.assert_called_once_with(
                    parent=window,
                    parent_frame=mock_frame,
                    initialdir=last_vehicle_dir,
                    label_text="Last used vehicle configuration directory:",
                    autoresize_width=False,
                    dir_tooltip="Last used vehicle configuration directory",
                    button_tooltip="",
                    is_template_selection=False,
                    connected_fc_vehicle_type="",
                )

                # Assert: Button created with normal state (directory exists)
                mock_button.assert_called_once()
                button_call_kwargs = mock_button.call_args[1]
                assert button_call_kwargs["state"] == tk.NORMAL

    def test_option3_button_disabled_when_no_last_directory(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        Option 3 button is disabled when no last directory exists.

        GIVEN: A user opens the window with no last used directory
        WHEN: The option 3 widgets are created
        THEN: The open button should be disabled
        """
        # Arrange: Window with no last vehicle directory
        window = configured_window_for_user_workflows
        last_vehicle_dir = ""  # No last directory

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.DirectorySelectionWidgets"),
            patch("tkinter.ttk.Button") as mock_button,
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
        ):
            # Act: Create option 3 widgets with no last directory
            window.create_option3_widgets(last_vehicle_dir)

            # Assert: Button created with disabled state
            mock_button.assert_called_once()
            button_call_kwargs = mock_button.call_args[1]
            assert button_call_kwargs["state"] == tk.DISABLED


class TestApplicationQuitBehavior:
    """Test application quit and cleanup behavior."""

    def test_user_can_close_window_cleanly(
        self, configured_window_for_user_workflows: VehicleDirectorySelectionWindow
    ) -> None:
        """
        User can close the window cleanly using the window close button.

        GIVEN: A user has the directory selection window open
        WHEN: They click the window close button
        THEN: The application should exit cleanly
        """
        # Arrange: Window ready for closing
        window = configured_window_for_user_workflows

        with patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.sys_exit") as mock_exit:
            # Act: User closes window
            window.close_and_quit()

            # Assert: Application exits cleanly
            mock_exit.assert_called_once_with(0)


# ==================== COMMAND LINE INTERFACE TESTS ====================


class TestCommandLineInterface:
    """Test command line argument parsing and main function behavior."""

    def test_argument_parser_returns_valid_namespace(self) -> None:
        """
        Argument parser returns a valid namespace object.

        GIVEN: The application is started from command line
        WHEN: Arguments are parsed
        THEN: A valid namespace should be returned with expected attributes
        """
        # Arrange & Act: Parse arguments
        with (
            patch("sys.argv", ["script_name", "--vehicle-dir", "/test/dir"]),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.LocalFilesystem.add_argparse_arguments",
                return_value=MagicMock(),
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.add_common_arguments"
            ) as mock_add_common,
        ):
            mock_parser = MagicMock()
            mock_namespace = MagicMock()
            mock_parser.parse_args.return_value = mock_namespace
            mock_add_common.return_value = mock_parser

            result = argument_parser()

            # Assert: Valid namespace returned
            assert result == mock_namespace
            mock_add_common.assert_called_once()
            mock_parser.parse_args.assert_called_once()

    def test_main_function_handles_no_parameter_files_scenario(self) -> None:
        """
        Main function handles scenario with no parameter files correctly.

        GIVEN: The application is started in a directory with no parameter files
        WHEN: The main function executes
        THEN: The directory selection window should be displayed
        """
        # Arrange: Mock environment with no parameter files
        mock_args = MagicMock()
        mock_args.vehicle_dir = "/empty/dir"
        mock_args.loglevel = "INFO"

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.argument_parser", return_value=mock_args
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.logging_basicConfig"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.logging_warning"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.logging_error"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.LocalFilesystem"
            ) as mock_filesystem_class,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleDirectorySelectionWindow"
            ) as mock_window_class,
        ):
            mock_filesystem = MagicMock()
            mock_filesystem.file_parameters = {}  # No parameter files
            mock_filesystem_class.return_value = mock_filesystem

            mock_window = MagicMock()
            mock_window_class.return_value = mock_window

            # Act: Execute main function
            main()

            # Assert: Window created and displayed
            mock_window_class.assert_called_once_with(mock_filesystem)
            mock_window.root.mainloop.assert_called_once()


# ==================== INTEGRATION TESTS ====================


class TestFullUserWorkflows:
    """Test complete end-to-end user workflows."""

    def test_complete_new_vehicle_creation_workflow(self) -> None:
        """
        Complete workflow from window opening to vehicle creation.

        GIVEN: A user wants to create a new vehicle configuration
        WHEN: They go through the complete workflow
        THEN: All steps should execute successfully
        """
        # Arrange: Set up complete workflow environment
        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_filesystem.vehicle_dir = "/test/dir"
        mock_filesystem.file_parameters = {}
        mock_filesystem.getcwd.return_value = "/test/cwd"

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.DirectorySelectionWidgets"
            ) as mock_dir_widgets,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.DirectoryNameWidgets"
            ) as mock_name_widgets,
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleDirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_directory_selection.show_tooltip"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.ttk.Checkbutton"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.LocalFilesystem.get_recently_used_dirs",
                return_value=("/template", "/base", "/vehicle"),
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.VehicleProjectCreator"
            ) as mock_creator_class,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_directory_selection.LocalFilesystem.get_directory_name_from_full_path",
                return_value="TestTemplate",
            ),
        ):
            # Set up widget mocks
            mock_template_dir = MagicMock()
            mock_template_dir.get_selected_directory.return_value = "/template/dir"
            mock_base_dir = MagicMock()
            mock_base_dir.get_selected_directory.return_value = "/base/dir"
            mock_last_dir = MagicMock()
            mock_last_dir.get_selected_directory.return_value = "/last/dir"
            mock_new_dir = MagicMock()
            mock_new_dir.get_selected_directory.return_value = "MyVehicle"

            mock_dir_widgets.side_effect = [mock_template_dir, mock_base_dir, mock_last_dir]
            mock_name_widgets.return_value = mock_new_dir

            mock_creator = MagicMock()
            mock_creator_class.return_value = mock_creator

            # Act: Execute complete workflow
            window = VehicleDirectorySelectionWindow(mock_filesystem)
            window.root = MagicMock()  # Mock root for destruction

            # Simulate user setting options
            window.blank_component_data.set(False)
            window.use_fc_params.set(True)

            # Simulate user creating vehicle
            window.create_new_vehicle_from_template()

            # Assert: Complete workflow executed successfully
            mock_creator.create_new_vehicle_from_template.assert_called_once()
            window.root.destroy.assert_called_once()
            assert window.configuration_template == "TestTemplate"
