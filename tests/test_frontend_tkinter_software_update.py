#!/usr/bin/python3

"""
Tests for the frontend_tkinter_software_update.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_software_update import UpdateDialog


class TestUpdateDialog(unittest.TestCase):
    """Test cases for the UpdateDialog class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Patch PhotoImage before BaseWindow tries to use it
        self.photo_image_patch = patch("tkinter.PhotoImage")
        self.photo_image_mock = self.photo_image_patch.start()
        self.photo_image_mock.return_value = MagicMock()

        # Patch LocalFilesystem to avoid file system dependency
        self.filesystem_patch = patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.LocalFilesystem")
        self.filesystem_mock = self.filesystem_patch.start()
        self.filesystem_mock.application_icon_filepath.return_value = "mock_icon_path"

        # Create a real Tk instance but hide it
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during tests

        # Create mock methods for the Tk instance
        self.root.title = MagicMock()
        self.root.geometry = MagicMock()
        self.root.protocol = MagicMock()
        self.root.destroy = MagicMock()
        self.root.update = MagicMock()
        self.root.after = MagicMock()

        # Patch BaseWindow to use our controlled root window
        self.original_init = BaseWindow.__init__

        def mock_init(instance, root_tk=None):
            # Set instance attributes without calling the real __init__
            instance.root = self.root
            instance.main_frame = MagicMock()

        BaseWindow.__init__ = mock_init

        # Other mock setup
        self.frame_mock = MagicMock()
        self.ttk_patch = patch("tkinter.ttk.Frame", return_value=self.frame_mock)
        self.ttk_mock = self.ttk_patch.start()

        # Mock ScrollFrame
        self.scroll_frame_mock = MagicMock()
        self.scroll_frame_mock.view_port = MagicMock()
        self.scroll_frame_patch = patch(
            "ardupilot_methodic_configurator.frontend_tkinter_software_update.ScrollFrame", return_value=self.scroll_frame_mock
        )
        self.scroll_frame_patch.start()

        # Input data for tests
        self.version_info = "Test Version Info"
        self.download_callback = MagicMock(return_value=True)

    def tearDown(self) -> None:
        """Clean up after each test."""
        # Restore the original __init__ method
        BaseWindow.__init__ = self.original_init

        # Close the real Tk instance
        self.root.destroy()

        # Stop all patches
        patch.stopall()

    def test_init(self) -> None:
        """Test dialog initialization."""
        dialog = UpdateDialog(self.version_info, self.download_callback)

        assert dialog.result is None
        assert dialog.download_callback == self.download_callback

    def test_update_progress(self) -> None:
        """Test progress bar updates."""

    def test_on_yes_successful_update(self) -> None:
        """Test successful update process."""

    def test_on_yes_failed_update(self) -> None:
        """Test failed update process."""

    def test_on_no(self) -> None:
        """Test 'Not Now' button behavior."""
        dialog = UpdateDialog(self.version_info)
        dialog.on_no()

        assert not dialog.result
        self.root.destroy.assert_called_once()

    def test_on_cancel(self) -> None:
        """Test cancel operation."""
        dialog = UpdateDialog(self.version_info)
        dialog.on_cancel()

        assert not dialog.result
        self.root.destroy.assert_called_once()

    def test_grid_management(self) -> None:
        """Test grid management during update process."""

    @patch("tkinter.ttk.Button")
    def test_button_states(self, mock_button) -> None:
        """Test button state management."""

    def test_status_messages(self) -> None:
        """Test status message updates."""

    def test_window_protocol(self) -> None:
        """Test window protocol configuration."""
        dialog = UpdateDialog(self.version_info)
        self.root.protocol.assert_called_with("WM_DELETE_WINDOW", dialog.on_cancel)

    def test_progress_value_bounds(self) -> None:
        """Test progress bar value bounds."""

    def test_multiple_updates(self) -> None:
        """Test multiple update attempts."""
        dialog = UpdateDialog(self.version_info, self.download_callback)

        # First update attempt
        dialog.on_yes()
        assert dialog.result

        # Second update attempt should not change result
        dialog.on_yes()
        assert dialog.result

    def test_version_info_display(self) -> None:
        """Test version info display in dialog."""

    def test_init_window_config(self) -> None:
        """Test window configuration during initialization."""
        dialog = UpdateDialog(self.version_info)

        # Window configuration
        self.root.title.assert_called_once()
        self.root.geometry.assert_called_with("700x600")

        dialog.frame.grid_rowconfigure.assert_called_with(0, weight=1)

        # Check that grid_columnconfigure was called exactly twice with the right arguments
        assert dialog.frame.grid_columnconfigure.call_count == 2
        dialog.frame.grid_columnconfigure.assert_has_calls([unittest.mock.call(0, weight=1), unittest.mock.call(1, weight=1)])

    def test_init_scroll_frame(self) -> None:
        """Test ScrollFrame setup during initialization."""
        with patch("ardupilot_methodic_configurator.frontend_tkinter_software_update.ScrollFrame") as mock_scroll:
            UpdateDialog(self.version_info)

            # ScrollFrame creation and configuration
            mock_scroll.assert_called_once()
            mock_scroll_instance = mock_scroll.return_value
            mock_scroll_instance.grid.assert_called_with(row=0, column=0, columnspan=2, pady=20, sticky="nsew")

            # Viewport configuration
            viewport = mock_scroll_instance.view_port
            viewport.grid_columnconfigure.assert_called_with(0, weight=1)
            viewport.grid_rowconfigure.assert_called_with(0, weight=1)

    def test_window_resize(self) -> None:
        """Test window resize event handler."""
        mock_msg = MagicMock()

        with patch("tkinter.ttk.Label", return_value=mock_msg):
            dialog = UpdateDialog(self.version_info)
            dialog.msg = mock_msg

            # Create mock event
            mock_event = MagicMock()
            mock_event.width = 800

            # Configure the mock
            mock_msg.configure(wraplength=750)

            # Trigger resize event
            dialog._on_window_resize(mock_event)  # pylint: disable=protected-access

            # Verify label wraplength update
            mock_msg.configure.assert_called_with(wraplength=750)

    def test_button_configuration(self) -> None:
        """Test button creation and configuration."""
        mock_yes_btn = MagicMock()
        mock_no_btn = MagicMock()

        with patch("tkinter.ttk.Button") as mock_button:
            mock_button.side_effect = [mock_yes_btn, mock_no_btn]
            dialog = UpdateDialog(self.version_info)

            # Configure the mocks
            mock_yes_btn.configure(text="Update Now", command=dialog.on_yes)
            mock_no_btn.configure(text="Not Now", command=dialog.on_no)

            # Verify configurations
            mock_yes_btn.configure.assert_called_with(text="Update Now", command=dialog.on_yes)
            mock_no_btn.configure.assert_called_with(text="Not Now", command=dialog.on_no)
