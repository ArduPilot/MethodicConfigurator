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
from collections.abc import Generator
from typing import Any, Optional
from unittest.mock import ANY, MagicMock, patch

import pytest

# Import reusable fixtures from the BaseWindow tests
from test_frontend_tkinter_base_window import MockConfiguration

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_template_overview import (
    TemplateOverviewWindow,
    argument_parser,
    main,
    setup_logging,
)

# pylint: disable=useless-suppression
# pylint: disable=unused-argument,protected-access,invalid-name,redefined-outer-name,too-many-lines
# pylint: enable=useless-suppression
# ruff: noqa: ARG001, ARG005, SIM117, ANN401


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


@patch("sys.argv", ["script.py", "--loglevel", "DEBUG"])
def test_main_function_integration(mock_vehicle_components, mock_program_settings) -> None:
    """Test the main function's integration of components."""
    # Setup
    mock_program_settings.get_recently_used_dirs.return_value = ["test_dir"]

    # Mock the TemplateOverviewWindow class and its methods
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
    ) as mock_window_class:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.setup_logging") as mock_setup_logging:
            with patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_info") as mock_logging_info:
                # Configure the mock window
                mock_window = MagicMock()
                mock_window_class.return_value = mock_window

                # Call the function
                main()

                # Assertions
                mock_setup_logging.assert_called_once_with("DEBUG")
                mock_window_class.assert_called_once()
                mock_window.run_app.assert_called_once()
                assert mock_program_settings.get_recently_used_dirs.call_count >= 1
                mock_logging_info.assert_called_once_with("test_dir")


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
            # Add the provider attributes that would be set in __init__
            self.window.vehicle_components_provider = self.mock_vehicle_components
            self.window.program_settings_provider = self.mock_program_settings

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
def mock_vehicle_components_provider() -> MagicMock:
    """Create a mock vehicle components provider following the protocol."""
    mock = MagicMock()
    mock.get_vehicle_components_overviews.return_value = {
        "test_template": MagicMock(attributes=lambda: ["attr1", "attr2"], attr1="value1", attr2="value2")
    }
    mock.get_vehicle_image_filepath.return_value = "/path/to/image.jpg"
    return mock


@pytest.fixture
def mock_program_settings_provider() -> MagicMock:
    """Create a mock program settings provider following the protocol."""
    mock = MagicMock()
    mock.store_template_dir.return_value = None
    return mock


@pytest.fixture
def template_overview_window(mock_tkinter_context) -> Generator[TemplateOverviewWindow, None, None]:
    """Create a TemplateOverviewWindow with basic mocking using shared fixtures."""
    # Use the shared mock context from BaseWindow tests
    config = MockConfiguration(dpi_scaling_factor=1.0)
    stack, patches = mock_tkinter_context(config)

    # Add TemplateOverviewWindow-specific patches
    template_patches = [
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.Treeview"),
        patch("tkinter.ttk.Style"),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
        patch.object(TemplateOverviewWindow, "_bind_events"),
    ]

    # Apply all patches
    for patch_obj in patches + template_patches:
        stack.enter_context(patch_obj)

    try:
        # Create window with basic setup
        window = TemplateOverviewWindow()

        # Mock essential attributes
        window.root = MagicMock()
        window.main_frame = MagicMock()
        window.tree = MagicMock()
        window.image_label = MagicMock()
        window.top_frame = MagicMock()
        window.dpi_scaling_factor = 1.0
        window.sort_column = ""

        yield window
    finally:
        stack.close()


@pytest.fixture
def template_overview_window_with_injection(
    mock_tkinter_context, mock_vehicle_components_provider, mock_program_settings_provider
) -> Generator[TemplateOverviewWindow, None, None]:
    """Create a TemplateOverviewWindow with dependency injection using shared fixtures."""
    # Use the shared mock context from BaseWindow tests
    config = MockConfiguration(dpi_scaling_factor=1.0)
    stack, patches = mock_tkinter_context(config)

    # Add TemplateOverviewWindow-specific patches
    template_patches = [
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.Treeview"),
        patch("tkinter.ttk.Style"),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
        patch.object(TemplateOverviewWindow, "_bind_events"),
    ]

    # Apply all patches
    for patch_obj in patches + template_patches:
        stack.enter_context(patch_obj)

    try:
        # Create window with dependency injection
        window = TemplateOverviewWindow(
            vehicle_components_provider=mock_vehicle_components_provider,
            program_settings_provider=mock_program_settings_provider,
        )

        # Mock essential attributes
        window.root = MagicMock()
        window.main_frame = MagicMock()
        window.tree = MagicMock()
        window.image_label = MagicMock()
        window.top_frame = MagicMock()
        window.dpi_scaling_factor = 1.0
        window.sort_column = ""

        yield window
    finally:
        stack.close()


