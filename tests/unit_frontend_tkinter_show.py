#!/usr/bin/env python3


"""
Unit tests for frontend_tkinter_show.py internal functions.

These tests focus on implementation details and internal logic for code coverage,
not user behavior.
For behavior-driven tests, see bdd_frontend_tkinter_show.py.
For GUI integration tests, see gui_frontend_tkinter_show.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from tkinter import TclError
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_show import (
    MonitorBounds,
    _convert_cocoa_to_tk_bounds,
    _find_screen_containing_point,
    _get_appkit_screens,
    _is_valid_monitor_bounds,
    _monitor_bounds_macos,
    _monitor_bounds_tk,
    _monitor_bounds_windows,
)


class TestWindowsMonitorBoundsImplementation:
    """Unit tests for Windows-specific monitor bounds implementation."""

    def test_missing_ctypes_returns_none(self) -> None:
        """Test that missing ctypes module returns None."""
        widget = MagicMock()

        with patch("builtins.__import__", side_effect=ImportError("No module named 'ctypes'")):
            result = _monitor_bounds_windows(widget)

        assert result is None

    def test_missing_windll_returns_none(self) -> None:
        """Test that missing windll attribute returns None."""
        widget = MagicMock()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.getattr", return_value=None):
            result = _monitor_bounds_windows(widget)

        assert result is None

    def test_destroyed_widget_returns_none(self) -> None:
        """Test that destroyed widget raises TclError and returns None."""
        widget = MagicMock()
        widget.winfo_id.side_effect = TclError("invalid command name")

        result = _monitor_bounds_windows(widget)

        assert result is None

    def test_monitor_handle_failure_returns_none(self) -> None:
        """Test that MonitorFromWindow failure returns None."""
        widget = MagicMock()
        widget.winfo_id.return_value = 12345

        mock_windll = MagicMock()
        mock_windll.user32.MonitorFromWindow.return_value = 0

        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.getattr", return_value=mock_windll):
            result = _monitor_bounds_windows(widget)

        assert result is None

    def test_getmonitorinfo_failure_returns_none(self) -> None:
        """Test that GetMonitorInfoW failure returns None."""
        widget = MagicMock()
        widget.winfo_id.return_value = 12345

        mock_windll = MagicMock()
        mock_windll.user32.MonitorFromWindow.return_value = 999
        mock_windll.user32.GetMonitorInfoW.return_value = 0

        with patch("ardupilot_methodic_configurator.frontend_tkinter_show.getattr", return_value=mock_windll):
            result = _monitor_bounds_windows(widget)

        assert result is None


class TestMacOSMonitorBoundsImplementation:
    """Unit tests for macOS-specific monitor bounds implementation."""

    def test_missing_appkit_returns_none(self) -> None:
        """Test that missing AppKit module returns None."""
        with patch("importlib.import_module", side_effect=ImportError("No module named 'AppKit'")):
            result = _get_appkit_screens()

        assert result is None

    def test_missing_nsscreen_returns_none(self) -> None:
        """Test that missing NSScreen attribute returns None."""
        mock_appkit = MagicMock()
        del mock_appkit.NSScreen

        with patch("importlib.import_module", return_value=mock_appkit):
            result = _get_appkit_screens()

        assert result is None

    def test_empty_screens_list_returns_none(self) -> None:
        """Test that empty screens list returns None."""
        widget = MagicMock()
        mock_ns_screen = MagicMock()
        mock_ns_screen.screens.return_value = []

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_show._get_appkit_screens",
            return_value=mock_ns_screen,
        ):
            result = _monitor_bounds_macos(widget)

        assert result is None

    def test_widget_errors_return_none(self) -> None:
        """Test that widget exceptions return None."""
        widget = MagicMock()
        mock_ns_screen = MagicMock()
        mock_ns_screen.screens.return_value = [MagicMock()]

        widget.winfo_toplevel.side_effect = TclError("invalid command")

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_show._get_appkit_screens",
            return_value=mock_ns_screen,
        ):
            result = _monitor_bounds_macos(widget)

        assert result is None

    def test_cocoa_to_tk_coordinate_conversion(self) -> None:
        """Test Cocoa to Tk coordinate conversion formula."""
        mock_frame = MagicMock()
        mock_frame.origin.x = 0
        mock_frame.origin.y = 900
        mock_frame.size.width = 1920
        mock_frame.size.height = 1080
        primary_height = 1080

        result = _convert_cocoa_to_tk_bounds(mock_frame, primary_height)

        # tk_y = primary_height - (cocoa_y + height) = 1080 - (900 + 1080) = -900
        assert result == MonitorBounds(0, -900, 1920, 180)

    def test_invalid_cocoa_frame_raises_valueerror(self) -> None:
        """Test that invalid frame raises ValueError."""
        invalid_frame = MagicMock()
        del invalid_frame.origin

        with pytest.raises(ValueError, match="Invalid AppKit frame object"):
            _convert_cocoa_to_tk_bounds(invalid_frame, 1080)

    def test_find_screen_containing_point_finds_correct_screen(self) -> None:
        """Test finding screen containing a specific point."""
        screen1 = MagicMock()
        screen1_frame = MagicMock()
        screen1_frame.origin.x = 0
        screen1_frame.origin.y = 0
        screen1_frame.size.width = 1920
        screen1_frame.size.height = 1080
        screen1.frame.return_value = screen1_frame

        screen2 = MagicMock()
        screen2_frame = MagicMock()
        screen2_frame.origin.x = 1920
        screen2_frame.origin.y = 0
        screen2_frame.size.width = 1920
        screen2_frame.size.height = 1080
        screen2.frame.return_value = screen2_frame

        screens = [screen1, screen2]
        primary_height = 1080

        result = _find_screen_containing_point(screens, 2000, 500, primary_height)

        assert result is not None
        assert result.left == 1920

    def test_find_screen_returns_none_when_point_outside(self) -> None:
        """Test finding screen returns None when point is outside all screens."""
        screen = MagicMock()
        frame = MagicMock()
        frame.origin.x = 0
        frame.origin.y = 0
        frame.size.width = 1920
        frame.size.height = 1080
        screen.frame.return_value = frame

        screens = [screen]
        primary_height = 1080

        result = _find_screen_containing_point(screens, 5000, 5000, primary_height)

        assert result is None


class TestMonitorBoundsValidationImplementation:
    """Unit tests for monitor bounds validation logic."""

    def test_valid_bounds_accepted(self) -> None:
        """Test various valid bounds configurations."""
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 1920, 1080)) is True
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 11520, 2160)) is True
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 100, 100)) is True
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 65535, 65535)) is True

    def test_invalid_bounds_rejected(self) -> None:
        """Test various invalid bounds configurations."""
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 50, 50)) is False
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 70000, 70000)) is False
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 99, 99)) is False
        assert _is_valid_monitor_bounds(MonitorBounds(0, 0, 65536, 65536)) is False
        assert _is_valid_monitor_bounds(None) is False

    def test_negative_dimensions_rejected(self) -> None:
        """Test negative dimensions are rejected."""
        assert _is_valid_monitor_bounds(MonitorBounds(100, 0, 50, 1080)) is False
        assert _is_valid_monitor_bounds(MonitorBounds(0, 100, 1920, 50)) is False


class TestTkFallbackBoundsImplementation:
    """Unit tests for Tk fallback bounds implementation."""

    def test_uses_virtual_root_coordinates(self) -> None:
        """Test virtual root coordinates are used."""
        widget = MagicMock()
        toplevel = MagicMock()
        toplevel.winfo_vrootx.return_value = 100
        toplevel.winfo_vrooty.return_value = 50
        toplevel.winfo_vrootwidth.return_value = 1920
        toplevel.winfo_vrootheight.return_value = 1080
        widget.winfo_toplevel.return_value = toplevel

        result = _monitor_bounds_tk(widget)

        assert result == MonitorBounds(100, 50, 2020, 1130)

    def test_falls_back_to_screen_dimensions_when_vroot_invalid(self) -> None:
        """Test fallback to screen dimensions when virtual root is invalid."""
        widget = MagicMock()
        toplevel = MagicMock()
        toplevel.winfo_vrootx.return_value = 0
        toplevel.winfo_vrooty.return_value = 0
        toplevel.winfo_vrootwidth.return_value = 0
        toplevel.winfo_vrootheight.return_value = 0
        toplevel.winfo_screenwidth.return_value = 1920
        toplevel.winfo_screenheight.return_value = 1080
        widget.winfo_toplevel.return_value = toplevel

        result = _monitor_bounds_tk(widget)

        assert result == MonitorBounds(0, 0, 1920, 1080)
