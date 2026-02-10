#!/usr/bin/env python3

"""
BDD-style tests for dependency injection services SerialPortDiscovery.

These tests verify the injectable services for testability, demonstrating how to use fake
implementations in production code for better test isolation and no external dependencies.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_serial import (
    FakeSerialPortDiscovery,
    SystemSerialPortDiscovery,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import (
    FlightControllerInfo,
)

# pylint: disable=protected-access


class TestSerialPortDiscoveryService:
    """Test serial port discovery service abstraction."""

    def test_system_serial_discovery_defaults_when_none_provided(self) -> None:
        """
        System serial discovery is used when no discovery service provided.

        GIVEN: FlightControllerConnection without explicit serial discovery
        WHEN: Connection initializes
        THEN: SystemSerialPortDiscovery should be the default
        """
        # Given: Create connection without service
        info = FlightControllerInfo()
        connection = FlightControllerConnection(info=info)

        # Then: Default system service is used
        assert isinstance(connection._serial_port_discovery, SystemSerialPortDiscovery)

    def test_fake_serial_discovery_can_be_injected(self) -> None:
        """
        Custom serial discovery service can be injected for testing.

        GIVEN: Developer wants to test without real hardware
        WHEN: Injecting FakeSerialPortDiscovery
        THEN: Connection should use the injected fake service
        """
        # Given: Create fake discovery service
        fake_serial = FakeSerialPortDiscovery()

        # When: Inject into connection
        info = FlightControllerInfo()
        connection = FlightControllerConnection(
            info=info,
            serial_port_discovery=fake_serial,
        )

        # Then: Injected service is used
        assert connection._serial_port_discovery is fake_serial

    def test_user_discovers_fake_serial_ports(self) -> None:
        """
        User can discover ports from fake serial discovery.

        GIVEN: Fake serial discovery with test ports
        WHEN: User calls discover_connections
        THEN: Fake ports should appear in available connections
        """
        # Given: Fake discovery with ports
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "Test Flight Controller")
        fake_serial.add_port("/dev/ttyUSB1", "Another Controller")

        info = FlightControllerInfo()
        connection = FlightControllerConnection(
            info=info,
            serial_port_discovery=fake_serial,
        )

        # When: Discover connections
        connection.discover_connections()

        # Then: Fake ports should be discoverable
        connection_devices = [conn[0] for conn in connection._connection_tuples]
        assert "/dev/ttyUSB0" in connection_devices
        assert "/dev/ttyUSB1" in connection_devices
        assert any("Test Flight Controller" in conn[1] for conn in connection._connection_tuples)

    def test_fake_serial_discovery_supports_port_management(self) -> None:
        """
        Fake serial discovery supports adding and clearing ports between tests.

        GIVEN: Fake serial discovery service
        WHEN: Adding and clearing ports
        THEN: Port list should be properly managed
        """
        # Given: Empty fake discovery
        fake_serial = FakeSerialPortDiscovery()
        assert len(fake_serial.get_available_ports()) == 0

        # When: Add ports
        fake_serial.add_port("/dev/ttyUSB0", "Port 1")
        fake_serial.add_port("/dev/ttyUSB1", "Port 2")

        # Then: Ports are added
        assert len(fake_serial.get_available_ports()) == 2

        # When: Clear ports
        fake_serial.clear_ports()

        # Then: Ports are cleared
        assert len(fake_serial.get_available_ports()) == 0

    def test_fake_serial_discovery_returns_port_description_when_found(self) -> None:
        """
        Fake serial discovery returns correct description when port is found.

        GIVEN: Fake discovery with a known port
        WHEN: Getting description for that port
        THEN: Should return the configured description
        """
        # Given: Fake discovery with a port
        fake_serial = FakeSerialPortDiscovery()
        fake_serial.add_port("/dev/ttyUSB0", "My Test Controller", "MyManufacturer")

        # When: Get description for known port
        description = fake_serial.get_port_description("/dev/ttyUSB0")

        # Then: Should return configured description
        assert description == "My Test Controller"

    def test_fake_serial_discovery_returns_default_description_when_not_found(self) -> None:
        """
        Fake serial discovery returns default description when port not found.

        GIVEN: Fake discovery without specific port
        WHEN: Getting description for unknown port
        THEN: Should return default description with device name
        """
        # Given: Empty fake discovery
        fake_serial = FakeSerialPortDiscovery()

        # When: Get description for unknown port
        description = fake_serial.get_port_description("/dev/unknown")

        # Then: Should return default description
        assert "unknown" in description
        assert "Test Port" in description

    def test_system_serial_discovery_returns_available_ports(self) -> None:
        """
        System serial discovery returns list of available ports.

        GIVEN: System serial discovery service
        WHEN: Requesting available ports
        THEN: Should return a list (may be empty in test environment)
        """
        # Given: System discovery
        system_serial = SystemSerialPortDiscovery()

        # When: Get available ports
        ports = system_serial.get_available_ports()

        # Then: Should return a list
        assert isinstance(ports, list)

    def test_system_serial_discovery_returns_port_description(self) -> None:
        """
        System serial discovery returns port description or device name as fallback.

        GIVEN: System serial discovery service
        WHEN: Getting description for a port (real or fake)
        THEN: Should return string description or device as fallback
        """
        # Given: System discovery
        system_serial = SystemSerialPortDiscovery()

        # When: Get description for a port that probably doesn't exist
        description = system_serial.get_port_description("/dev/nonexistent")

        # Then: Should return the device name as fallback
        assert isinstance(description, str)
        assert description == "/dev/nonexistent"  # Falls back to device name

    def test_system_serial_discovery_finds_port_description_when_available(self) -> None:
        """
        System serial discovery finds and returns port description when port exists.

        GIVEN: System serial discovery with mocked available ports
        WHEN: Getting description for an available port
        THEN: Should return the port's description
        """
        # Given: Mock a serial port
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyACM0"
        mock_port.description = "Arduino Uno"

        # When: System discovery with mocked comports
        with patch("serial.tools.list_ports.comports", return_value=[mock_port]):
            system_serial = SystemSerialPortDiscovery()
            description = system_serial.get_port_description("/dev/ttyACM0")

        # Then: Should return the mocked description
        assert description == "Arduino Uno"

    def test_system_serial_discovery_searches_multiple_ports(self) -> None:
        """
        System serial discovery searches through multiple ports to find matching device.

        GIVEN: System serial discovery with multiple mocked ports
        WHEN: Getting description for a specific port (not first in list)
        THEN: Should find and return the correct port's description
        """
        # Given: Mock multiple serial ports
        mock_port1 = MagicMock()
        mock_port1.device = "/dev/ttyUSB0"
        mock_port1.description = "USB Serial"

        mock_port2 = MagicMock()
        mock_port2.device = "/dev/ttyACM0"
        mock_port2.description = "Arduino Uno"

        mock_port3 = MagicMock()
        mock_port3.device = "/dev/ttyACM1"
        mock_port3.description = "Arduino Mega"

        # When: System discovery with multiple mocked comports
        with patch(
            "serial.tools.list_ports.comports",
            return_value=[mock_port1, mock_port2, mock_port3],
        ):
            system_serial = SystemSerialPortDiscovery()
            # Find the middle port
            description = system_serial.get_port_description("/dev/ttyACM0")

        # Then: Should find the correct port even when not first
        assert description == "Arduino Uno"

    def test_system_serial_discovery_lists_multiple_ports(self) -> None:
        """
        System serial discovery returns all available ports from comports.

        GIVEN: System serial discovery with mocked multiple ports
        WHEN: Getting available ports
        THEN: Should return list of all mocked ports
        """
        # Given: Mock multiple serial ports
        mock_port1 = MagicMock()
        mock_port1.device = "/dev/ttyUSB0"

        mock_port2 = MagicMock()
        mock_port2.device = "/dev/ttyACM0"

        # When: System discovery with multiple mocked comports
        with patch(
            "serial.tools.list_ports.comports",
            return_value=[mock_port1, mock_port2],
        ):
            system_serial = SystemSerialPortDiscovery()
            ports = system_serial.get_available_ports()

        # Then: Should return all mocked ports
        assert len(ports) == 2
        assert ports[0].device == "/dev/ttyUSB0"
        assert ports[1].device == "/dev/ttyACM0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