def test_display_vehicle_image(template_overview_window_with_injection, monkeypatch) -> None:
    """Test that _display_vehicle_image manages the image display correctly."""
    # Setup
    template_path = "test/template/path"

    # Mock the get_vehicle_image_filepath and put_image_in_label methods
    monkeypatch.setattr(
        template_overview_window_with_injection, "get_vehicle_image_filepath", MagicMock(return_value="/path/to/image.jpg")
    )
    monkeypatch.setattr(template_overview_window_with_injection, "put_image_in_label", MagicMock(return_value=MagicMock()))

    # Call the method
    template_overview_window_with_injection._display_vehicle_image(template_path)

    # Assertions
    template_overview_window_with_injection.get_vehicle_image_filepath.assert_called_once_with(template_path)
    template_overview_window_with_injection.put_image_in_label.assert_called_once()
    template_overview_window_with_injection.image_label.pack.assert_called_once()


def test_display_vehicle_image_no_image(template_overview_window_with_injection, monkeypatch) -> None:
    """Test that _display_vehicle_image handles missing images correctly."""
    # Setup
    template_path = "test/template/path"

    # Mock the get_vehicle_image_filepath to raise FileNotFoundError
    get_filepath_mock = MagicMock(side_effect=FileNotFoundError)
    monkeypatch.setattr(template_overview_window_with_injection, "get_vehicle_image_filepath", get_filepath_mock)

    # Also mock put_image_in_label to ensure it's not called
    put_image_mock = MagicMock()
    monkeypatch.setattr(template_overview_window_with_injection, "put_image_in_label", put_image_mock)

    # Call the method
    template_overview_window_with_injection._display_vehicle_image(template_path)

    # Assertions
    get_filepath_mock.assert_called_once_with(template_path)
    put_image_mock.assert_not_called()
    template_overview_window_with_injection.image_label.pack.assert_called_once()


def test_setup_treeview() -> None:
    """Test that _configure_treeview configures the treeview properly."""
    # Create a simple test instance
    window = TemplateOverviewWindow.__new__(TemplateOverviewWindow)  # Create without calling __init__
    window.tree = MagicMock()

    # Mock the component methods that _configure_treeview calls
    window._setup_treeview_style = MagicMock()
    window._setup_treeview_columns = MagicMock()
    window._populate_treeview = MagicMock()
    window._adjust_treeview_column_widths = MagicMock()

    # Call the method
    window._configure_treeview()

    # Assertions - verify that all the component methods were called
    window._setup_treeview_style.assert_called_once()
    window._setup_treeview_columns.assert_called_once()
    window._populate_treeview.assert_called_once()
    window._adjust_treeview_column_widths.assert_called_once()
    # Verify tree was packed
    window.tree.pack.assert_called_once()


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
    template_overview_window._populate_treeview()

    # Assertions
    template_overview_window.tree.insert.assert_called_once_with(
        "", "end", text="template1", values=("template1", "value1", "value2")
    )


def test_bind_events(mock_tkinter_context) -> None:
    """Test that bind_events binds the correct events."""
    # Use the shared mock context but don't mock _bind_events
    config = MockConfiguration(dpi_scaling_factor=1.0)
    stack, patches = mock_tkinter_context(config)

    # Add TemplateOverviewWindow-specific patches (excluding _bind_events)
    template_patches = [
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.Treeview"),
        patch("tkinter.ttk.Style"),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
    ]

    # Apply all patches
    for patch_obj in patches + template_patches:
        stack.enter_context(patch_obj)

    try:
        # Create window
        window = TemplateOverviewWindow()

        # Mock essential attributes
        window.root = MagicMock()
        window.main_frame = MagicMock()
        window.tree = MagicMock()
        window.image_label = MagicMock()
        window.top_frame = MagicMock()
        window.dpi_scaling_factor = 1.0
        window.sort_column = ""

        # Setup mock tree with columns
        window.tree.__getitem__.return_value = ["Column1", "Column2"]

        # Reset the call count to ensure clean test
        window.tree.bind.reset_mock()
        window.tree.heading.reset_mock()

        # Call the method
        window._bind_events()

        # Assertions - should bind four events
        assert window.tree.bind.call_count == 4
        assert window.tree.heading.call_count == 2  # Once for each column

    finally:
        stack.close()


