#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_parameter_editor_documentation_frame.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import Mock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame import DocumentationFrame


@pytest.fixture
def mock_webbrowser_open() -> Mock:
    with patch("webbrowser.open") as mock:
        yield mock


@pytest.fixture
def mock_show_tooltip() -> Mock:
    with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip") as mock:
        yield mock


class TestDocumentationFrame(unittest.TestCase):
    """Test the DocumentationFrame class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.local_filesystem = Mock()
        self.local_filesystem.get_documentation_text_and_url.return_value = ("Sample blog text", "http://example.com/blog")
        self.current_file = "test_file"
        self.local_filesystem.get_seq_tooltip_text.side_effect = ["Why text", "Why now text"]
        self.doc_frame = DocumentationFrame(self.root, self.local_filesystem, self.current_file)

    def test_create_documentation_frame(self) -> None:
        """Test the creation of the documentation frame."""
        assert isinstance(self.doc_frame.documentation_frame, ttk.LabelFrame)
        assert self.doc_frame.documentation_frame.cget("text") == "test_file Documentation"

        expected_labels = [self.doc_frame.BLOG_LABEL, self.doc_frame.WIKI_LABEL, self.doc_frame.EXTERNAL_TOOL_LABEL]
        for label in expected_labels:
            assert label in self.doc_frame.documentation_labels

        assert isinstance(self.doc_frame.mandatory_level, ttk.Progressbar)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.webbrowser_open")
    def test_auto_open_documentation_links(self, mock_webbrowser_open_) -> None:
        """Test the automatic opening of documentation links."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = [
            ("Blog text", "http://blog.url"),
            ("Wiki text", "http://wiki.url"),
            ("External tool text", "http://external_tool.url"),
            ("Mandatory text", None),
        ]
        self.doc_frame.auto_open_var.set(True)

        self.doc_frame.open_documentation_in_browser(self.current_file)

        mock_webbrowser_open_.assert_any_call(url="http://wiki.url", new=0, autoraise=False)
        mock_webbrowser_open_.assert_any_call(url="http://external_tool.url", new=0, autoraise=False)
        mock_webbrowser_open_.assert_any_call(url="http://blog.url", new=0, autoraise=True)

    @pytest.mark.usefixtures("mock_show_tooltip")
    def test_update_why_why_now_tooltip(self) -> None:
        """Test the update_why_why_now_tooltip method."""
        self.local_filesystem.get_seq_tooltip_text.side_effect = ["Why text", "Why now text"]
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip"
        ) as mock_show_tooltip_:
            self.doc_frame.update_why_why_now_tooltip(self.current_file)
            mock_show_tooltip_.assert_called_once_with(
                self.doc_frame.documentation_frame, "Why: Why text\nWhy now: Why now text", position_below=False
            )

    @pytest.mark.usefixtures("mock_show_tooltip")
    def test_update_why_why_now_tooltip_with_both_tooltips(self) -> None:
        """Test the update_why_why_now_tooltip method with both tooltips present."""
        self.local_filesystem.get_seq_tooltip_text.side_effect = ["Why text", "Why now text"]
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip"
        ) as mock_show_tooltip_:
            self.doc_frame.update_why_why_now_tooltip(self.current_file)
            mock_show_tooltip_.assert_called_once_with(
                self.doc_frame.documentation_frame, "Why: Why text\nWhy now: Why now text", position_below=False
            )

    @pytest.mark.usefixtures("mock_show_tooltip")
    def test_update_why_why_now_tooltip_with_empty_tooltips(self) -> None:
        """Test the update_why_why_now_tooltip method with empty tooltips."""
        self.local_filesystem.get_seq_tooltip_text.side_effect = ["", ""]
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip"
        ) as mock_show_tooltip_:
            self.doc_frame.update_why_why_now_tooltip(self.current_file)
            mock_show_tooltip_.assert_not_called()

    @pytest.mark.usefixtures("mock_webbrowser_open", "mock_show_tooltip")
    def test_refresh_documentation_labels(self) -> None:
        """Test the refresh_documentation_labels method."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = lambda _file, key: {
            "blog": ("Blog text", "http://blog.url"),
            "wiki": ("Wiki text", "http://wiki.url"),
            "external_tool": ("External tool text", "http://external_tool.url"),
            "mandatory": ("75", None),  # Changed to numeric value for progress bar
        }[key]

        self.doc_frame.refresh_documentation_labels(self.current_file)

        # Check regular labels
        assert self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL].cget("text") == "Blog text"
        assert self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL].cget("text") == "Wiki text"
        assert self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL].cget("text") == "External tool text"

        # Check colors for clickable links
        assert str(self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL].cget("foreground")) == "blue"

        # Check mandatory level progress bar
        assert self.doc_frame.mandatory_level.cget("value") == 75

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.webbrowser_open")
    def test_manual_open_documentation_links(self, mock_webbrowser_open_) -> None:
        """Test manually opening documentation links by clicking on labels."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = [
            ("Blog text", "http://blog.url"),
            ("Wiki text", "http://wiki.url"),
            ("External tool text", "http://external_tool.url"),
            ("Mandatory text", None),
        ]

        self.doc_frame.refresh_documentation_labels(self.current_file)

        # Simulate clicking on the labels
        self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL].event_generate("<Button-1>")
        self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL].event_generate("<Button-1>")
        self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL].event_generate("<Button-1>")

        mock_webbrowser_open_.assert_any_call("http://blog.url")
        mock_webbrowser_open_.assert_any_call("http://wiki.url")
        mock_webbrowser_open_.assert_any_call("http://external_tool.url")

    def test_update_documentation_labels_no_urls(self) -> None:
        """Test updating documentation labels when no URLs are provided."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = [
            ("Blog text", None),
            ("Wiki text", None),
            ("External tool text", None),
            ("0", None),  # Mandatory level
        ]

        self.doc_frame.refresh_documentation_labels(self.current_file)

        # Check regular labels
        assert self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL].cget("text") == "Blog text"
        assert self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL].cget("text") == "Wiki text"
        assert self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL].cget("text") == "External tool text"

        # Check colors for non-clickable text
        assert str(self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL].cget("foreground")) == "black"
        assert str(self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL].cget("foreground")) == "black"
        assert str(self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL].cget("foreground")) == "black"

        # Check mandatory level progress bar
        assert self.doc_frame.mandatory_level.cget("value") == 0

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip")
    def test_tooltip_texts(self, mock_show_tooltip_) -> None:
        """Test the tooltip texts for the documentation labels."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = [
            ("Blog text", "http://blog.url"),
            ("Wiki text", "http://wiki.url"),
            ("External tool text", "http://external_tool.url"),
            ("50", None),
        ]

        self.doc_frame.refresh_documentation_labels(self.current_file)

        assert self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL].cget("text") == "Blog text"
        assert self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL].cget("text") == "Wiki text"
        assert self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL].cget("text") == "External tool text"

        assert str(self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL].cget("foreground")) == "blue"

        mock_show_tooltip_.assert_any_call(self.doc_frame.documentation_labels[self.doc_frame.BLOG_LABEL], "http://blog.url")
        mock_show_tooltip_.assert_any_call(self.doc_frame.documentation_labels[self.doc_frame.WIKI_LABEL], "http://wiki.url")
        mock_show_tooltip_.assert_any_call(
            self.doc_frame.documentation_labels[self.doc_frame.EXTERNAL_TOOL_LABEL], "http://external_tool.url"
        )
        expected_tooltip = f"This configuration step ({self.current_file} intermediate parameter file) is 50% mandatory"
        mock_show_tooltip_.assert_any_call(self.doc_frame.mandatory_level, expected_tooltip)

    def test_refresh_mandatory_level_valid_percentage(self) -> None:
        """Test refresh_mandatory_level with valid percentage."""
        self.doc_frame._refresh_mandatory_level(self.current_file, "75% completion")  # pylint: disable=protected-access
        assert self.doc_frame.mandatory_level.cget("value") == 75

    def test_refresh_mandatory_level_invalid_percentage(self) -> None:
        """Test refresh_mandatory_level with invalid percentage."""
        self.doc_frame._refresh_mandatory_level(self.current_file, "invalid text")  # pylint: disable=protected-access
        assert self.doc_frame.mandatory_level.cget("value") == 0

    def test_refresh_mandatory_level_out_of_range(self) -> None:
        """Test refresh_mandatory_level with percentage out of range."""
        self.doc_frame._refresh_mandatory_level(self.current_file, "101% completion")  # pylint: disable=protected-access
        assert self.doc_frame.mandatory_level.cget("value") == 0

    @pytest.mark.usefixtures("mock_show_tooltip")
    def test_refresh_documentation_label_with_url(self) -> None:
        """Test refresh_documentation_label with valid URL."""
        label_key = self.doc_frame.BLOG_LABEL
        text = "Test text"
        url = "http://test.url"

        self.doc_frame._refresh_documentation_label(label_key, text, url)  # pylint: disable=protected-access

        label = self.doc_frame.documentation_labels[label_key]
        assert label.cget("text") == text
        assert str(label.cget("foreground")) == "blue"
        # Compare cursor string representation instead of object
        assert str(label.cget("cursor")) == "hand2"
        # Check that the font includes "underline" attribute
        font = label.cget("font")
        assert "underline" in font[-1] if isinstance(font, tuple) else font

    @pytest.mark.usefixtures("mock_show_tooltip")
    def test_refresh_documentation_label_without_url(self) -> None:
        """Test refresh_documentation_label without URL."""
        label_key = self.doc_frame.BLOG_LABEL
        text = "Test text"
        url = ""

        self.doc_frame._refresh_documentation_label(label_key, text, url)  # pylint: disable=protected-access

        label = self.doc_frame.documentation_labels[label_key]
        assert label.cget("text") == text
        assert str(label.cget("foreground")) == "black"
        # Compare cursor string representation instead of object
        assert str(label.cget("cursor")) == "arrow"
        # Check that the font doesn't include "underline" attribute
        font = label.cget("font")
        assert "underline" not in font[-1] if isinstance(font, tuple) else font


if __name__ == "__main__":
    unittest.main()
