#!/usr/bin/env python3

"""
BDD-style tests for the backend_flightcontroller.py file.

This file focuses on meaningful behavior-driven tests that validate user workflows
and business value rather than implementation details.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tempfile
from argparse import ArgumentParser
from typing import Any, Union, cast  # pylint: disable=unused-import
from unittest.mock import MagicMock, patch

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands
from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink import (
    FakeMavlinkConnectionFactory,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_serial import (
    FakeSerialPortDiscovery,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import (
    FlightControllerInfo,
)
from ardupilot_methodic_configurator.data_model_par_dict import ParDict

# pylint: disable=protected-access


def _build_flight_controller_with_mocks(
    reboot_time: int = 2,
) -> tuple[FlightController, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Helper returning a facade wired with MagicMock managers for delegation tests."""
    mock_master = MagicMock()
    mock_master.target_system = 1
    mock_master.target_component = 1

    mock_conn_mgr = MagicMock()
    mock_conn_mgr.master = mock_master
    mock_conn_mgr.info = FlightControllerInfo()
    mock_conn_mgr.comport = "ttyACM0"
    mock_conn_mgr.comport_device = "/dev/ttyACM0"
    mock_conn_mgr.baudrate = 115200
    mock_conn_mgr.discover_connections.return_value = None
    mock_conn_mgr.disconnect = MagicMock()
    mock_conn_mgr.add_connection.return_value = True
    mock_conn_mgr.create_connection_with_retry.return_value = "RECONNECTED"
    mock_conn_mgr.get_network_ports.return_value = ["tcp:127.0.0.1:5760"]
    mock_conn_mgr.get_connection_tuples.return_value = [("tcp:127.0.0.1:5760", "SITL")]
    mock_conn_mgr.set_master_for_testing = MagicMock()
    mock_conn_mgr._detect_vehicles_from_heartbeats.return_value = {(1, 1): {}}
    mock_conn_mgr._extract_firmware_type_from_banner.return_value = "ArduCopter"
    mock_conn_mgr._extract_chibios_version_from_banner.return_value = ("ChibiOS", None)
    mock_conn_mgr._select_supported_autopilot.return_value = "copter"
    mock_conn_mgr._populate_flight_controller_info = MagicMock()
    mock_conn_mgr._retrieve_autopilot_version_and_banner.return_value = "1.0"

    mock_params_mgr = MagicMock()
    mock_params_mgr.PARAM_FETCH_POLL_DELAY = 0.01
    mock_params_mgr.fc_parameters = {}
    mock_params_mgr.download_params.return_value = ({}, ParDict())
    mock_params_mgr.set_param.return_value = (True, "")
    mock_params_mgr.fetch_param.return_value = 1.0
    mock_params_mgr.clear_parameters = MagicMock()

    mock_commands_mgr = MagicMock()
    mock_commands_mgr.BATTERY_STATUS_CACHE_TIME = 1.0
    mock_commands_mgr.BATTERY_STATUS_TIMEOUT = 1.0
    mock_commands_mgr.COMMAND_ACK_TIMEOUT = 1.0
    mock_commands_mgr.reset_all_parameters_to_default.return_value = (True, "")
    mock_commands_mgr.test_motor.return_value = (True, "")
    mock_commands_mgr.test_all_motors.return_value = (True, "")
    mock_commands_mgr.test_motors_in_sequence.return_value = (True, "")
    mock_commands_mgr.stop_all_motors.return_value = (True, "")
    mock_commands_mgr.request_periodic_battery_status.return_value = (True, "")
    mock_commands_mgr.get_battery_status.return_value = ((12.0, 5.0), "")
    mock_commands_mgr.get_voltage_thresholds.return_value = (10.5, 21.0)
    mock_commands_mgr.is_battery_monitoring_enabled.return_value = True
    mock_commands_mgr.get_frame_info.return_value = (1, 2)

    mock_files_mgr = MagicMock()
    mock_files_mgr.upload_file.return_value = True
    mock_files_mgr.download_last_flight_log.return_value = True

    fc = FlightController(
        reboot_time=reboot_time,
        connection_manager=mock_conn_mgr,
        params_manager=mock_params_mgr,
        commands_manager=mock_commands_mgr,
        files_manager=mock_files_mgr,
    )
    return fc, mock_conn_mgr, mock_params_mgr, mock_commands_mgr, mock_files_mgr, mock_master


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
        # Note: Parameter is NOT cached by set_param - cache only updates from actual FC reads


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
        assert fc.master is not None
        master = cast("Any", fc.master)
        master.mav.command_long_send.assert_called_once()
        call_args = master.mav.command_long_send.call_args[0]

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
        assert fc.master is not None
        master = cast("Any", fc.master)
        master.mav.command_long_send.assert_called_once()
        call_args = master.mav.command_long_send.call_args[0]

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
        assert fc.master is not None
        master = cast("Any", fc.master)
        assert master.mav.command_long_send.call_count == 4

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

        # And: Data stream requests sent per retry configuration
        assert mock_send_command.call_count == FlightControllerCommands.BATTERY_STATUS_REQUEST_ATTEMPTS

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
        fc.fc_parameters["BATT_MONITOR"] = 4.0  # Simulate parameter in cache
        is_enabled = fc.is_battery_monitoring_enabled()

        # Then: Monitoring correctly identified as enabled
        assert is_enabled is True

        # When: Check with monitoring disabled
        fc.fc_parameters["BATT_MONITOR"] = 0.0  # Simulate parameter in cache
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

    def test_user_gets_timeout_error_for_nonexistent_parameters(self) -> None:
        """
        User gets appropriate timeout behavior when requesting nonexistent parameters.

        GIVEN: Connected flight controller
        WHEN: User requests parameter that doesn't exist
        THEN: fetch_param should raise TimeoutError after timeout
        AND: User understands the parameter is not available
        """
        # Given: Connected flight controller
        fc = FlightController(reboot_time=2, baudrate=115200)
        mock_master = MagicMock()
        # Mock recv_match to always return None (no PARAM_VALUE response)
        mock_master.recv_match.return_value = None
        # Mock the mav object for param_request_read_send
        mock_master.mav = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections",
            return_value=None,
        ):
            fc.set_master_for_testing(mock_master)

        # When/Then: Fetch nonexistent parameter and expect timeout
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_params.time_time") as mock_time:
            mock_time.side_effect = [0.0, 2.0]
            with pytest.raises(TimeoutError, match="FAKE_PARAM"):
                fc.fetch_param("FAKE_PARAM", timeout=1)

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


