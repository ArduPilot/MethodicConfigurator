#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_progress_window.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest

from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


class TestProgressWindow(unittest.TestCase):
    """Test cases for the ProgressWindow class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.progress_window = ProgressWindow(
            self.root, title="Test Progress", message="Progress: {}/{}", width=300, height=80
        )

    def tearDown(self) -> None:
        self.progress_window.destroy()
        self.root.destroy()

    def test_initialization(self) -> None:
        assert self.progress_window.progress_window.title() == "Test Progress"
        assert self.progress_window.progress_label.cget("text") == "Progress: 0/0"

    def test_update_progress_bar(self) -> None:
        self.progress_window.update_progress_bar(50, 100)
        assert self.progress_window.progress_bar["value"] == 50
        assert self.progress_window.progress_bar["maximum"] == 100
        assert self.progress_window.progress_label.cget("text") == "Progress: 50/100"

    def test_update_progress_bar_300_pct(self) -> None:
        self.progress_window.update_progress_bar_300_pct(150)
        assert self.progress_window.progress_bar["value"] == 50
        assert self.progress_window.progress_bar["maximum"] == 100
        assert self.progress_window.progress_label.cget("text") == "Please be patient, 50.0% of 100% complete"

    def test_destroy(self) -> None:
        self.progress_window.destroy()
        # Check if the progress window has been destroyed
        assert not self.progress_window.progress_window.winfo_exists()

    def test_update_progress_bar_exceeding_max(self) -> None:
        """Test updating progress bar with value exceeding maximum."""
        self.progress_window.update_progress_bar(150, 100)
        assert self.progress_window.progress_bar["value"] == 150
        assert self.progress_window.progress_bar["maximum"] == 100


if __name__ == "__main__":
    unittest.main()
