"""
Behavior-driven tests for the level calibration data model.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel


class TestLevelCalibrationWorkflow:
    """Test the user's level-trim calibration workflow."""

    def test_user_is_told_to_connect_before_starting_level_calibration(self, disconnected_flight_controller) -> None:
        """
        A disconnected controller prevents the calibration command.

        GIVEN: The user has not connected a flight controller
        WHEN: They start level calibration
        THEN: They receive a connection error and no MAVLink command is sent
        """
        # Arrange (Given)
        model = LevelCalibrationDataModel(disconnected_flight_controller)

        # Act (When)
        success, message = model.start_level_calibration()

        # Assert (Then)
        assert success is False
        assert message == "Flight controller not connected"
        disconnected_flight_controller.start_accel_calibration_level.assert_not_called()

    def test_user_receives_success_after_controller_levels_vehicle(self, connected_flight_controller) -> None:
        """
        A successful controller response confirms the level trim.

        GIVEN: A flight controller is connected and accepts level calibration
        WHEN: The user starts level calibration
        THEN: The user receives the successful result
        """
        # Arrange (Given)
        connected_flight_controller.start_accel_calibration_level.return_value = (True, "")
        model = LevelCalibrationDataModel(connected_flight_controller)

        # Act (When)
        success, message = model.start_level_calibration()

        # Assert (Then)
        assert success is True
        assert message == "Level calibration successful"
        connected_flight_controller.start_accel_calibration_level.assert_called_once_with()

    def test_user_receives_controller_failure_reason(self, connected_flight_controller) -> None:
        """
        A rejected calibration preserves the controller's actionable error.

        GIVEN: A connected controller rejects the level calibration
        WHEN: The user starts level calibration
        THEN: The controller's failure reason is returned
        """
        # Arrange (Given)
        connected_flight_controller.start_accel_calibration_level.return_value = (False, "Vehicle is moving")
        model = LevelCalibrationDataModel(connected_flight_controller)

        # Act (When)
        success, message = model.start_level_calibration()

        # Assert (Then)
        assert success is False
        assert message == "Vehicle is moving"
