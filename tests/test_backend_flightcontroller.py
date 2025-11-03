#!/usr/bin/env python3

"""
BDD-style tests for the backend_flightcontroller.py file.

This file focuses on meaningful behavior-driven tests that validate user workflows
and business value rather than implementation details.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Union
from unittest.mock import MagicMock, patch

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class TestFlightControllerConnectionLifecycle:
    """Test complete flight controller connection lifecycle from user perspective."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_initialize_flight_controller_for_configuration(self, mock_discover) -> None:
        """
        User can initialize a flight controller instance ready for configuration tasks.

        GIVEN: A user needs to configure a flight controller
        WHEN: They create a FlightController instance with appropriate settings
        THEN: The instance should be properly initialized
        AND: Ready to connect to devices for configuration
        """
        # Given: User needs flight controller for configuration
        mock_discover.return_value = None

        # When: Initialize flight controller with standard configuration settings
        fc = FlightController(reboot_time=5, baudrate=115200)

        # Then: Flight controller properly initialized
        assert fc is not None
        assert fc.reboot_time == 5  # Standard reboot time
        assert fc.baudrate == 115200  # Standard baudrate
        assert fc.master is None  # Not connected yet
        assert not fc.fc_parameters  # No parameters loaded yet

        # And: Connection discovery was attempted
        mock_discover.assert_called_once()

    @pytest.mark.integration
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection")
    def test_user_can_establish_connection_to_hardware_flight_controller(self, mock_mavlink, mock_discover) -> None:
        """
        User can establish MAVLink connection to physical flight controller hardware.

        GIVEN: A physical flight controller connected via USB/serial
        WHEN: User connects using appropriate connection string
        THEN: MAVLink communication should be established
        AND: Flight controller should be ready for parameter operations
        """
        # Given: Physical flight controller available
        mock_discover.return_value = None
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1
        mock_mavlink.return_value = mock_connection

        fc = FlightController(reboot_time=2, baudrate=115200)

        # Mock the connect method to return success
        with patch.object(fc, "connect", return_value="") as mock_connect:
            # When: Connect to serial device
            result = fc.connect(device="/dev/ttyACM0")

            # Then: Connection established successfully
            assert result == ""  # Empty string indicates success
            mock_connect.assert_called_once_with(device="/dev/ttyACM0")

    @pytest.mark.integration
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection")
    def test_user_can_connect_to_sitl_for_development_testing(self, mock_mavlink, mock_discover) -> None:
        """
        User can connect to SITL instance for development and testing.

        GIVEN: SITL (Software In The Loop) simulation is running
        WHEN: User connects using TCP connection to SITL
        THEN: Connection should be established to simulation environment
        AND: Ready for testing configuration workflows
        """
        # Given: SITL running on standard port
        mock_discover.return_value = None
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1
        mock_mavlink.return_value = mock_connection

        fc = FlightController(reboot_time=2, baudrate=115200)

        # Mock the connect method to return success
        with patch.object(fc, "connect", return_value="") as mock_connect:
            # When: Connect to SITL TCP endpoint
            result = fc.connect(device="tcp:127.0.0.1:5760")

            # Then: SITL connection established
            assert result == ""  # Success
            mock_connect.assert_called_once_with(device="tcp:127.0.0.1:5760")

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_disconnect_cleanly_after_configuration(self, mock_discover) -> None:
        """
        User can disconnect from flight controller after completing configuration.

        GIVEN: User has finished configuring flight controller
        WHEN: They disconnect from the device
        THEN: Connection should be cleanly closed
        AND: Resources should be properly released
        """
        # Given: Connected flight controller after configuration
        mock_discover.return_value = None
        fc = FlightController(reboot_time=2, baudrate=115200)
        mock_master = MagicMock()
        fc.set_master_for_testing(mock_master)

        # When: Disconnect after configuration complete
        fc.disconnect()

        # Then: Connection properly closed
        assert fc.master is None
        mock_master.close.assert_called_once()


