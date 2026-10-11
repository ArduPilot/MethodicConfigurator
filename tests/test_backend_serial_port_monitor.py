#!/usr/bin/env python3

"""
Tests for the operating system serial-port hotplug monitor.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from threading import Event
from time import monotonic, sleep
from typing import TYPE_CHECKING
from unittest.mock import Mock, call, patch

import pytest

import ardupilot_methodic_configurator.backend_serial_port_monitor as monitor_module
from ardupilot_methodic_configurator.backend_serial_port_monitor import (
    SerialPortRemovalMonitor,
    _matches_linux_serial_removal,
    serial_port_identity,
)

if TYPE_CHECKING:
    from pathlib import Path

# ctypes structures declare their attributes through _fields_.
# pylint: disable=protected-access, redefined-outer-name, attribute-defined-outside-init


def test_linux_uevent_matches_only_removal_of_selected_tty() -> None:
    """A tty removal uevent identifies its device without matching arrivals or other devices."""
    target_name = "ttyACM0"

    assert _matches_linux_serial_removal(b"ACTION=remove\0SUBSYSTEM=tty\0DEVNAME=ttyACM0\0", target_name)
    assert not _matches_linux_serial_removal(b"ACTION=add\0SUBSYSTEM=tty\0DEVNAME=ttyACM0\0", target_name)
    assert not _matches_linux_serial_removal(b"ACTION=remove\0SUBSYSTEM=tty\0DEVNAME=ttyUSB0\0", target_name)


@pytest.mark.skipif(sys.platform != "win32", reason="WM_DEVICECHANGE is a Windows API")
def test_windows_port_removal_event_matches_selected_com_port() -> None:
    """The hidden window reports removal only for its selected COM port."""

    class DeviceBroadcastPort(ctypes.Structure):  # pylint: disable=too-few-public-methods
        """Windows WM_DEVICECHANGE port payload."""

        _fields_ = [
            ("size", wintypes.DWORD),
            ("device_type", wintypes.DWORD),
            ("reserved", wintypes.DWORD),
            ("name", ctypes.c_wchar * 32),
        ]

    removed = Event()
    monitor = SerialPortRemovalMonitor("COM9234", removed.set)
    monitor.start()

    try:
        deadline = monotonic() + 2.0
        while monitor._windows_hwnd is None and monotonic() < deadline:
            sleep(0.01)
        assert monitor._windows_hwnd is not None

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = ctypes.c_ssize_t

        def send_removed_port(port_name: str) -> None:
            payload = DeviceBroadcastPort()
            payload.size = 12 + (len(port_name) + 1) * ctypes.sizeof(ctypes.c_wchar)
            payload.device_type = 3  # DBT_DEVTYP_PORT
            payload.name = port_name
            user32.SendMessageW(monitor._windows_hwnd, 0x0219, 0x8004, ctypes.addressof(payload))

        send_removed_port("COM9235")
        assert not removed.wait(0.05)

        send_removed_port("COM9234")
        assert removed.wait(0.5)
    finally:
        monitor.stop()


@pytest.mark.parametrize(
    ("platform", "device", "alias"),
    [("win32", r"\\.\COM21", "com21"), ("darwin", "/dev/tty.usbmodem123", "/dev/cu.usbmodem123")],
)
def test_native_and_polled_detection_use_the_same_port_identity(platform: str, device: str, alias: str) -> None:
    """GIVEN OS aliases for one device, WHEN identities are resolved, THEN both refer to the same endpoint."""
    assert serial_port_identity(device, platform) == serial_port_identity(alias, platform)


def test_linux_subscription_tolerates_idle_timeouts_and_ignores_other_devices() -> None:
    """GIVEN an idle subscription, WHEN another tty and then the selected tty disappear, THEN only one removal is reported."""
    removed = Mock()
    with patch.object(monitor_module, "serial_port_identity", return_value="/dev/ttyACM0"):
        monitor = SerialPortRemovalMonitor("/dev/ttyACM0", removed)
    event_socket = Mock()
    event_socket.recv.side_effect = [
        TimeoutError(),
        b"ACTION=remove\0SUBSYSTEM=tty\0DEVNAME=ttyUSB0\0",
        b"ACTION=remove\0SUBSYSTEM=tty\0DEVNAME=ttyACM0\0",
    ]
    socket_factory = Mock()
    socket_factory.return_value.__enter__ = Mock(return_value=event_socket)
    socket_factory.return_value.__exit__ = Mock(return_value=False)
    with (
        patch.object(monitor_module.socket, "AF_NETLINK", 16, create=True),
        patch.object(monitor_module.socket, "socket", socket_factory),
    ):
        monitor._run_linux()
    removed.assert_called_once_with()
    socket_factory.return_value.__exit__.assert_called_once()


@pytest.mark.skipif(sys.platform == "win32", reason="Creating symlinks requires additional Windows privileges")
def test_subscription_remembers_a_removed_symlinks_original_tty(tmp_path: Path) -> None:
    """GIVEN a by-id alias, WHEN its symlink is removed, THEN the original tty removal still matches."""
    target = tmp_path / "ttyACM0"
    target.touch()
    alias = tmp_path / "controller"
    alias.symlink_to(target)
    removed = Mock()
    monitor = SerialPortRemovalMonitor(str(alias), removed)
    alias.unlink()
    event_socket = Mock()
    event_socket.recv.return_value = b"ACTION=remove\0SUBSYSTEM=tty\0DEVNAME=ttyACM0\0"
    socket_factory = Mock()
    socket_factory.return_value.__enter__ = Mock(return_value=event_socket)
    socket_factory.return_value.__exit__ = Mock(return_value=False)
    with (
        patch.object(monitor_module.socket, "AF_NETLINK", 16, create=True),
        patch.object(monitor_module.socket, "socket", socket_factory),
    ):
        monitor._run_linux()
    removed.assert_called_once_with()


@pytest.mark.skipif(sys.platform != "darwin", reason="IOKit registration requires macOS")
def test_native_macos_registration_can_be_released_without_a_serial_device() -> None:
    """GIVEN no matching controller, WHEN native registration is cancelled, THEN IOKit handles can be released normally."""
    removed = Mock()
    monitor = SerialPortRemovalMonitor("/dev/cu.amc-test-nonexistent", removed)
    monitor.stop()
    monitor._run_macos()
    removed.assert_not_called()


def test_cancelled_subscription_does_not_report_a_late_removal() -> None:
    """GIVEN a cancelled subscription, WHEN a delayed event arrives, THEN the controller is not reported lost."""
    removed = Mock()
    monitor = SerialPortRemovalMonitor("COM21", removed)
    monitor.stop()
    monitor._notify_removed()
    removed.assert_not_called()


def test_subscriptions_can_be_stopped_and_started_again() -> None:
    """GIVEN an active subscription, WHEN it is stopped and restarted, THEN each worker exits before replacement."""
    started = Event()
    monitor = SerialPortRemovalMonitor("COM21", Mock())

    def wait_for_stop() -> None:
        started.set()
        monitor._stop_event.wait(2)

    with patch.object(monitor, "_run", side_effect=wait_for_stop):
        monitor.start()
        assert started.wait(1)
        first_thread = monitor._thread
        monitor.start()
        assert monitor._thread is first_thread
        monitor.stop()
        assert first_thread is not None
        assert not first_thread.is_alive()
        started.clear()
        monitor.start()
        try:
            assert started.wait(1)
            assert monitor._thread is not first_thread
        finally:
            monitor.stop()
    assert monitor._thread is None


@pytest.fixture
def macos_libraries() -> tuple[Mock, Mock]:
    """Provide the IOKit and CoreFoundation API boundaries without requiring macOS hardware."""
    iokit = Mock()
    core_foundation = Mock()
    iokit.IONotificationPortCreate.return_value = 11
    iokit.IONotificationPortGetRunLoopSource.return_value = 12
    iokit.IOServiceMatching.return_value = 13
    iokit.IOIteratorNext.return_value = 0
    core_foundation.CFRunLoopGetCurrent.return_value = 31
    core_foundation.CFStringCreateWithCString.side_effect = [21, 22]

    def register(*args: object) -> int:
        ctypes.cast(args[-1], ctypes.POINTER(ctypes.c_uint)).contents.value = 42
        return 0

    iokit.IOServiceAddMatchingNotification.side_effect = register
    return iokit, core_foundation


def test_macos_termination_matches_dial_in_alias_and_releases_every_handle(macos_libraries: tuple[Mock, Mock]) -> None:
    """GIVEN a tty alias, WHEN its callout service terminates, THEN removal is reported and all native handles are released."""
    iokit, core_foundation = macos_libraries
    removed = Mock()
    monitor = SerialPortRemovalMonitor("/dev/tty.usbmodem123", removed)
    iokit.IOIteratorNext.side_effect = [0, 1, 2, 0]
    iokit.IORegistryEntryCreateCFProperty.side_effect = [41, 43]

    def copy_device(property_ref: int, buffer: object, _size: int, _encoding: int) -> bool:
        name = b"/dev/cu.usbmodem999" if property_ref == 41 else b"/dev/cu.usbmodem123"
        ctypes.memmove(buffer, name + b"\0", len(name) + 1)
        return True

    def deliver_termination(*_args: object) -> int:
        callback = iokit.IOServiceAddMatchingNotification.call_args.args[3]
        callback(None, 42)
        return 1

    core_foundation.CFStringGetCString.side_effect = copy_device
    core_foundation.CFRunLoopRunInMode.side_effect = deliver_termination
    with patch.object(monitor_module.ctypes, "CDLL", side_effect=[iokit, core_foundation]):
        monitor._run_macos()
    removed.assert_called_once_with()
    assert iokit.IOObjectRelease.call_args_list == [call(1), call(2), call(42)]
    assert core_foundation.CFRelease.call_args_list == [call(41), call(43), call(22), call(21)]
    core_foundation.CFRunLoopRemoveSource.assert_called_once_with(31, 12, 21)
    iokit.IONotificationPortDestroy.assert_called_once_with(11)


@pytest.mark.parametrize("failure", ["source", "strings", "registration", "run_loop"])
def test_macos_startup_and_runtime_failures_release_allocated_resources(
    macos_libraries: tuple[Mock, Mock], failure: str
) -> None:
    """GIVEN a native API failure, WHEN monitoring aborts, THEN already acquired notification resources are released."""
    iokit, core_foundation = macos_libraries
    monitor = SerialPortRemovalMonitor("/dev/cu.usbmodem123", Mock())
    if failure == "source":
        iokit.IONotificationPortGetRunLoopSource.return_value = 0
    elif failure == "strings":
        core_foundation.CFStringCreateWithCString.side_effect = [21, None]
    elif failure == "registration":
        iokit.IOServiceAddMatchingNotification.side_effect = None
        iokit.IOServiceAddMatchingNotification.return_value = 5
    else:
        core_foundation.CFRunLoopRunInMode.side_effect = OSError("run loop failed")
    with (
        patch.object(monitor_module.ctypes, "CDLL", side_effect=[iokit, core_foundation]),
        pytest.raises(OSError, match=r"IOKit|run loop failed"),
    ):
        monitor._run_macos()
    iokit.IONotificationPortDestroy.assert_called_once_with(11)
    if failure == "source":
        core_foundation.CFRelease.assert_not_called()
    elif failure == "strings":
        core_foundation.CFRelease.assert_called_once_with(21)
    else:
        assert core_foundation.CFRelease.call_args_list == [call(22), call(21)]
        core_foundation.CFRunLoopRemoveSource.assert_called_once_with(31, 12, 21)
    if failure == "run_loop":
        iokit.IOObjectRelease.assert_called_once_with(42)


@pytest.mark.skipif(sys.platform != "win32", reason="Window class registration is a Windows API")
def test_windows_window_creation_failure_unregisters_its_class() -> None:
    """GIVEN a registered window class, WHEN window creation fails, THEN registration does not leak."""
    user32 = Mock()
    kernel32 = Mock()
    user32.RegisterClassW.return_value = 1
    user32.CreateWindowExW.return_value = None
    kernel32.GetModuleHandleW.return_value = 1
    monitor = SerialPortRemovalMonitor("COM21", Mock())
    with (
        patch.object(monitor_module.ctypes, "WinDLL", side_effect=[user32, kernel32]),
        patch.object(monitor_module.ctypes, "get_last_error", return_value=87),
        pytest.raises(OSError, match="WinError 87"),
    ):
        monitor._run_windows()
    user32.UnregisterClassW.assert_called_once()
    user32.DestroyWindow.assert_not_called()
    assert monitor._windows_hwnd is None
