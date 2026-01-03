#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_show.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from tkinter import TclError
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_show import (
    MonitorBounds,
    Tooltip,
    calculate_tooltip_position,
    get_monitor_bounds,
    show_error_message,
    show_no_connection_error,
    show_no_param_files_error,
    show_tooltip,
    show_tooltip_on_richtext_tag,
    show_warning_message,
)

# pylint: disable=redefined-outer-name, unused-argument, protected-access


# Fixtures
@pytest.fixture
def mock_tk() -> Generator[MagicMock, None, None]:
    with patch("tkinter.Tk") as mock:
        mock.return_value.withdraw.return_value = None
        mock.return_value.destroy.return_value = None
        yield mock


@pytest.fixture
def mock_widget() -> MagicMock:
    """Create a mock widget for testing."""
    return MagicMock()


@pytest.fixture
def mock_showerror() -> Generator[MagicMock, None, None]:
    with patch("tkinter.messagebox.showerror") as mock:
        yield mock


@pytest.fixture
def mock_showwarning() -> Generator[MagicMock, None, None]:
    with patch("tkinter.messagebox.showwarning") as mock:
        yield mock


@pytest.fixture
def mock_ttk_style() -> Generator[MagicMock, None, None]:
    with patch("tkinter.ttk.Style") as mock:
        yield mock


class TestUserErrorCommunication:
    """Test that users receive clear, helpful error messages when things go wrong."""

    @pytest.mark.parametrize(
        ("title", "message"),
        [
            ("Configuration Error", "The selected parameter file is corrupted."),
            ("Network Error", "Unable to connect to the flight controller."),
            ("Validation Error", "The entered value is outside the allowed range."),
        ],
    )
    def test_user_receives_clear_error_messages_when_application_encounters_problems(
        self, mock_tk: MagicMock, title: str, message: str
    ) -> None:
        """
        User receives clear error messages when application encounters problems.

        GIVEN: The application encounters various error conditions
        WHEN: An error occurs that requires user attention
        THEN: A clear, descriptive error message is displayed
        AND: The user understands what went wrong and what they might do about it
        """
        with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
            # When: Error occurs
            show_error_message(title, message)

            # Then: User sees clear error message
            mock_showerror.assert_called_once_with(title, message)

    def test_user_gets_specific_guidance_when_no_parameter_files_found(self, mock_tk) -> None:
        """
        User gets specific guidance when no parameter files are found.

        GIVEN: User attempts to load parameter files
        WHEN: No valid parameter files exist in the selected directory
        THEN: User receives specific instructions on how to resolve the issue
        AND: The guidance helps them understand what they need to do next
        """
        with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
            # When: User tries to load parameters from empty directory
            show_no_param_files_error("empty_directory")

            # Then: User gets helpful, specific guidance
            expected_message = (
                "No intermediate parameter files found in the selected 'empty_directory' vehicle directory.\n"
                "Please select and step inside a vehicle directory containing valid ArduPilot intermediate parameter files."
                "\n\nMake sure to step inside the directory (double-click) and not just select it."
            )
            mock_showerror.assert_called_once_with("No Parameter Files Found", expected_message)

    def test_user_receives_connection_troubleshooting_help_when_flight_controller_unreachable(self, mock_tk) -> None:
        """
        User receives connection troubleshooting help when flight controller unreachable.

        GIVEN: User attempts to connect to a flight controller
        WHEN: Connection fails due to timeout or other issues
        THEN: User gets specific troubleshooting steps to resolve connection problems
        AND: The guidance includes timing and hardware checks
        """
        with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
            # When: Connection attempt fails
            show_no_connection_error("Connection timed out after 10 seconds")

            # Then: User gets actionable troubleshooting guidance
            expected_message = (
                "Connection timed out after 10 seconds\n\n"
                "Please connect a flight controller to the PC,\n"
                "wait at least 7 seconds and retry."
            )
            mock_showerror.assert_called_once_with("No Connection to the Flight Controller", expected_message)

    @pytest.mark.parametrize(
        ("title", "message"),
        [
            ("Configuration Warning", "Some parameters may need adjustment."),
            ("Compatibility Warning", "This firmware version has known issues."),
        ],
    )
    def test_user_sees_helpful_warnings_for_non_critical_issues(self, mock_tk: MagicMock, title: str, message: str) -> None:
        """
        User sees helpful warnings for non-critical issues.

        GIVEN: Application encounters situations that need user awareness but aren't blocking
        WHEN: A warning condition occurs
        THEN: User receives informative warning messages
        AND: Warnings are clearly distinguished from errors
        """
        with patch("tkinter.messagebox.showwarning") as mock_showwarning, patch("tkinter.ttk.Style"):
            # When: Warning condition occurs
            show_warning_message(title, message)

            # Then: User sees appropriate warning
            mock_showwarning.assert_called_once_with(title, message)

    def test_user_can_provide_custom_root_for_error_messages(self, mock_tk) -> None:
        """
        Test that users can provide a custom root for error messages.

        GIVEN: Application needs to show error messages
        WHEN: A custom root is provided
        THEN: No new root is created or destroyed
        AND: Message is shown on the provided root
        """
        mock_root = MagicMock()
        with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
            # When: Error occurs with custom root
            show_error_message("Custom Error", "Custom message", root=mock_root)

            # Then: No Tk creation or destruction, message shown
            mock_showerror.assert_called_once_with("Custom Error", "Custom message")
            # Tk should not be called since root is provided
            mock_tk.assert_not_called()

    def test_user_can_provide_custom_root_for_warning_messages(self, mock_tk) -> None:
        """
        Test that users can provide a custom root for warning messages.

        GIVEN: Application needs to show warning messages
        WHEN: A custom root is provided
        THEN: No new root is created or destroyed
        AND: Message is shown on the provided root
        """
        mock_root = MagicMock()
        with patch("tkinter.messagebox.showwarning") as mock_showwarning, patch("tkinter.ttk.Style"):
            # When: Warning occurs with custom root
            show_warning_message("Custom Warning", "Custom message", root=mock_root)

            # Then: No Tk creation or destruction, message shown
            mock_showwarning.assert_called_once_with("Custom Warning", "Custom message")

    def test_user_experiences_reliable_error_reporting_across_different_scenarios(self, mock_tk) -> None:
        """
        User experiences reliable error reporting across different scenarios.

        GIVEN: Application can encounter various error conditions
        WHEN: Different types of errors occur
        THEN: Error reporting is consistent and reliable
        AND: Users can depend on getting helpful information regardless of error type
        """
        with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
            # When: Multiple error scenarios occur
            show_error_message("Error 1", "First problem")
            show_no_param_files_error("test_dir")
            show_no_connection_error("timeout")

            # Then: All error reporting works reliably
            assert mock_showerror.call_count == 3


