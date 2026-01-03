#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_progress_window.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


class TestProgressWindowUserExperience:
    """Test ProgressWindow from the user's perspective - focusing on progress indication behavior."""

    @pytest.fixture
    def progress_window(self, tk_root) -> Generator[ProgressWindow, None, None]:
        """Fixture providing a ProgressWindow ready for user interaction testing."""
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.center_window"):
            window = ProgressWindow(tk_root, title="Test Progress", message="Progress: {}/{}", width=300, height=80)
            yield window
            # Cleanup
            with contextlib.suppress(Exception):
                window.destroy()

    @pytest.fixture
    def lazy_progress_window(self, tk_root) -> Generator[ProgressWindow, None, None]:
        """Fixture providing a ProgressWindow that only shows when progress is updated."""
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.center_window"):
            window = ProgressWindow(
                tk_root, title="Lazy Progress", message="Processing: {}/{}", only_show_when_update_progress_called=True
            )
            yield window
            # Cleanup
            with contextlib.suppress(Exception):
                window.destroy()

    def test_user_sees_progress_window_with_initial_state(self, progress_window) -> None:
        """
        User sees a progress window that displays initial progress state.

        GIVEN: A progress window is created for a long-running task
        WHEN: The window is first shown
        THEN: The user sees the correct title and initial progress (0/0)
        """
        # Verify window title
        assert progress_window.progress_window.title() == "Test Progress"

        # Verify initial progress state
        assert progress_window.progress_label.cget("text") == "Progress: 0/0"
        assert progress_window.progress_bar["value"] == 0
        assert progress_window.progress_bar["maximum"] == 100

    def test_user_sees_progress_updates_during_task_execution(self, progress_window) -> None:
        """
        User sees progress updates as a task executes.

        GIVEN: A progress window is showing task progress
        WHEN: The task reports progress updates
        THEN: The user sees accurate progress indication and messages
        """
        # Update to 50% progress
        progress_window.update_progress_bar(50, 100)

        assert progress_window.progress_bar["value"] == 50
        assert progress_window.progress_bar["maximum"] == 100
        assert progress_window.progress_label.cget("text") == "Progress: 50/100"

        # Update to 75% progress
        progress_window.update_progress_bar(75, 100)

        assert progress_window.progress_bar["value"] == 75
        assert progress_window.progress_label.cget("text") == "Progress: 75/100"

    def test_user_sees_progress_window_close_when_task_completes(self, progress_window) -> None:
        """
        User sees progress window automatically close when task completes.

        GIVEN: A progress window is tracking task completion
        WHEN: The task reaches 100% completion
        THEN: The progress window closes automatically
        """
        # Complete the task
        progress_window.update_progress_bar(100, 100)

        # Window should be destroyed
        assert not progress_window.progress_window.winfo_exists()

    def test_user_sees_special_progress_for_long_running_tasks(self, progress_window) -> None:
        """
        User sees special progress indication for tasks that take longer than expected.

        GIVEN: A task is taking much longer than expected (300% of estimated time)
        WHEN: Progress is updated with the 300% method
        THEN: The user sees encouraging patience message with percentage of 100%
        """
        # Simulate 150% of estimated time (50% of 100% complete)
        progress_window.update_progress_bar_300_pct(150)

        assert progress_window.progress_bar["value"] == 50
        assert progress_window.progress_bar["maximum"] == 100
        # Note: The exact message depends on translation, but should contain the percentage
        assert "50.0%" in progress_window.progress_label.cget("text")

    def test_user_only_sees_lazy_progress_window_when_progress_starts(self, lazy_progress_window) -> None:
        """
        User only sees progress window when actual progress begins (lazy loading).

        GIVEN: A progress window configured to show only when progress updates
        WHEN: Progress is first updated
        THEN: The window becomes visible at that point
        """
        # Initially window should not be shown
        assert not lazy_progress_window._shown  # pylint: disable=protected-access

        # First progress update should show the window
        lazy_progress_window.update_progress_bar(25, 100)

        assert lazy_progress_window._shown  # pylint: disable=protected-access
        assert lazy_progress_window.progress_bar["value"] == 25
        assert lazy_progress_window.progress_label.cget("text") == "Processing: 25/100"

    def test_user_sees_progress_window_handle_values_exceeding_maximum(self, progress_window) -> None:
        """
        User sees progress window handle edge cases gracefully.

        GIVEN: A progress update with value exceeding maximum
        WHEN: Such progress is reported
        THEN: The progress bar shows the actual value (allowing overflow visualization)
        """
        # Update with value exceeding maximum
        progress_window.update_progress_bar(150, 100)

        # Progress bar should show the actual value
        assert progress_window.progress_bar["value"] == 150
        assert progress_window.progress_bar["maximum"] == 100
        assert progress_window.progress_label.cget("text") == "Progress: 150/100"

    def test_user_sees_progress_window_resist_destroyed_window_updates(self, progress_window) -> None:
        """
        User sees progress window handle updates gracefully even if window is destroyed.

        GIVEN: A progress window that gets destroyed externally
        WHEN: Progress updates are attempted
        THEN: No errors occur and updates are safely ignored
        """
        # Manually destroy the window
        progress_window.progress_window.destroy()

        # Attempting to update should not raise errors
        progress_window.update_progress_bar(50, 100)

        # Window should remain destroyed
        assert not progress_window.progress_window.winfo_exists()

    def test_user_can_manually_close_progress_window(self, progress_window) -> None:
        """
        User can manually close the progress window if needed.

        GIVEN: A progress window is showing
        WHEN: The user manually closes it
        THEN: The window is properly destroyed
        """
        # Verify window exists initially
        assert progress_window.progress_window.winfo_exists()

        # Manually destroy
        progress_window.destroy()

        # Window should be destroyed
        assert not progress_window.progress_window.winfo_exists()

    def test_user_sees_progress_window_handle_master_not_tk_instance(self, tk_root) -> None:
        """
        User sees progress window handle non-Tk master gracefully.

        GIVEN: A progress window is created with a non-Tk master
        WHEN: The window is initialized
        THEN: An error is logged but window creation continues
        """
        # Create a non-Tk master (using a Toplevel instead of Tk)
        non_tk_master = tk.Toplevel(tk_root)

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_progress_window.logging_error") as mock_logging,
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.center_window"),
        ):
            window = ProgressWindow(non_tk_master, title="Test Progress", message="Progress: {}/{}")

            # Verify error was logged
            mock_logging.assert_called_once()
            assert "master is not a tk.Tk instance" in mock_logging.call_args[0][0]

            # Window should still be created
            assert window.progress_window.winfo_exists()

            window.destroy()
            non_tk_master.destroy()

    def test_user_sees_progress_window_handle_widget_update_errors(self, progress_window) -> None:
        """
        User sees progress window handle Tkinter errors during updates gracefully.

        GIVEN: A progress window that encounters Tkinter errors during updates
        WHEN: Progress updates fail due to widget errors
        THEN: Errors are logged but no exceptions are raised
        """
        # Mock progress_bar.update to raise TclError
        progress_window.progress_bar.update = MagicMock(side_effect=tk.TclError("Widget destroyed"))

        with patch("ardupilot_methodic_configurator.frontend_tkinter_progress_window.logging_error") as mock_logging:
            # This should not raise an exception
            progress_window.update_progress_bar(50, 100)

            # Verify error was logged
            mock_logging.assert_called_once()
            assert "Updating progress widgets" in mock_logging.call_args[0][0]

    def test_user_sees_progress_window_handle_lazy_window_relift(self, progress_window) -> None:
        """
        User sees progress window handle relifting for already shown windows.

        GIVEN: A progress window that is already shown
        WHEN: Progress is updated multiple times
        THEN: Window is lifted appropriately for non-lazy windows
        """
        # Mock the lift method to track calls
        progress_window.progress_window.lift = MagicMock()

        # First update - window should be lifted
        progress_window.update_progress_bar(25, 100)

        # Verify window is lifted for non-lazy windows
        progress_window.progress_window.lift.assert_called_once()

        # Reset mock
        progress_window.progress_window.lift.reset_mock()

        # Second update - window should be lifted again
        progress_window.update_progress_bar(50, 100)

        # Should be lifted again
        progress_window.progress_window.lift.assert_called_once()
