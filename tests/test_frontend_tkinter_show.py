#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_show.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_show import (
    Tooltip,
    show_error_message,
    show_no_connection_error,
    show_no_param_files_error,
    show_tooltip,
)

# pylint: disable=redefined-outer-name


# Fixtures
@pytest.fixture
def mock_tk() -> Generator[MagicMock, None, None]:
    with patch("tkinter.Tk") as mock:
        mock.return_value.withdraw.return_value = None
        mock.return_value.destroy.return_value = None
        yield mock


@pytest.fixture
def mock_widget() -> MagicMock:
    widget = MagicMock()
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 200
    widget.winfo_width.return_value = 50
    widget.winfo_height.return_value = 30
    return widget


@pytest.fixture
def mock_toplevel() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    with patch("tkinter.Toplevel") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock, mock_instance


@pytest.fixture
def mock_label() -> Generator[MagicMock, None, None]:
    with patch("tkinter.ttk.Label") as mock:
        mock.return_value.pack.return_value = None
        yield mock


# Tests for show_error_message
@pytest.mark.parametrize(
    ("title", "message"),
    [
        ("Test Title", "Test Message"),
        ("Test & Title", "Test\nMessage with & special < chars >"),
    ],
)
def test_show_error_message(mock_tk, title, message) -> None:
    with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
        # Call the function with test parameters
        show_error_message(title, message)

        # Assert that the Tkinter Tk class was instantiated
        mock_tk.assert_called_once()

        # Assert that the Tkinter messagebox.showerror function was called with the correct parameters
        mock_showerror.assert_called_once_with(title, message)

        # Assert that the Tkinter Tk instance's withdraw method was called
        mock_tk.return_value.withdraw.assert_called_once()

        # Assert that the Tkinter Tk instance's destroy method was called
        mock_tk.return_value.destroy.assert_called_once()


# Tests for show_no_param_files_error
def test_show_no_param_files_error(mock_tk) -> None:
    with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
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


# Tests for show_no_connection_error
def test_show_no_connection_error(mock_tk) -> None:
    with patch("tkinter.messagebox.showerror") as mock_showerror, patch("tkinter.ttk.Style"):
        show_no_connection_error("test_error")

        mock_tk.assert_called_once()
        mock_showerror.assert_called_once_with(
            "No Connection to the Flight Controller",
            "test_error\n\nPlease connect a flight controller to the PC,\nwait at least 7 seconds and retry.",
        )
        mock_tk.return_value.withdraw.assert_called_once()
        mock_tk.return_value.destroy.assert_called_once()


# Tests for show_tooltip function
def test_show_tooltip(mock_widget) -> None:
    # Mock the Tooltip class to avoid creating actual tkinter windows
    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
        mock_tooltip_instance = MagicMock()
        mock_tooltip_class.return_value = mock_tooltip_instance

        # Call the function with test parameters
        tooltip = show_tooltip(mock_widget, "Test Tooltip Message")

        # Check that tooltip object was created and is the mocked instance
        assert tooltip is mock_tooltip_instance

        # Verify Tooltip was called with correct parameters (position_below=True is the default)
        mock_tooltip_class.assert_called_once_with(mock_widget, "Test Tooltip Message", position_below=True)


# Tests for Tooltip class
def test_tooltip_init(mock_widget) -> None:
    # Test non-macOS initialization (where tooltip is created immediately)
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel") as mock_toplevel,
    ):
        mock_instance = MagicMock()
        mock_toplevel.return_value = mock_instance

        tooltip = Tooltip(mock_widget, "Test tooltip text")

        # Verify attribute initialization
        assert tooltip.widget == mock_widget
        assert tooltip.text == "Test tooltip text"
        assert tooltip.tooltip is not None  # On non-macOS, tooltip is created immediately
        assert tooltip.position_below is True

        # Verify event bindings for non-macOS
        mock_widget.bind.assert_any_call("<Enter>", tooltip.show)
        mock_widget.bind.assert_any_call("<Leave>", tooltip.hide)

        # Verify that Toplevel was created and configured
        mock_toplevel.assert_called_once_with(mock_widget)
        mock_instance.wm_overrideredirect.assert_called_once_with(boolean=True)


