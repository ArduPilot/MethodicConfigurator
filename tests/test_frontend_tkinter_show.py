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

# pylint: disable=redefined-outer-name


from ardupilot_methodic_configurator.frontend_tkinter_show import (
    Tooltip,
    show_error_message,
    show_no_connection_error,
    show_no_param_files_error,
    show_tooltip,
)


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
    # Call the function with test parameters
    tooltip = show_tooltip(mock_widget, "Test Tooltip Message")

    # Check that tooltip object was created and is a Tooltip instance
    assert tooltip is not None
    assert isinstance(tooltip, Tooltip)

    # Verify bindings were created
    mock_widget.bind.assert_any_call("<Enter>", tooltip.show)
    mock_widget.bind.assert_any_call("<Leave>", tooltip.hide)


# Tests for Tooltip class
def test_tooltip_init(mock_widget) -> None:
    tooltip = Tooltip(mock_widget, "Test tooltip text")

    # Verify attribute initialization
    assert tooltip.widget == mock_widget
    assert tooltip.text == "Test tooltip text"
    assert tooltip.tooltip is None
    assert tooltip.position_below is True

    # Verify event bindings
    mock_widget.bind.assert_any_call("<Enter>", tooltip.show)
    mock_widget.bind.assert_any_call("<Leave>", tooltip.hide)


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


def test_tooltip_hide(mock_widget, mock_toplevel) -> None:
    _, mock_toplevel_instance = mock_toplevel

    tooltip = Tooltip(mock_widget, "Test tooltip")
    tooltip.show()

    # Verify tooltip created
    assert tooltip.tooltip is not None

    # Now hide the tooltip
    tooltip.hide()

    # Verify tooltip destroyed
    mock_toplevel_instance.destroy.assert_called_once()
    assert tooltip.tooltip is None


def test_tooltip_show_hide_event_handling(mock_widget) -> None:
    # Create mock event and patch Tooltip class before creating instance
    mock_event = MagicMock()

    # Use autospec to ensure method signatures are checked
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip.show", autospec=True) as mock_show,
        patch("ardupilot_methodic_configurator.frontend_tkinter_show.Tooltip.hide", autospec=True) as mock_hide,
    ):
        # Create tooltip after patching the methods
        tooltip = Tooltip(mock_widget, "Test tooltip")

        # Get the bound methods
        enter_callback = mock_widget.bind.call_args_list[0][0][1]
        leave_callback = mock_widget.bind.call_args_list[1][0][1]

        # Reset the mocks to clear the call_args from initialization
        mock_show.reset_mock()
        mock_hide.reset_mock()

        # Manually call the callbacks with the mock event
        enter_callback(mock_event)
        leave_callback(mock_event)

        # Verify our mocked methods were called with the correct arguments
        # The first arg is self (the tooltip instance)
        mock_show.assert_called_once_with(tooltip, mock_event)
        mock_hide.assert_called_once_with(tooltip, mock_event)


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
            tooltip.show()

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
            tooltip2.show()

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