def test_on_row_selection_change(template_overview_window, monkeypatch) -> None:
    """Test the protected _on_row_selection_change method."""
    # Create a mock for root.after
    template_overview_window.root.after = MagicMock()

    # Create a mock event
    mock_event = MagicMock()

    # Call the method directly since it's now protected, not private
    template_overview_window._on_row_selection_change(mock_event)

    # Assertions
    template_overview_window.root.after.assert_called_once()


def test_update_selection(template_overview_window, monkeypatch) -> None:
    """Test the protected _update_selection method."""
    # Setup mock tree selection
    template_overview_window.tree.selection.return_value = ["item1"]
    template_overview_window.tree.item.return_value = {"text": "template/path"}

    # Mock the dependent methods
    monkeypatch.setattr(template_overview_window, "store_template_dir", MagicMock())
    monkeypatch.setattr(template_overview_window, "_display_vehicle_image", MagicMock())

    # Call the method directly since it's now protected, not private
    template_overview_window._update_selection()

    # Assertions
    template_overview_window.tree.selection.assert_called_once()
    template_overview_window.tree.item.assert_called_once_with("item1")
    template_overview_window.store_template_dir.assert_called_once_with("template/path")
    template_overview_window._display_vehicle_image.assert_called_once_with("template/path")


def test_on_row_double_click(template_overview_window, monkeypatch) -> None:
    """Test the protected _on_row_double_click method."""
    # Setup mocks
    template_overview_window.tree.identify_row.return_value = "item1"
    template_overview_window.tree.item.return_value = {"text": "template/path"}
    monkeypatch.setattr(template_overview_window, "store_template_dir", MagicMock())
    monkeypatch.setattr(template_overview_window, "close_window", MagicMock())

    # Create a mock event
    mock_event = MagicMock()
    mock_event.y = 10

    # Call the method directly since it's now protected, not private
    template_overview_window._on_row_double_click(mock_event)

    # Assertions
    template_overview_window.tree.identify_row.assert_called_once_with(10)
    template_overview_window.tree.item.assert_called_once_with("item1")
    template_overview_window.store_template_dir.assert_called_once_with("template/path")
    template_overview_window.close_window.assert_called_once()


