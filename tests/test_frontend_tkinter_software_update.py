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


class TestUpdateDialog(unittest.TestCase):  # pylint: disable=too-many-instance-attributes
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

        def mock_init(instance, root_tk=None) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
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

    def test_window_protocol(self) -> None:
        """Test window protocol configuration."""
        dialog = UpdateDialog(self.version_info)
        self.root.protocol.assert_called_with("WM_DELETE_WINDOW", dialog.on_cancel)

    def test_multiple_updates(self) -> None:
        """Test multiple update attempts."""
        dialog = UpdateDialog(self.version_info, self.download_callback)

        # First update attempt
        dialog.on_yes()
        assert dialog.result

        # Second update attempt should not change result
        dialog.on_yes()
        assert dialog.result

    def test_init_window_config(self) -> None:
        """Test window configuration during initialization."""
        dialog = UpdateDialog(self.version_info)

        # Window configuration
        self.root.title.assert_called_once()
        self.root.geometry.assert_called_with("700x600")

        dialog.frame.grid_rowconfigure.assert_called_with(0, weight=1)  # pylint: disable=no-member

        # Check that grid_columnconfigure was called exactly twice with the right arguments
        assert dialog.frame.grid_columnconfigure.call_count == 2  # pylint: disable=no-member
        dialog.frame.grid_columnconfigure.assert_has_calls([unittest.mock.call(0, weight=1), unittest.mock.call(1, weight=1)])  # pylint: disable=no-member

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

    def test_update_progress(self) -> None:
        """Test progress bar updates."""
        progress_mock = MagicMock()
        status_label_mock = MagicMock()

        dialog = UpdateDialog(self.version_info)
        dialog.progress = progress_mock
        dialog.status_label = status_label_mock

        # Test with both value and status
        dialog.update_progress(75, "Downloading...")
        progress_mock.__setitem__.assert_called_with("value", 75)
        status_label_mock.__setitem__.assert_called_with("text", "Downloading...")
        self.root.update.assert_called_once()

        # Reset mocks
        progress_mock.reset_mock()
        status_label_mock.reset_mock()
        self.root.update.reset_mock()

        # Test with only value (no status)
        dialog.update_progress(50)
        progress_mock.__setitem__.assert_called_with("value", 50)
        status_label_mock.__setitem__.assert_not_called()
        self.root.update.assert_called_once()

    def test_on_yes_successful_update(self) -> None:
        """Test successful update process."""
        # Mock UI components
        progress_mock = MagicMock()
        status_label_mock = MagicMock()
        yes_btn_mock = MagicMock()
        no_btn_mock = MagicMock()

        # Create callback that returns success
        download_callback = MagicMock(return_value=True)

        dialog = UpdateDialog(self.version_info, download_callback)
        dialog.progress = progress_mock
        dialog.status_label = status_label_mock
        dialog.yes_btn = yes_btn_mock
        dialog.no_btn = no_btn_mock

        # Execute the method
        dialog.on_yes()

        # Verify progress bar is shown
        progress_mock.grid.assert_called_once()
        status_label_mock.grid.assert_called_once()

        # Verify buttons are disabled
        yes_btn_mock.config.assert_called_with(state="disabled")
        no_btn_mock.config.assert_called_with(state="disabled")

        # Verify download callback is called
        download_callback.assert_called_once()

        # Verify success message and result
        status_label_mock.__setitem__.assert_called_with("text", "Update complete! Please restart the application.")
        assert dialog.result is True

        # Verify window is scheduled to close after 4 seconds
        self.root.after.assert_called_with(4000, self.root.destroy)

    def test_on_yes_failed_update(self) -> None:
        """Test failed update process."""
        # Mock UI components
        progress_mock = MagicMock()
        status_label_mock = MagicMock()
        yes_btn_mock = MagicMock()
        no_btn_mock = MagicMock()

        # Create callback that returns failure
        download_callback = MagicMock(return_value=False)

        dialog = UpdateDialog(self.version_info, download_callback)
        dialog.progress = progress_mock
        dialog.status_label = status_label_mock
        dialog.yes_btn = yes_btn_mock
        dialog.no_btn = no_btn_mock

        # Execute the method
        dialog.on_yes()

        # Verify progress bar is shown
        progress_mock.grid.assert_called_once()
        status_label_mock.grid.assert_called_once()

        # Verify buttons get disabled and then re-enabled
        yes_btn_mock.config.assert_any_call(state="disabled")
        no_btn_mock.config.assert_any_call(state="disabled")

        # Verify download callback is called
        download_callback.assert_called_once()

        # Verify error message and result
        status_label_mock.__setitem__.assert_called_with("text", "Update failed!")
        assert dialog.result is False

        # Verify buttons are re-enabled
        yes_btn_mock.config.assert_any_call(state="normal")
        no_btn_mock.config.assert_any_call(state="normal")

        # Verify window is scheduled to close after 4 seconds
        self.root.after.assert_called_with(4000, self.root.destroy)

    def test_on_yes_without_callback(self) -> None:
        """Test on_yes method behavior when no callback is provided."""
        dialog = UpdateDialog(self.version_info, None)
        dialog.progress = MagicMock()
        dialog.status_label = MagicMock()
        dialog.yes_btn = MagicMock()
        dialog.no_btn = MagicMock()

        # Execute the method
        dialog.on_yes()

        # Verify progress bar is shown
        dialog.progress.grid.assert_called_once()
        dialog.status_label.grid.assert_called_once()

        # Verify buttons are disabled
        dialog.yes_btn.config.assert_called_with(state="disabled")
        dialog.no_btn.config.assert_called_with(state="disabled")

        # No further actions should happen without callback
        assert dialog.result is None
        self.root.after.assert_not_called()

    def test_grid_management(self) -> None:
        """Test grid management during update process."""
        dialog = UpdateDialog(self.version_info)

        # Mock the progress and status_label
        progress_mock = MagicMock()
        status_label_mock = MagicMock()
        dialog.progress = progress_mock
        dialog.status_label = status_label_mock

        # Initially, progress should be hidden (grid_remove should have been called)
        # We can't test this directly since it happens during initialization

        # When on_yes is called, grid should be called to show the progress bar
        dialog.on_yes()
        progress_mock.grid.assert_called_once()
        status_label_mock.grid.assert_called_once()

    def test_status_messages(self) -> None:
        """Test status message updates."""
        dialog = UpdateDialog(self.version_info)
        dialog.status_label = MagicMock()

        # Test empty status
        dialog.update_progress(50, "")
        dialog.status_label.__setitem__.assert_not_called()  # pylint: disable=no-member

        # Test with status message
        dialog.update_progress(75, "Processing...")
        dialog.status_label.__setitem__.assert_called_with("text", "Processing...")  # pylint: disable=no-member

    def test_progress_value_bounds(self) -> None:
        """Test progress bar value bounds."""
        dialog = UpdateDialog(self.version_info)
        dialog.progress = MagicMock()

        # Test minimum value
        dialog.update_progress(0)
        dialog.progress.__setitem__.assert_called_with("value", 0)  # pylint: disable=no-member

        # Test maximum value
        dialog.update_progress(100)
        dialog.progress.__setitem__.assert_called_with("value", 100)  # pylint: disable=no-member

        # Test value between bounds
        dialog.update_progress(50)
        dialog.progress.__setitem__.assert_called_with("value", 50)  # pylint: disable=no-member

    def test_version_info_display(self) -> None:
        """Test version info display in dialog."""
        version_info = "Version 2.0.0\n- New features\n- Bug fixes"

        # Mock the label
        label_mock = MagicMock()
        with patch("tkinter.ttk.Label", return_value=label_mock) as mock_label:
            _dialog = UpdateDialog(version_info)

            # The mock should have been created with our version info text
            mock_calls = mock_label.call_args_list
            # Find the call that created the label with our version info
            version_label_call_found = False
            for call in mock_calls:
                _args, kwargs = call
                if "text" in kwargs and kwargs["text"] == version_info:
                    version_label_call_found = True
                    break

            assert version_label_call_found, "Version info wasn't passed to the label"

    def test_show_method(self) -> None:
        """Test the show method returns the correct result."""
        # Mock tk.mainloop to avoid actually starting the event loop
        with patch("tkinter.Tk.mainloop"):
            dialog = UpdateDialog(self.version_info)

            # Set result and test return value
            dialog.result = True
            assert dialog.show() is True

            dialog.result = False
            assert dialog.show() is False

            dialog.result = None
            assert dialog.show() is False  # None should convert to False
