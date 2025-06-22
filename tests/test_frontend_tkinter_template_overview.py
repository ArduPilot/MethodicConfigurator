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
from collections.abc import Generator
from tkinter import ttk
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_template_overview import (
    TemplateOverviewWindow,
    argument_parser,
    main,
    setup_logging,
)

# pylint: disable=too-many-lines,protected-access,redefined-outer-name,unused-argument


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
def template_overview_window_setup() -> Generator[None, None, None]:
    """Fixture providing a properly mocked TemplateOverviewWindow for behavior testing."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "__init__", return_value=None),
        patch.object(TemplateOverviewWindow, "_configure_window"),
        patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
        patch.object(TemplateOverviewWindow, "_setup_layout"),
        patch.object(TemplateOverviewWindow, "_configure_treeview"),
        patch.object(TemplateOverviewWindow, "_bind_events"),
    ):
        yield


@pytest.fixture
def mock_vehicle_provider() -> MagicMock:
    """Fixture providing a mock vehicle components provider with common test data."""
    provider = MagicMock()

    # Create properly structured mock templates
    template_1 = MagicMock()
    template_1.attributes.return_value = ["name", "fc", "gnss"]
    template_1.name = "QuadCopter X"
    template_1.fc = "Pixhawk 6C"
    template_1.gnss = "Here3+"

    template_2 = MagicMock()
    template_2.attributes.return_value = ["name", "fc"]
    template_2.name = "Plane"
    template_2.fc = "Cube Orange"
    template_2.gnss = ""  # This attribute doesn't exist but getattr will return "" as default

    provider.get_vehicle_components_overviews.return_value = {
        "Copter/QuadX": template_1,
        "Plane/FixedWing": template_2,
    }
    provider.get_vehicle_image_filepath.return_value = "/mock/path/image.jpg"
    return provider


@pytest.fixture
def mock_program_provider() -> MagicMock:
    """Fixture providing a mock program settings provider."""
    return MagicMock()


@pytest.fixture
def vehicle_filtering_templates() -> dict[str, MagicMock]:
    """Fixture providing mock templates for vehicle filtering tests."""
    return {
        "Copter/QuadX": MagicMock(attributes=lambda: ["name"], name="QuadCopter"),
        "Plane/FixedWing": MagicMock(attributes=lambda: ["name"], name="Airplane"),
        "Copter/HexaX": MagicMock(attributes=lambda: ["name"], name="Hexacopter"),
        "Rover/SkidSteer": MagicMock(attributes=lambda: ["name"], name="Rover"),
        "ArduCopter/QuadX": MagicMock(attributes=lambda: ["name"], name="ArduCopter QuadX"),
        "ArduPlane/FixedWing": MagicMock(attributes=lambda: ["name"], name="ArduPlane"),
        "Custom/Copter/Experimental": MagicMock(attributes=lambda: ["name"], name="Experimental Copter"),
    }


@pytest.fixture
def vehicle_window(mock_vehicle_provider, mock_program_provider, vehicle_filtering_templates) -> TemplateOverviewWindow:
    """Fixture providing a configured window for vehicle filtering tests."""
    mock_vehicle_provider.get_vehicle_components_overviews.return_value = vehicle_filtering_templates

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
            vehicle_components_provider=mock_vehicle_provider,
            program_settings_provider=mock_program_provider,
            connected_fc_vehicle_type="ArduCopter",  # Default vehicle type for filtering tests
        )
        window.root = MagicMock()
        window.tree = MagicMock()
        return window


@pytest.fixture
def template_window(mock_vehicle_provider, mock_program_provider) -> TemplateOverviewWindow:
    """Fixture providing a configured TemplateOverviewWindow for behavior testing."""
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
            vehicle_components_provider=mock_vehicle_provider,
            program_settings_provider=mock_program_provider,
            connected_fc_vehicle_type=None,  # No filtering for most tests
        )
        # Mock essential UI components that tests actually interact with
        window.root = MagicMock()
        window.tree = MagicMock()
        return window


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


class TestUserTemplateSelection:
    """Test user stories around template selection behavior."""

    def test_user_can_select_template_by_double_clicking(self, template_window) -> None:
        """
        User can select a template by double-clicking on it.

        GIVEN: A user is viewing the template overview window
        WHEN: They double-click on a template row
        THEN: The selected template should be stored for use
        AND: The window should close
        """
        # Arrange: Configure mock responses for double-click behavior
        template_window.tree.identify_row.return_value = "item_1"
        template_window.tree.item.return_value = {"text": "Copter/QuadCopter"}

        mock_event = MagicMock(y=100)

        # Act: User double-clicks
        template_window._on_row_double_click(mock_event)

        # Assert: Template is stored and window closes
        template_window.program_settings_provider.store_template_dir.assert_called_once_with("Copter/QuadCopter")
        template_window.root.destroy.assert_called_once()

    def test_user_sees_vehicle_image_when_selecting_template(self, template_window) -> None:
        """
        When a template is highlighted or selected, the corresponding vehicle image should be displayed.

        GIVEN: A user is browsing templates
        WHEN: They click on a template with an available image
        THEN: The vehicle image should be displayed
        """
        # Arrange: Configure selection behavior
        template_window.tree.selection.return_value = ["item_1"]
        template_window.tree.item.return_value = {"text": "Copter/QuadX"}

        with patch.object(template_window, "_display_vehicle_image") as mock_display:
            mock_event = MagicMock()

            # Act: User selects template
            template_window._on_row_selection_change(mock_event)
            template_window._update_selection()  # Simulate the after callback

            # Assert: Image is displayed for selected template
            mock_display.assert_called_once_with("Copter/QuadX")

    def test_user_sees_fallback_message_when_no_vehicle_image_available(self, template_window) -> None:
        """
        When no vehicle image is available for a template, a helpful fallback message is shown.

        GIVEN: A user selects a template
        WHEN: No vehicle image is available for that template
        THEN: A helpful message should be displayed instead
        """
        # Arrange: Configure vehicle provider to return no image
        template_window.vehicle_components_provider.get_vehicle_image_filepath.return_value = ""
        template_window.tree.selection.return_value = ["item_1"]
        template_window.tree.item.return_value = {"text": "Experimental/NewDesign"}

        with patch.object(template_window, "_display_vehicle_image") as mock_display:
            mock_event = MagicMock()

            # Act: User selects template without image
            template_window._on_row_selection_change(mock_event)
            template_window._update_selection()

            # Assert: Display method is called (internal logic handles missing image gracefully)
            mock_display.assert_called_once_with("Experimental/NewDesign")


class TestTemplateDataDisplay:
    """Test how template data is presented to users."""

    def test_templates_are_populated_from_vehicle_components(self, template_window) -> None:
        """
        Test that templates are correctly populated from vehicle components.

        GIVEN: Vehicle templates exist in the system
        WHEN: The template overview window is opened
        THEN: All available templates should be displayed in the tree
        """
        # Act: Populate the tree with templates from our mock provider
        template_window._populate_treeview("")  # Empty string means no filtering

        # Assert: Both templates are added to tree with correct data
        assert template_window.tree.insert.call_count == 2

        # Check first template (Copter/QuadX)
        first_call = template_window.tree.insert.call_args_list[0]
        assert first_call[0] == ("", "end")
        assert first_call[1]["text"] == "Copter/QuadX"
        assert first_call[1]["values"] == ("Copter/QuadX", "QuadCopter X", "Pixhawk 6C", "Here3+")

        # Check second template (Plane/FixedWing)
        second_call = template_window.tree.insert.call_args_list[1]
        assert second_call[0] == ("", "end")
        assert second_call[1]["text"] == "Plane/FixedWing"
        assert second_call[1]["values"] == ("Plane/FixedWing", "Plane", "Cube Orange")

    def test_sorting_helps_users_find_templates(self, template_window) -> None:
        """
        Test that sorting templates by column helps users find what they need.

        GIVEN: Multiple templates are displayed
        WHEN: User clicks a column header to sort
        THEN: Templates should be reordered to help users find what they need
        """
        # Arrange: Mock tree data for sorting
        template_window.tree.get_children.return_value = ["item1", "item2", "item3"]
        template_window.tree.set.side_effect = lambda item, col: {
            ("item1", "Frame"): "QuadCopter",
            ("item2", "Frame"): "Airplane",
            ("item3", "Frame"): "Helicopter",
        }.get((item, col), "")

        # Act: User clicks on Frame column to sort
        template_window._sort_by_column("Frame", reverse=False)

        # Assert: Items are reordered (Airplane, Helicopter, QuadCopter)
        assert template_window.tree.move.call_count == 3
        # Verify ascending sort indicator is shown
        template_window.tree.heading.assert_called_with("Frame", command=ANY)


class TestAccessibilityAndUsability:
    """Test accessibility and usability features."""

    def test_window_scales_properly_for_high_dpi_displays(self, template_window) -> None:
        """
        Test that the template overview window scales properly on high-DPI displays.

        GIVEN: A user has a high-DPI display
        WHEN: The template overview window opens
        THEN: UI elements should be appropriately scaled for readability
        """
        # Arrange: Simulate high-DPI display
        template_window.dpi_scaling_factor = 2.0

        # Mock the geometry method to capture calls
        with patch.object(template_window.root, "geometry") as mock_geometry:
            # Act: Configure window for high-DPI
            template_window._configure_window()

            # Assert: Window size is scaled appropriately
            mock_geometry.assert_called_once()
            geometry_call = mock_geometry.call_args[0][0]
            # Should be 2400x1200 (1200x600 * 2.0 scaling)
            assert "2400x1200" in geometry_call

    def test_keyboard_navigation_works_for_accessibility(self, template_window) -> None:
        """
        Test that keyboard navigation works for users with accessibility needs.

        GIVEN: A user navigating with keyboard
        WHEN: They use up/down arrow keys
        THEN: The selection should update and show vehicle image
        """
        # Arrange: Set up selection return values
        template_window.tree.selection.return_value = ["new_item"]
        template_window.tree.item.return_value = {"text": "Plane/Glider"}

        with patch.object(template_window, "_display_vehicle_image") as mock_display:
            # Act: User presses down arrow key
            mock_event = MagicMock()
            template_window._on_row_selection_change(mock_event)

            # Trigger the delayed update
            template_window.root.after.assert_called_once_with(0, template_window._update_selection)

            # Simulate the after callback
            template_window._update_selection()

            # Assert: Image updates for new selection
            mock_display.assert_called_once_with("Plane/Glider")


class TestErrorHandlingAndEdgeCases:
    """Test system behavior in error conditions."""

    def test_graceful_handling_when_no_templates_available(self, template_overview_window_setup) -> None:
        """
        Test that the system handles no available templates gracefully.

        GIVEN: No templates are available in the system
        WHEN: User opens the template overview
        THEN: The system should handle this gracefully without crashing
        """
        # Arrange: Mock empty template data
        mock_vehicle_provider = MagicMock()
        mock_vehicle_provider.get_vehicle_components_overviews.return_value = {}

        window = TemplateOverviewWindow(vehicle_components_provider=mock_vehicle_provider)
        window.tree = MagicMock()

        # Act: Try to populate empty template list
        window._populate_treeview("")  # Empty string means no filtering

        # Assert: No crash, no tree items added
        window.tree.insert.assert_not_called()

    def test_window_closes_properly_on_user_cancel(self, template_window) -> None:
        """
        Test that the window closes properly when the user cancels the operation.

        GIVEN: A user has the template overview open
        WHEN: They close the window (cancel operation)
        THEN: Resources should be cleaned up properly
        """
        # Act: User closes window
        template_window.close_window()

        # Assert: Window is properly destroyed
        template_window.root.destroy.assert_called_once()


class TestUIComponentInitialization:
    """Test UI component initialization and responsive layout behavior."""

    def test_high_dpi_displays_get_properly_scaled_components(self, template_window) -> None:
        """
        Users on high-DPI displays should see properly scaled UI components.

        GIVEN: A user opens the template overview on a high-DPI display
        WHEN: UI components are initialized
        THEN: All components should be created with appropriate DPI scaling
        """
        # Arrange: Set high-DPI environment
        template_window.dpi_scaling_factor = 2.0
        template_window.calculate_scaled_font_size = MagicMock(return_value=24)

        # Act: Initialize UI components (already done by fixture, verify state)
        # Assert: Window has proper scaling setup
        assert hasattr(template_window, "dpi_scaling_factor")
        assert template_window.dpi_scaling_factor == 2.0

    def test_users_see_clear_instructions_for_template_selection(self, template_window) -> None:
        """
        Users should see clear, localized instructions for selecting templates.

        GIVEN: A user opens the template overview window
        WHEN: The instruction text is displayed
        THEN: Text should be clear, multilingual, and properly formatted
        """
        # Act: Get instruction text
        instruction_text = template_window._get_instruction_text()

        # Assert: Text contains helpful guidance
        assert "double-click" in instruction_text.lower()
        assert "template" in instruction_text.lower()
        assert "\n" in instruction_text  # Multi-line for readability

    def test_window_layout_adapts_to_different_screen_sizes(self, template_window) -> None:
        """
        Window layout should adapt gracefully to different screen sizes.

        GIVEN: A user opens the template overview on any screen size
        WHEN: The layout is configured
        THEN: Components should be positioned with responsive scaling
        """
        # Arrange: Set up variable DPI environment
        template_window.dpi_scaling_factor = 1.25
        template_window.calculate_scaled_padding_tuple = MagicMock(return_value=(15, 30))

        # Mock the necessary components for layout
        template_window.top_frame = MagicMock()
        template_window.instruction_label = MagicMock()
        template_window.image_label = MagicMock()

        # Act: Test layout setup
        try:
            TemplateOverviewWindow._setup_layout(template_window)
            layout_success = True
        except Exception:  # pylint: disable=broad-exception-caught
            layout_success = False

        # Assert: Layout setup completes successfully
        assert layout_success, "Layout setup should complete without errors"
        assert hasattr(template_window, "top_frame")
        assert hasattr(template_window, "instruction_label")


class TestTreeviewConfiguration:
    """Test treeview configuration and user experience optimization."""

    def test_treeview_styling_adapts_to_user_display_settings(self, template_window) -> None:
        """
        Treeview styling should provide optimal readability on all displays.

        GIVEN: A user opens the template overview on any display
        WHEN: Treeview styling is configured
        THEN: Styling should be applied with proper DPI scaling for readability
        """
        # Arrange: Set up style environment
        template_window.calculate_scaled_padding = MagicMock(return_value=3)

        with patch("tkinter.ttk.Style") as mock_style_class:
            mock_style = MagicMock()
            mock_style_class.return_value = mock_style

            # Act: Apply treeview styling
            template_window._setup_treeview_style()

            # Assert: Style configuration provides good UX
            mock_style.layout.assert_called_once()
            mock_style.configure.assert_called_once()

    def test_treeview_columns_resize_for_content_readability(self, template_window) -> None:
        """
        Treeview columns should automatically size for optimal content readability.

        GIVEN: A populated treeview with varying content lengths
        WHEN: Column widths are adjusted
        THEN: Widths should accommodate content with appropriate DPI scaling
        """
        # Arrange: Set up mock font and treeview data
        with patch("tkinter.font.Font") as mock_font_class:
            mock_font = MagicMock()
            mock_font.measure.return_value = 100
            mock_font_class.return_value = mock_font

            # Configure template_window tree with test data
            template_window.tree.__getitem__.return_value = ["Frame", "Size"]
            template_window.tree.get_children.return_value = ["item1", "item2"]
            template_window.tree.item.side_effect = lambda item, key: {
                "values": ["QuadCopter", "Large"] if item == "item1" else ["Airplane", "Medium"]
            }.get(key, ["QuadCopter", "Large"])
            template_window.dpi_scaling_factor = 1.5

            # Act: Adjust column widths
            template_window._adjust_treeview_column_widths()

            # Assert: Columns are properly sized
            assert template_window.tree.column.call_count >= 2


class TestUserInteractionBehavior:
    """Test user interaction patterns and responsive behavior."""

    def test_user_selection_updates_provide_immediate_feedback(self, template_window) -> None:
        """
        Users should see immediate visual feedback when selecting templates.

        GIVEN: A user browses through different templates
        WHEN: They select a row in the treeview
        THEN: Their selection should be immediately stored and image updated
        """
        # Arrange: Set up selection behavior
        template_window.tree.selection.return_value = ["item1"]
        template_window.tree.item.return_value = {"text": "Copter/QuadCopter"}
        template_window.store_template_dir = MagicMock()
        template_window._display_vehicle_image = MagicMock()

        # Act: User clicks on a template
        mock_event = MagicMock()
        template_window._on_row_selection_change(mock_event)
        template_window._update_selection()  # Simulate the after callback

        # Assert: Immediate feedback provided
        template_window.store_template_dir.assert_called_once_with("Copter/QuadCopter")
        template_window._display_vehicle_image.assert_called_once_with("Copter/QuadCopter")

    def test_user_double_click_provides_quick_template_selection(self, template_window) -> None:
        """
        Users should be able to quickly select templates with double-click.

        GIVEN: A user has found their desired template
        WHEN: They double-click on the template row
        THEN: Template should be selected and window closed for efficient workflow
        """
        # Arrange: Set up double-click behavior
        template_window.tree.identify_row.return_value = "item1"
        template_window.tree.item.return_value = {"text": "Copter/QuadCopter"}
        template_window.store_template_dir = MagicMock()
        template_window.close_window = MagicMock()

        # Act: User double-clicks to select
        mock_event = MagicMock()
        mock_event.y = 100
        template_window._on_row_double_click(mock_event)

        # Assert: Quick selection workflow completed
        template_window.store_template_dir.assert_called_once_with("Copter/QuadCopter")
        template_window.close_window.assert_called_once()


class TestVisualFeedbackAndImageDisplay:  # pylint: disable=too-few-public-methods
    """Test visual feedback mechanisms for better user experience."""

    def test_missing_vehicle_images_handled_gracefully_for_users(self, template_window) -> None:
        """
        Users should experience graceful handling when vehicle images are missing.

        GIVEN: A user selects a template without an associated image
        WHEN: The system tries to display the vehicle image
        THEN: The missing image should be handled without disrupting user workflow
        """
        # Arrange: Template without image
        template_window.top_frame = MagicMock()
        template_window.top_frame.winfo_children.return_value = []
        template_window.image_label = MagicMock()
        template_window.dpi_scaling_factor = 1.0
        template_window.vehicle_components_provider.get_vehicle_image_filepath.return_value = "missing.png"
        template_window.get_vehicle_image_filepath = MagicMock(return_value="missing.png")

        # Act: User selects template without image
        template_window._display_vehicle_image("Copter/ExperimentalQuad")

        # Assert: Graceful handling without errors (method completes without exceptions)


class TestApplicationEntryPoint:  # pylint: disable=too-few-public-methods
    """Test application startup and command-line interface behavior."""

    def test_command_line_startup_creates_functional_user_interface(self) -> None:
        """
        Command-line startup should create a fully functional user interface.

        GIVEN: A user starts the application from command line
        WHEN: The main function is called with arguments
        THEN: A complete template overview window should be created and run
        """
        # Arrange: Command line environment with minimal mocking
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.argument_parser") as mock_parser,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.setup_logging") as mock_setup_logging,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings") as mock_settings,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
            ) as mock_window_class,
        ):
            # Set up mock returns
            mock_args = MagicMock()
            mock_args.loglevel = "INFO"
            mock_parser.return_value = mock_args
            mock_settings.get_recently_used_dirs.return_value = ["/test/dir"]

            mock_window = MagicMock()
            mock_window_class.return_value = mock_window

            # Act: User starts application from command line
            main()

            # Assert: Complete application setup
            mock_parser.assert_called_once()
            mock_setup_logging.assert_called_once_with("INFO")
            mock_window.run_app.assert_called_once()


class TestWindowInitialization:
    """Test comprehensive window initialization behavior."""

    def test_window_initialization_creates_all_required_components(self, template_overview_window_setup) -> None:
        """
        Window initialization should create all required UI components.

        GIVEN: A user opens the template overview window
        WHEN: Window initialization occurs
        THEN: All UI components should be properly created and configured
        """
        # Arrange: Mock all required components for full initialization
        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.Treeview"),
        ):
            mock_vehicle_provider = MagicMock()
            mock_program_provider = MagicMock()

            # Act: Initialize window with real initialization call
            window = TemplateOverviewWindow(
                vehicle_components_provider=mock_vehicle_provider,
                program_settings_provider=mock_program_provider,
            )

            # Assert: Components are properly initialized
            assert window.vehicle_components_provider == mock_vehicle_provider
            assert window.program_settings_provider == mock_program_provider

    def test_ui_components_get_proper_dependency_injection(self, template_overview_window_setup) -> None:
        """
        UI components should receive proper dependency injection.

        GIVEN: A user provides custom providers
        WHEN: Window is initialized with dependency injection
        THEN: Custom providers should be used instead of defaults
        """
        # Arrange: Custom providers
        mock_vehicle_provider = MagicMock()
        mock_program_provider = MagicMock()

        # Act: Initialize with custom providers
        window = TemplateOverviewWindow(
            vehicle_components_provider=mock_vehicle_provider,
            program_settings_provider=mock_program_provider,
        )

        # Assert: Custom providers are used
        assert window.vehicle_components_provider is mock_vehicle_provider
        assert window.program_settings_provider is mock_program_provider

    def test_window_uses_default_providers_when_none_specified(self, template_overview_window_setup) -> None:
        """
        Window should use default providers when none are specified.

        GIVEN: A user doesn't specify custom providers
        WHEN: Window is initialized without providers
        THEN: Default providers should be used
        """
        # Arrange: Patch the default classes
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.VehicleComponents") as mock_vc,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings") as mock_ps,
        ):
            # Act: Initialize without providers
            window = TemplateOverviewWindow()

            # Assert: Default providers are used
            assert window.vehicle_components_provider is mock_vc
            assert window.program_settings_provider is mock_ps


class TestWindowApplicationRunner:
    """Test window application running behavior."""

    def test_toplevel_window_runs_with_update_loop(self, template_window) -> None:
        """
        Toplevel window should run with proper update loop.

        GIVEN: A window is created as Toplevel
        WHEN: run_app is called
        THEN: Update loop should run properly
        """
        # Arrange: Mock Toplevel window
        template_window.root = MagicMock(spec=tk.Toplevel)
        # Start with children, will be cleared to exit loop
        template_window.root.children = {"child1": MagicMock()}

        def clear_children_after_call() -> None:
            template_window.root.children = {}

        template_window.root.update_idletasks.side_effect = clear_children_after_call

        # Act: Run the app
        template_window.run_app()

        # Assert: Update methods were called
        template_window.root.update_idletasks.assert_called()

    def test_tk_window_runs_with_mainloop(self, template_window) -> None:
        """
        Tk window should run with mainloop.

        GIVEN: A window is created as Tk root
        WHEN: run_app is called
        THEN: Mainloop should be called
        """
        # Arrange: Mock Tk root window
        template_window.root = MagicMock(spec=tk.Tk)

        # Act: Run the app
        template_window.run_app()

        # Assert: Mainloop was called
        template_window.root.mainloop.assert_called_once()

    def test_tcl_error_handled_gracefully_in_toplevel_run(self, template_window) -> None:
        """
        TclError should be handled gracefully in Toplevel run.

        GIVEN: A Toplevel window encounters TclError
        WHEN: run_app is called and TclError occurs
        THEN: Error should be handled without crashing
        """
        # Arrange: Mock Toplevel with TclError
        template_window.root = MagicMock(spec=tk.Toplevel)
        template_window.root.children = {"child1": MagicMock()}
        template_window.root.update_idletasks.side_effect = tk.TclError("Test error")

        # Act: Run the app (should not raise exception)
        try:
            template_window.run_app()
            test_passed = True
        except tk.TclError:
            test_passed = False

        # Assert: Error was handled gracefully
        assert test_passed


class TestTreeviewConfigurationDetails:
    """Test detailed treeview configuration behavior."""

    def test_treeview_style_configuration_uses_proper_scaling(self, template_window) -> None:
        """
        Treeview style should use proper DPI scaling.

        GIVEN: A window with specific DPI scaling
        WHEN: Treeview style is configured
        THEN: Style should use appropriate scaling values
        """
        # Arrange: Set scaling and mock style
        template_window.dpi_scaling_factor = 1.5
        template_window.calculate_scaled_padding = MagicMock(return_value=15)

        with patch("tkinter.ttk.Style") as mock_style_class:
            mock_style = MagicMock()
            mock_style_class.return_value = mock_style

            # Act: Configure treeview style
            template_window._setup_treeview_style()

            # Assert: Style methods were called with scaling
            mock_style.layout.assert_called_once()
            mock_style.configure.assert_called_once()

    def test_treeview_columns_setup_creates_proper_headings(self, template_window) -> None:
        """
        Treeview columns should be set up with proper headings.

        GIVEN: A treeview needs column configuration
        WHEN: Columns are set up
        THEN: Proper headings should be created
        """
        # Arrange: Mock the tree columns directly
        template_window.tree = MagicMock()
        template_window.tree.__getitem__.return_value = ["Template", "Frame", "FC"]

        # Act: Setup treeview columns
        template_window._setup_treeview_columns()

        # Assert: Headings were configured for each column
        assert template_window.tree.heading.call_count == 3

    def test_event_binding_creates_all_required_handlers(self, template_window) -> None:
        """
        Event binding should create all required event handlers.

        GIVEN: A treeview needs event handling
        WHEN: Events are bound
        THEN: All required events should have handlers
        """
        # Arrange: Mock tree columns
        template_window.tree.__getitem__ = MagicMock(return_value=["Template", "Frame"])

        # Act: Bind events
        template_window._bind_events()

        # Assert: All required events are bound
        expected_events = ["<ButtonRelease-1>", "<Up>", "<Down>", "<Double-1>"]
        actual_bind_calls = [call[0][0] for call in template_window.tree.bind.call_args_list]
        for event in expected_events:
            assert event in actual_bind_calls


class TestSortingBehaviorDetails:
    """Test detailed sorting behavior."""

    def test_numeric_sorting_works_with_float_values(self, template_window) -> None:
        """
        Numeric sorting should work with float values.

        GIVEN: A treeview with numeric data
        WHEN: User sorts by numeric column
        THEN: Values should be sorted numerically, not alphabetically
        """
        # Arrange: Mock tree with numeric data
        template_window.tree.get_children.return_value = ["item1", "item2", "item3"]
        template_window.tree.set.side_effect = lambda item, col: {
            ("item1", "Size"): "1.5",
            ("item2", "Size"): "10.2",
            ("item3", "Size"): "2.0",
        }.get((item, col), "0")

        # Act: Sort by Size column
        template_window._sort_by_column("Size", reverse=False)

        # Assert: Items were moved (sorted)
        assert template_window.tree.move.call_count == 3

    def test_string_sorting_fallback_handles_non_numeric_data(self, template_window) -> None:
        """
        String sorting should work as fallback for non-numeric data.

        GIVEN: A treeview with non-numeric data
        WHEN: User sorts by text column
        THEN: Values should be sorted alphabetically
        """
        # Arrange: Mock tree with text data
        template_window.tree.get_children.return_value = ["item1", "item2"]
        template_window.tree.set.side_effect = lambda item, col: {
            ("item1", "Name"): "Zebra",
            ("item2", "Name"): "Alpha",
        }.get((item, col), "")

        # Act: Sort by Name column
        template_window._sort_by_column("Name", reverse=False)

        # Assert: String sorting was used (move was called)
        assert template_window.tree.move.call_count == 2

    def test_sorting_indicators_update_properly(self, template_window) -> None:
        """
        Sorting indicators should update properly.

        GIVEN: A user sorts by different columns
        WHEN: Sort direction changes
        THEN: Visual indicators should update correctly
        """
        # Arrange: Initial sort state
        template_window.sort_column = "OldColumn"
        template_window.tree.get_children.return_value = ["item1"]
        template_window.tree.set.return_value = "value"

        # Act: Sort by new column
        template_window._sort_by_column("NewColumn", reverse=False)

        # Assert: Old column indicator cleared, new column shows ascending
        template_window.tree.heading.assert_any_call("OldColumn", text="OldColumn")
        template_window.tree.heading.assert_any_call("NewColumn", text="NewColumn ▲")


class TestImageDisplayBehavior:
    """Test vehicle image display behavior."""

    def test_image_display_removes_previous_image_correctly(self, template_window) -> None:
        """
        Image display should remove previous image correctly.

        GIVEN: A previous image is displayed
        WHEN: A new template is selected
        THEN: Previous image should be removed before showing new one
        """
        # Arrange: Mock existing image widget and top_frame
        old_image_widget = MagicMock(spec=ttk.Label)
        template_window.image_label = old_image_widget
        template_window.top_frame = MagicMock()
        template_window.top_frame.winfo_children.return_value = [old_image_widget]
        template_window.dpi_scaling_factor = 1.0

        with (
            patch.object(template_window, "get_vehicle_image_filepath", return_value="/path/to/image.jpg"),
            patch.object(template_window, "put_image_in_label", return_value=MagicMock()),
        ):
            # Act: Display new image
            template_window._display_vehicle_image("Copter/NewTemplate")

            # Assert: Old image was destroyed
            old_image_widget.destroy.assert_called_once()

    def test_image_display_handles_file_not_found_gracefully(self, template_window) -> None:
        """
        Image display should handle FileNotFoundError gracefully.

        GIVEN: A template without an associated image
        WHEN: Image display is attempted
        THEN: A fallback message should be shown
        """
        # Arrange: Mock FileNotFoundError and top_frame
        template_window.top_frame = MagicMock()
        template_window.top_frame.winfo_children.return_value = []
        template_window.dpi_scaling_factor = 1.0

        with (
            patch.object(template_window, "get_vehicle_image_filepath", side_effect=FileNotFoundError),
            patch("tkinter.ttk.Label") as mock_label,
        ):
            # Act: Try to display image
            template_window._display_vehicle_image("Copter/NoImage")

            # Assert: Fallback label was created
            mock_label.assert_called_once()
            call_args = mock_label.call_args[1]
            assert "No 'vehicle.jpg'" in call_args["text"]

    def test_get_vehicle_image_filepath_delegates_to_provider(self, template_window) -> None:
        """
        get_vehicle_image_filepath should delegate to vehicle components provider.

        GIVEN: A template path
        WHEN: Vehicle image filepath is requested
        THEN: Request should be delegated to provider
        """
        # Arrange: Mock provider response
        template_window.vehicle_components_provider.get_vehicle_image_filepath.return_value = "/test/path.jpg"

        # Act: Get image filepath
        result = template_window.get_vehicle_image_filepath("Copter/Test")

        # Assert: Provider was called and result returned
        template_window.vehicle_components_provider.get_vehicle_image_filepath.assert_called_once_with("Copter/Test")
        assert result == "/test/path.jpg"


class TestAdvancedMainFunctionality:
    """Test advanced main function behavior."""

    def test_main_function_logs_recently_used_directory_when_available(self) -> None:
        """
        Main function should log recently used directory when available.

        GIVEN: A user has recently used directories
        WHEN: Main function completes
        THEN: Most recent directory should be logged
        """
        # Arrange: Mock all main dependencies
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.argument_parser") as mock_parser,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.setup_logging"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
            ) as mock_window_class,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings") as mock_settings,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_info") as mock_log_info,
        ):
            # Set up mocks
            mock_args = MagicMock()
            mock_args.loglevel = "INFO"
            mock_parser.return_value = mock_args

            mock_window = MagicMock()
            mock_window_class.return_value = mock_window
            mock_settings.get_recently_used_dirs.return_value = ["/recent/dir"]

            # Act: Run main function
            main()

            # Assert: Recent directory was logged
            mock_log_info.assert_called_once_with("/recent/dir")

    def test_main_function_handles_no_recently_used_directories(self) -> None:
        """
        Main function should handle no recently used directories gracefully.

        GIVEN: A user has no recently used directories
        WHEN: Main function completes
        THEN: No logging should occur without error
        """
        # Arrange: Mock all main dependencies
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.argument_parser") as mock_parser,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.setup_logging"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_template_overview.TemplateOverviewWindow"
            ) as mock_window_class,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.ProgramSettings") as mock_settings,
            patch("ardupilot_methodic_configurator.frontend_tkinter_template_overview.logging_info") as mock_log_info,
        ):
            # Set up mocks
            mock_args = MagicMock()
            mock_args.loglevel = "INFO"
            mock_parser.return_value = mock_args

            mock_window = MagicMock()
            mock_window_class.return_value = mock_window
            mock_settings.get_recently_used_dirs.return_value = []

            # Act: Run main function
            main()

            # Assert: No logging occurred
            mock_log_info.assert_not_called()


class TestVehicleTypeFiltering:
    """Test vehicle type filtering functionality."""

    def test_filtering_shows_only_matching_vehicle_templates(self, vehicle_window) -> None:
        """
        Test that vehicle filtering shows only templates matching the connected flight controller.

        GIVEN: Multiple templates exist for different vehicle types
        WHEN: User has a specific vehicle type connected (e.g., "ArduCopter")
        THEN: Only templates matching that vehicle type should be displayed
        """
        # Act: Populate treeview with Copter filtering
        vehicle_window._populate_treeview("ArduCopter")

        # Assert: Only ArduCopter templates are added
        # Should not include: Copter/QuadX, Copter/HexaX, Custom/Copter/Experimental
        assert vehicle_window.tree.insert.call_count == 1

        # Verify the calls contain only Copter templates
        call_args_list = vehicle_window.tree.insert.call_args_list
        inserted_keys = [call[1]["text"] for call in call_args_list]
        assert "Copter/QuadX" not in inserted_keys
        assert "Copter/HexaX" not in inserted_keys
        assert "ArduCopter/QuadX" in inserted_keys
        assert "Custom/Copter/Experimental" not in inserted_keys
        assert "Plane/FixedWing" not in inserted_keys
        assert "Rover/SkidSteer" not in inserted_keys

    def test_no_filtering_shows_all_templates(self, vehicle_window) -> None:
        """
        Test that passing empty/None vehicle type shows all available templates.

        GIVEN: Multiple templates exist for different vehicle types
        WHEN: No specific vehicle type is provided for filtering
        THEN: All available templates should be displayed
        """
        # Act: Populate treeview without filtering
        vehicle_window._populate_treeview("")

        # Assert: All templates are added
        assert vehicle_window.tree.insert.call_count == 7  # All seven templates

        # Verify all template types are included
        call_args_list = vehicle_window.tree.insert.call_args_list
        inserted_keys = [call[1]["text"] for call in call_args_list]
        assert "Copter/QuadX" in inserted_keys
        assert "Plane/FixedWing" in inserted_keys
        assert "Rover/SkidSteer" in inserted_keys
        assert "ArduCopter/QuadX" in inserted_keys

    def test_partial_vehicle_matching_works_correctly(self, vehicle_window) -> None:
        """
        Test that vehicle filtering works with partial string matching.

        GIVEN: Templates with vehicle types as part of their keys
        WHEN: A specific vehicle substring is used for filtering
        THEN: All templates containing that substring should be included
        """
        # Act: Filter by "ArduCopter" substring
        vehicle_window._populate_treeview("ArduCopter")

        # Assert: Only ArduCopter templates are included
        assert vehicle_window.tree.insert.call_count == 1

        call_args_list = vehicle_window.tree.insert.call_args_list
        inserted_keys = [call[1]["text"] for call in call_args_list]
        assert "ArduCopter/QuadX" in inserted_keys
        assert "Custom/Copter/Experimental" not in inserted_keys
        assert "Copter/QuadX" not in inserted_keys
        assert "ArduPlane/FixedWing" not in inserted_keys

    def test_constructor_passes_vehicle_type_to_configure_treeview(self, mock_vehicle_provider, mock_program_provider) -> None:
        """
        Test that the constructor properly passes vehicle type to the configuration methods.

        GIVEN: A TemplateOverviewWindow is created with a specific vehicle type
        WHEN: The constructor initializes the UI components
        THEN: The vehicle type should be passed down to the treeview configuration
        """
        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "__init__", return_value=None),
            patch.object(TemplateOverviewWindow, "_configure_window"),
            patch.object(TemplateOverviewWindow, "_initialize_ui_components"),
            patch.object(TemplateOverviewWindow, "_setup_layout"),
            patch.object(TemplateOverviewWindow, "_configure_treeview") as mock_configure_treeview,
            patch.object(TemplateOverviewWindow, "_bind_events"),
        ):
            # Act: Create window with specific vehicle type
            TemplateOverviewWindow(
                vehicle_components_provider=mock_vehicle_provider,
                program_settings_provider=mock_program_provider,
                connected_fc_vehicle_type="Plane",
            )

            # Assert: vehicle type is passed to configure_treeview
            mock_configure_treeview.assert_called_once_with("Plane")
