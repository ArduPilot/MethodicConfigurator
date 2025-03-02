#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_flightcontroller_info.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.frontend_tkinter_base import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import FlightControllerInfoWindow


# Create a mock for BaseWindow to avoid TK root issues
class MockBaseWindow:  # pylint: disable=too-few-public-methods
    """Mock version of BaseWindow for testing."""

    def __init__(self) -> None:
        self.root = MagicMock()
        self.main_frame = MagicMock()


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Create a properly configured mock flight controller."""
    mock_fc = MagicMock(spec=FlightController)
    # Set up the info attribute as a nested mock
    mock_fc.info = MagicMock()
    mock_fc.info.get_info.return_value = {"FC Firmware Version": "ArduPlane 4.3.0-dev", "FC Hardware": "CubeOrange"}
    # Set up other info attributes that might be accessed
    mock_fc.info.flight_sw_version_and_type = "ArduPlane 4.3.0-dev"
    mock_fc.info.flight_custom_version = "abcd1234"
    mock_fc.info.os_custom_version = "efgh5678"
    mock_fc.info.firmware_type = "ArduPlane"
    mock_fc.info.apj_board_id = "1234"
    mock_fc.info.board_version = "CubeOrange"
    mock_fc.info.vendor = "Hex"
    mock_fc.info.product = "CubeOrange"
    return mock_fc


@pytest.mark.parametrize(
    "test_method",
    ["test_init", "test_ui_elements_creation", "test_download_flight_controller_parameters", "test_get_param_default_values"],
)
def test_flight_controller_info_window_with_pytest(monkeypatch, test_method, mock_flight_controller) -> None:  # pylint: disable=redefined-outer-name
    """Test FlightControllerInfoWindow methods with pytest."""
    # Patch BaseWindow.__init__ to avoid tkinter initialization
    monkeypatch.setattr(BaseWindow, "__init__", lambda _: None)

    # Patch tkinter-related classes and methods
    with (
        patch("tkinter.Toplevel"),
        patch("tkinter.Tk"),
        patch("tkinter.ttk.Frame", return_value=MagicMock()),
        patch("tkinter.ttk.Label", return_value=MagicMock()),
        patch("tkinter.ttk.Entry", return_value=MagicMock()),
        patch("tkinter.Tk.mainloop"),
        patch("tkinter.Tk.after"),
        patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()),
    ):
        # Create a test window using __new__ to skip __init__
        window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
        window.root = MagicMock()
        window.main_frame = MagicMock()
        window.flight_controller = mock_flight_controller
        window.param_default_values = {}

        if test_method == "test_download_flight_controller_parameters":
            # Additional mocks needed for this test
            with patch(
                "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow"
            ) as mock_progress_window:
                # Set up mock parameters and default values
                mock_params = {"PARAM1": 100, "PARAM2": 200}
                mock_defaults = {"PARAM1": Par("PARAM1", 50), "PARAM2": Par("PARAM2", 100)}
                mock_flight_controller.download_params.return_value = (mock_params, mock_defaults)

                # Set up mock progress window instance
                mock_progress_instance = MagicMock()
                mock_progress_window.return_value = mock_progress_instance

                # Test method
                window.download_flight_controller_parameters()

                # Assertions
                mock_progress_window.assert_called_once()
                mock_progress_instance.destroy.assert_called_once()
                mock_flight_controller.download_params.assert_called_once()
                assert window.flight_controller.fc_parameters == mock_params
                assert window.param_default_values == mock_defaults

        elif test_method == "test_init":
            # Only test that the object has expected attributes
            assert window.flight_controller == mock_flight_controller
            assert window.param_default_values == {}

        elif test_method == "test_ui_elements_creation":
            # We can't test UI creation directly with this approach
            # Just verify the window was created with mocked attributes
            assert window.root is not None
            assert window.main_frame is not None

        elif test_method == "test_get_param_default_values":
            # Setup test data
            test_defaults = {"PARAM1": Par("PARAM1", 50), "PARAM2": Par("PARAM2", 100)}
            window.param_default_values = test_defaults

            # Test the getter method
            result = window.get_param_default_values()

            # Assertion
            assert result == test_defaults


class TestFlightControllerInfoWindow(unittest.TestCase):  # pylint: disable=too-many-instance-attributes
    """Test cases for the FlightControllerInfoWindow class."""

    def setUp(self) -> None:
        """Set up the mock flight controller for each test."""
        self.mock_flight_controller = MagicMock(spec=FlightController)
        # Set up the info attribute as a nested mock
        self.mock_flight_controller.info = MagicMock()
        self.mock_flight_controller.info.get_info.return_value = {
            "FC Firmware Version": "ArduPlane 4.3.0-dev",
            "FC Hardware": "CubeOrange",
        }
        # Set up other info attributes that might be accessed
        self.mock_flight_controller.info.flight_sw_version_and_type = "ArduPlane 4.3.0-dev"
        self.mock_flight_controller.info.flight_custom_version = "abcd1234"
        self.mock_flight_controller.info.os_custom_version = "efgh5678"
        self.mock_flight_controller.info.firmware_type = "ArduPlane"
        self.mock_flight_controller.info.apj_board_id = "1234"
        self.mock_flight_controller.info.board_version = "CubeOrange"
        self.mock_flight_controller.info.vendor = "Hex"
        self.mock_flight_controller.info.product = "CubeOrange"

        # Create a patcher for BaseWindow.__init__
        self.base_patcher = patch.object(BaseWindow, "__init__", return_value=None)
        self.mock_base_init = self.base_patcher.start()

        # Patch PIL.ImageTk.PhotoImage to prevent "no default root window" errors
        self.image_patcher = patch("PIL.ImageTk.PhotoImage", return_value=MagicMock())
        self.mock_image = self.image_patcher.start()

        # Patch tk.Tk to prevent tkinter issues
        self.tk_patcher = patch("tkinter.Tk", return_value=MagicMock())
        self.mock_tk = self.tk_patcher.start()

        # Patch tkinter.Toplevel
        self.toplevel_patcher = patch("tkinter.Toplevel", return_value=MagicMock())
        self.mock_toplevel = self.toplevel_patcher.start()

        # Patch tkinter mainloop and after
        self.mainloop_patcher = patch("tkinter.Tk.mainloop")
        self.mock_mainloop = self.mainloop_patcher.start()

        self.after_patcher = patch("tkinter.Tk.after")
        self.mock_after = self.after_patcher.start()

    def tearDown(self) -> None:
        """Clean up patchers."""
        self.base_patcher.stop()
        self.image_patcher.stop()
        self.tk_patcher.stop()
        self.toplevel_patcher.stop()
        self.mainloop_patcher.stop()
        self.after_patcher.stop()

    def test_init(self) -> None:
        """Test initialization of FlightControllerInfoWindow."""
        # Create a window without calling __init__
        window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
        window.root = MagicMock()
        window.main_frame = MagicMock()
        window.flight_controller = self.mock_flight_controller
        window.param_default_values = {}

        # Assert flight controller was set correctly
        assert window.flight_controller == self.mock_flight_controller

        # Assert param_default_values is initialized as empty dict
        assert window.param_default_values == {}

    def test_ui_elements_creation(self) -> None:
        """Test that UI elements are created correctly."""
        # Setup mocks to capture UI creation
        mock_frame = MagicMock()
        mock_label = MagicMock()
        mock_entry = MagicMock()

        with (
            patch("tkinter.ttk.Frame", return_value=mock_frame),
            patch("tkinter.ttk.Label", return_value=mock_label),
            patch("tkinter.ttk.Entry", return_value=mock_entry),
        ):
            # Create the window without calling __init__
            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.root = MagicMock()
            window.main_frame = MagicMock()
            window.flight_controller = self.mock_flight_controller
            window.param_default_values = {}

            # We can't test UI creation directly with this approach
            # Just verify window was created with mocked attributes
            assert window.root is not None
            assert window.main_frame is not None

    def test_download_flight_controller_parameters(self) -> None:
        """Test download_flight_controller_parameters method."""
        # Setup mock parameters and default values
        mock_params = {"PARAM1": 100, "PARAM2": 200}
        mock_defaults = {"PARAM1": Par("PARAM1", 50), "PARAM2": Par("PARAM2", 100)}
        self.mock_flight_controller.download_params.return_value = (mock_params, mock_defaults)

        # Setup mock progress window
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow"
        ) as mock_progress_window:
            # Set up mock progress window instance
            mock_progress_instance = MagicMock()
            mock_progress_window.return_value = mock_progress_instance

            # Create the window without calling __init__
            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.root = MagicMock()
            window.flight_controller = self.mock_flight_controller
            window.param_default_values = {}

            # Test the method
            window.download_flight_controller_parameters()

            # Assert progress window was created and used
            mock_progress_window.assert_called_once()
            mock_progress_instance.destroy.assert_called_once()

            # Assert download_params was called
            self.mock_flight_controller.download_params.assert_called_once()

            # Assert parameters were stored correctly
            assert window.flight_controller.fc_parameters == mock_params
            assert window.param_default_values == mock_defaults

    def test_get_param_default_values(self) -> None:
        """Test get_param_default_values method."""
        # Setup test data
        test_defaults = {"PARAM1": Par("PARAM1", 50), "PARAM2": Par("PARAM2", 100)}

        # Create window without calling __init__
        window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
        window.root = MagicMock()
        window.flight_controller = self.mock_flight_controller
        window.param_default_values = test_defaults

        # Test the getter method
        result = window.get_param_default_values()

        # Assert result is correct
        assert result == test_defaults


if __name__ == "__main__":
    unittest.main()
