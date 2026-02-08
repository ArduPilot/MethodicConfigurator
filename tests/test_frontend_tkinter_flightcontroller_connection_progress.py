#!/usr/bin/env python3

"""
Behavior-driven tests for FlightControllerConnectionProgress class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_connection_progress import (
    PROGRESS_FC_INIT_COMPLETE,
    FlightControllerConnectionProgress,
)

# pylint: disable=redefined-outer-name, unused-argument


@pytest.fixture
def mock_progress_window() -> tuple[MagicMock, MagicMock]:
    """Fixture providing a mock ProgressWindow for testing."""
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_connection_progress.ProgressWindow"
    ) as mock_pw:
        mock_progress_instance = MagicMock()
        mock_progress_instance.progress_window = MagicMock()
        mock_pw.return_value = mock_progress_instance
        yield mock_pw, mock_progress_instance


@pytest.fixture
def mock_tkinter_root() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Fixture providing a mock Tk root window."""
    with (
        patch("tkinter.Tk") as mock_tk,
        patch("tkinter.ttk.Style") as mock_style,
    ):
        mock_root = MagicMock()
        mock_root.winfo_width.return_value = 1  # Minimal temp root
        mock_tk.return_value = mock_root

        mock_style_instance = MagicMock()
        mock_style.return_value = mock_style_instance

        yield mock_tk, mock_root, mock_style_instance


