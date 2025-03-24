#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_scroll_frame.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from platform import system as platform_system
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame


class TestScrollFrame(unittest.TestCase):
    """Test cases for the ScrollFrame class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.scroll_frame = ScrollFrame(self.root)

    def tearDown(self) -> None:
        self.root.destroy()

    def test_initialization(self) -> None:
        assert isinstance(self.scroll_frame.canvas, tk.Canvas)
        assert isinstance(self.scroll_frame.view_port, ttk.Frame)
        assert isinstance(self.scroll_frame.vsb, tk.Scrollbar)

    def test_on_frame_configure(self) -> None:
        with patch.object(self.scroll_frame.canvas, "configure") as mock_configure:
            self.scroll_frame.on_frame_configure(None)
            mock_configure.assert_called_once_with(scrollregion=self.scroll_frame.canvas.bbox("all"))

    def test_on_canvas_configure(self) -> None:
        event = MagicMock()
        event.width = 500
        with patch.object(self.scroll_frame.canvas, "itemconfig") as mock_itemconfig:
            self.scroll_frame.on_canvas_configure(event)
            mock_itemconfig.assert_called_once_with(self.scroll_frame.canvas_window, width=500)

    def test_on_mouse_wheel(self) -> None:
        event = MagicMock()
        event.delta = -120
        event.num = 4
        with patch.object(self.scroll_frame.canvas, "yview_scroll") as mock_yview_scroll:
            self.scroll_frame.on_mouse_wheel(event)
            mock_yview_scroll.assert_called()

    def test_on_enter(self) -> None:
        with patch.object(self.scroll_frame.canvas, "bind_all") as mock_bind_all:
            self.scroll_frame.on_enter(None)
            mock_bind_all.assert_called()

    def test_on_leave(self) -> None:
        with patch.object(self.scroll_frame.canvas, "unbind_all") as mock_unbind_all:
            self.scroll_frame.on_leave(None)
            mock_unbind_all.assert_called()

    def test_mouse_wheel_scroll_windows(self) -> None:
        """Test mouse wheel scrolling on Windows."""
        if platform_system() != "Windows":
            pytest.skip("Test only applicable on Windows")
        with patch("platform.system", return_value="Windows"):
            event = MagicMock()
            event.delta = 120
            with patch.object(self.scroll_frame.canvas, "yview_scroll") as mock_yview_scroll:
                self.scroll_frame.on_mouse_wheel(event)
                mock_yview_scroll.assert_called_with(-1, "units")

    def test_mouse_wheel_scroll_linux(self) -> None:
        """Test mouse wheel scrolling on Linux."""
        if platform_system() != "Linux":
            pytest.skip("Test only applicable on Linux")
        with patch("platform.system", return_value="Linux"):
            event = MagicMock()
            event.num = 4  # Scroll up
            # Mock canvas methods needed for scroll test
            self.scroll_frame.canvas.bbox = MagicMock(return_value=(0, 0, 100, 1000))
            self.scroll_frame.canvas.winfo_height = MagicMock(return_value=100)

            with patch.object(self.scroll_frame.canvas, "yview_scroll") as mock_yview_scroll:
                self.scroll_frame.on_mouse_wheel(event)
                mock_yview_scroll.assert_called_once_with(-1, "units")  # Linux scroll direction is inverted


if __name__ == "__main__":
    unittest.main()
