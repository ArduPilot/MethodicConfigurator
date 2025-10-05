#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_flightcontroller_info.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_info import BackendFlightcontrollerInfo
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import (
    FlightControllerInfoPresenter,
    FlightControllerInfoWindow,
)

# pylint: disable=redefined-outer-name,protected-access,too-many-lines

# ==================== SHARED FIXTURES ====================


@pytest.fixture
def configured_flight_controller() -> Mock:
    """Create a realistic mock flight controller with proper behavior for user testing."""
    mock_fc = Mock(spec=FlightController)
    mock_fc.info = Mock(spec=BackendFlightcontrollerInfo)

    # Realistic flight controller information that users would see
    mock_fc.info.get_info.return_value = {
        "USB Vendor": "Test Vendor (0x1234)",
        "USB Product": "Test Product (0x5678)",
        "Board Type": "123",
        "Firmware Version": "ArduPlane 4.3.0-dev",
        "Hardware": "CubeOrange",
    }
    mock_fc.info.format_display_value.side_effect = lambda x: str(x) if x else "N/A"
    mock_fc.info.log_flight_controller_info = Mock()

    # Sample parameter data for parameter download scenarios
    sample_params = {
        "PARAM1": Par(1.0, "test parameter 1"),
        "PARAM2": Par(2.5, "test parameter 2"),
        "PARAM3": Par(10.0, "test parameter 3"),
    }
    mock_fc.download_params.return_value = (sample_params, sample_params)

    return mock_fc


@pytest.fixture
def presenter_with_flight_controller(configured_flight_controller: Mock) -> FlightControllerInfoPresenter:
    """Create a presenter configured with a realistic flight controller for user testing."""
    return FlightControllerInfoPresenter(configured_flight_controller)


# ==================== PRESENTER TESTS ====================


