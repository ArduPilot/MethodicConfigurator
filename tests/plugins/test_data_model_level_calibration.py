#!/usr/bin/env python3

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

    def test_user_receives_started_status_before_controller_acknowledges(self, connected_flight_controller) -> None:
        """
        Starting level trim does not wait for the eventual controller response.

        GIVEN: A flight controller is connected and accepts level calibration
        WHEN: The user starts level calibration
        THEN: The user receives a started status and can poll for completion
        """
        # Arrange (Given)
        connected_flight_controller.start_accel_calibration_level.return_value = (True, "")
        model = LevelCalibrationDataModel(connected_flight_controller)

        # Act (When)
        success, message = model.start_level_calibration()

        # Assert (Then)
        assert success is True
        assert message == "Level calibration started"
        connected_flight_controller.start_accel_calibration_level.assert_called_once_with()

    def test_user_can_poll_until_level_calibration_acknowledgment_arrives(self, connected_flight_controller) -> None:
        """Pending and accepted ACKs are exposed without blocking the caller."""
        connected_flight_controller.poll_accel_calibration_level.side_effect = [None, (True, "")]
        model = LevelCalibrationDataModel(connected_flight_controller)

        assert model.poll_level_calibration() is None
        assert model.poll_level_calibration() == (True, "Level calibration successful")
        assert connected_flight_controller.poll_accel_calibration_level.call_count == 2

    def test_abandoning_calibration_releases_the_flight_controller_session(self, connected_flight_controller) -> None:
        """Closing the view must reach the persistent command manager through the model."""
        model = LevelCalibrationDataModel(connected_flight_controller)

        model.abort_level_calibration()

        connected_flight_controller.abort_accel_calibration_level.assert_called_once_with()

    def test_user_receives_controller_failure_when_polling_completes(self, connected_flight_controller) -> None:
        """A failed ACK is propagated as the completed model result."""
        connected_flight_controller.poll_accel_calibration_level.return_value = (False, "Command failed")
        model = LevelCalibrationDataModel(connected_flight_controller)

        assert model.poll_level_calibration() == (False, "Command failed")

    def test_user_receives_controller_failure_reason(self, connected_flight_controller) -> None:
        """
        A rejected calibration preserves the controller's actionable error.

        GIVEN: A connected controller rejects the level calibration
        WHEN: The user starts level calibration
        THEN: The controller's failure reason is returned
        """
        # Arrange (Given)
        connected_flight_controller.start_accel_calibration_level.return_value = (False, "link down")
        model = LevelCalibrationDataModel(connected_flight_controller)

        # Act (When)
        success, message = model.start_level_calibration()

        # Assert (Then)
        assert success is False
        assert message == "link down"

    def test_user_receives_fallback_when_start_returns_no_failure_reason(self, connected_flight_controller) -> None:
        """
        A failed calibration with no controller detail still gives the user a reason.

        GIVEN: A connected controller rejects calibration without an error message
        WHEN: The user starts level calibration
        THEN: The generic level-calibration failure message is returned
        """
        # Arrange (Given)
        connected_flight_controller.start_accel_calibration_level.return_value = (False, "")
        model = LevelCalibrationDataModel(connected_flight_controller)

        # Act (When)
        success, message = model.start_level_calibration()

        # Assert (Then)
        assert success is False
        assert message == "Failed to start level calibration"
