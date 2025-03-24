#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_base_window.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


class TestBaseWindow(unittest.TestCase):
    """Test cases for the BaseWindow class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.base_window = BaseWindow(self.root)

    def tearDown(self) -> None:
        self.base_window.root.update_idletasks()
        self.base_window.root.destroy()
        self.root.destroy()

    def test_initialization(self) -> None:
        assert isinstance(self.base_window.root, tk.Toplevel)
        assert isinstance(self.base_window.main_frame, ttk.Frame)

    def test_center_window(self) -> None:
        child_window = tk.Toplevel(self.root)
        BaseWindow.center_window(child_window, self.root)
        assert child_window.winfo_x() >= 0
        assert child_window.winfo_y() >= 0
        child_window.destroy()

    def test_create_progress_window(self) -> None:
        progress_window = ProgressWindow(self.base_window.root, title="Progress Test", message="Progress: {}/{}")
        assert progress_window.progress_window.title() == "Progress Test"
        assert progress_window.progress_label.cget("text") == "Progress: 0/0"
        progress_window.destroy()

    def test_theme_and_style(self) -> None:
        style = ttk.Style()
        assert style.theme_use() == "alt"
        assert style.lookup("Bold.TLabel", "font") == "TkDefaultFont 10 bold"

    @patch("PIL.Image.open")
    @patch("PIL.ImageTk.PhotoImage")
    @patch("tkinter.ttk.Label")
    def test_put_image_in_label(self, mock_label, mock_photo, mock_open) -> None:
        """Test creating a label with an image."""
        # Set up image mock
        mock_image = MagicMock()
        mock_image.size = (100, 100)
        mock_image.resize = MagicMock(return_value=mock_image)
        mock_open.return_value = mock_image

        # Set up PhotoImage mock
        mock_photo_instance = MagicMock()
        mock_photo_instance._PhotoImage__photo = "photo1"  # pylint: disable=protected-access
        mock_photo.return_value = mock_photo_instance

        # Set up Label mock
        mock_label_instance = MagicMock()
        mock_label.return_value = mock_label_instance

        # Test the method
        label = BaseWindow.put_image_in_label(self.base_window.main_frame, "test_image.png", image_height=50)

        # Verify behavior
        mock_open.assert_called_once_with("test_image.png")
        mock_image.resize.assert_called_once_with((50, 50))  # Based on aspect ratio of 1:1
        mock_photo.assert_called_once_with(mock_image)
        mock_label.assert_called_once()
        assert isinstance(label, MagicMock)

    def test_window_title(self) -> None:
        """Test setting window title."""
        title = "Test Window"
        self.base_window.root.title(title)
        assert self.base_window.root.title() == title


if __name__ == "__main__":
    unittest.main()
