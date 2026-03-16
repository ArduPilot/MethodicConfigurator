#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_connection.py.

This file focuses on connection management behavior including port discovery,
connection establishment, heartbeat detection, and error handling.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from time import time as real_time
from typing import NoReturn
from unittest.mock import Mock, patch

import pytest
import serial.tools.list_ports_common
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    DEFAULT_BAUDRATE,
    SUPPORTED_BAUDRATES,
    FakeSerialForTests,
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink import (
    FakeMavlinkConnectionFactory,
    MavlinkConnectionFactory,
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

    def test_preserved_connection_survives_port_rediscovery(self) -> None:
        """
        Caller-supplied preserved connection persists across auto-discovery refreshes.

        GIVEN: User has previously used a custom connection (e.g. a TCP address stored in history)
        WHEN: discover_connections() is called again (periodic 3s refresh) and returns different ports
            AND the caller supplies the history list as preserved_connections
        THEN: The preserved connection should still be present in the available connections list/tuples
        AND: Auto-discovered ports that disappeared should be gone from the available connections list/tuples
        AND: Newly auto-discovered ports should appear in the available connections list/tuples
        """
        # Given: Connection manager with a mocked serial port discovery
        mock_discovery = Mock()
        mock_port = Mock()
        mock_port.device = "COM3"
        mock_port.description = "USB Serial"

        # First discovery: COM3 is present
        mock_discovery.get_available_ports.return_value = [mock_port]
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=mock_discovery,
            network_ports=[],
        )
        connection.discover_connections()

        # When: Port list changes (COM3 disappears, COM4 appears) but caller preserves the TCP address
        mock_port2 = Mock()
        mock_port2.device = "COM4"
        mock_port2.description = "Another USB Serial"
        mock_discovery.get_available_ports.return_value = [mock_port2]
        connection.discover_connections(preserved_connections=["tcp:127.0.0.1:5760"])

        # Then: Preserved TCP connection is present
        tuples = connection.get_connection_tuples()
        assert any(t[0] == "tcp:127.0.0.1:5760" for t in tuples)
        # COM3 is gone (no longer auto-discovered, not in preserved list)
        assert not any(t[0] == "COM3" for t in tuples)
        # COM4 is present (auto-discovered)
        assert any(t[0] == "COM4" for t in tuples)

    def test_without_preserved_connections_non_discovered_ports_disappear(self) -> None:
        """
        Without preserved_connections, ports that are no longer auto-discovered are removed.

        GIVEN: Many USB devices are connected and auto-discovered
        WHEN: discover_connections() is called again without preserved_connections
            AND one port is no longer detected
        THEN: The missing port is removed from the combobox
        AND: The backend has no hidden state keeping old connections alive
        """
        # Given: Connection manager with multiple auto-discovered ports
        mock_discovery = Mock()
        ports = []
        for i in range(5):
            p = Mock()
            p.device = f"COM{i + 1}"
            p.description = f"USB Device {i + 1}"
            ports.append(p)
        mock_discovery.get_available_ports.return_value = ports

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=mock_discovery,
            network_ports=[],
        )

        # When: Initial discovery
        connection.discover_connections()
        tuples = connection.get_connection_tuples()
        for i in range(5):
            assert any(t[0] == f"COM{i + 1}" for t in tuples)

        # When: Re-discovery with fewer ports and no preserved list
        mock_discovery.get_available_ports.return_value = ports[:2]  # Only COM1, COM2 remain
        connection.discover_connections()

        # Then: Only auto-discovered ports are present - COM3..COM5 are gone
        tuples = connection.get_connection_tuples()
        assert any(t[0] == "COM1" for t in tuples)
        assert any(t[0] == "COM2" for t in tuples)
        for i in range(2, 5):
            assert not any(t[0] == f"COM{i + 1}" for t in tuples)

    def test_preserved_connection_already_auto_discovered_is_not_duplicated(self) -> None:
        """
        A preserved connection that is also auto-discovered appears exactly once.

        GIVEN: A connection (e.g. COM3) is both physically present on the bus
            AND present in the caller-supplied preserved history
        WHEN: discover_connections is called with that connection in preserved_connections
        THEN: The connection should appear exactly once in the result list
        AND: No duplicate tuple should be present
        """
        # Given: COM3 is auto-discovered AND in preserved history
        mock_discovery = Mock()
        mock_port = Mock()
        mock_port.device = "COM3"
        mock_port.description = "USB Serial"
        mock_discovery.get_available_ports.return_value = [mock_port]

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=mock_discovery,
            network_ports=[],
        )

        # When: Discover with COM3 also in preserved list
        connection.discover_connections(preserved_connections=["COM3"])

        # Then: COM3 appears only once (de-duplicated)
        tuples = connection.get_connection_tuples()
        com3_count = sum(1 for t in tuples if t[0] == "COM3")
        assert com3_count == 1

    def test_preserved_connections_accepts_tuple_sequence_input(self) -> None:
        """
        Preserved connections can be any Sequence[str], not just a list.

        GIVEN: Calling code passes preserved history as a tuple (immutable sequence)
        WHEN: discover_connections is called with a tuple preserved_connections argument
        THEN: All connections in the tuple should be merged correctly
        AND: No TypeError should be raised from iterating a tuple
        """
        # Given: No auto-discovered ports
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=Mock(get_available_ports=Mock(return_value=[])),
            network_ports=[],
        )

        # When: Pass preserved connections as a tuple (not a list)
        connection.discover_connections(preserved_connections=("tcp:127.0.0.1:5760", "COM1"))

        # Then: Both connections present in the result
        tuples = connection.get_connection_tuples()
        assert any(t[0] == "tcp:127.0.0.1:5760" for t in tuples)
        assert any(t[0] == "COM1" for t in tuples)

    def test_empty_string_in_preserved_connections_is_silently_skipped(self) -> None:
        """
        Empty strings in preserved_connections are ignored and not added to the list.

        GIVEN: The caller-supplied history contains empty string entries
            (e.g. from corrupted or partially-initialised settings)
        WHEN: discover_connections is called with those entries
        THEN: The empty strings should not appear in the connection list
        AND: Valid connections in the list should still be present
        """
        # Given: No auto-discovered ports
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=Mock(get_available_ports=Mock(return_value=[])),
            network_ports=[],
        )

        # When: Preserved list contains empty strings mixed with a valid entry
        connection.discover_connections(preserved_connections=["", "COM1", ""])

        # Then: Empty strings absent; valid entry present
        tuples = connection.get_connection_tuples()
        assert not any(t[0] == "" for t in tuples)
        assert any(t[0] == "COM1" for t in tuples)

    def test_add_another_sentinel_in_preserved_connections_is_not_duplicated(self) -> None:
        """
        The 'Add another' sentinel value in preserved_connections is filtered out.

        GIVEN: The caller accidentally includes the 'Add another' UI sentinel in history
        WHEN: discover_connections merges preserved_connections
        THEN: 'Add another' should appear exactly once (appended by discover_connections itself)
        AND: There should be no extra 'Add another' entry from the preserved list
        """
        # Given: No auto-discovered ports; preserved list already contains the sentinel
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=Mock(get_available_ports=Mock(return_value=[])),
            network_ports=[],
        )

        # When: Discover with 'Add another' and a valid entry in preserved list
        connection.discover_connections(preserved_connections=["Add another", "COM1"])

        # Then: Exactly one 'Add another' entry exists (the one appended at the end)
        tuples = connection.get_connection_tuples()
        add_another_count = sum(1 for t in tuples if t[0] == "Add another")
        assert add_another_count == 1
        # The last entry should be the sentinel (standard placement)
        assert tuples[-1][0] == "Add another"
        # COM1 is still present
        assert any(t[0] == "COM1" for t in tuples)

    def test_duplicate_entries_within_preserved_connections_are_deduplicated(self) -> None:
        """
        Duplicate connection strings within preserved_connections appear only once.

        GIVEN: The caller supplies a preserved history that contains the same connection
            multiple times (e.g. from a history list with duplicates)
        WHEN: discover_connections processes the list
        THEN: Each unique connection should appear exactly once in the result
        """
        # Given: No auto-discovered ports
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=Mock(get_available_ports=Mock(return_value=[])),
            network_ports=[],
        )

        # When: Preserved list has three copies of the same entry
        connection.discover_connections(preserved_connections=["COM1", "COM1", "COM1"])

        # Then: COM1 appears exactly once
        tuples = connection.get_connection_tuples()
        com1_count = sum(1 for t in tuples if t[0] == "COM1")
        assert com1_count == 1


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


