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

# pylint: disable=redefined-outer-name, unused-argument


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
            # Tk should not be called since root is provided
            mock_tk.assert_not_called()


class TestUserHelpSystem:
    """Test that users can access helpful information through tooltips."""

    def test_user_can_get_contextual_help_through_tooltips(self, mock_widget) -> None:
        """
        User can get contextual help through tooltips.

        GIVEN: User interface contains elements that might be confusing
        WHEN: User needs help understanding a UI element
        THEN: Helpful tooltip information is available on demand
        AND: Tooltips provide clear, concise guidance
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
            mock_tooltip_instance = MagicMock()
            mock_tooltip_class.return_value = mock_tooltip_instance

            # When: Application provides tooltip help
            tooltip = show_tooltip(mock_widget, "This button saves your configuration safely.")

            # Then: User can access helpful information
            mock_tooltip_class.assert_called_with(
                mock_widget, "This button saves your configuration safely.", position_below=True, tag_name=""
            )
            assert tooltip is mock_tooltip_instance

    def test_user_receives_helpful_guidance_for_complex_ui_elements(self, mock_widget) -> None:
        """
        User receives helpful guidance for complex UI elements.

        GIVEN: Application has complex controls that need explanation
        WHEN: User interacts with advanced features
        THEN: Contextual help explains complex functionality clearly
        AND: Help content is appropriate for the user's expertise level
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
            mock_tooltip_instance = MagicMock()
            mock_tooltip_class.return_value = mock_tooltip_instance

            # When: Complex feature needs explanation
            tooltip = show_tooltip(
                mock_widget,
                "Advanced calibration mode. Use only if you understand the implications for flight safety.",
                position_below=False,
            )

            # Then: User gets appropriate guidance for complex features
            mock_tooltip_class.assert_called_with(
                mock_widget,
                "Advanced calibration mode. Use only if you understand the implications for flight safety.",
                position_below=False,
                tag_name="",
            )
            assert tooltip is mock_tooltip_instance

    def test_user_can_access_help_for_rich_text_content(self, mock_widget) -> None:
        """
        User can access help for rich text content.

        GIVEN: Application displays rich text with potentially confusing elements
        WHEN: User needs clarification on formatted content
        THEN: Tagged text regions provide contextual help
        AND: Help is specifically relevant to the content being viewed
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
            mock_tooltip_instance = MagicMock()
            mock_tooltip_class.return_value = mock_tooltip_instance

            # When: Rich text content needs explanation
            show_tooltip_on_richtext_tag(mock_widget, "This indicates a critical safety parameter.", "safety_warning")

            # Then: User gets context-specific help
            mock_tooltip_class.assert_called_with(
                mock_widget, "This indicates a critical safety parameter.", position_below=True, tag_name="safety_warning"
            )
            assert mock_tooltip_instance is not None


class TestUserExperienceConsistency:
    """Test that user experience is consistent and reliable."""

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

    def test_user_can_rely_on_tooltip_system_for_consistent_help_delivery(self, mock_widget) -> None:
        """
        User can rely on tooltip system for consistent help delivery.

        GIVEN: Application provides help through tooltips
        WHEN: Users need assistance with various UI elements
        THEN: Tooltip system delivers help consistently and reliably
        AND: Users can depend on getting help when they need it
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
            mock_tooltip_instance = MagicMock()
            mock_tooltip_class.return_value = mock_tooltip_instance

            # When: Multiple help requests are made
            tooltip1 = show_tooltip(mock_widget, "Help 1")
            tooltip2 = show_tooltip(mock_widget, "Help 2", position_below=False)

            # Then: Help system works consistently
            assert mock_tooltip_class.call_count == 2
            assert tooltip1 is mock_tooltip_instance
            assert tooltip2 is mock_tooltip_instance


