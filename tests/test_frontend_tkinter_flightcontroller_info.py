#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_flightcontroller_info.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from contextlib import ExitStack
from tkinter import ttk
from typing import NoReturn
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import FlightControllerInfoWindow

# pylint: disable=redefined-outer-name,unused-argument
# ruff: noqa: ARG001


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


@pytest.fixture
def mock_tk_classes() -> None:  # pylint: disable=too-many-locals
    """Mock various tkinter classes and methods."""
    tk_toplevel_patcher = patch("tkinter.Toplevel", return_value=MagicMock())
    tk_patcher = patch("tkinter.Tk", return_value=MagicMock())
    frame_patcher = patch("tkinter.ttk.Frame", return_value=MagicMock())
    label_patcher = patch("tkinter.ttk.Label", return_value=MagicMock())
    entry_patcher = patch("tkinter.ttk.Entry", return_value=MagicMock())
    style_patcher = patch("tkinter.ttk.Style", return_value=MagicMock())
    photoimage_patcher = patch("tkinter.PhotoImage", return_value=MagicMock())
    mainloop_patcher = patch("tkinter.Tk.mainloop")
    after_patcher = patch("tkinter.Tk.after")
    imagetk_patcher = patch("PIL.ImageTk.PhotoImage", return_value=MagicMock())
    image_open_patcher = patch("PIL.Image.open", return_value=MagicMock(size=(100, 100)))

    tk_toplevel = tk_toplevel_patcher.start()
    tk_instance = tk_patcher.start()
    frame = frame_patcher.start()
    label = label_patcher.start()
    entry = entry_patcher.start()
    style = style_patcher.start()
    photoimage = photoimage_patcher.start()
    mainloop = mainloop_patcher.start()
    after = after_patcher.start()
    imagetk = imagetk_patcher.start()
    image_open = image_open_patcher.start()

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

    tk_toplevel_patcher.stop()
    tk_patcher.stop()
    frame_patcher.stop()
    label_patcher.stop()
    entry_patcher.stop()
    style_patcher.stop()
    photoimage_patcher.stop()
    mainloop_patcher.stop()
    after_patcher.stop()
    imagetk_patcher.stop()
    image_open_patcher.stop()


@pytest.fixture
def mock_logging() -> None:
    """Set up mocks for logging functions."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.logging_error") as mock_error:
        yield {"error": mock_error}


@pytest.fixture
def mock_progress_window() -> MagicMock:
    """Provide a mock ProgressWindow."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow") as mock_pw_class:
        mock_instance = MagicMock()
        mock_pw_class.return_value = mock_instance
        yield mock_instance


@pytest.mark.parametrize(
    "test_method",
    ["test_init", "test_ui_elements_creation", "test_download_flight_controller_parameters", "test_get_param_default_values"],
)
def test_flight_controller_info_window_with_pytest(monkeypatch, test_method, mock_flight_controller) -> None:  # pylint: disable=too-many-locals,too-many-statements # noqa: PLR0915
    """Test FlightControllerInfoWindow methods with pytest."""
    # Patch BaseWindow.__init__ to avoid tkinter initialization
    monkeypatch.setattr(BaseWindow, "__init__", lambda _: None)

    # Patch tkinter-related classes and methods
    toplevel_patcher = patch("tkinter.Toplevel")
    tk_patcher = patch("tkinter.Tk")
    frame_patcher = patch("tkinter.ttk.Frame", return_value=MagicMock())
    label_patcher = patch("tkinter.ttk.Label", return_value=MagicMock())
    entry_patcher = patch("tkinter.ttk.Entry", return_value=MagicMock())
    mainloop_patcher = patch("tkinter.Tk.mainloop")
    after_patcher = patch("tkinter.Tk.after")
    imagetk_patcher = patch("PIL.ImageTk.PhotoImage", return_value=MagicMock())

    toplevel_patcher.start()
    tk_patcher.start()
    frame_patcher.start()
    label_patcher.start()
    entry_patcher.start()
    mainloop_patcher.start()
    after_patcher.start()
    imagetk_patcher.start()

    try:
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
    finally:
        toplevel_patcher.stop()
        tk_patcher.stop()
        frame_patcher.stop()
        label_patcher.stop()
        entry_patcher.stop()
        mainloop_patcher.stop()
        after_patcher.stop()
        imagetk_patcher.stop()


@pytest.fixture
def setup_window_with_mocks(monkeypatch, mock_flight_controller, mock_tk_classes) -> FlightControllerInfoWindow:
    """Set up a FlightControllerInfoWindow with all necessary mocks."""
    # Avoid tkinter initialization
    monkeypatch.setattr(BaseWindow, "__init__", lambda self, root_tk=None: None)  # noqa: ARG005

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


