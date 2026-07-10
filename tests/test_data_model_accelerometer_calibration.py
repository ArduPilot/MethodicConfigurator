#!/usr/bin/env python3

"""
Tests for the data_model_accelerometer_calibration.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def connected_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller that reports a live MAVLink link."""
    flight_controller = MagicMock()
    flight_controller.master = MagicMock()
    return flight_controller


@pytest.fixture
def disconnected_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller with no MAVLink link."""
    flight_controller = MagicMock()
    flight_controller.master = None
    return flight_controller


class TestAccelerometerCalibrationDataModelConnection:
    """Test how the model reflects the flight controller connection state."""

    def test_model_reports_connected_when_master_link_exists(self, connected_flight_controller) -> None:
        """
        The model is connected when the backend holds a MAVLink master link.

        GIVEN: A flight controller with an active master link
        WHEN: is_connected is queried
        THEN: It reports the vehicle as connected
        """
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        assert model.is_connected() is True

    def test_model_reports_disconnected_when_master_link_absent(self, disconnected_flight_controller) -> None:
        """
        The model is disconnected when the backend has no MAVLink master link.

        GIVEN: A flight controller with no master link
        WHEN: is_connected is queried
        THEN: It reports the vehicle as disconnected
        """
        model = AccelerometerCalibrationDataModel(disconnected_flight_controller)

        assert model.is_connected() is False


class TestAccelerometerCalibrationDataModelSimpleCalibration:
    """Test the simple one-shot level calibration workflow."""

    def test_simple_calibration_is_refused_when_disconnected(self, disconnected_flight_controller) -> None:
        """
        Simple calibration cannot run without a connected flight controller.

        GIVEN: A disconnected flight controller
        WHEN: start_simple_calibration is called
        THEN: It fails with a not-connected message and never touches the backend
        """
        model = AccelerometerCalibrationDataModel(disconnected_flight_controller)

        success, message = model.start_simple_calibration()

        assert success is False
        assert "not connected" in message
        disconnected_flight_controller.start_accel_calibration_simple.assert_not_called()

    def test_simple_calibration_succeeds_when_backend_confirms(self, connected_flight_controller) -> None:
        """
        A successful backend calibration is reported as success to the user.

        GIVEN: A connected flight controller whose backend calibration succeeds
        WHEN: start_simple_calibration is called
        THEN: The backend is invoked and a success message is returned
        """
        connected_flight_controller.start_accel_calibration_simple.return_value = (True, "")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_simple_calibration()

        assert success is True
        assert "successful" in message
        connected_flight_controller.start_accel_calibration_simple.assert_called_once_with()

    def test_simple_calibration_surfaces_backend_error_message(self, connected_flight_controller) -> None:
        """
        A backend failure propagates its error message to the user.

        GIVEN: A connected flight controller whose backend calibration fails with a message
        WHEN: start_simple_calibration is called
        THEN: The backend error message is returned
        """
        connected_flight_controller.start_accel_calibration_simple.return_value = (False, "sensor timeout")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_simple_calibration()

        assert success is False
        assert message == "sensor timeout"

    def test_simple_calibration_provides_default_error_when_backend_is_silent(self, connected_flight_controller) -> None:
        """
        A backend failure with no message still yields a meaningful failure text.

        GIVEN: A connected flight controller whose backend calibration fails without a message
        WHEN: start_simple_calibration is called
        THEN: A default failure message is returned
        """
        connected_flight_controller.start_accel_calibration_simple.return_value = (False, "")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_simple_calibration()

        assert success is False
        assert "failed" in message


class TestAccelerometerCalibrationDataModelLevelCalibration:
    """Test the level-trim calibration workflow."""

    def test_level_calibration_is_refused_when_disconnected(self, disconnected_flight_controller) -> None:
        """
        Level calibration cannot run without a connected flight controller.

        GIVEN: A disconnected flight controller
        WHEN: start_level_calibration is called
        THEN: It fails with a not-connected message and never touches the backend
        """
        model = AccelerometerCalibrationDataModel(disconnected_flight_controller)

        success, message = model.start_level_calibration()

        assert success is False
        assert "not connected" in message
        disconnected_flight_controller.start_accel_calibration_level.assert_not_called()

    def test_level_calibration_succeeds_when_backend_confirms(self, connected_flight_controller) -> None:
        """
        A successful level-trim is reported as success to the user.

        GIVEN: A connected flight controller whose level calibration succeeds
        WHEN: start_level_calibration is called
        THEN: The backend is invoked and a success message is returned
        """
        connected_flight_controller.start_accel_calibration_level.return_value = (True, "")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_level_calibration()

        assert success is True
        assert "successful" in message
        connected_flight_controller.start_accel_calibration_level.assert_called_once_with()

    def test_level_calibration_surfaces_backend_error_message(self, connected_flight_controller) -> None:
        """
        A backend level-trim failure propagates its error message to the user.

        GIVEN: A connected flight controller whose level calibration fails with a message
        WHEN: start_level_calibration is called
        THEN: The backend error message is returned
        """
        connected_flight_controller.start_accel_calibration_level.return_value = (False, "vehicle not level")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_level_calibration()

        assert success is False
        assert message == "vehicle not level"

    def test_level_calibration_provides_default_error_when_backend_is_silent(self, connected_flight_controller) -> None:
        """
        A silent level-trim failure still yields a meaningful failure text.

        GIVEN: A connected flight controller whose level calibration fails without a message
        WHEN: start_level_calibration is called
        THEN: A default failure message is returned
        """
        connected_flight_controller.start_accel_calibration_level.return_value = (False, "")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_level_calibration()

        assert success is False
        assert "failed" in message


class TestAccelerometerCalibrationDataModelFullCalibration:
    """Test the interactive 6-position calibration start-up."""

    def test_full_calibration_is_refused_when_disconnected(self, disconnected_flight_controller) -> None:
        """
        Full calibration cannot start without a connected flight controller.

        GIVEN: A disconnected flight controller
        WHEN: start_full_calibration is called
        THEN: It fails with a not-connected message and never touches the backend
        """
        model = AccelerometerCalibrationDataModel(disconnected_flight_controller)

        success, message = model.start_full_calibration()

        assert success is False
        assert "not connected" in message
        disconnected_flight_controller.send_accel_calibration_full_start.assert_not_called()

    def test_full_calibration_start_resets_current_position_and_confirms_start(self, connected_flight_controller) -> None:
        """
        Starting a fresh full calibration clears any stale position state.

        GIVEN: A model that still holds a position from a previous run
        WHEN: start_full_calibration is called and the backend accepts the start
        THEN: The stale position is cleared and a start-success message is returned
        """
        connected_flight_controller.send_accel_calibration_full_start.return_value = (True, "")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)
        model._current_position = mavutil.mavlink.ACCELCAL_VEHICLE_POS_RIGHT

        success, message = model.start_full_calibration()

        assert success is True
        assert "follow on-screen instructions" in message
        assert model._current_position is None
        connected_flight_controller.send_accel_calibration_full_start.assert_called_once_with()

    def test_full_calibration_start_surfaces_backend_error_message(self, connected_flight_controller) -> None:
        """
        A failed full-calibration start propagates its backend error message.

        GIVEN: A connected flight controller whose start command fails with a message
        WHEN: start_full_calibration is called
        THEN: The backend error message is returned
        """
        connected_flight_controller.send_accel_calibration_full_start.return_value = (False, "link busy")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_full_calibration()

        assert success is False
        assert message == "link busy"

    def test_full_calibration_start_provides_default_error_when_backend_is_silent(self, connected_flight_controller) -> None:
        """
        A silent full-calibration start failure still yields a meaningful message.

        GIVEN: A connected flight controller whose start command fails without a message
        WHEN: start_full_calibration is called
        THEN: A default failure message is returned
        """
        connected_flight_controller.send_accel_calibration_full_start.return_value = (False, "")
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        success, message = model.start_full_calibration()

        assert success is False
        assert "Failed to start" in message


class TestAccelerometerCalibrationDataModelPolling:
    """Test the non-blocking position polling used to drive the wizard."""

    def test_poll_returns_none_and_keeps_state_when_no_message_available(self, connected_flight_controller) -> None:
        """
        Polling with no pending FC message leaves the tracked position untouched.

        GIVEN: A backend that has no new position message
        WHEN: poll_for_next_position is called
        THEN: None is returned and no current position is recorded
        """
        connected_flight_controller.poll_accel_cal_vehicle_pos.return_value = None
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        result = model.poll_for_next_position()

        assert result is None
        assert model._current_position is None

    def test_poll_records_requested_position_from_flight_controller(self, connected_flight_controller) -> None:
        """
        A new FC position request is returned and remembered for later confirmation.

        GIVEN: A backend that reports the NOSE DOWN position
        WHEN: poll_for_next_position is called
        THEN: That position is returned and stored as the current position
        """
        connected_flight_controller.poll_accel_cal_vehicle_pos.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN
        model = AccelerometerCalibrationDataModel(connected_flight_controller)

        result = model.poll_for_next_position()

        assert result == mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN
        assert model._current_position == mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN


class TestAccelerometerCalibrationDataModelPositionHelpers:
    """Test the pure helpers that classify and label calibration positions."""

    def test_known_position_returns_human_readable_instruction(self) -> None:
        """
        A recognised position maps to its human-readable instruction.

        GIVEN: The LEVEL position enum value
        WHEN: get_position_label is called
        THEN: The matching instruction text is returned
        """
        model = AccelerometerCalibrationDataModel(MagicMock())

        label = model.get_position_label(mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL)

        assert "LEVEL" in label

    def test_unknown_position_falls_back_to_generic_label(self) -> None:
        """
        An unrecognised position still produces a safe fallback label.

        GIVEN: A position value that is not in the known label map
        WHEN: get_position_label is called
        THEN: A generic "Unknown position" label including the value is returned
        """
        model = AccelerometerCalibrationDataModel(MagicMock())

        label = model.get_position_label(9999)

        assert "Unknown position" in label
        assert "9999" in label

    def test_success_terminal_state_is_reported_complete_and_successful(self) -> None:
        """
        The SUCCESS sentinel is both complete and successful.

        GIVEN: The ACCELCAL_VEHICLE_POS_SUCCESS terminal value
        WHEN: The completion helpers are queried
        THEN: The calibration is reported complete and successful
        """
        model = AccelerometerCalibrationDataModel(MagicMock())
        pos = mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS

        assert model.is_calibration_complete(pos) is True
        assert model.is_calibration_successful(pos) is True

    def test_failed_terminal_state_is_complete_but_not_successful(self) -> None:
        """
        The FAILED sentinel is complete but not successful.

        GIVEN: The ACCELCAL_VEHICLE_POS_FAILED terminal value
        WHEN: The completion helpers are queried
        THEN: The calibration is reported complete but not successful
        """
        model = AccelerometerCalibrationDataModel(MagicMock())
        pos = mavutil.mavlink.ACCELCAL_VEHICLE_POS_FAILED

        assert model.is_calibration_complete(pos) is True
        assert model.is_calibration_successful(pos) is False

    def test_intermediate_position_is_neither_complete_nor_successful(self) -> None:
        """
        A mid-sequence position is not a terminal state.

        GIVEN: The LEFT-side intermediate position
        WHEN: The completion helpers are queried
        THEN: The calibration is reported neither complete nor successful
        """
        model = AccelerometerCalibrationDataModel(MagicMock())
        pos = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT

        assert model.is_calibration_complete(pos) is False
        assert model.is_calibration_successful(pos) is False


class TestAccelerometerCalibrationDataModelConfirmCurrentPosition:
    """Test full-calibration position confirmation guard rails and backend delegation."""

    def test_confirm_current_position_fails_before_flight_controller_requests_position(self) -> None:
        """
        Confirmation is blocked until the flight controller requests a position.

        GIVEN: A full accelerometer calibration model with no current position
        WHEN: confirm_current_position is called
        THEN: It returns a failure message and does not call the flight controller
        """
        flight_controller = MagicMock()
        model = AccelerometerCalibrationDataModel(flight_controller)

        success, message = model.confirm_current_position()

        assert success is False
        assert "No position has been requested" in message
        flight_controller.confirm_accel_vehicle_pos.assert_not_called()

    def test_confirm_current_position_fails_after_success_completion(self) -> None:
        """
        Confirmation is blocked after calibration has completed successfully.

        GIVEN: The current position is ACCELCAL_VEHICLE_POS_SUCCESS
        WHEN: confirm_current_position is called
        THEN: It reports that calibration has already completed
        """
        flight_controller = MagicMock()
        model = AccelerometerCalibrationDataModel(flight_controller)
        model._current_position = mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS

        success, message = model.confirm_current_position()

        assert success is False
        assert "already completed" in message
        flight_controller.confirm_accel_vehicle_pos.assert_not_called()

    def test_confirm_current_position_fails_after_failed_completion(self) -> None:
        """
        Confirmation is blocked after calibration has failed.

        GIVEN: The current position is ACCELCAL_VEHICLE_POS_FAILED
        WHEN: confirm_current_position is called
        THEN: It reports that calibration has already completed
        """
        flight_controller = MagicMock()
        model = AccelerometerCalibrationDataModel(flight_controller)
        model._current_position = mavutil.mavlink.ACCELCAL_VEHICLE_POS_FAILED

        success, message = model.confirm_current_position()

        assert success is False
        assert "already completed" in message
        flight_controller.confirm_accel_vehicle_pos.assert_not_called()

    def test_confirm_current_position_delegates_normal_position_and_propagates_success_message(self) -> None:
        """
        A normal requested position is confirmed through the flight controller.

        GIVEN: The flight controller requested the LEVEL position
        AND: The backend confirmation succeeds with a message
        WHEN: confirm_current_position is called
        THEN: The backend receives the current position and the success message is returned
        """
        flight_controller = MagicMock()
        flight_controller.confirm_accel_vehicle_pos.return_value = (True, "confirmed")
        model = AccelerometerCalibrationDataModel(flight_controller)
        model._current_position = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL

        success, message = model.confirm_current_position()

        assert success is True
        assert message == "confirmed"
        flight_controller.confirm_accel_vehicle_pos.assert_called_once_with(mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL)

    def test_confirm_current_position_delegates_normal_position_and_propagates_error_message(self) -> None:
        """
        Backend confirmation errors are surfaced to the caller.

        GIVEN: The flight controller requested the LEFT position
        AND: The backend confirmation fails with an error message
        WHEN: confirm_current_position is called
        THEN: The backend error message is returned
        """
        flight_controller = MagicMock()
        flight_controller.confirm_accel_vehicle_pos.return_value = (False, "command denied")
        model = AccelerometerCalibrationDataModel(flight_controller)
        model._current_position = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT

        success, message = model.confirm_current_position()

        assert success is False
        assert message == "command denied"
        flight_controller.confirm_accel_vehicle_pos.assert_called_once_with(mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT)

    def test_confirm_current_position_provides_default_error_when_backend_is_silent(self) -> None:
        """
        A silent backend confirmation failure still yields a meaningful message.

        GIVEN: The flight controller requested the RIGHT position
        AND: The backend confirmation fails without a message
        WHEN: confirm_current_position is called
        THEN: A default failure message is returned
        """
        flight_controller = MagicMock()
        flight_controller.confirm_accel_vehicle_pos.return_value = (False, "")
        model = AccelerometerCalibrationDataModel(flight_controller)
        model._current_position = mavutil.mavlink.ACCELCAL_VEHICLE_POS_RIGHT

        success, message = model.confirm_current_position()

        assert success is False
        assert "Failed to send position confirmation" in message
