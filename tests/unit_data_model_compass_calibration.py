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
    """Fixture providing a connected flight controller."""
    fc = MagicMock(spec=FlightController)
    fc.master = MagicMock()

    fc.start_compass_calibration.return_value = (True, "")
    fc.cancel_compass_calibration.return_value = (True, "")
    fc.get_compass_calibration_progress.return_value = [{"type": "PROGRESS", "compass_id": 0, "completion_pct": 50}]

    return fc


@pytest.fixture
def disconnected_flight_controller() -> MagicMock:
    """Fixture providing a disconnected flight controller."""
    fc = MagicMock(spec=FlightController)
    fc.master = None

    return fc


@pytest.fixture
def connected_compass_calibration_model(connected_flight_controller: MagicMock) -> CompassCalibrationDataModel:
    """Fixture providing a compass calibration model with a connected flight controller."""
    return CompassCalibrationDataModel(connected_flight_controller)


@pytest.fixture
def disconnected_compass_calibration_model(
    disconnected_flight_controller: MagicMock,
) -> CompassCalibrationDataModel:
    """Fixture providing a compass calibration model with a disconnected flight controller."""
    return CompassCalibrationDataModel(disconnected_flight_controller)


class TestCompassCalibrationWithDisconnectedFlightController:
    """Test compass calibration behavior when the flight controller is disconnected."""

    def test_user_sees_not_connected_state_when_fc_is_disconnected(
        self, disconnected_compass_calibration_model: CompassCalibrationDataModel
    ) -> None:
        """
        The model reports that the flight controller is not connected.

        GIVEN: Flight controller is not connected (master is None)
        WHEN: The connection state is checked
        THEN: The model should report False
        """
        # Act
        result = disconnected_compass_calibration_model.is_connected()

        # Assert
        assert result is False

    def test_user_cannot_start_calibration_without_a_flight_controller(
        self, disconnected_compass_calibration_model: CompassCalibrationDataModel, disconnected_flight_controller: MagicMock
    ) -> None:
        """
        Starting calibration fails early when there is no connection.

        GIVEN: Flight controller is disconnected
        WHEN: The user starts calibration
        THEN: The model returns a connection error
        AND: The backend is not called
        """
        # Act
        success, error_msg = disconnected_compass_calibration_model.start_calibration()

        # Assert
        assert success is False
        assert error_msg == "Flight controller not connected"
        disconnected_flight_controller.start_compass_calibration.assert_not_called()
        assert disconnected_compass_calibration_model._is_calibrating is False

    def test_user_cannot_cancel_calibration_without_a_flight_controller(
        self, disconnected_compass_calibration_model: CompassCalibrationDataModel, disconnected_flight_controller: MagicMock
    ) -> None:
        """
        Canceling calibration fails early when there is no connection.

        GIVEN: Flight controller is disconnected
        WHEN: The user cancels calibration
        THEN: The model returns a connection error
        AND: The backend is not called
        """
        # Act
        success, error_msg = disconnected_compass_calibration_model.cancel_calibration()

        # Assert
        assert success is False
        assert error_msg == "Flight controller not connected"
        disconnected_flight_controller.cancel_compass_calibration.assert_not_called()

    def test_user_sees_no_progress_data_when_fc_is_disconnected(
        self, disconnected_compass_calibration_model: CompassCalibrationDataModel, disconnected_flight_controller: MagicMock
    ) -> None:
        """
        Progress polling returns no updates when there is no connection.

        GIVEN: Flight controller is disconnected
        WHEN: The GUI asks for calibration progress
        THEN: The model returns an empty list
        AND: The backend is not called
        """
        # Act
        result = disconnected_compass_calibration_model.get_progress()

        # Assert
        assert result == []
        disconnected_flight_controller.get_compass_calibration_progress.assert_not_called()