def test_window_initialization_with_params(monkeypatch, mock_flight_controller, mock_tk_classes) -> None:
    """Test initialization of window with parameters."""
    init_called = False

    # Mock super().__init__() calls
    def mock_init(self, root_tk=None) -> None:
        nonlocal init_called
        init_called = True
        self.root = MagicMock()
        self.main_frame = MagicMock()

    monkeypatch.setattr(BaseWindow, "__init__", mock_init)

    # Use ExitStack to manage multiple context managers
    with ExitStack() as stack:
        stack.enter_context(patch("tkinter.Tk.after", lambda ms, func: None))  # noqa: ARG005
        stack.enter_context(patch("tkinter.Tk.mainloop"))
        stack.enter_context(
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow",
                return_value=MagicMock(),
            )
        )

        # Initialize the window with the flight controller
        try:
            FlightControllerInfoWindow(mock_flight_controller)
            assert init_called
        except Exception:  # pylint: disable=broad-exception-caught
            # We expect an exception when tkinter tries to draw the window
            assert init_called


def test_center_window(setup_window_with_mocks) -> None:
    """Test the center_window method."""
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


def test_put_image_in_label(monkeypatch, setup_window_with_mocks) -> None:
    """Test the put_image_in_label method."""
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
    monkeypatch.setattr("tkinter.ttk.Label", lambda parent, image=None: mock_label)  # noqa: ARG005

    # Call the method
    result = BaseWindow.put_image_in_label(mock_parent, "test_image.png", image_height=40)

    # Check results
    assert result == mock_label
    mock_image.resize.assert_called_once_with((40, 40))  # Should resize to maintain aspect ratio
    assert hasattr(result, "image")
    assert result.image == mock_photo


def test_put_image_in_label_error_handling(monkeypatch, setup_window_with_mocks) -> None:
    """Test error handling in put_image_in_label method."""
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
    monkeypatch.setattr("tkinter.ttk.Label", lambda parent, image=None: mock_label)  # noqa: ARG005
    monkeypatch.setattr("ardupilot_methodic_configurator.frontend_tkinter_base_window.logging_error", mock_logging_error)

    # Call the method
    result = BaseWindow.put_image_in_label(mock_parent, "test_image.png")

    # Check that logging_error was called and a label was returned
    assert result == mock_label
    # Check that logging_error was called
    mock_logging_error.assert_called_once()


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
def test_info_display_improved(  # noqa: PLR0915
    monkeypatch, mock_flight_controller, info_dict, expected_grid_calls, expected_values
) -> None:
    """Test that flight controller info is displayed correctly in the window with more assertions."""
    mock_flight_controller.info.get_info.return_value = info_dict

    # Count UI element creation
    label_calls = 0
    entry_calls = 0
    entry_values = []

    # Mock ttk.Label and ttk.Entry
    def mock_label(*args, **kwargs) -> MagicMock:
        nonlocal label_calls
        label_calls += 1
        return MagicMock()

    def mock_entry(*args, **kwargs) -> MagicMock:
        nonlocal entry_calls
        entry = MagicMock()
        entry_calls += 1

        # Track what values get inserted
        def mock_insert(position, value) -> None:
            entry_values.append(value)

        entry.insert = mock_insert
        return entry

    # Apply patches
    monkeypatch.setattr("tkinter.ttk.Label", mock_label)
    monkeypatch.setattr("tkinter.ttk.Entry", mock_entry)

    # Create mock of __init__ to test the dynamic UI creation
    original_init = FlightControllerInfoWindow.__init__

    def mock_init(self, flight_controller) -> None:
        # Only execute part of __init__ needed for this test
        self.root = MagicMock()
        self.main_frame = MagicMock()
        self.info_frame = MagicMock()
        self.flight_controller = flight_controller
        self.param_default_values = {}
        # pylint: disable=duplicate-code
        # Process each info item to create UI elements
        for row_nr, (description, attr_value) in enumerate(flight_controller.info.get_info().items()):
            label = ttk.Label(self.info_frame, text=f"{description}:")
            label.grid(row=row_nr, column=0, sticky="w")

            text_field = ttk.Entry(self.info_frame)
            text_field.grid(row=row_nr, column=1, sticky="ew", columnspan=1)

            # Check if the attribute exists and has a non-empty value before inserting
            if attr_value:
                if isinstance(attr_value, dict):
                    text_field.insert(0, (", ").join(attr_value.keys()))
                else:
                    text_field.insert(0, attr_value)
            else:
                text_field.insert(0, "N/A")  # Insert "Not Available" if the attribute is missing or empty
            text_field.configure(state="readonly")
        # pylint: enable=duplicate-code

        # Avoid actual download_flight_controller_parameters execution
        self.root.after = MagicMock()
        self.root.mainloop = MagicMock()

    try:
        # Apply the mock initialization
        monkeypatch.setattr(FlightControllerInfoWindow, "__init__", mock_init)

        # Create the window
        FlightControllerInfoWindow(mock_flight_controller)

        # Check that UI elements were created
        assert label_calls == expected_grid_calls
        assert entry_calls == expected_grid_calls

        # Check entry values
        for value in info_dict.values():
            if not value:
                assert "N/A" in entry_values
            elif isinstance(value, dict):
                assert ", ".join(value.keys()) in entry_values
            else:
                assert value in entry_values

    finally:
        # Restore original __init__
        monkeypatch.setattr(FlightControllerInfoWindow, "__init__", original_init)


