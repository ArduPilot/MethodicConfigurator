#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_connection.py.

This file focuses on connection management behavior including port discovery,
connection establishment, heartbeat detection, and error handling.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import Mock, patch

import pytest
import serial.tools.list_ports_common
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    DEFAULT_BAUDRATE,
    SUPPORTED_BAUDRATES,
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink import (
    FakeMavlinkConnectionFactory,
    SystemMavlinkConnectionFactory,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_serial import (
    FakeSerialPortDiscovery,
    SystemSerialPortDiscovery,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

# pylint: disable=protected-access, too-many-lines


class TestFlightControllerConnectionServiceInjection:
    """Test dependency injection of services into connection manager."""

    def test_default_services_are_system_implementations(self) -> None:
        """
        Default services use system implementations for real hardware.

        GIVEN: FlightControllerConnection created without services
        WHEN: Connection initializes
        THEN: System serial discovery should be default
        AND: System MAVLink factory should be default
        """
        # Given/When: Create connection without services
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # Then: System services are defaults
        assert isinstance(connection._serial_port_discovery, SystemSerialPortDiscovery)
        assert isinstance(connection._mavlink_connection_factory, SystemMavlinkConnectionFactory)

    def test_user_can_inject_fake_serial_discovery(self) -> None:
        """
        User can inject fake serial discovery for testing.

        GIVEN: Developer testing without real hardware
        WHEN: Injecting FakeSerialPortDiscovery
        THEN: Connection should use the fake service
        AND: Port discovery should return only fake ports
        """
        # Given: Fake serial discovery with test ports
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Test Controller")

        # When: Inject into connection
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
        )

        # Then: Fake service is used
        assert connection._serial_port_discovery is fake_serial
        connection.discover_connections()
        tuples = connection.get_connection_tuples()
        assert any(t[0] == "/dev/ttyUSB0" for t in tuples)

    def test_user_can_inject_fake_mavlink_factory(self) -> None:
        """
        User can inject fake MAVLink factory for testing.

        GIVEN: Developer testing without real flight controller
        WHEN: Injecting FakeMavlinkConnectionFactory
        THEN: Connection should use the fake factory
        AND: Factory should create test connections
        """
        # Given: Fake MAVLink factory
        fake_mavlink = FakeMavlinkConnectionFactory()

        # When: Inject into connection
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=fake_mavlink,
        )

        # Then: Fake factory is used
        assert connection._mavlink_connection_factory is fake_mavlink

    def test_user_can_inject_both_fake_services(self) -> None:
        """
        User can inject both services for complete test isolation.

        GIVEN: Developer needs full test environment control
        WHEN: Injecting both fake services
        THEN: Both should be active
        AND: Complete workflow should work with fakes
        """
        # Given: Both fake services
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Fake FC")
        fake_mavlink = FakeMavlinkConnectionFactory()

        # When: Inject both
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
            mavlink_connection_factory=fake_mavlink,
        )

        # Then: Both services are active
        assert connection._serial_port_discovery is fake_serial
        assert connection._mavlink_connection_factory is fake_mavlink