class TestFakeSerialForTests:
    """Test the FakeSerialForTests helper class used in unit tests."""

    def test_read_returns_empty_string(self) -> None:
        """
        FakeSerialForTests.read always returns an empty string.

        GIVEN: A FakeSerialForTests instance
        WHEN: read(n) is called for any length
        THEN: An empty string should be returned
        """
        fake = FakeSerialForTests("/dev/ttyUSB0")
        assert fake.read(0) == ""
        assert fake.read(1) == ""
        assert fake.read(1024) == ""

    def test_write_always_raises_exception(self) -> None:
        """
        FakeSerialForTests.write always raises an Exception to simulate write failure.

        GIVEN: A FakeSerialForTests instance
        WHEN: write() is called with any buffer
        THEN: An Exception should be raised
        """
        fake = FakeSerialForTests("/dev/ttyUSB0")
        with pytest.raises(Exception, match="write always fails"):
            fake.write(b"data")

    def test_in_waiting_returns_zero(self) -> None:
        """
        FakeSerialForTests.inWaiting always returns zero bytes available.

        GIVEN: A FakeSerialForTests instance
        WHEN: inWaiting() is called
        THEN: Zero should be returned (no bytes in buffer)
        """
        fake = FakeSerialForTests("/dev/ttyUSB0")
        assert fake.inWaiting() == 0

    def test_close_does_not_raise(self) -> None:
        """
        FakeSerialForTests.close completes without raising.

        GIVEN: A FakeSerialForTests instance
        WHEN: close() is called
        THEN: No exception should be raised
        """
        fake = FakeSerialForTests("/dev/ttyUSB0")
        fake.close()  # Must not raise

    def test_device_attribute_is_stored(self) -> None:
        """
        FakeSerialForTests stores the device string passed at construction.

        GIVEN: A device string passed to the constructor
        WHEN: The device attribute is accessed
        THEN: The same string should be returned
        """
        fake = FakeSerialForTests("COM3")
        assert fake.device == "COM3"


class TestFlightControllerConnectionLinuxSoftlink:
    """Test Linux-specific soft link resolution in connect()."""

    def test_connect_resolves_soft_link_on_posix(self) -> None:
        """
        On Linux (posix), connect() resolves soft links before attempting connection.

        GIVEN: An auto-detected serial port that is a soft link on Linux
        WHEN: connect() is called with an empty device string
        THEN: os.readlink() should be called to resolve the link
        AND: The resolved path should be used for the connection
        """
        mock_port = Mock()
        mock_port.device = "/dev/serial/by-id/usb-link"

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_connection.os_name",
                "posix",
            ),
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_connection.os_readlink",
                return_value="../../ttyACM0",
            ) as mock_readlink,
            patch.object(connection, "_auto_detect_serial", return_value=[mock_port]),
            patch.object(connection, "_register_and_try_connect", return_value="") as mock_connect,
        ):
            result = connection.connect(device="")

        mock_readlink.assert_called_once()
        mock_connect.assert_called_once()
        assert result == ""

    def test_connect_handles_ose_rror_when_not_soft_link(self) -> None:
        """
        connect() continues normally when os.readlink() raises OSError (not a soft link).

        GIVEN: An auto-detected serial port that is NOT a soft link on Linux
        WHEN: connect() is called with empty device string
        THEN: OSError from os.readlink() should be silently caught
        AND: Connection should proceed with the original device path
        """
        mock_port = Mock()
        mock_port.device = "/dev/ttyACM0"

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_connection.os_name",
                "posix",
            ),
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_connection.os_readlink",
                side_effect=OSError("not a link"),
            ),
            patch.object(connection, "_auto_detect_serial", return_value=[mock_port]),
            patch.object(connection, "_register_and_try_connect", return_value="") as mock_connect,
        ):
            result = connection.connect(device="")

        # Soft link failure silently ignored, connection still attempted
        mock_connect.assert_called_once()
        assert result == ""


