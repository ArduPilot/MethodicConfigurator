"""
Regression tests for bootloader device identity resolution.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: INP001

import pytest
from serial.tools.list_ports_common import ListPortInfo

from ardupilot_methodic_configurator import backend_flightcontroller_bootloader as bl


def test_bootloader_port_refuses_a_partial_usb_identity_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A bootloader port must match every captured USB identity attribute.

    GIVEN: A controller was captured with both a USB location and serial number
    WHEN: Only one of those attributes matches a re-enumerated port
    THEN: The stale or different controller is rejected
    """
    port = ListPortInfo("COM11")
    port.location = "1-2.3"
    port.serial_number = "FC-other"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [port])

    identity = bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123")

    with pytest.raises(OSError, match="cannot uniquely"):
        bl.resolve_bootloader_device("COM7", identity)


def test_bootloader_port_refuses_an_ambiguous_macos_dual_cdc_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """An application-port interface identifier cannot safely identify a bootloader port."""
    mavlink_port = ListPortInfo("/dev/cu.usbmodem14101")
    mavlink_port.location = "1-2.3"
    mavlink_port.serial_number = "FC-123"
    mavlink_port.interface = "0"
    console_port = ListPortInfo("/dev/cu.usbmodem14102")
    console_port.location = "1-2.3"
    console_port.serial_number = "FC-123"
    console_port.interface = "2"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [mavlink_port, console_port])

    identity = bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123", interface="0")

    with pytest.raises(OSError, match="cannot uniquely"):
        bl.resolve_bootloader_device("/dev/cu.usbmodem14101", identity)
