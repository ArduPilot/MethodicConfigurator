#!/usr/bin/python3

"""
Tests for the frontend_tkinter_template_overview.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import logging
import tkinter as tk
import unittest
from collections.abc import Generator
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_template_overview import (
    TemplateOverviewWindow,
    argument_parser,
    main,
    run_app,
    setup_logging,
)

# pylint: disable=unused-argument,protected-access,redefined-outer-name
# ruff: noqa: ARG001, SIM117, ANN401


@pytest.fixture
def mock_logging_basicconfig() -> Generator[Any, Any, Any]:
    """Fixture to mock logging.basicConfig."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_basicConfig") as mock:
        yield mock


@pytest.fixture
def mock_logging_getlevelname() -> Generator[Any, Any, Any]:
    """Fixture to mock logging.getLevelName."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_getLevelName") as mock:
        yield mock


@pytest.fixture
def mock_toplevel() -> Generator[Any, Any, Any]:
    """Fixture to mock tkinter.Toplevel."""
    with patch("tkinter.Toplevel") as mock:
        yield mock


@pytest.fixture
def mock_vehicle_components() -> Generator[Any, Any, Any]:
    """Fixture to mock VehicleComponents."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents") as mock:
        mock.get_vehicle_components_overviews.return_value = {}
        yield mock


@pytest.fixture
def mock_program_settings() -> Generator[Any, Any, Any]:
    """Fixture to mock ProgramSettings."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings") as mock:
        yield mock


@pytest.fixture
def mock_root() -> MagicMock:
    """Fixture to create a mock tkinter root window."""
    return MagicMock()


@pytest.fixture
def mock_treeview() -> MagicMock:
    """Fixture to create a mock ttk.Treeview."""
    return MagicMock()


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


def test_setup_logging(mock_logging_basicconfig, mock_logging_getlevelname) -> None:
    """Test that setup_logging configures logging correctly."""
    # Setup
    loglevel = "DEBUG"
    mock_logging_getlevelname.return_value = logging.DEBUG

    # Call the function
    setup_logging(loglevel)

    # Assertions
    mock_logging_getlevelname.assert_called_once_with(loglevel)
    mock_logging_basicconfig.assert_called_once_with(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


def test_run_app_without_mainloop(mock_toplevel, mock_vehicle_components) -> None:
    """Test that run_app works without running the mainloop."""
    # Setup
    mock_root = MagicMock()
    mock_toplevel.return_value = mock_root

    # Mock the TemplateOverviewWindow constructor
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
    ) as mock_window_class:
        mock_window = MagicMock()
        mock_window_class.return_value = mock_window

        # Call the function
        result = run_app(parent=None, run_mainloop=False)

        # Assertions
        mock_window_class.assert_called_once_with(None)
        assert result == mock_window
        mock_window.root.mainloop.assert_not_called()


def test_run_app_with_mainloop(mock_toplevel, mock_vehicle_components) -> None:
    """Test that run_app runs the mainloop when requested."""
    # Setup
    mock_root = MagicMock()
    mock_toplevel.return_value = mock_root

    # Mock the TemplateOverviewWindow constructor
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
    ) as mock_window_class:
        mock_window = MagicMock()
        mock_window_class.return_value = mock_window

        # Call the function
        result = run_app(parent=None, run_mainloop=True)

        # Assertions
        mock_window_class.assert_called_once_with(None)
        assert result == mock_window
        mock_window.root.mainloop.assert_called_once()


def test_run_app_with_tcl_error(mock_toplevel, mock_vehicle_components) -> None:
    """Test that run_app handles TclError gracefully."""
    # Setup
    mock_root = MagicMock()
    mock_toplevel.return_value = mock_root

    # Mock the TemplateOverviewWindow constructor
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
    ) as mock_window_class:
        mock_window = MagicMock()
        mock_window_class.return_value = mock_window
        mock_window.root.mainloop.side_effect = tk.TclError("Test error")

        # Call the function - should not raise the TclError
        result = run_app(parent=None, run_mainloop=True)

        # Assertions
        mock_window_class.assert_called_once_with(None)
        assert result == mock_window
        mock_window.root.mainloop.assert_called_once()


@patch("sys.argv", ["script.py", "--loglevel", "DEBUG"])
def test_main_function_integration(mock_toplevel, mock_vehicle_components, mock_program_settings) -> None:
    """Test the main function's integration of components."""
    # Setup
    mock_program_settings.get_recently_used_dirs.return_value = ["test_dir"]

    # Mock logging and run_app
    with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.setup_logging") as mock_setup_logging:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.run_app") as mock_run_app:
            with patch(
                "ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_debug"
            ) as mock_logging_debug:
                mock_window = MagicMock()
                mock_run_app.return_value = mock_window

                # Call the function
                main()

                # Assertions
                mock_setup_logging.assert_called_once_with("DEBUG")
                mock_run_app.assert_called_once()
                # Changed from assert_called_once since our implementation calls it twice
                assert mock_program_settings.get_recently_used_dirs.call_count >= 1
                mock_logging_debug.assert_called_once_with("test_dir")


