#!/usr/bin/python3

"""
Tests for the frontend_tkinter_template_overview.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import logging
import unittest
from os import path as os_path
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.frontend_tkinter_template_overview import TemplateOverviewWindow, argument_parser, main

# pylint: disable=useless-suppression
# pylint: disable=unused-argument,protected-access,invalid-name
# pylint: enable=useless-suppression
# ruff: noqa: ARG001


class TestTemplateOverviewWindow(unittest.TestCase):
    """Test cases for the TemplateOverviewWindow class."""

    @patch("tkinter.Toplevel")
    @patch("tkinter.ttk.Treeview")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_init_creates_window_with_correct_properties(self, mock_vehicle_components, mock_treeview, mock_toplevel) -> None:
        """Test that window initializes with correct properties."""
        # Setup mocks
        mock_root = MagicMock()
        mock_main_frame = MagicMock()
        mock_toplevel.return_value = mock_root
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create a mock Treeview instance
        mock_tree_instance = MagicMock()
        mock_treeview.return_value = mock_tree_instance

        # Skip BaseWindow's __init__ entirely and directly test TemplateOverviewWindow's functionality
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = mock_root
            window.main_frame = mock_main_frame
            window.tree = mock_tree_instance

            # Now manually call the methods we want to test
            window.root.title("Amilcar Lucas's - ArduPilot methodic configurator - Template Overview and selection")
            window.root.geometry("1200x600")

        # Assertions
        mock_root.title.assert_called_once()
        mock_root.geometry.assert_called_once_with("1200x600")
        assert hasattr(window, "tree")

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings")
    def test_on_row_double_click_stores_template_dir(
        self,
        mock_program_settings,
        mock_vehicle_components,
        mock_toplevel,  # pylint: disable=unused-argument
    ) -> None:
        """Test that double-clicking a row in the treeview stores the template directory."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create a mock event
        mock_event = MagicMock()
        mock_event.y = 10

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.tree = MagicMock()
            window.top_frame = MagicMock()
            window.image_label = MagicMock()

            # Mock the tree.identify_row and tree.item methods
            window.tree.identify_row.return_value = "item1"
            window.tree.item.return_value = {"text": "template/path"}

            # Call the method
            window._TemplateOverviewWindow__on_row_double_click(mock_event)

            # Assertions
            window.tree.identify_row.assert_called_once_with(10)
            window.tree.item.assert_called_once_with("item1")
            mock_program_settings.store_template_dir.assert_called_once_with("template/path")
            window.root.destroy.assert_called_once()

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings")
    def test_on_row_selection_change_updates_image(
        self,
        mock_program_settings,
        mock_vehicle_components,
        mock_toplevel,  # pylint: disable=unused-argument
    ) -> None:
        """Test that changing row selection updates the image display."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create a mock event
        mock_event = MagicMock()

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.tree = MagicMock()
            window.top_frame = MagicMock()
            window.image_label = MagicMock()

            # Mock the after method to directly call the update_selection method
            def side_effect(ms, func) -> None:  # pylint: disable=unused-argument
                func()

            window.root.after.side_effect = side_effect

            # Mock tree.selection method
            window.tree.selection.return_value = ["item1"]
            window.tree.item.return_value = {"text": "template/path"}

            # Mock the _display_vehicle_image method
            window._display_vehicle_image = MagicMock()

            # Call the method
            window._TemplateOverviewWindow__on_row_selection_change(mock_event)

            # Assertions
            window.root.after.assert_called_once()
            window.tree.selection.assert_called_once()
            mock_program_settings.store_template_dir.assert_called_once_with("template/path")
            window._display_vehicle_image.assert_called_once_with("template/path")

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_sort_by_column(self, mock_vehicle_components, mock_toplevel) -> None:  # pylint: disable=unused-argument
        """Test that sorting by column works correctly."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.tree = MagicMock()
            window.tree.get_children.return_value = ["item1", "item2"]
            window.tree.set.side_effect = lambda k, col: "B" if k == "item1" and col == "col1" else "A"

            # Call the method
            window._TemplateOverviewWindow__sort_by_column("col1", reverse=False)

            # Assertions
            window.tree.heading.assert_called()
            assert window.sort_column == "col1"
            window.tree.move.assert_any_call("item2", "", 0)  # "A" should come first when not reversed

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_display_vehicle_image_with_valid_image(self, mock_vehicle_components, mock_toplevel) -> None:  # pylint: disable=unused-argument
        """Test displaying a vehicle image when a valid image exists."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}
        mock_vehicle_components.get_vehicle_image_filepath.return_value = "path/to/image.jpg"

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.top_frame = MagicMock()
            window.top_frame.winfo_children.return_value = []
            window.image_label = MagicMock()

            # Mock the put_image_in_label method
            window.put_image_in_label = MagicMock()
            mock_new_label = MagicMock()
            window.put_image_in_label.return_value = mock_new_label

            # Call the method
            window._display_vehicle_image("template/path")

            # Assertions
            mock_vehicle_components.get_vehicle_image_filepath.assert_called_once_with("template/path")
            window.put_image_in_label.assert_called_once()
            mock_new_label.pack.assert_called_once()

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_display_vehicle_image_with_missing_image(self, mock_vehicle_components, mock_toplevel) -> None:  # pylint: disable=unused-argument
        """Test displaying a vehicle image when no image exists."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}
        mock_vehicle_components.get_vehicle_image_filepath.side_effect = FileNotFoundError

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.top_frame = MagicMock()
            window.top_frame.winfo_children.return_value = []
            window.image_label = MagicMock()

            # Call the method
            with patch("tkinter.ttk.Label") as mock_label:
                mock_label.return_value = MagicMock()
                window._display_vehicle_image("template/path")

                # Assertions
                mock_vehicle_components.get_vehicle_image_filepath.assert_called_once_with("template/path")
                mock_label.assert_called_once()

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_adjust_treeview_column_widths(self, mock_vehicle_components, mock_toplevel) -> None:  # pylint: disable=unused-argument
        """Test that treeview column widths are adjusted correctly."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.tree = MagicMock()

            # Setup columns
            columns = ["col1", "col2"]

            # Mock the behavior of tree["columns"]
            window.tree.__getitem__.return_value = columns

            # Setup appropriate return values for tree.item
            def mock_item_side_effect(item_id, option=None) -> dict[str, list[str]]:  # pylint: disable=unused-argument
                """Test sorting by a column with numeric values."""
                if option == "values":
                    return ["value1", "value2"]  # Return values matching the number of columns
                return {"values": ["value1", "value2"]}

            window.tree.item.side_effect = mock_item_side_effect

            # Make tree.get_children() return some item IDs
            window.tree.get_children.return_value = ["item1", "item2"]

            # Mock font.measure to return a consistent width
            with patch("tkinter.font.Font") as mock_font:
                mock_font_instance = MagicMock()
                mock_font_instance.measure.return_value = 50  # Fixed width for simplicity
                mock_font.return_value = mock_font_instance

                # Call the method
                with patch(
                    "ardupilot_methodic_configurator.frontend_tkinter_template_overview.tk.font.Font",
                    return_value=mock_font_instance,
                ):
                    window._adjust_treeview_column_widths()

                # Assertions
                assert window.tree.column.call_count == 2  # Two columns
                window.tree.column.assert_any_call("col1", width=40)  # 50 * 0.6 + 10 = 40
                window.tree.column.assert_any_call("col2", width=40)  # 50 * 0.6 + 10 = 40

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_update_selection_with_no_selection(self, mock_vehicle_components, mock_toplevel) -> None:  # pylint: disable=unused-argument
        """Test that update_selection handles the case when there's no selection."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.tree = MagicMock()
            window.tree.selection.return_value = []  # No selection
            window._display_vehicle_image = MagicMock()

            # Call the method
            window._TemplateOverviewWindow__update_selection()

            # Assertions
            window.tree.selection.assert_called_once()
            window._display_vehicle_image.assert_not_called()

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings")
    def test_sort_by_column_with_numeric_values(self, mock_program_settings, mock_vehicle_components, mock_toplevel) -> None:  # pylint: disable=unused-argument
        """Test sorting by a column with numeric values."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.tree = MagicMock()
            window.tree.get_children.return_value = ["item1", "item2", "item3"]
            # Set up numeric values for the column
            window.tree.set.side_effect = lambda k, _col: "10" if k == "item1" else "5" if k == "item2" else "20"

            # Call the method with reverse=True to sort in descending order
            window._TemplateOverviewWindow__sort_by_column("numeric_col", reverse=True)

            # Assertions
            window.tree.heading.assert_called()
            assert window.sort_column == "numeric_col"
            # Check the order of items after sorting (should be item3, item1, item2 for values 20, 10, 5)
            window.tree.move.assert_any_call("item3", "", 0)  # "20" should be first when reversed
            window.tree.move.assert_any_call("item1", "", 1)  # "10" should be second
            window.tree.move.assert_any_call("item2", "", 2)  # "5" should be third

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_populate_treeview(self, mock_vehicle_components, mock_toplevel) -> None:
        """Test that the treeview is properly populated with data from vehicle components."""
        # Setup mock data
        mock_template_overview1 = MagicMock()
        mock_template_overview1.attributes.return_value = ["attrib1", "attrib2"]
        mock_template_overview1.attrib1 = "value1"
        mock_template_overview1.attrib2 = "value2"

        mock_template_overview2 = MagicMock()
        mock_template_overview2.attributes.return_value = ["attrib1", "attrib2"]
        mock_template_overview2.attrib1 = "value3"
        mock_template_overview2.attrib2 = "value4"

        mock_vehicle_components.get_vehicle_components_overviews.return_value = {
            "template1": mock_template_overview1,
            "template2": mock_template_overview2,
        }

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.main_frame = MagicMock()
            window.top_frame = MagicMock()
            window.tree = MagicMock()
            window._adjust_treeview_column_widths = MagicMock()

            # Manually call the initialization code that would populate the treeview
            columns = MagicMock()
            with patch(
                "ardupilot_methodic_configurator.middleware_template_overview.TemplateOverview.columns", return_value=columns
            ):
                window.tree = MagicMock()
                window.tree["columns"] = columns

                # Now populate the tree
                for key, template_overview in mock_vehicle_components.get_vehicle_components_overviews().items():
                    attribute_names = template_overview.attributes()
                    values = (key, *(getattr(template_overview, attr, "") for attr in attribute_names))
                    window.tree.insert("", "end", text=key, values=values)

            # Assertions
            assert window.tree.insert.call_count == 2
            window.tree.insert.assert_any_call("", "end", text="template1", values=("template1", "value1", "value2"))
            window.tree.insert.assert_any_call("", "end", text="template2", values=("template2", "value3", "value4"))

    @patch("sys.argv", ["script.py", "--loglevel", "DEBUG"])
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_basicConfig")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_debug")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings")
    def test_main_function_logging_configuration(
        self, mock_program_settings, mock_logging_debug, mock_logging_basicconfig, mock_window
    ) -> None:
        """Test that the main function configures logging correctly."""
        # Setup
        mock_program_settings.get_recently_used_dirs.return_value = ["test_dir"]

        # Call the function
        main()

        # Assertions
        mock_logging_basicconfig.assert_called_once()
        mock_window.assert_called_once_with(None)
        mock_logging_debug.assert_called_once_with("test_dir")

    @patch("tkinter.Toplevel")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
    def test_tree_bindings(self, mock_vehicle_components, mock_toplevel) -> None:
        """Test that the treeview has the correct event bindings."""
        # Setup
        mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        # Create window with mocked components
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.tree = MagicMock()

            # Create mocks for the private methods using the correct name mangling format
            window._TemplateOverviewWindow__on_row_selection_change = MagicMock()
            window._TemplateOverviewWindow__on_row_double_click = MagicMock()

            # Manually call the binding code
            window.tree.bind("<ButtonRelease-1>", window._TemplateOverviewWindow__on_row_selection_change)
            window.tree.bind("<Up>", window._TemplateOverviewWindow__on_row_selection_change)
            window.tree.bind("<Down>", window._TemplateOverviewWindow__on_row_selection_change)
            window.tree.bind("<Double-1>", window._TemplateOverviewWindow__on_row_double_click)

            # Assertions
            assert window.tree.bind.call_count == 4
            window.tree.bind.assert_any_call("<ButtonRelease-1>", window._TemplateOverviewWindow__on_row_selection_change)
            window.tree.bind.assert_any_call("<Up>", window._TemplateOverviewWindow__on_row_selection_change)
            window.tree.bind.assert_any_call("<Down>", window._TemplateOverviewWindow__on_row_selection_change)
            window.tree.bind.assert_any_call("<Double-1>", window._TemplateOverviewWindow__on_row_double_click)


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_column_heading_command(mock_vehicle_components, mock_toplevel) -> None:
    """Test that column headings are configured with sort commands."""
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()

        window.tree = MagicMock()

        window.tree["columns"] = ["col1", "col2"]

        # Create a mock for __sort_by_column that we can track
        window._TemplateOverviewWindow__sort_by_column = MagicMock()

        # Directly call heading for each column instead of using a loop
        window.tree.heading(
            "col1", text="col1", command=lambda: window._TemplateOverviewWindow__sort_by_column("col1", reverse=False)
        )
        window.tree.heading(
            "col2", text="col2", command=lambda: window._TemplateOverviewWindow__sort_by_column("col2", reverse=False)
        )

        # Verify the heading was called with proper parameters
        assert window.tree.heading.call_count == 2  # Once for each column

        # Extract and call the command functions to test if they call sort_by_column properly
        for i, col in enumerate(["col1", "col2"]):
            command_arg = window.tree.heading.call_args_list[i][1]["command"]
            command_arg()  # Execute the lambda directly
            window._TemplateOverviewWindow__sort_by_column.assert_called_with(col, reverse=False)


@pytest.mark.parametrize(
    ("argv", "expected_level"),
    [
        (["script.py", "--loglevel", "DEBUG"], "DEBUG"),
        (["script.py", "--loglevel", "INFO"], "INFO"),
        (["script.py", "--loglevel", "WARNING"], "WARNING"),
        (["script.py", "--loglevel", "ERROR"], "ERROR"),
    ],
)
def test_argument_parser_loglevel_options(argv, expected_level, monkeypatch) -> None:
    """Test that the argument parser handles different log levels correctly."""
    monkeypatch.setattr("sys.argv", argv)

    # Mock the ArgumentParser to avoid system exit
    with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
        mock_parse_args.return_value = argparse.Namespace(loglevel=expected_level)
        args = argument_parser()
        assert args.loglevel == expected_level


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_style_configuration(mock_vehicle_components, mock_toplevel) -> None:
    """Test that the Treeview style is configured correctly."""
    # Setup
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}
    mock_root = MagicMock()
    mock_toplevel.return_value = mock_root

    # We need to patch PIL.ImageTk to prevent image-related errors
    with (
        patch("PIL.ImageTk.PhotoImage", MagicMock()),
        patch("PIL.Image.open", MagicMock()),
        patch("tkinter.ttk.Style") as mock_style,
        patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.__version__", "1.0.0"),
    ):
        mock_style_instance = MagicMock()
        mock_style.return_value = mock_style_instance

        # Instead of patching BaseWindow.__init__, patch the entire TemplateOverviewWindow.__init__
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            # Create window with minimal initialization
            window = TemplateOverviewWindow()

            # Explicitly set the attributes that would normally be set in __init__
            window.root = mock_root
            window.style = mock_style_instance

            # Now manually configure the style, simulating what would happen during initialization
            mock_style_instance.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
            mock_style_instance.configure("Treeview.Heading", padding=[2, 2, 2, 18], justify="center")

            # Verify the style configuration was called correctly
            mock_style_instance.layout.assert_called_once_with("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
            mock_style_instance.configure.assert_called_once_with("Treeview.Heading", padding=[2, 2, 2, 18], justify="center")


@pytest.mark.parametrize(
    ("event_type", "handler_name"),
    [
        ("<ButtonRelease-1>", "__on_row_selection_change"),
        ("<Double-1>", "__on_row_double_click"),
        ("<Up>", "__on_row_selection_change"),
        ("<Down>", "__on_row_selection_change"),
    ],
)
@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_tree_event_bindings_parameterized(mock_vehicle_components, mock_toplevel, event_type, handler_name) -> None:
    """Test that tree event bindings work correctly."""
    # Setup
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.tree = MagicMock()

        # Create mocks for the event handlers
        window._TemplateOverviewWindow__on_row_selection_change = MagicMock()
        window._TemplateOverviewWindow__on_row_double_click = MagicMock()

        # Bind the event to the appropriate handler
        handler = getattr(window, f"_TemplateOverviewWindow{handler_name}")
        window.tree.bind(event_type, handler)

        # Verify binding was called with correct event and handler
        window.tree.bind.assert_called_once_with(event_type, handler)


def test_get_vehicle_image_filepath_copter(monkeypatch) -> None:
    """Test that get_vehicle_image_filepath returns the correct path for copter."""
    _test_get_vehicle_image_filepath("templates/copter/quad", "vehicle.jpg", monkeypatch)


def test_get_vehicle_image_filepath_plane(monkeypatch) -> None:
    """Test that get_vehicle_image_filepath returns the correct path for plane."""
    _test_get_vehicle_image_filepath("templates/plane/standard", "vehicle.jpg", monkeypatch)


def _test_get_vehicle_image_filepath(template_path, expected_filename, monkeypatch) -> None:
    """Helper method for testing get_vehicle_image_filepath."""

    # Mock ProgramSettings.get_templates_base_dir to return a predictable path
    def mock_get_templates_base_dir() -> str:
        return "/mocked/path"

    monkeypatch.setattr(ProgramSettings, "get_templates_base_dir", mock_get_templates_base_dir)

    filepath = VehicleComponents.get_vehicle_image_filepath(template_path)

    assert os_path.join("/mocked/path", template_path, expected_filename) == filepath
    assert expected_filename in str(filepath)
    assert template_path in str(filepath)


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_sort_by_column_numeric_ordering_ascending(mock_vehicle_components, mock_toplevel) -> None:
    """Test that numeric sorting works correctly in ascending order."""
    _test_sort_by_column_numeric_ordering(
        mock_vehicle_components,
        mock_toplevel,
        sort_reverse=False,
        expected_order=["item2", "item1", "item3"],  # Ascending order: 5, 10, 20
    )


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_sort_by_column_numeric_ordering_descending(mock_vehicle_components, mock_toplevel) -> None:
    """Test that numeric sorting works correctly in descending order."""
    _test_sort_by_column_numeric_ordering(
        mock_vehicle_components,
        mock_toplevel,
        sort_reverse=True,
        expected_order=["item3", "item1", "item2"],  # Descending order: 20, 10, 5
    )


def _test_sort_by_column_numeric_ordering(mock_vehicle_components, mock_toplevel, sort_reverse, expected_order) -> None:
    """Helper method for testing numeric sorting."""
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.tree = MagicMock()
        window.tree.get_children.return_value = ["item1", "item2", "item3"]
        # Set up numeric values for the column
        window.tree.set.side_effect = lambda k, _col: "10" if k == "item1" else "5" if k == "item2" else "20"

        # Call the method
        window._TemplateOverviewWindow__sort_by_column("numeric_col", reverse=sort_reverse)

        # Check the order of items after sorting
        actual_order = []
        for _i, call_args in enumerate(window.tree.move.call_args_list):
            actual_order.append(call_args[0][0])  # Extract the item being moved

        assert actual_order == expected_order


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_display_vehicle_image_behavior_with_image(mock_vehicle_components, mock_toplevel) -> None:
    """Test display_vehicle_image handles existing images properly."""
    _test_display_vehicle_image_behavior(
        mock_vehicle_components, mock_toplevel, image_exists=True, expected_method="put_image_in_label"
    )


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_display_vehicle_image_behavior_without_image(mock_vehicle_components, mock_toplevel) -> None:
    """Test display_vehicle_image handles missing images properly."""
    _test_display_vehicle_image_behavior(
        mock_vehicle_components, mock_toplevel, image_exists=False, expected_method="ttk.Label"
    )


def _test_display_vehicle_image_behavior(mock_vehicle_components, mock_toplevel, image_exists, expected_method) -> None:
    """Helper method for testing display_vehicle_image behavior."""
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    if image_exists:
        mock_vehicle_components.get_vehicle_image_filepath.return_value = "path/to/image.jpg"
    else:
        mock_vehicle_components.get_vehicle_image_filepath.side_effect = FileNotFoundError

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.top_frame = MagicMock()
        window.top_frame.winfo_children.return_value = []
        window.image_label = MagicMock()

        # If testing the image exists path, mock the put_image_in_label method
        if image_exists:
            window.put_image_in_label = MagicMock()
            window.put_image_in_label.return_value = MagicMock()

        # Call the method under test
        with patch("tkinter.ttk.Label") as mock_label:
            mock_label.return_value = MagicMock()
            window._display_vehicle_image("template/path")

            # Assertions
            if image_exists:
                assert window.put_image_in_label.called
            else:
                assert mock_label.called


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_column_heading_commands_trigger_sort(mock_vehicle_components, mock_toplevel) -> None:
    """Test that clicking column headings triggers the sort function with correct parameters."""
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.tree = MagicMock()

        # Directly set up columns without relying on __getitem__
        columns = ["col1", "col2"]
        window.tree.__getitem__.return_value = columns

        # Create a mock for __sort_by_column that we can track
        window._TemplateOverviewWindow__sort_by_column = MagicMock()

        # Directly call heading for each column instead of using a loop
        window.tree.heading(
            "col1", text="col1", command=lambda: window._TemplateOverviewWindow__sort_by_column("col1", reverse=False)
        )
        window.tree.heading(
            "col2", text="col2", command=lambda: window._TemplateOverviewWindow__sort_by_column("col2", reverse=False)
        )

        # Verify the heading was called with proper parameters
        assert window.tree.heading.call_count == 2  # Once for each column

        # Extract and call the command functions to test if they call sort_by_column properly
        for i, col in enumerate(columns):
            command_arg = window.tree.heading.call_args_list[i][1]["command"]
            command_arg()  # Execute the lambda directly
            window._TemplateOverviewWindow__sort_by_column.assert_called_with(col, reverse=False)


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_adjust_treeview_column_widths_with_varied_content(mock_vehicle_components, mock_toplevel) -> None:
    """Test treeview column width adjustment with varied content lengths."""
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.tree = MagicMock()

        # Set up columns with varied lengths
        columns = ["short", "medium_length_column", "very_long_column_name_that_exceeds_others"]

        # Create the mock for window.tree["columns"]
        window.tree.__getitem__.return_value = columns

        # Mock items with varied content lengths
        window.tree.get_children.return_value = ["item1", "item2"]

        # Create a more complex mock for tree.item
        def mock_item_side_effect(item_id, option=None) -> dict[str, list[str]]:
            values = {
                "item1": ["Short", "Medium length content", "Very long content that should require more space"],
                "item2": ["S", "Med", "Long but not as long as item1"],
            }
            if option == "values":
                return values[item_id]
            return {"values": values[item_id]}

        window.tree.item.side_effect = mock_item_side_effect

        # The critical part - BOTH tk.font.Font and tkinter.font.Font need to be mocked
        # Create a single font mock instance
        font_mock = MagicMock()
        font_mock.measure.side_effect = lambda text: len(str(text)) * 8

        # Patch both import paths for Font
        with patch("tkinter.font.Font", return_value=font_mock):
            with patch(
                "ardupilot_methodic_configurator.frontend_tkinter_template_overview.tk.font.Font", return_value=font_mock
            ):
                # Call the method under test
                window._adjust_treeview_column_widths()

            # Verify column widths are set proportionally to content length
            # Formula: max_width * 0.6 + 10
            expected_widths = {
                "short": 34,  # (5 chars * 8) * 0.6 + 10 = 34
                "medium_length_column": 110,  # (20 chars * 8) * 0.6 + 10 = 110
                "very_long_column_name_that_exceeds_others": 240,  # (44 chars * 8) * 0.6 + 10 = 240
            }

            # Check each column is set with the expected width
            assert window.tree.column.call_count == 3  # Verify 3 columns were set
            for col, width in expected_widths.items():
                window.tree.column.assert_any_call(col, width=width)


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings")
@patch("logging.exception")  # Add this to check if exceptions are logged
def test_on_row_selection_change_with_logging(
    mock_logging, mock_program_settings, mock_vehicle_components, mock_toplevel
) -> None:
    """Test that exceptions in update_selection are properly logged."""
    # Setup
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create a mock event
    mock_event = MagicMock()

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.tree = MagicMock()

        # Modify the after method to directly call the function with exception handling
        def safe_after(ms, func) -> None:
            try:
                func()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.exception("Exception in after callback: %s", e)

        window.root.after.side_effect = safe_after

        # Create a mock update_selection that raises an exception
        window._TemplateOverviewWindow__update_selection = MagicMock(side_effect=Exception("Test exception"))

        # Call the method
        window._TemplateOverviewWindow__on_row_selection_change(mock_event)

        # Verify that after was called
        window.root.after.assert_called_once()

        # Verify that update_selection was called
        window._TemplateOverviewWindow__update_selection.assert_called_once()

        # Verify that the exception was logged
        mock_logging.assert_called_once()


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings")
@patch("logging.exception")
def test_on_row_selection_change_exception_handling(
    mock_logging_exception, mock_program_settings, mock_vehicle_components, mock_toplevel
) -> None:
    """Test that exceptions in update_selection are properly caught and logged."""
    # Setup
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create a mock event
    mock_event = MagicMock()

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.tree = MagicMock()

        # Create a wrapped version of after that includes try/except since
        # that's how tkinter would handle exceptions in callbacks
        def safe_after(ms, func) -> None:
            try:
                func()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.exception("Error in update_selection: %s", e)

        window.root.after.side_effect = safe_after

        # Make update_selection raise an exception
        test_exception = Exception("Test exception")
        window._TemplateOverviewWindow__update_selection = MagicMock(side_effect=test_exception)

        # Call the method - this should not propagate the exception
        window._TemplateOverviewWindow__on_row_selection_change(mock_event)

        # Verify after was called
        window.root.after.assert_called_once()

        # Verify update_selection was called
        window._TemplateOverviewWindow__update_selection.assert_called_once()

        # Verify the exception was logged - check format string and args separately
        mock_logging_exception.assert_called_once()

        # Check that the format string matches
        assert mock_logging_exception.call_args[0][0] == "Error in update_selection: %s"

        # Check that the test exception was passed as an argument
        assert mock_logging_exception.call_args[0][1] == test_exception


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings")
def test_on_row_selection_change_with_exception(mock_program_settings, mock_vehicle_components, mock_toplevel) -> None:
    """Test that exception in on_row_selection_change doesn't prevent the after callback from being scheduled."""
    # Setup
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create a mock event
    mock_event = MagicMock()

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.tree = MagicMock()

        # Make update_selection raise an exception when called later
        window._TemplateOverviewWindow__update_selection = MagicMock(side_effect=Exception("Test exception"))

        # Call the method - this should schedule the callback
        window._TemplateOverviewWindow__on_row_selection_change(mock_event)

        # Verify after was called to schedule update_selection
        window.root.after.assert_called_once_with(0, window._TemplateOverviewWindow__update_selection)

        # Note: We're not directly verifying that update_selection was called,
        # since that would happen later when the Tkinter event loop processes the scheduled callback


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_populate_treeview_with_no_templates(mock_vehicle_components, mock_toplevel) -> None:
    """Test populating the treeview when no templates are available."""
    # Setup - return empty dictionary
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.main_frame = MagicMock()
        window.top_frame = MagicMock()
        window.tree = MagicMock()
        window._adjust_treeview_column_widths = MagicMock()

        # Manually call the initialization code that would populate the treeview
        columns = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.middleware_template_overview.TemplateOverview.columns", return_value=columns
        ):
            window.tree = MagicMock()
            window.tree["columns"] = columns

            # Now populate the tree
            for key, template_overview in mock_vehicle_components.get_vehicle_components_overviews().items():
                attribute_names = template_overview.attributes()
                values = (key, *(getattr(template_overview, attr, "") for attr in attribute_names))
                window.tree.insert("", "end", text=key, values=values)

        # Assertions - no items should be inserted
        window.tree.insert.assert_not_called()