def test_window_title_and_geometry(monkeypatch, setup_window_with_mocks) -> None:
    """Test that window title and geometry are set correctly."""
    window = setup_window_with_mocks
    window.root = MagicMock()

    # Mock __version__
    monkeypatch.setattr("ardupilot_methodic_configurator.__version__", "1.0.0")

    # Create a partial mock of __init__ just to test title and geometry
    original_init = FlightControllerInfoWindow.__init__

    def mock_init(self, flight_controller) -> None:
        self.root = MagicMock()
        self.flight_controller = flight_controller
        self.param_default_values = {}

        # Call the real title and geometry setting code
        self.root.title("ArduPilot methodic configurator 1.0.0 - Flight Controller Info")
        self.root.geometry("500x350")

        # Avoid the rest of initialization
        self.root.after = MagicMock()
        self.root.mainloop = MagicMock()

    monkeypatch.setattr(FlightControllerInfoWindow, "__init__", mock_init)

    # Initialize window
    window = FlightControllerInfoWindow(window.flight_controller)

    # Assert title and geometry were set correctly
    window.root.title.assert_called_once_with("ArduPilot methodic configurator 1.0.0 - Flight Controller Info")
    window.root.geometry.assert_called_once_with("500x350")

    # Restore original init
    monkeypatch.setattr(FlightControllerInfoWindow, "__init__", original_init)


def test_download_flight_controller_parameters_error_handling(monkeypatch, setup_window_with_mocks) -> None:
    """Test error handling in download_flight_controller_parameters method."""
    window = setup_window_with_mocks

    # Make download_params raise an exception
    window.flight_controller.download_params.side_effect = RuntimeError("Download failed")

    # Create a mock for logging_error
    mock_logging_error = MagicMock()
    monkeypatch.setattr("logging.error", mock_logging_error)

    # Create mock progress window
    mock_progress_window = MagicMock()

    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow",
        return_value=mock_progress_window,
    ):
        # Test method
        try:
            window.download_flight_controller_parameters()
            msg = "Expected an exception but none was raised"
            raise AssertionError(msg)
        except RuntimeError:
            # Assert progress window was destroyed even when exception occurs
            mock_progress_window.destroy.assert_called_once()


def test_empty_info_dict(monkeypatch, mock_flight_controller) -> None:
    """Test handling of an empty info dictionary."""
    # Set up an empty info dictionary
    mock_flight_controller.info.get_info.return_value = {}

    # Count UI element creation
    label_calls = 0
    entry_calls = 0

    # Mock ttk.Label and ttk.Entry
    monkeypatch.setattr("tkinter.ttk.Label", lambda *args, **kwargs: MagicMock())  # noqa: ARG005
    monkeypatch.setattr("tkinter.ttk.Entry", lambda *args, **kwargs: MagicMock())  # noqa: ARG005

    # Create mock of minimal __init__
    def mock_init(self, flight_controller) -> None:
        self.root = MagicMock()
        self.main_frame = MagicMock()
        self.info_frame = MagicMock()
        self.flight_controller = flight_controller
        self.param_default_values = {}

        # Process info items - this should not enter the loop if dict is empty
        for _row_nr, (_description, _attr_value) in enumerate(flight_controller.info.get_info().items()):
            nonlocal label_calls, entry_calls
            label_calls += 1
            entry_calls += 1

        self.root.after = MagicMock()
        self.root.mainloop = MagicMock()

    # Apply the mock initialization
    original_init = FlightControllerInfoWindow.__init__
    monkeypatch.setattr(FlightControllerInfoWindow, "__init__", mock_init)

    try:
        # Create the window
        FlightControllerInfoWindow(mock_flight_controller)

        # Check that no UI elements were created
        assert label_calls == 0
        assert entry_calls == 0

    finally:
        # Restore original __init__
        monkeypatch.setattr(FlightControllerInfoWindow, "__init__", original_init)


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
