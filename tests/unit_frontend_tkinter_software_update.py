#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_software_update.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from collections import deque
from collections.abc import Callable, Generator
from threading import Event, get_ident
from tkinter import ttk
from unittest.mock import MagicMock, call, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_software_update import UpdateDialog


class TestUpdateDialog(unittest.TestCase):  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Test cases for the UpdateDialog class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Patch PhotoImage before BaseWindow tries to use it
        self.photo_image_patch = patch("tkinter.PhotoImage")
        self.photo_image_mock = self.photo_image_patch.start()
        self.photo_image_mock.return_value = MagicMock()

        # Patch LocalFilesystem to avoid file system dependency
        self.filesystem_patch = patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.ProgramSettings")
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

        # Patch center_window_on_screen to prevent extra root.update() calls
        self.center_window_patch = patch.object(BaseWindow, "center_window_on_screen")
        self.center_window_patch.start()
        self.addCleanup(self.center_window_patch.stop)

        # Patch BaseWindow to use our controlled root window
        self.original_init = BaseWindow.__init__

        def mock_init(instance, root_tk=None) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Set instance attributes without calling the real __init__
            instance.root = self.root
            instance.main_frame = MagicMock()
            instance.dpi_scaling_factor = 1.0

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

        # Execute tasks deterministically in unit tests; the real runner is tested below.
        self.runner_patch = patch("ardupilot_methodic_configurator.frontend_tkinter_software_update.BackgroundTaskRunner")
        runner = self.runner_patch.start().return_value
        runner.active = False

        def start(
            task: Callable[[Callable[[float, str], None]], bool],
            on_progress: Callable[[float, str], None],
            on_done: Callable[[object | None, Exception | None], None],
        ) -> bool:
            on_done(task(on_progress), None)
            return True

        runner.start.side_effect = start

        # Input data for tests
        self.version_info = "Test Version Info"
        self.download_callback = MagicMock(return_value=True)

    def tearDown(self) -> None:
        """Clean up after each test."""
        # Restore the original __init__ method
        BaseWindow.__init__ = self.original_init

        # Bypass the mocked destroy method so later tests inherit a live Tk root.
        tk.Tk.destroy(self.root)

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

    def test_retry_keeps_dialog_open_past_previous_failure_close_deadline(self) -> None:
        """
        Retrying a failed download keeps its dialog available until the retry finishes.

        GIVEN: A failed update has enabled retry and scheduled the dialog to close
        WHEN: The user starts another download before that deadline
        THEN: Advancing past the old deadline cannot destroy the active dialog
        """
        pending: dict[str, Callable[[], None]] = {}

        def schedule(_milliseconds: int, callback: Callable[[], None]) -> str:
            timer_id = f"close-{len(pending)}"
            pending[timer_id] = callback
            return timer_id

        def cancel(timer_id: str) -> None:
            pending.pop(timer_id)

        self.download_callback.return_value = False
        dialog = UpdateDialog(self.version_info, self.download_callback)
        with (
            patch.object(self.root, "after", side_effect=schedule),
            patch.object(self.root, "after_cancel", side_effect=cancel),
        ):
            dialog.on_yes()
            assert dialog.result is False
            assert pending

            # The runner accepts the retry but leaves its download pending.
            dialog._download_runner.start.side_effect = None  # pylint: disable=protected-access
            dialog.on_yes()
            for callback in list(pending.values()):
                callback()

            self.root.destroy.assert_not_called()

    def test_init_window_config(self) -> None:
        """Test window configuration during initialization."""
        dialog = UpdateDialog(self.version_info)

        # Window configuration
        self.root.title.assert_called_once()
        self.root.geometry.assert_any_call("700x600")

        dialog.frame.grid_rowconfigure.assert_called_with(0, weight=1)  # pylint: disable=no-member

        # Check that grid_columnconfigure was called exactly twice with the right arguments
        assert dialog.frame.grid_columnconfigure.call_count == 2  # pylint: disable=no-member
        dialog.frame.grid_columnconfigure.assert_has_calls([call(0, weight=1), call(1, weight=1)])  # pylint: disable=no-member

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

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_software_update.is_macos_sequoia_or_older",
                return_value=False,
            ),
            patch.object(self.root, "update_idletasks") as update_idletasks,
        ):
            # Test with both value and status
            dialog.update_progress(75, "Downloading...")
            progress_mock.__setitem__.assert_called_with("value", 75)
            status_label_mock.__setitem__.assert_called_with("text", "Downloading...")
            update_idletasks.assert_called_once()
            self.root.update.assert_not_called()

            # Reset mocks
            progress_mock.reset_mock()
            status_label_mock.reset_mock()
            update_idletasks.reset_mock()

            # Test with only value (no status)
            dialog.update_progress(50)
            progress_mock.__setitem__.assert_called_with("value", 50)
            status_label_mock.__setitem__.assert_not_called()
            update_idletasks.assert_called_once()
            self.root.update.assert_not_called()

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
        dialog.status_label.__setitem__.assert_not_called()

        # Test with status message
        dialog.update_progress(75, "Processing...")
        dialog.status_label.__setitem__.assert_called_with("text", "Processing...")

    def test_progress_value_bounds(self) -> None:
        """Test progress bar value bounds."""
        dialog = UpdateDialog(self.version_info)
        dialog.progress = MagicMock()

        # Test minimum value
        dialog.update_progress(0)
        dialog.progress.__setitem__.assert_called_with("value", 0)

        # Test maximum value
        dialog.update_progress(100)
        dialog.progress.__setitem__.assert_called_with("value", 100)

        # Test value between bounds
        dialog.update_progress(50)
        dialog.progress.__setitem__.assert_called_with("value", 50)

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
            for m_call in mock_calls:
                _args, kwargs = m_call
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


