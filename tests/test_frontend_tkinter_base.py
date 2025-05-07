#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_base_window.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


@pytest.fixture
def tk_setup():
    """Setup and teardown for tkinter tests."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window during tests
    base_window = BaseWindow(root)

    yield root, base_window

    # Teardown
    base_window.root.update_idletasks()
    base_window.root.destroy()
    root.destroy()


def test_initialization(tk_setup):
    """Test that BaseWindow initializes correctly."""
    _, base_window = tk_setup
    assert isinstance(base_window.root, tk.Toplevel)
    assert isinstance(base_window.main_frame, ttk.Frame)


def test_center_window(tk_setup):
    """Test the window centering functionality."""
    root, _ = tk_setup
    child_window = tk.Toplevel(root)
    BaseWindow.center_window(child_window, root)
    assert child_window.winfo_x() >= 0
    assert child_window.winfo_y() >= 0
    child_window.destroy()


def test_create_progress_window(tk_setup):
    """Test creating a progress window."""
    _, base_window = tk_setup
    progress_window = ProgressWindow(base_window.root, title="Progress Test", message="Progress: {}/{}")
    assert progress_window.progress_window.title() == "Progress Test"
    assert progress_window.progress_label.cget("text") == "Progress: 0/0"
    progress_window.destroy()


def test_theme_and_style():
    """Test the theme and style settings."""
    import platform

    style = ttk.Style()
    expected_theme = "vista" if platform.system() == "Windows" else "alt"
    assert style.theme_use() == expected_theme
    expected_font = "TkDefaultFont" if platform.system() == "Windows" else "TkDefaultFont 10 bold"
    assert style.lookup("Bold.TLabel", "font") == expected_font


@patch("PIL.Image.open")
@patch("PIL.ImageTk.PhotoImage")
@patch("tkinter.ttk.Label")
def test_put_image_in_label(mock_label, mock_photo, mock_open, tk_setup):
    """Test creating a label with an image."""
    _, base_window = tk_setup

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
    label = BaseWindow.put_image_in_label(base_window.main_frame, "test_image.png", image_height=50)

    # Verify behavior
    mock_open.assert_called_once_with("test_image.png")
    mock_image.resize.assert_called_once_with((50, 50))  # Based on aspect ratio of 1:1
    mock_photo.assert_called_once_with(mock_image)
    mock_label.assert_called_once()
    assert isinstance(label, MagicMock)


def test_window_title(tk_setup):
    """Test setting window title."""
    _, base_window = tk_setup
    title = "Test Window"
    base_window.root.title(title)
    assert base_window.root.title() == title
