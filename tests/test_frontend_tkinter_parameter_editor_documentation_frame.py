#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_parameter_editor_documentation_frame.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

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

        expected_labels = ["Forum Blog:", "Wiki:", "External tool:", "Mandatory:"]
        for label in expected_labels:
            assert label in self.doc_frame.documentation_labels

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

        self.doc_frame.update_documentation_labels(self.current_file)

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
                self.doc_frame.documentation_frame, "Why: Why text\nWhy now: Why now text"
            )

    @pytest.mark.usefixtures("mock_webbrowser_open", "mock_show_tooltip")
    def test_update_documentation_labels(self) -> None:
        """Test the update_documentation_labels method."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = lambda _file, key: {
            "blog": ("Blog text", "http://blog.url"),
            "wiki": ("Wiki text", "http://wiki.url"),
            "external_tool": ("External tool text", "http://external_tool.url"),
            "mandatory": ("Mandatory text", None),
        }[key]

        self.doc_frame.update_documentation_labels(self.current_file)

        assert self.doc_frame.documentation_labels["Forum Blog:"].cget("text") == "Blog text"
        assert self.doc_frame.documentation_labels["Wiki:"].cget("text") == "Wiki text"
        assert self.doc_frame.documentation_labels["External tool:"].cget("text") == "External tool text"
        assert self.doc_frame.documentation_labels["Mandatory:"].cget("text") == "Mandatory text"

        assert str(self.doc_frame.documentation_labels["Forum Blog:"].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels["Wiki:"].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels["External tool:"].cget("foreground")) == "blue"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.webbrowser_open")
    def test_manual_open_documentation_links(self, mock_webbrowser_open_) -> None:
        """Test manually opening documentation links by clicking on labels."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = [
            ("Blog text", "http://blog.url"),
            ("Wiki text", "http://wiki.url"),
            ("External tool text", "http://external_tool.url"),
            ("Mandatory text", None),
        ]

        self.doc_frame.update_documentation_labels(self.current_file)

        # Simulate clicking on the labels
        self.doc_frame.documentation_labels["Forum Blog:"].event_generate("<Button-1>")
        self.doc_frame.documentation_labels["Wiki:"].event_generate("<Button-1>")
        self.doc_frame.documentation_labels["External tool:"].event_generate("<Button-1>")

        mock_webbrowser_open_.assert_any_call("http://blog.url")
        mock_webbrowser_open_.assert_any_call("http://wiki.url")
        mock_webbrowser_open_.assert_any_call("http://external_tool.url")

    def test_update_documentation_labels_no_urls(self) -> None:
        """Test updating documentation labels when no URLs are provided."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = [
            ("Blog text", None),
            ("Wiki text", None),
            ("External tool text", None),
            ("Mandatory text", None),
        ]

        self.doc_frame.update_documentation_labels(self.current_file)

        assert self.doc_frame.documentation_labels["Forum Blog:"].cget("text") == "Blog text"
        assert self.doc_frame.documentation_labels["Wiki:"].cget("text") == "Wiki text"
        assert self.doc_frame.documentation_labels["External tool:"].cget("text") == "External tool text"
        assert self.doc_frame.documentation_labels["Mandatory:"].cget("text") == "Mandatory text"

        assert str(self.doc_frame.documentation_labels["Forum Blog:"].cget("foreground")) == "black"
        assert str(self.doc_frame.documentation_labels["Wiki:"].cget("foreground")) == "black"
        assert str(self.doc_frame.documentation_labels["External tool:"].cget("foreground")) == "black"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip")
    def test_tooltip_texts(self, mock_show_tooltip_) -> None:
        """Test the tooltip texts for the documentation labels."""
        self.local_filesystem.get_documentation_text_and_url.side_effect = [
            ("Blog text", "http://blog.url"),
            ("Wiki text", "http://wiki.url"),
            ("External tool text", "http://external_tool.url"),
            ("Mandatory text", None),
        ]

        self.doc_frame.update_documentation_labels(self.current_file)

        assert self.doc_frame.documentation_labels["Forum Blog:"].cget("text") == "Blog text"
        assert self.doc_frame.documentation_labels["Wiki:"].cget("text") == "Wiki text"
        assert self.doc_frame.documentation_labels["External tool:"].cget("text") == "External tool text"
        assert self.doc_frame.documentation_labels["Mandatory:"].cget("text") == "Mandatory text"

        assert str(self.doc_frame.documentation_labels["Forum Blog:"].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels["Wiki:"].cget("foreground")) == "blue"
        assert str(self.doc_frame.documentation_labels["External tool:"].cget("foreground")) == "blue"

        mock_show_tooltip_.assert_any_call(self.doc_frame.documentation_labels["Forum Blog:"], "http://blog.url")
        mock_show_tooltip_.assert_any_call(self.doc_frame.documentation_labels["Wiki:"], "http://wiki.url")
        mock_show_tooltip_.assert_any_call(self.doc_frame.documentation_labels["External tool:"], "http://external_tool.url")


if __name__ == "__main__":
    unittest.main()