@pytest.fixture(name="download_dialog")
def fixture_download_dialog(root: tk.Tk) -> Generator[UpdateDialog, None, None]:
    """Provide real download widgets without release-note layout or event-loop rendering."""
    parent = tk.Toplevel(root)
    parent.withdraw()
    try:
        dialog = object.__new__(UpdateDialog)
        dialog.root = parent
        dialog.progress = ttk.Progressbar(parent)
        dialog.status_label = ttk.Label(parent)
        dialog.yes_btn = ttk.Button(parent)
        dialog.no_btn = ttk.Button(parent)
        dialog.result = None
        dialog._close_timer_id = None  # pylint: disable=protected-access
        yield dialog
    finally:
        parent.destroy()


def test_download_keeps_tk_responsive_and_delivers_progress_on_tk_thread(download_dialog: UpdateDialog) -> None:
    """
    A slow update yields to UI callbacks and delivers progress on Tk's thread.

    GIVEN: A download worker waits for a heartbeat scheduled on the UI thread
    WHEN: UI callbacks run while the download is pending
    THEN: The UI stays available and progress reaches widgets on the UI thread
    """
    dialog = download_dialog
    parent = dialog.root
    ui_thread = get_ident()
    heartbeat = Event()
    worker_threads: list[int] = []
    progress_threads: list[int] = []
    scheduled: deque[Callable[[], None]] = deque()

    def download(report: Callable[[float, str], None]) -> bool:
        worker_threads.append(get_ident())
        assert heartbeat.wait(2)
        report(55.0, "Downloading")
        return True

    # Drive scheduled callbacks explicitly: a native Tk event loop can abort
    # the interpreter on headless macOS runners, even with withdrawn windows.
    runner = BackgroundTaskRunner(lambda _delay, callback: scheduled.append(callback))
    try:
        dialog.download_callback = download
        dialog._download_runner = runner  # pylint: disable=protected-access
        original_progress = dialog.update_progress

        def on_progress(value: float, status: str = "") -> None:
            progress_threads.append(get_ident())
            assert (value, status) == (55.0, "Downloading")
            original_progress(value, status)

        with (
            patch.object(dialog, "update_progress", side_effect=on_progress),
            patch.object(parent, "after"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_software_update.is_macos_sequoia_or_older", return_value=True
            ),
            patch.object(parent, "destroy", wraps=parent.destroy) as destroy,
        ):
            dialog.on_yes()
            dialog.on_yes()
            dialog.on_cancel()
            destroy.assert_not_called()
            scheduled.append(heartbeat.set)
            scheduled.popleft()()  # The first poll yields while the worker waits.
            assert dialog.result is None
            scheduled.popleft()()  # The UI heartbeat releases the worker.
            worker = runner.thread
            assert worker is not None
            worker.join(timeout=2)
            assert not worker.is_alive()
            scheduled.popleft()()  # Deliver progress and completion on the UI thread.

        assert dialog.result is True
        assert len(worker_threads) == 1
        assert worker_threads[0] != ui_thread
        assert progress_threads == [ui_thread]
        assert dialog.progress["value"] == 55.0
    finally:
        heartbeat.set()
        if runner.thread is not None:
            runner.thread.join(timeout=2)
