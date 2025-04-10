#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_flightcontroller_info.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from typing import NoReturn
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import FlightControllerInfoWindow

# pylint: disable=redefined-outer-name,unused-argument,protected-access
# ruff: noqa: ARG001, ARG005


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


@pytest.fixture
def mock_tk_classes() -> Generator[dict[str, MagicMock], None, None]:
    """Mock various tkinter classes and methods."""
    with (
        patch("tkinter.Toplevel", return_value=MagicMock()) as tk_toplevel,
        patch("tkinter.Tk", return_value=MagicMock()) as tk_instance,
        patch("tkinter.ttk.Frame", return_value=MagicMock()) as frame,
        patch("tkinter.ttk.Label", return_value=MagicMock()) as label,
        patch("tkinter.ttk.Entry", return_value=MagicMock()) as entry,
        patch("tkinter.ttk.Style", return_value=MagicMock()) as style,
        patch("tkinter.PhotoImage", return_value=MagicMock()) as photoimage,
        patch("tkinter.Tk.mainloop") as mainloop,
        patch("tkinter.Tk.after") as after,
        patch("PIL.ImageTk.PhotoImage", return_value=MagicMock()) as imagetk,
        patch("PIL.Image.open", return_value=MagicMock(size=(100, 100))) as image_open,
    ):
        yield {
            "tk_toplevel": tk_toplevel,
            "tk_instance": tk_instance,
            "frame": frame,
            "label": label,
            "entry": entry,
            "style": style,
            "photoimage": photoimage,
            "mainloop": mainloop,
            "after": after,
            "imagetk": imagetk,
            "image_open": image_open,
        }


@pytest.fixture
def mock_logging() -> Generator[dict[str, MagicMock], None, None]:
    """Set up mocks for logging functions."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.logging_error") as mock_error,
        patch("ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.logging_error") as mock_fc_error,
        patch("ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.logging_info") as mock_fc_info,
    ):
        yield {"error": mock_error, "fc_error": mock_fc_error, "fc_info": mock_fc_info}


@pytest.fixture
def mock_progress_window() -> MagicMock:
    """Provide a mock ProgressWindow."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow") as mock_pw_class:
        mock_instance = MagicMock()
        mock_pw_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def setup_window_with_mocks(monkeypatch, mock_flight_controller, mock_tk_classes) -> FlightControllerInfoWindow:
    """Set up a FlightControllerInfoWindow with all necessary mocks."""
    # Avoid tkinter initialization
    monkeypatch.setattr(BaseWindow, "__init__", lambda self, root_tk=None: None)

    # Mock LocalFilesystem for the icon
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.application_icon_filepath",
        lambda: "mock_path/icon.png",
    )

    # Create a window without calling __init__ to avoid tkinter issues
    window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
    window.root = MagicMock()
    window.main_frame = MagicMock()
    window.flight_controller = mock_flight_controller
    window.param_default_values = {}
    window.info_frame = MagicMock()

    return window


def test_init_basic_properties(monkeypatch, mock_flight_controller, mock_tk_classes) -> None:
    """Test basic properties after initialization."""
    # Mock BaseWindow.__init__ to avoid tkinter initialization
    init_called = False

    def mock_init(self, root_tk=None) -> None:
        nonlocal init_called
        init_called = True
        self.root = MagicMock()
        self.main_frame = MagicMock()

    monkeypatch.setattr(BaseWindow, "__init__", mock_init)
    monkeypatch.setattr("ardupilot_methodic_configurator.__version__", "1.0.0")

    # Patch methods that would be called during initialization
    with (
        patch.object(FlightControllerInfoWindow, "_init_ui"),
        patch.object(FlightControllerInfoWindow, "_log_flight_controller_info"),
        patch("tkinter.Tk.after"),
    ):
        window = FlightControllerInfoWindow(mock_flight_controller)

        # Check initialization of basic properties
        assert window.flight_controller == mock_flight_controller
        assert window.param_default_values == {}
        assert init_called
        window.root.title.assert_called_once()
        window.root.geometry.assert_called_once_with("500x350")