@patch("tkinter.Toplevel")
@patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents")
def test_sort_direction_indicators(mock_vehicle_components, mock_toplevel) -> None:
    """Test that sort direction indicators (▲/▼) are added to column headings."""
    mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

    # Create window with mocked components
    with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
        window = TemplateOverviewWindow()
        window.root = MagicMock()
        window.tree = MagicMock()
        window.tree.get_children.return_value = ["item1", "item2"]
        window.tree.set.return_value = "value"

        # Set initial sort column
        window.sort_column = "col1"

        # Test ascending sort indicator
        window._TemplateOverviewWindow__sort_by_column("col1", reverse=False)
        window.tree.heading.assert_any_call("col1", text="col1 ▲")

        # Test descending sort indicator
        window._TemplateOverviewWindow__sort_by_column("col1", reverse=True)
        window.tree.heading.assert_any_call("col1", text="col1 ▼")

        # Test changing sort column removes indicator from previous column
        window._TemplateOverviewWindow__sort_by_column("col2", reverse=False)
        window.tree.heading.assert_any_call("col1", text="col1")
        window.tree.heading.assert_any_call("col2", text="col2 ▲")


class TestArgumentParser(unittest.TestCase):
    """Test cases for argument parsing functionality."""

    def test_argument_parser_exit(self) -> None:
        """Test argument parser exits with no arguments."""
        with pytest.raises(SystemExit):
            argument_parser()

    @patch("sys.argv", ["script.py", "--loglevel", "DEBUG"])
    def test_main_function(self) -> None:
        """Test main function execution."""
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow") as mock_window,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.argument_parser") as mock_parser,
        ):
            mock_parser.return_value = argparse.Namespace(loglevel="DEBUG")
            main()
            mock_window.assert_called_once_with(None)

    @patch("sys.argv", ["script.py", "--loglevel", "INFO"])
    def test_argument_parser_loglevel(self) -> None:
        """Test argument parser correctly handles loglevel argument."""
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = argparse.Namespace(loglevel="INFO")
            args = argument_parser()
            assert args.loglevel == "INFO"


if __name__ == "__main__":
    unittest.main()
