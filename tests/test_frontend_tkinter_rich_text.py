#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_rich_text.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from platform import system as platform_system
from tkinter import ttk

from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText, get_widget_font_family_and_size


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
        expected_family = ["Segoe UI"] if platform_system() == "Windows" else ["Helvetica", "sans-serif"]
        expected_size = [9] if platform_system() == "Windows" else [-12, 10]
        assert isinstance(family, str)
        assert isinstance(size, int)
        assert family in expected_family
        assert size in expected_size


if __name__ == "__main__":
    unittest.main()