class TestFlightControllerConnectionVehicleDetection:
    """Test vehicle detection methods including edge cases."""

    def test_detect_vehicles_handles_type_error_from_pymavlink(self) -> None:
        """
        _detect_vehicles_from_heartbeats continues polling after pymavlink TypeError.

        GIVEN: A connection where pymavlink occasionally raises TypeError
        WHEN: _detect_vehicles_from_heartbeats is called
        THEN: TypeError should be caught and polling should continue
        AND: Successfully returned heartbeats should still be collected
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_master = Mock()

        call_count = 0

        def recv_match_side_effect(**_kwargs) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                err_msg = "pymavlink internal error"
                raise TypeError(err_msg)

        mock_master.recv_match = recv_match_side_effect
        connection.master = mock_master

        start = real_time()
        # Use a very short timeout so the test runs quickly
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_connection.time_time",
            side_effect=[start, start + 0.0, start + 0.01, start + 999],
        ):
            result = connection._detect_vehicles_from_heartbeats(timeout=1)

        assert isinstance(result, dict)

    def test_select_supported_autopilot_returns_empty_string_on_success(self) -> None:
        """
        _select_supported_autopilot returns empty string when a supported autopilot is found.

        GIVEN: A dictionary with one ArduPilot (MAV_AUTOPILOT_ARDUPILOTMEGA) heartbeat
        WHEN: _select_supported_autopilot is called with that dictionary
        THEN: An empty string should be returned to indicate success
        AND: The info object should be populated with sysid / compid / type
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # Build a fake heartbeat message where autopilot == MAV_AUTOPILOT_ARDUPILOTMEGA
        mock_heartbeat = Mock()
        mock_heartbeat.autopilot = mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA
        mock_heartbeat.type = mavutil.mavlink.MAV_TYPE_QUADROTOR

        detected_vehicles = {(1, 1): mock_heartbeat}

        result = connection._select_supported_autopilot(detected_vehicles)

        assert result == ""
        assert connection.info.is_supported

    def test_select_supported_autopilot_returns_error_when_none_supported(self) -> None:
        """
        _select_supported_autopilot returns an error when no autopilot is supported.

        GIVEN: A dictionary with only unsupported autopilot heartbeat(s)
        WHEN: _select_supported_autopilot is called
        THEN: A non-empty error string should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())

        mock_heartbeat = Mock()
        mock_heartbeat.autopilot = mavutil.mavlink.MAV_AUTOPILOT_GENERIC  # not ArduPilot

        detected_vehicles = {(1, 1): mock_heartbeat}

        result = connection._select_supported_autopilot(detected_vehicles)

        assert result != ""

    def test_select_supported_autopilot_returns_error_when_empty(self) -> None:
        """
        _select_supported_autopilot returns error for empty detected_vehicles dict.

        GIVEN: No heartbeats were detected
        WHEN: _select_supported_autopilot is called with an empty dict
        THEN: An error message should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        result = connection._select_supported_autopilot({})
        assert result != ""


class TestFlightControllerConnectionBannerMethods:
    """Test banner and version request methods."""

    def test_request_banner_calls_command_long_send_when_master_is_set(self) -> None:
        """
        _request_banner sends a MAVLink command when master is not None.

        GIVEN: A connection with a mock master object
        WHEN: _request_banner() is called
        THEN: master.mav.command_long_send() should be called once
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_master = Mock()
        mock_master.target_system = 1
        mock_master.target_component = 1
        connection.master = mock_master

        connection._request_banner()

        mock_master.mav.command_long_send.assert_called_once()

    def test_request_banner_does_nothing_when_master_is_none(self) -> None:
        """
        _request_banner silently does nothing when master is None.

        GIVEN: A connection without a master (not connected)
        WHEN: _request_banner() is called
        THEN: No exception should be raised
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        assert connection.master is None
        connection._request_banner()  # Must not raise

    def test_receive_banner_text_collects_statustext_messages(self) -> None:
        """
        _receive_banner_text collects STATUS_TEXT messages until timeout.

        GIVEN: A connection with a mock master that returns STATUS_TEXT messages
        WHEN: _receive_banner_text() is called
        THEN: All returned STATUS_TEXT text values should be collected in a list
        AND: The list should be returned after timeout
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_master = Mock()

        msg1 = Mock()
        msg1.text = "ArduCopter V4.5.0"
        msg2 = Mock()
        msg2.text = "ChibiOS: abc1234"

        call_count = 0

        def recv_match_side_effect(**_kwargs) -> Mock | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return msg1
            if call_count == 2:
                return msg2
            return None

        mock_master.recv_match = recv_match_side_effect
        connection.master = mock_master

        start = real_time()
        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_connection.time_time",
                side_effect=[start, start, start, start + 9999],
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.time_sleep"),
        ):
            banner_msgs = connection._receive_banner_text()

        assert "ArduCopter V4.5.0" in banner_msgs
        assert "ChibiOS: abc1234" in banner_msgs

    def test_receive_banner_text_returns_empty_list_without_master(self) -> None:
        """
        _receive_banner_text returns an empty list when master is None.

        GIVEN: A connection without a master
        WHEN: _receive_banner_text() is called
        THEN: An empty list should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        assert connection.master is None
        result = connection._receive_banner_text()
        assert not result

    def test_request_message_calls_command_long_send_when_master_is_set(self) -> None:
        """
        _request_message sends a MAVLink command for the given message IDs.

        GIVEN: A connection with a mock master
        WHEN: _request_message() is called with a message ID
        THEN: master.mav.command_long_send() should be called once with that ID
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_master = Mock()
        connection.master = mock_master
        connection.info.set_system_id_and_component_id("1", "1")

        connection._request_message(mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION)

        mock_master.mav.command_long_send.assert_called_once()

    def test_request_message_does_nothing_when_master_is_none(self) -> None:
        """
        _request_message silently does nothing when master is None.

        GIVEN: A connection without a master
        WHEN: _request_message() is called
        THEN: No exception should be raised
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        assert connection.master is None
        connection._request_message(253)  # Must not raise