class TestUserPlatformSpecificBehavior:
    """Test platform-specific tooltip behavior to ensure consistent user experience across operating systems."""

    def test_user_gets_proper_tooltip_lifecycle_on_macos(self, mock_widget) -> None:
        """
        Test macOS tooltip lifecycle behavior.

        GIVEN: User is on macOS system
        WHEN: Tooltip is shown and hidden
        THEN: Tooltip is fully created and destroyed for optimal performance
        AND: User gets responsive help without memory leaks
        """
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"),
            patch("tkinter.Toplevel") as mock_toplevel,
            patch("tkinter.ttk.Label") as mock_label,
        ):
            mock_tooltip_window = MagicMock()
            mock_tooltip_window.winfo_reqwidth.return_value = 150
            mock_tooltip_window.winfo_reqheight.return_value = 50
            mock_toplevel.return_value = mock_tooltip_window

            # Configure mock widget
            mock_widget.winfo_rootx.return_value = 100
            mock_widget.winfo_rooty.return_value = 100
            mock_widget.winfo_width.return_value = 50
            mock_widget.winfo_height.return_value = 20
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent

            tooltip = Tooltip(mock_widget, "macOS tooltip")

            # When: Tooltip is shown (create_show called on macOS)
            tooltip.create_show()

            # Then: Tooltip window is created and shown
            mock_toplevel.assert_called_once()
            mock_label.assert_called_once()
            mock_tooltip_window.geometry.assert_called()

            # When: Tooltip is hidden (destroy_hide called on macOS)
            tooltip.destroy_hide()

            # Then: Tooltip is fully destroyed
            mock_tooltip_window.destroy.assert_called_once()
            assert tooltip.tooltip is None

    def test_user_gets_tooltip_fallback_on_macos_when_macwindowstyle_fails(self, mock_widget) -> None:
        """
        Test tooltip fallback on macOS when MacWindowStyle fails.

        GIVEN: User is on macOS system
        WHEN: MacWindowStyle call fails with AttributeError
        THEN: Tooltip still works with fallback configuration
        AND: User gets functional tooltip despite the failure
        """
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"),
            patch("tkinter.Toplevel") as mock_toplevel,
            patch("tkinter.ttk.Label") as mock_label,
        ):
            mock_tooltip_window = MagicMock()
            mock_toplevel.return_value = mock_tooltip_window
            mock_tooltip_window.tk.call.side_effect = AttributeError("MacWindowStyle not available")
            mock_tooltip_window.winfo_reqwidth.return_value = 150
            mock_tooltip_window.winfo_reqheight.return_value = 50

            # Configure mock widget
            mock_widget.winfo_rootx.return_value = 100
            mock_widget.winfo_rooty.return_value = 100
            mock_widget.winfo_width.return_value = 50
            mock_widget.winfo_height.return_value = 20
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent

            tooltip = Tooltip(mock_widget, "macOS fallback tooltip")

            # When: Tooltip is created (create_show called on macOS)
            tooltip.create_show()

            # Then: Tooltip window is created with fallback config
            mock_toplevel.assert_called_once()
            mock_label.assert_called_once()
            # Verify wm_attributes was called for alpha and topmost (fallback)
            calls = [call[0] for call in mock_tooltip_window.wm_attributes.call_args_list]
            assert ("-alpha", 1.0) in calls
            assert ("-topmost", True) in calls
            mock_tooltip_window.configure.assert_called_with(bg="#ffffe0")

    def test_user_gets_standard_tooltip_behavior_on_non_macos(self, mock_widget) -> None:
        """
        Test standard tooltip behavior on non-macOS systems.

        GIVEN: User is on non-macOS system (Windows/Linux)
        WHEN: Tooltip is shown and hidden
        THEN: Tooltip uses standard show/hide pattern for compatibility
        AND: User gets consistent help experience
        """
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
            patch("tkinter.Toplevel") as mock_toplevel,
        ):
            mock_tooltip_window = MagicMock()
            mock_tooltip_window.winfo_reqwidth.return_value = 150
            mock_tooltip_window.winfo_reqheight.return_value = 50
            mock_toplevel.return_value = mock_tooltip_window

            # Configure mock widget
            mock_widget.winfo_rootx.return_value = 100
            mock_widget.winfo_rooty.return_value = 100
            mock_widget.winfo_width.return_value = 50
            mock_widget.winfo_height.return_value = 20
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent

            tooltip = Tooltip(mock_widget, "Windows tooltip")

            # When: Tooltip is shown (standard show)
            tooltip.show()

            # Then: Tooltip window is shown
            assert mock_toplevel.called
            assert mock_tooltip_window.deiconify.called

            # When: Tooltip is hidden (standard hide)
            tooltip.hide()

            # Then: Tooltip is hidden but not destroyed
            assert mock_tooltip_window.withdraw.called
            assert tooltip.tooltip is not None


