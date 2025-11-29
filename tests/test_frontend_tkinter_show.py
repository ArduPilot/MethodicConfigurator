#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_show.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_show import (
    Tooltip,
    calculate_tooltip_position,
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
    def test_user_receives_clear_error_messages_when_application_encounters_problems(self, mock_tk, title, message) -> None:
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
    def test_user_sees_helpful_warnings_for_non_critical_issues(self, mock_tk, title, message) -> None:
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
            parent_x=0,
            parent_y=0,
            parent_width=1920,
            parent_height=1080,
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
            parent_x=0,
            parent_y=0,
            parent_width=1920,
            parent_height=1080,
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
            parent_x=0,
            parent_y=0,
            parent_width=1920,
            parent_height=1080,
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
            parent_x=0,
            parent_y=0,
            parent_width=1920,
            parent_height=1080,
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
            parent_x=0,
            parent_y=0,
            parent_width=1920,
            parent_height=1080,
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
            parent_x=0,
            parent_y=0,
            parent_width=1920,
            parent_height=1080,
            position_below=True,
        )
        assert x == 0  # clamped to parent_x
        assert y == 0  # clamped to parent_y

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
            parent_x=50,
            parent_y=50,
            parent_width=800,
            parent_height=600,
            position_below=True,
        )
        # x = 100 + 25 = 125, 125 + 150 = 275 < 50 + 800 = 850, so x=125
        # But then x = max(125, 50) = 125
        # If 125 + 150 > 850? 275 < 850, no adjustment
        assert x == 125
        assert y == 120  # 100 + 20 = 120, 120 + 50 = 170 < 50 + 600 = 650, y=120


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
        widget.winfo_toplevel.return_value = MagicMock()
        widget.winfo_toplevel.return_value.winfo_rootx.return_value = 0
        widget.winfo_toplevel.return_value.winfo_rooty.return_value = 0
        widget.winfo_toplevel.return_value.winfo_width.return_value = 1920
        widget.winfo_toplevel.return_value.winfo_height.return_value = 1080
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

    @patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system")
    def test_tooltip_initialization_non_macos(self, mock_platform, mock_widget, mock_toplevel) -> None:
        """
        Test Tooltip initialization on non-macOS platforms.

        GIVEN: Non-macOS platform
        WHEN: Tooltip is created
        THEN: Tooltip is created immediately and bindings are set
        """
        mock_platform.return_value = "Linux"

        with patch("tkinter.Toplevel", return_value=mock_toplevel), patch("tkinter.ttk.Label") as mock_label:
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

    @patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system")
    def test_tooltip_initialization_macos(self, mock_platform, mock_widget) -> None:
        """
        Test Tooltip initialization on macOS.

        GIVEN: macOS platform
        WHEN: Tooltip is created
        THEN: Tooltip is not created immediately, only bindings are set
        """
        mock_platform.return_value = "Darwin"

        tooltip = Tooltip(mock_widget, "Test text")

        # Check that tooltip is None initially
        assert tooltip.tooltip is None
        # Check bindings
        mock_widget.bind.assert_any_call("<Enter>", tooltip.create_show, "+")
        mock_widget.bind.assert_any_call("<Leave>", tooltip.destroy_hide, "+")

    @patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system")
    def test_tooltip_create_show_on_macos(self, mock_platform, mock_widget, mock_toplevel) -> None:
        """
        Test tooltip creation and show on macOS.

        GIVEN: macOS platform
        WHEN: Mouse enters widget
        THEN: Tooltip is created and shown
        """
        mock_platform.return_value = "Darwin"

        with patch("tkinter.Toplevel", return_value=mock_toplevel), patch("tkinter.ttk.Label") as mock_label:
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

    @patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system")
    def test_tooltip_destroy_hide_on_macos(self, mock_platform, mock_widget, mock_toplevel) -> None:
        """
        Test tooltip destroy hide on macOS.

        GIVEN: macOS platform
        WHEN: Mouse leaves widget
        THEN: Tooltip is destroyed
        """
        mock_platform.return_value = "Darwin"

        tooltip = Tooltip(mock_widget, "Test text")
        tooltip.tooltip = mock_toplevel

        tooltip.destroy_hide()

        mock_toplevel.destroy.assert_called_once()
        assert tooltip.tooltip is None