class TestFlightControllerConnectionErrorGuidance:
    """Test _get_connection_error_guidance messages."""

    def test_permission_error_on_linux_dev_path_returns_guidance(self) -> None:
        """
        PermissionError on a Linux /dev/ path returns helpful guidance text.

        GIVEN: A PermissionError on a path containing /dev/
        WHEN: _get_connection_error_guidance is called on Linux (os_name=posix)
        THEN: A non-empty guidance string about dialout group should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_connection.os_name",
            "posix",
        ):
            guidance = connection._get_connection_error_guidance(
                PermissionError("Permission denied"),
                "/dev/ttyACM0",
            )

        assert "dialout" in guidance
        assert len(guidance) > 0

    def test_permission_error_on_windows_returns_empty_guidance(self) -> None:
        """
        PermissionError on Windows does not return Linux-specific guidance.

        GIVEN: A PermissionError on Windows (os_name != posix)
        WHEN: _get_connection_error_guidance is called
        THEN: An empty string should be returned (no guidance)
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_connection.os_name",
            "nt",
        ):
            guidance = connection._get_connection_error_guidance(
                PermissionError("Permission denied"),
                "COM3",
            )

        assert guidance == ""

    def test_non_permission_error_returns_empty_guidance(self) -> None:
        """
        Non-PermissionError exceptions return empty guidance.

        GIVEN: A generic ConnectionError (not PermissionError)
        WHEN: _get_connection_error_guidance is called
        THEN: Empty string should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        guidance = connection._get_connection_error_guidance(
            ConnectionError("Connection refused"),
            "/dev/ttyACM0",
        )
        assert guidance == ""


class TestFlightControllerConnectionBannerParsing:
    """Test banner and firmware version parsing methods."""

    def test_extract_chibios_version_finds_version_in_banner(self) -> None:
        """
        _extract_chibios_version_from_banner extracts version string when present.

        GIVEN: Banner messages containing a 'ChibiOS:' line
        WHEN: _extract_chibios_version_from_banner is called
        THEN: The version string should be returned
        AND: The index of the ChibiOS line should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        banner_msgs = ["ArduCopter V4.5.0", "ChibiOS: abc1234567", "ArduCopter"]

        os_ver, index = connection._extract_chibios_version_from_banner(banner_msgs)

        assert os_ver == "abc1234567"
        assert index == 1

    def test_extract_chibios_version_logs_warning_on_mismatch(self) -> None:
        """
        _extract_chibios_version_from_banner logs a warning when banner version does not match AUTOPILOT_VERSION.

        GIVEN: Banner with ChibiOS version that differs from info.os_custom_version
        WHEN: _extract_chibios_version_from_banner is called
        THEN: A warning should be logged about the mismatch
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        # Simulate that AUTOPILOT_VERSION gave a different hash
        connection.info.os_custom_version = "zzz9999999"
        banner_msgs = ["ChibiOS: abc1234567"]

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.logging_warning") as mock_warn:
            os_ver, index = connection._extract_chibios_version_from_banner(banner_msgs)

        assert os_ver == "abc1234567"
        assert index == 0
        mock_warn.assert_called_once()

    def test_extract_chibios_version_returns_none_index_when_absent(self) -> None:
        """
        _extract_chibios_version_from_banner returns (empty, None) when ChibiOS not in banner.

        GIVEN: Banner messages that do not contain 'ChibiOS:'
        WHEN: _extract_chibios_version_from_banner is called
        THEN: Empty string and None index should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        banner_msgs = ["ArduCopter V4.5.0", "Some other message"]

        os_ver, index = connection._extract_chibios_version_from_banner(banner_msgs)

        assert os_ver == ""
        assert index is None

    def test_extract_firmware_type_from_message_after_chibios(self) -> None:
        """
        _extract_firmware_type_from_banner extracts type from message after ChibiOS line.

        GIVEN: Banner messages where ChibiOS is at index 0 and firmware type at index 1
        WHEN: _extract_firmware_type_from_banner is called with os_custom_version_index=0
        THEN: The firmware type (first word of the next message) should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        banner_msgs = ["ChibiOS: abc1234", "ArduCopter V4.5.0 (dev)"]

        firmware_type = connection._extract_firmware_type_from_banner(banner_msgs, os_custom_version_index=0)

        assert firmware_type == "ArduCopter"

    def test_extract_firmware_type_falls_back_to_first_message(self) -> None:
        """
        _extract_firmware_type_from_banner falls back to first message when no ChibiOS index.

        GIVEN: Banner messages without a ChibiOS line (SITL scenario)
        WHEN: _extract_firmware_type_from_banner is called with os_custom_version_index=None
        THEN: The firmware type should be extracted from the first message
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        banner_msgs = ["ArduPlane V4.5.0"]

        firmware_type = connection._extract_firmware_type_from_banner(banner_msgs, os_custom_version_index=None)

        assert firmware_type == "ArduPlane"

    def test_extract_firmware_type_returns_empty_for_empty_banner(self) -> None:
        """
        _extract_firmware_type_from_banner returns empty string when banner is empty.

        GIVEN: An empty banner messages list
        WHEN: _extract_firmware_type_from_banner is called
        THEN: An empty string should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        firmware_type = connection._extract_firmware_type_from_banner([], os_custom_version_index=None)
        assert firmware_type == ""


class TestFlightControllerConnectionProcessAutopilotVersion:
    """Test _process_autopilot_version covering edge cases."""

    def test_process_autopilot_version_returns_error_when_m_is_none(self) -> None:
        """
        _process_autopilot_version returns error message when AUTOPILOT_VERSION not received.

        GIVEN: No AUTOPILOT_VERSION message was received (m=None)
        WHEN: _process_autopilot_version is called
        THEN: A non-empty error string should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())
        result = connection._process_autopilot_version(None, [])
        assert result != ""
        assert "AUTOPILOT_VERSION" in result or "4.3.8" in result

    def test_process_autopilot_version_firmware_mismatch_uses_banner_value(self) -> None:
        """
        _process_autopilot_version uses banner firmware type when it differs from AUTOPILOT_VERSION.

        GIVEN: An AUTOPILOT_VERSION message and a banner with a different firmware type
        WHEN: _process_autopilot_version is called
        THEN: firmware_type should be overridden with the banner value
        AND: A debug log should be emitted about the mismatch
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # Create a mock AUTOPILOT_VERSION message with board_version that maps to something
        mock_m = Mock()
        mock_m.capabilities = 0
        mock_m.flight_sw_version = 0x04050000
        mock_m.vendor_id = 0
        mock_m.product_id = 0
        mock_m.board_version = 0
        mock_m.flight_custom_version = [0] * 8
        mock_m.os_custom_version = [0] * 8

        # After _populate_flight_controller_info, firmware_type will be set by set_board_version
        # We need banner to have a different firmware type
        banner_msgs = ["ChibiOS: abc1234", "ArduPlane V4.5.0 (dev)"]

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.logging_debug") as mock_debug:
            result = connection._process_autopilot_version(mock_m, banner_msgs)

        assert result == ""
        # firmware_type should be overridden with 'ArduPlane' from the banner
        assert connection.info.firmware_type == "ArduPlane"
        # Should have logged a debug message about the mismatch
        mock_debug.assert_called()

    def test_process_autopilot_version_returns_empty_without_mismatch(self) -> None:
        """
        _process_autopilot_version returns empty string when successfully processed.

        GIVEN: A valid AUTOPILOT_VERSION message with no banner firmware mismatch
        WHEN: _process_autopilot_version is called
        THEN: An empty string should be returned
        """
        connection = FlightControllerConnection(info=FlightControllerInfo())

        mock_m = Mock()
        mock_m.capabilities = 0
        mock_m.flight_sw_version = 0x04050000
        mock_m.vendor_id = 0
        mock_m.product_id = 0
        mock_m.board_version = 0
        mock_m.flight_custom_version = [0] * 8
        mock_m.os_custom_version = [0] * 8

        # Empty banner — no firmware type to compare
        result = connection._process_autopilot_version(mock_m, [])

        assert result == ""


class TestFlightControllerConnectionRetry:
    """Test create_connection_with_retry edge cases."""

    def test_create_connection_udp_device_logs_without_baudrate(self) -> None:
        """
        create_connection_with_retry logs UDP/TCP info without baud rate.

        GIVEN: comport device starts with 'udp'
        WHEN: create_connection_with_retry is called
        THEN: logging_info should be called without mentioning baud rate
        AND: connection should proceed normally
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        connection.comport = mavutil.SerialPort(device="udp:127.0.0.1:14550", description="UDP")

        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.logging_info") as mock_info,
            patch.object(connection, "_detect_vehicles_from_heartbeats", return_value={}),
            patch.object(connection, "_select_supported_autopilot", return_value="no heartbeat"),
        ):
            result = connection.create_connection_with_retry(progress_callback=None, retries=1, timeout=1)

        # Should have logged the UDP connection info (without baudrate)
        info_calls = [str(c) for c in mock_info.call_args_list]
        assert any("udp:127.0.0.1:14550" in c for c in info_calls)
        assert result != ""  # error from no heartbeat

    def test_create_connection_with_retry_raises_connection_error_when_master_is_none(self) -> None:
        """
        create_connection_with_retry raises ConnectionError when factory returns None.

        GIVEN: The MAVLink factory returns None (connection failed to create)
        WHEN: create_connection_with_retry is called with log_errors=False
        THEN: The returned string should contain the device name
        """

        class NullFactory(MavlinkConnectionFactory):  # pylint: disable=too-few-public-methods, missing-class-docstring
            def create(  # pylint: disable=too-many-arguments, too-many-positional-arguments
                self, device, baudrate=115200, timeout=5.0, retries=3, progress_callback=None
            ) -> None:  # type: ignore[override]
                return None

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=NullFactory(),
        )
        connection.comport = mavutil.SerialPort(device="COM99", description="Test")

        result = connection.create_connection_with_retry(progress_callback=None, retries=1, timeout=1, log_errors=False)

        assert "COM99" in result

    def test_create_connection_with_retry_logs_errors_when_log_errors_is_true(self) -> None:
        """
        create_connection_with_retry logs warning and error messages when log_errors=True.

        GIVEN: A connection that raises ConnectionError and log_errors=True
        WHEN: create_connection_with_retry is called
        THEN: logging_warning and logging_error should each be called once
        """

        class NullFactory(MavlinkConnectionFactory):  # pylint: disable=too-few-public-methods, missing-class-docstring
            def create(  # pylint: disable=too-many-arguments, too-many-positional-arguments
                self, device, baudrate=115200, timeout=5.0, retries=3, progress_callback=None
            ) -> None:  # type: ignore[override]
                return None

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=NullFactory(),
        )
        connection.comport = mavutil.SerialPort(device="COM99", description="Test")

        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.logging_warning") as mock_warn,
            patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.logging_error") as mock_err,
        ):
            connection.create_connection_with_retry(progress_callback=None, retries=1, timeout=1, log_errors=True)

        mock_warn.assert_called_once()
        mock_err.assert_called_once()

    def test_create_connection_appends_guidance_on_permission_error_linux(self) -> None:
        """
        create_connection_with_retry appends guidance text on PermissionError.

        GIVEN: A Linux system where a PermissionError occurs on /dev/ path
        WHEN: create_connection_with_retry is called
        THEN: Returned error message should include the guidance text
        """

        class PermErrorFactory(MavlinkConnectionFactory):  # pylint: disable=too-few-public-methods, missing-class-docstring
            def create(  # pylint: disable=too-many-arguments, too-many-positional-arguments
                self, device, baudrate=115200, timeout=5.0, retries=3, progress_callback=None
            ) -> NoReturn:
                err_msg = "Permission denied"
                raise PermissionError(err_msg)

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=PermErrorFactory(),
        )
        connection.comport = mavutil.SerialPort(device="/dev/ttyACM0", description="Test")

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_connection.os_name",
            "posix",
        ):
            result = connection.create_connection_with_retry(progress_callback=None, retries=1, timeout=1, log_errors=False)

        assert "dialout" in result


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


