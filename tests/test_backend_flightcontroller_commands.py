#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_commands.py.

This file focuses on command execution behavior including motor tests,
battery status requests, and parameter reset commands.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import time
from unittest.mock import MagicMock, Mock

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands

# pylint: disable=too-many-lines


class TestFlightControllerCommandsInitialization:
    """Test command manager initialization and setup."""

    def test_user_can_create_commands_manager(self) -> None:
        """
        User can create command manager with required dependencies.

        GIVEN: Params manager and connection manager available
        WHEN: User creates commands manager
        THEN: Manager should be initialized successfully
        AND: Dependencies should be stored
        """
        # Given: Mock dependencies
        mock_params_mgr = Mock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None

        # When: Create commands manager
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # Then: Manager initialized
        assert commands_mgr is not None
        assert commands_mgr.master is None

    def test_commands_manager_requires_dependencies(self) -> None:
        """
        Command manager requires both params and connection managers.

        GIVEN: Missing required dependencies
        WHEN: User attempts to create commands manager
        THEN: ValueError should be raised
        AND: Clear error message should be provided
        """
        # When/Then: Missing params manager
        with pytest.raises(ValueError, match="params_manager is required"):
            FlightControllerCommands(params_manager=None, connection_manager=Mock())

        # When/Then: Missing connection manager
        with pytest.raises(ValueError, match="connection_manager is required"):
            FlightControllerCommands(params_manager=Mock(), connection_manager=None)