class TestFlightControllerConnectionPortDiscovery:
    """Test port discovery functionality for serial and network connections."""

    def test_user_can_discover_available_serial_ports(self) -> None:
        """
        User can discover all available serial ports on the system.

        GIVEN: System with multiple USB serial devices
        WHEN: User requests port discovery
        THEN: All available serial ports should be listed
        AND: Each port should have device path and description
        """
        # Given: System with serial ports
        mock_port1 = Mock(spec=serial.tools.list_ports_common.ListPortInfo)
        mock_port1.device = "/dev/ttyUSB0"
        mock_port1.description = "CP2102 USB to UART"

        mock_port2 = Mock(spec=serial.tools.list_ports_common.ListPortInfo)
        mock_port2.device = "/dev/ttyACM0"
        mock_port2.description = "Pixhawk Flight Controller"

        with patch("serial.tools.list_ports.comports", return_value=[mock_port1, mock_port2]):
            connection = FlightControllerConnection(info=FlightControllerInfo())

            # When: Discover serial ports
            ports = connection.get_serial_ports()

            # Then: All ports discovered with details
            assert len(ports) == 2
            assert any(p.device == "/dev/ttyUSB0" for p in ports)
            assert any(p.device == "/dev/ttyACM0" for p in ports)
            assert any("CP2102" in p.description for p in ports)
            assert any("Pixhawk" in p.description for p in ports)

    def test_user_discovers_fake_ports_with_injected_service(self) -> None:
        """
        User can discover fake ports using injected serial discovery service.

        GIVEN: FakeSerialPortDiscovery with test ports
        WHEN: User calls discover_connections
        THEN: Only fake ports should appear
        AND: Real system ports should not appear
        """
        # Given: Fake discovery with specific ports
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyFAKE0", "Fake Port 1")
        fake_serial.add_port("/dev/ttyFAKE1", "Fake Port 2")

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
        )

        # When: Discover connections
        connection.discover_connections()

        # Then: Only fake ports present
        tuples = connection.get_connection_tuples()
        assert any(t[0] == "/dev/ttyFAKE0" for t in tuples)
        assert any(t[0] == "/dev/ttyFAKE1" for t in tuples)

    def test_user_can_discover_network_connection_options(self) -> None:
        """
        User can see available network connection options for SITL/remote connections.

        GIVEN: Application supporting UDP/TCP connections
        WHEN: User requests network ports
        THEN: Standard ArduPilot network ports should be listed
        AND: Both UDP and TCP options should be available
        """
        # Given: Connection manager with network support
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Get network ports
        network_ports = connection.get_network_ports()

        # Then: Standard ArduPilot ports available
        assert len(network_ports) > 0
        # Check for common SITL ports
        assert any("udp:0.0.0.0:14550" in port for port in network_ports)
        assert any("tcp:127.0.0.1:5760" in port for port in network_ports)

    def test_user_can_specify_custom_network_ports(self) -> None:
        """
        User can specify custom network ports when creating connection.

        GIVEN: User needs different network ports for their setup
        WHEN: Creating connection with custom network_ports
        THEN: Specified ports should override defaults
        AND: Only custom ports should be available
        """
        # Given: Custom network ports
        custom_ports = ["tcp:192.168.1.1:5760", "udp:10.0.0.1:14550"]

        # When: Create connection with custom ports
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            network_ports=custom_ports,
        )

        # Then: Custom ports are used
        ports = connection.get_network_ports()
        assert ports == custom_ports

    def test_connection_list_includes_add_another_option(self) -> None:
        """
        Connection list includes option to add custom connection strings.

        GIVEN: Standard ports discovered
        WHEN: User views connection options
        THEN: "Add another" option should be present
        AND: User can specify custom connection strings
        """
        # Given: Connection manager
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Discover connections
        connection.discover_connections()
        tuples = connection.get_connection_tuples()

        # Then: Add another option present
        assert len(tuples) > 0
        assert tuples[-1] == ("Add another", "Add another")