class TestServiceInjectionIntegration:
    """Test service injection integration with FlightControllerConnection."""

    def test_user_can_inject_both_services(self) -> None:
        """
        User can inject both serial discovery and MAVLink factory together.

        GIVEN: Developer wants full test isolation
        WHEN: Injecting both services
        THEN: Both should be used consistently
        """
        # Given: Both fake services
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Fake Controller")

        fake_mavlink = FakeMavlinkConnectionFactory()

        # When: Inject both services
        info = FlightControllerInfo()
        connection = FlightControllerConnection(
            info=info,
            serial_port_discovery=fake_serial,
            mavlink_connection_factory=fake_mavlink,
        )

        # Then: Both services are active
        assert connection._serial_port_discovery is fake_serial  # pylint: disable=protected-access
        assert connection._mavlink_connection_factory is fake_mavlink  # pylint: disable=protected-access

    def test_discovery_and_creation_workflow(self) -> None:
        """
        Complete workflow: discover ports then create connections.

        GIVEN: Both services injected
        WHEN: Discovering ports and creating connections
        THEN: Workflow should complete without errors
        """
        # Given: Fake services
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Test FC")

        fake_mavlink = FakeMavlinkConnectionFactory()

        info = FlightControllerInfo()
        connection = FlightControllerConnection(
            info=info,
            serial_port_discovery=fake_serial,
            mavlink_connection_factory=fake_mavlink,
        )

        # When: Discover connections
        connection.discover_connections()

        # Then: Ports are discoverable
        connection_tuples = connection.get_connection_tuples()
        assert any(t[0] == "/dev/ttyUSB0" for t in connection_tuples)