class TestFlightControllerCommandsMotorTest:
    """Test motor testing command functionality."""

    def test_user_can_test_individual_motor(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can test individual motor at specified throttle.

        GIVEN: Connected flight controller ready for motor test
        WHEN: User tests motor 1 at 10% throttle
        THEN: MAVLink command should be sent correctly
        AND: Command acknowledgment should be received
        """
        # Given: Connected FC with ACK response
        mock_master, mock_conn_mgr = mock_connected_master

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Test motor
        success, error = commands_mgr.test_motor(
            test_sequence_nr=1, motor_letters="A", motor_output_nr=1, throttle_percent=10, timeout_seconds=2
        )

        # Then: Command sent successfully
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()

    def test_motor_test_fails_without_connection(self) -> None:
        """
        Motor test fails gracefully without connection.

        GIVEN: No flight controller connection
        WHEN: User attempts motor test
        THEN: Operation should fail with clear error
        AND: No exceptions should be raised
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Attempt motor test
        success, error = commands_mgr.test_motor(1, "A", 1, 10, 2)

        # Then: Clear failure
        assert success is False
        assert "connection" in error.lower()


class TestFlightControllerCommandsBatteryStatus:
    """Test battery status request functionality."""

    def test_user_can_request_battery_status(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can request periodic battery status updates.

        GIVEN: Connected flight controller with battery monitoring
        WHEN: User requests battery status at 1Hz
        THEN: Data stream request should be sent
        AND: Command should be acknowledged
        """
        # Given: Connected FC
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Request battery status
        success, error = commands_mgr.request_periodic_battery_status(
            interval_microseconds=1000000  # 1Hz
        )

        # Then: Request sent
        assert success is True
        assert error == ""

    def test_user_can_get_battery_status(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can get current battery status from flight controller.

        GIVEN: Flight controller with battery monitoring enabled
        WHEN: User requests current battery status
        THEN: Voltage and current should be returned
        AND: Values should be in expected ranges
        """
        # Given: FC with battery data
        mock_master, mock_conn_mgr = mock_connected_master
        mock_battery_msg = MagicMock()
        mock_battery_msg.voltages = [4200, 4180, 4190]  # mV
        mock_battery_msg.current_battery = 2500  # centi-amps
        mock_master.recv_match.return_value = mock_battery_msg

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4.0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_data, message = commands_mgr.get_battery_status()

        # Then: Status retrieved
        assert battery_data is not None
        assert message == ""
        voltage, current = battery_data
        assert voltage > 0
        assert current >= 0


class TestFlightControllerCommandsParameterReset:  # pylint: disable=too-few-public-methods
    """Test parameter reset command functionality."""

    def test_user_can_reset_all_parameters_to_defaults(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can reset all parameters to factory defaults.

        GIVEN: Flight controller with modified parameters
        WHEN: User resets all parameters to defaults
        THEN: Reset command should be sent
        AND: Command should be acknowledged
        """
        # Given: Connected FC
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Reset parameters
        success, error = commands_mgr.reset_all_parameters_to_default()

        # Then: Command sent
        assert success is True
        assert error == ""


class TestFlightControllerCommandsSendCommandAndWaitAck:
    """Test low-level command sending with ACK waiting."""

    def test_command_waits_for_acknowledgment(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Command sending waits for proper acknowledgment.

        GIVEN: Flight controller command infrastructure
        WHEN: User sends command with ACK expected
        THEN: Function should wait for ACK message
        AND: Return success when ACK received
        """
        # Given: FC that sends ACK
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = 123
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Send command
        success, error = commands_mgr.send_command_and_wait_ack(
            command=123, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0, timeout=1.0
        )

        # Then: ACK received
        assert success is True
        assert error == ""

    def test_command_timeout_returns_error(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Command timeout returns appropriate error.

        GIVEN: Flight controller not responding
        WHEN: User sends command with timeout
        THEN: Timeout error should be returned
        AND: Error message should indicate timeout
        """
        # Given: FC that doesn't respond
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Send command with short timeout
        success, error = commands_mgr.send_command_and_wait_ack(
            command=999, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0, timeout=0.1
        )

        # Then: Timeout error
        assert success is False
        assert "timeout" in error.lower()


class TestFlightControllerCommandsPropertyDelegation:  # pylint: disable=too-few-public-methods
    """Test property delegation to connection manager."""

    def test_master_property_delegates_to_connection_manager(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Master property correctly delegates to connection manager.

        GIVEN: Commands manager with connection manager
        WHEN: Accessing master property
        THEN: Connection manager's master should be returned
        """
        # Given: Connection with master
        mock_master, mock_conn_mgr = mock_connected_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Access master
        retrieved_master = commands_mgr.master

        # Then: Correct master returned
        assert retrieved_master is mock_master


class TestFlightControllerCommandsEdgeCases:
    """Additional edge-case tests for battery and command handling."""

    def test_request_periodic_battery_status_denied(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """Battery status request should propagate NACK/denied responses."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_DENIED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.request_periodic_battery_status(interval_microseconds=1000000)

        assert success is False
        assert "denied" in error.lower()

    def test_get_battery_status_returns_recent_cache(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """Return cached battery data when no new telemetry is available but a recent value exists."""
        mock_master, mock_conn_mgr = mock_connected_master
        # Simulate no new telemetry
        mock_master.recv_match.return_value = None

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4.0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # Inject a recent cached battery reading
        commands_mgr._last_battery_status = (11.1, 2.2)  # pylint: disable=protected-access
        commands_mgr._last_battery_message_time = time.time()  # now-ish # pylint: disable=protected-access

        data, _ = commands_mgr.get_battery_status()

        assert data == (11.1, 2.2)

    def test_get_battery_status_handles_invalid_readings(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """BATTERY_STATUS messages with invalid sentinel values (-1) should be converted to zeros."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_battery_msg = MagicMock()
        mock_battery_msg.voltages = [-1]
        mock_battery_msg.current_battery = -1
        mock_master.recv_match.return_value = mock_battery_msg

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4.0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        battery_data, _ = commands_mgr.get_battery_status()

        assert battery_data is not None
        voltage, current = battery_data
        assert voltage == 0.0
        assert current == 0.0

    def test_motor_test_denied_ack(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """Motor test should fail when FC returns a DENIED acknowledgment."""
        mock_master, mock_conn_mgr = mock_connected_master

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_DENIED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.test_motor(1, "A", 1, 10, 2)

        assert success is False
        assert "denied" in error.lower()

    def test_send_command_unknown_result(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """send_command_and_wait_ack should return an error for unknown result codes."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = 9999  # unknown result
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        assert success is False
        assert "unknown result" in error.lower()

    def test_send_command_in_progress_then_accepted(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """send_command_and_wait_ack should handle IN_PROGRESS followed by ACCEPTED."""
        mock_master, mock_conn_mgr = mock_connected_master

        in_progress = MagicMock()
        in_progress.command = 555
        in_progress.result = mavutil.mavlink.MAV_RESULT_IN_PROGRESS
        in_progress.progress = 10

        accepted = MagicMock()
        accepted.command = 555
        accepted.result = mavutil.mavlink.MAV_RESULT_ACCEPTED

        # First return in-progress, then accepted
        mock_master.recv_match.side_effect = [in_progress, accepted]

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_command_and_wait_ack(command=555, timeout=1.0)

        assert success is True
        assert error == ""


class TestFlightControllerCommandsAllMotors:
    """Test test_all_motors functionality."""

    def test_user_can_test_all_motors(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can test all motors simultaneously.

        GIVEN: Connected flight controller ready for motor test
        WHEN: User tests all 4 motors at 25% throttle
        THEN: Motor commands should be sent for each motor
        AND: Method should return success
        """
        # Given: Connected FC
        mock_master, mock_conn_mgr = mock_connected_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Test all motors
        success, error = commands_mgr.test_all_motors(nr_of_motors=4, throttle_percent=25, timeout_seconds=5)

        # Then: Commands should be sent
        assert success is True
        assert error == ""
        assert mock_master.mav.command_long_send.call_count == 4

    def test_test_all_motors_fails_without_connection(self) -> None:
        """
        Testing all motors fails without connection.

        GIVEN: Flight controller with no active connection
        WHEN: User attempts to test all motors
        THEN: Should return failure
        AND: Error message should indicate no connection
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When/Then
        success, error = commands_mgr.test_all_motors(nr_of_motors=4, throttle_percent=25, timeout_seconds=5)

        assert success is False
        assert "no flight controller connection" in error.lower()


class TestFlightControllerCommandsSequencedMotors:
    """Test test_motors_in_sequence functionality."""

    def test_user_can_test_motors_in_sequence(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can test motors in sequence.

        GIVEN: Connected flight controller ready for motor test
        WHEN: User tests 4 motors starting from motor 1 at 30% throttle
        THEN: Sequential motor test command should be sent with wait for ack
        AND: Method should return success
        """
        # Given: Connected FC with ACK response
        mock_master, mock_conn_mgr = mock_connected_master

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Test motors in sequence
        success, error = commands_mgr.test_motors_in_sequence(
            start_motor=1, motor_count=4, throttle_percent=30, timeout_seconds=3
        )

        # Then: Command acknowledged
        assert success is True
        assert error == ""

    def test_test_motors_in_sequence_fails_without_connection(self) -> None:
        """
        Testing motors in sequence fails without connection.

        GIVEN: Flight controller with no active connection
        WHEN: User attempts to test motors in sequence
        THEN: Should return failure
        AND: Error message should indicate no connection
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When/Then
        success, error = commands_mgr.test_motors_in_sequence(
            start_motor=1, motor_count=4, throttle_percent=30, timeout_seconds=3
        )

        assert success is False
        assert "no flight controller connection" in error.lower()


class TestFlightControllerCommandsStopMotors:  # pylint: disable=too-few-public-methods
    """Test stop_all_motors functionality."""

    def test_user_can_stop_all_motors(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can stop all motors with emergency stop command.

        GIVEN: Connected flight controller with running motors
        WHEN: User executes stop all motors command
        THEN: Motor stop command should be sent
        AND: Command should be acknowledged
        """
        # Given: Connected FC with ACK response
        mock_master, mock_conn_mgr = mock_connected_master

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Stop all motors
        success, error = commands_mgr.stop_all_motors()

        # Then: Command acknowledged
        assert success is True
        assert error == ""


class TestFlightControllerCommandsWrapperMethods:
    """Test wrapper methods that delegate to business logic."""

    def test_user_can_get_voltage_thresholds(self) -> None:
        """
        User can retrieve voltage thresholds for safe motor testing.

        GIVEN: Parameters manager with battery voltage parameters
        WHEN: User requests voltage thresholds
        THEN: Should return min and max voltage values
        AND: Values should be reasonable thresholds
        """
        # Given: Mock params manager with typical battery parameters
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {
            "BATT_ARM_VOLT": 9.6,
            "MOT_BAT_VOLT_MAX": 12.6,
        }

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get voltage thresholds
        min_volt, max_volt = commands_mgr.get_voltage_thresholds()

        # Then: Should return reasonable thresholds
        assert isinstance(min_volt, (int, float))
        assert isinstance(max_volt, (int, float))
        assert min_volt < max_volt
        assert min_volt == 9.6
        assert max_volt == 12.6

    def test_user_can_check_battery_monitoring_enabled(self) -> None:
        """
        User can check if battery monitoring is enabled.

        GIVEN: Parameters manager with BATT_MONITOR parameter
        WHEN: User checks battery monitoring status
        THEN: Should return True if BATT_MONITOR != 0
        """
        # Given: Battery monitoring enabled
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Check if battery monitoring enabled
        enabled = commands_mgr.is_battery_monitoring_enabled()

        # Then: Should be True
        assert enabled is True

    def test_battery_monitoring_disabled_returns_false(self) -> None:
        """
        Battery monitoring check returns False when disabled.

        GIVEN: Parameters manager with BATT_MONITOR=0
        WHEN: User checks battery monitoring status
        THEN: Should return False
        """
        # Given: Battery monitoring disabled
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 0}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Check if battery monitoring enabled
        enabled = commands_mgr.is_battery_monitoring_enabled()

        # Then: Should be False
        assert enabled is False

    def test_user_can_get_frame_info(self) -> None:
        """
        User can retrieve frame class and type information.

        GIVEN: Parameters manager with FRAME_CLASS and FRAME_TYPE
        WHEN: User requests frame information
        THEN: Should return frame class and type as integers
        """
        # Given: Mock params manager with frame parameters
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {
            "FRAME_CLASS": 1,  # Copter quadrotor
            "FRAME_TYPE": 1,  # X
        }

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get frame info
        frame_class, frame_type = commands_mgr.get_frame_info()

        # Then: Should return frame class and type
        assert frame_class == 1
        assert frame_type == 1


class TestFlightControllerCommandsAccelerometerCalibration:
    """Test accelerometer calibration command functionality."""

    def test_user_can_start_simple_accelerometer_calibration(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can start the simple one-shot accelerometer calibration.

        GIVEN: Connected flight controller ready for calibration
        WHEN: User starts simple accelerometer calibration
        THEN: Preflight calibration command should be sent with param5=4
        AND: The command should be acknowledged successfully
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_simple()

        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        args = mock_master.mav.command_long_send.call_args.args
        assert args[2] == mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        assert args[8] == 4.0

    def test_simple_accelerometer_calibration_fails_without_connection(self) -> None:
        """
        Simple accelerometer calibration fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: User starts simple accelerometer calibration
        THEN: The method should return a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_simple()

        assert success is False
        assert "connection" in error.lower()

    def test_user_can_start_full_accelerometer_calibration(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can start the interactive 6-position accelerometer calibration.

        GIVEN: Connected flight controller ready for calibration
        WHEN: User starts full accelerometer calibration
        THEN: Preflight calibration command should be sent with param5=1
        AND: The command should be reported as sent successfully
        """
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_accel_calibration_full_start()

        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        args = mock_master.mav.command_long_send.call_args.args
        assert args[2] == mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        assert args[8] == 1

    def test_full_accelerometer_calibration_fails_without_connection(self) -> None:
        """
        Full accelerometer calibration fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: User starts the full accelerometer calibration
        THEN: The method should return a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_accel_calibration_full_start()

        assert success is False
        assert "connection" in error.lower()

    def test_poll_accel_cal_vehicle_pos_is_non_blocking_and_parses_position(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling for accel calibration position should not block the UI thread.

        GIVEN: A COMMAND_LONG message requesting a calibration position
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: The message should be read with non-blocking recv_match
        AND: The requested position should be returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_msg = MagicMock()
        mock_msg.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        mock_msg.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT
        # Return the message once, then None to terminate the drain loop
        mock_master.recv_match.side_effect = [mock_msg, None]

        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        position = commands_mgr.poll_accel_cal_vehicle_pos()

        assert position == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT
        assert mock_master.recv_match.call_count == 2
        mock_master.recv_match.assert_called_with(type="COMMAND_LONG", blocking=False)

    def test_poll_accel_cal_vehicle_pos_returns_none_without_connection(self) -> None:
        """
        Polling accel calibration position returns None without a connection.

        GIVEN: No flight controller connection
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: The method should return None
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_simple_accelerometer_calibration_reports_backend_failure(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        A rejected simple calibration surfaces the acknowledgement failure.

        GIVEN: A connected flight controller that rejects the calibration command
        WHEN: User starts simple accelerometer calibration
        THEN: The method reports failure with the backend error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        mock_ack.result = mavutil.mavlink.MAV_RESULT_FAILED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_simple()

        assert success is False
        assert error == "Command failed"

    def test_user_can_run_level_accelerometer_calibration(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can level-trim the accelerometers on a connected vehicle.

        GIVEN: A connected flight controller ready for level trim
        WHEN: User starts level calibration
        THEN: Preflight calibration is sent with param5=2 and acknowledged
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_level()

        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        args = mock_master.mav.command_long_send.call_args.args
        assert args[2] == mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        assert args[8] == 2.0

    def test_level_accelerometer_calibration_fails_without_connection(self) -> None:
        """
        Level calibration fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: User starts level calibration
        THEN: The method returns a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_level()

        assert success is False
        assert "connection" in error.lower()

    def test_level_accelerometer_calibration_reports_backend_failure(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        A rejected level calibration surfaces the acknowledgement failure.

        GIVEN: A connected flight controller that rejects the level command
        WHEN: User starts level calibration
        THEN: The method reports failure with the backend error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        mock_ack.result = mavutil.mavlink.MAV_RESULT_FAILED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_level()

        assert success is False
        assert error == "Command failed"

    def test_full_accelerometer_calibration_reports_send_error(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        A transport error while starting full calibration is surfaced cleanly.

        GIVEN: A connected flight controller whose link raises on send
        WHEN: User starts the full 6-position calibration
        THEN: The method returns failure with the transport error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.mav.command_long_send.side_effect = ConnectionError("link down")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_accel_calibration_full_start()

        assert success is False
        assert error == "Failed to send full accelerometer calibration command: link down"

    def test_poll_accel_cal_vehicle_pos_ignores_unrelated_messages(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling ignores COMMAND_LONG messages that are not position requests.

        GIVEN: A COMMAND_LONG that is not a MAV_CMD_ACCELCAL_VEHICLE_POS request
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: No position is returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_msg = MagicMock()
        mock_msg.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        # Return the unrelated message once, then None to terminate the drain loop
        mock_master.recv_match.side_effect = [mock_msg, None]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_returns_none_when_no_message_waiting(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling returns None when the flight controller has sent nothing.

        GIVEN: A non-blocking poll that finds no message
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: None is returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_swallows_transport_exceptions(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        A transient link error during polling never propagates to the UI loop.

        GIVEN: A poll whose recv_match raises a transport error
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: None is returned instead of raising
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.side_effect = ConnectionError("socket reset")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_drains_duplicate_messages(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Polling drains all duplicate position messages and returns only the latest.

        GIVEN: ArduPilot sends the same position request multiple times (every second while waiting)
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: All stale duplicates are consumed and only the latest position is returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        # Simulate FC sending LEVEL position 3 times, then nothing
        msg1 = MagicMock()
        msg1.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        msg1.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        msg2 = MagicMock()
        msg2.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        msg2.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        msg3 = MagicMock()
        msg3.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        msg3.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        mock_master.recv_match.side_effect = [msg1, msg2, msg3, None]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        result = commands_mgr.poll_accel_cal_vehicle_pos()

        # Should drain all 3 duplicates and return the position once
        assert result == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        # Next poll should return None (queue is drained)
        mock_master.recv_match.side_effect = [None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_suppresses_stale_position_after_confirmation(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling returns None when the FC re-sends the already-confirmed position.

        GIVEN: A position was already returned to the caller (user confirmed it)
        WHEN: poll_accel_cal_vehicle_pos is called and the FC sends the same position again
        THEN: None is returned so the UI does not re-enable Continue for the same orientation

        This is the core fix for #1801: after the user confirms LEVEL, ArduPilot keeps
        sending LEVEL every second.  Without deduplication the UI would immediately
        re-show the LEVEL instruction; with it, polling returns None until the FC
        advances to the next position.
        """
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        level_msg = MagicMock()
        level_msg.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        level_msg.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL

        # First poll: FC sends LEVEL → caller receives LEVEL and confirms it
        mock_master.recv_match.side_effect = [level_msg, None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL

        # Second poll: FC re-sends stale LEVEL while waiting → should be suppressed
        mock_master.recv_match.side_effect = [level_msg, None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

        # Third poll: FC advances to the next position → new value must be returned
        left_msg = MagicMock()
        left_msg.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        left_msg.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT
        mock_master.recv_match.side_effect = [left_msg, None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT

    def test_user_can_confirm_accelerometer_calibration_position(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User confirmation of a position is sent back to the flight controller.

        GIVEN: A connected flight controller mid full calibration
        WHEN: confirm_accel_vehicle_pos is called with a position
        THEN: MAV_CMD_ACCELCAL_VEHICLE_POS is sent with that position in param1
        """
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.confirm_accel_vehicle_pos(mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN)

        assert success is True
        assert error == ""
        args = mock_master.mav.command_long_send.call_args.args
        assert args[2] == mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        assert args[4] == float(mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN)

    def test_confirm_accelerometer_position_fails_without_connection(self) -> None:
        """
        Position confirmation fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: confirm_accel_vehicle_pos is called
        THEN: The method returns a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.confirm_accel_vehicle_pos(mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL)

        assert success is False
        assert "connection" in error.lower()

    def test_confirm_accelerometer_position_reports_send_error(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        A transport error while confirming a position is surfaced cleanly.

        GIVEN: A connected flight controller whose link raises on send
        WHEN: confirm_accel_vehicle_pos is called
        THEN: The method returns failure with the transport error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.mav.command_long_send.side_effect = ConnectionError("write failed")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.confirm_accel_vehicle_pos(mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT)

        assert success is False
        assert error == "Failed to send position confirmation: write failed"


class TestFlightControllerCommandsResultCodes:
    """Test command result code handling."""

    def test_send_command_temporarily_rejected(self) -> None:
        """
        send_command_and_wait_ack handles TEMPORARILY_REJECTED result.

        GIVEN: Flight controller that rejects command temporarily
        WHEN: User sends command
        THEN: Should return failure
        AND: Error message should indicate temporary rejection
        """
        # Given
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED

        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        # Then
        assert success is False
        assert "temporarily rejected" in error.lower()

    def test_send_command_unsupported(self) -> None:
        """
        send_command_and_wait_ack handles UNSUPPORTED result.

        GIVEN: Flight controller that doesn't support command
        WHEN: User sends unsupported command
        THEN: Should return failure
        AND: Error message should indicate command unsupported
        """
        # Given
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = mavutil.mavlink.MAV_RESULT_UNSUPPORTED

        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        # Then
        assert success is False
        assert "unsupported" in error.lower()

    def test_send_command_failed(self) -> None:
        """
        send_command_and_wait_ack handles FAILED result.

        GIVEN: Flight controller that reports command failure
        WHEN: User sends command
        THEN: Should return failure
        AND: Error message should indicate command failed
        """
        # Given
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = mavutil.mavlink.MAV_RESULT_FAILED

        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        # Then
        assert success is False
        assert "failed" in error.lower()


class TestFlightControllerCommandsBatteryEdgeCases:
    """Test battery status edge cases and error handling."""

    def test_get_battery_status_returns_none_when_battery_monitoring_disabled(self) -> None:
        """
        get_battery_status returns None when battery monitoring is disabled.

        GIVEN: Flight controller with BATT_MONITOR=0
        WHEN: User requests battery status
        THEN: Should return None
        AND: Error message should indicate monitoring disabled
        """
        # Given: Battery monitoring disabled
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 0}

        mock_master = MagicMock()

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_status, error = commands_mgr.get_battery_status()

        # Then: Should return None
        assert battery_status is None
        assert "battery monitoring is not enabled" in error.lower()

    def test_get_battery_status_returns_none_when_no_connection(self) -> None:
        """
        get_battery_status returns None when no connection available.

        GIVEN: Flight controller with no connection
        WHEN: User requests battery status
        THEN: Should return None
        AND: Error message should indicate no connection
        """
        # Given: No connection
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = None

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_status, error = commands_mgr.get_battery_status()

        # Then: Should return None
        assert battery_status is None
        assert "no flight controller connection" in error.lower()

    def test_get_battery_status_handles_exception_in_telemetry(self) -> None:
        """
        get_battery_status handles exceptions during telemetry fetch.

        GIVEN: Flight controller with exception in recv_match
        WHEN: User requests battery status
        THEN: Should handle exception gracefully
        AND: Should return None with error message
        """
        # Given: Exception in telemetry
        mock_master = MagicMock()
        mock_master.recv_match.side_effect = Exception("Connection lost")

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_status, error = commands_mgr.get_battery_status()

        # Then: Should return None
        assert battery_status is None
        assert error is not None

    def test_get_battery_status_uses_cache_when_recent(self) -> None:
        """
        get_battery_status uses cached data when recent.

        GIVEN: Flight controller with recent battery status cached
        WHEN: User requests battery status but telemetry fails
        THEN: Should return cached data
        AND: Error message should be empty
        """
        # Given: Setup with working telemetry first
        mock_master = MagicMock()
        mock_battery_msg = MagicMock()
        mock_battery_msg.voltages = [12000]  # 12V in millivolts
        mock_battery_msg.current_battery = 1050  # 10.5A in centiamps
        mock_master.recv_match.return_value = mock_battery_msg

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: First call gets data successfully
        battery_status1, error1 = commands_mgr.get_battery_status()

        # Then: First call succeeds
        assert battery_status1 is not None
        assert error1 == ""

        # When: Second call (telemetry fails but cache is still fresh)
        mock_master.recv_match.side_effect = Exception("Connection lost")
        battery_status2, error2 = commands_mgr.get_battery_status()

        # Then: Should use cached data
        assert battery_status2 == battery_status1
        assert error2 == ""

    def test_send_command_exception_in_send(self) -> None:
        """
        send_command_and_wait_ack handles exception during command send.

        GIVEN: Flight controller connection that raises exception on send
        WHEN: User sends command
        THEN: Should handle exception
        AND: Should return failure with error message
        """
        # Given: Exception on command send
        mock_master = MagicMock()
        mock_master.mav.command_long_send.side_effect = Exception("Serial port error")

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        # Then
        assert success is False
        assert "failed to send command" in error.lower()


class TestFlightControllerCommandsAccelCalibrationCancel:
    """Test cancelling an in-progress accelerometer calibration (hardware-free)."""

    def test_user_can_cancel_accel_calibration_when_connected(self, mock_connected_master) -> None:
        """
        User can cancel an ongoing accelerometer calibration.

        GIVEN: A connected flight controller
        WHEN: User cancels the accelerometer calibration
        THEN: A PREFLIGHT_CALIBRATION command with all-zero params is sent
        AND: The call reports success
        """
        # Given: Connected FC
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Cancel calibration
        success, error = commands_mgr.cancel_accel_calibration()

        # Then: Success and the abort command was sent once
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        sent_args = mock_master.mav.command_long_send.call_args.args
        # target_system, target_component, command, then 8 params
        assert sent_args[2] == mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        # every calibration param must be 0 (abort signal)
        assert all(param == 0 for param in sent_args[3:])

    def test_cancel_accel_calibration_resets_vehicle_position(self, mock_connected_master) -> None:
        """
        Cancelling calibration clears any cached vehicle-position state.

        GIVEN: A connected FC with a stale cached vehicle position
        WHEN: User cancels the calibration
        THEN: The cached position is reset to None
        """
        # Given: Connected FC with stale cached position
        _mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        commands_mgr._last_accel_cal_vehicle_pos = 3  # pylint: disable=protected-access

        # When: Cancel calibration
        success, _error = commands_mgr.cancel_accel_calibration()

        # Then: Cached position cleared
        assert success is True
        assert commands_mgr._last_accel_cal_vehicle_pos is None  # pylint: disable=protected-access

    def test_cancel_accel_calibration_fails_without_connection(self) -> None:
        """
        Cancelling calibration fails gracefully when no FC is connected.

        GIVEN: No flight controller connection
        WHEN: User attempts to cancel the calibration
        THEN: The call reports failure with a descriptive message
        AND: No command is attempted
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Cancel calibration
        success, error = commands_mgr.cancel_accel_calibration()

        # Then: Graceful failure
        assert success is False
        assert error != ""

    def test_cancel_accel_calibration_handles_send_exception(self, mock_connected_master) -> None:
        """
        Cancelling calibration reports failure if the MAVLink send raises.

        GIVEN: A connected FC whose command send raises an exception
        WHEN: User attempts to cancel the calibration
        THEN: The call reports failure with the error captured in the message
        """
        # Given: Connected FC that raises on send
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.mav.command_long_send.side_effect = RuntimeError("link down")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Cancel calibration
        success, error = commands_mgr.cancel_accel_calibration()

        # Then: Failure surfaced without raising
        assert success is False
        assert "link down" in error


class TestFlightControllerCommandsPollScaledImu:
    """Test polling SCALED_IMU accelerometer readings (hardware-free)."""

    def test_poll_scaled_imu_returns_accelerations(self, mock_connected_master) -> None:
        """
        Polling SCALED_IMU returns the three axis accelerations.

        GIVEN: A connected FC that has a SCALED_IMU message available
        WHEN: User polls SCALED_IMU
        THEN: The (xacc, yacc, zacc) triple is returned as floats
        """
        # Given: Connected FC with a SCALED_IMU message
        mock_master, mock_conn_mgr = mock_connected_master
        mock_msg = MagicMock()
        mock_msg.xacc, mock_msg.yacc, mock_msg.zacc = 10, -20, 1000
        mock_master.recv_match.return_value = mock_msg
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Poll SCALED_IMU
        result = commands_mgr.poll_scaled_imu()

        # Then: Triple of floats returned
        assert result == (10.0, -20.0, 1000.0)
        assert all(isinstance(v, float) for v in result)

    def test_poll_scaled_imu_returns_none_when_no_message(self, mock_connected_master) -> None:
        """
        Polling SCALED_IMU returns None when no message has arrived.

        GIVEN: A connected FC with no pending SCALED_IMU message
        WHEN: User polls SCALED_IMU
        THEN: None is returned
        """
        # Given: Connected FC, no message
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When/Then
        assert commands_mgr.poll_scaled_imu() is None

    def test_poll_scaled_imu_returns_none_without_connection(self) -> None:
        """
        Polling SCALED_IMU returns None when no FC is connected.

        GIVEN: No flight controller connection
        WHEN: User polls SCALED_IMU
        THEN: None is returned
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When/Then
        assert commands_mgr.poll_scaled_imu() is None

    def test_poll_scaled_imu_returns_none_on_exception(self, mock_connected_master) -> None:
        """
        Polling SCALED_IMU returns None if reading raises.

        GIVEN: A connected FC whose recv_match raises
        WHEN: User polls SCALED_IMU
        THEN: None is returned instead of propagating the exception
        """
        # Given: Connected FC that raises on recv_match
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.side_effect = RuntimeError("decode error")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When/Then: Swallowed, None returned
        assert commands_mgr.poll_scaled_imu() is None


class TestFlightControllerCommandsRequestScaledImu:
    """Test requesting a periodic SCALED_IMU stream (hardware-free)."""

    def test_request_scaled_imu_stream_succeeds_on_ack(self, mock_connected_master) -> None:
        """
        Requesting the SCALED_IMU stream succeeds when the FC acknowledges.

        GIVEN: A connected FC that ACKs SET_MESSAGE_INTERVAL
        WHEN: User requests the SCALED_IMU stream
        THEN: The call reports success
        AND: A SET_MESSAGE_INTERVAL command is sent
        """
        # Given: Connected FC that accepts the command
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream
        success, error = commands_mgr.request_scaled_imu_messages()

        # Then: Success and command sent
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()

    def test_request_scaled_imu_stream_passes_requested_interval(self, mock_connected_master) -> None:
        """
        The requested interval is forwarded to the FC as a command parameter.

        GIVEN: A connected FC that ACKs the command
        WHEN: User requests the stream with a custom interval
        THEN: That interval (µs) appears in the command parameters
        """
        # Given: Connected FC that accepts the command
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream at 10 Hz (100 000 µs)
        success, _error = commands_mgr.request_scaled_imu_messages(interval_microseconds=100_000)

        # Then: Interval forwarded in the sent command params
        assert success is True
        sent_args = mock_master.mav.command_long_send.call_args.args
        assert float(100_000) in [float(a) for a in sent_args[3:]]

    def test_request_scaled_imu_stream_fails_without_connection(self) -> None:
        """
        Requesting the SCALED_IMU stream fails gracefully with no connection.

        GIVEN: No flight controller connection
        WHEN: User requests the SCALED_IMU stream
        THEN: The call reports failure with a descriptive message
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream
        success, error = commands_mgr.request_scaled_imu_messages()

        # Then: Graceful failure
        assert success is False
        assert error != ""