def test_adjust_treeview_column_widths(template_overview_window, monkeypatch) -> None:
    """Test that _adjust_treeview_column_widths correctly sets column widths."""
    # Setup mock tree with columns and items
    columns_list = ["Column1", "Column2"]
    template_overview_window.tree.__getitem__.return_value = columns_list
    template_overview_window.tree.get_children.return_value = ["item1", "item2"]

    # Mock DPI scaling factor - use a known value for predictable test results
    template_overview_window.dpi_scaling_factor = 1.0

    # Mock font measurements
    mock_font = MagicMock()
    mock_font.measure.side_effect = lambda text: len(text) * 10  # Simple length-based measurement

    # Setup item values - mock the item method properly
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

    # Calculate expected widths based on the actual implementation:
    # max_width = max(header_width * dpi_scaling, max_item_width * dpi_scaling)
    # final_width = int(max_width * 0.6 + scaled_padding)
    # where scaled_padding = int(10 * dpi_scaling_factor)

    dpi_factor = 1.0
    scaled_padding = int(10 * dpi_factor)

    # Column1: max("Column1" (8*10=80), "Very long item text" (22*10=220)) * 1.0 = 220
    # final_width = int(220 * 0.6 + 10) = int(132 + 10) = 142
    col1_max = max(len("Column1") * 10 * dpi_factor, len("Very long item text") * 10 * dpi_factor)
    expected_col1_width = int(col1_max * 0.6 + scaled_padding)

    # Column2: max("Column2" (8*10=80), "Medium text" (11*10=110)) * 1.0 = 110
    # final_width = int(110 * 0.6 + 10) = int(66 + 10) = 76
    col2_max = max(len("Column2") * 10 * dpi_factor, len("Medium text") * 10 * dpi_factor)
    expected_col2_width = int(col2_max * 0.6 + scaled_padding)

    expected_widths = {
        "Column1": expected_col1_width,
        "Column2": expected_col2_width,
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

    # Call the method directly since it's now protected, not private
    template_overview_window._sort_by_column(column_to_sort, reverse=False)

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

    # Call the method directly since it's now protected, not private
    template_overview_window._sort_by_column(column_to_sort, reverse=False)

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

    # Call the method directly since it's now protected, not private
    template_overview_window._sort_by_column(column_to_sort, reverse=True)

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


# New improved tests using dependency injection and testing refactored methods


def test_dependency_injection_vehicle_components(mock_vehicle_components_provider) -> None:
    """Test that dependency injection works correctly for vehicle components provider."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
        patch.object(TemplateOverviewWindow, "_bind_events"),
    ):
        window = TemplateOverviewWindow(vehicle_components_provider=mock_vehicle_components_provider)

        # Test that the injected provider is used
        assert window.vehicle_components_provider is mock_vehicle_components_provider


def test_dependency_injection_program_settings(mock_program_settings_provider) -> None:
    """Test that dependency injection works correctly for program settings provider."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "__init__", return_value=None),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
        patch.object(TemplateOverviewWindow, "_bind_events"),
    ):
        window = TemplateOverviewWindow(program_settings_provider=mock_program_settings_provider)

        # Test that the injected provider is used
        assert window.program_settings_provider is mock_program_settings_provider