class TestTooltipPositionCalculation:
    """Test the pure function for calculating tooltip positions."""

    def test_calculate_tooltip_position_normal_case(self) -> None:
        """
        Test tooltip position calculation in normal case.

        GIVEN: Widget and tooltip dimensions
        WHEN: Calculating position below widget
        THEN: Position is calculated correctly
        """
        x, y = calculate_tooltip_position(
            widget_x=100,
            widget_y=100,
            widget_width=50,
            widget_height=20,
            tooltip_width=150,
            tooltip_height=50,
            area_left=0,
            area_top=0,
            area_width=1920,
            area_height=1080,
            position_below=True,
        )
        assert x == 125  # 100 + min(50//2, 100) = 100 + 25
        assert y == 120  # 100 + 20

    def test_calculate_tooltip_position_above(self) -> None:
        """
        Test tooltip position calculation above widget.

        GIVEN: Position above requested
        WHEN: Calculating position
        THEN: Y is adjusted above
        """
        x, y = calculate_tooltip_position(
            widget_x=100,
            widget_y=100,
            widget_width=50,
            widget_height=20,
            tooltip_width=150,
            tooltip_height=50,
            area_left=0,
            area_top=0,
            area_width=1920,
            area_height=1080,
            position_below=False,
        )
        assert x == 125
        assert y == 90  # 100 - 10

    def test_calculate_tooltip_position_adjusts_for_window_edge(self) -> None:
        """
        Test tooltip position adjustment when near window edge.

        GIVEN: Tooltip would go beyond parent window
        WHEN: Calculating position
        THEN: Position is adjusted to fit inside
        """
        x, y = calculate_tooltip_position(
            widget_x=1800,
            widget_y=100,
            widget_width=100,
            widget_height=30,
            tooltip_width=200,
            tooltip_height=50,
            area_left=0,
            area_top=0,
            area_width=1920,
            area_height=1080,
            position_below=True,
        )
        assert x == 1720  # 1920 - 200
        assert y == 130

    def test_calculate_tooltip_position_at_left_edge(self) -> None:
        """
        Test tooltip position when widget is at left edge.

        GIVEN: Widget at left edge
        WHEN: Calculating position
        THEN: X is adjusted to not go negative
        """
        x, y = calculate_tooltip_position(
            widget_x=10,
            widget_y=100,
            widget_width=50,
            widget_height=20,
            tooltip_width=150,
            tooltip_height=50,
            area_left=0,
            area_top=0,
            area_width=1920,
            area_height=1080,
            position_below=True,
        )
        assert x == 35  # 10 + min(50//2, 100) = 10 + 25 = 35
        assert y == 120

    def test_calculate_tooltip_position_at_top_edge_above(self) -> None:
        """
        Test tooltip position when widget is at top edge and positioning above.

        GIVEN: Widget at top edge, position above
        WHEN: Calculating position
        THEN: Y is adjusted to not go negative
        """
        x, y = calculate_tooltip_position(
            widget_x=100,
            widget_y=10,
            widget_width=50,
            widget_height=20,
            tooltip_width=150,
            tooltip_height=50,
            area_left=0,
            area_top=0,
            area_width=1920,
            area_height=1080,
            position_below=False,
        )
        assert x == 125
        assert y == 0  # max(10 - 10, 0) = 0

    def test_calculate_tooltip_position_tooltip_larger_than_screen(self) -> None:
        """
        Test tooltip position when tooltip is larger than screen.

        GIVEN: Tooltip dimensions exceed screen
        WHEN: Calculating position
        THEN: Position is clamped to screen bounds
        """
        x, y = calculate_tooltip_position(
            widget_x=100,
            widget_y=100,
            widget_width=50,
            widget_height=20,
            tooltip_width=2000,
            tooltip_height=1200,
            area_left=0,
            area_top=0,
            area_width=1920,
            area_height=1080,
            position_below=True,
        )
        assert x == 0  # clamped to the left edge
        assert y == 0  # clamped to the top edge

    def test_calculate_tooltip_position_with_parent_offset(self) -> None:
        """
        Test tooltip position with parent window offset.

        GIVEN: Parent window not at (0,0)
        WHEN: Calculating position
        THEN: Position accounts for parent offset
        """
        x, y = calculate_tooltip_position(
            widget_x=100,
            widget_y=100,
            widget_width=50,
            widget_height=20,
            tooltip_width=150,
            tooltip_height=50,
            area_left=50,
            area_top=50,
            area_width=800,
            area_height=600,
            position_below=True,
        )
        # x = 100 + 25 = 125, 125 + 150 = 275 < 50 + 800 = 850, so x=125
        # But then x = max(125, 50) = 125
        # If 125 + 150 > 850? 275 < 850, no adjustment
        assert x == 125
        assert y == 120  # 100 + 20 = 120, 120 + 50 = 170 < 50 + 600 = 650, y=120