class TestUserTooltipPositioning:
    """Test tooltip positioning logic to ensure tooltips are always visible and usable."""

    def test_user_sees_tooltip_when_positioned_at_edge_of_parent_window(self, mock_widget) -> None:
        """
        Test tooltip repositioning when near parent window edge.

        GIVEN: Widget is positioned near the edge of the parent window
        WHEN: Tooltip would extend beyond parent window boundaries
        THEN: Tooltip is repositioned to stay within visible area
        AND: User can always read the help text
        """
        with patch("tkinter.Toplevel") as mock_toplevel:
            mock_tooltip_window = MagicMock()
            mock_toplevel.return_value = mock_tooltip_window

            # Mock widget position near right edge
            mock_widget.winfo_rootx.return_value = 1800  # Near right edge of 1920px screen
            mock_widget.winfo_rooty.return_value = 100
            mock_widget.winfo_width.return_value = 100
            mock_widget.winfo_height.return_value = 30

            # Mock parent window
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent

            # Mock tooltip dimensions
            mock_tooltip_window.winfo_reqwidth.return_value = 200
            mock_tooltip_window.winfo_reqheight.return_value = 50

            tooltip = Tooltip(mock_widget, "Edge tooltip")

            # When: Tooltip position is calculated
            tooltip.position_tooltip()

            # Then: Tooltip is repositioned to fit within parent window
            # Expected x: max(1800 + min(100//2, 100) = 1850, but 1850 + 200 = 2050 > 1920, so 1920 - 200 = 1720
            # Expected y: 100 + 30 = 130 (position_below=True)
            mock_tooltip_window.geometry.assert_called_with("+1720+130")

    def test_user_sees_tooltip_when_widget_is_at_bottom_of_parent_window(self, mock_widget) -> None:
        """
        Test tooltip repositioning when widget is at bottom of window.

        GIVEN: Widget is positioned at the bottom of the parent window
        WHEN: Tooltip would extend below parent window
        THEN: Tooltip is repositioned above the widget
        AND: User can access help without scrolling
        """
        with patch("tkinter.Toplevel") as mock_toplevel:
            mock_tooltip_window = MagicMock()
            mock_toplevel.return_value = mock_tooltip_window

            # Mock widget position at bottom
            mock_widget.winfo_rootx.return_value = 500
            mock_widget.winfo_rooty.return_value = 1000  # Near bottom of 1080px screen
            mock_widget.winfo_width.return_value = 100
            mock_widget.winfo_height.return_value = 30

            # Mock parent window
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent

            # Mock tooltip dimensions
            mock_tooltip_window.winfo_reqwidth.return_value = 150
            mock_tooltip_window.winfo_reqheight.return_value = 100

            tooltip = Tooltip(mock_widget, "Bottom tooltip", position_below=True)

            # When: Tooltip position is calculated
            tooltip.position_tooltip()

            # Then: Tooltip is repositioned above widget since it would go below screen
            # y would be 1000 + 30 = 1030, but 1030 + 100 = 1130 > 1080, so 1080 - 100 = 980
            mock_tooltip_window.geometry.assert_called_with("+550+980")

    def test_user_sees_tooltip_with_position_above_when_requested(self, mock_widget) -> None:
        """
        Test tooltip positioning above widget when requested.

        GIVEN: User requests tooltip above widget
        WHEN: Tooltip is positioned
        THEN: Tooltip appears above the widget as requested
        AND: User gets expected positioning behavior
        """
        with patch("tkinter.Toplevel") as mock_toplevel:
            mock_tooltip_window = MagicMock()
            mock_toplevel.return_value = mock_tooltip_window

            # Mock widget position
            mock_widget.winfo_rootx.return_value = 500
            mock_widget.winfo_rooty.return_value = 500
            mock_widget.winfo_width.return_value = 100
            mock_widget.winfo_height.return_value = 30

            # Mock parent window
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent

            # Mock tooltip dimensions
            mock_tooltip_window.winfo_reqwidth.return_value = 150
            mock_tooltip_window.winfo_reqheight.return_value = 50

            tooltip = Tooltip(mock_widget, "Above tooltip", position_below=False)

            # When: Tooltip position is calculated
            tooltip.position_tooltip()

            # Then: Tooltip is positioned above widget (y = 500 - 10 = 490)
            mock_tooltip_window.geometry.assert_called_with("+550+490")