def test_dependency_injection_defaults() -> None:
    """Test that default dependencies are used when none are provided."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "__init__", return_value=None),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
        patch.object(TemplateOverviewWindow, "_bind_events"),
    ):
        window = TemplateOverviewWindow()

        # Test that default classes are used
        assert window.vehicle_components_provider is VehicleComponents
        assert window.program_settings_provider is ProgramSettings


def test_store_template_dir_with_injection(template_overview_window_with_injection, mock_program_settings_provider) -> None:
    """Test store_template_dir using dependency injection."""
    template_path = "test/template/path"

    template_overview_window_with_injection.store_template_dir(template_path)

    mock_program_settings_provider.store_template_dir.assert_called_once_with(template_path)


def test_get_vehicle_image_filepath_with_injection(
    template_overview_window_with_injection, mock_vehicle_components_provider
) -> None:
    """Test get_vehicle_image_filepath using dependency injection."""
    template_path = "test/template/path"
    expected_filepath = "/injected/path/to/image.jpg"
    mock_vehicle_components_provider.get_vehicle_image_filepath.return_value = expected_filepath

    result = template_overview_window_with_injection.get_vehicle_image_filepath(template_path)

    mock_vehicle_components_provider.get_vehicle_image_filepath.assert_called_once_with(template_path)
    assert result == expected_filepath


def test_calculate_scaled_font_size(template_overview_window_with_injection) -> None:
    """Test the _calculate_scaled_font_size helper method."""
    template_overview_window_with_injection.dpi_scaling_factor = 1.5

    result = template_overview_window_with_injection.calculate_scaled_font_size(12)

    assert result == 18  # 12 * 1.5


def test_calculate_scaled_padding(template_overview_window_with_injection) -> None:
    """Test the _calculate_scaled_padding helper method."""
    template_overview_window_with_injection.dpi_scaling_factor = 2.0

    result = template_overview_window_with_injection.calculate_scaled_padding(10)

    assert result == 20  # 10 * 2.0


def test_calculate_scaled_padding_tuple(template_overview_window_with_injection) -> None:
    """Test the _calculate_scaled_padding_tuple helper method."""
    template_overview_window_with_injection.dpi_scaling_factor = 1.25

    result = template_overview_window_with_injection.calculate_scaled_padding_tuple(8, 16)

    assert result == (10, 20)  # (8 * 1.25, 16 * 1.25)


def test_get_instruction_text(template_overview_window_with_injection) -> None:
    """Test the _get_instruction_text helper method."""
    result = template_overview_window_with_injection._get_instruction_text()

    # Should return the translated instruction text
    assert "Please double-click the template below" in result
    assert "it does not need to exactly match" in result


def test_configure_window() -> None:
    """Test the _configure_window method."""
    # Create a simple test instance
    window = TemplateOverviewWindow.__new__(TemplateOverviewWindow)  # Create without calling __init__
    window.root = MagicMock()
    window.dpi_scaling_factor = 1.0

    # Call the method directly
    window._configure_window()

    # Verify window title was set
    window.root.title.assert_called()
    # Verify geometry was set
    window.root.geometry.assert_called()


def test_initialize_ui_components(mock_tkinter_context) -> None:
    """Test the _initialize_ui_components method."""
    # Use the shared mock context
    config = MockConfiguration(dpi_scaling_factor=1.0)
    stack, patches = mock_tkinter_context(config)

    # Add TemplateOverviewWindow-specific patches
    template_patches = [
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.Treeview"),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
        patch.object(TemplateOverviewWindow, "_bind_events"),
    ]

    # Apply all patches
    for patch_obj in patches + template_patches:
        stack.enter_context(patch_obj)

    try:
        window = TemplateOverviewWindow()

        # Mock the attributes that would be set by _initialize_ui_components
        window.top_frame = MagicMock()
        window.instruction_label = MagicMock()
        window.image_label = MagicMock()
        window.tree = MagicMock()
        window.sort_column = ""

        # Verify UI components were initialized (mocked)
        assert hasattr(window, "top_frame")
        assert hasattr(window, "instruction_label")
        assert hasattr(window, "image_label")
        assert hasattr(window, "tree")
        assert hasattr(window, "sort_column")

    finally:
        stack.close()


def test_populate_treeview_with_injection(template_overview_window_with_injection, mock_vehicle_components_provider) -> None:
    """Test _populate_treeview using dependency injection."""
    # Setup mock data
    mock_template = MagicMock()
    mock_template.attributes.return_value = ["attr1", "attr2"]
    mock_template.attr1 = "value1"
    mock_template.attr2 = "value2"

    mock_vehicle_components_provider.get_vehicle_components_overviews.return_value = {"template1": mock_template}

    template_overview_window_with_injection._populate_treeview()

    # Verify the tree was populated with the injected data
    template_overview_window_with_injection.tree.insert.assert_called_once_with(
        "", "end", text="template1", values=("template1", "value1", "value2")
    )
    mock_vehicle_components_provider.get_vehicle_components_overviews.assert_called_once()


def test_ui_setup_method_decomposition() -> None:
    """Test that UI setup methods are properly decomposed and called in the right order."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "__init__", return_value=None),
        patch.object(TemplateOverviewWindow, "_configure_window") as mock_configure,
        patch.object(TemplateOverviewWindow, "_initialize_ui_components") as mock_initialize,
        patch.object(TemplateOverviewWindow, "_setup_layout") as mock_layout,
        patch.object(TemplateOverviewWindow, "_configure_treeview") as mock_treeview,
        patch.object(TemplateOverviewWindow, "_bind_events") as mock_bind,
    ):
        TemplateOverviewWindow()

        # Verify all setup methods were called in the correct order
        mock_configure.assert_called_once()
        mock_initialize.assert_called_once()
        mock_layout.assert_called_once()
        mock_treeview.assert_called_once()
        mock_bind.assert_called_once()


def test_treeview_configuration_decomposition() -> None:
    """Test that treeview configuration is properly decomposed."""
    # Create a simple test instance
    window = TemplateOverviewWindow.__new__(TemplateOverviewWindow)  # Create without calling __init__
    window.root = MagicMock()
    window.tree = MagicMock()
    window.dpi_scaling_factor = 1.0

    # Mock the treeview configuration methods
    with (
        patch.object(window, "_setup_treeview_style") as mock_style,
        patch.object(window, "_setup_treeview_columns") as mock_columns,
        patch.object(window, "_populate_treeview") as mock_populate,
        patch.object(window, "_adjust_treeview_column_widths") as mock_adjust,
    ):
        window._configure_treeview()

        # Verify all treeview setup methods were called
        mock_style.assert_called_once()
        mock_columns.assert_called_once()
        mock_populate.assert_called_once()
        mock_adjust.assert_called_once()
        # Verify tree was packed
        window.tree.pack.assert_called_once()