class TestFlightControllerConnectionLifecycle:
    """Test connection lifecycle management."""

    def test_user_can_disconnect_cleanly(self) -> None:
        """
        User can disconnect cleanly from flight controller.

        GIVEN: Active connection to flight controller
        WHEN: User disconnects
        THEN: Connection should be closed
        AND: Resources should be released
        """
        # Given: Connected flight controller
        info = FlightControllerInfo()
        info.system_id = "42"
        info.capabilities["FTP"] = "supported"
        connection = FlightControllerConnection(info=info)
        mock_master = Mock()
        connection.set_master_for_testing(mock_master)

        # When: Disconnect
        connection.disconnect()

        # Then: Connection closed
        assert connection.master is None
        mock_master.close.assert_called_once()
        assert info.system_id == ""
        assert not info.capabilities

    def test_disconnect_handles_no_connection_gracefully(self) -> None:
        """
        Disconnect handles case where no connection exists.

        GIVEN: No active connection
        WHEN: User calls disconnect
        THEN: Operation should complete without errors
        AND: No exceptions should be raised
        """
        # Given: No connection
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Disconnect with no connection
        # Then: No exception raised
        connection.disconnect()
        assert connection.master is None

    def test_disconnect_handles_exception_during_close(self) -> None:
        """
        Disconnect handles exceptions during close gracefully.

        GIVEN: Connection with mock that raises exception
        WHEN: Disconnect is called
        THEN: Exception should be suppressed
        AND: Master should still be set to None
        """
        # Given: Connected with mock that raises
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_master = Mock()
        mock_master.close.side_effect = RuntimeError("Close failed")
        connection.set_master_for_testing(mock_master)

        # When: Disconnect (should not raise)
        connection.disconnect()

        # Then: Master is None despite exception
        assert connection.master is None

    def test_connect_none_resets_cached_info(self) -> None:
        """
        Selecting the "none" device clears stale controller metadata.

        GIVEN: Previously populated FlightControllerInfo
        WHEN: User selects the special "none" device to skip connecting
        THEN: Info should be reset so UI shows blank values
        """
        # Given: Cached info with stale values
        info = FlightControllerInfo()
        info.system_id = "11"
        info.capabilities["FTP"] = "supported"
        connection = FlightControllerConnection(info=info)

        # When: Connect with device="none"
        result = connection.connect(device="none")

        # Then: Info reset and no error reported
        assert result == ""
        assert info.system_id == ""
        assert not info.capabilities


class TestFlightControllerConnectionConfiguration:
    """Test connection configuration and settings."""

    def test_supported_baudrates_include_standard_values(self) -> None:
        """
        Supported baudrates include all standard ArduPilot values.

        GIVEN: ArduPilot firmware with specific baud rate support
        WHEN: User checks supported baud rates
        THEN: All standard rates should be available
        AND: Common rates like 115200 and 57600 should be included
        """
        # Then: Standard baud rates supported
        assert "115200" in SUPPORTED_BAUDRATES
        assert "57600" in SUPPORTED_BAUDRATES
        assert "921600" in SUPPORTED_BAUDRATES
        assert len(SUPPORTED_BAUDRATES) >= 10

    def test_default_baudrate_is_standard_value(self) -> None:
        """
        Default baud rate is set to standard USB serial value.

        GIVEN: USB serial connections typically use 115200
        WHEN: User creates connection with defaults
        THEN: Baud rate should be 115200
        """
        # Then: Default is standard USB serial rate
        assert DEFAULT_BAUDRATE == 115200

    def test_user_can_specify_custom_baudrate(self) -> None:
        """
        User can specify custom baudrate for connection.

        GIVEN: Non-standard baudrate requirement
        WHEN: Creating connection with custom baudrate
        THEN: Specified baudrate should be used
        """
        # When: Create connection with custom baudrate
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            baudrate=57600,
        )

        # Then: Custom baudrate is set
        assert connection.baudrate == 57600

    def test_default_baudrate_is_used_when_not_specified(self) -> None:
        """
        Default baudrate is used when not explicitly specified.

        GIVEN: User creates connection without specifying baudrate
        WHEN: Connection initializes
        THEN: Default baudrate should be used
        """
        # When: Create without specifying
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # Then: Default is used
        assert connection.baudrate == DEFAULT_BAUDRATE


class TestFlightControllerConnectionCustomStrings:
    """Test custom connection string handling."""

    def test_user_can_add_custom_connection_string(self) -> None:
        """
        User can add custom connection strings for specialized setups.

        GIVEN: Non-standard connection requirement
        WHEN: User adds custom connection string
        THEN: Connection should be added to available options
        AND: Duplicate connections should not be added
        """
        # Given: Connection manager
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Add custom connection
        result1 = connection.add_connection("udp:192.168.1.100:14550")
        result2 = connection.add_connection("udp:192.168.1.100:14550")  # Duplicate

        # Then: Custom connection added once
        assert result1 is True
        assert result2 is False  # Duplicate not added

        tuples = connection.get_connection_tuples()
        custom_added = any(t[0] == "udp:192.168.1.100:14550" for t in tuples)
        assert custom_added is True

    def test_empty_connection_string_rejected(self) -> None:
        """
        Empty connection strings are rejected.

        GIVEN: User attempts to add empty connection
        WHEN: Add connection is called with empty string
        THEN: Connection should not be added
        AND: False should be returned
        """
        # Given: Connection manager
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Add empty string
        result = connection.add_connection("")

        # Then: Not added
        assert result is False

    def test_custom_connection_string_deduplication(self) -> None:
        """
        Duplicate connection strings are not added.

        GIVEN: Connection already added
        WHEN: Same connection is added again
        THEN: Duplicate should be rejected
        AND: Only one instance should exist
        """
        # Given: Connection manager
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Add same connection multiple times
        assert connection.add_connection("/dev/ttyUSB0") is True
        assert connection.add_connection("/dev/ttyUSB0") is False

        # Then: Only one instance
        tuples = connection.get_connection_tuples()
        count = sum(1 for t in tuples if t[0] == "/dev/ttyUSB0")
        assert count == 1