class TestMonitorBoundsDetection:
    """Test system behavior for detecting monitor boundaries across different platforms."""

    @pytest.fixture
    def mock_widget(self) -> MagicMock:
        """Provide a mock widget for testing monitor bounds detection."""
        return MagicMock()

    @pytest.mark.parametrize(
        ("platform", "platform_api_returns", "fallback_returns", "expected_bounds"),
        [
            # Windows with working native API
            ("Windows", MonitorBounds(10, 20, 1010, 620), MonitorBounds(0, 0, 800, 600), MonitorBounds(10, 20, 1010, 620)),
            # Windows with failed native API falls back to Tk
            ("Windows", None, MonitorBounds(0, 0, 800, 600), MonitorBounds(0, 0, 800, 600)),
            # macOS with working native API
            ("Darwin", MonitorBounds(-100, 0, 1180, 900), MonitorBounds(0, 0, 1920, 1080), MonitorBounds(-100, 0, 1180, 900)),
            # macOS with failed native API falls back to Tk
            ("Darwin", None, MonitorBounds(0, 0, 1920, 1080), MonitorBounds(0, 0, 1920, 1080)),
            # Linux always uses Tk fallback
            ("Linux", None, MonitorBounds(0, 0, 1920, 1080), MonitorBounds(0, 0, 1920, 1080)),
        ],
    )
    def test_system_returns_correct_monitor_bounds_for_platform(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_widget: MagicMock,
        platform: str,
        platform_api_returns: Optional[MonitorBounds],
        fallback_returns: MonitorBounds,
        expected_bounds: MonitorBounds,
    ) -> None:
        """
        System returns accurate monitor bounds appropriate for the platform.

        GIVEN: A widget on a specific operating system platform
        WHEN: The system queries for monitor bounds
        THEN: Platform-native APIs are preferred, with graceful fallback to Tk
        """
        # Arrange: Configure platform and API responses
        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show.platform_system",
                return_value=platform,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_windows",
                return_value=platform_api_returns if platform == "Windows" else None,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_macos",
                return_value=platform_api_returns if platform == "Darwin" else None,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_tk",
                return_value=fallback_returns,
            ),
        ):
            # Act: Query monitor bounds
            result = get_monitor_bounds(mock_widget)

        # Assert: System returns correct bounds for platform
        assert result == expected_bounds

    def test_system_caches_monitor_bounds_for_same_toplevel(self, mock_widget: MagicMock) -> None:
        """
        System caches monitor bounds to avoid repeated platform API calls.

        GIVEN: A widget whose monitor bounds were previously queried
        WHEN: The same widget's monitor bounds are queried again
        THEN: The cached value is returned without calling platform APIs
        """
        # Arrange: Configure mock widget with consistent toplevel
        toplevel = MagicMock()
        toplevel.winfo_rootx.return_value = 100
        toplevel.winfo_rooty.return_value = 50
        mock_widget.winfo_toplevel.return_value = toplevel
        expected_bounds = MonitorBounds(0, 0, 1920, 1080)

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_tk",
                return_value=expected_bounds,
            ) as mock_tk,
        ):
            # Act: Query bounds twice
            result1 = get_monitor_bounds(mock_widget)
            result2 = get_monitor_bounds(mock_widget)

        # Assert: Same bounds returned both times, but API called only once
        assert result1 == expected_bounds
        assert result2 == expected_bounds
        mock_tk.assert_called_once()

    def test_system_invalidates_cache_when_widget_moves_to_different_monitor(self, mock_widget: MagicMock) -> None:
        """
        System invalidates cache when widget moves outside cached monitor bounds.

        GIVEN: A cached monitor bounds for a widget
        WHEN: The widget moves to a position outside the cached bounds
        THEN: The cache is invalidated and bounds are re-queried
        """
        # Arrange: Widget starts on primary monitor, then moves to secondary
        toplevel = MagicMock()
        mock_widget.winfo_toplevel.return_value = toplevel
        primary_bounds = MonitorBounds(0, 0, 1920, 1080)
        secondary_bounds = MonitorBounds(1920, 0, 3840, 1080)

        # First call: widget at (100, 50) within primary monitor
        toplevel.winfo_rootx.return_value = 100
        toplevel.winfo_rooty.return_value = 50

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_tk",
                side_effect=[primary_bounds, secondary_bounds],
            ) as mock_tk,
        ):
            result1 = get_monitor_bounds(mock_widget)

            # Act: Widget moves to (2000, 50) outside primary monitor
            toplevel.winfo_rootx.return_value = 2000
            toplevel.winfo_rooty.return_value = 50
            result2 = get_monitor_bounds(mock_widget)

        # Assert: Cache invalidated, new bounds returned
        assert result1 == primary_bounds
        assert result2 == secondary_bounds
        assert mock_tk.call_count == 2

    def test_system_invalidates_cache_when_widget_moves_vertically_to_different_monitor(self, mock_widget: MagicMock) -> None:
        """
        System invalidates cache when widget moves vertically outside cached monitor bounds.

        GIVEN: A cached monitor bounds for a widget
        WHEN: The widget moves vertically to a position outside the cached bounds (e.g., stacked monitors)
        THEN: The cache is invalidated and bounds are re-queried
        """
        # Arrange: Widget starts on top monitor, then moves to bottom monitor
        toplevel = MagicMock()
        mock_widget.winfo_toplevel.return_value = toplevel
        top_monitor_bounds = MonitorBounds(0, 0, 1920, 1080)
        bottom_monitor_bounds = MonitorBounds(0, 1080, 1920, 2160)

        # First call: widget at (100, 50) within top monitor
        toplevel.winfo_rootx.return_value = 100
        toplevel.winfo_rooty.return_value = 50

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_tk",
                side_effect=[top_monitor_bounds, bottom_monitor_bounds],
            ) as mock_tk,
        ):
            result1 = get_monitor_bounds(mock_widget)

            # Act: Widget moves to (100, 1500) outside top monitor (Y changed)
            toplevel.winfo_rootx.return_value = 100
            toplevel.winfo_rooty.return_value = 1500
            result2 = get_monitor_bounds(mock_widget)

        # Assert: Cache invalidated due to Y-axis movement, new bounds returned
        assert result1 == top_monitor_bounds
        assert result2 == bottom_monitor_bounds
        assert mock_tk.call_count == 2

    def test_system_handles_widget_destruction_gracefully(self, mock_widget: MagicMock) -> None:
        """
        System handles widget destruction without crashing.

        GIVEN: A widget that gets destroyed during bounds query
        WHEN: Monitor bounds are queried
        THEN: The system falls back gracefully and returns valid bounds
        """
        # Arrange: Widget raises TclError (destroyed)
        mock_widget.winfo_toplevel.side_effect = TclError("invalid command name")
        fallback_bounds = MonitorBounds(0, 0, 1920, 1080)

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_tk",
                return_value=fallback_bounds,
            ),
        ):
            # Act: Query bounds for destroyed widget
            result = get_monitor_bounds(mock_widget)

        # Assert: Fallback bounds returned without crash
        assert result == fallback_bounds

    @pytest.mark.parametrize(
        ("invalid_bounds", "description"),
        [
            (MonitorBounds(0, 0, 50, 50), "too small (50x50)"),
            (MonitorBounds(0, 0, 0, 0), "zero dimensions"),
            (MonitorBounds(0, 0, -100, -100), "negative dimensions"),
            (MonitorBounds(0, 0, 70000, 70000), "too large (70000x70000)"),
        ],
    )
    def test_system_rejects_invalid_monitor_bounds(
        self, mock_widget: MagicMock, invalid_bounds: MonitorBounds, description: str
    ) -> None:
        """
        System validates and rejects invalid monitor bounds.

        GIVEN: Platform API returns invalid monitor bounds
        WHEN: Monitor bounds are queried
        THEN: Invalid bounds are rejected and fallback is used
        """
        # Arrange: Platform API returns invalid bounds
        valid_fallback = MonitorBounds(0, 0, 1920, 1080)

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_windows",
                return_value=invalid_bounds,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_tk",
                return_value=valid_fallback,
            ) as mock_fallback,
        ):
            # Act: Query bounds
            result = get_monitor_bounds(mock_widget)

        # Assert: Invalid bounds rejected, fallback used
        assert result == valid_fallback, f"Failed for {description}"
        mock_fallback.assert_called_once()

    def test_system_accepts_large_multi_monitor_setups(self, mock_widget: MagicMock) -> None:
        """
        System accepts valid large multi-monitor configurations.

        GIVEN: A multi-monitor setup with very wide virtual desktop
        WHEN: Monitor bounds are queried
        THEN: Large but valid bounds are accepted
        """
        # Arrange: Triple 4K monitor setup (11520x2160)
        large_bounds = MonitorBounds(0, 0, 11520, 2160)

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show._monitor_bounds_windows",
                return_value=large_bounds,
            ),
        ):
            # Act: Query bounds
            result = get_monitor_bounds(mock_widget)

        # Assert: Large bounds accepted
        assert result == large_bounds