def test_init_ui_and_create_info_fields(monkeypatch, mock_flight_controller) -> None:
    """Test UI initialization and info field creation."""
    mock_frame = MagicMock()
    mock_label = MagicMock()
    mock_entry = MagicMock()

    # Set up mock for ttk.Frame, Label and Entry
    monkeypatch.setattr("tkinter.ttk.Frame", lambda *args, **kwargs: mock_frame)
    monkeypatch.setattr("tkinter.ttk.Label", lambda *args, **kwargs: mock_label)
    monkeypatch.setattr("tkinter.ttk.Entry", lambda *args, **kwargs: mock_entry)

    # Create a partial window without calling __init__
    window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
    window.main_frame = MagicMock()
    window.flight_controller = mock_flight_controller
    window.param_default_values = {}

    # Call the methods we're testing
    window._init_ui()

    # Check that frame was created and packed
    assert window.info_frame == mock_frame
    mock_frame.pack.assert_called_once()
    mock_frame.columnconfigure.assert_called_once_with(1, weight=1)


def test_download_flight_controller_parameters_with_progress_callback(setup_window_with_mocks) -> None:
    """Test downloading parameters with a provided progress callback."""
    window = setup_window_with_mocks

    # Set up mock parameters and default values
    mock_params = {"PARAM1": 100, "PARAM2": 200}
    mock_defaults = {"PARAM1": Par("PARAM1", 50), "PARAM2": Par("PARAM2", 100)}
    window.flight_controller.download_params.return_value = (mock_params, mock_defaults)

    # Create a mock progress callback
    mock_callback = MagicMock()

    # Call the method with the mock callback
    window.download_flight_controller_parameters(mock_callback)

    # Verify the callback was used
    window.flight_controller.download_params.assert_called_once_with(mock_callback)

    # Verify parameters were stored
    assert window.flight_controller.fc_parameters == mock_params
    assert window.param_default_values == mock_defaults


def test_download_flight_controller_parameters_with_progress_window(setup_window_with_mocks, mock_progress_window) -> None:
    """Test downloading parameters using the progress window."""
    window = setup_window_with_mocks

    # Set up mock parameters and default values
    mock_params = {"PARAM1": 100, "PARAM2": 200}
    mock_defaults = {"PARAM1": Par("PARAM1", 50), "PARAM2": Par("PARAM2", 100)}
    window.flight_controller.download_params.return_value = (mock_params, mock_defaults)

    # Call the method without a callback (should use progress window)
    window.download_flight_controller_parameters()

    # Verify the progress window was created and used
    window.flight_controller.download_params.assert_called_once_with(mock_progress_window.update_progress_bar)
    mock_progress_window.destroy.assert_called_once()

    # Verify parameters were stored
    assert window.flight_controller.fc_parameters == mock_params
    assert window.param_default_values == mock_defaults


def test_download_flight_controller_parameters_error_handling(
    setup_window_with_mocks, mock_progress_window, mock_logging
) -> None:
    """Test error handling in download_flight_controller_parameters method."""
    window = setup_window_with_mocks

    # Make download_params raise an exception
    error_msg = "Download failed"
    window.flight_controller.download_params.side_effect = RuntimeError(error_msg)

    # Test method with progress window (no callback)
    with pytest.raises(RuntimeError, match=error_msg):
        window.download_flight_controller_parameters()

    # Assert progress window was destroyed even when exception occurs
    mock_progress_window.destroy.assert_called_once()
    mock_logging["fc_error"].assert_called_once()

    # Reset mocks for testing with callback
    window.flight_controller.download_params.reset_mock()
    mock_logging["fc_error"].reset_mock()

    # Test with callback
    mock_callback = MagicMock()
    with pytest.raises(RuntimeError, match=error_msg):
        window.download_flight_controller_parameters(mock_callback)

    # Verify callback was used
    window.flight_controller.download_params.assert_called_once_with(mock_callback)
    mock_logging["fc_error"].assert_called_once()


def test_schedule_download_parameters(monkeypatch, setup_window_with_mocks) -> None:
    """Test parameter download scheduling."""
    window = setup_window_with_mocks

    # Mock download method and root.destroy
    mock_download = MagicMock()
    monkeypatch.setattr(window, "download_flight_controller_parameters", mock_download)

    # Test successful download
    window._schedule_download_parameters()

    # Verify download was called and window was destroyed
    mock_download.assert_called_once()
    window.root.destroy.assert_called_once()

    # Reset mocks
    mock_download.reset_mock()
    window.root.destroy.reset_mock()

    # Test with exception
    mock_download.side_effect = RuntimeError("Download error")

    # Run function
    window._schedule_download_parameters()

    # Verify window was destroyed even after exception
    mock_download.assert_called_once()
    window.root.destroy.assert_called_once()


