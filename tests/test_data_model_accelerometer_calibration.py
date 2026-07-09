#!/usr/bin/env python3

"""
Tests for the data_model_accelerometer_calibration.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

from pymavlink import mavutil

from ardupilot_methodic_configurator.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel

# pylint: disable=protected-access


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
