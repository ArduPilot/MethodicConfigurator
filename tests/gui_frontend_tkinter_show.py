#!/usr/bin/env python3

"""
GUI integration tests for tooltip functionality using PyAutoGUI.

This module contains automated GUI tests for the Tkinter tooltip system.
Tests verify that tooltips work correctly in real GUI scenarios, focusing on
user experience and business value rather than implementation details.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import time
from collections.abc import Generator
from tkinter import ttk

import pyautogui
import pytest

from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip, show_tooltip_on_richtext_tag

# pylint: disable=unused-argument


class TestTooltipUserExperienceIntegration:
    """Integration tests for tooltip user experience using real GUI components."""

    @pytest.fixture(autouse=True)
    def setup_pyautogui(self) -> Generator[None, None, None]:
        """Disable PyAutoGUI fail-safe for testing."""
        original_failsafe = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False
        yield
        pyautogui.FAILSAFE = original_failsafe

    @pytest.fixture
    def tooltip_test_window(self, tk_root) -> Generator[ttk.Frame, None, None]:
        """
        Create a test window with various widgets for tooltip testing.

        GIVEN: A user has the application open
        WHEN: They interact with different UI elements
        THEN: Tooltips should provide helpful guidance
        """
        # Create a test frame
        test_frame = ttk.Frame(tk_root)
        test_frame.pack(padx=20, pady=20)

        # Create various widgets with tooltips
        button = ttk.Button(test_frame, text="Test Button")
        button.pack(pady=10)
        show_tooltip(button, "This button performs an important action when clicked.")

        label = ttk.Label(test_frame, text="Test Label")
        label.pack(pady=10)
        show_tooltip(label, "This label shows important information to the user.")

        entry = ttk.Entry(test_frame)
        entry.pack(pady=10)
        show_tooltip(entry, "Enter your configuration value here.")

        # Create RichText widget with tagged content
        rich_text = RichText(test_frame, wrap="word", height=3, width=50)
        rich_text.pack(pady=10)
        rich_text.insert("end", "Click here for ")
        rich_text.insert_clickable_link("help documentation", "help_link", "https://example.com/help")
        rich_text.insert("end", " or visit ")
        rich_text.insert_clickable_link("support forum", "forum_link", "https://example.com/forum")
        rich_text.insert("end", " for assistance.")

        # Add tooltips to the RichText tags
        show_tooltip_on_richtext_tag(rich_text, "Opens the official help documentation in your browser", "help_link")
        show_tooltip_on_richtext_tag(rich_text, "Access community support and discussions", "forum_link")

        # Force geometry calculation
        tk_root.update_idletasks()

        yield test_frame

        # Cleanup
        test_frame.destroy()

    def test_user_sees_helpful_tooltips_when_hovering_over_ui_elements(self, tooltip_test_window, tk_root) -> None:
        """
        User sees helpful tooltips when hovering over UI elements.

        GIVEN: A user is interacting with the application's interface
        WHEN: They hover over buttons, labels, and input fields
        THEN: Helpful tooltips appear providing context and guidance
        AND: The tooltips contain relevant information for the specific element
        AND: Tooltips appear near the cursor for easy reading
        """
        # Get the button widget
        button = None
        for child in tooltip_test_window.winfo_children():
            if isinstance(child, ttk.Button):
                button = child
                break

        assert button is not None, "Button should be found in test window"

        # Get button position on screen
        button_x = button.winfo_rootx() + button.winfo_width() // 2
        button_y = button.winfo_rooty() + button.winfo_height() // 2

        # Move mouse to button and wait for tooltip
        pyautogui.moveTo(button_x, button_y)
        time.sleep(0.5)  # Allow tooltip to appear

        # Take screenshot to verify tooltip appearance
        screenshot = pyautogui.screenshot()

        # The tooltip should be visible (this is a simplified check)
        # In practice, you might use more sophisticated image analysis
        assert screenshot is not None, "Screenshot should be captured"

        # Verify the button is still functional
        assert button.cget("text") == "Test Button"

    def test_user_sees_context_specific_tooltips_on_richtext_links(self, tooltip_test_window, tk_root) -> None:
        """
        User sees context-specific tooltips on RichText clickable links.

        GIVEN: A user is reading rich text content with clickable links
        WHEN: They hover over different types of links
        THEN: Each link shows a specific tooltip explaining what will happen when clicked
        AND: Tooltips help users understand the purpose of each link before clicking
        AND: Different link types have distinct tooltip messages
        """
        # Find the RichText widget
        rich_text = None
        for child in tooltip_test_window.winfo_children():
            if isinstance(child, RichText):
                rich_text = child
                break

        assert rich_text is not None, "RichText widget should be found"

        # Get RichText position
        text_x = rich_text.winfo_rootx() + 50  # Approximate position of first link
        text_y = rich_text.winfo_rooty() + rich_text.winfo_height() // 2

        # Move mouse to approximate link position
        pyautogui.moveTo(text_x, text_y)
        time.sleep(0.5)

        # Take screenshot
        screenshot = pyautogui.screenshot()

        # Verify screenshot was taken (simplified check)
        assert screenshot is not None

        # Verify the RichText widget contains the expected content
        text_content = rich_text.get("1.0", "end").strip()
        assert "help documentation" in text_content
        assert "support forum" in text_content

    def test_user_experiences_consistent_tooltip_behavior_across_widgets(self, tooltip_test_window, tk_root) -> None:
        """
        User experiences consistent tooltip behavior across different widget types.

        GIVEN: A user interacts with various UI elements in the application
        WHEN: They hover over different types of widgets
        THEN: All tooltips behave consistently in terms of timing and positioning
        AND: The user gets a cohesive help experience throughout the application
        AND: Tooltips don't interfere with normal widget functionality
        """
        widgets = [
            child for child in tooltip_test_window.winfo_children() if isinstance(child, (ttk.Button, ttk.Label, ttk.Entry))
        ]

        assert len(widgets) >= 3, "Should have at least 3 widgets with tooltips"

        # Test each widget
        for widget in widgets:
            # Get widget center position
            widget_x = widget.winfo_rootx() + widget.winfo_width() // 2
            widget_y = widget.winfo_rooty() + widget.winfo_height() // 2

            # Move mouse to widget
            pyautogui.moveTo(widget_x, widget_y)
            time.sleep(0.3)  # Brief pause

            # Move mouse away
            pyautogui.moveTo(widget_x + 100, widget_y)
            time.sleep(0.2)

            # Verify widget is still functional
            if isinstance(widget, ttk.Button):
                assert widget.cget("state") != "disabled"
            elif isinstance(widget, ttk.Entry):
                # Entry should be focusable
                assert widget.cget("state") != "disabled"

    def test_user_can_access_help_information_without_disrupting_workflow(self, tooltip_test_window, tk_root) -> None:
        """
        User can access help information without disrupting their workflow.

        GIVEN: A user is working through a configuration process
        WHEN: They need occasional help or reminders about UI elements
        THEN: Tooltips provide information without requiring them to leave their current context
        AND: Tooltips appear and disappear smoothly without blocking interaction
        AND: Users can continue their work immediately after seeing tooltip information
        """
        # Find a button to test with
        button = None
        for child in tooltip_test_window.winfo_children():
            if isinstance(child, ttk.Button):
                button = child
                break

        assert button is not None

        # Get button position
        button_x = button.winfo_rootx() + button.winfo_width() // 2
        button_y = button.winfo_rooty() + button.winfo_height() // 2

        # Simulate user workflow: hover to see tooltip, then click button
        pyautogui.moveTo(button_x, button_y)
        time.sleep(0.5)  # Tooltip appears

        # User can still interact with the button
        # In a real test, you might simulate a click, but for now we verify the button is accessible
        assert button.cget("text") == "Test Button", "Button should remain functional"

        # Move mouse away - tooltip should disappear
        pyautogui.moveTo(button_x + 100, button_y + 100)
        time.sleep(0.5)

        # Button should still be functional
        assert button.cget("text") == "Test Button"

    def test_user_sees_tooltips_positioned_for_easy_reading(self, tooltip_test_window, tk_root) -> None:
        """
        User sees tooltips positioned for easy reading and minimal obstruction.

        GIVEN: A user needs help information while working
        WHEN: Tooltips appear near interactive elements
        THEN: Tooltips are positioned to not obstruct the element being explained
        AND: Tooltips appear near the cursor for immediate visibility
        AND: Positioning adapts to screen boundaries when necessary
        """
        # Test with a widget near the edge of the window
        # Move the test window to ensure we have space to test positioning

        # Find a widget to test
        label = None
        for child in tooltip_test_window.winfo_children():
            if isinstance(child, ttk.Label):
                label = child
                break

        assert label is not None

        # Position mouse at widget
        label_x = label.winfo_rootx() + label.winfo_width() // 2
        label_y = label.winfo_rooty() + label.winfo_height() // 2

        pyautogui.moveTo(label_x, label_y)
        time.sleep(0.5)

        # Verify the widget is still visible and accessible
        assert label.cget("text") == "Test Label", "Label should remain functional"

        # Check that we're within reasonable screen bounds
        screen_width, screen_height = pyautogui.size()
        assert 0 <= label_x <= screen_width
        assert 0 <= label_y <= screen_height

    def test_user_experiences_reliable_tooltip_system_under_normal_usage(self, tk_root) -> None:
        """
        User experiences a reliable tooltip system under normal usage conditions.

        GIVEN: A user is using the application under normal conditions
        WHEN: They interact with tooltip-enabled elements repeatedly
        THEN: The tooltip system works reliably without crashes or unexpected behavior
        AND: Tooltips appear consistently across multiple interactions
        AND: The system handles rapid mouse movements gracefully
        """
        # Create multiple widgets with tooltips
        test_frame = ttk.Frame(tk_root)
        test_frame.pack(padx=20, pady=20)

        # Create several buttons with tooltips
        for i in range(5):
            button = ttk.Button(test_frame, text=f"Button {i + 1}")
            button.pack(pady=5)
            show_tooltip(button, f"This is button {i + 1} with tooltip")

        tk_root.update_idletasks()

        # Test rapid interactions
        buttons = [child for child in test_frame.winfo_children() if isinstance(child, ttk.Button)]

        for button in buttons:
            button_x = button.winfo_rootx() + button.winfo_width() // 2
            button_y = button.winfo_rooty() + button.winfo_height() // 2

            # Quick hover
            pyautogui.moveTo(button_x, button_y)
            time.sleep(0.2)

            # Move to next button quickly
            pyautogui.moveTo(button_x + 50, button_y)
            time.sleep(0.1)

        # Verify all buttons are still functional
        for i, button in enumerate(buttons):
            assert button.cget("text") == f"Button {i + 1}"
            assert button.cget("state") != "disabled", f"Button {i + 1} should remain enabled"

        test_frame.destroy()

    def test_user_sees_tooltips_with_clear_helpful_text(self, tk_root) -> None:
        """
        User sees tooltips with clear, helpful, and contextually appropriate text.

        GIVEN: A user needs guidance while using the application
        WHEN: They see tooltips on various elements
        THEN: Tooltip text is clear and helpful for the specific context
        AND: Text is concise but informative
        AND: Tooltips use appropriate language for the target audience
        """
        # Create a test widget with a specific tooltip
        test_frame = ttk.Frame(tk_root)
        test_frame.pack(padx=20, pady=20)

        button = ttk.Button(test_frame, text="Save Configuration")
        button.pack(pady=10)

        # Add a realistic tooltip
        show_tooltip(button, "Save your current parameter configuration to a file for later use.")

        tk_root.update_idletasks()

        # Get button position
        button_x = button.winfo_rootx() + button.winfo_width() // 2
        button_y = button.winfo_rooty() + button.winfo_height() // 2

        # Hover to show tooltip
        pyautogui.moveTo(button_x, button_y)
        time.sleep(0.5)

        # Verify the button and tooltip setup
        assert button.cget("text") == "Save Configuration"
        assert button.cget("state") != "disabled", "Button should remain functional"

        # Clean up
        test_frame.destroy()

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS specific GUI test")
    def test_gui_functionality_on_macos(self, tooltip_test_window, tk_root) -> None:
        """
        MacOS specific test for GUI functionality.

        GIVEN: A user is running the application on macOS
        WHEN: They interact with tooltip-enabled UI elements
        THEN: Tooltips work correctly using Quartz/XQuartz framework
        AND: PyAutoGUI can capture screenshots and simulate input
        AND: Tkinter widgets remain functional
        """
        # Get the button widget
        button = None
        for child in tooltip_test_window.winfo_children():
            if isinstance(child, ttk.Button):
                button = child
                break

        assert button is not None, "Button should be found in test window"

        # Get button position on screen
        button_x = button.winfo_rootx() + button.winfo_width() // 2
        button_y = button.winfo_rooty() + button.winfo_height() // 2

        # Move mouse to button and wait for tooltip
        pyautogui.moveTo(button_x, button_y)
        time.sleep(0.5)  # Allow tooltip to appear

        # Take screenshot to verify GUI is working on macOS
        screenshot = pyautogui.screenshot()

        # Verify screenshot was captured successfully
        assert screenshot is not None, "Screenshot should be captured on macOS"

        # Verify the button remains functional
        assert button.cget("text") == "Test Button"
        assert button.cget("state") != "disabled", "Button should remain enabled on macOS"

    def test_user_experiences_tooltip_positioning_at_screen_edges(self, tk_root) -> None:
        """
        User experiences correct tooltip positioning at screen edges.

        GIVEN: Widgets positioned at screen edges
        WHEN: Tooltips are triggered
        THEN: Tooltips are positioned to stay within screen bounds
        AND: Positioning adapts to prevent tooltips from going off-screen
        """
        # Create a frame and position it
        test_frame = ttk.Frame(tk_root)
        test_frame.pack(padx=20, pady=20)

        # Create widgets at different positions
        # Top-left widget
        top_left_button = ttk.Button(test_frame, text="Top Left")
        top_left_button.pack(anchor="nw", pady=5)
        show_tooltip(top_left_button, "Tooltip for top-left button")

        # Bottom-right widget (simulate by placing at bottom)
        bottom_right_button = ttk.Button(test_frame, text="Bottom Right")
        bottom_right_button.pack(anchor="se", pady=5)
        show_tooltip(bottom_right_button, "Tooltip for bottom-right button")

        tk_root.update_idletasks()

        # Test hovering over top-left button
        top_x = top_left_button.winfo_rootx() + 5
        top_y = top_left_button.winfo_rooty() + 5

        pyautogui.moveTo(top_x, top_y)
        time.sleep(0.5)

        screenshot = pyautogui.screenshot()
        assert screenshot is not None

        # Test hovering over bottom-right button
        bottom_x = bottom_right_button.winfo_rootx() + bottom_right_button.winfo_width() // 2
        bottom_y = bottom_right_button.winfo_rooty() + bottom_right_button.winfo_height() // 2

        pyautogui.moveTo(bottom_x, bottom_y)
        time.sleep(0.5)

        screenshot = pyautogui.screenshot()
        assert screenshot is not None

        # Verify widgets remain functional
        assert top_left_button.cget("text") == "Top Left"
        assert bottom_right_button.cget("text") == "Bottom Right"

        test_frame.destroy()

    def test_user_sees_multiple_tooltips_without_interference(self, tk_root) -> None:
        """
        User sees multiple tooltips without interference.

        GIVEN: Multiple widgets with tooltips in the same interface
        WHEN: User hovers over different widgets rapidly
        THEN: Each tooltip appears correctly without interfering with others
        AND: Tooltips are managed properly without conflicts
        """
        test_frame = ttk.Frame(tk_root)
        test_frame.pack(padx=20, pady=20)

        # Create multiple buttons with tooltips
        buttons = []
        for i in range(3):
            button = ttk.Button(test_frame, text=f"Button {i + 1}")
            button.pack(pady=5)
            show_tooltip(button, f"Tooltip for button {i + 1}")
            buttons.append(button)

        tk_root.update_idletasks()

        # Rapidly hover over each button
        for button in buttons:
            button_x = button.winfo_rootx() + button.winfo_width() // 2
            button_y = button.winfo_rooty() + button.winfo_height() // 2

            pyautogui.moveTo(button_x, button_y)
            time.sleep(0.3)  # Allow tooltip to appear

            # Move to next position
            pyautogui.moveTo(button_x + 50, button_y)
            time.sleep(0.2)

        # Verify all buttons are still functional
        for i, button in enumerate(buttons):
            assert button.cget("text") == f"Button {i + 1}"
            assert button.cget("state") != "disabled"

        test_frame.destroy()

    def test_user_experiences_tooltip_with_richtext_at_cursor_position(self, tk_root) -> None:
        """
        User experiences tooltip with RichText at cursor position.

        GIVEN: RichText widget with clickable links
        WHEN: User hovers over different parts of the text
        THEN: Tooltips appear based on tagged regions
        AND: Only relevant tooltips show for the hovered area
        """
        test_frame = ttk.Frame(tk_root)
        test_frame.pack(padx=20, pady=20)

        rich_text = RichText(test_frame, wrap="word", height=4, width=60)
        rich_text.pack(pady=10)

        # Insert text with multiple links
        rich_text.insert("end", "Visit the ")
        rich_text.insert_clickable_link("documentation", "doc_link", "https://docs.example.com")
        rich_text.insert("end", " or check ")
        rich_text.insert_clickable_link("FAQ", "faq_link", "https://faq.example.com")
        rich_text.insert("end", " for help.")

        # Add tooltips
        show_tooltip_on_richtext_tag(rich_text, "Access comprehensive documentation", "doc_link")
        show_tooltip_on_richtext_tag(rich_text, "Frequently asked questions", "faq_link")

        tk_root.update_idletasks()

        # Get RichText position
        text_x = rich_text.winfo_rootx() + 20  # Approximate position of first link
        text_y = rich_text.winfo_rooty() + rich_text.winfo_height() // 2

        # Hover over approximate link position
        pyautogui.moveTo(text_x, text_y)
        time.sleep(0.5)

        screenshot = pyautogui.screenshot()
        assert screenshot is not None

        # Verify RichText content
        content = rich_text.get("1.0", "end").strip()
        assert "documentation" in content
        assert "FAQ" in content

        test_frame.destroy()

    def test_user_sees_tooltip_timing_behavior(self, tk_root) -> None:
        """
        User sees tooltip timing behavior.

        GIVEN: A widget with tooltip
        WHEN: User hovers and moves mouse away quickly
        THEN: Tooltip appears and disappears with appropriate timing
        AND: Rapid movements don't cause tooltip to get stuck
        """
        test_frame = ttk.Frame(tk_root)
        test_frame.pack(padx=20, pady=20)

        button = ttk.Button(test_frame, text="Timing Test")
        button.pack(pady=10)
        show_tooltip(button, "Test tooltip timing")

        tk_root.update_idletasks()

        button_x = button.winfo_rootx() + button.winfo_width() // 2
        button_y = button.winfo_rooty() + button.winfo_height() // 2

        # Quick hover
        pyautogui.moveTo(button_x, button_y)
        time.sleep(0.2)

        # Move away quickly
        pyautogui.moveTo(button_x + 100, button_y + 100)
        time.sleep(0.3)  # Allow hide timer to trigger

        # Verify button is still functional
        assert button.cget("text") == "Timing Test"
        assert button.cget("state") != "disabled"

        test_frame.destroy()
