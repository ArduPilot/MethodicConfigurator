#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_commands.py.

This file focuses on command execution behavior including motor tests,
battery status requests, and parameter reset commands.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, Mock

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands


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

    def test_user_can_test_individual_motor(self) -> None:
        """
        User can test individual motor at specified throttle.

        GIVEN: Connected flight controller ready for motor test
        WHEN: User tests motor 1 at 10% throttle
        THEN: MAVLink command should be sent correctly
        AND: Command acknowledgment should be received
        """
        # Given: Connected FC with ACK response
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
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

    def test_user_can_request_battery_status(self) -> None:
        """
        User can request periodic battery status updates.

        GIVEN: Connected flight controller with battery monitoring
        WHEN: User requests battery status at 1Hz
        THEN: Data stream request should be sent
        AND: Command should be acknowledged
        """
        # Given: Connected FC
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Request battery status
        success, error = commands_mgr.request_periodic_battery_status(
            interval_microseconds=1000000  # 1Hz
        )

        # Then: Request sent
        assert success is True
        assert error == ""

    def test_user_can_get_battery_status(self) -> None:
        """
        User can get current battery status from flight controller.

        GIVEN: Flight controller with battery monitoring enabled
        WHEN: User requests current battery status
        THEN: Voltage and current should be returned
        AND: Values should be in expected ranges
        """
        # Given: FC with battery data
        mock_master = MagicMock()
        mock_battery_msg = MagicMock()
        mock_battery_msg.voltages = [4200, 4180, 4190]  # mV
        mock_battery_msg.current_battery = 2500  # centi-amps
        mock_master.recv_match.return_value = mock_battery_msg

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4.0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_data, message = commands_mgr.get_battery_status()

        # Then: Status retrieved
        assert battery_data is not None
        assert message == ""
        if battery_data:
            voltage, current = battery_data
            assert voltage > 0
            assert current >= 0


class TestFlightControllerCommandsParameterReset:  # pylint: disable=too-few-public-methods
    """Test parameter reset command functionality."""

    def test_user_can_reset_all_parameters_to_defaults(self) -> None:
        """
        User can reset all parameters to factory defaults.

        GIVEN: Flight controller with modified parameters
        WHEN: User resets all parameters to defaults
        THEN: Reset command should be sent
        AND: Command should be acknowledged
        """
        # Given: Connected FC
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Reset parameters
        success, error = commands_mgr.reset_all_parameters_to_default()

        # Then: Command sent
        assert success is True
        assert error == ""


class TestFlightControllerCommandsSendCommandAndWaitAck:
    """Test low-level command sending with ACK waiting."""

    def test_command_waits_for_acknowledgment(self) -> None:
        """
        Command sending waits for proper acknowledgment.

        GIVEN: Flight controller command infrastructure
        WHEN: User sends command with ACK expected
        THEN: Function should wait for ACK message
        AND: Return success when ACK received
        """
        # Given: FC that sends ACK
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = 123
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Send command
        success, error = commands_mgr.send_command_and_wait_ack(
            command=123, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0, timeout=1.0
        )

        # Then: ACK received
        assert success is True
        assert error == ""

    def test_command_timeout_returns_error(self) -> None:
        """
        Command timeout returns appropriate error.

        GIVEN: Flight controller not responding
        WHEN: User sends command with timeout
        THEN: Timeout error should be returned
        AND: Error message should indicate timeout
        """
        # Given: FC that doesn't respond
        mock_master = MagicMock()
        mock_master.recv_match.return_value = None

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
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

    def test_master_property_delegates_to_connection_manager(self) -> None:
        """
        Master property correctly delegates to connection manager.

        GIVEN: Commands manager with connection manager
        WHEN: Accessing master property
        THEN: Connection manager's master should be returned
        """
        # Given: Connection with master
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Access master
        retrieved_master = commands_mgr.master

        # Then: Correct master returned
        assert retrieved_master is mock_master