def test_tooltip_init_macos(mock_widget) -> None:
    # Test macOS initialization (where tooltip is not created immediately)
    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"):
        tooltip = Tooltip(mock_widget, "Test tooltip text")

        # Verify attribute initialization
        assert tooltip.widget == mock_widget
        assert tooltip.text == "Test tooltip text"
        assert tooltip.tooltip is None  # On macOS, tooltip is not created immediately
        assert tooltip.position_below is True

        # Verify event bindings for macOS
        mock_widget.bind.assert_any_call("<Enter>", tooltip.create_show)
        mock_widget.bind.assert_any_call("<Leave>", tooltip.destroy_hide)


def test_tooltip_show(mock_widget, mock_toplevel, mock_label) -> None:
    _, mock_toplevel_instance = mock_toplevel

    tooltip = Tooltip(mock_widget, "Test tooltip")
    tooltip.show()

    # Verify toplevel window was created
    assert tooltip.tooltip is not None

    # Calculate expected positioning
    expected_x = mock_widget.winfo_rootx() + min(mock_widget.winfo_width() // 2, 100)
    expected_y = mock_widget.winfo_rooty() + mock_widget.winfo_height()

    # Check positioning
    mock_toplevel_instance.geometry.assert_called_with(f"+{expected_x}+{expected_y}")

    # Verify label was created with right text
    mock_label.assert_called_once()
    assert mock_label.call_args[1]["text"] == "Test tooltip"


def test_tooltip_show_position_above(mock_widget, mock_toplevel) -> None:
    _, mock_toplevel_instance = mock_toplevel

    # Create tooltip positioned above widget
    tooltip = Tooltip(mock_widget, "Test tooltip", position_below=False)
    tooltip.show()

    # Calculate expected positioning (should be above the widget)
    expected_x = mock_widget.winfo_rootx() + min(mock_widget.winfo_width() // 2, 100)
    expected_y = mock_widget.winfo_rooty() - 10  # positioned above

    # Check positioning
    mock_toplevel_instance.geometry.assert_called_with(f"+{expected_x}+{expected_y}")

    # Create tooltip positioned above widget


def test_tooltip_hide(mock_widget, mock_toplevel) -> None:
    _, mock_toplevel_instance = mock_toplevel

    tooltip = Tooltip(mock_widget, "Test tooltip")
    tooltip.show()

    # Verify tooltip created
    assert tooltip.tooltip is not None

    # Clear the call count from initialization
    mock_toplevel_instance.withdraw.reset_mock()

    # Now hide the tooltip
    tooltip.hide()

    # On non-macOS systems, hide() should call withdraw() but not destroy the tooltip
    mock_toplevel_instance.withdraw.assert_called_once()
    # The tooltip instance should still exist
    assert tooltip.tooltip is not None
    # destroy should not have been called
    mock_toplevel_instance.destroy.assert_not_called()


def test_tooltip_destroy_hide_macos(mock_widget) -> None:
    # Test macOS specific destroy behavior
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"),
        patch("tkinter.Toplevel") as mock_toplevel,
    ):
        mock_instance = MagicMock()
        mock_toplevel.return_value = mock_instance

        tooltip = Tooltip(mock_widget, "Test tooltip")

        # Simulate the tooltip being shown (created on macOS)
        tooltip.create_show()

        # Verify tooltip created
        assert tooltip.tooltip is not None

        # Now destroy_hide the tooltip (macOS behavior)
        tooltip.destroy_hide()

        # On macOS systems, destroy_hide() should destroy the tooltip
        mock_instance.destroy.assert_called_once()
        # The tooltip instance should be None
        assert tooltip.tooltip is None


def test_tooltip_show_hide_event_handling(mock_widget) -> None:
    """Test that tooltip properly handles Enter and Leave events."""
    # Test non-macOS event handling
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel") as mock_toplevel,
    ):
        mock_toplevel_instance = MagicMock()
        mock_toplevel.return_value = mock_toplevel_instance

        # Create tooltip instance
        tooltip = Tooltip(mock_widget, "Test tooltip")

        # Verify the widget was bound to the correct events
        mock_widget.bind.assert_any_call("<Enter>", tooltip.show)
        mock_widget.bind.assert_any_call("<Leave>", tooltip.hide)

        # Test show method with event
        mock_event = MagicMock()
        tooltip.show(mock_event)

        # Verify tooltip is visible after show
        mock_toplevel_instance.deiconify.assert_called_once()

        # Reset mock for hide test
        mock_toplevel_instance.reset_mock()

        # Test hide method with event
        tooltip.hide(mock_event)

        # Verify tooltip is hidden after hide
        mock_toplevel_instance.withdraw.assert_called_once()


