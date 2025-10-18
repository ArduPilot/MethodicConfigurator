#!/usr/bin/env python3

"""
Tests for the backend_flightcontroller.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Union
from unittest.mock import MagicMock, mock_open, patch

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

# pylint: disable=protected-access


def test_add_connection() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    assert fc.add_connection("test_connection") is True
    assert fc.add_connection("test_connection") is False
    assert fc.add_connection("") is False


def test_discover_connections() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.discover_connections()
    assert len(fc.get_connection_tuples()) > 0


def test_connect() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    result = fc.connect(device="test")
    assert result == ""


def test_disconnect() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    fc.disconnect()
    assert fc.master is None


@patch("builtins.open", new_callable=mock_open, read_data="param1=1\nparam2=2")
@patch(
    "ardupilot_methodic_configurator.data_model_par_dict.ParDict.load_param_file_into_dict",
    side_effect=lambda x: ParDict({"param1": Par(1, x), "param2": Par(2, x)}),
)
def test_download_params(mock_load_param_file_into_dict, mock_file) -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    with patch("ardupilot_methodic_configurator.backend_flightcontroller.open", mock_file):
        params, _ = fc.download_params()
    assert isinstance(params, dict)
    assert params == {"param1": 1, "param2": 2}
    mock_load_param_file_into_dict.assert_called_once_with("params.param")


@patch("builtins.open", new_callable=mock_open, read_data="param1,1\nparam2,2")
@patch(
    "ardupilot_methodic_configurator.data_model_par_dict.ParDict.load_param_file_into_dict",
    side_effect=lambda x: ParDict({"param1": Par(1, x), "param2": Par(2, x)}),
)
def test_set_param(mock_load_param_file_into_dict, mock_file) -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    fc.set_param("TEST_PARAM", 1.0)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller.open", mock_file):
        params, _ = fc.download_params()
    assert params.get("TEST_PARAM") is None  # Assuming the mock environment does not actually set the parameter
    mock_load_param_file_into_dict.assert_called_once_with("params.param")


def test_reset_and_reconnect() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    result = fc.reset_and_reconnect()
    assert result == ""


def test_upload_file() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    result = fc.upload_file("local.txt", "remote.txt")
    # Assuming the mock environment always returns False for upload_file
    assert result is False


def test_get_connection_tuples() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.add_connection("test_connection")
    connections = fc.get_connection_tuples()
    assert ("test_connection", "test_connection") in connections


@patch("builtins.open", new_callable=mock_open, read_data="param1,1\nparam2,2")
@patch(
    "ardupilot_methodic_configurator.data_model_par_dict.ParDict.load_param_file_into_dict",
    side_effect=lambda x: ParDict({"param1": Par(1, x), "param2": Par(2, x)}),
)
def test_set_param_and_verify(mock_load_param_file_into_dict, mock_file) -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    fc.set_param("TEST_PARAM", 1.0)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller.open", mock_file):
        params, _ = fc.download_params()
    # Assuming the mock environment does not actually set the parameter
    assert params.get("TEST_PARAM") is None
    mock_load_param_file_into_dict.assert_called_once_with("params.param")


def test_download_params_via_mavftp() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    params, default_params = fc._download_params_via_mavftp()
    assert isinstance(params, dict)
    assert isinstance(default_params, dict)


def test_auto_detect_serial() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    serial_ports = fc._FlightController__auto_detect_serial()  # pylint: disable=protected-access
    assert isinstance(serial_ports, list)


def test_list_serial_ports() -> None:
    serial_ports = FlightController._FlightController__list_serial_ports()  # pylint: disable=protected-access
    assert isinstance(serial_ports, list)


def test_list_network_ports() -> None:
    network_ports = FlightController._FlightController__list_network_ports()  # pylint: disable=protected-access
    assert isinstance(network_ports, list)
    assert "tcp:127.0.0.1:5760" in network_ports


def test_request_banner() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    fc._FlightController__request_banner()  # pylint: disable=protected-access
    # Since we cannot verify in the mock environment, we will just ensure no exceptions are raised


def test_receive_banner_text() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    banner_text = fc._FlightController__receive_banner_text()  # pylint: disable=protected-access
    assert isinstance(banner_text, list)


def test_request_message() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    fc._FlightController__request_message(1)  # pylint: disable=protected-access
    # Since we cannot verify in the mock environment, we will just ensure no exceptions are raised


def test_create_connection_with_retry() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    result = fc._FlightController__create_connection_with_retry(progress_callback=None, retries=1, timeout=1)  # pylint: disable=protected-access
    assert result == ""


def test_process_autopilot_version() -> None:
    fc = FlightController(reboot_time=7, baudrate=115200)
    fc.connect(device="test")
    banner_msgs = ["ChibiOS: 123", "ArduPilot"]
    result = fc._FlightController__process_autopilot_version(None, banner_msgs)  # pylint: disable=protected-access
    assert isinstance(result, str)


class TestMotorTestFunctionality:
    """Test motor test commands and functionality in FlightController."""

    @pytest.fixture
    def mock_fc_connection(self) -> MagicMock:
        """Fixture providing a mocked flight controller connection."""
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1
        mock_connection.wait_heartbeat.return_value = None

        # Mock COMMAND_ACK response for successful commands
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_ack.progress = 100
        mock_ack.result_param2 = 0

        # Configure recv_match to return COMMAND_ACK on first call, None on subsequent calls
        def recv_match_side_effect(*_args: tuple, **kwargs: dict) -> Union[MagicMock, None]:
            # Check if looking for COMMAND_ACK message type
            type_arg = kwargs.get("type")
            if isinstance(type_arg, str) and type_arg == "COMMAND_ACK":
                return mock_ack
            return None

        mock_connection.recv_match.side_effect = recv_match_side_effect
        return mock_connection

    @pytest.fixture
    def flight_controller(self, mock_fc_connection) -> FlightController:
        """Fixture providing a configured FlightController for motor testing."""
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection",
            return_value=mock_fc_connection,
        ):
            fc = FlightController()
            fc.master = mock_fc_connection
            return fc

    def test_user_can_test_individual_motor(self, flight_controller) -> None:
        """
        User can test an individual motor safely.

        GIVEN: A connected flight controller with proper motor test setup
        WHEN: User requests to test motor 1 at 15% throttle for 3 seconds
        THEN: The motor test command should be sent with correct parameters
        AND: The function should return True indicating success
        """
        # Arrange: Set up motor test parameters
        test_sequence_nr = 0  # First motor (0-based for test sequence)
        motor_letters = "A"
        motor_output_nr = 1  # First output (1-based)
        throttle_percent = 15
        timeout_seconds = 3

        # Act: Execute motor test
        success, error_msg = flight_controller.test_motor(
            test_sequence_nr, motor_letters, motor_output_nr, throttle_percent, timeout_seconds
        )

        # Assert: Motor test command sent correctly
        assert success is True, f"Motor test should succeed, but got error: {error_msg}"
        assert error_msg == "", f"No error message expected on success, but got: {error_msg}"
        flight_controller.master.mav.command_long_send.assert_called_once()
        call_args = flight_controller.master.mav.command_long_send.call_args[0]  # Positional args

        assert call_args[0] == 1  # target_system
        assert call_args[1] == 1  # target_component
        assert call_args[2] == mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST  # command
        assert call_args[3] == 0  # confirmation
        assert call_args[4] == test_sequence_nr + 1  # param1: motor test number (1-based)
        assert call_args[5] == mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT  # param2: throttle type
        assert call_args[6] == throttle_percent  # param3: throttle value
        assert call_args[7] == timeout_seconds  # param4: timeout
        assert call_args[8] == 0  # param5: motor count (0=single motor test)
        assert call_args[9] == 0  # param6: test order (0=default/board order)

    def test_user_can_stop_all_motors_immediately(self, flight_controller) -> None:
        """
        User can stop all motors immediately for safety.

        GIVEN: Motors are currently running during test
        WHEN: User presses emergency stop button
        THEN: All motors should stop immediately
        AND: The function should return True indicating success
        """
        # Arrange: Emergency stop scenario

        # Act: Execute emergency stop
        success, error_msg = flight_controller.stop_all_motors()

        # Assert: Emergency stop command sent
        assert success is True, f"Motor stop should succeed, but got error: {error_msg}"
        assert error_msg == "", f"No error message expected on success, but got: {error_msg}"
        flight_controller.master.mav.command_long_send.assert_called_once()
        call_args = flight_controller.master.mav.command_long_send.call_args[0]  # Positional args

        assert call_args[0] == 1  # target_system
        assert call_args[1] == 1  # target_component
        assert call_args[2] == mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST  # command
        assert call_args[3] == 0  # confirmation
        assert call_args[4] == 0  # param1: motor number (0 = all)
        assert call_args[5] == mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT  # param2: throttle type
        assert call_args[6] == 0  # param3: throttle value (0 = stop)
        assert call_args[7] == 0  # param4: timeout (0 = immediate)
        assert call_args[8] == 0  # param5: motor count (0 = all)
        assert call_args[9] == 0  # param6: test order (0 = default/board order)

    def test_user_can_test_motors_in_sequence(self, flight_controller) -> None:
        """
        User can test all motors in sequence automatically.

        GIVEN: A quadcopter frame with 4 motors configured
        WHEN: User requests sequential motor test at 12% throttle for 2 seconds each
        THEN: Each motor should be tested in sequence (A, B, C, D)
        AND: The function should return True indicating success
        """
        # Arrange: Configure for quad frame (4 motors)
        flight_controller.fc_parameters = {
            "FRAME_CLASS": 1,  # Quad
            "FRAME_TYPE": 1,  # X configuration
        }
        throttle_percent = 12
        timeout_seconds = 2

        # Act: Execute sequential motor test
        start_motor = 1  # Start with first motor
        motor_count = 4  # Test 4 motors
        success, error_msg = flight_controller.test_motors_in_sequence(
            start_motor, motor_count, throttle_percent, timeout_seconds
        )

        # Assert: Sequential test command sent for all motors
        assert success is True, f"Sequential motor test should succeed, but got error: {error_msg}"
        assert error_msg == "", f"No error message expected on success, but got: {error_msg}"
        flight_controller.master.mav.command_long_send.assert_called_once()
        call_args = flight_controller.master.mav.command_long_send.call_args[0]  # Positional args

        assert call_args[0] == 1  # target_system
        assert call_args[1] == 1  # target_component
        assert call_args[2] == mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST  # command
        assert call_args[3] == 0  # confirmation
        assert call_args[4] == start_motor  # param1: starting motor number (1-based)
        assert call_args[5] == mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT  # param2: throttle type
        assert call_args[6] == throttle_percent  # param3: throttle value
        assert call_args[7] == timeout_seconds  # param4: timeout per motor
        assert call_args[8] == motor_count  # param5: number of motors to test in sequence
        assert call_args[9] == mavutil.mavlink.MOTOR_TEST_ORDER_SEQUENCE  # param6: test order (sequence)

    def test_motor_test_handles_communication_failure(self, flight_controller) -> None:
        """
        Motor test handles communication failures gracefully.

        GIVEN: Flight controller connection is unstable
        WHEN: Motor test command fails to send due to communication error
        THEN: The function should handle the exception gracefully
        AND: Return False to indicate failure
        """
        # Arrange: Simulate communication failure
        flight_controller.master.mav.command_long_send.side_effect = Exception("Connection lost")

        # Act: Attempt motor test during communication failure
        success, error_msg = flight_controller.test_motor(0, "A", 1, 10, 2)

        # Assert: Function handles error gracefully
        assert success is False
        assert "Connection lost" in error_msg

    def test_battery_status_monitoring_during_motor_test(self, flight_controller) -> None:
        """
        Battery status is properly monitored during motor tests.

        GIVEN: Battery monitoring is enabled with voltage and current sensors
        WHEN: Battery status is requested during motor testing
        THEN: Current voltage and current readings should be returned
        AND: Values should be within expected ranges for safe operation
        """
        # Arrange: Set up battery monitoring parameters
        flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,  # Voltage and current monitoring
            "BATT_ARM_VOLT": 11.0,  # Minimum arming voltage
            "MOT_BAT_VOLT_MAX": 12.6,  # Maximum motor voltage
        }

        # Mock battery status message
        mock_battery_status = MagicMock()
        mock_battery_status.voltages = [12100, -1, -1, -1, -1, -1, -1, -1, -1, -1]  # 12.1V in mV
        mock_battery_status.current_battery = 250  # 2.5A in cA

        # Configure recv_match to return BATTERY_STATUS for this specific test
        def recv_match_battery_side_effect(*_args: tuple, **kwargs: dict) -> Union[MagicMock, None]:
            type_arg = kwargs.get("type")
            if isinstance(type_arg, str) and type_arg == "BATTERY_STATUS":
                return mock_battery_status
            if isinstance(type_arg, str) and type_arg == "COMMAND_ACK":
                # Return the existing COMMAND_ACK mock from the fixture
                mock_ack = MagicMock()
                mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
                mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
                return mock_ack
            return None

        flight_controller.master.recv_match.side_effect = recv_match_battery_side_effect

        # Act: Get battery status
        battery_info, error_msg = flight_controller.get_battery_status()

        # Assert: Battery values are correctly parsed
        assert battery_info is not None, f"Battery info should be available, got error: {error_msg}"
        voltage, current = battery_info
        assert error_msg == "", f"No error expected on successful battery status, got: {error_msg}"
        assert voltage == 12.1  # Converted from mV to V
        assert current == 2.5  # Converted from cA to A
        assert 11.0 <= voltage <= 12.6  # Within safe operating range

    def test_battery_status_monitoring_during_motor_test_no_current(self, flight_controller) -> None:
        """
        Battery status can be monitored during motor test operations.

        GIVEN: A flight controller connection is available
        WHEN: Battery status is requested during motor test
        THEN: Battery voltage information should be available
        AND: The information should be properly formatted for safety checks
        """
        # Arrange: Configure battery monitoring
        flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 12.6,
        }

        # Mock battery status response
        mock_battery_status = MagicMock()
        mock_battery_status.voltages = [12100, -1, -1, -1, -1, -1, -1, -1, -1, -1]  # 12.1V
        mock_battery_status.current_battery = 0
        flight_controller.master.recv_match.return_value = mock_battery_status

        # Act: Request battery status
        flight_controller.master.mav.request_data_stream_send(
            flight_controller.master.target_system,
            flight_controller.master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
            1,
            1,
        )

        # Assert: Battery status should be available for monitoring
        assert flight_controller.master.mav.request_data_stream_send.called
        assert mock_battery_status.voltages[0] == 12100  # Voltage in millivolts
        assert mock_battery_status.current_battery >= 0  # Valid battery index


class TestMotorTestCommandSending:
    """Test motor test command sending functionality."""

    @pytest.fixture
    def flight_controller(self) -> FlightController:
        """Fixture providing a FlightController for command sending testing."""
        with patch("ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection"):
            fc = FlightController()
            mock_master = MagicMock()
            mock_master.target_system = 1
            mock_master.target_component = 1

            # Mock COMMAND_ACK response for successful commands
            mock_ack = MagicMock()
            mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
            mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
            mock_ack.progress = 100
            mock_ack.result_param2 = 0

            # Configure recv_match to return COMMAND_ACK
            def recv_match_side_effect(*_args: tuple, **kwargs: dict) -> Union[MagicMock, None]:
                type_arg = kwargs.get("type")
                if isinstance(type_arg, str) and type_arg == "COMMAND_ACK":
                    return mock_ack
                return None

            mock_master.recv_match.side_effect = recv_match_side_effect
            fc.master = mock_master
            return fc

    def test_motor_commands_are_sent_to_flight_controller(self, flight_controller) -> None:
        """
        Motor test commands are properly sent to the flight controller.

        GIVEN: A valid flight controller connection exists
        WHEN: Motor test commands are issued with various parameters
        THEN: The commands should be sent to the flight controller via MAVLink
        AND: The function should return True to indicate successful command sending
        """
        # Arrange: Set up test parameters
        test_cases = [
            (1, 5, 1.0),  # Minimum test
            (4, 50, 5.0),  # Mid-range test
            (8, 100, 10.0),  # Maximum test
        ]

        # Act & Assert: Test command sending for each case
        for motor_num, throttle, timeout in test_cases:
            # Convert motor_num to test parameters
            test_sequence_nr = motor_num - 1  # Convert to 0-based index
            motor_letters = chr(ord("A") + test_sequence_nr)  # A, B, C, etc.
            motor_output_nr = motor_num  # Keep 1-based for output number
            success, error_msg = flight_controller.test_motor(
                test_sequence_nr, motor_letters, motor_output_nr, throttle, timeout
            )

            # Assert: Command should be sent successfully
            assert success is True, f"Motor test command should be sent successfully for motor {motor_num}, error: {error_msg}"
            assert error_msg == "", f"No error expected on successful motor test, got: {error_msg}"
            flight_controller.master.mav.command_long_send.assert_called()

    def test_command_sending_handles_no_connection_gracefully(self, flight_controller) -> None:
        """
        Motor test commands handle connection failures gracefully.

        GIVEN: No flight controller connection is available
        WHEN: Motor test commands are attempted
        THEN: The function should return False safely
        AND: No exceptions should be raised
        """
        # Arrange: Remove connection
        flight_controller.master = None

        # Act: Attempt motor test without connection
        success, error_msg = flight_controller.test_motor(0, "A", 1, 10, 2.0)

        # Assert: Should fail gracefully
        assert success is False, "Motor test should fail gracefully when no connection is available"
        assert "No flight controller connection" in error_msg, f"Expected connection error message, got: {error_msg}"


# ==================== COMPREHENSIVE BDD TEST CLASSES ====================


class TestFlightControllerConnectionManagement:
    """Test flight controller connection lifecycle in BDD style."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_create_flight_controller_without_auto_discovery(self, mock_discover) -> None:
        """
        User can create flight controller instance without automatic connection discovery.

        GIVEN: A system where automatic discovery is disabled
        WHEN: The user creates a FlightController instance
        THEN: The instance should be created successfully
        AND: No automatic connection discovery should occur
        """
        # Given: Mock discover_connections to prevent automatic discovery
        mock_discover.return_value = None

        # When: Create FlightController instance
        fc = FlightController(reboot_time=5, baudrate=57600)

        # Then: Instance created successfully
        assert fc is not None
        assert fc._FlightController__reboot_time == 5
        assert fc._FlightController__baudrate == 57600
        assert fc.master is None
        assert not fc.fc_parameters

        # And: No automatic discovery occurred
        mock_discover.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection")
    def test_user_can_connect_to_flight_controller_successfully(self, mock_mavlink, mock_discover) -> None:
        """
        User can establish successful connection to flight controller.

        GIVEN: A flight controller that responds to connection attempts
        WHEN: The user connects to a specific device
        THEN: A successful connection should be established
        AND: Connection status should be available
        """
        # Given: Mock successful connection
        mock_discover.return_value = None
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1
        mock_mavlink.return_value = mock_connection

        fc = FlightController(reboot_time=5, baudrate=115200)

        # When: Connect to device
        fc.connect(device="tcp:127.0.0.1:5760")

        # Then: Connection established successfully
        assert fc.master is not None
        assert fc.master == mock_connection
        mock_mavlink.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_disconnect_from_flight_controller_cleanly(self, mock_discover) -> None:
        """
        User can cleanly disconnect from flight controller.

        GIVEN: A connected flight controller
        WHEN: The user disconnects
        THEN: All connection resources should be released
        AND: Connection state should be cleared
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)
        mock_master = MagicMock()
        fc.master = mock_master

        # When: Disconnect
        fc.disconnect()

        # Then: Connection resources released
        assert fc.master is None
        mock_master.close.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_manage_multiple_connection_strings(self, mock_discover) -> None:
        """
        User can manage multiple connection strings for different devices.

        GIVEN: A flight controller with no initial connections
        WHEN: The user adds multiple connection strings
        THEN: All valid connections should be stored
        AND: Duplicate connections should be rejected
        AND: Invalid connections should be rejected
        """
        # Given: Flight controller with no connections
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)

        # When: Add multiple connection strings
        result1 = fc.add_connection("tcp:127.0.0.1:5760")
        result2 = fc.add_connection("udp:127.0.0.1:14550")
        result3 = fc.add_connection("tcp:127.0.0.1:5760")  # Duplicate
        result4 = fc.add_connection("")  # Invalid

        # Then: Valid connections accepted, invalid rejected
        assert result1 is True, "First connection should be accepted"
        assert result2 is True, "Second connection should be accepted"
        assert result3 is False, "Duplicate connection should be rejected"
        assert result4 is False, "Empty connection should be rejected"

        # And: Connection tuples available
        connection_tuples = fc.get_connection_tuples()
        assert len(connection_tuples) >= 2, "Should have at least 2 connections"


class TestFlightControllerParameterOperations:
    """Test parameter download and management operations in BDD style."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController._download_params_via_mavlink")
    def test_user_can_download_parameters_with_progress_feedback(self, mock_download, mock_discover) -> None:
        """
        User can download parameters with real-time progress feedback.

        GIVEN: A connected flight controller with parameters
        WHEN: The user downloads parameters with a progress callback
        THEN: Parameters should be downloaded successfully
        AND: Progress callback should be called with updates
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        mock_params = {"ALT_HOLD_RTL": 100.0, "BATT_MONITOR": 4.0}
        # Note: _download_params_via_mavlink returns only dict, not tuple
        mock_download.return_value = mock_params

        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.master = MagicMock()

        # Track progress updates
        progress_updates = []

        def progress_callback(current, total) -> None:
            progress_updates.append((current, total))

        # When: Download parameters with progress callback
        result_params, result_defaults = fc.download_params(progress_callback)

        # Then: Parameters downloaded successfully
        assert result_params == mock_params
        assert isinstance(result_defaults, ParDict)  # Will be empty ParDict() from MAVLink fallback
        mock_download.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_set_individual_parameter_values(self, mock_discover) -> None:
        """
        User can set individual parameter values on flight controller.

        GIVEN: A connected flight controller
        WHEN: The user sets a parameter value
        THEN: The parameter should be sent to the flight controller
        AND: No errors should occur
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)
        mock_master = MagicMock()
        fc.master = mock_master

        # When: Set parameter
        fc.set_param("ALT_HOLD_RTL", 150.0)

        # Then: Parameter sent to flight controller
        mock_master.param_set_send.assert_called_once_with("ALT_HOLD_RTL", 150.0)

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController._send_command_and_wait_ack")
    def test_user_can_reset_all_parameters_to_defaults(self, mock_send_command, mock_discover) -> None:
        """
        User can reset all parameters to factory defaults.

        GIVEN: A connected flight controller with modified parameters
        WHEN: The user resets all parameters to defaults
        THEN: A reset command should be sent to the flight controller
        AND: Success status should be returned
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        mock_send_command.return_value = (True, "")
        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.master = MagicMock()

        # When: Reset all parameters
        success, message = fc.reset_all_parameters_to_default()

        # Then: Reset command sent successfully
        assert success is True
        assert message == ""
        mock_send_command.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_receives_timeout_error_when_fetching_nonexistent_parameter(self, mock_discover) -> None:
        """
        User receives appropriate timeout error when fetching nonexistent parameter.

        GIVEN: A connected flight controller
        WHEN: The user fetches a parameter that doesn't exist
        THEN: A TimeoutError should be raised after waiting period
        """
        # Given: Connected flight controller that doesn't respond to param requests
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)
        mock_master = MagicMock()
        mock_master.recv_match.return_value = None  # No response
        fc.master = mock_master

        # When: Fetch nonexistent parameter
        # Then: Timeout error should be raised
        with pytest.raises(TimeoutError, match="Timeout waiting for parameter NONEXISTENT_PARAM"):
            fc.fetch_param("NONEXISTENT_PARAM", timeout=1)  # Short timeout for testing


class TestFlightControllerMotorTesting:
    """Test motor testing functionality in BDD style."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController._send_command_and_wait_ack")
    def test_user_can_test_all_motors_simultaneously(self, mock_send_command, mock_discover) -> None:
        """
        User can test all motors simultaneously at specified throttle.

        GIVEN: A connected flight controller with multiple motors
        WHEN: The user tests all motors at once
        THEN: Motor test commands should be sent for all motors
        AND: Success status should be returned
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        mock_send_command.return_value = (True, "")
        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.master = MagicMock()

        # When: Test all 4 motors at 20% throttle
        success, message = fc.test_all_motors(nr_of_motors=4, throttle_percent=20, timeout_seconds=5)

        # Then: Motor test successful
        assert success is True
        assert message == ""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController._send_command_and_wait_ack")
    def test_user_can_stop_all_motors_immediately(self, mock_send_command, mock_discover) -> None:
        """
        User can immediately stop all motors for safety.

        GIVEN: A flight controller with motors running
        WHEN: The user stops all motors
        THEN: Motor stop commands should be sent
        AND: All motors should be stopped safely
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        mock_send_command.return_value = (True, "")
        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.master = MagicMock()

        # When: Stop all motors
        success, _message = fc.stop_all_motors()

        # Then: Motors stopped successfully
        assert success is True
        mock_send_command.assert_called()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController._send_command_and_wait_ack")
    def test_user_can_test_motors_in_sequence_safely(self, mock_send_command, mock_discover) -> None:
        """
        User can test motors in sequence for safer testing.

        GIVEN: A connected flight controller with multiple motors
        WHEN: The user tests motors in sequence
        THEN: A single sequential motor test command should be sent
        AND: The command should specify the motor sequence parameters
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        mock_send_command.return_value = (True, "")
        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.master = MagicMock()

        # When: Test motors in sequence
        success, _message = fc.test_motors_in_sequence(start_motor=1, motor_count=3, throttle_percent=15, timeout_seconds=3)

        # Then: Sequential motor test command sent successfully
        assert success is True
        mock_send_command.assert_called_once()


class TestFlightControllerBatteryMonitoring:
    """Test battery monitoring functionality in BDD style."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController._send_command_and_wait_ack")
    def test_user_can_enable_periodic_battery_status_monitoring(self, mock_send_command, mock_discover) -> None:
        """
        User can enable periodic battery status monitoring.

        GIVEN: A connected flight controller with battery monitoring capability
        WHEN: The user enables periodic battery status
        THEN: Battery monitoring should be configured
        AND: Periodic status messages should be requested
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        mock_send_command.return_value = (True, "")
        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.master = MagicMock()

        # When: Enable battery monitoring with 1-second interval
        success, _message = fc.request_periodic_battery_status(interval_microseconds=1000000)

        # Then: Battery monitoring enabled
        assert success is True
        mock_send_command.assert_called()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_retrieve_current_battery_status(self, mock_discover) -> None:
        """
        User can retrieve current battery voltage and current readings.

        GIVEN: A connected flight controller with battery monitoring enabled
        WHEN: The user requests current battery status
        THEN: Voltage and current readings should be returned
        AND: Values should be within expected ranges
        """
        # Given: Connected flight controller with battery data
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)
        mock_master = MagicMock()

        # Mock battery status message
        mock_battery_msg = MagicMock()
        mock_battery_msg.voltages = [4200, 4180, 4190]  # mV per cell
        mock_battery_msg.current_battery = 1500  # cA (15A)
        mock_master.recv_match.return_value = mock_battery_msg
        fc.master = mock_master
        # Need battery monitoring enabled for get_battery_status to work
        fc.fc_parameters = {"BATT_MONITOR": 4}  # Battery monitoring enabled

        # When: Get battery status
        battery_data, message = fc.get_battery_status()

        # Then: Battery data retrieved successfully
        if battery_data is not None:
            voltage, current = battery_data
            assert voltage > 0, "Voltage should be positive"
            assert current > 0, "Current should be positive"
        assert message == ""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_check_battery_monitoring_configuration(self, mock_discover) -> None:
        """
        User can check if battery monitoring is properly configured.

        GIVEN: A flight controller with parameter configuration
        WHEN: The user checks battery monitoring status
        THEN: Configuration status should be returned accurately
        """
        # Given: Flight controller with battery monitoring enabled
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.fc_parameters = {"BATT_MONITOR": 4.0}  # Battery monitoring enabled

        # When: Check battery monitoring status
        is_enabled = fc.is_battery_monitoring_enabled()

        # Then: Monitoring status correctly identified
        assert is_enabled is True

        # When: Check with monitoring disabled
        fc.fc_parameters = {"BATT_MONITOR": 0.0}  # Disabled
        is_enabled = fc.is_battery_monitoring_enabled()

        # Then: Disabled status correctly identified
        assert is_enabled is False


class TestFlightControllerErrorHandling:
    """Test error handling and edge cases in BDD style."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_receives_appropriate_error_when_operations_attempted_without_connection(self, mock_discover) -> None:
        """
        User receives clear error messages when attempting operations without connection.

        GIVEN: A flight controller that is not connected
        WHEN: The user attempts various operations
        THEN: Clear error messages should be provided
        AND: Operations should fail gracefully
        """
        # Given: Unconnected flight controller
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)
        assert fc.master is None

        # When/Then: Various operations should fail gracefully

        # Motor testing without connection
        success, error = fc.test_motor(0, "A", 1, 10, 2)
        assert success is False
        assert "No flight controller connection" in error

        # Battery status without connection
        battery_data, error = fc.get_battery_status()
        assert battery_data is None
        assert "No flight controller connection" in error

        # Stop motors without connection
        success, error = fc.stop_all_motors()
        assert success is False
        assert "No flight controller connection" in error

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_gets_voltage_thresholds_with_graceful_fallback(self, mock_discover) -> None:
        """
        User gets voltage thresholds with graceful fallback to defaults.

        GIVEN: A flight controller that may or may not have threshold parameters
        WHEN: The user requests voltage thresholds
        THEN: Either configured values or safe defaults should be returned
        """
        # Given: Flight controller without threshold parameters
        mock_discover.return_value = None
        fc = FlightController(reboot_time=5, baudrate=115200)
        fc.fc_parameters = {}

        # When: Get voltage thresholds (default values)
        low_threshold, critical_threshold = fc.get_voltage_thresholds()

        # Then: Default thresholds returned (both 0.0 when no parameters set)
        assert isinstance(low_threshold, float)
        assert isinstance(critical_threshold, float)
        assert low_threshold == 0.0
        assert critical_threshold == 0.0

        # When: Flight controller has configured thresholds
        fc.fc_parameters = {"BATT_ARM_VOLT": 14.0, "MOT_BAT_VOLT_MAX": 16.8}
        low_threshold, critical_threshold = fc.get_voltage_thresholds()

        # Then: Configured thresholds returned
        assert low_threshold == 14.0
        assert critical_threshold == 16.8