class TestTooltipFunctionality:
    """Test the Tooltip class and related functions."""

    @pytest.fixture
    def mock_widget(self) -> MagicMock:
        """Create a mock widget for testing."""
        widget = MagicMock()
        widget.winfo_rootx.return_value = 100
        widget.winfo_rooty.return_value = 100
        widget.winfo_width.return_value = 50
        widget.winfo_height.return_value = 20
        parent = MagicMock()
        parent.winfo_rootx.return_value = 0
        parent.winfo_rooty.return_value = 0
        parent.winfo_width.return_value = 1920
        parent.winfo_height.return_value = 1080
        parent.winfo_vrootx.return_value = 0
        parent.winfo_vrooty.return_value = 0
        parent.winfo_vrootwidth.return_value = 1920
        parent.winfo_vrootheight.return_value = 1080
        parent.winfo_toplevel.return_value = parent
        widget.winfo_toplevel.return_value = parent
        widget.after_cancel.return_value = None
        widget.after.return_value = "timer_id"
        return widget

    @pytest.fixture
    def mock_toplevel(self) -> MagicMock:
        """Create a mock Toplevel for testing."""
        toplevel = MagicMock()
        toplevel.winfo_reqwidth.return_value = 150
        toplevel.winfo_reqheight.return_value = 50
        toplevel.geometry.return_value = None
        toplevel.update_idletasks.return_value = None
        toplevel.deiconify.return_value = None
        toplevel.withdraw.return_value = None
        toplevel.destroy.return_value = None
        toplevel.bind.return_value = None
        return toplevel

    def test_show_tooltip_creates_tooltip_instance(self, mock_widget) -> None:
        """
        Test that show_tooltip creates a Tooltip instance.

        GIVEN: A widget
        WHEN: show_tooltip is called
        THEN: A Tooltip instance is returned
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
            mock_tooltip_instance = MagicMock()
            mock_tooltip_class.return_value = mock_tooltip_instance

            result = show_tooltip(mock_widget, "Test tooltip")

            mock_tooltip_class.assert_called_once_with(mock_widget, "Test tooltip", position_below=True, tag_name="")
            assert result == mock_tooltip_instance

    def test_show_tooltip_on_richtext_tag_creates_tooltip_instance(self, mock_widget) -> None:
        """
        Test that show_tooltip_on_richtext_tag creates a Tooltip instance.

        GIVEN: A RichText widget and tag
        WHEN: show_tooltip_on_richtext_tag is called
        THEN: A Tooltip instance is returned with tag_name
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
            mock_tooltip_instance = MagicMock()
            mock_tooltip_class.return_value = mock_tooltip_instance

            result = show_tooltip_on_richtext_tag(mock_widget, "Test tooltip", "test_tag")

            mock_tooltip_class.assert_called_once_with(mock_widget, "Test tooltip", position_below=True, tag_name="test_tag")
            assert result == mock_tooltip_instance

    def test_tooltip_initialization_non_macos(self, mock_widget: MagicMock, mock_toplevel: MagicMock) -> None:
        """
        Test Tooltip initialization on non-macOS platforms.

        GIVEN: Non-macOS platform
        WHEN: Tooltip is created
        THEN: Tooltip is created immediately and bindings are set
        """
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
            patch("tkinter.Toplevel", return_value=mock_toplevel),
            patch("tkinter.ttk.Label") as mock_label,
        ):
            tooltip = Tooltip(mock_widget, "Test text")

            # Check that Toplevel was created
            assert tooltip.tooltip == mock_toplevel
            # Check bindings
            mock_widget.bind.assert_any_call("<Enter>", tooltip.show, "+")
            mock_widget.bind.assert_any_call("<Leave>", tooltip.hide, "+")
            # Check tooltip setup
            mock_toplevel.wm_overrideredirect.assert_called_with(boolean=True)
            mock_label.assert_called_once()
            mock_toplevel.withdraw.assert_called_once()

    def test_tooltip_initialization_macos(self, mock_widget: MagicMock) -> None:
        """
        Test Tooltip initialization on macOS.

        GIVEN: macOS platform
        WHEN: Tooltip is created
        THEN: Tooltip is not created immediately, only bindings are set
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"):
            tooltip = Tooltip(mock_widget, "Test text")

        # Check that tooltip is None initially
        assert tooltip.tooltip is None
        # Check bindings
        mock_widget.bind.assert_any_call("<Enter>", tooltip.create_show, "+")
        mock_widget.bind.assert_any_call("<Leave>", tooltip.destroy_hide, "+")

    def test_tooltip_create_show_on_macos(self, mock_widget: MagicMock, mock_toplevel: MagicMock) -> None:
        """
        Test tooltip creation and show on macOS.

        GIVEN: macOS platform
        WHEN: Mouse enters widget
        THEN: Tooltip is created and shown
        """
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"),
            patch("tkinter.Toplevel", return_value=mock_toplevel),
            patch("tkinter.ttk.Label") as mock_label,
        ):
            tooltip = Tooltip(mock_widget, "Test text")
            tooltip.create_show()

            assert tooltip.tooltip == mock_toplevel
            mock_label.assert_called_once()
            mock_toplevel.bind.assert_any_call("<Enter>", tooltip._cancel_hide)
            mock_toplevel.bind.assert_any_call("<Leave>", tooltip.hide)

    def test_tooltip_position_tooltip(self, mock_widget, mock_toplevel) -> None:
        """
        Test tooltip positioning.

        GIVEN: Tooltip instance
        WHEN: position_tooltip is called
        THEN: Geometry is set correctly
        """
        with (
            patch("tkinter.Toplevel", return_value=mock_toplevel),
            patch("tkinter.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_show.get_monitor_bounds",
                return_value=MonitorBounds(0, 0, 1920, 1080),
            ),
        ):
            tooltip = Tooltip(mock_widget, "Test text")

            tooltip.position_tooltip()

            # Check that geometry was set
            mock_toplevel.geometry.assert_called_once()
            # The call should be with calculated position
            call_args = mock_toplevel.geometry.call_args[0][0]
            assert call_args.startswith("+")

    def test_tooltip_show_non_macos(self, mock_widget, mock_toplevel) -> None:
        """
        Test tooltip show on non-macOS.

        GIVEN: Tooltip on non-macOS
        WHEN: show is called
        THEN: Tooltip is deiconified
        """
        with (
            patch("tkinter.Toplevel", return_value=mock_toplevel),
            patch("tkinter.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
        ):
            tooltip = Tooltip(mock_widget, "Test text")

            tooltip.show()

            mock_toplevel.deiconify.assert_called_once()

    def test_tooltip_hide(self, mock_widget, mock_toplevel) -> None:
        """
        Test tooltip hide.

        GIVEN: Tooltip instance
        WHEN: hide is called
        THEN: Timer is set to hide tooltip
        """
        with (
            patch("tkinter.Toplevel", return_value=mock_toplevel),
            patch("tkinter.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
        ):
            tooltip = Tooltip(mock_widget, "Test text")

            tooltip.hide()

            mock_widget.after.assert_called_once_with(10, tooltip._do_hide)

    def test_tooltip_cancel_hide(self, mock_widget) -> None:
        """
        Test canceling hide timer.

        GIVEN: Hide timer is set
        WHEN: _cancel_hide is called
        THEN: Timer is canceled
        """
        with (
            patch("tkinter.Toplevel"),
            patch("tkinter.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Linux"),
        ):
            tooltip = Tooltip(mock_widget, "Test text")
            tooltip.hide_timer = "timer_id"

            tooltip._cancel_hide()

            mock_widget.after_cancel.assert_called_once_with("timer_id")
            assert tooltip.hide_timer is None

    def test_tooltip_destroy_hide_on_macos(self, mock_widget: MagicMock, mock_toplevel: MagicMock) -> None:
        """
        Test tooltip destroy hide on macOS.

        GIVEN: macOS platform
        WHEN: Mouse leaves widget
        THEN: Tooltip is destroyed
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"):
            tooltip = Tooltip(mock_widget, "Test text")
        tooltip.tooltip = mock_toplevel

        tooltip.destroy_hide()

        mock_toplevel.destroy.assert_called_once()
        assert tooltip.tooltip is None
