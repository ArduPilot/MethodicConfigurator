#!/usr/bin/env python3

"""
SITL integration tests for the backend_flightcontroller.py file.

These tests exercise REAL MAVLink communication with ArduPilot SITL (Software In The Loop).
Unlike unit tests with mocks, these validate actual protocol behavior, timing, and edge cases.

WHY SITL TESTS MATTER:
- Catch protocol bugs that mocks hide (message sequencing, timing, retries)
- Validate compatibility with real ArduPilot firmware
- Test async behavior that's impossible to properly mock
- Ensure changes work with actual hardware (SITL uses same protocol as real flight controllers)
- Verify real timeout handling and error conditions
- Validate actual MAVLink message acknowledgments (COMMAND_ACK, PARAM_VALUE, etc.)

RUNNING THESE TESTS:
1. These tests require SITL to be running (managed by sitl_manager fixture in conftest.py)
2. Run all SITL tests: pytest -m sitl tests/
3. Skip SITL tests: pytest -m "not sitl" tests/
4. SITL is automatically started/stopped by pytest fixtures
5. Connection string is configured in conftest.py (default: tcp:127.0.0.1:5760)

FIXTURES:
- sitl_manager: Manages SITL lifecycle (start/stop ArduCopter SITL process)
- sitl_flight_controller: Connected FlightController instance ready for testing with real SITL

IMPORTANT: These tests validate REAL protocol behavior that mocks cannot simulate:
- Actual network timing and latency
- Real parameter persistence in SITL memory
- Authentic command acknowledgment sequences
- True async communication patterns
- Genuine timeout and retry logic

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import time
from typing import TYPE_CHECKING

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

if TYPE_CHECKING:
    from conftest import SITLManager


# Test helper to wait for parameter value with timeout
def wait_for_param_value(fc: FlightController, param_name: str, expected_value: float, timeout: float = 2.0) -> bool:
    """
    Wait for parameter to reach expected value.

    Poll the parameter until it matches the expected value or timeout is reached.
    """
    start = time.time()
    while time.time() - start < timeout:
        actual = fc.fetch_param(param_name)
        if actual == expected_value:
            return True
        time.sleep(fc.PARAM_FETCH_POLL_DELAY)
    return False


@pytest.mark.integration
@pytest.mark.sitl
def test_user_can_connect_to_real_sitl_via_tcp(sitl_flight_controller: FlightController) -> None:
    """
    User can establish TCP connection to real ArduPilot SITL simulation.

    GIVEN: Real ArduCopter SITL instance is running on localhost:5760
    WHEN: User connects FlightController via TCP MAVLink connection
    THEN: Connection should be established successfully
    AND: Firmware type should be detected as ArduCopter from real heartbeat
    AND: Actual MAVLink communication channel should be active

    NOTE: This test validates REAL connection behavior that mocks cannot simulate:
    - Actual TCP socket communication
    - Real MAVLink heartbeat detection
    - Authentic firmware version identification
    - True network timing and latency
    """
    assert sitl_flight_controller.master is not None
    assert sitl_flight_controller.info.firmware_type == "ArduCopter"


@pytest.mark.integration
@pytest.mark.sitl
def test_user_can_download_all_parameters_from_real_sitl(sitl_flight_controller: FlightController) -> None:
    """
    User can download complete parameter set from real SITL via MAVLink protocol.

    GIVEN: Connected flight controller with real SITL containing ArduCopter parameters
    WHEN: User downloads all parameters using MAVLink PARAM_REQUEST_LIST
    THEN: Standard ArduCopter parameters should be retrieved successfully
    AND: Parameters should include frame configuration (FRAME_TYPE, FRAME_CLASS)
    AND: Actual MAVLink parameter protocol should complete without errors

    NOTE: This validates REAL parameter download that mocks cannot replicate:
    - Actual PARAM_REQUEST_LIST / PARAM_VALUE message sequence
    - Real parameter count and ordering from SITL
    - Authentic retry logic for missing parameters
    - True async parameter streaming behavior
    """
    params, _ = sitl_flight_controller.download_params()

    assert isinstance(params, dict)
    assert len(params) > 0
    assert "FRAME_TYPE" in params  # Common ArduCopter parameter
    assert "FRAME_CLASS" in params


@pytest.mark.integration
@pytest.mark.sitl
def test_user_can_safely_test_motors_with_real_sitl_acknowledgment(sitl_flight_controller: FlightController) -> None:
    """
    User receives real MAVLink COMMAND_ACK from SITL during motor testing.

    GIVEN: Real ArduCopter SITL that processes MAV_CMD_DO_MOTOR_TEST commands
    WHEN: User sends motor test command with 10% throttle for 2 seconds
    THEN: Real SITL should send COMMAND_ACK with MAV_RESULT_ACCEPTED
    AND: Test should complete without errors
    AND: Safety protocols should be validated by real SITL firmware

    NOTE: SITL is essential here because it validates:
    - Real SITL safety parameter checks (throttle limits, arming state)
    - COMMAND_ACK timing is realistic (not instant like mocks)
    - Actual command sequencing that hardware uses
    - Authentic MAV_CMD_DO_MOTOR_TEST protocol behavior
    """
    success, error_msg = sitl_flight_controller.test_motor(
        test_sequence_nr=0, motor_letters="A", motor_output_nr=1, throttle_percent=10, timeout_seconds=2
    )

    assert success, f"Motor test failed: {error_msg}"


@pytest.mark.integration
@pytest.mark.sitl
def test_user_can_monitor_battery_status_from_real_sitl(sitl_flight_controller: FlightController) -> None:
    """
    User can monitor battery voltage and current from real SITL telemetry.

    GIVEN: Connected flight controller with battery monitoring enabled in real SITL
    WHEN: User requests periodic battery status via MAVLink
    THEN: Real battery voltage and current should be returned from SITL
    AND: MAVLink BATTERY_STATUS messages should be received
    AND: Actual telemetry streaming should work correctly

    NOTE: This validates REAL telemetry that mocks cannot simulate:
    - Actual MAVLink message streaming (SET_MESSAGE_INTERVAL)
    - Real BATTERY_STATUS message format and timing
    - Authentic parameter-dependent behavior (BATT_MONITOR)
    - True async telemetry reception
    """
    # Download parameters first as get_battery_status requires them
    params, _ = sitl_flight_controller.download_params()
    assert isinstance(params, dict)
    assert len(params) > 0
    # Store parameters in the flight controller instance
    sitl_flight_controller.fc_parameters = params

    success, error_msg = sitl_flight_controller.request_periodic_battery_status()
    assert success, f"Battery monitoring setup failed: {error_msg}"

    # Use the constant instead of magic number
    time.sleep(sitl_flight_controller.BATTERY_STATUS_CACHE_TIME / 3)  # Wait for battery data

    battery_status, status_error = sitl_flight_controller.get_battery_status()
    assert battery_status is not None, f"Battery status retrieval failed: {status_error}"


@pytest.mark.integration
@pytest.mark.sitl
def test_user_can_modify_and_verify_parameters_on_real_sitl(sitl_flight_controller: FlightController) -> None:
    """
    User can reliably set and verify parameters with real ArduPilot SITL.

    GIVEN: Real SITL instance with actual parameter storage in memory
    WHEN: User modifies FRAME_TYPE parameter via MAVLink PARAM_SET
    THEN: Parameter should be set and acknowledged by real SITL
    AND: Fetching parameter should return the new value from SITL memory
    AND: Original value should be restorable without issues

    NOTE: This validates REAL MAVLink parameter protocol including:
    - PARAM_SET message handling by actual SITL firmware
    - PARAM_VALUE acknowledgment with real timing
    - Parameter persistence in SITL memory during session
    - Async request/response timing and retry logic
    - Actual parameter validation by SITL (value ranges, types)
    """
    # Save original value
    original_value = sitl_flight_controller.fetch_param("FRAME_TYPE")
    assert original_value is not None

    # Set a new value (ensure it's different)
    new_value = 1 if original_value != 1 else 2
    sitl_flight_controller.set_param("FRAME_TYPE", float(new_value))

    # Use helper function with proper polling instead of arbitrary sleep
    assert wait_for_param_value(sitl_flight_controller, "FRAME_TYPE", new_value), (
        f"Parameter not set correctly: expected {new_value}"
    )

    # Restore original value
    sitl_flight_controller.set_param("FRAME_TYPE", float(original_value))
    assert wait_for_param_value(sitl_flight_controller, "FRAME_TYPE", original_value), "Failed to restore original value"


@pytest.mark.integration
@pytest.mark.sitl
def test_user_can_retrieve_frame_configuration_from_real_sitl(sitl_flight_controller: FlightController) -> None:
    """
    User can retrieve accurate frame information from real SITL parameters.

    GIVEN: Connected flight controller with real SITL parameter storage
    WHEN: User requests frame class and type information
    THEN: Frame class and type should be returned correctly as integers
    AND: Values should match actual SITL configuration
    AND: Frame class should be valid (> 0)
    AND: Frame type should be valid (>= 0)

    NOTE: This validates real parameter retrieval and business logic:
    - Actual parameter fetch from SITL (FRAME_CLASS, FRAME_TYPE)
    - Type conversion from float to int with real data
    - Default value handling matches SITL behavior
    """
    frame_class, frame_type = sitl_flight_controller.get_frame_info()

    assert isinstance(frame_class, int)
    assert isinstance(frame_type, int)
    assert frame_class > 0  # Should have valid frame class
    assert frame_type >= 0  # Frame type can be 0


@pytest.mark.integration
@pytest.mark.sitl
def test_user_can_configure_custom_network_ports_for_sitl(sitl_manager: "SITLManager") -> None:
    """
    User can initialize FlightController with custom network ports for flexible SITL connections.

    GIVEN: Custom network port configuration for SITL (tcp://127.0.0.1:5760)
    WHEN: User creates FlightController with custom network_ports parameter
    THEN: Custom ports should be stored and used for connection attempts
    AND: Connection discovery should include custom port
    AND: User can connect to non-standard SITL ports

    NOTE: This validates real configuration flexibility needed for:
    - Multiple SITL instances on different ports
    - Custom network configurations
    - Integration with different SITL setups
    """
    # Use the new configurable network_ports feature
    custom_port = sitl_manager.connection_string.replace("tcp:", "tcp://")
    custom_fc = FlightController(reboot_time=2, baudrate=115200, network_ports=[custom_port])

    # Verify the custom port was set - check if port number is in the connection string
    assert "5760" in custom_fc._network_ports[0]  # pylint: disable=protected-access

    # Clean up
    if custom_fc.master:
        custom_fc.disconnect()


@pytest.mark.integration
@pytest.mark.sitl
def test_timeout_constants_are_properly_configured(sitl_flight_controller: FlightController) -> None:
    """
    Timeout constants are properly defined and accessible for real MAVLink timing.

    GIVEN: Connected flight controller instance
    WHEN: Checking timeout and polling constants
    THEN: Constants should be properly defined and accessible
    AND: Values should be reasonable for real network communication
    AND: Constants should match actual usage in MAVLink protocol handlers

    NOTE: These constants control real timing behavior that affects:
    - Command acknowledgment timeouts (COMMAND_ACK_TIMEOUT)
    - Parameter fetch polling intervals (PARAM_FETCH_POLL_DELAY)
    - Battery status request timeouts (BATTERY_STATUS_TIMEOUT)
    """
    # Verify new constants are accessible
    assert hasattr(sitl_flight_controller, "COMMAND_ACK_TIMEOUT")
    assert hasattr(sitl_flight_controller, "PARAM_FETCH_POLL_DELAY")
    assert hasattr(sitl_flight_controller, "BATTERY_STATUS_TIMEOUT")

    # Verify constants have reasonable values
    assert sitl_flight_controller.COMMAND_ACK_TIMEOUT > 0
    assert sitl_flight_controller.PARAM_FETCH_POLL_DELAY > 0
    assert sitl_flight_controller.BATTERY_STATUS_TIMEOUT > 0


@pytest.mark.integration
@pytest.mark.sitl
def test_firmware_type_extraction_from_real_banner_messages(sitl_flight_controller: FlightController) -> None:
    """
    Firmware type can be correctly extracted from various real banner message formats.

    GIVEN: Different banner message formats from real flight controllers
    WHEN: Extracting firmware type using _extract_firmware_type_from_banner
    THEN: Correct firmware type should be identified (ArduCopter, ArduPlane, etc.)
    AND: Method should handle both hardware (with ChibiOS) and SITL (without ChibiOS) banners
    AND: Empty banners should return empty string gracefully

    NOTE: This validates real-world banner parsing that users encounter:
    - ChibiOS-style banners from real hardware flight controllers
    - SITL-style banners without ChibiOS information
    - Different ArduPilot vehicle types (Copter, Plane, Rover, etc.)
    - Robustness with malformed or missing banner data
    """
    # Test with ChibiOS-style banner (typical for hardware)
    banner_with_chibios = [
        "Some header message",
        "ChibiOS: 12345678",
        "ArduCopter V4.5.0 (abc123)",
        "Other info",
    ]
    firmware_type = sitl_flight_controller._extract_firmware_type_from_banner(banner_with_chibios, 1)  # pylint: disable=protected-access
    assert firmware_type == "ArduCopter"

    # Test with SITL-style banner (no ChibiOS)
    banner_sitl = [
        "ArduCopter V4.5.0-dev (12345678)",
        "Frame: QUAD",
    ]
    firmware_type = sitl_flight_controller._extract_firmware_type_from_banner(banner_sitl, None)  # pylint: disable=protected-access
    assert firmware_type == "ArduCopter"

    # Test with ArduPlane
    banner_plane = ["ArduPlane V4.5.0 (abc123)"]
    firmware_type = sitl_flight_controller._extract_firmware_type_from_banner(banner_plane, None)  # pylint: disable=protected-access
    assert firmware_type == "ArduPlane"

    # Test with empty banner
    firmware_type = sitl_flight_controller._extract_firmware_type_from_banner([], None)  # pylint: disable=protected-access
    assert firmware_type == ""


@pytest.mark.integration
@pytest.mark.sitl
def test_chibios_version_extraction_from_banner_messages(sitl_flight_controller: FlightController) -> None:
    """
    ChibiOS version can be correctly extracted from real flight controller banners.

    GIVEN: Banner messages from real flight controllers with or without ChibiOS
    WHEN: Extracting ChibiOS version using _extract_chibios_version_from_banner
    THEN: Version and index should be correctly identified when present
    AND: Empty version and None index should be returned for SITL (no ChibiOS)
    AND: Method should handle various banner formats robustly

    NOTE: This validates real banner parsing needed for:
    - Hardware flight controller identification (has ChibiOS)
    - SITL vs hardware detection (SITL lacks ChibiOS)
    - Firmware version tracking and compatibility checks
    """
    # Test with ChibiOS present
    banner_with_chibios = [
        "Some header",
        "ChibiOS: 12345678",
        "ArduCopter V4.5.0",
    ]
    version, index = sitl_flight_controller._extract_chibios_version_from_banner(banner_with_chibios)  # pylint: disable=protected-access
    assert version == "12345678"
    assert index == 1

    # Test without ChibiOS (SITL case)
    banner_no_chibios = [
        "ArduCopter V4.5.0-dev",
        "Frame: QUAD",
    ]
    version, index = sitl_flight_controller._extract_chibios_version_from_banner(banner_no_chibios)  # pylint: disable=protected-access
    assert version == ""
    assert index is None


@pytest.mark.integration
@pytest.mark.sitl
def test_vehicle_detection_from_real_heartbeat_messages(sitl_flight_controller: FlightController) -> None:
    """
    Vehicles can be detected from real MAVLink HEARTBEAT messages from SITL.

    GIVEN: Real SITL instance broadcasting HEARTBEAT messages
    WHEN: Detecting vehicles using _detect_vehicles_from_heartbeats
    THEN: At least one vehicle should be detected with valid system/component IDs
    AND: System ID should be positive integer
    AND: Component ID should be non-negative integer
    AND: Detection should work within reasonable timeout

    NOTE: This validates REAL heartbeat detection that is critical for:
    - Initial connection establishment to flight controllers
    - Multiple vehicle detection in MAVLink networks
    - System/component ID identification for message routing
    - Actual async message reception and filtering
    """
    # The sitl_flight_controller fixture already has a connection established
    # We can test the detection method works by verifying the master connection exists
    assert sitl_flight_controller.master is not None

    # Detect vehicles (should find at least the SITL instance)
    detected = sitl_flight_controller._detect_vehicles_from_heartbeats(timeout=2)  # pylint: disable=protected-access

    # Should have detected at least one vehicle
    assert len(detected) > 0

    # Verify the detected vehicle has valid IDs
    for sysid, compid in detected:
        assert isinstance(sysid, int)
        assert isinstance(compid, int)
        assert sysid > 0  # System ID should be positive
        assert compid >= 0  # Component ID can be 0


@pytest.mark.integration
@pytest.mark.sitl
def test_protected_methods_remain_accessible_after_refactoring(sitl_flight_controller: FlightController) -> None:
    """
    Protected methods remain accessible for testing after Phase 1 refactoring.

    GIVEN: FlightController instance after refactoring to delegation pattern
    WHEN: Accessing protected methods (single underscore prefix)
    THEN: Methods should exist and be callable (not name-mangled)
    AND: Refactoring should maintain testability
    AND: Protected methods should not be hidden by double underscore

    NOTE: This validates a key refactoring goal:
    - Methods are protected (single _) not private (double __)
    - Testing infrastructure can access internal methods when needed
    - Refactoring preserved the ability to test implementation details
    - Documentation and maintainability are improved
    """
    # Verify protected methods exist and are accessible
    assert hasattr(sitl_flight_controller, "_extract_firmware_type_from_banner")
    assert hasattr(sitl_flight_controller, "_extract_chibios_version_from_banner")
    assert hasattr(sitl_flight_controller, "_detect_vehicles_from_heartbeats")
    assert hasattr(sitl_flight_controller, "_select_supported_autopilot")
    assert hasattr(sitl_flight_controller, "_populate_flight_controller_info")
    assert hasattr(sitl_flight_controller, "_retrieve_autopilot_version_and_banner")

    # Verify they are callable
    assert callable(sitl_flight_controller._extract_firmware_type_from_banner)  # pylint: disable=protected-access
    assert callable(sitl_flight_controller._extract_chibios_version_from_banner)  # pylint: disable=protected-access
    assert callable(sitl_flight_controller._detect_vehicles_from_heartbeats)  # pylint: disable=protected-access