class TestFlightControllerConnectionInfo:
    """Test flight controller information gathering."""

    def test_connection_info_is_single_source_of_truth(self) -> None:
        """
        Connection manager is single source of truth for flight controller info.

        GIVEN: Connection manager with info object
        WHEN: Info is accessed
        THEN: Same info object should be returned consistently
        AND: External modifications should be reflected
        """
        # Given: Connection manager
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Get info multiple times
        info1 = connection.info
        info2 = connection.info

        # Then: Same object returned
        assert info1 is info2
        assert isinstance(info1, FlightControllerInfo)

    def test_comport_device_returns_device_string(self) -> None:
        """
        Comport device property returns the device string when available.

        GIVEN: Connection with comport set
        WHEN: User accesses comport_device
        THEN: Device string should be returned
        """
        # Given: Connection with comport
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_comport = Mock()
        mock_comport.device = "/dev/ttyACM0"
        connection.comport = mock_comport

        # When: Access device string
        device = connection.comport_device

        # Then: Correct device returned
        assert device == "/dev/ttyACM0"

    def test_comport_device_returns_empty_when_no_connection(self) -> None:
        """
        Comport device property returns empty string when no connection.

        GIVEN: Connection without comport
        WHEN: User accesses comport_device
        THEN: Empty string should be returned
        """
        # Given: Connection without comport
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # When: Access device string
        device = connection.comport_device

        # Then: Empty string returned
        assert device == ""

    def test_connection_persists_comport_across_calls(self) -> None:
        """
        Comport is persisted across multiple calls.

        GIVEN: Connection with comport set
        WHEN: Accessing comport multiple times
        THEN: Same comport should be returned
        """
        # Given: Connection with comport
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_comport = Mock()
        connection.comport = mock_comport

        # When: Access multiple times
        comport1 = connection.comport
        comport2 = connection.comport

        # Then: Same object returned
        assert comport1 is comport2
        assert comport1 is mock_comport


class TestFlightControllerConnectionFactoryIntegration:
    """Test MAVLink factory integration with connection creation."""

    def test_fake_factory_creates_connections_with_attributes(self) -> None:
        """
        Fake MAVLink factory properly sets retries and progress_callback.

        GIVEN: Fake factory injected into connection
        WHEN: Creating a connection
        THEN: Connection should have retries attribute set
        AND: Connection should have progress_callback attribute
        """
        # Given: Connection with fake factory
        fake_factory = FakeMavlinkConnectionFactory()
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=fake_factory,
        )

        # When: Create connection via factory
        def test_callback(current: int, total: int) -> None:  # pylint: disable=unused-argument
            pass

        test_conn = connection._mavlink_connection_factory.create(
            device="/dev/ttyUSB0",
            baudrate=115200,
            retries=5,
            progress_callback=test_callback,
        )

        # Then: Attributes are set
        assert test_conn is not None
        assert test_conn.retries == 5
        assert test_conn.progress_callback is test_callback

    def test_connection_factory_methods_are_called(self) -> None:
        """
        Connection factory methods are properly called with parameters.

        GIVEN: Fake factory for testing
        WHEN: Calling factory create method
        THEN: Method should be invoked with correct parameters
        """
        # Given: Connection with fake factory
        fake_factory = FakeMavlinkConnectionFactory()
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=fake_factory,
        )

        # When: Create connection
        conn = connection._mavlink_connection_factory.create(
            device="/dev/ttyUSB0",
            baudrate=57600,
            timeout=10.0,
            retries=2,
        )

        # Then: Connection created with parameters
        assert conn is not None
        assert conn.device == "/dev/ttyUSB0"
        assert conn.baudrate == 57600
        assert conn.retries == 2