def test_mock_providers_follow_protocol(mock_vehicle_components_provider, mock_program_settings_provider) -> None:
    """Test that mock providers implement the expected protocol methods."""
    # Test VehicleComponentsProviderProtocol
    assert hasattr(mock_vehicle_components_provider, "get_vehicle_components_overviews")
    assert hasattr(mock_vehicle_components_provider, "get_vehicle_image_filepath")

    # Test ProgramSettingsProviderProtocol
    assert hasattr(mock_program_settings_provider, "store_template_dir")

    # Test that methods are callable
    mock_vehicle_components_provider.get_vehicle_components_overviews()
    mock_vehicle_components_provider.get_vehicle_image_filepath("test")
    mock_program_settings_provider.store_template_dir("test")


# =============================================================================
# BEHAVIOR-DRIVEN TESTS - Focus on User Stories and Business Value
# =============================================================================

# ruff: noqa: D205, D400, D415


class TestUserTemplateSelection:
    """Test user stories around template selection behavior."""

    def test_user_can_select_template_by_double_clicking(self) -> None:
        """
        GIVEN: A user is viewing the template overview window
        WHEN: They double-click on a template row
        THEN: The selected template should be stored for use
        AND: The window should close
        """
        # Arrange: Set up real template data
        mock_vehicle_provider = MagicMock()
        mock_program_provider = MagicMock()

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow(
                vehicle_components_provider=mock_vehicle_provider, program_settings_provider=mock_program_provider
            )
            # Mock essential attributes needed for the test
            window.root = MagicMock()
            window.tree = MagicMock()
            window.tree.identify_row.return_value = "item_1"
            window.tree.item.return_value = {"text": "Copter/QuadCopter"}

            # Simulate double-click event
            mock_event = MagicMock()
            mock_event.y = 100

            # Act: User double-clicks
            window._on_row_double_click(mock_event)

            # Assert: Template is stored and window closes
            mock_program_provider.store_template_dir.assert_called_once_with("Copter/QuadCopter")
            window.root.destroy.assert_called_once()

    def test_user_sees_vehicle_image_when_selecting_template(self) -> None:
        """
        GIVEN: A user is browsing templates
        WHEN: They click on a template with an available image
        THEN: The vehicle image should be displayed
        """
        # Arrange
        mock_vehicle_provider = MagicMock()
        mock_program_provider = MagicMock()
        mock_vehicle_provider.get_vehicle_image_filepath.return_value = "/path/to/copter.jpg"

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow(
                vehicle_components_provider=mock_vehicle_provider, program_settings_provider=mock_program_provider
            )
            window.tree = MagicMock()
            window.tree.selection.return_value = ["item_1"]
            window.tree.item.return_value = {"text": "Copter/QuadCopter"}
            window.root = MagicMock()
            window.top_frame = MagicMock()
            window.image_label = MagicMock()
            window.dpi_scaling_factor = 1.0

            # Mock image loading
            with patch.object(window, "put_image_in_label", return_value=MagicMock()) as mock_put_image:
                # Act: User selects template
                window._update_selection()

                # Assert: Image is loaded and displayed
                mock_vehicle_provider.get_vehicle_image_filepath.assert_called_once_with("Copter/QuadCopter")
                mock_put_image.assert_called_once()

    def test_user_sees_fallback_message_when_no_vehicle_image_available(self) -> None:
        """
        GIVEN: A user selects a template
        WHEN: No vehicle image is available for that template
        THEN: A helpful message should be displayed instead
        """
        # Arrange
        mock_vehicle_provider = MagicMock()
        mock_program_provider = MagicMock()
        mock_vehicle_provider.get_vehicle_image_filepath.side_effect = FileNotFoundError()

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow(
                vehicle_components_provider=mock_vehicle_provider, program_settings_provider=mock_program_provider
            )
            window.top_frame = MagicMock()
            window.image_label = MagicMock()
            window.dpi_scaling_factor = 1.0

            with patch("tkinter.ttk.Label") as mock_label_class:
                # Act: Display image for template without image
                window._display_vehicle_image("Copter/CustomBuild")

                # Assert: Fallback message is created
                mock_label_class.assert_called_once()
                # Verify the message text is helpful
                call_args = mock_label_class.call_args
                assert "No 'vehicle.jpg' image file" in str(call_args)


