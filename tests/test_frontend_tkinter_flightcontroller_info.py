#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_flightcontroller_info.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import Mock, patch

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_info import BackendFlightcontrollerInfo
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import (
    FlightControllerInfoPresenter,
    FlightControllerInfoWindow,
)

# pylint: disable=redefined-outer-name,protected-access

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
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
                patch(
                    "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow"
                ) as mock_progress_window,
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()

                # When
                window._download_flight_controller_parameters()

                # Then
                mock_progress_window.return_value.destroy.assert_called_once()
                window.root.destroy.assert_called_once()

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
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after"),
                patch(
                    "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.ProgressWindow"
                ) as mock_progress_window,
                patch(
                    "ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info.messagebox.showerror"
                ) as mock_showerror,
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()

                # When - should not raise an exception
                window._download_flight_controller_parameters()

                # Then - cleanup still occurs despite error
                mock_progress_window.return_value.destroy.assert_called_once()
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
                mock_ttk_frame.pack.assert_called_once()
                mock_ttk_frame.columnconfigure.assert_called_once_with(1, weight=1)
                configured_flight_controller.info.get_info.assert_called_once()