def test_run_method(setup_window_with_mocks) -> None:
    """Test the run method starts the mainloop."""
    window = setup_window_with_mocks

    # Call run method
    window.run()

    # Verify mainloop was called
    window.root.mainloop.assert_called_once()


def test_log_flight_controller_info(setup_window_with_mocks, mock_logging) -> None:
    """Test that flight controller information is properly logged."""
    window = setup_window_with_mocks

    # Call the logging method
    window._log_flight_controller_info()

    # Verify logging calls were made (should be 7 calls for the 7 info items)
    assert mock_logging["fc_info"].call_count == 7


def test_get_param_default_values(setup_window_with_mocks) -> None:
    """Test get_param_default_values method."""
    window = setup_window_with_mocks

    # Setup test data
    test_defaults = {"PARAM1": Par("PARAM1", 50), "PARAM2": Par("PARAM2", 100)}
    window.param_default_values = test_defaults

    # Test the getter method
    result = window.get_param_default_values()

    # Assert result is correct
    assert result == test_defaults


def test_create_info_fields(monkeypatch, setup_window_with_mocks) -> None:
    """Test that info fields are created correctly based on flight controller information."""
    window = setup_window_with_mocks
    window.info_frame = MagicMock()

    # Track UI element creation and values
    label_calls = 0
    entry_calls = 0
    entry_values = []
    MagicMock()

    # Mock Label and Entry
    def mock_label(*args, **kwargs) -> MagicMock:
        nonlocal label_calls
        label_calls += 1
        return MagicMock()

    def mock_entry(*args, **kwargs) -> MagicMock:
        nonlocal entry_calls, entry_values
        entry_calls += 1

        # Create new mock for each call
        mock = MagicMock()

        # Add insert method to track values
        def mock_insert(_, value) -> None:
            entry_values.append(value)

        mock.insert = mock_insert
        return mock

    # Apply patches
    monkeypatch.setattr("tkinter.ttk.Label", mock_label)
    monkeypatch.setattr("tkinter.ttk.Entry", mock_entry)

    # Call method
    window._create_info_fields()

    # Check number of elements created (should match info dict size)
    info_dict_size = len(window.flight_controller.info.get_info())
    assert label_calls == info_dict_size
    assert entry_calls == info_dict_size

    # Check that values were inserted
    assert len(entry_values) == info_dict_size
    for value in window.flight_controller.info.get_info().values():
        if isinstance(value, dict):
            assert (", ").join(value.keys()) in entry_values
        elif value:
            assert value in entry_values
        else:
            assert "N/A" in entry_values


@pytest.mark.parametrize(
    ("info_dict", "expected_grid_calls", "expected_values"),
    [
        (
            {"FC Firmware Version": "ArduPlane 4.3.0-dev", "FC Hardware": "CubeOrange"},
            2,  # Expect two rows of labels and entries
            ["ArduPlane 4.3.0-dev", "CubeOrange"],
        ),
        (
            {"FC Firmware Version": "ArduPlane 4.3.0-dev", "FC Hardware": "CubeOrange", "Extra Info": "Some Value"},
            3,  # Expect three rows
            ["ArduPlane 4.3.0-dev", "CubeOrange", "Some Value"],
        ),
        (
            {"Empty Value": ""},
            1,  # One row with N/A for empty value
            ["N/A"],
        ),
        (
            {"Dict Value": {"key1": "value1", "key2": "value2"}},
            1,  # One row with combined keys
            ["key1, key2"],
        ),
    ],
)
def test_info_display_with_different_values(
    monkeypatch, mock_flight_controller, info_dict, expected_grid_calls, expected_values
) -> None:
    """Test that flight controller info is displayed correctly with different input values."""
    # Update mock to return the test info dictionary
    mock_flight_controller.info.get_info.return_value = info_dict

    # Track UI element creation and values
    label_calls = 0
    entry_calls = 0
    entry_values = []

    # Mock Label and Entry
    def mock_label(*args, **kwargs) -> MagicMock:
        nonlocal label_calls
        label_calls += 1
        return MagicMock()

    def mock_entry(*args, **kwargs) -> MagicMock:
        nonlocal entry_calls, entry_values
        entry_calls += 1
        mock = MagicMock()

        # Track values
        def mock_insert(_, value) -> None:
            entry_values.append(value)

        mock.insert = mock_insert
        return mock

    # Apply patches
    monkeypatch.setattr("tkinter.ttk.Label", mock_label)
    monkeypatch.setattr("tkinter.ttk.Entry", mock_entry)

    # Create partial window
    window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
    window.info_frame = MagicMock()
    window.flight_controller = mock_flight_controller
    window.param_default_values = {}

    # Call the method
    window._create_info_fields()

    # Check UI elements
    assert label_calls == expected_grid_calls
    assert entry_calls == expected_grid_calls

    # Check entry values
    for value in expected_values:
        assert value in entry_values