def test_tooltip_macos_event_handling(mock_widget) -> None:
    """Test that tooltip properly handles Enter and Leave events on macOS."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"):
        # Create tooltip instance
        tooltip = Tooltip(mock_widget, "Test tooltip")

        # Verify the widget was bound to the correct events for macOS
        mock_widget.bind.assert_any_call("<Enter>", tooltip.create_show)
        mock_widget.bind.assert_any_call("<Leave>", tooltip.destroy_hide)

        # Verify tooltip is initially None on macOS
        assert tooltip.tooltip is None


def test_tooltip_position_tooltip_method(mock_widget) -> None:
    """Test the position_tooltip method directly."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel") as mock_toplevel,
    ):
        mock_toplevel_instance = MagicMock()
        mock_toplevel.return_value = mock_toplevel_instance

        # Test positioning below (default)
        tooltip = Tooltip(mock_widget, "Test tooltip")
        tooltip.position_tooltip()

        expected_x = mock_widget.winfo_rootx() + min(mock_widget.winfo_width() // 2, 100)
        expected_y = mock_widget.winfo_rooty() + mock_widget.winfo_height()
        mock_toplevel_instance.geometry.assert_called_with(f"+{expected_x}+{expected_y}")

        # Test positioning above
        tooltip_above = Tooltip(mock_widget, "Test tooltip", position_below=False)
        tooltip_above.position_tooltip()

        expected_y_above = mock_widget.winfo_rooty() - 10
        mock_toplevel_instance.geometry.assert_called_with(f"+{expected_x}+{expected_y_above}")


def test_tooltip_none_tooltip_edge_cases(mock_widget) -> None:
    """Test tooltip behavior when tooltip is None."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel") as mock_toplevel,
    ):
        mock_toplevel_instance = MagicMock()
        mock_toplevel.return_value = mock_toplevel_instance

        tooltip = Tooltip(mock_widget, "Test tooltip")

        # Set tooltip to None and test methods don't crash
        tooltip.tooltip = None

        # These should not raise exceptions
        tooltip.show()
        tooltip.hide()
        tooltip.position_tooltip()


def test_tooltip_show_tooltip_function_with_different_positions(mock_widget) -> None:
    """Test the show_tooltip function with different position parameters."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
        mock_tooltip_instance = MagicMock()
        mock_tooltip_class.return_value = mock_tooltip_instance

        # Test with position_below=True (default)
        tooltip1 = show_tooltip(mock_widget, "Test message 1")
        mock_tooltip_class.assert_called_with(mock_widget, "Test message 1", position_below=True)
        assert tooltip1 is mock_tooltip_instance

        # Reset mock for next test
        mock_tooltip_class.reset_mock()

        # Test with position_below=False
        tooltip2 = show_tooltip(mock_widget, "Test message 2", position_below=False)
        mock_tooltip_class.assert_called_with(mock_widget, "Test message 2", position_below=False)
        assert tooltip2 is mock_tooltip_instance


def test_tooltip_create_show_destroy_hide_macos_complete_cycle(mock_widget) -> None:
    """Test complete create/destroy cycle on macOS."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"),
        patch("tkinter.Toplevel") as mock_toplevel,
        patch("tkinter.ttk.Label") as mock_label,
    ):
        mock_toplevel_instance = MagicMock()
        mock_toplevel.return_value = mock_toplevel_instance

        tooltip = Tooltip(mock_widget, "Test tooltip")

        # Initially tooltip should be None on macOS
        assert tooltip.tooltip is None

        # Create and show tooltip
        tooltip.create_show()
        assert tooltip.tooltip is not None
        mock_toplevel.assert_called_once_with(mock_widget)
        mock_label.assert_called_once()

        # Destroy and hide tooltip
        tooltip.destroy_hide()
        assert tooltip.tooltip is None
        mock_toplevel_instance.destroy.assert_called_once()


def test_error_message_functions_comprehensive() -> None:
    """Test all error message functions comprehensively."""
    with (
        patch("tkinter.Tk") as mock_tk,
        patch("tkinter.messagebox.showerror") as mock_showerror,
        patch("tkinter.ttk.Style") as mock_style,  # noqa: F841 # pylint: disable=unused-variable
    ):
        mock_tk_instance = MagicMock()
        mock_tk.return_value = mock_tk_instance

        # Test show_error_message with special characters
        show_error_message("Test & Title", "Test\nMessage with & special < chars >")
        mock_tk.assert_called_once()
        mock_showerror.assert_called_once_with("Test & Title", "Test\nMessage with & special < chars >")
        mock_tk_instance.withdraw.assert_called_once()
        mock_tk_instance.destroy.assert_called_once()

        # Reset mocks
        mock_tk.reset_mock()
        mock_showerror.reset_mock()
        mock_tk_instance.reset_mock()

        # Test show_no_param_files_error
        show_no_param_files_error("test_directory")
        mock_tk.assert_called_once()
        expected_message = (
            "No intermediate parameter files found in the selected 'test_directory' vehicle directory.\n"
            "Please select and step inside a vehicle directory containing valid ArduPilot intermediate parameter files."
            "\n\nMake sure to step inside the directory (double-click) and not just select it."
        )
        mock_showerror.assert_called_once_with("No Parameter Files Found", expected_message)

        # Reset mocks
        mock_tk.reset_mock()
        mock_showerror.reset_mock()
        mock_tk_instance.reset_mock()

        # Test show_no_connection_error
        show_no_connection_error("Connection failed: timeout")
        mock_tk.assert_called_once()
        expected_message = (
            "Connection failed: timeout\n\nPlease connect a flight controller to the PC,\nwait at least 7 seconds and retry."
        )
        mock_showerror.assert_called_once_with("No Connection to the Flight Controller", expected_message)


def test_tooltip_darwin_handling(mock_widget) -> None:
    # Test macOS specific code paths
    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"):
        # Test the successful path
        with patch("tkinter.Toplevel") as mock_toplevel_class:
            # Set up the mock instance
            mock_toplevel_instance = MagicMock()
            mock_toplevel_class.return_value = mock_toplevel_instance

            # Create a tooltip and show it
            tooltip = Tooltip(mock_widget, "Test tooltip")
            tooltip.create_show()

            # Check that tk.call was called (don't check exact parameters)
            assert mock_toplevel_instance.tk.call.called

        # Test the AttributeError exception path with a separate patch
        with patch("tkinter.Toplevel") as mock_toplevel_class:
            # Set up the mock instance with exception
            mock_toplevel_instance = MagicMock()
            mock_toplevel_class.return_value = mock_toplevel_instance

            # We need to set side_effect only for the specific tk.call we're testing
            # First mock with a function that checks arguments
            def side_effect_function(*args) -> None:
                # Only raise AttributeError for the MacWindowStyle call
                if args and args[0] == "::tk::unsupported::MacWindowStyle":
                    raise AttributeError
                # For all other calls, return None or a default value

            mock_toplevel_instance.tk.call.side_effect = side_effect_function

            # Create a new tooltip and show it
            tooltip2 = Tooltip(mock_widget, "Test tooltip")
            tooltip2.create_show()

            # Check the fallback attributes were set
            mock_toplevel_instance.wm_attributes.assert_any_call("-alpha", 1.0)
            mock_toplevel_instance.wm_attributes.assert_any_call("-topmost", True)  # noqa: FBT003


def test_tooltip_non_darwin_handling(mock_widget) -> None:
    # Test non-macOS code path
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel") as mock_toplevel,
    ):
        mock_instance = MagicMock()
        mock_toplevel.return_value = mock_instance

        tooltip = Tooltip(mock_widget, "Test tooltip")
        tooltip.show()

        # Verify overrideredirect was called
        mock_instance.wm_overrideredirect.assert_called_with(boolean=True)


def test_tooltip_edge_case_empty_text(mock_widget) -> None:
    """Test tooltip with empty text."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel"),
    ):
        tooltip = Tooltip(mock_widget, "")
        assert tooltip.text == ""