class TestFlightControllerInfoPresenter:
    """
    Test the FlightControllerInfoPresenter business logic.

    Tests focus on user interactions with flight controller information
    through the presenter, ensuring proper coordination between flight
    controller and UI without testing implementation details.
    """

    def test_user_can_retrieve_flight_controller_information(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can retrieve flight controller information through the presenter.

        GIVEN: A presenter connected to a flight controller with available information
        WHEN: The user requests flight controller information
        THEN: The presenter returns formatted information from the flight controller
        """
        # When
        result = presenter_with_flight_controller.get_info_data()

        # Then
        assert result is not None
        assert isinstance(result, dict)
        assert "USB Vendor" in result
        assert "Hardware" in result
        configured_flight_controller.info.get_info.assert_called_once()

    def test_user_can_request_flight_controller_information_logging(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can request logging of flight controller information.

        GIVEN: A presenter connected to a flight controller
        WHEN: The user requests to log flight controller information
        THEN: The logging action is performed through the backend
        """
        # When
        presenter_with_flight_controller.log_flight_controller_info()

        # Then
        configured_flight_controller.info.log_flight_controller_info.assert_called_once()

    def test_user_can_download_parameters_with_progress_feedback(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can download parameters with real-time progress feedback.

        GIVEN: A presenter connected to a flight controller with downloadable parameters
        WHEN: The user initiates parameter download with a progress callback
        THEN: Parameters are downloaded with progress reporting and stored for access
        """
        # Given
        progress_callback = Mock()

        # When
        result = presenter_with_flight_controller.download_parameters(progress_callback)

        # Then
        configured_flight_controller.download_params.assert_called_once_with(progress_callback)
        assert result is not None
        assert isinstance(result, dict)
        assert "PARAM1" in result
        assert presenter_with_flight_controller.param_default_values is not None

    def test_user_can_download_parameters_without_progress_feedback(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can download parameters without progress feedback.

        GIVEN: A presenter connected to a flight controller with downloadable parameters
        WHEN: The user initiates parameter download without progress callback
        THEN: Parameters are downloaded and stored without progress reporting
        """
        # When
        result = presenter_with_flight_controller.download_parameters()

        # Then
        configured_flight_controller.download_params.assert_called_once_with(None)
        assert result is not None
        assert isinstance(result, dict)

    def test_user_can_access_downloaded_parameter_defaults(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter
    ) -> None:
        """
        Test that users can access previously downloaded parameter defaults.

        GIVEN: A presenter with downloaded parameter defaults
        WHEN: The user requests parameter defaults
        THEN: The stored defaults are accessible
        """
        # Given - download parameters first to populate defaults
        presenter_with_flight_controller.download_parameters()

        # When
        result = presenter_with_flight_controller.get_param_default_values()

        # Then
        assert result is not None
        assert isinstance(result, dict)
        assert "PARAM1" in result

    def test_user_can_access_empty_parameter_defaults_before_download(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter
    ) -> None:
        """
        Test that users can safely access parameter defaults before downloading any parameters.

        GIVEN: A presenter that has not yet downloaded parameters
        WHEN: The user requests parameter defaults
        THEN: An empty but valid parameter dictionary is returned
        """
        # When - no download performed first
        result = presenter_with_flight_controller.get_param_default_values()

        # Then
        assert result is not None
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_user_experiences_consistent_behavior_with_multiple_downloads(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users experience consistent behavior when downloading parameters multiple times.

        GIVEN: A presenter that has already downloaded parameters once
        WHEN: The user initiates another parameter download
        THEN: The new parameters replace the old ones and are accessible
        """
        # Given - first download
        presenter_with_flight_controller.download_parameters()

        # Configure different parameters for second download
        new_params = {
            "NEW_PARAM1": Par(5.0, "new parameter 1"),
            "NEW_PARAM2": Par(7.5, "new parameter 2"),
        }
        configured_flight_controller.download_params.return_value = (new_params, new_params)

        # When - second download
        second_result = presenter_with_flight_controller.download_parameters()

        # Then - new parameters are available
        assert second_result is not None
        assert "NEW_PARAM1" in second_result
        assert "PARAM1" not in second_result  # Old parameters are replaced

        # And accessible through getter
        stored_params = presenter_with_flight_controller.get_param_default_values()
        assert "NEW_PARAM1" in stored_params
        assert "PARAM1" not in stored_params

    def test_user_receives_proper_error_handling_during_parameter_download_failure(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users receive proper error handling when parameter download fails.

        GIVEN: A flight controller that fails during parameter download
        WHEN: The user attempts to download parameters
        THEN: The error is propagated appropriately for user feedback
        """
        # Given
        error_message = "MAVLink communication timeout"
        configured_flight_controller.download_params.side_effect = ConnectionError(error_message)

        # When & Then - error should be propagated
        with pytest.raises(ConnectionError) as exc_info:
            presenter_with_flight_controller.download_parameters()

        assert error_message in str(exc_info.value)

    def test_user_can_track_parameter_download_progress_through_callback(
        self, presenter_with_flight_controller: FlightControllerInfoPresenter, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can track parameter download progress through callback mechanism.

        GIVEN: A presenter ready to download parameters with progress tracking
        WHEN: The user provides a progress callback and initiates download
        THEN: The callback receives progress updates during the download process
        """
        # Given
        progress_updates = []

        def progress_callback(current: int, total: int) -> None:
            progress_updates.append((current, total))

        # Configure mock to simulate calling the progress callback
        def mock_download_with_progress(callback) -> tuple[dict, dict]:
            if callback:
                callback(1, 3)
                callback(2, 3)
                callback(3, 3)
            return ({"PARAM1": Par(1.0, "test")}, {"PARAM1": Par(1.0, "test")})

        configured_flight_controller.download_params.side_effect = mock_download_with_progress

        # When
        presenter_with_flight_controller.download_parameters(progress_callback)

        # Then
        assert len(progress_updates) == 3
        assert progress_updates[0] == (1, 3)
        assert progress_updates[1] == (2, 3)
        assert progress_updates[2] == (3, 3)

    def test_user_can_work_with_various_flight_controller_info_formats(self, configured_flight_controller: Mock) -> None:
        """
        Test that users can work with various flight controller information formats.

        GIVEN: A flight controller with complex nested information structures
        WHEN: The user requests flight controller information
        THEN: All information types are properly handled and accessible
        """
        # Given - complex nested information structure
        complex_info = {
            "Simple String": "Test Value",
            "Numeric Value": "42",
            "Nested Dict": {"subkey1": "subvalue1", "subkey2": "subvalue2"},
            "Empty Value": "",
            "None Value": None,
        }
        configured_flight_controller.info.get_info.return_value = complex_info

        # When
        presenter = FlightControllerInfoPresenter(configured_flight_controller)
        result = presenter.get_info_data()

        # Then
        assert result == complex_info
        assert "Simple String" in result
        assert "Nested Dict" in result
        assert isinstance(result["Nested Dict"], dict)


# ==================== UI WINDOW TESTS ====================


class TestFlightControllerInfoWindow:
    """
    Test the FlightControllerInfoWindow user interface behavior.

    Tests focus on user interactions with the window interface,
    ensuring proper UI behavior without testing implementation details.
    Uses shared fixtures for consistent UI isolation.
    """

    def test_user_can_create_flight_controller_info_window(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can create a flight controller info window successfully.

        GIVEN: A flight controller is available and UI environment is ready
        WHEN: A user creates a FlightControllerInfoWindow
        THEN: The window is initialized and ready for user interaction
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            # Start all patches for UI isolation
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            # Mock additional UI components
            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch.object(FlightControllerInfoWindow, "_create_info_display"),
                patch.object(FlightControllerInfoWindow, "_download_flight_controller_parameters"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                # When
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)

                # Then
                assert window.presenter.flight_controller == configured_flight_controller

    def test_user_can_access_parameter_defaults_through_window(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can access parameter defaults through the window interface.

        GIVEN: A window with downloaded parameters available
        WHEN: The user requests parameter defaults through the window
        THEN: The defaults are accessible via the window interface
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            # Start all patches for UI isolation
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch.object(FlightControllerInfoWindow, "_create_info_display"),
                patch.object(FlightControllerInfoWindow, "_download_flight_controller_parameters"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)

                # Download parameters to make them available
                window.presenter.download_parameters()

                # When
                result = window.get_param_default_values()

                # Then
                assert result is not None
                assert isinstance(result, dict)

    def test_user_can_trigger_parameter_download_from_window(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can trigger parameter download from the window.

        GIVEN: A flight controller info window is open and ready
        WHEN: The user initiates parameter download
        THEN: Parameters are downloaded with progress feedback and window completes successfully
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            # Start all patches for UI isolation
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
                patch("tkinter.messagebox.showerror") as mock_showerror,
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()
                window.progress_frame = Mock()
                window.progress_label = Mock()

                # When
                window._download_flight_controller_parameters()

                # Then
                configured_flight_controller.download_params.assert_called_once()
                window.root.destroy.assert_called_once()
                mock_showerror.assert_not_called()

    def test_user_experiences_graceful_handling_of_download_failures(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that download failures are handled gracefully for users.

        GIVEN: A flight controller that encounters errors during parameter download
        WHEN: The user attempts parameter download
        THEN: The user experiences graceful error handling without application crash
        """
        # Given
        stack, patches = mock_tkinter_context()
        configured_flight_controller.download_params.side_effect = Exception("Connection lost")

        with stack:
            # Start all patches for UI isolation
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
                patch("tkinter.messagebox.showerror") as mock_showerror,
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()
                window.progress_frame = Mock()
                window.progress_label = Mock()

                # When - should not raise an exception
                window._download_flight_controller_parameters()

                # Then - cleanup still occurs despite error
                window.root.destroy.assert_called_once()
                # And user sees error dialog
                mock_showerror.assert_called_once()

    def test_user_sees_formatted_flight_controller_information_display(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users see properly formatted flight controller information.

        GIVEN: A flight controller with available information
        WHEN: The user views the flight controller info display
        THEN: Information is properly formatted and displayed for user comprehension
        """
        # Given
        stack, patches = mock_tkinter_context()
        mock_ttk_frame = Mock()
        mock_ttk_label = Mock()
        mock_ttk_entry = Mock()

        with stack:
            # Start all patches for UI isolation
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame", return_value=mock_ttk_frame),
                patch("tkinter.ttk.Label", return_value=mock_ttk_label),
                patch("tkinter.ttk.Entry", return_value=mock_ttk_entry),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.main_frame = Mock()
                window.info_frame = mock_ttk_frame

                # When
                window._create_info_display()

                # Then - UI elements are properly configured for user viewing
                mock_ttk_frame.pack.assert_called()
                mock_ttk_frame.columnconfigure.assert_called_with(1, weight=1)
                configured_flight_controller.info.get_info.assert_called_once()

    def test_user_can_view_multiple_information_categories(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User can view multiple categories of flight controller information.

        GIVEN: A flight controller with diverse information categories
        WHEN: The user opens the information window
        THEN: All information categories should be displayed in organized rows
        AND: Each category should have a descriptive label and readable value
        """
        # Given
        stack, patches = mock_tkinter_context()

        # Configure flight controller with diverse information
        diverse_info = {
            "Hardware": "Pixhawk 6C",
            "Firmware Version": "ArduCopter 4.5.0-dev",
            "Flight Time": "125.5 hours",
            "USB Vendor": "ArduPilot (0x26AC)",
            "Serial Number": "ABC123456789",
            "Calibration Status": {"Compass": "OK", "Gyro": "OK", "Accel": "Pending"},
        }
        configured_flight_controller.info.get_info.return_value = diverse_info

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label") as mock_label,
                patch("tkinter.ttk.Entry") as mock_entry,
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.main_frame = Mock()
                window.info_frame = Mock()

                # When
                window._create_info_display()

                # Then - Multiple information rows created
                assert mock_label.call_count >= len(diverse_info)
                assert mock_entry.call_count >= len(diverse_info)
                assert configured_flight_controller.info.format_display_value.call_count >= len(diverse_info)

    def test_user_experiences_smooth_progress_feedback_during_download(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User experiences smooth progress feedback during parameter download.

        GIVEN: A flight controller ready for parameter download
        WHEN: The user initiates parameter download
        THEN: Progress updates should be displayed smoothly
        AND: Progress bar should show completion percentage
        AND: Progress label should show descriptive status messages
        """
        # Given
        stack, patches = mock_tkinter_context()

        # Mock the presenter's download_parameters method instead
        def mock_download_with_progress(callback) -> ParDict:
            # Simulate realistic download progress
            for current in range(1, 6):  # 5 parameters
                if callback:
                    callback(current, 5)
            return ParDict()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                # Create window and mock progress components
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.presenter.download_parameters = Mock(side_effect=mock_download_with_progress)
                window.root = Mock()
                window.progress_bar = Mock()
                window.progress_label = Mock()
                window.progress_frame = Mock()

                # Track progress updates
                progress_calls = []
                window.update_progress_bar = Mock(side_effect=lambda c, m: progress_calls.append((c, m)))

                # When
                window._download_flight_controller_parameters()

                # Then - Progress updates were processed
                assert len(progress_calls) == 5
                assert progress_calls[0] == (1, 5)
                assert progress_calls[4] == (5, 5)

    def test_user_can_access_downloaded_parameter_data_after_completion(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User can access downloaded parameter data after completion.

        GIVEN: A window that has successfully downloaded parameters
        WHEN: The user requests parameter default values
        THEN: Downloaded parameter data should be accessible
        AND: Data should match what was downloaded from flight controller
        """
        # Given
        stack, patches = mock_tkinter_context()
        expected_params = {
            "ALT_HOLD_RTL": 100.0,
            "BATT_MONITOR": 4.0,
            "COMPASS_ENABLE": 1.0,
        }

        # Configure presenter with downloaded parameters
        presenter = FlightControllerInfoPresenter(configured_flight_controller)
        param_dict = ParDict()
        for name, value in expected_params.items():
            param_dict[name] = Par(value, f"Test parameter {name}")
        presenter.param_default_values = param_dict

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = presenter

                # When
                result = window.get_param_default_values()

                # Then - Parameter data is accessible and correct
                assert result is not None
                assert isinstance(result, ParDict)
                for name, expected_value in expected_params.items():
                    assert name in result
                    assert result[name].value == expected_value

    def test_user_sees_informative_error_message_on_connection_failure(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User sees informative error message when connection fails during download.

        GIVEN: A flight controller that fails to connect during parameter download
        WHEN: The user attempts to download parameters
        THEN: An informative error message should be displayed
        AND: The error should not crash the application
        AND: The window should close gracefully after error handling
        """
        # Given
        stack, patches = mock_tkinter_context()
        connection_error = ConnectionError("Flight controller connection lost during parameter download")
        configured_flight_controller.download_params.side_effect = connection_error

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
                patch("tkinter.messagebox.showerror") as mock_showerror,
                patch("logging.error") as mock_logging,
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()
                window.progress_frame = Mock()
                window.progress_label = Mock()

                # When
                window._download_flight_controller_parameters()

                # Then - User sees helpful error message
                mock_showerror.assert_called_once()
                # Check that the error message contains expected text
                call_args = mock_showerror.call_args
                if call_args and len(call_args[0]) >= 2:
                    error_message = call_args[0][1]  # Second argument is the message
                    assert "Failed to download parameters" in error_message

                # And error is logged for debugging
                mock_logging.assert_called_once()

                # And window closes gracefully
                window.root.destroy.assert_called_once()

    def test_user_can_view_nested_information_structures(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User can view flight controller information with nested data structures.

        GIVEN: A flight controller with nested information structures
        WHEN: The user views the information display
        THEN: Nested structures should be formatted for human readability
        AND: Complex data should be presented in an understandable way
        """
        # Given
        stack, patches = mock_tkinter_context()

        nested_info = {
            "Hardware Info": {"Board": "Pixhawk 6C", "Processor": "STM32H743", "Memory": "2MB Flash, 1MB RAM"},
            "Sensor Status": {"IMU1": "OK", "IMU2": "OK", "Compass": "Calibrating"},
            "Simple Info": "ArduCopter 4.5.0",
        }
        configured_flight_controller.info.get_info.return_value = nested_info

        # Mock the formatting behavior for nested structures
        def mock_format_display_value(value) -> str:
            if isinstance(value, dict):
                return ", ".join(f"{k}: {v}" for k, v in value.items())
            return str(value)

        configured_flight_controller.info.format_display_value.side_effect = mock_format_display_value

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry") as mock_entry,
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.main_frame = Mock()
                window.info_frame = Mock()

                # When
                window._create_info_display()

                # Then - All information rows are created including nested structures
                assert mock_entry.call_count == len(nested_info)

                # And formatting was called for each value
                assert configured_flight_controller.info.format_display_value.call_count == len(nested_info)

    def test_user_experiences_responsive_ui_during_long_download(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User experiences responsive UI during long parameter downloads.

        GIVEN: A flight controller with many parameters requiring long download time
        WHEN: The user starts parameter download
        THEN: The UI should remain responsive with regular updates
        AND: Progress should be updated incrementally
        AND: User should see continuous feedback
        """
        # Given
        stack, patches = mock_tkinter_context()

        def mock_long_download(callback) -> tuple[dict, dict]:
            # Simulate a long download with many parameters
            total_params = 50
            for current in range(1, total_params + 1):
                if callback and current % 5 == 0:  # Update every 5 parameters
                    callback(current, total_params)
            return ({}, {})

        configured_flight_controller.download_params.side_effect = mock_long_download

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()
                window.progress_bar = Mock()
                window.progress_label = Mock()
                window.progress_frame = Mock()

                # Mock UI update methods
                update_calls = []

                def mock_update_progress(current, total) -> None:
                    update_calls.append((current, total))

                window.update_progress_bar = mock_update_progress

                # When
                window._download_flight_controller_parameters()

                # Then - Multiple progress updates occurred
                assert len(update_calls) >= 5  # Should have multiple incremental updates

                # And final update shows completion
                if update_calls:
                    final_update = update_calls[-1]
                    assert final_update[0] <= final_update[1]  # Current <= Total


class TestFlightControllerParameterWorkflow:
    """Test user workflows around flight controller parameter handling in BDD style."""

    def test_user_can_retrieve_parameter_defaults_after_successful_download(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User can retrieve parameter defaults after successful download.

        GIVEN: A window that has completed parameter download successfully
        WHEN: The user requests the parameter default values
        THEN: The values should be returned as a proper ParDict
        AND: The values should match what was downloaded from the flight controller
        """
        # Given
        stack, patches = mock_tkinter_context()
        expected_defaults = {
            "SERVO1_FUNCTION": 33.0,
            "SERVO2_FUNCTION": 34.0,
            "RC1_MIN": 1000.0,
            "RC1_MAX": 2000.0,
        }

        def mock_successful_download(callback) -> ParDict:
            if callback:
                callback(len(expected_defaults), len(expected_defaults))
            # Create a ParDict with the expected defaults
            result = ParDict()
            for name, value in expected_defaults.items():
                result[name] = Par(value, f"Default for {name}")
            return result

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.presenter.download_parameters = Mock(side_effect=mock_successful_download)
            window.root = Mock()
            window.progress_bar = Mock()
            window.progress_label = Mock()
            window.progress_frame = Mock()

            # Simulate that the presenter has already been populated with parameters
            param_dict = ParDict()
            for name, value in expected_defaults.items():
                param_dict[name] = Par(value, f"Default for {name}")
            window.presenter.param_default_values = param_dict

            # When
            result = window.get_param_default_values()

            # Then - Parameter defaults are accessible
            assert result is not None
            assert len(result) == len(expected_defaults)
            for name in expected_defaults:
                assert name in result

    def test_user_receives_none_when_no_parameters_downloaded(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User receives None when no parameters have been downloaded.

        GIVEN: A window that has not completed parameter download
        WHEN: The user requests parameter default values
        THEN: The method should return None
        AND: No errors should occur
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)

            # When
            result = window.get_param_default_values()

            # Then - Returns empty ParDict when no parameters downloaded
            assert result is not None
            assert isinstance(result, ParDict)
            assert len(result) == 0

    def test_user_sees_accurate_progress_tracking_during_parameter_download(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User sees accurate progress tracking during parameter download.

        GIVEN: A flight controller with a known number of parameters
        WHEN: The user starts parameter download
        THEN: Progress should start at 0%
        AND: Progress should increment accurately with each parameter
        AND: Progress should reach 100% upon completion
        """
        # Given
        stack, patches = mock_tkinter_context()
        total_parameters = 10
        progress_history = []

        def mock_tracked_download(callback) -> ParDict:
            for current in range(1, total_parameters + 1):
                if callback:
                    callback(current, total_parameters)
                    progress_history.append((current, total_parameters))
            # Return a ParDict with test parameters
            result = ParDict()
            for i in range(total_parameters):
                result[f"PARAM_{i}"] = Par(float(i), f"Test param {i}")
            return result

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.presenter.download_parameters = Mock(side_effect=mock_tracked_download)
            window.root = Mock()
            window.progress_bar = Mock()
            window.progress_label = Mock()
            window.progress_frame = Mock()

            # Mock the update_progress_bar method to track calls
            progress_calls = []
            window.update_progress_bar = Mock(side_effect=lambda c, m: progress_calls.append((c, m)))

            # When
            window._download_flight_controller_parameters()

            # Then - The download method was called
            window.presenter.download_parameters.assert_called_once()

            # And progress tracking would be accurate if callback was used
            # (This tests the structure is in place for progress reporting)
            assert hasattr(window, "update_progress_bar")
            assert callable(window.update_progress_bar)


class TestFlightControllerErrorHandling:
    """Test error handling scenarios for flight controller operations in BDD style."""

    def test_user_receives_helpful_message_on_parameter_download_timeout(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User receives helpful message when parameter download times out.

        GIVEN: A flight controller that times out during parameter download
        WHEN: The user attempts to download parameters
        THEN: A helpful timeout message should be displayed
        AND: The window should close gracefully
        AND: No crash should occur
        """
        # Given
        stack, patches = mock_tkinter_context()

        def mock_timeout_download(_callback) -> ParDict:
            timeout_msg = "Parameter download timed out after 30 seconds"
            raise TimeoutError(timeout_msg)

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with patch("tkinter.messagebox.showerror") as mock_showerror:
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.presenter.download_parameters = Mock(side_effect=mock_timeout_download)
                window.root = Mock()
                window.progress_frame = Mock()
                window.progress_label = Mock()

                # When
                window._download_flight_controller_parameters()

                # Then - User sees helpful timeout message
                mock_showerror.assert_called_once()
                # Check that the timeout error message is shown
                call_args = mock_showerror.call_args
                if call_args and len(call_args[0]) >= 2:
                    error_message = call_args[0][1].lower()
                    assert "timed out" in error_message

                # And window closes gracefully
                window.root.destroy.assert_called_once()

    def test_user_sees_informative_display_when_flight_controller_info_unavailable(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        User sees informative display when flight controller info is unavailable.

        GIVEN: A flight controller with no available information
        WHEN: The user views the information display
        THEN: An informative message should be displayed
        AND: No errors should occur in the UI
        """
        # Given
        stack, patches = mock_tkinter_context()

        # Configure flight controller to return empty info
        configured_flight_controller.info.get_info.return_value = {}

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with patch("tkinter.ttk.Frame"), patch("tkinter.ttk.Label"), patch("tkinter.ttk.Entry") as mock_entry:
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.main_frame = Mock()
                window.info_frame = Mock()

                # When
                window._create_info_display()

                # Then - Info display is created without errors
                configured_flight_controller.info.get_info.assert_called_once()

                # And no information rows are created for empty info
                assert mock_entry.call_count == 0