class TestCompassCalibrationWithConnectedFlightController:
    """Test compass calibration behavior when the flight controller is connected."""

    def test_user_sees_connected_state_when_fc_is_connected(
        self, connected_compass_calibration_model: CompassCalibrationDataModel
    ) -> None:
        """
        The model reports that the flight controller is connected.

        GIVEN: Flight controller is connected (master is not None)
        WHEN: The connection state is checked
        THEN: The model should report True
        """
        assert connected_compass_calibration_model.is_connected() is True

    def test_user_can_start_calibration_successfully(
        self, connected_compass_calibration_model: CompassCalibrationDataModel, connected_flight_controller: MagicMock
    ) -> None:
        """
        Starting calibration delegates to the backend and updates model state.

        GIVEN: Flight controller is connected and will successfully start calibration
        WHEN: The user starts calibration
        THEN: The backend command succeeds
        AND: The model marks itself as calibrating
        """
        # Arrange
        assert connected_compass_calibration_model._is_calibrating is False

        # Act
        success, error_msg = connected_compass_calibration_model.start_calibration()

        # Assert
        connected_flight_controller.start_compass_calibration.assert_called_once()
        assert success is True
        assert error_msg == ""
        assert connected_compass_calibration_model._is_calibrating is True

    def test_user_sees_backend_error_when_starting_calibration_fails(
        self, connected_compass_calibration_model: CompassCalibrationDataModel, connected_flight_controller: MagicMock
    ) -> None:
        """
        Backend failures are surfaced and the calibrating state stays unchanged.

        GIVEN: Flight controller backend fails to start calibration
        WHEN: The user starts calibration
        THEN: The backend error is returned
        AND: The model does not enter the calibrating state
        """
        # Arrange
        connected_flight_controller.start_compass_calibration.return_value = (False, "MAVLink command rejected")

        # Act
        success, error_msg = connected_compass_calibration_model.start_calibration()

        # Assert
        assert success is False
        assert error_msg == "MAVLink command rejected"
        assert connected_compass_calibration_model._is_calibrating is False

    def test_user_can_cancel_calibration_successfully(
        self, connected_compass_calibration_model: CompassCalibrationDataModel, connected_flight_controller: MagicMock
    ) -> None:
        """
        Canceling calibration delegates to the backend and clears model state.

        GIVEN: Flight controller is calibrating and backend successfully cancels
        WHEN: The user cancels calibration
        THEN: The backend command succeeds
        AND: The model leaves the calibrating state
        """
        # Arrange
        connected_compass_calibration_model._is_calibrating = True

        # Act
        success, error_msg = connected_compass_calibration_model.cancel_calibration()

        # Assert
        connected_flight_controller.cancel_compass_calibration.assert_called_once()
        assert success is True
        assert error_msg == ""
        assert connected_compass_calibration_model._is_calibrating is False

    def test_user_can_mark_calibration_complete(
        self, connected_compass_calibration_model: CompassCalibrationDataModel
    ) -> None:
        """
        The model can be explicitly marked as finished after the popup completes.

        GIVEN: Compass calibration is in progress
        WHEN: The workflow reaches the final completion state
        THEN: The calibrating flag is cleared
        """
        # Arrange
        connected_compass_calibration_model._is_calibrating = True

        # Act
        connected_compass_calibration_model.finish_calibration()

        # Assert
        assert connected_compass_calibration_model._is_calibrating is False

    def test_user_sees_backend_error_when_canceling_calibration_fails(
        self, connected_compass_calibration_model: CompassCalibrationDataModel, connected_flight_controller: MagicMock
    ) -> None:
        """
        Backend cancel failures are surfaced and the state is preserved.

        GIVEN: Flight controller backend fails to cancel calibration
        WHEN: The user cancels calibration
        THEN: The backend error is returned
        AND: The model stays in the calibrating state
        """
        # Arrange
        connected_flight_controller.cancel_compass_calibration.return_value = (False, "Timeout")
        connected_compass_calibration_model._is_calibrating = True

        # Act
        success, error_msg = connected_compass_calibration_model.cancel_calibration()

        # Assert
        assert success is False
        assert error_msg == "Timeout"
        assert connected_compass_calibration_model._is_calibrating is True

    def test_user_can_poll_progress_updates_from_the_backend(
        self, connected_compass_calibration_model: CompassCalibrationDataModel, connected_flight_controller: MagicMock
    ) -> None:
        """
        Progress polling returns the backend updates unchanged.

        GIVEN: Flight controller is connected
        WHEN: The GUI asks for calibration progress
        THEN: The backend progress list is returned unchanged
        """
        # Arrange
        expected_data = [{"type": "REPORT", "compass_id": 0, "status": 4}]
        connected_flight_controller.get_compass_calibration_progress.return_value = expected_data

        # Act
        result = connected_compass_calibration_model.get_progress()

        # Assert
        connected_flight_controller.get_compass_calibration_progress.assert_called_once()
        assert result == expected_data
