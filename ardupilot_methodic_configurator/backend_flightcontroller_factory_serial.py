"""
Serial port discovery service for flight controller connections.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Protocol

import serial.tools.list_ports
import serial.tools.list_ports_common


class SerialPortDiscovery(Protocol):
    """Protocol for discovering and managing serial ports."""

    def get_available_ports(
        self,
    ) -> list[serial.tools.list_ports_common.ListPortInfo]:
        """Get list of available serial ports."""
        ...  # pylint: disable=unnecessary-ellipsis

    def get_port_description(self, device: str) -> str:
        """Get description for a serial port device."""
        ...  # pylint: disable=unnecessary-ellipsis


class SystemSerialPortDiscovery:
    """Real implementation using PySerial for hardware discovery."""

    def get_available_ports(
        self,
    ) -> list[serial.tools.list_ports_common.ListPortInfo]:
        """Get actual serial ports from system."""
        return list(serial.tools.list_ports.comports())

    def get_port_description(self, device: str) -> str:
        """Get port description from system."""
        for port in serial.tools.list_ports.comports():
            if port.device == device:
                return str(port.description)
        return device


class FakeSerialPortDiscovery:
    """Mock implementation for testing without physical hardware."""

    def __init__(self) -> None:
        """Initialize with empty port list."""
        self._ports: list[serial.tools.list_ports_common.ListPortInfo] = []

    def get_available_ports(
        self,
    ) -> list[serial.tools.list_ports_common.ListPortInfo]:
        """Return configured fake ports."""
        return self._ports.copy()

    def get_port_description(self, device: str) -> str:
        """Return fake port description."""
        for port in self._ports:
            if port.device == device:
                return str(port.description)
        return f"Test Port {device}"

    def add_port(
        self,
        device: str,
        description: str = "Test Serial Port",
        manufacturer: str = "Test Manufacturer",
    ) -> None:
        """Add a fake port for testing."""
        port_info = _create_mock_port_info(device, description, manufacturer)
        self._ports.append(port_info)

    def clear_ports(self) -> None:
        """Clear all configured fake ports."""
        self._ports.clear()


def _create_mock_port_info(device: str, description: str, manufacturer: str) -> serial.tools.list_ports_common.ListPortInfo:
    """Create a mock ListPortInfo object for testing."""
    port_info = serial.tools.list_ports_common.ListPortInfo(device)
    port_info.description = description
    port_info.manufacturer = manufacturer
    return port_info
