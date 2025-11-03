#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_connection.py.

This file focuses on connection management behavior including port discovery,
connection establishment, heartbeat detection, and error handling.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import Mock, patch

import serial.tools.list_ports_common

from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    DEFAULT_BAUDRATE,
    SUPPORTED_BAUDRATES,
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo


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
        assert any("udp:127.0.0.1:14550" in port for port in network_ports)
        assert any("tcp:127.0.0.1:5760" in port for port in network_ports)

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
        connection = FlightControllerConnection(info=FlightControllerInfo())
        mock_master = Mock()
        connection.set_master_for_testing(mock_master)

        # When: Disconnect
        connection.disconnect()

        # Then: Connection closed
        assert connection.master is None
        mock_master.close.assert_called_once()

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