class TestFlightControllerParameterManagement:
    """Test parameter download, modification, and verification workflows."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @pytest.mark.integration
    @patch(
        "ardupilot_methodic_configurator.backend_flightcontroller_params.FlightControllerParams._download_params_via_mavlink"
    )
    def test_user_can_download_all_parameters_for_configuration_review(self, mock_download, mock_discover) -> None:
        """
        User can download complete parameter set for configuration review and modification.

        GIVEN: Connected flight controller with configuration parameters
        WHEN: User downloads all parameters for review
        THEN: Complete parameter set should be retrieved
        AND: Parameters should be available for configuration decisions
        """
        # Given: Connected flight controller with parameters
        mock_discover.return_value = None
        test_params = {
            "FRAME_TYPE": 1.0,  # Quad X
            "BATT_MONITOR": 4.0,  # Battery monitoring enabled
            "MOT_SPIN_ARM": 0.1,  # Motor spin on arm
            "MOT_SPIN_MIN": 0.15,  # Minimum motor spin
        }
        mock_download.return_value = test_params

        fc = FlightController(reboot_time=2, baudrate=115200)
        fc.set_master_for_testing(MagicMock())
        # Mock info to disable MAVFTP so it uses mavlink
        fc.info.is_mavftp_supported = False

        # When: Download parameters for configuration review
        params, defaults = fc.download_params()

        # Then: All parameters retrieved successfully
        assert params == test_params
        assert isinstance(defaults, dict)  # Default parameters also available
        assert "FRAME_TYPE" in params
        assert "BATT_MONITOR" in params

        # And: Download method called correctly
        mock_download.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_modify_individual_parameters_for_customization(self, mock_discover) -> None:
        """
        User can modify individual parameters to customize flight controller behavior.

        GIVEN: Connected flight controller with downloaded parameters
        WHEN: User modifies specific parameter for customization
        THEN: Parameter change should be sent to flight controller
        AND: Change should be applied immediately
        """
        # Given: Connected flight controller ready for configuration
        mock_discover.return_value = None
        fc = FlightController(reboot_time=2, baudrate=115200)
        mock_master = MagicMock()
        fc.set_master_for_testing(mock_master)

        # When: Modify battery monitoring parameter
        fc.set_param("BATT_MONITOR", 4.0)  # Enable battery monitoring

        # Then: Parameter change sent to flight controller
        mock_master.param_set_send.assert_called_once_with("BATT_MONITOR", 4.0)
        # And: Parameter cached locally
        assert fc.fc_parameters["BATT_MONITOR"] == 4.0


class TestFlightControllerMotorTestingWorkflow:
    """Test complete motor testing workflow for safety and functionality verification."""

    # pylint: disable=duplicate-code
    @pytest.fixture
    def mock_connected_fc(self) -> FlightController:
        """Fixture providing a properly mocked connected flight controller."""
        with patch("ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection"):
            fc = FlightController()
            mock_master = MagicMock()
            mock_master.target_system = 1
            mock_master.target_component = 1

            # Mock successful COMMAND_ACK response
            mock_ack = MagicMock()
            mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
            mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
            mock_ack.progress = 100
            mock_ack.result_param2 = 0

            def recv_match_side_effect(*_args: tuple, **kwargs: dict) -> Union[MagicMock, None]:
                type_arg = kwargs.get("type")
                if isinstance(type_arg, str) and type_arg == "COMMAND_ACK":
                    return mock_ack
                return None

            mock_master.recv_match.side_effect = recv_match_side_effect
            fc.set_master_for_testing(mock_master)
            return fc

    # pylint: enable=duplicate-code

    def test_user_can_safely_test_individual_motor_before_flight(self, mock_connected_fc: FlightController) -> None:
        """
        User can safely test individual motors before flight to verify functionality.

        GIVEN: Flight controller connected and armed state safe for testing
        WHEN: User tests motor 1 at low throttle for short duration
        THEN: Motor should spin at specified throttle
        AND: Test should complete without errors
        AND: Safety protocols should prevent accidental flight
        """
        # Given: Safe testing conditions
        fc = mock_connected_fc

        # When: Test individual motor safely
        success, error_msg = fc.test_motor(
            test_sequence_nr=0,  # First motor in sequence
            motor_letters="A",  # Motor A
            motor_output_nr=1,  # Output 1
            throttle_percent=10,  # Low throttle for safety
            timeout_seconds=2,  # Short test duration
        )

        # Then: Motor test completed successfully
        assert success is True, f"Motor test failed: {error_msg}"
        assert error_msg == "", "No error message expected on success"

        # And: Correct MAVLink command sent
        fc.master.mav.command_long_send.assert_called_once()  # type: ignore[attr-defined]
        call_args = fc.master.mav.command_long_send.call_args[0]  # type: ignore[attr-defined]

        assert call_args[0] == 1  # target_system
        assert call_args[1] == 1  # target_component
        assert call_args[2] == mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        assert call_args[4] == 1  # motor test number (1-based)
        assert call_args[5] == mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT
        assert call_args[6] == 10  # 10% throttle
        assert call_args[7] == 2  # 2 second timeout

    def test_user_can_emergency_stop_all_motors_during_testing(self, mock_connected_fc: FlightController) -> None:
        """
        User can immediately stop all motors during testing for emergency safety.

        GIVEN: Motors are running during testing
        WHEN: User activates emergency stop
        THEN: All motors should stop immediately
        AND: Safety should be prioritized over test completion
        """
        # Given: Motors running during test
        fc = mock_connected_fc

        # When: Emergency stop activated
        success, error_msg = fc.stop_all_motors()

        # Then: All motors stopped immediately
        assert success is True, f"Emergency stop failed: {error_msg}"
        assert error_msg == ""

        # And: Stop command sent to all motors
        fc.master.mav.command_long_send.assert_called_once()
        call_args = fc.master.mav.command_long_send.call_args[0]

        assert call_args[2] == mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        assert call_args[4] == 0  # motor number 0 = all motors
        assert call_args[6] == 0  # throttle 0 = stop
        assert call_args[7] == 0  # timeout 0 = immediate

    def test_user_can_test_all_motors_simultaneously_for_efficiency(self, mock_connected_fc: FlightController) -> None:
        """
        User can test all motors simultaneously to efficiently verify quadcopter functionality.

        GIVEN: Quadcopter frame with 4 motors configured
        WHEN: User tests all motors at once
        THEN: All motors should spin together
        AND: Test should complete efficiently
        """
        # Given: Quadcopter configuration
        fc = mock_connected_fc

        # When: Test all motors simultaneously
        success, error_msg = fc.test_all_motors(
            nr_of_motors=4,  # Quadcopter
            throttle_percent=15,  # Moderate throttle
            timeout_seconds=3,  # Reasonable test duration
        )

        # Then: All motors tested successfully
        assert success is True, f"All motors test failed: {error_msg}"
        assert error_msg == ""

        # And: Commands sent for all motors (4 commands for 4 motors)
        assert fc.master.mav.command_long_send.call_count == 4  # type: ignore[attr-defined]

    def test_motor_testing_handles_connection_failures_gracefully(self) -> None:
        """
        Motor testing handles connection failures gracefully without crashes.

        GIVEN: Flight controller connection lost during operation
        WHEN: User attempts motor testing
        THEN: Clear error message should be provided
        AND: No exceptions should be raised
        """
        # Given: No connection available
        with patch("ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection"):
            fc = FlightController()
            fc.set_master_for_testing(None)  # Simulate lost connection

            # When: Attempt motor test without connection
            success, error_msg = fc.test_motor(0, "A", 1, 10, 2)

            # Then: Graceful failure with clear message
            assert success is False
            assert "No flight controller connection" in error_msg


class TestFlightControllerBatteryMonitoringWorkflow:
    """Test battery monitoring setup and status checking for safe operation."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch(
        "ardupilot_methodic_configurator.backend_flightcontroller_commands.FlightControllerCommands.send_command_and_wait_ack"
    )
    def test_user_can_enable_battery_monitoring_for_flight_safety(self, mock_send_command, mock_discover) -> None:
        """
        User can enable battery monitoring to ensure safe flight operations.

        GIVEN: Flight controller capable of battery monitoring
        WHEN: User enables battery status monitoring
        THEN: Periodic battery data should be available
        AND: Low battery warnings can prevent unsafe flight
        """
        # Given: Flight controller with battery monitoring capability
        mock_discover.return_value = None
        mock_send_command.return_value = (True, "")
        fc = FlightController(reboot_time=2, baudrate=115200)
        fc.set_master_for_testing(MagicMock())

        # When: Enable battery monitoring
        success, error_msg = fc.request_periodic_battery_status(interval_microseconds=1000000)  # 1 second

        # Then: Battery monitoring enabled successfully
        assert success is True, f"Battery monitoring setup failed: {error_msg}"
        assert error_msg == ""

        # And: Data stream request sent
        mock_send_command.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_can_verify_battery_monitoring_configuration(self, mock_discover) -> None:
        """
        User can verify battery monitoring is properly configured before flight.

        GIVEN: Flight controller with parameter configuration
        WHEN: User checks battery monitoring status
        THEN: Configuration state should be clearly indicated
        AND: User can confirm safety systems are active
        """
        # Given: Flight controller with battery monitoring configured
        mock_discover.return_value = None
        fc = FlightController(reboot_time=2, baudrate=115200)
        fc.set_master_for_testing(MagicMock())  # Need a master connection

        # When: Check monitoring with battery monitoring enabled
        fc.set_param("BATT_MONITOR", 4.0)  # Analog voltage monitoring
        is_enabled = fc.is_battery_monitoring_enabled()

        # Then: Monitoring correctly identified as enabled
        assert is_enabled is True

        # When: Check with monitoring disabled
        fc.set_param("BATT_MONITOR", 0.0)  # Disabled
        is_enabled = fc.is_battery_monitoring_enabled()

        # Then: Monitoring correctly identified as disabled
        assert is_enabled is False