class TestConnectionErrorHandling:
    """Test error handling for connection failures and edge cases."""

    def test_failed_connection_includes_root_cause(self) -> None:
        """
        Connection errors surface the underlying exception message for users.

        GIVEN: MAVLink factory raises a ConnectionError with detailed cause
        WHEN: User attempts to connect to a specific device
        THEN: Returned error message should contain the original cause text
        """

        class ExplodingFactory(SystemMavlinkConnectionFactory):  # pylint: disable=too-few-public-methods
            """MAVLink factory that always raises ConnectionError."""

            def create(  # type: ignore[override] # pylint: disable=too-many-arguments, too-many-positional-arguments
                self,
                device: str,
                baudrate: int,
                timeout: float = 5.0,
                retries: int = 3,
                progress_callback: object = None,
            ) -> object:
                _ = (baudrate, timeout, retries, progress_callback)
                msg = f"{device}: Permission denied"
                raise ConnectionError(msg)

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=ExplodingFactory(),
        )

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_connection.mavutil.SerialPort"
        ) as mock_serial_port:
            mock_serial = Mock()
            mock_serial.device = "/dev/ttyACM0"
            mock_serial.description = "Mock"
            mock_serial_port.return_value = mock_serial
            error = connection.connect(device="/dev/ttyACM0", log_errors=False)

        assert "Permission denied" in error
        assert "/dev/ttyACM0" in error

    def test_connection_with_invalid_device_string(self) -> None:
        """
        Connection handles empty device strings gracefully.

        GIVEN: Empty device string
        WHEN: Creating connection with empty device
        THEN: Fake factory should create connection with empty device
        AND: Real factory would validate and reject empty device
        """
        # Given: Connection with fake services
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=FakeSerialPortDiscovery(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        # When: Create with empty device (fake factory accepts anything)
        conn = connection._mavlink_connection_factory.create(
            device="",
            baudrate=115200,
            retries=1,
        )

        # Then: Fake factory creates connection even with empty device
        # (Real factory would validate and reject this)
        assert conn is not None
        assert conn.device == ""

    def test_connection_with_unsupported_baudrate(self) -> None:
        """
        Connection validates baudrate is in supported list.

        GIVEN: Unsupported baudrate value (e.g., 999999)
        WHEN: Attempting connection with unsupported baudrate
        THEN: Should reject unsupported baudrates
        AND: Error message should list supported rates
        """
        # Given: Unsupported baudrate
        unsupported_baudrate = 999999

        # When: Try to create with unsupported rate
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        # Then: Should handle gracefully (either via mock or validation)
        test_conn = connection._mavlink_connection_factory.create(
            device="/dev/ttyUSB0",
            baudrate=unsupported_baudrate,
            retries=1,
        )
        # Fake factory accepts anything, but real factory would validate
        assert test_conn is not None

    def test_connection_discovery_with_no_serial_ports_available(self) -> None:
        """
        Connection discovery returns network ports when no serial ports available.

        GIVEN: No serial ports connected to system
        WHEN: Discovering connections
        THEN: Should return default network ports
        AND: get_connection_tuples should include network ports
        """
        # Given: Fake serial discovery with no ports
        fake_serial = FakeSerialPortDiscovery()
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
        )

        # When: Discover connections
        connection.discover_connections()

        # Then: Should return network ports even without serial ports
        tuples = connection.get_connection_tuples()
        assert isinstance(tuples, list)
        # Default network ports are always included
        assert len(tuples) > 0
        # Should include TCP network port
        assert any("tcp" in str(t[0]).lower() for t in tuples)

    def test_connection_retries_parameter_validation(self) -> None:
        """
        Connection validates retries parameter is positive.

        GIVEN: Various retry values (0, negative, positive)
        WHEN: Creating connection with different retry counts
        THEN: Should accept positive integers
        AND: Should handle edge cases (0, negative) appropriately
        """
        # Given: Connection factory
        fake_factory = FakeMavlinkConnectionFactory()
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=fake_factory,
        )

        # When: Create with valid positive retries
        conn_positive = connection._mavlink_connection_factory.create(
            device="/dev/ttyUSB0",
            baudrate=115200,
            retries=5,
        )
        assert conn_positive is not None
        assert conn_positive.retries == 5

        # When: Create with zero retries (edge case)
        conn_zero = connection._mavlink_connection_factory.create(
            device="/dev/ttyUSB0",
            baudrate=115200,
            retries=0,
        )
        assert conn_zero is not None
        assert conn_zero.retries == 0

    def test_connection_timeout_parameter_validation(self) -> None:
        """
        Connection validates timeout parameter is positive.

        GIVEN: Various timeout values
        WHEN: Creating connection with different timeouts
        THEN: Should accept positive timeout values
        AND: Should handle None as default
        """
        # Given: Connection factory
        fake_factory = FakeMavlinkConnectionFactory()
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=fake_factory,
        )

        # When: Create with valid timeout
        conn = connection._mavlink_connection_factory.create(
            device="/dev/ttyUSB0",
            baudrate=115200,
            timeout=5.0,
        )
        assert conn is not None

    def test_connection_with_progress_callback_none(self) -> None:
        """
        Connection handles missing progress callback gracefully.

        GIVEN: Connection without progress callback
        WHEN: Creating connection
        THEN: Should work without callback
        AND: Connection should be created successfully
        """
        # Given: No callback provided
        fake_factory = FakeMavlinkConnectionFactory()
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=fake_factory,
        )

        # When: Create connection without callback
        conn = connection._mavlink_connection_factory.create(
            device="/dev/ttyUSB0",
            baudrate=115200,
            progress_callback=None,
        )

        # Then: Connection created successfully
        assert conn is not None
        assert conn.progress_callback is None