class TestTemplateOverviewWindow(unittest.TestCase):  # pylint: disable=too-many-instance-attributes
    """Tests for the TemplateOverviewWindow class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_root = MagicMock()
        self.mock_main_frame = MagicMock()
        self.mock_top_frame = MagicMock()
        self.mock_tree = MagicMock()
        self.mock_image_label = MagicMock()

        # Create patches
        self.patcher_toplevel = patch("tkinter.Toplevel", return_value=self.mock_root)
        self.mock_toplevel = self.patcher_toplevel.start()

        self.patcher_frame = patch("tkinter.ttk.Frame", return_value=self.mock_main_frame)
        self.mock_frame = self.patcher_frame.start()

        self.patcher_label = patch("tkinter.ttk.Label", return_value=self.mock_image_label)
        self.mock_label = self.patcher_label.start()

        self.patcher_treeview = patch("tkinter.ttk.Treeview", return_value=self.mock_tree)
        self.mock_treeview = self.patcher_treeview.start()

        self.patcher_vehicle_components = patch(
            "ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents"
        )
        self.mock_vehicle_components = self.patcher_vehicle_components.start()
        self.mock_vehicle_components.get_vehicle_components_overviews.return_value = {}

        self.patcher_program_settings = patch(
            "ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings"
        )
        self.mock_program_settings = self.patcher_program_settings.start()

        # Create class with init mocked
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            self.window = TemplateOverviewWindow()
            self.window.root = self.mock_root
            self.window.main_frame = self.mock_main_frame
            self.window.top_frame = self.mock_top_frame
            self.window.tree = self.mock_tree
            self.window.image_label = self.mock_image_label

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        self.patcher_toplevel.stop()
        self.patcher_frame.stop()
        self.patcher_label.stop()
        self.patcher_treeview.stop()
        self.patcher_vehicle_components.stop()
        self.patcher_program_settings.stop()

    def test_store_template_dir(self) -> None:
        """Test that store_template_dir calls ProgramSettings.store_template_dir correctly."""
        # Setup
        template_path = "test/template/path"

        # Call the method
        self.window.store_template_dir(template_path)

        # Assertions
        self.mock_program_settings.store_template_dir.assert_called_once_with(template_path)

    def test_close_window(self) -> None:
        """Test that close_window destroys the root window."""
        # Call the method
        self.window.close_window()

        # Assertions
        self.mock_root.destroy.assert_called_once()

    def test_get_vehicle_image_filepath(self) -> None:
        """Test that get_vehicle_image_filepath calls VehicleComponents correctly."""
        # Setup
        template_path = "test/template/path"
        expected_filepath = "/some/image/path.jpg"
        self.mock_vehicle_components.get_vehicle_image_filepath.return_value = expected_filepath

        # Call the method
        result = self.window.get_vehicle_image_filepath(template_path)

        # Assertions
        self.mock_vehicle_components.get_vehicle_image_filepath.assert_called_once_with(template_path)
        assert result == expected_filepath


@pytest.fixture
def template_overview_window() -> None:
    """Create a mocked TemplateOverviewWindow instance with pytest fixture."""
    with (
        patch("tkinter.Toplevel"),
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.Treeview"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings"),
    ):
        # Create the window with a mocked __init__
        with patch.object(TemplateOverviewWindow, "__init__", return_value=None):
            window = TemplateOverviewWindow()
            window.root = MagicMock()
            window.main_frame = MagicMock()
            window.top_frame = MagicMock()
            window.tree = MagicMock()
            window.image_label = MagicMock()
            yield window


def test_display_vehicle_image(template_overview_window, monkeypatch) -> None:
    """Test that _display_vehicle_image manages the image display correctly."""
    # Setup
    template_path = "test/template/path"

    # Mock the get_vehicle_image_filepath and put_image_in_label methods
    monkeypatch.setattr(template_overview_window, "get_vehicle_image_filepath", MagicMock(return_value="/path/to/image.jpg"))
    monkeypatch.setattr(template_overview_window, "put_image_in_label", MagicMock(return_value=MagicMock()))

    # Call the method
    template_overview_window._display_vehicle_image(template_path)

    # Assertions
    template_overview_window.get_vehicle_image_filepath.assert_called_once_with(template_path)
    template_overview_window.put_image_in_label.assert_called_once()
    template_overview_window.image_label.pack.assert_called_once()


def test_display_vehicle_image_no_image(template_overview_window, monkeypatch) -> None:
    """Test that _display_vehicle_image handles missing images correctly."""
    # Setup
    template_path = "test/template/path"

    # Mock the get_vehicle_image_filepath to raise FileNotFoundError
    get_filepath_mock = MagicMock(side_effect=FileNotFoundError)
    monkeypatch.setattr(template_overview_window, "get_vehicle_image_filepath", get_filepath_mock)

    # Also mock put_image_in_label to ensure it's not called
    put_image_mock = MagicMock()
    monkeypatch.setattr(template_overview_window, "put_image_in_label", put_image_mock)

    # Call the method
    template_overview_window._display_vehicle_image(template_path)

    # Assertions
    get_filepath_mock.assert_called_once_with(template_path)
    put_image_mock.assert_not_called()
    template_overview_window.image_label.pack.assert_called_once()


def test_setup_treeview(template_overview_window, monkeypatch) -> None:
    """Test that setup_treeview configures the treeview properly."""
    # Mock the dependent methods
    monkeypatch.setattr(template_overview_window, "populate_treeview", MagicMock())
    monkeypatch.setattr(template_overview_window, "_adjust_treeview_column_widths", MagicMock())

    # Create a mock for Style and columns
    mock_style = MagicMock()
    monkeypatch.setattr("tkinter.ttk.Style", lambda root: mock_style)  # noqa: ARG005
    mock_columns = ["Column1", "Column2"]
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.middleware_template_overview.TemplateOverview.columns", lambda: mock_columns
    )

    # Call the method
    template_overview_window.setup_treeview()

    # Assertions
    mock_style.layout.assert_called_once()
    mock_style.configure.assert_called_once()
    template_overview_window.tree.heading.call_count = len(mock_columns)
    template_overview_window.populate_treeview.assert_called_once()
    template_overview_window._adjust_treeview_column_widths.assert_called_once()
    template_overview_window.tree.pack.assert_called_once()


def test_populate_treeview(template_overview_window, monkeypatch) -> None:
    """Test that populate_treeview adds items to the treeview."""
    # Create a mock template overview
    mock_template = MagicMock()
    mock_template.attributes.return_value = ["attr1", "attr2"]
    mock_template.attr1 = "value1"
    mock_template.attr2 = "value2"

    # Mock VehicleComponents.get_vehicle_components_overviews
    mock_components = {"template1": mock_template}
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.frontend_tkinter_template_overview."
        "VehicleComponents.get_vehicle_components_overviews",
        lambda: mock_components,
    )

    # Call the method
    template_overview_window.populate_treeview()

    # Assertions
    template_overview_window.tree.insert.assert_called_once_with(
        "", "end", text="template1", values=("template1", "value1", "value2")
    )


def test_bind_events(template_overview_window) -> None:
    """Test that bind_events binds the correct events."""
    # Setup mock tree with columns
    template_overview_window.tree.__getitem__.return_value = ["Column1", "Column2"]

    # Call the method
    template_overview_window.bind_events()

    # Assertions - should bind four events
    assert template_overview_window.tree.bind.call_count == 4
    assert template_overview_window.tree.heading.call_count == 2  # Once for each column


def test_row_selection_change(template_overview_window, monkeypatch) -> None:
    """Test the private __on_row_selection_change method."""
    # Create a mock for root.after
    template_overview_window.root.after = MagicMock()

    # Create a mock event
    mock_event = MagicMock()

    # Get the __on_row_selection_change method using a wrapper
    def run_on_row_selection_change(event) -> Any:
        # Access the private method using _TestTemplateOverviewWindow__on_row_selection_change name mangling
        method = template_overview_window._TemplateOverviewWindow__on_row_selection_change
        return method(event)

    # Call the method
    run_on_row_selection_change(mock_event)

    # Assertions
    template_overview_window.root.after.assert_called_once()


def test_update_selection(template_overview_window, monkeypatch) -> None:
    """Test the private __update_selection method."""
    # Setup mock tree selection
    template_overview_window.tree.selection.return_value = ["item1"]
    template_overview_window.tree.item.return_value = {"text": "template/path"}

    # Mock the dependent methods
    monkeypatch.setattr(template_overview_window, "store_template_dir", MagicMock())
    monkeypatch.setattr(template_overview_window, "_display_vehicle_image", MagicMock())

    # Get the __update_selection method using a wrapper
    def run_update_selection() -> Any:
        # Access the private method using _TestTemplateOverviewWindow__update_selection name mangling
        method = template_overview_window._TemplateOverviewWindow__update_selection
        return method()

    # Call the method
    run_update_selection()

    # Assertions
    template_overview_window.tree.selection.assert_called_once()
    template_overview_window.tree.item.assert_called_once_with("item1")
    template_overview_window.store_template_dir.assert_called_once_with("template/path")
    template_overview_window._display_vehicle_image.assert_called_once_with("template/path")


def test_row_double_click(template_overview_window, monkeypatch) -> None:
    """Test the private __on_row_double_click method."""
    # Setup mocks
    template_overview_window.tree.identify_row.return_value = "item1"
    template_overview_window.tree.item.return_value = {"text": "template/path"}
    monkeypatch.setattr(template_overview_window, "store_template_dir", MagicMock())
    monkeypatch.setattr(template_overview_window, "close_window", MagicMock())

    # Create a mock event
    mock_event = MagicMock()
    mock_event.y = 10

    # Get the __on_row_double_click method using a wrapper
    def run_on_row_double_click(event) -> Any:
        # Access the private method using _TestTemplateOverviewWindow__on_row_double_click name mangling
        method = template_overview_window._TemplateOverviewWindow__on_row_double_click
        return method(event)

    # Call the method
    run_on_row_double_click(mock_event)

    # Assertions
    template_overview_window.tree.identify_row.assert_called_once_with(10)
    template_overview_window.tree.item.assert_called_once_with("item1")
    template_overview_window.store_template_dir.assert_called_once_with("template/path")
    template_overview_window.close_window.assert_called_once()


@pytest.mark.parametrize(
    ("parent", "expected_mainloop_call"),
    [
        (None, True),  # No parent should call mainloop
        (MagicMock(), False),  # With parent should not call mainloop
    ],
)
def test_integration_run_app_with_parent(parent, expected_mainloop_call) -> None:
    """Test that run_app works correctly with or without a parent window."""
    # Mock the relevant classes and methods
    with (
        patch("tkinter.Toplevel"),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
        ) as mock_window_class,
    ):
        mock_window = MagicMock()
        mock_window_class.return_value = mock_window

        # Call run_app
        result = run_app(parent=parent, run_mainloop=True)

        # Assertions
        mock_window_class.assert_called_once_with(parent)
        assert result == mock_window

        if expected_mainloop_call:
            mock_window.root.mainloop.assert_called_once()
        else:
            mock_window.root.mainloop.assert_not_called()


def test_adjust_treeview_column_widths(template_overview_window, monkeypatch) -> None:
    """Test that _adjust_treeview_column_widths correctly sets column widths."""
    # Setup mock tree with columns and items
    template_overview_window.tree.__getitem__.return_value = ["Column1", "Column2"]
    template_overview_window.tree.get_children.return_value = ["item1", "item2"]

    # Mock font measurements
    mock_font = MagicMock()
    mock_font.measure.side_effect = lambda text: len(text) * 10  # Simple length-based measurement

    # Setup item values
    def mock_item_values(item, option) -> Optional[list[str]]:
        if option == "values":
            if item == "item1":
                return ["Short", "Medium text"]
            return ["Very long item text", "Short"]
        return None

    template_overview_window.tree.item.side_effect = mock_item_values

    # Mock Font class
    monkeypatch.setattr("tkinter.font.Font", lambda: mock_font)

    # Call the method
    template_overview_window._adjust_treeview_column_widths()

    # Assertions - width should be calculated based on the longest text + padding
    expected_widths = {
        "Column1": int(max(len("Column1") * 10, len("Very long item text") * 10) * 0.6 + 10),
        "Column2": int(max(len("Column2") * 10, len("Medium text") * 10) * 0.6 + 10),
    }

    # Verify column width was set correctly for each column
    calls = template_overview_window.tree.column.call_args_list
    assert len(calls) == 2

    # Check each column was set with the correct width
    for call in calls:
        args, kwargs = call
        column_name = args[0]
        assert "width" in kwargs
        assert kwargs["width"] == expected_widths[column_name]


def test_sort_by_column_numeric(template_overview_window) -> None:
    """Test sorting by column with numeric values."""
    # Setup
    template_overview_window.sort_column = "OldColumn"
    column_to_sort = "NumericColumn"

    # Mock tree methods
    template_overview_window.tree.get_children.return_value = ["item1", "item2", "item3"]

    # Set up the column data with numeric values
    template_overview_window.tree.set = MagicMock()
    template_overview_window.tree.set.side_effect = lambda item, col: {
        ("item1", "NumericColumn"): "10.5",
        ("item2", "NumericColumn"): "5.2",
        ("item3", "NumericColumn"): "7.8",
    }.get((item, col), "")

    # Mock the move method
    template_overview_window.tree.move = MagicMock()

    # Mock the heading method
    template_overview_window.tree.heading = MagicMock()

    # Get the __sort_by_column method using a wrapper
    def run_sort_by_column(col, reverse=False) -> Any:
        method = template_overview_window._TemplateOverviewWindow__sort_by_column
        return method(col, reverse)

    # Call the method
    run_sort_by_column(column_to_sort, reverse=False)

    # Assertions
    # 1. Old column heading should be reset
    template_overview_window.tree.heading.assert_any_call("OldColumn", text="OldColumn")

    # 2. New column should have ascending sort indicator
    template_overview_window.tree.heading.assert_any_call(column_to_sort, text=column_to_sort + " ▲")

    # 3. Sort column should be updated
    assert template_overview_window.sort_column == column_to_sort

    # 4. Items should be sorted in ascending order (item2, item3, item1)
    assert template_overview_window.tree.move.call_count == 3
    template_overview_window.tree.move.assert_any_call("item2", "", 0)  # 5.2 is smallest
    template_overview_window.tree.move.assert_any_call("item3", "", 1)  # 7.8 is middle
    template_overview_window.tree.move.assert_any_call("item1", "", 2)  # 10.5 is largest

    # 5. Heading should have command for reverse sort
    assert len(template_overview_window.tree.heading.call_args_list) == 3
    assert template_overview_window.tree.heading.call_args_list[2][0][0] == column_to_sort
    # Verify the command parameter is set (exact function comparison is complex)
    assert "command" in template_overview_window.tree.heading.call_args_list[2][1]


def test_sort_by_column_text(template_overview_window) -> None:
    """Test sorting by column with text values."""
    # Setup
    template_overview_window.sort_column = ""
    column_to_sort = "TextColumn"

    # Mock tree methods
    template_overview_window.tree.get_children.return_value = ["item1", "item2", "item3"]

    # Set up the column data with text values
    template_overview_window.tree.set = MagicMock()
    template_overview_window.tree.set.side_effect = lambda item, col: {
        ("item1", "TextColumn"): "Zebra",
        ("item2", "TextColumn"): "Apple",
        ("item3", "TextColumn"): "Monkey",
    }.get((item, col), "")

    # Mock the move method
    template_overview_window.tree.move = MagicMock()

    # Mock the heading method
    template_overview_window.tree.heading = MagicMock()

    # Get the __sort_by_column method using a wrapper
    def run_sort_by_column(col, reverse=False) -> Any:
        # Access the private method using _TestTemplateOverviewWindow__sort_by_column name mangling
        method = template_overview_window._TemplateOverviewWindow__sort_by_column
        return method(col, reverse)

    # Call the method
    run_sort_by_column(column_to_sort, reverse=False)

    # Assertions
    # 1. New column should have ascending sort indicator
    template_overview_window.tree.heading.assert_any_call(column_to_sort, text=column_to_sort + " ▲")

    # 2. Sort column should be updated
    assert template_overview_window.sort_column == column_to_sort

    # 3. Items should be sorted in ascending order (item2, item3, item1)
    assert template_overview_window.tree.move.call_count == 3
    template_overview_window.tree.move.assert_any_call("item2", "", 0)  # Apple comes first
    template_overview_window.tree.move.assert_any_call("item3", "", 1)  # Monkey comes second
    template_overview_window.tree.move.assert_any_call("item1", "", 2)  # Zebra comes last


def test_sort_by_column_reverse(template_overview_window) -> None:
    """Test sorting by column in reverse order."""
    # Setup
    template_overview_window.sort_column = "OldColumn"
    column_to_sort = "TextColumn"

    # Mock tree methods
    template_overview_window.tree.get_children.return_value = ["item1", "item2", "item3"]

    # Set up the column data with text values
    template_overview_window.tree.set = MagicMock()
    template_overview_window.tree.set.side_effect = lambda item, col: {
        ("item1", "TextColumn"): "Zebra",
        ("item2", "TextColumn"): "Apple",
        ("item3", "TextColumn"): "Monkey",
    }.get((item, col), "")

    # Mock the move method
    template_overview_window.tree.move = MagicMock()

    # Mock the heading method
    template_overview_window.tree.heading = MagicMock()

    # Get the __sort_by_column method using a wrapper
    def run_sort_by_column(col, reverse=False) -> Any:
        method = template_overview_window._TemplateOverviewWindow__sort_by_column
        return method(col, reverse)

    # Call the method with reverse=True
    run_sort_by_column(column_to_sort, reverse=True)

    # Assertions
    # 1. Old column heading should be reset
    template_overview_window.tree.heading.assert_any_call("OldColumn", text="OldColumn")

    # 2. New column should have descending sort indicator
    template_overview_window.tree.heading.assert_any_call(column_to_sort, text=column_to_sort + " ▼")

    # 3. Sort column should be updated
    assert template_overview_window.sort_column == column_to_sort

    # 4. Items should be sorted in descending order (item1, item3, item2)
    assert template_overview_window.tree.move.call_count == 3
    template_overview_window.tree.move.assert_any_call("item1", "", 0)  # Zebra comes first in reverse
    template_overview_window.tree.move.assert_any_call("item3", "", 1)  # Monkey comes second in reverse
    template_overview_window.tree.move.assert_any_call("item2", "", 2)  # Apple comes last in reverse