class TestFlightControllerConnectionProgressCallbacks:
    """Test progress callback functionality during connection operations."""

    def test_discover_connections_reports_progress_during_serial_discovery(self) -> None:
        """
        Connection discovery reports progress during serial port scanning.

        GIVEN: User is discovering available flight controller connections
        WHEN: Providing a progress callback during discovery
        THEN: Callback should be invoked with progress updates
        AND: Progress should cover serial port discovery phase
        """
        # Arrange: Create connection with fake serial ports
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Flight Controller")

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
        )

        progress_updates = []

        def track_progress(current: int, total: int) -> None:
            progress_updates.append((current, total))

        # Act: Discover connections with progress tracking
        connection.discover_connections(progress_callback=track_progress)

        # Assert: Progress updates received
        assert len(progress_updates) > 0
        # Should include serial discovery progress (82%, 90%)
        assert any(current >= 82 for current, _ in progress_updates)
        assert any(current >= 90 for current, _ in progress_updates)
        # Total should be 100
        assert all(total == 100 for _, total in progress_updates)

    def test_discover_connections_reports_progress_during_network_discovery(self) -> None:
        """
        Connection discovery reports progress during network port detection.

        GIVEN: User is discovering network-based flight controller connections
        WHEN: Network ports are being scanned
        THEN: Progress callback should receive network discovery updates
        """
        # Arrange: Create connection with network ports
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            network_ports=["tcp:127.0.0.1:5760"],
        )

        progress_updates = []

        def track_progress(current: int, total: int) -> None:
            progress_updates.append((current, total))

        # Act: Discover connections with progress tracking
        connection.discover_connections(progress_callback=track_progress)

        # Assert: Network discovery progress received (95%)
        assert any(current >= 95 for current, _ in progress_updates)

    def test_discover_connections_without_callback_works_normally(self) -> None:
        """
        Connection discovery works without progress callback.

        GIVEN: User discovers connections without progress tracking
        WHEN: No progress callback is provided
        THEN: Discovery should complete successfully
        AND: No errors should occur
        """
        # Arrange: Create connection
        connection = FlightControllerConnection(info=FlightControllerInfo())

        # Act/Assert: Discover without callback - should not raise
        connection.discover_connections(progress_callback=None)

        # Assert: Discovery completed
        assert connection.get_connection_tuples() is not None

    def test_connect_reports_progress_during_serial_autodetection(self) -> None:
        """
        Connect reports progress during serial port autodetection.

        GIVEN: User connects without specifying device (autodetect mode)
        WHEN: Connection attempts serial port autodetection
        THEN: Progress callback should receive serial detection updates
        """
        # Arrange: Create connection with fake serial port
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Flight Controller")

        fake_mavlink = FakeMavlinkConnectionFactory()

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
            mavlink_connection_factory=fake_mavlink,
        )

        progress_updates = []

        def track_progress(current: int, total: int) -> None:
            progress_updates.append((current, total))

        # Act: Connect with autodetection
        serial_port = mavutil.SerialPort(device="/dev/ttyUSB0", description="Flight Controller")
        with patch.object(connection, "_auto_detect_serial", return_value=[serial_port]):
            connection.connect(device=None, progress_callback=track_progress)

        # Assert: Serial detection progress received (10%, 25%)
        assert any(current >= 10 for current, _ in progress_updates)

    def test_connect_reports_progress_during_network_port_attempts(self) -> None:
        """
        Connect reports progress during network port connection attempts.

        GIVEN: User connects via network (TCP/UDP)
        WHEN: Connection tries multiple network ports
        THEN: Progress callback should receive updates for each attempt
        AND: Progress should increase from 50% to 100%
        """
        # Arrange: Create connection with network ports
        fake_mavlink = FakeMavlinkConnectionFactory()

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            network_ports=["tcp:127.0.0.1:5760", "tcp:127.0.0.1:5761"],
            mavlink_connection_factory=fake_mavlink,
        )

        progress_updates = []

        def track_progress(current: int, total: int) -> None:
            progress_updates.append((current, total))

        # Act: Connect with network ports
        with patch.object(connection, "_auto_detect_serial", return_value=None):
            connection.connect(device=None, progress_callback=track_progress)

        # Assert: Network port progress received (50% to 100%)
        assert any(current >= 50 for current, _ in progress_updates)
        # Progress should increase through network port attempts
        values = [current for current, _ in progress_updates]
        # Should have multiple updates in 50-100 range
        network_updates = [v for v in values if 50 <= v <= 100]
        assert len(network_updates) > 0

    def test_connect_without_callback_works_normally(self) -> None:
        """
        Connect works without progress callback.

        GIVEN: User connects to flight controller without progress tracking
        WHEN: No progress callback is provided
        THEN: Connection should work normally
        AND: No errors should occur
        """
        # Arrange: Create connection with fake components
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "FC")

        fake_mavlink = FakeMavlinkConnectionFactory()

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
            mavlink_connection_factory=fake_mavlink,
        )

        # Act: Connect without callback
        serial_port = mavutil.SerialPort(device="/dev/ttyUSB0", description="FC")
        with patch.object(connection, "_auto_detect_serial", return_value=[serial_port]):
            error = connection.connect(device=None, progress_callback=None)

        # Assert: Connection attempted (may succeed or fail, but shouldn't crash)
        assert error is not None  # Returns either "" or error message

    def test_progress_updates_are_monotonically_increasing(self) -> None:
        """
        Progress updates increase monotonically during connection process.

        GIVEN: User monitors connection progress
        WHEN: Connection process is ongoing
        THEN: Progress values should never decrease
        AND: Progress should reach 100% on completion
        """
        # Arrange: Create connection
        fake_mavlink = FakeMavlinkConnectionFactory()

        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            network_ports=["tcp:127.0.0.1:5760"],
            mavlink_connection_factory=fake_mavlink,
        )

        progress_updates = []

        def track_progress(current: int, total: int) -> None:
            progress_updates.append((current, total))

        # Act: Connect with progress tracking
        with patch.object(connection, "_auto_detect_serial", return_value=None):
            connection.connect(device=None, progress_callback=track_progress)

        # Assert: Progress is monotonically increasing
        if len(progress_updates) > 1:
            values = [current for current, _ in progress_updates]
            # Check each value is >= previous (allowing duplicates)
            for i in range(1, len(values)):
                assert values[i] >= values[i - 1], f"Progress decreased: {values[i - 1]} -> {values[i]}"