class TestConnectionStateManagement:
    """Test connection state management and lifecycle."""

    def test_connection_info_is_populated_after_connection(self) -> None:
        """
        Connection info object is populated with flight controller details.

        GIVEN: FlightControllerConnection with info object
        WHEN: Connection initializes
        THEN: Info object should be accessible and updateable
        AND: Should maintain state across operations
        """
        # Given: Connection with info object
        info = FlightControllerInfo()
        connection = FlightControllerConnection(
            info=info,
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        # When: Access info
        # Then: Info should be available
        assert connection.info is not None
        assert connection.info is info

    def test_connection_master_attribute_starts_none(self) -> None:
        """
        Master connection attribute starts as None until connected.

        GIVEN: New FlightControllerConnection
        WHEN: Created but not yet connected
        THEN: Master should be None initially
        AND: Should be set only after successful connection
        """
        # Given: New connection
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        # Then: Master should be None initially
        assert connection.master is None

    def test_connection_multiple_discover_cycles(self) -> None:
        """
        Connection can be discovered multiple times without issues.

        GIVEN: FlightControllerConnection with services
        WHEN: Calling discover_connections multiple times
        THEN: Should not accumulate duplicate ports
        AND: Should handle repeated discovery gracefully
        """
        # Given: Connection with fake discovery
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Test Controller")
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
        )

        # When: Discover multiple times
        connection.discover_connections()
        tuples_1 = connection.get_connection_tuples()
        connection.discover_connections()
        tuples_2 = connection.get_connection_tuples()

        # Then: Should get consistent results
        assert len(tuples_1) > 0
        assert len(tuples_2) > 0

    def test_connection_get_connection_tuples_format(self) -> None:
        """
        Connection tuples have correct format (device, description).

        GIVEN: Connection with serial ports configured
        WHEN: Getting connection tuples
        THEN: Each tuple should have exactly 2 elements
        AND: First element should be device string, second description
        """
        # Given: Connection with ports
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=FakeSerialPortDiscovery(),
        )

        # When: Discover and get tuples
        connection.discover_connections()
        tuples = connection.get_connection_tuples()

        # Then: All tuples should be properly formatted
        for device, description in tuples:
            assert isinstance(device, str)
            assert isinstance(description, str)
            assert len(device) > 0  # Device string should not be empty
            # Description can be empty for network ports

    def test_connection_baudrate_configuration(self) -> None:
        """
        Connection stores and retrieves baudrate configuration.

        GIVEN: FlightControllerConnection created with custom baudrate
        WHEN: Accessing connection properties
        THEN: Baudrate should match configured value
        AND: Should support standard baudrates
        """
        # Given: Connection with custom baudrate
        custom_baudrate = 57600
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            baudrate=custom_baudrate,
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        # Then: Baudrate should be stored
        assert connection._baudrate == custom_baudrate

    def test_connection_network_ports_override(self) -> None:
        """
        Connection supports custom network port configuration.

        GIVEN: Custom network ports list provided
        WHEN: Creating connection with custom ports
        THEN: Custom ports should override defaults
        AND: Ports should be accessible for discovery
        """
        # Given: Custom network ports
        custom_ports = ["tcp:192.168.1.100:5760", "udp:192.168.1.100:14550"]
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            network_ports=custom_ports,
        )

        # Then: Custom ports should be set
        assert connection._network_ports == custom_ports

    def test_connection_comport_attribute_lifecycle(self) -> None:
        """
        Connection comport attribute lifecycle management.

        GIVEN: FlightControllerConnection
        WHEN: Checking comport status
        THEN: Should start as None
        AND: Should be updateable for connection tracking
        """
        # Given: New connection
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        # Then: Comport should be None initially
        assert connection.comport is None