def test_tooltip_edge_case_very_long_text(mock_widget) -> None:
    """Test tooltip with very long text."""
    long_text = "This is a very long tooltip text " * 100
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel"),
    ):
        tooltip = Tooltip(mock_widget, long_text)
        assert tooltip.text == long_text


def test_tooltip_edge_case_special_characters(mock_widget) -> None:
    """Test tooltip with special characters and unicode."""
    special_text = 'Test with ñ, é, ü, ™, ©, €, 🚁, <>&"'
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel"),
    ):
        tooltip = Tooltip(mock_widget, special_text)
        assert tooltip.text == special_text


def test_tooltip_position_calculation_edge_cases(mock_widget) -> None:
    """Test tooltip positioning with edge case widget dimensions."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel") as mock_toplevel,
    ):
        mock_toplevel_instance = MagicMock()
        mock_toplevel.return_value = mock_toplevel_instance

        # Test with very small widget
        mock_widget.winfo_width.return_value = 1
        mock_widget.winfo_height.return_value = 1
        mock_widget.winfo_rootx.return_value = 0
        mock_widget.winfo_rooty.return_value = 0

        tooltip = Tooltip(mock_widget, "Test")
        tooltip.position_tooltip()

        # Width is 1, so min(1//2, 100) = min(0, 100) = 0
        expected_x = 0 + 0  # rootx + min(width//2, 100)
        expected_y = 0 + 1  # rooty + height (position_below=True)
        mock_toplevel_instance.geometry.assert_called_with(f"+{expected_x}+{expected_y}")

        # Test with very large widget
        mock_widget.winfo_width.return_value = 1000
        mock_widget.winfo_height.return_value = 500
        mock_widget.winfo_rootx.return_value = 100
        mock_widget.winfo_rooty.return_value = 200

        tooltip.position_tooltip()

        # Width is 1000, so min(1000//2, 100) = min(500, 100) = 100
        expected_x = 100 + 100  # rootx + min(width//2, 100)
        expected_y = 200 + 500  # rooty + height
        mock_toplevel_instance.geometry.assert_called_with(f"+{expected_x}+{expected_y}")


def test_tooltip_macos_exception_handling_comprehensive(mock_widget) -> None:
    """Test comprehensive exception handling on macOS."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Darwin"),
        patch("tkinter.Toplevel") as mock_toplevel_class,
    ):
        mock_toplevel_instance = MagicMock()
        mock_toplevel_class.return_value = mock_toplevel_instance

        # Test different types of exceptions that might occur
        def tk_call_side_effect(*args) -> None:
            if args and args[0] == "::tk::unsupported::MacWindowStyle":
                msg = "MacWindowStyle not supported"
                raise AttributeError(msg)

        mock_toplevel_instance.tk.call.side_effect = tk_call_side_effect

        tooltip = Tooltip(mock_widget, "Test tooltip")
        tooltip.create_show()

        # Verify fallback attributes were set
        mock_toplevel_instance.wm_attributes.assert_any_call("-alpha", 1.0)
        mock_toplevel_instance.wm_attributes.assert_any_call("-topmost", True)  # noqa: FBT003
        mock_toplevel_instance.configure.assert_called_with(bg="#ffffe0")


