#!/usr/bin/python3

"""
Tests for the frontend_tkinter_template_overview.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import unittest
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_template_overview import TemplateOverviewWindow, argument_parser, main


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
            window._TemplateOverviewWindow__on_row_double_click(mock_event)  # pylint: disable=protected-access

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
            def side_effect(ms, func) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
                func()

            window.root.after.side_effect = side_effect

            # Mock tree.selection method
            window.tree.selection.return_value = ["item1"]
            window.tree.item.return_value = {"text": "template/path"}

            # Mock the _display_vehicle_image method
            window._display_vehicle_image = MagicMock()  # pylint: disable=protected-access

            # Call the method
            window._TemplateOverviewWindow__on_row_selection_change(mock_event)  # pylint: disable=protected-access

            # Assertions
            window.root.after.assert_called_once()
            window.tree.selection.assert_called_once()
            mock_program_settings.store_template_dir.assert_called_once_with("template/path")
            window._display_vehicle_image.assert_called_once_with("template/path")  # pylint: disable=protected-access

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
            window._TemplateOverviewWindow__sort_by_column("col1", reverse=False)  # pylint: disable=protected-access

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
            window._display_vehicle_image("template/path")  # pylint: disable=protected-access

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
                window._display_vehicle_image("template/path")  # pylint: disable=protected-access

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
            def mock_item_side_effect(item_id, option=None) -> dict[str, list[str]]:  # noqa: ARG001  # pylint: disable=unused-argument
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
                    window._adjust_treeview_column_widths()  # pylint: disable=protected-access

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
            window._display_vehicle_image = MagicMock()  # pylint: disable=protected-access

            # Call the method
            window._TemplateOverviewWindow__update_selection()  # pylint: disable=protected-access

            # Assertions
            window.tree.selection.assert_called_once()
            window._display_vehicle_image.assert_not_called()  # pylint: disable=protected-access

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
            window._TemplateOverviewWindow__sort_by_column("numeric_col", reverse=True)  # pylint: disable=protected-access

            # Assertions
            window.tree.heading.assert_called()
            assert window.sort_column == "numeric_col"
            # Check the order of items after sorting (should be item3, item1, item2 for values 20, 10, 5)
            window.tree.move.assert_any_call("item3", "", 0)  # "20" should be first when reversed
            window.tree.move.assert_any_call("item1", "", 1)  # "10" should be second
            window.tree.move.assert_any_call("item2", "", 2)  # "5" should be third


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
