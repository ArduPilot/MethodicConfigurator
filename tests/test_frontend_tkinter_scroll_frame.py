#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_scroll_frame.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame


class TestScrollFrameUserExperience:
    """Test ScrollFrame from the user's perspective - focusing on behavior, not implementation."""

    @pytest.fixture
    def scrollable_frame(self) -> ScrollFrame:
        """Fixture providing a ScrollFrame ready for user interaction testing."""
        with patch("tkinter.Canvas"), patch("tkinter.ttk.Frame"), patch("tkinter.Scrollbar"):
            frame = ScrollFrame(MagicMock())
            frame.canvas = MagicMock()
            frame.view_port = MagicMock()
            frame.vsb = MagicMock()
            frame.canvas_window = 1
            return frame

    def test_user_can_scroll_when_content_exceeds_visible_area(self, scrollable_frame) -> None:
        """
        User can scroll through content that doesn't fit in the visible area.

        GIVEN: A ScrollFrame containing content taller than the visible area
        WHEN: The user performs a scroll action (mouse wheel, etc.)
        THEN: The content should scroll appropriately to reveal hidden content
        """
        # Mock content that exceeds visible area
        scrollable_frame.canvas.winfo_height.return_value = 100  # Visible height
        scrollable_frame.canvas.bbox.return_value = (0, 0, 100, 500)  # Content height 500

        event = MagicMock()
        event.num = 4  # Linux scroll up event

        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Linux"):
            scrollable_frame.on_mouse_wheel(event)

        # Verify scrolling occurred
        scrollable_frame.canvas.yview_scroll.assert_called_once_with(-1, "units")

    def test_user_sees_scrollbar_when_content_overflows(self, scrollable_frame) -> None:
        """
        User sees a scrollbar when content exceeds the visible area.

        GIVEN: A ScrollFrame with content that doesn't fit
        WHEN: The frame is configured with overflowing content
        THEN: The scrollbar should be present and functional
        """
        # Mock overflowing content
        scrollable_frame.canvas.bbox.return_value = (0, 0, 100, 300)  # Content bounds

        scrollable_frame.on_frame_configure(None)

        # Verify scrollbar region is configured
        scrollable_frame.canvas.configure.assert_called_once_with(scrollregion=(0, 0, 100, 300))

    def test_user_content_resizes_when_container_changes_size(self, scrollable_frame) -> None:
        """
        User sees content properly resized when the container window changes size.

        GIVEN: A ScrollFrame in a resizable window
        WHEN: The user resizes the window horizontally
        THEN: The content should adjust its width to match the new container size
        """
        resize_event = MagicMock()
        resize_event.width = 800  # New window width

        scrollable_frame.on_canvas_configure(resize_event)

        # Verify content width was adjusted
        scrollable_frame.canvas.itemconfig.assert_called_once_with(1, width=800)

    def test_user_scrolling_works_on_any_supported_platform(self, scrollable_frame) -> None:
        """
        User can scroll on any supported platform (Windows, macOS, Linux).

        GIVEN: A ScrollFrame with scrollable content on different platforms
        WHEN: The user scrolls using platform-appropriate input methods
        THEN: Scrolling should work regardless of platform
        """
        # Mock scrollable content
        scrollable_frame.canvas.winfo_height.return_value = 100
        scrollable_frame.canvas.bbox.return_value = (0, 0, 100, 400)

        # Test Windows scrolling
        event_win = MagicMock()
        event_win.delta = 120
        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Windows"):
            scrollable_frame.on_mouse_wheel(event_win)
            scrollable_frame.canvas.yview_scroll.assert_called_with(-1, "units")

        # Reset mock
        scrollable_frame.canvas.yview_scroll.reset_mock()

        # Test macOS scrolling
        event_mac = MagicMock()
        event_mac.delta = 10
        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Darwin"):
            scrollable_frame.on_mouse_wheel(event_mac)
            scrollable_frame.canvas.yview_scroll.assert_called_with(-10, "units")

        # Reset mock
        scrollable_frame.canvas.yview_scroll.reset_mock()

        # Test Linux scrolling (Button-4 = scroll up)
        event_linux_up = MagicMock()
        event_linux_up.num = 4
        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Linux"):
            scrollable_frame.on_mouse_wheel(event_linux_up)
            scrollable_frame.canvas.yview_scroll.assert_called_with(-1, "units")

        # Reset mock
        scrollable_frame.canvas.yview_scroll.reset_mock()

        # Test Linux scrolling (Button-5 = scroll down)
        event_linux_down = MagicMock()
        event_linux_down.num = 5
        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Linux"):
            scrollable_frame.on_mouse_wheel(event_linux_down)
            scrollable_frame.canvas.yview_scroll.assert_called_with(1, "units")

    def test_user_does_not_scroll_when_all_content_is_visible(self, scrollable_frame) -> None:
        """
        User does not see scrolling behavior when all content fits in the visible area.

        GIVEN: A ScrollFrame where all content fits within the visible area
        WHEN: The user attempts to scroll
        THEN: No scrolling should occur since it's not needed
        """
        # Mock content that fits completely in visible area
        scrollable_frame.canvas.winfo_height.return_value = 500  # Large visible area
        scrollable_frame.canvas.bbox.return_value = (0, 0, 100, 200)  # Small content

        event = MagicMock()
        event.delta = 120

        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Windows"):
            scrollable_frame.on_mouse_wheel(event)

        # Verify no scrolling occurred
        scrollable_frame.canvas.yview_scroll.assert_not_called()

    def test_user_mouse_events_are_properly_managed_on_enter_leave(self, scrollable_frame) -> None:
        """
        User mouse events are properly bound and unbound as cursor enters/leaves the scroll area.

        GIVEN: A ScrollFrame that should capture mouse events when active
        WHEN: The cursor enters and leaves the scrollable area
        THEN: Mouse events should be bound when entering and unbound when leaving
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Windows"):
            # Enter the area
            scrollable_frame.on_enter(None)
            scrollable_frame.canvas.bind_all.assert_called_with("<MouseWheel>", scrollable_frame.on_mouse_wheel)

            # Leave the area
            scrollable_frame.on_leave(None)
            scrollable_frame.canvas.unbind_all.assert_called_with("<MouseWheel>")

    def test_user_mouse_events_are_properly_managed_on_linux(self, scrollable_frame) -> None:
        """
        User mouse events are properly bound and unbound on Linux platform.

        GIVEN: A ScrollFrame on Linux platform
        WHEN: The cursor enters and leaves the scrollable area
        THEN: Linux-specific mouse events should be bound when entering and unbound when leaving
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_scroll_frame.platform_system", return_value="Linux"):
            # Enter the area
            scrollable_frame.on_enter(None)
            scrollable_frame.canvas.bind_all.assert_any_call("<Button-4>", scrollable_frame.on_mouse_wheel)
            scrollable_frame.canvas.bind_all.assert_any_call("<Button-5>", scrollable_frame.on_mouse_wheel)

            # Reset mock
            scrollable_frame.canvas.bind_all.reset_mock()

            # Leave the area
            scrollable_frame.on_leave(None)
            scrollable_frame.canvas.unbind_all.assert_any_call("<Button-4>")
            scrollable_frame.canvas.unbind_all.assert_any_call("<Button-5>")
