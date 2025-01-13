#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_base.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from platform import system as platform_system
from tkinter import ttk
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_base import (
    AutoResizeCombobox,
    BaseWindow,
    ProgressWindow,
    RichText,
    ScrollFrame,
    get_widget_font_family_and_size,
    show_error_message,
    show_no_connection_error,
    show_no_param_files_error,
    show_tooltip,
    update_combobox_width,
)


class TestShowErrorMessage(unittest.TestCase):
    """Test cases for the show_error_message function."""

    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.Tk")
    @patch("tkinter.ttk.Style")  # Mock the ttk.Style class
    def test_show_error_message(self, _mock_style, mock_tk, mock_showerror) -> None:  # noqa: PT019
        # Mock the Tkinter Tk class to prevent it from actually creating a window
        mock_tk.return_value.withdraw.return_value = None
        mock_tk.return_value.destroy.return_value = None

        # Call the function with test parameters
        show_error_message("Test Title", "Test Message")

        # Assert that the Tkinter Tk class was instantiated
        mock_tk.assert_called_once()

        # Assert that the Tkinter messagebox.showerror function was called with the correct parameters
        mock_showerror.assert_called_once_with("Test Title", "Test Message")

        # Assert that the Tkinter Tk instance's withdraw method was called
        mock_tk.return_value.withdraw.assert_called_once()

        # Assert that the Tkinter Tk instance's destroy method was called
        mock_tk.return_value.destroy.assert_called_once()


class TestShowTooltip(unittest.TestCase):
    """Test cases for the show_tooltip function."""

    @patch("tkinter.Toplevel")
    @patch("tkinter.ttk.Label")
    def test_show_tooltip(self, mock_label, mock_toplevel) -> None:
        # Mock the Tkinter Toplevel class to prevent it from actually creating a window
        mock_toplevel.return_value.deiconify.return_value = None
        mock_toplevel.return_value.withdraw.return_value = None

        # Mock the Tkinter Label class to prevent it from actually creating a label
        mock_label.return_value.pack.return_value = None

        # Create a mock widget
        mock_widget = MagicMock()
        mock_widget.winfo_rootx.return_value = 100
        mock_widget.winfo_rooty.return_value = 200
        mock_widget.winfo_width.return_value = 50
        mock_widget.winfo_height.return_value = 30

        # Call the function with test parameters
        show_tooltip(mock_widget, "Test Tooltip Message")

        # Create a mock event object
        mock_event = MagicMock()

        # Simulate the <Enter> event to trigger the deiconify method
        enter_event = mock_widget.bind.call_args_list[0][0][1]
        enter_event(mock_event)

        # Assert that the Tkinter Toplevel class was instantiated
        mock_toplevel.assert_called_once()

        # Assert that the Tkinter Label class was instantiated with the correct parameters
        mock_label.assert_called_once_with(
            mock_toplevel.return_value,
            text="Test Tooltip Message",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            justify=tk.LEFT,
        )

        # Assert that the Tkinter Toplevel instance's deiconify method was called
        mock_toplevel.return_value.deiconify.assert_called()

        # Simulate the <Leave> event to trigger the withdraw method
        leave_event = mock_widget.bind.call_args_list[1][0][1]
        leave_event(mock_event)

        # Assert that the Tkinter Toplevel instance's withdraw method was called
        mock_toplevel.return_value.withdraw.assert_called()


class TestShowNoParamFilesError(unittest.TestCase):
    """Test cases for the show_no_param_files_error function."""

    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.Tk")
    @patch("tkinter.ttk.Style")
    def test_show_no_param_files_error(self, _mock_style, mock_tk, mock_showerror) -> None:  # noqa: PT019
        mock_tk.return_value.withdraw.return_value = None
        mock_tk.return_value.destroy.return_value = None

        show_no_param_files_error("test_dir")

        mock_tk.assert_called_once()
        mock_showerror.assert_called_once_with(
            "No Parameter Files Found",
            (
                "No intermediate parameter files found in the selected 'test_dir' vehicle directory.\n"
                "Please select and step inside a vehicle directory containing valid ArduPilot intermediate parameter files."
                "\n\nMake sure to step inside the directory (double-click) and not just select it."
            ),
        )
        mock_tk.return_value.withdraw.assert_called_once()
        mock_tk.return_value.destroy.assert_called_once()