class TestFlightControllerConnectionProgressBehavior:
    """Test user-visible behavior of flight controller connection progress UI."""

    def test_user_sees_progress_window_during_connection(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        User sees progress window when connecting to flight controller.

        GIVEN: User initiates connection to flight controller
        WHEN: Connection process begins
        THEN: A progress window should be created and displayed
        """
        # Arrange: Mock dependencies
        mock_pw_class, _ = mock_progress_window

        # Act: User triggers flight controller connection
        progress = FlightControllerConnectionProgress()

        # Assert: Progress window should be created
        mock_pw_class.assert_called_once()
        assert progress.progress_window is not None

    def test_connection_window_is_themed_and_positioned(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        Connection window uses proper theme and positioning.

        GIVEN: Connection progress window is created
        WHEN: Window is initialized
        THEN: Should apply theme and center on screen
        """
        # Arrange: Mock dependencies
        _, _, mock_style_instance = mock_tkinter_root

        # Act: Create connection progress
        FlightControllerConnectionProgress()

        # Assert: Theme configured (centering is handled by ProgressWindow)
        mock_style_instance.theme_use.assert_called_once_with("alt")

    def test_user_sees_initialization_progress_updates(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        User sees initialization progress updates during connection.

        GIVEN: Connection to flight controller is in progress
        WHEN: Initialization phase progresses
        THEN: Progress bar should update to reflect current initialization status
        """
        # Arrange: Create progress window
        _, mock_pw_instance = mock_progress_window
        progress = FlightControllerConnectionProgress()

        # Act: Simulate initialization progress updates (0-100%)
        progress.update_init_progress_bar(0, 100)
        progress.update_init_progress_bar(50, 100)
        progress.update_init_progress_bar(100, 100)

        # Assert: Progress should be mapped to 0-20% range (PROGRESS_FC_INIT_COMPLETE)
        calls = mock_pw_instance.update_progress_bar.call_args_list
        assert len(calls) == 3
        assert calls[0][0] == (0, 100)  # 0% -> 0
        assert calls[1][0] == (10, 100)  # 50% -> 10 (50% of 20)
        assert calls[2][0] == (20, 100)  # 100% -> 20

    def test_user_sees_connection_progress_updates(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        User sees connection progress updates during connection phase.

        GIVEN: Flight controller initialization is complete
        WHEN: Connection phase progresses
        THEN: Progress bar should update to reflect current connection status
        """
        # Arrange: Create progress window
        _, mock_pw_instance = mock_progress_window
        progress = FlightControllerConnectionProgress()

        # Act: Simulate connection progress updates (0-100%)
        progress.update_connect_progress_bar(0, 100)
        progress.update_connect_progress_bar(50, 100)
        progress.update_connect_progress_bar(100, 100)

        # Assert: Progress should be mapped to 20-100% range
        calls = mock_pw_instance.update_progress_bar.call_args_list
        assert len(calls) == 3
        assert calls[0][0] == (20, 100)  # 0% -> 20 (PROGRESS_FC_INIT_COMPLETE)
        assert calls[1][0] == (60, 100)  # 50% -> 60 (20 + 50% of 80)
        assert calls[2][0] == (100, 100)  # 100% -> 100

    def test_user_can_use_connection_progress_as_context_manager(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        User benefits from automatic cleanup when using connection progress.

        GIVEN: Connection progress is used in a context manager
        WHEN: Context exits (normally or with exception)
        THEN: Resources should be cleaned up automatically
        """
        # Arrange: Mock dependencies
        _, mock_root, _ = mock_tkinter_root
        _, mock_pw_instance = mock_progress_window

        # Act: Use as context manager
        with FlightControllerConnectionProgress() as progress:
            assert progress is not None
            # Simulate some work
            progress.update_init_progress_bar(50, 100)

        # Assert: Cleanup should have been called
        mock_pw_instance.destroy.assert_called_once()
        mock_root.destroy.assert_called_once()

    def test_user_informed_of_invalid_progress_values(self, mock_tkinter_root, mock_progress_window, caplog) -> None:
        """
        User is protected from invalid progress values.

        GIVEN: Progress update with invalid max_value
        WHEN: Application tries to update progress with invalid data
        THEN: Should log error and not crash
        AND: Should not attempt to update progress bar
        """
        # Arrange: Create progress window
        _, mock_pw_instance = mock_progress_window
        progress = FlightControllerConnectionProgress()
        initial_call_count = mock_pw_instance.update_progress_bar.call_count

        # Act: Try to update with invalid max_value
        with caplog.at_level("ERROR"):
            progress.update_init_progress_bar(50, 0)  # Invalid: max_value=0
            progress.update_connect_progress_bar(50, -1)  # Invalid: max_value=-1

        # Assert: Should log error and not call update_progress_bar
        assert len(caplog.records) == 2
        assert "Invalid max_value" in caplog.text
        assert mock_pw_instance.update_progress_bar.call_count == initial_call_count

    def test_progress_calculation_boundary_conditions(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        Progress calculations handle boundary conditions correctly.

        GIVEN: Various boundary conditions for progress values
        WHEN: Progress is updated with edge case values
        THEN: Calculations should handle boundaries gracefully
        """
        # Arrange: Create progress window
        _, mock_pw_instance = mock_progress_window
        progress = FlightControllerConnectionProgress()

        # Act & Assert: Test initialization phase boundaries
        progress.update_init_progress_bar(0, 100)
        assert mock_pw_instance.update_progress_bar.call_args[0] == (0, 100)

        progress.update_init_progress_bar(100, 100)
        assert mock_pw_instance.update_progress_bar.call_args[0] == (
            PROGRESS_FC_INIT_COMPLETE,
            100,
        )

        # Act & Assert: Test connection phase boundaries
        progress.update_connect_progress_bar(0, 100)
        assert mock_pw_instance.update_progress_bar.call_args[0] == (
            PROGRESS_FC_INIT_COMPLETE,
            100,
        )

        progress.update_connect_progress_bar(100, 100)
        assert mock_pw_instance.update_progress_bar.call_args[0] == (100, 100)

    def test_cleanup_handles_missing_resources_gracefully(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        Cleanup handles missing or already-destroyed resources gracefully.

        GIVEN: Progress window with potentially missing resources
        WHEN: Destroy is called
        THEN: Should not raise exceptions even if resources are missing
        """
        # Arrange: Create progress window
        progress = FlightControllerConnectionProgress()

        # Simulate missing progress_window (using type: ignore since type is non-Optional)
        progress.progress_window = None  # type: ignore[assignment]

        # Act & Assert: Should not raise exception
        progress.destroy()

        # Simulate missing temp_root
        progress.temp_root = None  # type: ignore[assignment]
        progress.destroy()  # Should still not raise

    def test_context_manager_cleanup_on_exception(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        Context manager ensures cleanup even when exception occurs.

        GIVEN: Connection progress used in context manager
        WHEN: Exception occurs during context
        THEN: Cleanup should still happen
        AND: Exception should propagate
        """
        # Arrange: Mock dependencies
        _, mock_root, _ = mock_tkinter_root
        _, mock_pw_instance = mock_progress_window

        # Act: Exception should propagate but cleanup should happen
        error_msg = "Test exception"
        with pytest.raises(ValueError, match=error_msg), FlightControllerConnectionProgress():
            raise ValueError(error_msg)

        # Assert: Cleanup should have been called despite exception
        mock_pw_instance.destroy.assert_called_once()
        mock_root.destroy.assert_called_once()


class TestProgressMappingAccuracy:
    """Test progress value mapping accuracy."""

    def test_init_progress_maps_correctly_across_range(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        Initialization progress maps correctly across entire range.

        GIVEN: Initialization progress values from 0-100%
        WHEN: Each value is mapped to display range
        THEN: Should map proportionally to 0-20% range
        """
        # Arrange
        _, mock_pw_instance = mock_progress_window
        progress = FlightControllerConnectionProgress()

        test_cases = [
            (0, 0),
            (10, 2),
            (25, 5),
            (50, 10),
            (75, 15),
            (100, 20),
        ]

        # Act & Assert: Test each mapping
        for input_val, expected_output in test_cases:
            progress.update_init_progress_bar(input_val, 100)
            actual_output = mock_pw_instance.update_progress_bar.call_args[0][0]
            assert actual_output == expected_output, f"Failed for input {input_val}"

    def test_connect_progress_maps_correctly_across_range(self, mock_tkinter_root, mock_progress_window) -> None:
        """
        Connection progress maps correctly across entire range.

        GIVEN: Connection progress values from 0-100%
        WHEN: Each value is mapped to display range
        THEN: Should map proportionally to 20-100% range
        """
        # Arrange
        _, mock_pw_instance = mock_progress_window
        progress = FlightControllerConnectionProgress()

        test_cases = [
            (0, 20),
            (10, 28),
            (25, 40),
            (50, 60),
            (75, 80),
            (100, 100),
        ]

        # Act & Assert: Test each mapping
        for input_val, expected_output in test_cases:
            progress.update_connect_progress_bar(input_val, 100)
            actual_output = mock_pw_instance.update_progress_bar.call_args[0][0]
            assert actual_output == expected_output, f"Failed for input {input_val}"
