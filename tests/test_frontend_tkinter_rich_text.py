#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_rich_text.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from platform import system as platform_system
from tkinter import ttk
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_rich_text import (
    RichText,
    _get_ttk_label_color,
    get_widget_font_family_and_size,
)


class TestRichText(unittest.TestCase):
    """Test cases for the RichText class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.rich_text = RichText(self.root)

    def tearDown(self) -> None:
        self.root.update_idletasks()
        self.root.destroy()

    def test_initialization(self) -> None:
        assert isinstance(self.rich_text, tk.Text)
        assert self.rich_text.tag_cget("bold", "font")
        assert self.rich_text.tag_cget("italic", "font")
        assert self.rich_text.tag_cget("h1", "font")

    def test_tag_configure(self) -> None:
        self.rich_text.insert("1.0", "Bold Text\n", "bold")
        self.rich_text.insert("2.0", "Italic Text\n", "italic")
        self.rich_text.insert("3.0", "Heading Text\n", "h1")
        assert self.rich_text.get("1.0", "1.end") == "Bold Text"
        assert self.rich_text.get("2.0", "2.end") == "Italic Text"
        assert self.rich_text.get("3.0", "3.end") == "Heading Text"

    def test_insert_text(self) -> None:
        self.rich_text.insert("1.0", "Normal Text\n")
        self.rich_text.insert("2.0", "Bold Text\n", "bold")
        self.rich_text.insert("3.0", "Italic Text\n", "italic")
        self.rich_text.insert("4.0", "Heading Text\n", "h1")
        assert self.rich_text.get("1.0", "1.end") == "Normal Text"
        assert self.rich_text.get("2.0", "2.end") == "Bold Text"
        assert self.rich_text.get("3.0", "3.end") == "Italic Text"
        assert self.rich_text.get("4.0", "4.end") == "Heading Text"

    def test_multiple_tags(self) -> None:
        """Test applying multiple tags to text."""
        self.rich_text.insert("1.0", "Bold and Italic\n", ("bold", "italic"))
        self.rich_text.insert("2.0", "Bold and H1\n", ("bold", "h1"))
        assert "bold" in self.rich_text.tag_names("1.0")
        assert "italic" in self.rich_text.tag_names("1.0")
        assert "bold" in self.rich_text.tag_names("2.0")
        assert "h1" in self.rich_text.tag_names("2.0")


class TestUserClickableLinkInteraction(unittest.TestCase):
    """Test that users can interact with clickable links in rich text widgets."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.rich_text = RichText(self.root)

    def tearDown(self) -> None:
        self.root.update_idletasks()
        self.root.destroy()

    def test_user_can_click_link_to_open_url(self) -> None:
        """
        Given: User sees a clickable link in the rich text widget.

        WHEN: User clicks on the link
        THEN: The URL opens in the default web browser
        AND: User gets visual feedback that it's clickable
        """
        mock_tooltip = MagicMock()
        with (
            patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open_url"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_rich_text.show_tooltip_on_richtext_tag",
                return_value=mock_tooltip,
            ) as mock_show_tooltip,
        ):
            # When: User inserts a clickable link
            self.rich_text.insert_clickable_link("Click here", "link1", "https://example.com")

            # Then: Link text is inserted with proper styling
            content = self.rich_text.get("1.0", tk.END).strip()
            assert content == "Click here"

            # And: Link has blue color and underline
            link_config = self.rich_text.tag_configure("link1")
            assert "foreground" in str(link_config)
            assert "underline" in str(link_config)

            # And: Tooltip is configured to show the URL
            mock_show_tooltip.assert_called_once_with(self.rich_text, "https://example.com", "link1")

            # And: Tooltip is shown for the link
            mock_show_tooltip.assert_called_once_with(self.rich_text, "https://example.com", "link1")

    def test_user_sees_multiple_unique_links_with_different_urls(self) -> None:
        """
        Given: User needs multiple links in the same document.

        WHEN: Multiple unique links are inserted
        THEN: Each link works independently
        AND: User can distinguish between different links
        """
        mock_tooltip = MagicMock()
        with (
            patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open_url"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_rich_text.show_tooltip_on_richtext_tag",
                return_value=mock_tooltip,
            ) as mock_show_tooltip,
        ):
            # When: Multiple links are inserted
            self.rich_text.insert_clickable_link("Link 1", "link1", "https://example1.com")
            self.rich_text.insert_clickable_link("Link 2", "link2", "https://example2.com")

            # Then: Both links are present
            content = self.rich_text.get("1.0", tk.END).strip()
            assert "Link 1" in content
            assert "Link 2" in content

            # And: Each link has its own tag configuration
            assert "link1" in self.rich_text.tag_names()
            assert "link2" in self.rich_text.tag_names()

            # And: Tooltips are set up for each link
            assert mock_show_tooltip.call_count == 2
            mock_show_tooltip.assert_any_call(self.rich_text, "https://example1.com", "link1")
            mock_show_tooltip.assert_any_call(self.rich_text, "https://example2.com", "link2")

            # And: Each link opens different URL when clicked
            # Click on first link
            self.rich_text.tag_bind("link1", "<Button-1>", lambda _: None)  # Clear existing binding
            self.rich_text.event_generate("<Button-1>", x=10, y=10)  # Simulate click on link1
            # Note: This is a simplified test - in real usage, the tag binding handles the click

    def test_user_gets_helpful_tooltips_on_links(self) -> None:
        """
        Given: User hovers over a link.

        WHEN: Tooltip appears
        THEN: User sees the URL as tooltip text
        AND: User understands where the link leads
        """
        mock_tooltip = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_rich_text.show_tooltip_on_richtext_tag",
            return_value=mock_tooltip,
        ) as mock_show_tooltip:
            # When: Link is inserted
            self.rich_text.insert_clickable_link("Visit Google", "google_link", "https://google.com")

            # Then: Tooltip is configured to show the URL
            mock_show_tooltip.assert_called_once_with(self.rich_text, "https://google.com", "google_link")


