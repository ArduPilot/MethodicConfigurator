"""
Regression tests for bootloader device identity resolution.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: INP001

from pathlib import Path

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

    identity = bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123")

    with pytest.raises(OSError, match="cannot uniquely"):
        bl.resolve_bootloader_device("/dev/cu.usbmodem14101", identity)


def test_bootloader_port_matches_linux_interface_qualified_location(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second Linux CDC interface still maps to the same bootloader device."""
    bootloader_port = ListPortInfo("/dev/ttyACM0")
    bootloader_port.location = "1-2.3:1.0"
    bootloader_port.serial_number = "FC-123"
    bootloader_port.interface = None
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [bootloader_port])

    identity = bl.SerialDeviceIdentity(location="1-2.3:1.2", serial_number="FC-123")

    assert bl.resolve_bootloader_device("/dev/ttyACM1", identity) == "/dev/ttyACM0"


def test_application_port_prefers_an_exact_interface_qualified_location(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dual-CDC application reconnects to the originally selected port."""
    mavlink_port = ListPortInfo("/dev/ttyACM0")
    mavlink_port.location = "1-2.3:1.0"
    mavlink_port.serial_number = "FC-123"
    mavlink_port.interface = None
    console_port = ListPortInfo("/dev/ttyACM1")
    console_port.location = "1-2.3:1.2"
    console_port.serial_number = "FC-123"
    console_port.interface = None
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [mavlink_port, console_port])

    identity = bl.SerialDeviceIdentity(location="1-2.3:1.0", serial_number="FC-123")

    assert bl.resolve_bootloader_device("/dev/ttyACM0", identity) == "/dev/ttyACM0"


def test_bootloader_port_refuses_identical_macos_dual_cdc_interfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Identical CDC metadata must remain fail-closed after reboot."""
    first_port = ListPortInfo("/dev/cu.usbmodem14101")
    first_port.location = "1-2.3"
    first_port.serial_number = "FC-123"
    first_port.interface = "0"
    second_port = ListPortInfo("/dev/cu.usbmodem14102")
    second_port.location = "1-2.3"
    second_port.serial_number = "FC-123"
    second_port.interface = "0"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [first_port, second_port])

    identity = bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123", interface="0")

    with pytest.raises(OSError, match="cannot uniquely"):
        bl.resolve_bootloader_device("/dev/cu.usbmodem14101", identity)


def test_bootloader_port_selects_the_captured_macos_dual_cdc_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    """A captured CDC interface disambiguates the two ports exposed by macOS."""
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

    assert bl.resolve_bootloader_device("/dev/cu.usbmodem14101", identity) == "/dev/cu.usbmodem14101"


def test_bootloader_port_accepts_a_sole_match_when_its_interface_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The application interface must not exclude the sole bootloader candidate."""
    port = ListPortInfo("/dev/cu.usbmodem14101")
    port.location = "1-2.3"
    port.serial_number = "FC-123"
    port.interface = "Bootloader"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [port])

    identity = bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123", interface="ArduPilot")

    assert bl.resolve_bootloader_device("/dev/cu.usbmodem14101", identity) == "/dev/cu.usbmodem14101"


def test_bootloader_port_refuses_duplicate_serials_on_different_devices_despite_interface_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An interface name must not select one of several physical USB devices."""
    bootloader_port = ListPortInfo("/dev/ttyACM0")
    bootloader_port.serial_number = "DUP"
    bootloader_port.location = "1-2.3"
    bootloader_port.interface = "Bootloader"
    other_port = ListPortInfo("/dev/ttyACM1")
    other_port.serial_number = "DUP"
    other_port.location = "1-2.4"
    other_port.interface = "ArduPilot"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [bootloader_port, other_port])

    identity = bl.SerialDeviceIdentity(serial_number="DUP", interface="ArduPilot")

    with pytest.raises(OSError, match="cannot uniquely"):
        bl.resolve_bootloader_device("/dev/ttyACM0", identity)


def test_capture_serial_identity_follows_a_symlinked_device_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """USB metadata is retained when the selected port is a symlink such as by-id."""
    device = tmp_path / "ttyACM0"
    device.touch()
    device_link = tmp_path / "usb-ArduPilot"
    device_link.symlink_to(device)
    port = ListPortInfo(str(device))
    port.location = "1-2.3"
    port.serial_number = "FC-123"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [port])

    assert bl.capture_serial_device_identity(str(device_link)) == bl.SerialDeviceIdentity(
        location="1-2.3", serial_number="FC-123"
    )


def test_capture_serial_identity_preserves_macos_cdc_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    """The selected macOS CDC interface is retained for post-reboot resolution."""
    port = ListPortInfo("/dev/cu.usbmodem14101")
    port.location = "1-2.3"
    port.serial_number = "FC-123"
    port.interface = "0"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [port])

    assert bl.capture_serial_device_identity(port.device) == bl.SerialDeviceIdentity(
        location="1-2.3", serial_number="FC-123", interface="0"
    )