def test_error_functions_with_extreme_inputs() -> None:
    """Test error functions with extreme inputs."""
    with (
        patch("tkinter.Tk") as mock_tk,
        patch("tkinter.messagebox.showerror") as mock_showerror,
        patch("tkinter.ttk.Style"),
    ):
        mock_tk_instance = MagicMock()
        mock_tk.return_value = mock_tk_instance

        # Test with empty strings
        show_error_message("", "")
        mock_showerror.assert_called_with("", "")

        # Test with very long strings
        long_title = "A" * 1000
        long_message = "B" * 10000
        show_error_message(long_title, long_message)
        mock_showerror.assert_called_with(long_title, long_message)

        # Test with None-like empty directory
        show_no_param_files_error("")
        assert mock_showerror.called

        # Test with special path characters
        show_no_param_files_error("C:\\Program Files\\Test & Dir\\")
        assert mock_showerror.called


def test_tooltip_multiple_instances(mock_widget) -> None:
    """Test creating multiple tooltip instances."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.platform_system", return_value="Windows"),
        patch("tkinter.Toplevel"),
    ):
        # Create multiple tooltips for the same widget
        tooltip1 = Tooltip(mock_widget, "Tooltip 1")
        tooltip2 = Tooltip(mock_widget, "Tooltip 2")
        tooltip3 = Tooltip(mock_widget, "Tooltip 3", position_below=False)

        assert tooltip1.text == "Tooltip 1"
        assert tooltip2.text == "Tooltip 2"
        assert tooltip3.text == "Tooltip 3"
        assert tooltip1.position_below is True
        assert tooltip2.position_below is True
        assert tooltip3.position_below is False


def test_show_tooltip_function_stress_test(mock_widget) -> None:
    """Stress test the show_tooltip function."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip") as mock_tooltip_class:
        mock_instances = []

        # Create multiple tooltips rapidly
        for i in range(10):
            mock_instance = MagicMock()
            mock_instances.append(mock_instance)
            mock_tooltip_class.return_value = mock_instance

            tooltip = show_tooltip(mock_widget, f"Tooltip {i}", position_below=i % 2 == 0)
            assert tooltip is mock_instance

            # Verify correct call
            expected_position = i % 2 == 0
            mock_tooltip_class.assert_called_with(mock_widget, f"Tooltip {i}", position_below=expected_position)
            mock_tooltip_class.reset_mock()