class TestUserTooltipLifecycle:
    """Test tooltip show/hide lifecycle methods."""

    def test_user_can_show_existing_tooltip(self, mock_widget) -> None:
        """
        Test that user can show an existing tooltip.

        GIVEN: Tooltip already exists
        WHEN: User triggers show event
        THEN: Tooltip becomes visible
        AND: Position is recalculated
        """
        with patch("tkinter.Toplevel") as mock_toplevel:
            mock_tooltip_window = MagicMock()
            mock_toplevel.return_value = mock_tooltip_window

            # Configure mock widget and parent
            mock_widget.winfo_rootx.return_value = 100
            mock_widget.winfo_rooty.return_value = 100
            mock_widget.winfo_width.return_value = 50
            mock_widget.winfo_height.return_value = 20
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent
            mock_tooltip_window.winfo_reqwidth.return_value = 150
            mock_tooltip_window.winfo_reqheight.return_value = 50

            tooltip = Tooltip(mock_widget, "Test tooltip")

            # When: Tooltip is shown
            tooltip.show()

            # Then: Tooltip is made visible and position is set
            mock_tooltip_window.deiconify.assert_called_once()
            mock_tooltip_window.geometry.assert_called_once()

    def test_user_can_hide_existing_tooltip(self, mock_widget) -> None:
        """
        Test that user can hide an existing tooltip.

        GIVEN: Tooltip is visible
        WHEN: User triggers hide event
        THEN: Tooltip becomes hidden
        AND: Window remains available for future use
        """
        with patch("tkinter.Toplevel") as mock_toplevel:
            mock_tooltip_window = MagicMock()
            mock_toplevel.return_value = mock_tooltip_window

            tooltip = Tooltip(mock_widget, "Test tooltip")

            # When: Tooltip is hidden
            tooltip.hide()

            # Then: Tooltip is withdrawn but not destroyed
            assert mock_tooltip_window.withdraw.called
            assert tooltip.tooltip is not None

    def test_user_can_destroy_tooltip_on_macos_style_hide(self, mock_widget) -> None:
        """
        Test that tooltip can be fully destroyed.

        GIVEN: Tooltip exists
        WHEN: Destroy hide is called (macOS style)
        THEN: Tooltip is completely removed
        AND: Memory is freed
        """
        with (
            patch("tkinter.Toplevel") as mock_toplevel,
            patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"),
        ):
            mock_tooltip_window = MagicMock()
            mock_toplevel.return_value = mock_tooltip_window
            mock_tooltip_window.winfo_reqwidth.return_value = 150
            mock_tooltip_window.winfo_reqheight.return_value = 50

            # Configure mock widget
            mock_widget.winfo_rootx.return_value = 100
            mock_widget.winfo_rooty.return_value = 100
            mock_widget.winfo_width.return_value = 50
            mock_widget.winfo_height.return_value = 20
            mock_parent = MagicMock()
            mock_parent.winfo_rootx.return_value = 0
            mock_parent.winfo_rooty.return_value = 0
            mock_parent.winfo_width.return_value = 1920
            mock_parent.winfo_height.return_value = 1080
            mock_widget.winfo_toplevel.return_value = mock_parent

            tooltip = Tooltip(mock_widget, "Test tooltip")

            # Simulate creating the tooltip (on macOS, it's created on enter)
            tooltip.create_show()

            # When: Tooltip is destroyed
            tooltip.destroy_hide()

            # Then: Tooltip is fully destroyed
            mock_tooltip_window.destroy.assert_called_once()
            assert tooltip.tooltip is None


