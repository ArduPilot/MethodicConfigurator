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

# pylint: disable=protected-access


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
        # Test that DPI scaling factor is initialized
        assert hasattr(self.base_window, "dpi_scaling_factor")
        assert isinstance(self.base_window.dpi_scaling_factor, float)
        assert self.base_window.dpi_scaling_factor > 0.0

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
        # The font size should be scaled by DPI scaling factor
        expected_font_size = int(10 * self.base_window.dpi_scaling_factor)
        assert style.lookup("Bold.TLabel", "font") == f"TkDefaultFont {expected_font_size} bold"

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

    def test_dpi_scaling_factor_method_exists(self) -> None:
        """Test that the DPI scaling factor method exists and returns a reasonable value."""
        scaling_factor = self.base_window._get_dpi_scaling_factor()
        assert isinstance(scaling_factor, float)
        assert scaling_factor > 0.0
        # Typically DPI scaling should be between 0.5 and 4.0 in most realistic scenarios
        assert 0.5 <= scaling_factor <= 4.0

    def test_dpi_scaling_factor_integration(self) -> None:
        """Test that DPI scaling is properly integrated into BaseWindow initialization."""
        # Test that the dpi_scaling_factor attribute exists and is set properly
        assert hasattr(self.base_window, "dpi_scaling_factor")
        assert isinstance(self.base_window.dpi_scaling_factor, float)
        assert self.base_window.dpi_scaling_factor > 0.0

    def test_dpi_scaling_factor_fallback_on_error(self) -> None:
        """Test DPI scaling factor fallback when detection fails."""
        # Mock TclError to simulate detection failure
        with patch.object(self.base_window.root, "winfo_fpixels", side_effect=tk.TclError):
            scaling_factor = self.base_window._get_dpi_scaling_factor()
            assert scaling_factor == 1.0

        # Mock AttributeError to simulate detection failure
        with patch.object(self.base_window.root, "winfo_fpixels", side_effect=AttributeError):
            scaling_factor = self.base_window._get_dpi_scaling_factor()
            assert scaling_factor == 1.0


if __name__ == "__main__":
    unittest.main()