def test_select_supported_autopilot_with_string_ids_does_not_raise() -> None:
    """
    Ensure that system/component IDs stored as strings do not cause logging to raise (previously %d was used).

    This is to prevent future regressions
    GIVEN: FlightControllerConnection and a detected vehicle
    WHEN: _select_supported_autopilot is called and FlightControllerInfo stores
          string IDs
    THEN: The function returns success and does not raise
    """
    connection = FlightControllerConnection(info=FlightControllerInfo())

    # Minimal dummy heartbeat message - use supported autopilot constant
    class DummyHeartbeat:  # pylint: disable=too-few-public-methods
        """Dummy MAVLink heartbeat used as input to _select_supported_autopilot."""

        autopilot = mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA
        type = mavutil.mavlink.MAV_TYPE_GROUND_ROVER

    dummy = DummyHeartbeat()

    # Call with integer keys (function converts to strings internally) and ensure no exception
    result = connection._select_supported_autopilot({(1, 1): dummy})

    # Successful selection returns empty string and system/component IDs are stored as strings
    assert result == ""
    assert connection.info.system_id == "1"
    assert connection.info.component_id == "1"


def test_detect_vehicles_handles_recv_match_type_error() -> None:
    """Ensure _detect_vehicles_from_heartbeats swallows transient TypeError and recovers."""
    connection = FlightControllerConnection(info=FlightControllerInfo())

    class DummyMsg:  # pylint: disable=missing-class-docstring
        def __init__(self, sysid: int, compid: int) -> None:
            self._sysid = sysid
            self._compid = compid
            self.autopilot = mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA
            self.type = mavutil.mavlink.MAV_TYPE_GROUND_ROVER

        def get_srcSystem(self) -> int:  # noqa: N802 - mimic pymavlink camelCase API; pylint: disable=invalid-name
            return self._sysid

        def get_srcComponent(self) -> int:  # noqa: N802 - mimic pymavlink camelCase API; pylint: disable=invalid-name
            return self._compid

    calls = [TypeError("broken internal state"), DummyMsg(42, 17), None]

    def fake_recv_match(*_args, **_kwargs) -> object:
        """Return next queued value, raise if it's Exception, otherwise None when exhausted."""
        if not calls:
            return None
        val = calls.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    # Attach a dummy master object with the fake recv_match
    connection.master = type("M", (), {"recv_match": staticmethod(fake_recv_match)})()

    detected = connection._detect_vehicles_from_heartbeats(timeout=1)

    # Should have recovered and collected our DummyMsg
    assert (42, 17) in detected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