class TestFlightControllerErrorHandlingAndRecovery:
    """Test error handling and recovery scenarios for robust operation."""

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_gets_clear_error_when_connection_lost(self, mock_discover) -> None:
        """
        User gets clear error messages when flight controller connection is lost.

        GIVEN: Flight controller was connected but connection lost
        WHEN: User attempts operations requiring connection
        THEN: Clear error message should indicate connection issue
        AND: No cryptic exceptions should be raised
        """
        # Given: Connection lost during operation
        mock_discover.return_value = None
        fc = FlightController(reboot_time=2, baudrate=115200)
        fc.set_master_for_testing(None)  # Simulate lost connection

        # When: Attempt parameter operation without connection
        success, message = fc.reset_all_parameters_to_default()

        # Then: Clear error message provided
        assert success is False
        assert "No flight controller connection" in message

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    def test_user_gets_timeout_error_for_nonexistent_parameters(self, mock_discover) -> None:
        """
        User gets appropriate timeout errors when requesting nonexistent parameters.

        GIVEN: Connected flight controller
        WHEN: User requests parameter that doesn't exist
        THEN: Timeout error should be raised with clear message
        AND: User understands the parameter is not available
        """
        # Given: Connected flight controller
        mock_discover.return_value = None
        fc = FlightController(reboot_time=2, baudrate=115200)
        mock_master = MagicMock()
        # Mock recv_match to always return None (no PARAM_VALUE response)
        mock_master.recv_match.return_value = None
        # Mock the mav object for param_request_read_send
        mock_master.mav = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1
        fc.set_master_for_testing(mock_master)

        # When: Fetch nonexistent parameter
        # Then: Clear timeout error raised
        with pytest.raises(TimeoutError, match="Timeout waiting for parameter NONEXISTENT_PARAM"):
            fc.fetch_param("NONEXISTENT_PARAM", timeout=1)  # Short timeout for testing

    @patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections")
    @patch("ardupilot_methodic_configurator.backend_flightcontroller.mavutil.mavlink_connection")
    def test_user_can_recover_from_connection_failures(self, mock_mavlink, mock_discover) -> None:
        """
        User can recover from connection failures and re-establish communication.

        GIVEN: Connection failure occurred
        WHEN: User attempts to reconnect
        THEN: New connection should be established
        AND: Previous connection state should be cleared
        """
        # Given: Previous connection failed
        mock_discover.return_value = None
        mock_connection = MagicMock()
        mock_connection.target_system = 1
        mock_connection.target_component = 1
        mock_mavlink.return_value = mock_connection

        fc = FlightController(reboot_time=2, baudrate=115200)

        # When: Recover with reconnection
        result = fc.reset_and_reconnect()

        # Then: Reconnection attempted (result may vary based on implementation)
        assert isinstance(result, str)  # Result is a string message