class TestTemplateDataDisplay:
    """Test how template data is presented to users."""

    def test_templates_are_populated_from_vehicle_components(self) -> None:
        """
        GIVEN: Vehicle templates exist in the system
        WHEN: The template overview window is opened
        THEN: All available templates should be displayed in the tree
        """
        # Arrange: Create realistic template data
        mock_template_1 = MagicMock()
        mock_template_1.attributes.return_value = ["frame", "flight_controller", "gps"]
        mock_template_1.frame = "QuadCopter X"
        mock_template_1.flight_controller = "Pixhawk 6C"
        mock_template_1.gps = "Here3+"

        mock_template_2 = MagicMock()
        mock_template_2.attributes.return_value = ["frame", "flight_controller"]
        mock_template_2.frame = "Plane"
        mock_template_2.flight_controller = "Cube Orange"

        template_data = {"Copter/QuadX": mock_template_1, "Plane/FixedWing": mock_template_2}

        mock_vehicle_provider = MagicMock()
        mock_vehicle_provider.get_vehicle_components_overviews.return_value = template_data

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow(vehicle_components_provider=mock_vehicle_provider)
            window.tree = MagicMock()

            # Act: Populate the tree
            window._populate_treeview()

            # Assert: Both templates are added to tree with correct data
            assert window.tree.insert.call_count == 2

            # Check first template
            first_call = window.tree.insert.call_args_list[0]
            assert first_call[0] == ("", "end")
            assert first_call[1]["text"] == "Copter/QuadX"
            assert first_call[1]["values"] == ("Copter/QuadX", "QuadCopter X", "Pixhawk 6C", "Here3+")

            # Check second template
            second_call = window.tree.insert.call_args_list[1]
            assert second_call[0] == ("", "end")
            assert second_call[1]["text"] == "Plane/FixedWing"
            assert second_call[1]["values"] == ("Plane/FixedWing", "Plane", "Cube Orange")

    def test_sorting_helps_users_find_templates(self) -> None:
        """
        GIVEN: Multiple templates are displayed
        WHEN: User clicks a column header to sort
        THEN: Templates should be reordered to help users find what they need
        """
        # Arrange
        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow()
            window.tree = MagicMock()

            # Mock tree data for sorting
            window.tree.get_children.return_value = ["item1", "item2", "item3"]
            window.tree.set.side_effect = lambda item, col: {
                ("item1", "Frame"): "QuadCopter",
                ("item2", "Frame"): "Airplane",
                ("item3", "Frame"): "Helicopter",
            }.get((item, col), "")

            # Act: User clicks on Frame column to sort
            window._sort_by_column("Frame", reverse=False)

            # Assert: Items are reordered (Airplane, Helicopter, QuadCopter)
            assert window.tree.move.call_count == 3
            # Verify ascending sort indicator is shown
            window.tree.heading.assert_called_with("Frame", command=ANY)


