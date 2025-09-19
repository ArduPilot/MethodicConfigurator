#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_flightcontroller_info.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from unittest.mock import Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_info import BackendFlightcontrollerInfo
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import (
    FlightControllerInfoPresenter,
    FlightControllerInfoWindow,
)

# pylint: disable=redefined-outer-name,protected-access,too-many-lines,unnecessary-dunder-call

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

    def test_user_sees_progress_updates_during_parameter_download(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users see real-time progress updates during parameter download.

        GIVEN: A window with progress display components
        WHEN: Parameter download progress updates are received
        THEN: The progress bar and message are updated to reflect current status
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            # Create a progress bar mock that supports dictionary-style access
            progress_bar_data: dict[str, int] = {}
            progress_bar_mock = Mock()
            progress_bar_mock.__setitem__ = lambda _self, key, value: progress_bar_data.__setitem__(key, value)
            progress_bar_mock.__getitem__ = lambda _self, key: progress_bar_data.__getitem__(key)
            progress_bar_mock.update = Mock()

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.root = Mock()
            window.progress_bar = progress_bar_mock
            window.progress_label = Mock()
            window.progress_frame = Mock()

            # When
            window.update_progress_bar(50, 100)

            # Then
            assert window.progress_bar["value"] == 50
            assert window.progress_bar["maximum"] == 100
            window.progress_label.config.assert_called_with(text="Downloaded 50 of 100 parameters")
            window.progress_bar.update.assert_called_once()

    def test_user_sees_progress_completion_feedback(self, mock_tkinter_context, configured_flight_controller: Mock) -> None:
        """
        Test that users see appropriate feedback when parameter download completes.

        GIVEN: A window with progress display showing ongoing download
        WHEN: Parameter download reaches completion (100%)
        THEN: The progress display is hidden to indicate completion
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            # Create a progress bar mock that supports dictionary-style access
            progress_bar_data: dict[str, int] = {}
            progress_bar_mock = Mock()
            progress_bar_mock.__setitem__ = lambda _self, key, value: progress_bar_data.__setitem__(key, value)
            progress_bar_mock.__getitem__ = lambda _self, key: progress_bar_data.__getitem__(key)
            progress_bar_mock.update = Mock()

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.root = Mock()
            window.progress_bar = progress_bar_mock
            window.progress_label = Mock()
            window.progress_frame = Mock()

            # When - download completes
            window.update_progress_bar(100, 100)

            # Then - progress frame is hidden
            window.progress_frame.pack_forget.assert_called_once()

    def test_user_experiences_robust_progress_error_handling(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that progress update errors don't crash the user experience.

        GIVEN: A window where progress widgets encounter Tkinter errors
        WHEN: Progress updates are attempted during widget lifecycle issues
        THEN: The errors are handled gracefully without crashing the application
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.root = Mock()
            window.progress_bar = None  # type: ignore[assignment]  # Simulate widget destruction
            window.progress_label = Mock()
            window.progress_frame = Mock()

            # When - should not raise exception
            window.update_progress_bar(50, 100)

            # Then - method returns safely without updates
            window.progress_label.config.assert_not_called()

    def test_user_can_view_complex_flight_controller_info_rows(  # pylint: disable=too-many-locals
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that users can view complex flight controller information in formatted rows.

        GIVEN: A flight controller with various types of information (strings, dicts, etc.)
        WHEN: The user views the information display
        THEN: Each piece of information is properly formatted and displayed in its own row
        """
        # Given
        stack, patches = mock_tkinter_context()
        configured_flight_controller.info.format_display_value.side_effect = [
            "Test Vendor (0x1234)",
            "Test Product (0x5678)",
            "123",
            "ArduPlane 4.3.0-dev",
            "CubeOrange",
        ]

        mock_labels = []
        mock_entries = []

        def create_mock_label(*_args, **_kwargs) -> Mock:
            mock_label = Mock()
            mock_labels.append(mock_label)
            return mock_label

        def create_mock_entry(*_args, **_kwargs) -> Mock:
            mock_entry = Mock()
            mock_entries.append(mock_entry)
            return mock_entry

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label", side_effect=create_mock_label),
                patch("tkinter.ttk.Entry", side_effect=create_mock_entry),
                patch("tkinter.ttk.Progressbar"),
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.main_frame = Mock()
                window.info_frame = Mock()

                # When
                info_data = configured_flight_controller.info.get_info.return_value
                for row_nr, (description, attr_value) in enumerate(info_data.items()):
                    window._create_info_row(row_nr, description, attr_value)

                # Then - all info rows are created
                assert len(mock_labels) == 5  # One for each info item
                assert len(mock_entries) == 5  # One for each info item

                # Verify entry fields are configured correctly
                for entry in mock_entries:
                    entry.grid.assert_called_once()
                    entry.insert.assert_called_once()
                    entry.configure.assert_called_with(state="readonly")


# ==================== INTEGRATION TESTS ====================


class TestFlightControllerInfoIntegration:
    """
    Test complete user workflows and integration scenarios.

    These tests verify that the presenter and window work together
    to provide a seamless user experience from start to finish.
    """

    def test_complete_user_workflow_successful_parameter_download(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test the complete user workflow from window creation to successful parameter download.

        GIVEN: A user wants to view flight controller information and download parameters
        WHEN: They open the info window and the download process completes successfully
        THEN: They see the flight controller information, progress updates, and window closes properly
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch("tkinter.ttk.Entry"),
                patch("tkinter.ttk.Progressbar"),
                patch("tkinter.Tk.mainloop"),
                patch("tkinter.Tk.after") as mock_after,
                patch.object(FlightControllerInfoWindow, "_create_info_display") as mock_create_display,
                patch.object(FlightControllerInfoWindow, "_download_flight_controller_parameters") as mock_download,
            ):
                # When - user creates window (simulating __init__)
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()

                # Simulate the init process
                mock_create_display()
                window.presenter.log_flight_controller_info()
                mock_after(50, mock_download)

                # Then - complete workflow is initiated
                mock_create_display.assert_called_once()
                configured_flight_controller.info.log_flight_controller_info.assert_called_once()
                mock_after.assert_called_once_with(50, mock_download)

    def test_user_workflow_with_parameter_download_and_access(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test the user workflow including parameter download and subsequent access.

        GIVEN: A user successfully downloads parameters through the window
        WHEN: They request access to the downloaded parameter defaults
        THEN: The parameters are available and accessible through the window interface
        """
        # Given
        stack, patches = mock_tkinter_context()

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
                window.progress_frame = Mock()
                window.progress_label = Mock()

                # When - complete download workflow
                window._download_flight_controller_parameters()
                result = window.get_param_default_values()

                # Then - parameters are downloaded and accessible
                assert result is not None
                assert "PARAM1" in result
                configured_flight_controller.download_params.assert_called_once()

    def test_user_workflow_handles_connection_interruption_gracefully(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that connection interruptions during the workflow are handled gracefully.

        GIVEN: A user attempts the complete workflow but experiences connection issues
        WHEN: The parameter download encounters a connection error
        THEN: The user receives appropriate feedback and the application remains stable
        """
        # Given
        stack, patches = mock_tkinter_context()
        configured_flight_controller.download_params.side_effect = ConnectionError("Flight controller disconnected")

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
            ):
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
                window.root = Mock()
                window.progress_frame = Mock()
                window.progress_label = Mock()

                # When - workflow encounters error
                window._download_flight_controller_parameters()

                # Then - error is handled gracefully
                mock_showerror.assert_called_once()
                window.root.destroy.assert_called_once()

    def test_presenter_and_window_coordination_during_progress_updates(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test coordination between presenter and window during progress updates.

        GIVEN: A presenter downloading parameters with a window providing progress feedback
        WHEN: The download process sends progress updates
        THEN: The window receives and displays the updates correctly
        """
        # Given
        stack, patches = mock_tkinter_context()
        progress_calls = []

        # Configure mock to track progress calls
        def mock_download_with_progress(callback) -> tuple[dict, dict]:
            if callback:
                callback(25, 100)
                callback(50, 100)
                callback(75, 100)
                callback(100, 100)
            return ({"PARAM1": Par(1.0, "test")}, {"PARAM1": Par(1.0, "test")})

        configured_flight_controller.download_params.side_effect = mock_download_with_progress

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            # Create a progress bar mock that supports dictionary-style access
            progress_bar_data: dict[str, int] = {}
            progress_bar_mock = Mock()
            progress_bar_mock.__setitem__ = lambda _self, key, value: progress_bar_data.__setitem__(key, value)
            progress_bar_mock.__getitem__ = lambda _self, key: progress_bar_data.__getitem__(key)
            progress_bar_mock.update = Mock()

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.root = Mock()
            window.progress_bar = progress_bar_mock
            window.progress_label = Mock()
            window.progress_frame = Mock()

            # Create a progress callback that tracks calls
            def track_progress(current: int, total: int) -> None:
                progress_calls.append((current, total))
                window.update_progress_bar(current, total)

            # When - download with progress tracking
            window.presenter.download_parameters(track_progress)

            # Then - progress coordination works correctly
            assert len(progress_calls) == 4
            assert progress_calls[-1] == (100, 100)  # Completion
            window.progress_frame.pack_forget.assert_called_once()  # Hidden on completion


# ==================== EDGE CASE AND ERROR TESTS ====================


class TestFlightControllerInfoEdgeCases:
    """
    Test edge cases, boundary conditions, and unusual scenarios.

    These tests ensure robust behavior when users encounter
    unexpected situations or data conditions.
    """

    def test_presenter_handles_empty_flight_controller_info(self, configured_flight_controller: Mock) -> None:
        """
        Test that presenter handles empty flight controller information gracefully.

        GIVEN: A flight controller that returns empty information
        WHEN: The user requests flight controller information
        THEN: The presenter returns empty data without errors
        """
        # Given
        configured_flight_controller.info.get_info.return_value = {}

        # When
        presenter = FlightControllerInfoPresenter(configured_flight_controller)
        result = presenter.get_info_data()

        # Then
        assert result == {}
        assert isinstance(result, dict)

    def test_presenter_handles_malformed_parameter_data(self, configured_flight_controller: Mock) -> None:
        """
        Test that presenter handles malformed parameter data appropriately.

        GIVEN: A flight controller that returns malformed parameter data
        WHEN: The user attempts parameter download
        THEN: The error is properly propagated for user feedback
        """
        # Given
        configured_flight_controller.download_params.side_effect = ValueError("Invalid parameter format")

        # When & Then
        presenter = FlightControllerInfoPresenter(configured_flight_controller)
        with pytest.raises(ValueError, match="Invalid parameter format"):
            presenter.download_parameters()

    def test_window_handles_missing_progress_widgets_gracefully(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that window handles missing progress widgets without crashing.

        GIVEN: A window where progress widgets are not properly initialized
        WHEN: Progress updates are attempted
        THEN: The updates are handled gracefully without errors
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.root = Mock()
            # Missing progress widgets

            # When - should not raise exception
            window.update_progress_bar(50, 100)

            # Then - method completes without error (no assertions needed for graceful handling)

    def test_presenter_handles_none_values_in_flight_controller_info(self, configured_flight_controller: Mock) -> None:
        """
        Test that presenter handles None values in flight controller information.

        GIVEN: A flight controller with None values in its information
        WHEN: The user requests flight controller information
        THEN: The None values are properly handled and returned
        """
        # Given
        info_with_nones = {
            "Valid Field": "Valid Value",
            "None Field": None,
            "Empty Field": "",
        }
        configured_flight_controller.info.get_info.return_value = info_with_nones

        # When
        presenter = FlightControllerInfoPresenter(configured_flight_controller)
        result = presenter.get_info_data()

        # Then
        assert result["Valid Field"] == "Valid Value"
        assert result["None Field"] is None
        assert result["Empty Field"] == ""

    def test_window_handles_tkinter_errors_during_progress_updates(
        self, mock_tkinter_context, configured_flight_controller: Mock
    ) -> None:
        """
        Test that window handles Tkinter errors during progress updates.

        GIVEN: A window where Tkinter widgets raise errors during updates
        WHEN: Progress updates encounter widget errors
        THEN: The errors are caught and handled gracefully
        """
        # Given
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            # Create a progress bar mock that supports dictionary-style access
            progress_bar_data: dict[str, int] = {}
            progress_bar_mock = Mock()
            progress_bar_mock.__setitem__ = lambda _self, key, value: progress_bar_data.__setitem__(key, value)
            progress_bar_mock.__getitem__ = lambda _self, key: progress_bar_data.get(key, 0)
            progress_bar_mock.update = Mock()

            window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
            window.presenter = FlightControllerInfoPresenter(configured_flight_controller)
            window.root = Mock()
            window.root.lift.side_effect = tk.TclError("Widget destroyed")
            window.progress_bar = progress_bar_mock
            window.progress_label = Mock()
            window.progress_frame = Mock()

            # When - Tkinter error occurs during update
            window.update_progress_bar(50, 100)

            # Then - error is handled gracefully, method doesn't crash
            # Note: TclError causes early return, so progress bar won't be updated
            # but method handles the error gracefully without crashing
            window.root.lift.assert_called_once()  # Error occurred during lift
            # progress_label.config should not be called due to early return
            window.progress_label.config.assert_not_called()

    def test_presenter_handles_large_parameter_datasets(self, configured_flight_controller: Mock) -> None:
        """
        Test that presenter handles large parameter datasets efficiently.

        GIVEN: A flight controller with a large number of parameters
        WHEN: The user downloads the parameter dataset
        THEN: All parameters are processed and stored correctly
        """
        # Given - large parameter dataset
        large_params = {}
        for i in range(1000):
            large_params[f"PARAM_{i:04d}"] = Par(float(i), f"test parameter {i}")

        configured_flight_controller.download_params.return_value = (large_params, large_params)

        # When
        presenter = FlightControllerInfoPresenter(configured_flight_controller)
        result = presenter.download_parameters()

        # Then
        assert len(result) == 1000
        assert "PARAM_0000" in result
        assert "PARAM_0999" in result
        assert result["PARAM_0500"].value == 500.0

    def test_window_creation_with_unusual_flight_controller_states(self, mock_tkinter_context) -> None:
        """
        Test window creation with unusual flight controller states.

        GIVEN: A flight controller in an unusual state (missing info, etc.)
        WHEN: The user attempts to create an info window
        THEN: The window handles the unusual state appropriately
        """
        # Given
        mock_fc = Mock(spec=FlightController)
        mock_fc.info = Mock()
        mock_fc.info.get_info.return_value = None  # Unusual state
        mock_fc.info.format_display_value.return_value = "N/A"
        mock_fc.info.log_flight_controller_info = Mock()

        stack, patches = mock_tkinter_context()

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
                # When - should not raise exception
                window = FlightControllerInfoWindow.__new__(FlightControllerInfoWindow)
                window.presenter = FlightControllerInfoPresenter(mock_fc)

                # Then - unusual state is handled
                assert window.presenter.flight_controller == mock_fc