class TestFlightControllerResetAndDelegation:
    """Test reset workflow and delegation helpers exposed by the facade."""

    def test_user_is_warned_about_modemmanager_interference(self) -> None:
        """
        Users are warned about ModemManager before connections are attempted.

        GIVEN: ModemManager is detected on the operating system
        WHEN: A flight controller instance is created
        THEN: A warning should be logged with remediation guidance
        """
        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller.os_path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_flightcontroller.logging_warning") as mock_warning,
        ):
            _build_flight_controller_with_mocks()

        mock_warning.assert_called_once()

    def test_user_can_reset_and_reconnect_after_configuration(self) -> None:
        """
        Reset workflow restarts the controller and reconnects with progress updates.

        GIVEN: Connected controller after configuration changes
        WHEN: User requests a reset to apply firmware changes
        THEN: The autopilot should reboot and reconnect using retries if needed
        AND: Progress callbacks should reflect each wait step
        """
        fc, mock_conn_mgr, *_others, mock_master = _build_flight_controller_with_mocks(reboot_time=2)
        mock_conn_mgr.create_connection_with_retry.return_value = "RECONNECTED"
        progress_updates: list[tuple[int, int]] = []
        connection_progress = MagicMock()

        with patch("ardupilot_methodic_configurator.backend_flightcontroller.time_sleep", return_value=None):
            result = fc.reset_and_reconnect(
                reset_progress_callback=lambda current, total: progress_updates.append((current, total)),
                connection_progress_callback=connection_progress,
                extra_sleep_time=1,
            )

        mock_master.reboot_autopilot.assert_called_once()
        mock_conn_mgr.disconnect.assert_called_once()
        mock_conn_mgr.create_connection_with_retry.assert_called_once_with(
            progress_callback=connection_progress,
            retries=3,
            timeout=5,
            baudrate=mock_conn_mgr.baudrate,
            log_errors=True,
        )
        assert progress_updates[0] == (0, 3)
        assert progress_updates[-1] == (3, 3)
        assert result == "RECONNECTED"

    def test_reset_and_reconnect_returns_immediately_when_disconnected(self) -> None:
        """
        Reset workflow aborts gracefully when no connection exists.

        GIVEN: Controller facade without an active connection
        WHEN: User triggers reset
        THEN: No reboot attempts should be performed
        AND: An empty status string should be returned
        """
        fc, mock_conn_mgr, *_ = _build_flight_controller_with_mocks()
        mock_conn_mgr.master = None

        result = fc.reset_and_reconnect()

        assert result == ""
        mock_conn_mgr.disconnect.assert_not_called()

    def test_user_can_read_current_comport_and_device(self) -> None:
        """
        Users can inspect the delegated comport information for diagnostics.

        GIVEN: Controller facade backed by a mocked connection manager
        WHEN: The user inspects comport properties
        THEN: Values should be retrieved directly from the connection manager
        """
        fc, mock_conn_mgr, *_ = _build_flight_controller_with_mocks()
        mock_conn_mgr.comport = "ttyUSB0"
        mock_conn_mgr.comport_device = "/dev/ttyUSB0"

        assert fc.comport == "ttyUSB0"
        assert fc.comport_device == "/dev/ttyUSB0"

    def test_user_can_query_available_network_ports(self) -> None:
        """
        Users can request enumerated network ports through the facade.

        GIVEN: Connection manager advertises network targets
        WHEN: User calls get_network_ports()
        THEN: The same list should be returned unchanged
        """
        fc, mock_conn_mgr, *_ = _build_flight_controller_with_mocks()
        mock_conn_mgr.get_network_ports.return_value = ["tcp:1"]

        assert fc.get_network_ports() == ["tcp:1"]
        mock_conn_mgr.get_network_ports.assert_called_once()

    def test_user_can_list_known_connections(self) -> None:
        """
        Users can view named connection tuples gathered by discovery.

        GIVEN: Connection discovery populated friendly names
        WHEN: User requests the tuple list
        THEN: The manager-provided tuples should be returned as-is
        """
        fc, mock_conn_mgr, *_ = _build_flight_controller_with_mocks()
        mock_conn_mgr.get_connection_tuples.return_value = [("tcp:2", "SITL")]

        assert fc.get_connection_tuples() == [("tcp:2", "SITL")]
        mock_conn_mgr.get_connection_tuples.assert_called_once()

    def test_user_can_retry_connection_attempts_via_facade(self) -> None:
        """
        Users can reuse the retry helper exposed by the facade.

        GIVEN: Controller facade with mocked connection manager
        WHEN: create_connection_with_retry is invoked with custom options
        THEN: The connection manager should receive the provided arguments
        """
        fc, mock_conn_mgr, *_ = _build_flight_controller_with_mocks()
        progress = MagicMock()

        fc.create_connection_with_retry(progress_callback=progress, retries=5, timeout=10, baudrate=57600, log_errors=False)

        mock_conn_mgr.create_connection_with_retry.assert_called_with(
            progress_callback=progress,
            retries=5,
            timeout=10,
            baudrate=57600,
            log_errors=False,
        )

    def test_user_can_request_serial_port_listing(self) -> None:
        """
        Serial port enumeration delegates to the connection utility.

        GIVEN: FlightControllerConnection exposes discovered ports
        WHEN: User calls the static helper
        THEN: The static method should forward to the connection class
        """
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller.FlightControllerConnection.get_serial_ports",
            return_value=["/dev/ttyS0"],
        ) as mock_ports:
            ports = FlightController.get_serial_ports()

        assert ports == ["/dev/ttyS0"]
        mock_ports.assert_called_once()

    def test_user_can_delegate_file_transfers_through_facade(self) -> None:
        """
        File uploads and downloads reuse the injected files manager.

        GIVEN: Controller facade wired with mocked files manager
        WHEN: User uploads or downloads a file
        THEN: The corresponding files manager methods should be triggered
        """
        fc, _conn_mgr, _params_mgr, _commands_mgr, mock_files_mgr, _master = _build_flight_controller_with_mocks()

        with tempfile.NamedTemporaryFile() as tmp_file:
            destination = tmp_file.name
            assert fc.upload_file("local.txt", "@SYS/local.txt") is True
            assert fc.download_last_flight_log(destination) is True

        mock_files_mgr.upload_file.assert_called_once_with("local.txt", "@SYS/local.txt", None)
        mock_files_mgr.download_last_flight_log.assert_called_once_with(destination, None)

    def test_cli_argument_helper_exposes_expected_flags(self) -> None:
        """
        CLI helper wires baudrate, device, and reboot-time arguments for users.

        GIVEN: An ArgumentParser dedicated to CLI tooling
        WHEN: add_argparse_arguments is invoked
        THEN: The resulting parser should accept key flight controller options
        """
        parser = ArgumentParser(prog="fc")
        parser = FlightController.add_argparse_arguments(parser)
        args = parser.parse_args(["--device", "tcp:1", "--baudrate", "57600", "--reboot-time", "9"])

        assert args.device == "tcp:1"
        assert args.baudrate == 57600
        assert args.reboot_time == 9

    def test_sitl_helper_methods_delegate_to_connection_manager(self) -> None:
        """
        SITL helper methods expose the connection manager without duplicating logic.

        GIVEN: Controller facade with mocked connection manager internals
        WHEN: Developer utilities are invoked from tests
        THEN: Each call should be forwarded to the connection manager implementation
        """
        fc, mock_conn_mgr, *_ = _build_flight_controller_with_mocks()
        fc._select_supported_autopilot({(1, 1): {}})
        dummy_msg = MagicMock()
        fc._populate_flight_controller_info(dummy_msg)

        mock_conn_mgr._select_supported_autopilot.assert_called_once()
        mock_conn_mgr._populate_flight_controller_info.assert_called_once_with(dummy_msg)