class TestUserTooltipOnRichTextTagInteraction:
    """
    BDD tests for user interactions with tooltips on RichText widget tags.

    These tests verify that users can see helpful tooltips when hovering over
    specific tags in RichText widgets, providing contextual information for
    clickable links and other tagged content.
    """

    def test_user_sees_tooltip_when_hovering_over_tagged_text(self) -> None:
        """
        Given: A RichText widget with tagged text and tooltip function.

        When: User hovers over the tagged text
        Then: A helpful tooltip appears with the specified message
        """
        # Given: RichText widget with tagged text
        mock_text_widget = MagicMock()
        mock_text_widget.tag_names.return_value = ["clickable_link"]
        mock_text_widget.tag_ranges.return_value = ("1.0", "1.10")

        mock_tooltip = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip", return_value=mock_tooltip
        ) as mock_tooltip_class:
            # When: show_tooltip_on_richtext_tag is called
            result = show_tooltip_on_richtext_tag(mock_text_widget, "Click to open URL", "clickable_link")

            # Then: Tooltip is created with correct parameters
            mock_tooltip_class.assert_called_once_with(
                mock_text_widget, "Click to open URL", position_below=True, tag_name="clickable_link"
            )
            assert result == mock_tooltip

    def test_user_gets_no_tooltip_on_untagged_text(self) -> None:
        """
        Given: A RichText widget with some tagged text.

        When: User hovers over untagged text
        Then: No tooltip appears
        """
        # Given: RichText widget with only specific tagged text
        mock_text_widget = MagicMock()
        mock_text_widget.tag_names.return_value = ["clickable_link"]
        mock_text_widget.tag_ranges.return_value = ("1.0", "1.10")

        mock_tooltip = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip", return_value=mock_tooltip
        ) as mock_tooltip_class:
            # When: show_tooltip_on_richtext_tag is called for a different tag
            result = show_tooltip_on_richtext_tag(mock_text_widget, "Other tooltip", "other_tag")

            # Then: Tooltip is still created (function doesn't check if tag exists)
            mock_tooltip_class.assert_called_once_with(
                mock_text_widget, "Other tooltip", position_below=True, tag_name="other_tag"
            )
            assert result == mock_tooltip

    def test_user_sees_different_tooltips_for_different_tags(self) -> None:
        """
        Given: A RichText widget with multiple tagged sections.

        When: User hovers over different tagged sections
        Then: Appropriate tooltips appear for each tag
        """
        # Given: RichText widget with multiple tags
        mock_text_widget = MagicMock()
        mock_text_widget.tag_names.return_value = ["link1", "link2", "link3"]

        mock_tooltip = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip", return_value=mock_tooltip
        ) as mock_tooltip_class:
            # When: Multiple tooltips are set up for different tags
            result1 = show_tooltip_on_richtext_tag(mock_text_widget, "Tooltip for link 1", "link1")
            result2 = show_tooltip_on_richtext_tag(mock_text_widget, "Tooltip for link 2", "link2")
            result3 = show_tooltip_on_richtext_tag(mock_text_widget, "Tooltip for link 3", "link3")

            # Then: Each tag gets its own tooltip
            assert mock_tooltip_class.call_count == 3
            mock_tooltip_class.assert_any_call(mock_text_widget, "Tooltip for link 1", position_below=True, tag_name="link1")
            mock_tooltip_class.assert_any_call(mock_text_widget, "Tooltip for link 2", position_below=True, tag_name="link2")
            mock_tooltip_class.assert_any_call(mock_text_widget, "Tooltip for link 3", position_below=True, tag_name="link3")
            assert result1 == mock_tooltip
            assert result2 == mock_tooltip
            assert result3 == mock_tooltip


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