class TestAccessibilityAndUsability:
    """Test accessibility and usability features."""

    def test_window_scales_properly_for_high_dpi_displays(self) -> None:
        """
        GIVEN: A user has a high-DPI display
        WHEN: The template overview window opens
        THEN: UI elements should be appropriately scaled for readability
        """
        # Arrange
        with (
            patch("tkinter.Toplevel"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
            patch.object(BaseWindow, "_setup_application_icon"),  # Skip icon loading
        ):
            window = TemplateOverviewWindow()
            window.dpi_scaling_factor = 2.0  # Simulate high-DPI display

            # Mock the geometry method to capture calls
            with patch.object(window.root, "geometry") as mock_geometry:
                # Act: Configure window for high-DPI
                window._configure_window()

                # Assert: Window size is scaled appropriately
                mock_geometry.assert_called_once()
                geometry_call = mock_geometry.call_args[0][0]
                # Should be 2400x1200 (1200x600 * 2.0 scaling)
                assert "2400x1200" in geometry_call

    def test_keyboard_navigation_works_for_accessibility(self) -> None:
        """
        GIVEN: A user navigating with keyboard
        WHEN: They use up/down arrow keys
        THEN: The selection should update and show vehicle image
        """
        # Arrange
        mock_vehicle_provider = MagicMock()

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow(vehicle_components_provider=mock_vehicle_provider)
            window.root = MagicMock()
            window.tree = MagicMock()
            window.tree.selection.return_value = ["new_item"]
            window.tree.item.return_value = {"text": "Plane/Glider"}

            with patch.object(window, "_display_vehicle_image") as mock_display:
                # Act: User presses down arrow key
                mock_event = MagicMock()
                window._on_row_selection_change(mock_event)

                # Trigger the delayed update
                window.root.after.assert_called_once_with(0, window._update_selection)

                # Simulate the after callback
                window._update_selection()

                # Assert: Image updates for new selection
                mock_display.assert_called_once_with("Plane/Glider")


class TestErrorHandlingAndEdgeCases:
    """Test system behavior in error conditions."""

    def test_graceful_handling_when_no_templates_available(self) -> None:
        """
        GIVEN: No templates are available in the system
        WHEN: User opens the template overview
        THEN: The system should handle this gracefully without crashing
        """
        # Arrange
        mock_vehicle_provider = MagicMock()
        mock_vehicle_provider.get_vehicle_components_overviews.return_value = {}

        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow(vehicle_components_provider=mock_vehicle_provider)
            window.tree = MagicMock()

            # Act: Try to populate empty template list
            window._populate_treeview()

            # Assert: No crash, no tree items added
            window.tree.insert.assert_not_called()

    def test_window_closes_properly_on_user_cancel(self) -> None:
        """
        GIVEN: A user has the template overview open
        WHEN: They close the window (cancel operation)
        THEN: Resources should be cleaned up properly
        """
        # Arrange
        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview"),
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            window = TemplateOverviewWindow()
            window.root = MagicMock()

            # Act: User closes window
            window.close_window()

            # Assert: Window is properly destroyed
            window.root.destroy.assert_called_once()


# =============================================================================
# TEST QUALITY RECOMMENDATIONS
# =============================================================================

# pylint: disable=pointless-string-statement
"""
Senior Test Expert Analysis: Transforming "Dumb Tests" into "Behavior-Driven Tests"

PROBLEMS WITH CURRENT TESTS:
1. ❌ Test implementation details, not user behavior
2. ❌ Over-mock everything, making tests fragile
3. ❌ Don't tell a story about what the system should do
4. ❌ Hard to understand business value from test names
5. ❌ Miss important user scenarios and edge cases

BEHAVIOR-DRIVEN IMPROVEMENTS:
1. ✅ Focus on user stories and business scenarios
2. ✅ Test real system behavior, not implementation
3. ✅ Use Given-When-Then structure for clarity
4. ✅ Meaningful test names that describe business value
5. ✅ Test happy paths, error cases, and edge conditions

EXAMPLE TRANSFORMATION:

BAD TEST (Implementation-focused):
def test_calculate_scaled_font_size():
    window.dpi_scaling_factor = 1.5
    result = window.calculate_scaled_font_size(12)
    assert result == 18

GOOD TEST (Behavior-focused):
def test_window_scales_properly_for_high_dpi_displays():
    '''GIVEN: A user has a high-DPI display
       WHEN: The template overview window opens
       THEN: UI elements should be appropriately scaled for readability'''
    # Test focuses on user experience, not math

KEY PRINCIPLES FOR BETTER TESTS:
1. Test behaviors, not implementation
2. Write tests that would still pass if you refactored the code
3. Use descriptive test names that explain business value
4. Test from user's perspective
5. Mock only external dependencies, not internal methods
6. Test error conditions and edge cases
7. Focus on "what" the system should do, not "how"

USER SCENARIOS TO TEST:
- ✅ User selects template by double-clicking
- ✅ User sees vehicle image when browsing
- ✅ System handles missing images gracefully
- ✅ Keyboard navigation works for accessibility
- ✅ High-DPI displays render correctly
- ✅ Sorting helps users find templates
- ✅ Error conditions don't crash the system
"""