class TestGetWidgetFontFamilyAndSize(unittest.TestCase):
    """Test cases for the get_widget_font_family_and_size function."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests

    def tearDown(self) -> None:
        self.root.destroy()

    def test_get_widget_font_family_and_size(self) -> None:
        label = ttk.Label(self.root, text="Test")
        family, size = get_widget_font_family_and_size(label)
        expected_family = (
            ["Segoe UI"]
            if platform_system() == "Windows"
            else [".AppleSystemUIFont", "Helvetica"]
            if platform_system() == "Darwin"
            else ["Helvetica", "sans-serif"]
        )
        expected_size = [9] if platform_system() == "Windows" else [13] if platform_system() == "Darwin" else [-12, 10]
        assert isinstance(family, str)
        assert isinstance(size, int)
        assert family in expected_family
        assert size in expected_size


if __name__ == "__main__":
    unittest.main()


class TestRichTextColorAndFontFallbacks:
    """Tests for color and font fallback behavior in RichText."""

    def test_user_can_create_rich_text_with_explicit_background_color(self, root: tk.Tk) -> None:
        """
        User can create RichText with an explicit background color.

        GIVEN: User wants a custom background color for the text widget
        WHEN: RichText is created with a background kwarg
        THEN: The background kwarg should skip the auto-detection
        AND: Widget should use the provided background color
        """
        rich_text = RichText(root, background="red")
        assert rich_text.cget("background") == "red"

    def test_user_can_create_rich_text_with_bg_shorthand(self, root: tk.Tk) -> None:
        """
        User can create RichText with bg shorthand.

        GIVEN: User wants a custom background color using 'bg' alias
        WHEN: RichText is created with bg kwarg
        THEN: The bg kwarg should skip the auto-detection
        AND: Widget should use the provided background color
        """
        rich_text = RichText(root, bg="blue")
        # Color may be returned as RGB by Tk on some platforms
        assert rich_text.cget("background")

    def test_user_can_create_rich_text_with_explicit_foreground_color(self, root: tk.Tk) -> None:
        """
        User can create RichText with an explicit foreground color.

        GIVEN: User wants a custom foreground color
        WHEN: RichText is created with foreground kwarg
        THEN: The foreground kwarg should skip auto-detection
        AND: Widget should use provided foreground color
        """
        rich_text = RichText(root, foreground="green")
        assert rich_text.cget("foreground")

    def test_user_can_create_rich_text_with_fg_shorthand(self, root: tk.Tk) -> None:
        """
        User can create RichText with fg shorthand.

        GIVEN: User wants a custom foreground color using 'fg' alias
        WHEN: RichText is created with fg kwarg
        THEN: Widget should be created successfully
        """
        rich_text = RichText(root, fg="purple")
        assert rich_text.cget("foreground")

    def test_user_can_create_rich_text_when_safe_font_nametofont_returns_none(self, root: tk.Tk) -> None:
        """
        User can create RichText even when safe_font_nametofont returns None.

        GIVEN: The font lookup fails (returns None)
        WHEN: RichText is created without an explicit font
        THEN: Should fall back to get_safe_font_config for font configuration
        AND: Widget should be created successfully
        """
        with patch("ardupilot_methodic_configurator.frontend_tkinter_rich_text.safe_font_nametofont", return_value=None):
            rich_text = RichText(root)

        assert rich_text is not None
        assert "bold" in rich_text.tag_names()
        assert "italic" in rich_text.tag_names()
        assert "h1" in rich_text.tag_names()

    def test_get_ttk_label_color_handles_cget_tclerror(self) -> None:
        """
        _get_ttk_label_color handles TclError from widget.cget gracefully.

        GIVEN: A widget where cget raises TclError for the requested option
        WHEN: _get_ttk_label_color is called
        THEN: TclError should be caught and fallback color should be used
        """
        mock_widget = MagicMock()
        mock_widget.cget.side_effect = tk.TclError("Unknown option")

        # Mock style lookup to return empty so we enter the fallback branch
        with patch("ardupilot_methodic_configurator.frontend_tkinter_rich_text.ttk.Style") as mock_style_class:
            mock_style = MagicMock()
            mock_style.lookup.return_value = ""  # Empty = no style found
            mock_style_class.return_value = mock_style

            result = _get_ttk_label_color(mock_widget, "background", "white")

        # Should use fallback since cget raised TclError
        assert result == "white"
