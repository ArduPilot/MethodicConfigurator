#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_usage_popup_window.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import UsagePopupWindow


@pytest.fixture
def tk_root() -> tk.Tk:
    """Create a Tk root window for tests."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window during tests
    yield root
    root.destroy()


@pytest.fixture
def usage_window(tk_root) -> BaseWindow:  # pylint: disable=redefined-outer-name
    """Create a BaseWindow instance for tests."""
    window = BaseWindow(tk_root)
    yield window
    window.root.destroy()


@pytest.fixture
def rich_text(usage_window) -> RichText:  # pylint: disable=redefined-outer-name
    """Create a RichText instance for tests."""
    return RichText(usage_window.main_frame)


@pytest.fixture
def mock_set_display() -> MagicMock:
    """Mock the set_display_usage_popup method."""
    with patch(
        "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_display_usage_popup"
    ) as mock_fun:
        yield mock_fun


@pytest.mark.usefixtures("tk_root")
class TestUsagePopupWindowPytest:
    """Test cases for the UsagePopupWindow class using pytest style."""

    def test_should_display_true(self) -> None:
        """Test should_display returns True when configured so."""
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup",
            return_value=True,
        ) as mock_display:
            assert UsagePopupWindow.should_display("test_type") is True
            mock_display.assert_called_once_with("test_type")

    def test_should_display_false(self) -> None:
        """Test should_display returns False when configured so."""
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup",
            return_value=False,
        ) as mock_display:
            assert UsagePopupWindow.should_display("test_type") is False
            mock_display.assert_called_once_with("test_type")

    def test_display_sets_window_properties(self, tk_root, usage_window, rich_text) -> None:  # pylint: disable=redefined-outer-name
        """Test display method sets window properties correctly."""
        with patch("tkinter.BooleanVar") as mock_bool_var:
            mock_var_instance = MagicMock()
            mock_bool_var.return_value = mock_var_instance
            mock_var_instance.get.return_value = True

            # Call the display method
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=usage_window,
                title="Test Title",
                ptype="test_type",
                geometry="400x300",
                instructions_text=rich_text,
            )

            # Check window properties
            assert usage_window.root.title() == "Test Title"
            assert usage_window.root.geometry().startswith("400x300")

            # Verify checkbox and button were created
            children = usage_window.main_frame.winfo_children()
            checkbuttons = [w for w in children if isinstance(w, ttk.Checkbutton)]
            buttons = [w for w in children if isinstance(w, ttk.Button)]
            assert len(checkbuttons) == 1
            assert len(buttons) == 1

    def test_dismiss_button_closes_window(self, tk_root, usage_window, rich_text) -> None:  # pylint: disable=redefined-outer-name
        """Test dismiss button closes the window."""
        with patch("tkinter.BooleanVar"), patch.object(UsagePopupWindow, "close", autospec=True) as mock_close:
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=usage_window,
                title="Test Usage",
                ptype="test_type",
                geometry="300x200",
                instructions_text=rich_text,
            )

            # Find dismiss button
            buttons = [w for w in usage_window.main_frame.winfo_children() if isinstance(w, ttk.Button)]
            assert len(buttons) == 1
            dismiss_button = buttons[0]

            # Call command
            dismiss_button.invoke()

            # Verify close was called with correct arguments
            mock_close.assert_called_once_with(usage_window, tk_root)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window.platform_system", return_value="Windows")
    def test_windows_specific_behavior(self, mock_platform, tk_root, usage_window, rich_text) -> None:  # pylint: disable=redefined-outer-name, unused-argument
        """Test Windows-specific behavior for disabling parent window."""
        # Add mock for attributes method
        with patch.object(tk_root, "attributes") as mock_attributes, patch("tkinter.BooleanVar"):
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=usage_window,
                title="Test Usage",
                ptype="test_type",
                geometry="300x200",
                instructions_text=rich_text,
            )

            # On Windows, parent window should be disabled
            mock_attributes.assert_called_with("-disabled", True)  # noqa: FBT003

    @patch("ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window.platform_system", return_value="Linux")
    def test_non_windows_behavior(self, mock_platform, tk_root, usage_window, rich_text) -> None:  # pylint: disable=redefined-outer-name, unused-argument
        """Test non-Windows behavior where parent window is not disabled."""
        # Add mock for attributes method
        with patch.object(tk_root, "attributes") as mock_attributes, patch("tkinter.BooleanVar"):
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=usage_window,
                title="Test Usage",
                ptype="test_type",
                geometry="300x200",
                instructions_text=rich_text,
            )

            # On non-Windows, parent window should not be disabled with -disabled attribute
            mock_attributes.assert_not_called()  # This assumes attributes is never called for non-Windows platforms

    @patch("ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window.platform_system")
    def test_close_window(self, mock_platform, tk_root, usage_window) -> None:  # pylint: disable=redefined-outer-name
        """Test close method behavior."""
        # Test Windows behavior
        mock_platform.return_value = "Windows"

        # Mock attributes, destroy and focus_set methods
        with (
            patch.object(usage_window.root, "destroy") as mock_destroy,
            patch.object(tk_root, "focus_set") as mock_focus,
            patch.object(tk_root, "attributes") as mock_attributes,
        ):
            UsagePopupWindow.close(usage_window, tk_root)

            # Verify window is destroyed
            mock_destroy.assert_called_once()

            # Verify parent window is re-enabled on Windows
            mock_attributes.assert_called_with("-disabled", False)  # noqa: FBT003

            # Verify parent window gets focus
            mock_focus.assert_called_once()

        # Reset mocks for Linux test
        mock_platform.return_value = "Linux"

        # Mock methods again for Linux test
        with (
            patch.object(usage_window.root, "destroy") as mock_destroy,
            patch.object(tk_root, "focus_set") as mock_focus,
            patch.object(tk_root, "attributes") as mock_attributes,
        ):
            UsagePopupWindow.close(usage_window, tk_root)

            # Verify window is destroyed
            mock_destroy.assert_called_once()

            # Verify parent window attributes are not called on non-Windows
            mock_attributes.assert_not_called()

            # Verify parent window gets focus
            mock_focus.assert_called_once()

    def test_window_delete_protocol(self, tk_root, usage_window, rich_text) -> None:  # pylint: disable=redefined-outer-name
        """Test window delete protocol is set correctly."""
        with patch("tkinter.BooleanVar"), patch.object(usage_window.root, "protocol") as mock_protocol:
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=usage_window,
                title="Test Usage",
                ptype="test_type",
                geometry="300x200",
                instructions_text=rich_text,
            )

            # Verify WM_DELETE_WINDOW protocol is set
            mock_protocol.assert_called_once()
            assert mock_protocol.call_args[0][0] == "WM_DELETE_WINDOW"


class TestUsagePopupWindow(unittest.TestCase):
    """Test cases for the UsagePopupWindow class using unittest style."""

    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self) -> None:
        self.root.destroy()

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup")
    def test_should_display(self, mock_display_popup) -> None:
        """Test should_display method."""
        mock_display_popup.return_value = True
        assert UsagePopupWindow.should_display("test_type") is True
        mock_display_popup.assert_called_once_with("test_type")

    @patch("tkinter.BooleanVar")
    @pytest.mark.usefixtures("mock_set_display")
    def test_display_popup(self, mock_bool_var) -> None:
        """Test display method."""
        mock_bool_var.return_value.get.return_value = True
        usage_window = BaseWindow(self.root)  # pylint: disable=redefined-outer-name
        instructions = RichText(usage_window.main_frame)

        UsagePopupWindow.display(
            parent=self.root,
            usage_popup_window=usage_window,
            title="Test Usage",
            ptype="test_type",
            geometry="300x200",
            instructions_text=instructions,
        )

        assert usage_window.root.title() == "Test Usage"
        assert usage_window.root.geometry().startswith("300x200")
        # Test button creation and checkbox state
        checkbuttons = [w for w in usage_window.main_frame.winfo_children() if isinstance(w, ttk.Checkbutton)]
        assert len(checkbuttons) == 1


if __name__ == "__main__":
    unittest.main()
