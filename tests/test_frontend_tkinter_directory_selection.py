#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_directory_selection.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_base import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import (
    DirectoryNameWidgets,
    DirectorySelectionWidgets,
    VehicleDirectorySelectionWidgets,
)


class TestDirectorySelectionWidgets(unittest.TestCase):
    """Test cases for the DirectorySelectionWidgets class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.parent = BaseWindow(self.root)
        self.parent_frame = ttk.Frame(self.root)
        self.initialdir = "/test/dir"
        self.widget = DirectorySelectionWidgets(
            parent=self.parent,
            parent_frame=self.parent_frame,
            initialdir=self.initialdir,
            label_text="Test Directory",
            autoresize_width=True,
            dir_tooltip="Directory tooltip",
            button_tooltip="Button tooltip",
            is_template_selection=False,
        )

    def tearDown(self) -> None:
        self.root.destroy()

    def test_initialization(self) -> None:
        """Test that widgets are properly initialized."""
        assert self.widget.directory == self.initialdir
        assert isinstance(self.widget.container_frame, ttk.Frame)
        assert isinstance(self.widget.directory_entry, tk.Entry)
        assert self.widget.directory_entry.cget("state") == "readonly"

    def test_directory_selection_with_button(self) -> None:
        """Test directory selection with button."""
        with patch("tkinter.filedialog.askdirectory", return_value="/new/dir") as mock_dialog:
            result = self.widget.on_select_directory()
            mock_dialog.assert_called_once()
            assert result
            assert self.widget.directory == "/new/dir"
            assert self.widget.directory_entry.get() == "/new/dir"

    def test_directory_selection_cancelled(self) -> None:
        """Test when directory selection is cancelled."""
        with patch("tkinter.filedialog.askdirectory", return_value="") as mock_dialog:
            result = self.widget.on_select_directory()
            mock_dialog.assert_called_once()
            assert not result
            assert self.widget.directory == self.initialdir

    def test_without_button(self) -> None:
        """Test widget creation without button."""
        widget = DirectorySelectionWidgets(
            parent=self.parent,
            parent_frame=self.parent_frame,
            initialdir=self.initialdir,
            label_text="Test Directory",
            autoresize_width=True,
            dir_tooltip="Directory tooltip",
            button_tooltip="",  # Empty tooltip means no button
            is_template_selection=False,
        )
        # No button should be present in the widget's children
        buttons = [child for child in widget.container_frame.winfo_children() if isinstance(child, ttk.Button)]
        assert len(buttons) == 0

    def test_get_selected_directory(self) -> None:
        """Test getting the selected directory."""
        assert self.widget.get_selected_directory() == self.initialdir
        self.widget.directory = "/another/dir"
        assert self.widget.get_selected_directory() == "/another/dir"


class TestDirectoryNameWidgets(unittest.TestCase):
    """Test cases for the DirectoryNameWidgets class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window during tests
        self.master = ttk.Labelframe(self.root)
        self.initial_dir = "test_dir"
        self.label_text = "Test Label"
        self.dir_tooltip = "Test Tooltip"
        self.widget = DirectoryNameWidgets(
            master=self.master,
            initial_dir=self.initial_dir,
            label_text=self.label_text,
            dir_tooltip=self.dir_tooltip,
        )

    def tearDown(self) -> None:
        self.root.destroy()

    def test_initialization(self) -> None:
        """Test that widgets are properly initialized."""
        # Check if the container frame was created
        assert isinstance(self.widget.container_frame, ttk.Frame)

        # Check if the frame contains the expected widgets
        children = self.widget.container_frame.winfo_children()
        assert len(children) == 2  # Should have a label and an entry
        assert isinstance(children[0], ttk.Label)  # First child should be a label
        assert isinstance(children[1], ttk.Entry)  # Second child should be an entry

        # Check if the label has the correct text
        assert children[0].cget("text") == self.label_text

        # Check if the entry has the correct initial value
        assert self.widget.dir_var.get() == self.initial_dir

    def test_get_selected_directory(self) -> None:
        """Test getting the selected directory name."""
        # Test initial value
        assert self.widget.get_selected_directory() == self.initial_dir

        # Test after changing the value
        new_dir = "new_test_dir"
        self.widget.dir_var.set(new_dir)
        assert self.widget.get_selected_directory() == new_dir

    def test_entry_width(self) -> None:
        """Test that the entry width is set correctly based on initial directory length."""
        entry = self.widget.container_frame.winfo_children()[1]
        assert isinstance(entry, ttk.Entry)
        expected_width = max(4, len(self.initial_dir))
        assert int(entry.cget("width")) == expected_width


class TestVehicleDirectorySelectionWidgets(unittest.TestCase):
    """Test cases for the VehicleDirectorySelectionWidgets class."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.parent = BaseWindow(self.root)
        self.parent_frame = ttk.Frame(self.root)
        self.local_filesystem = MagicMock()
        self.initial_dir = "/test/vehicle/dir"
        self.widget = VehicleDirectorySelectionWidgets(
            parent=self.parent,
            parent_frame=self.parent_frame,
            local_filesystem=self.local_filesystem,
            initial_dir=self.initial_dir,
            destroy_parent_on_open=True,
        )

    def tearDown(self) -> None:
        self.root.destroy()

    def test_initialization(self) -> None:
        """Test that widgets are properly initialized."""
        assert isinstance(self.widget.container_frame, ttk.Frame)
        assert isinstance(self.widget.directory_entry, tk.Entry)
        assert self.widget.directory == self.initial_dir
        assert self.widget.directory_entry.cget("state") == "readonly"

    @patch("tkinter.filedialog.askdirectory")
    @patch("tkinter.messagebox.showerror")
    def test_directory_selection_template_not_allowed(self, mock_error, mock_askdir) -> None:
        """Test selecting a directory in templates when not allowed."""
        mock_askdir.return_value = "/vehicle_templates/some_dir"
        self.local_filesystem.allow_editing_template_files = False
        result = self.widget.on_select_directory()
        assert not result
        mock_error.assert_called_once()

    @patch("tkinter.filedialog.askdirectory")
    @patch("tkinter.messagebox.showerror")
    def test_directory_selection_invalid_vehicle_dir(self, mock_error, mock_askdir) -> None:
        """Test selecting an invalid vehicle directory."""
        mock_askdir.return_value = "/some/dir"
        self.local_filesystem.vehicle_configuration_files_exist.return_value = False
        result = self.widget.on_select_directory()
        assert not result
        mock_error.assert_called_once()

    @patch("tkinter.filedialog.askdirectory")
    def test_directory_selection_success(self, mock_askdir) -> None:
        """Test successful directory selection."""
        mock_askdir.return_value = "/valid/vehicle/dir"
        self.local_filesystem.vehicle_configuration_files_exist.return_value = True
        self.local_filesystem.file_parameters = {"file1.param": {}}

        result = self.widget.on_select_directory()

        assert result
        assert self.widget.directory == "/valid/vehicle/dir"
        self.local_filesystem.re_init.assert_called_once_with("/valid/vehicle/dir", self.local_filesystem.vehicle_type)

    @patch("tkinter.filedialog.askdirectory")
    def test_directory_selection_cancelled(self, mock_askdir) -> None:
        """Test cancelling directory selection."""
        mock_askdir.return_value = ""
        result = self.widget.on_select_directory()
        assert not result
        assert self.widget.directory == self.initial_dir


if __name__ == "__main__":
    unittest.main()