def test_center_window() -> None:
    """Test the center_window method from BaseWindow."""
    # Create mock windows
    mock_window = MagicMock()
    mock_parent = MagicMock()

    # Set up mock window attributes
    mock_window.winfo_width.return_value = 400
    mock_window.winfo_height.return_value = 300
    mock_parent.winfo_width.return_value = 800
    mock_parent.winfo_height.return_value = 600
    mock_parent.winfo_x.return_value = 100
    mock_parent.winfo_y.return_value = 100

    # Call the method
    BaseWindow.center_window(mock_window, mock_parent)

    # Check that geometry was called with the right parameters
    expected_x = 100 + (800 // 2) - (400 // 2)  # parent_x + (parent_width // 2) - (window_width // 2)
    expected_y = 100 + (600 // 2) - (300 // 2)  # parent_y + (parent_height // 2) - (window_height // 2)
    mock_window.geometry.assert_called_once_with(f"+{expected_x}+{expected_y}")


def test_put_image_in_label(monkeypatch) -> None:
    """Test the put_image_in_label method from BaseWindow."""
    # Mock required objects
    mock_parent = MagicMock()
    mock_image = MagicMock()
    mock_image.size = (100, 100)
    mock_image.resize.return_value = mock_image

    mock_photo = MagicMock()
    mock_label = MagicMock()

    # Apply monkeypatches
    monkeypatch.setattr("PIL.Image.open", lambda _: mock_image)
    monkeypatch.setattr("PIL.ImageTk.PhotoImage", lambda _: mock_photo)
    monkeypatch.setattr("tkinter.ttk.Label", lambda parent, image=None: mock_label)

    # Call the method
    result = BaseWindow.put_image_in_label(mock_parent, "test_image.png", image_height=40)

    # Check results
    assert result == mock_label
    mock_image.resize.assert_called_once_with((40, 40))  # Should resize to maintain aspect ratio
    assert hasattr(result, "image")
    assert result.image == mock_photo


def test_put_image_in_label_error_handling(monkeypatch) -> None:
    """Test error handling in put_image_in_label method from BaseWindow."""
    # Mock required objects
    mock_parent = MagicMock()
    mock_image = MagicMock()
    mock_image.size = (100, 100)
    mock_image.resize.return_value = mock_image

    mock_label = MagicMock()

    # Apply monkeypatches
    monkeypatch.setattr("PIL.Image.open", lambda _: mock_image)

    # Mock TypeError when calling PhotoImage
    def mock_photo_image(_) -> NoReturn:
        msg = "Mock error"
        raise TypeError(msg)

    # Create a mock for logging_error
    mock_logging_error = MagicMock()

    monkeypatch.setattr("PIL.ImageTk.PhotoImage", mock_photo_image)
    monkeypatch.setattr("tkinter.ttk.Label", lambda parent, image=None: mock_label)
    monkeypatch.setattr("ardupilot_methodic_configurator.frontend_tkinter_base_window.logging_error", mock_logging_error)

    # Call the method
    result = BaseWindow.put_image_in_label(mock_parent, "test_image.png")

    # Check that logging_error was called and a label was returned
    assert result == mock_label
    mock_logging_error.assert_called_once()