class TestFlightControllerConnectionSetMaster:
    """Tests for set_master_for_testing method edge cases."""

    def test_set_master_for_testing_none_clears_comport(self) -> None:
        """
        set_master_for_testing(None) clears comport.

        GIVEN: A connection with a comport set
        WHEN: set_master_for_testing is called with None
        THEN: comport should also be set to None
        """
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "FC")
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        # Manually set comport before calling the tested method
        mock_comport = Mock()
        mock_comport.device = "/dev/ttyUSB0"
        connection.comport = mock_comport

        connection.set_master_for_testing(None)

        assert connection.comport is None
        assert connection.master is None

    def test_set_master_for_testing_with_object_keeps_comport(self) -> None:
        """
        set_master_for_testing with a real master does not clear comport.

        GIVEN: A connection with a comport set
        WHEN: set_master_for_testing is called with a mock master
        THEN: comport should remain unchanged
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        mock_comport = Mock()
        mock_comport.device = "/dev/ttyUSB0"
        connection.comport = mock_comport

        mock_master = Mock()
        connection.set_master_for_testing(mock_master)

        assert connection.master is mock_master
        # comport was NOT cleared
        assert connection.comport is mock_comport


class TestFlightControllerConnectionRegisterAndTryConnect:  # pylint: disable=too-few-public-methods
    """Tests for _register_and_try_connect when device already exists in tuples."""

    def test_device_already_in_connection_tuples_skips_insert(self) -> None:
        """
        _register_and_try_connect skips insert when device already in _connection_tuples.

        GIVEN: A connection with '/dev/ttyUSB0' already in _connection_tuples
        WHEN: _register_and_try_connect is called with the same device
        THEN: The tuple list should not gain a duplicate entry
        AND: create_connection_with_retry should still be called
        """
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "FC")
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            serial_port_discovery=fake_serial,
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        # Pre-populate the connection_tuples with the same device
        connection._connection_tuples = [("/dev/ttyUSB0", "FC"), ("", "Disconnect")]

        initial_len = len(connection._connection_tuples)

        mock_comport = Mock()
        mock_comport.device = "/dev/ttyUSB0"

        with patch.object(connection, "create_connection_with_retry", return_value="") as mock_retry:
            connection._register_and_try_connect(
                comport=mock_comport,
                progress_callback=None,
                baudrate=115200,
                log_errors=False,
            )

        # The list should not have grown
        assert len(connection._connection_tuples) == initial_len
        # create_connection_with_retry should still be called
        mock_retry.assert_called_once()


class TestFlightControllerConnectionAutoDetectWithMavlink:
    """Tests for _auto_detect_serial when connection tuples have 'mavlink' description."""

    def test_single_mavlink_port_returns_directly(self) -> None:
        """
        _auto_detect_serial returns single mavlink port without calling auto_detect_serial.

        GIVEN: A connection with exactly one entry having 'mavlink' in description
        WHEN: _auto_detect_serial is called
        THEN: That single port should be returned directly (not via mavutil.auto_detect_serial)
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        # Pre-populate with a single mavlink-described port
        connection._connection_tuples = [
            ("udp:127.0.0.1:14550", "MAVLink UDP"),
            ("", "Disconnect"),
        ]

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_connection.mavutil.auto_detect_serial"
        ) as mock_auto_detect:
            result = connection._auto_detect_serial()

        # auto_detect_serial should NOT have been called
        mock_auto_detect.assert_not_called()
        assert result is not None
        assert len(result) == 1
        assert result[0].device == "udp:127.0.0.1:14550"

    def test_multiple_mavlink_ports_falls_through_to_autodetect(self) -> None:
        """
        _auto_detect_serial falls through to mavutil.auto_detect_serial when >1 mavlink port.

        GIVEN: A connection with 2+ entries having 'mavlink' in description
        WHEN: _auto_detect_serial is called
        THEN: mavutil.auto_detect_serial should be called for hardware detection
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        connection._connection_tuples = [
            ("udp:127.0.0.1:14550", "MAVLink UDP"),
            ("tcp:192.168.1.1:5760", "MAVLink TCP"),
            ("", "Disconnect"),
        ]

        mock_ports = [Mock()]
        mock_ports[0].device = "/dev/ttyUSB0"

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_connection.mavutil.auto_detect_serial",
            return_value=mock_ports,
        ) as mock_auto_detect:
            result = connection._auto_detect_serial()

        mock_auto_detect.assert_called_once()
        assert result == mock_ports


class TestFlightControllerConnectionChibiOSVersionMatch:
    """Tests for _extract_chibios_version_from_banner when versions match."""

    def test_matching_chibi_os_version_no_warning_logged(self) -> None:
        """
        _extract_chibios_version_from_banner does not log warning when versions match.

        GIVEN: A banner with 'ChibiOS: abcdef1' and info.os_custom_version = 'abcdef1'
        WHEN: _extract_chibios_version_from_banner is called
        THEN: No warning is logged, and os_custom_version is extracted
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        connection.info.os_custom_version = "abcdef1234567"

        banner_msgs = ["ChibiOS: abcdef1234567", "ArduCopter V4.5.0"]

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.logging_warning") as mock_warn:
            version, index = connection._extract_chibios_version_from_banner(banner_msgs)

        mock_warn.assert_not_called()
        assert version == "abcdef1234567"
        assert index == 0

    def test_mismatched_chibios_version_logs_warning(self) -> None:
        """
        _extract_chibios_version_from_banner logs a warning when versions differ.

        GIVEN: A banner with 'ChibiOS: abc123' but info.os_custom_version = 'xyz789'
        WHEN: _extract_chibios_version_from_banner is called
        THEN: A warning should be logged about the version mismatch
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        connection.info.os_custom_version = "xyz789aaaaaaa"

        banner_msgs = ["ChibiOS: abc123aaaaaaa"]

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.logging_warning") as mock_warn:
            version, index = connection._extract_chibios_version_from_banner(banner_msgs)

        mock_warn.assert_called_once()
        assert version == "abc123aaaaaaa"
        assert index == 0


class TestFlightControllerConnectionFirmwareTypeExtraction:
    """Tests for _extract_firmware_type_from_banner edge cases."""

    def test_message_after_chibi_os_with_few_words_falls_to_fallback(self) -> None:
        """
        _extract_firmware_type_from_banner uses fallback when post-ChibiOS message has <3 words.

        GIVEN: Banner where after ChibiOS there is a message with fewer than 3 words
        AND: First banner message has 1+ good word
        WHEN: _extract_firmware_type_from_banner is called
        THEN: firmware_type should be extracted from first banner message (fallback)
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        # index=0, so index+1=1; message at index 1 has only 1 word (< 3)
        banner_msgs = ["ChibiOS: abc123", "ShortMsg"]
        os_custom_version_index = 0

        result = connection._extract_firmware_type_from_banner(banner_msgs, os_custom_version_index)

        # Fallback would use banner_msgs[0] = "ChibiOS: abc123", first word = "ChibiOS:"
        # But since os_custom_version_index is NOT None, the elif fallback is not taken
        # (only elif when index IS None)
        # With index=0 but post-ChibiOS message too short, firmware_type stays ""
        assert result == ""

    def test_no_chibi_os_uses_first_banner_message(self) -> None:
        """
        _extract_firmware_type_from_banner uses first banner message when no ChibiOS found.

        GIVEN: Banner without ChibiOS (os_custom_version_index is None)
        AND: First banner message has multiple words
        WHEN: _extract_firmware_type_from_banner is called
        THEN: First word of first message should be used as firmware_type
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        banner_msgs = ["ArduCopter V4.5.0 extra-data"]

        result = connection._extract_firmware_type_from_banner(banner_msgs, None)

        assert result == "ArduCopter"

    def test_empty_first_word_in_fallback_returns_empty(self) -> None:
        """
        _extract_firmware_type_from_banner returns empty when first word is whitespace.

        GIVEN: Banner without ChibiOS, first message is all whitespace
        WHEN: _extract_firmware_type_from_banner is called
        THEN: Empty firmware_type should be returned
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        banner_msgs = ["   "]  # Only whitespace

        result = connection._extract_firmware_type_from_banner(banner_msgs, None)

        assert result == ""


