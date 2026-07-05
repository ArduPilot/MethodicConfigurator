#!/usr/bin/env python3

"""
Unit tests for compass calibration data model.

This file tests the CompassCalibrationDataModel class in isolation using mocks.
Tests focus on business logic, state management, and flight controller delegation.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_compass_calibration import CompassCalibrationDataModel

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def connected_flight_controller() -> MagicMock:
    """Fixture provides a connected flight controller."""
    fc = MagicMock(spec=FlightController)
    fc.master = MagicMock()  # Simulate connected state

    # Setup default successful return values for compass methods
    fc.start_compass_calibration.return_value = (True, "")
    fc.cancel_compass_calibration.return_value = (True, "")
    fc.get_compass_calibration_progress.return_value = {"type": "PROGRESS", "completion_pct": 50}

    return fc


@pytest.fixture
def disconnected_flight_controller() -> MagicMock:
    """Fixture providing a disconnected flight controller."""
    fc = MagicMock(spec=FlightController)
    fc.master = None  # Simulate disconnected state

    return fc


@pytest.fixture
def compass_calibration_data_model(
    connected_flight_controller: MagicMock,
) -> CompassCalibrationDataModel:
    """Fixture providing a compass calibration data model with connected flight controller."""
    return CompassCalibrationDataModel(connected_flight_controller)


# ==================== UNIT TESTS ====================


class TestCompassCalibrationWithDisconnectedFlightController:
    """Test compass calibration behavior when flight controller is disconnected."""

    def test_is_connected_returns_false_when_disconnected(self, disconnected_flight_controller: MagicMock) -> None:
        """
        is_connected() returns False when flight controller is disconnected.

        GIVEN: Flight controller is not connected (master is None)
        WHEN: is_connected() is called
        THEN: Should return False
        """
        # Arrange: Disconnected FC
        model = CompassCalibrationDataModel(disconnected_flight_controller)

        # Act
        result = model.is_connected()

        # Assert
        assert result is False, "Should return False when flight controller disconnected"

    def test_start_calibration_fails_gracefully_when_disconnected(self, disconnected_flight_controller: MagicMock) -> None:
        """
        start_calibration aborts and returns an error when disconnected.

        GIVEN: Flight controller is disconnected
        WHEN: start_calibration() is called
        THEN: It should return False with an error message
        AND: It should not call the flight controller backend
        """
        model = CompassCalibrationDataModel(disconnected_flight_controller)

        success, error_msg = model.start_calibration()

        assert success is False
        assert error_msg == "Flight controller not connected"
        assert model._is_calibrating is False
        disconnected_flight_controller.start_compass_calibration.assert_not_called()

    def test_cancel_calibration_fails_gracefully_when_disconnected(self, disconnected_flight_controller: MagicMock) -> None:
        """
        cancel_calibration aborts and returns an error when disconnected.

        GIVEN: Flight controller is disconnected
        WHEN: cancel_calibration() is called
        THEN: It should return False with an error message
        AND: It should not call the flight controller backend
        """
        model = CompassCalibrationDataModel(disconnected_flight_controller)

        success, error_msg = model.cancel_calibration()

        assert success is False
        assert error_msg == "Flight controller not connected"
        disconnected_flight_controller.cancel_compass_calibration.assert_not_called()

    def test_get_progress_returns_none_when_disconnected(self, disconnected_flight_controller: MagicMock) -> None:
        """
        get_progress returns None when disconnected.

        GIVEN: Flight controller is disconnected
        WHEN: get_progress() is called
        THEN: It should return None
        AND: It should not call the flight controller backend
        """
        model = CompassCalibrationDataModel(disconnected_flight_controller)

        result = model.get_progress()

        assert result is None
        disconnected_flight_controller.get_compass_calibration_progress.assert_not_called()


class TestCompassCalibrationWithConnectedFlightController:
    """Test compass calibration behavior when flight controller is connected."""

    def test_is_connected_returns_true_when_connected(
        self, compass_calibration_data_model: CompassCalibrationDataModel
    ) -> None:
        """
        is_connected() returns True when flight controller is connected.

        GIVEN: Flight controller is connected (master is not None)
        WHEN: is_connected() is called
        THEN: Should return True
        """
        assert compass_calibration_data_model.is_connected() is True

    def test_start_calibration_success_updates_state(self, connected_flight_controller: MagicMock) -> None:
        """
        start_calibration delegates to the backend and updates internal state on success.

        GIVEN: Flight controller is connected and will successfully start calibration
        WHEN: start_calibration() is called
        THEN: It should delegate to flight_controller.start_compass_calibration()
        AND: Return True with no error
        AND: Update _is_calibrating state to True
        """
        model = CompassCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.start_compass_calibration.return_value = (True, "")

        assert model._is_calibrating is False

        success, error_msg = model.start_calibration()

        connected_flight_controller.start_compass_calibration.assert_called_once()
        assert success is True
        assert error_msg == ""
        assert model._is_calibrating is True

    def test_start_calibration_failure_preserves_state(self, connected_flight_controller: MagicMock) -> None:
        """
        start_calibration preserves state if backend command fails.

        GIVEN: Flight controller backend fails to start calibration
        WHEN: start_calibration() is called
        THEN: It should return False with the backend error message
        AND: _is_calibrating should remain False
        """
        model = CompassCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.start_compass_calibration.return_value = (False, "MAVLink command rejected")

        success, error_msg = model.start_calibration()

        assert success is False
        assert error_msg == "MAVLink command rejected"
        assert model._is_calibrating is False

    def test_cancel_calibration_success_updates_state(self, connected_flight_controller: MagicMock) -> None:
        """
        cancel_calibration delegates to the backend and updates internal state on success.

        GIVEN: Flight controller is calibrating and backend successfully cancels
        WHEN: cancel_calibration() is called
        THEN: It should delegate to flight_controller.cancel_compass_calibration()
        AND: Update _is_calibrating state to False
        """
        model = CompassCalibrationDataModel(connected_flight_controller)
        model._is_calibrating = True  # Manually set state as if calibration is running
        connected_flight_controller.cancel_compass_calibration.return_value = (True, "")

        success, error_msg = model.cancel_calibration()

        connected_flight_controller.cancel_compass_calibration.assert_called_once()
        assert success is True
        assert error_msg == ""
        assert model._is_calibrating is False

    def test_cancel_calibration_failure_preserves_state(self, connected_flight_controller: MagicMock) -> None:
        """
        cancel_calibration preserves state if backend command fails.

        GIVEN: Flight controller backend fails to cancel calibration
        WHEN: cancel_calibration() is called
        THEN: It should return False with the backend error message
        AND: _is_calibrating should remain True
        """
        model = CompassCalibrationDataModel(connected_flight_controller)
        model._is_calibrating = True
        connected_flight_controller.cancel_compass_calibration.return_value = (False, "Timeout")

        success, error_msg = model.cancel_calibration()

        assert success is False
        assert error_msg == "Timeout"
        assert model._is_calibrating is True

    def test_get_progress_delegates_to_backend(self, connected_flight_controller: MagicMock) -> None:
        """
        get_progress delegates data retrieval directly to the backend.

        GIVEN: Flight controller is connected
        WHEN: get_progress() is called
        THEN: It should return the dictionary provided by the backend
        """
        model = CompassCalibrationDataModel(connected_flight_controller)
        expected_data = {"type": "REPORT", "status": 4}
        connected_flight_controller.get_compass_calibration_progress.return_value = expected_data

        result = model.get_progress()

        connected_flight_controller.get_compass_calibration_progress.assert_called_once()
        assert result == expected_data