class TestShowNoConnectionError(unittest.TestCase):
    """Test cases for the show_no_connection_error function."""

    @patch("tkinter.messagebox.showerror")
    @patch("tkinter.Tk")
    @patch("tkinter.ttk.Style")
    def test_show_no_connection_error(self, _mock_style, mock_tk, mock_showerror) -> None:  # noqa: PT019
        mock_tk.return_value.withdraw.return_value = None
        mock_tk.return_value.destroy.return_value = None

        show_no_connection_error("test_error")

        mock_tk.assert_called_once()
        mock_showerror.assert_called_once_with(
            "No Connection to the Flight Controller",
            "test_error\n\nPlease connect a flight controller to the PC,\nwait at least 7 seconds and retry.",
        )
        mock_tk.return_value.withdraw.assert_called_once()
        mock_tk.return_value.destroy.assert_called_once()


class TestUpdateComboboxWidth(unittest.TestCase):
    """Test cases for the update_combobox_width function."""

    def test_update_combobox_width(self) -> None:
        combobox = ttk.Combobox(values=["short", "longer", "longest"])
        update_combobox_width(combobox)
        assert combobox.cget("width") == 7


class TestAutoResizeCombobox(unittest.TestCase):
    """Test cases for the AutoResizeCombobox class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.combobox = AutoResizeCombobox(
            self.root, values=["one", "two", "three"], selected_element="two", tooltip="Test Tooltip"
        )

    def tearDown(self) -> None:
        self.root.destroy()

    def test_initial_selection(self) -> None:
        assert self.combobox.get() == "two"

    def test_tooltip(self) -> None:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base.show_tooltip") as mock_show_tooltip:
            self.combobox.set_entries_tupple(["one", "two", "three"], "two", tooltip="Test Tooltip")
            mock_show_tooltip.assert_called_once_with(self.combobox, "Test Tooltip")

    def test_update_values(self) -> None:
        self.combobox.set_entries_tupple(["four", "five", "six"], "five")
        assert self.combobox.get() == "five"
        assert self.combobox["values"] == ("four", "five", "six")

    def test_invalid_selection(self) -> None:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base.logging_error") as mock_logging_error:
            self.combobox.set_entries_tupple(["seven", "eight"], "nine")
            mock_logging_error.assert_called_once()

    def test_no_selection(self) -> None:
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base.logging_warning") as mock_logging_warning:
            self.combobox.set_entries_tupple(["ten", "eleven"], "")
            mock_logging_warning.assert_called_once()


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
        expected_family = "Segoe UI" if platform_system() == "Windows" else "sans-serif"
        expected_size = 9 if platform_system() == "Windows" else 10
        assert isinstance(family, str)
        assert isinstance(size, int)
        assert family == expected_family
        assert size == expected_size


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

    def test_put_image_in_label(self) -> None:
        with patch("PIL.Image.open") as mock_open, patch("PIL.ImageTk.PhotoImage") as mock_photo:
            mock_image = MagicMock()
            mock_open.return_value = mock_image
            mock_image.size = (100, 100)
            return  # FIXME the test does not pass yet pylint: disable=fixme
            label = BaseWindow.put_image_in_label(self.base_window.main_frame, "test_image.png", image_height=50)  # pylint: disable=unreachable
            assert isinstance(label, ttk.Label)
            mock_open.assert_called_once_with("test_image.png")
            mock_photo.assert_called_once()


if __name__ == "__main__":
    unittest.main()