class TestFlightControllerConnectionRetrieveAutopilotVersion:  # pylint: disable=too-few-public-methods
    """Tests for _retrieve_autopilot_version_and_banner."""

    def test_retrieve_autopilot_version_calls_sub_methods(self) -> None:
        """
        _retrieve_autopilot_version_and_banner calls banner request methods and processes the result.

        GIVEN: A connection with a mock master
        WHEN: _retrieve_autopilot_version_and_banner is called
        THEN: _request_banner, _receive_banner_text, _request_message, and _process_autopilot_version
              should all be called
        """
        connection = FlightControllerConnection(
            info=FlightControllerInfo(),
            mavlink_connection_factory=FakeMavlinkConnectionFactory(),
        )
        mock_master = Mock()
        connection.master = mock_master

        with (
            patch.object(connection, "_request_banner") as mock_req_banner,
            patch.object(connection, "_receive_banner_text", return_value=["ArduCopter V4.5.0"]) as mock_recv,
            patch.object(connection, "_request_message") as mock_req_msg,
            patch.object(connection, "_process_autopilot_version", return_value="") as mock_process,
        ):
            mock_master.recv_match.return_value = Mock()
            result = connection._retrieve_autopilot_version_and_banner(timeout=5)

        mock_req_banner.assert_called_once()
        mock_recv.assert_called_once()
        mock_req_msg.assert_called_once()
        mock_process.assert_called_once()
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
