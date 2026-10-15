"""
Cross-platform serial device removal notifications.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
from contextlib import suppress
from ctypes import wintypes
from threading import Event, Thread, current_thread
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable


def serial_port_identity(device: str, platform: str | None = None) -> str:
    """Identify a physical serial endpoint across OS-specific aliases."""
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        return device.removeprefix("\\\\.\\").casefold()
    device = os.path.realpath(device)
    if platform == "darwin":
        # Dial-in and callout nodes belong to the same IOSerialBSDClient.
        name = os.path.basename(device)
        if name.startswith("tty."):
            device = os.path.join(os.path.dirname(device), "cu." + name[4:])
    return os.path.normcase(device)


class SerialPortMonitor(Protocol):
    """Lifecycle of a serial-device removal subscription."""

    def start(self) -> None:
        """Subscribe to removal events."""

    def stop(self) -> None:
        """Cancel the subscription."""


def _matches_linux_serial_removal(packet: bytes, target_name: str) -> bool:
    """Return whether a Linux uevent reports removal of the selected tty node."""
    fields = {
        key.decode("utf-8", errors="replace"): value.decode("utf-8", errors="replace")
        for item in packet.split(b"\0")
        if b"=" in item
        for key, value in (item.split(b"=", 1),)
    }
    return (
        fields.get("ACTION") == "remove"
        and fields.get("SUBSYSTEM") == "tty"
        and os.path.basename(fields.get("DEVNAME", "")) == target_name
    )


class SerialPortRemovalMonitor:
    """Listen for OS hotplug events and report removal of one serial port."""

    def __init__(self, device: str, on_removed: Callable[[], None]) -> None:
        # Resolve symlinks while their target still exists, before removal.
        self._device = serial_port_identity(device)
        self._on_removed = on_removed
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._windows_hwnd: int | None = None

    def start(self) -> None:
        """Start a daemon thread that receives native device notifications."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="serial-port-removal-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the native event loop and wait briefly for its thread to exit."""
        self._stop_event.set()
        hwnd = self._windows_hwnd
        if hwnd is not None and sys.platform == "win32":
            with suppress(AttributeError, OSError):
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
        if self._thread is not None and self._thread is not current_thread() and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None

    def _notify_removed(self) -> None:
        """Deliver one removal event unless the subscription was cancelled."""
        if not self._stop_event.is_set():
            self._stop_event.set()
            self._on_removed()

    def _run(self) -> None:
        """Dispatch to the active operating system's hotplug API."""
        try:
            if sys.platform.startswith("linux"):
                self._run_linux()
            elif sys.platform == "darwin":
                self._run_macos()
            elif sys.platform == "win32":
                self._run_windows()
            else:
                logging.debug("Serial hotplug monitoring is unsupported on %s", sys.platform)
        except (OSError, AttributeError, TypeError) as error:
            logging.debug("Native serial hotplug monitoring could not start: %s", error)

    def _run_linux(self) -> None:
        """Receive Linux kernel uevents and match tty removal by device-node name."""
        netlink_kobject_uevent = 15
        uevent_group = 1
        target_name = os.path.basename(self._device)
        netlink_family = getattr(socket, "AF_NETLINK", None)
        if netlink_family is None:
            error_message = "This Python build does not provide Linux netlink sockets"
            raise OSError(error_message)
        with socket.socket(netlink_family, socket.SOCK_DGRAM, netlink_kobject_uevent) as event_socket:
            event_socket.bind((0, uevent_group))
            event_socket.settimeout(0.5)
            while not self._stop_event.is_set():
                try:
                    packet = event_socket.recv(8192)
                except TimeoutError:
                    continue
                if _matches_linux_serial_removal(packet, target_name):
                    self._notify_removed()
                    return

    def _run_windows(self) -> None:  # noqa: PLR0915 # pylint: disable=too-many-statements, too-many-locals
        """Receive WM_DEVICECHANGE port notifications on a private hidden window."""
        port_name = self._device.removeprefix("\\\\.\\").casefold()
        if not port_name.startswith("com"):
            return

        lresult = ctypes.c_ssize_t
        wndproc_type = ctypes.WINFUNCTYPE(lresult, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class WindowClass(ctypes.Structure):  # pylint: disable=too-few-public-methods
            """WNDCLASSW layout including the pinned Python window procedure."""

            _fields_ = [
                ("style", wintypes.UINT),
                ("window_proc", wndproc_type),
                ("class_extra", ctypes.c_int),
                ("window_extra", ctypes.c_int),
                ("instance", wintypes.HINSTANCE),
                ("icon", wintypes.HICON),
                ("cursor", wintypes.HANDLE),
                ("background", wintypes.HBRUSH),
                ("menu_name", wintypes.LPCWSTR),
                ("class_name", wintypes.LPCWSTR),
            ]

        class Message(ctypes.Structure):  # pylint: disable=too-few-public-methods
            """Complete MSG layout on both 32-bit and 64-bit Windows."""

            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wparam", wintypes.WPARAM),
                ("lparam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("point_x", wintypes.LONG),
                ("point_y", wintypes.LONG),
                ("private", wintypes.DWORD),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WindowClass)]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.GetMessageW.argtypes = [ctypes.POINTER(Message), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(Message)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(Message)]
        user32.DispatchMessageW.restype = lresult
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = lresult
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        class_name = f"AMCSerialPortMonitor{os.getpid()}_{id(self)}"

        def window_proc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
            wm_devicechange = 0x0219
            dbt_device_removed = 0x8004
            dbt_devicetype_port = 0x00000003
            if message == wm_devicechange and wparam == dbt_device_removed and lparam:
                header_size = ctypes.sizeof(wintypes.DWORD) * 3
                device_type = ctypes.cast(lparam, ctypes.POINTER(wintypes.DWORD))[1]
                if device_type == dbt_devicetype_port:
                    removed_port = ctypes.wstring_at(lparam + header_size).casefold()
                    if removed_port == port_name:
                        self._notify_removed()
            if message == 0x0010:  # WM_CLOSE
                user32.PostQuitMessage(0)
                return 0
            return int(user32.DefWindowProcW(hwnd, message, wparam, lparam))

        callback = wndproc_type(window_proc)
        instance = kernel32.GetModuleHandleW(None)
        window_class = WindowClass(0, callback, 0, 0, instance, None, None, None, None, class_name)
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            raise ctypes.WinError(ctypes.get_last_error())
        hwnd = None
        try:
            hwnd = user32.CreateWindowExW(0, class_name, class_name, 0, 0, 0, 0, 0, None, None, instance, None)
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._windows_hwnd = int(hwnd)
            message_data = Message()
            while not self._stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(message_data), None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(message_data))
                user32.DispatchMessageW(ctypes.byref(message_data))
        finally:
            if hwnd:
                user32.DestroyWindow(hwnd)
            user32.UnregisterClassW(class_name, instance)
            self._windows_hwnd = None

    def _run_macos(self) -> None:  # noqa: PLR0915 # pylint: disable=too-many-statements, too-many-locals
        """Use IOKit termination notifications for IOSerialBSDClient devices."""
        iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
        core_foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        io_object = ctypes.c_uint
        cf_ref = ctypes.c_void_p
        callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, io_object)
        utf8_encoding = 0x08000100

        iokit.IONotificationPortCreate.argtypes = [io_object]
        iokit.IONotificationPortCreate.restype = cf_ref
        iokit.IONotificationPortDestroy.argtypes = [cf_ref]
        iokit.IONotificationPortGetRunLoopSource.argtypes = [cf_ref]
        iokit.IONotificationPortGetRunLoopSource.restype = cf_ref
        iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
        iokit.IOServiceMatching.restype = cf_ref
        iokit.IOServiceAddMatchingNotification.argtypes = [
            cf_ref,
            ctypes.c_char_p,
            cf_ref,
            callback_type,
            ctypes.c_void_p,
            ctypes.POINTER(io_object),
        ]
        iokit.IOServiceAddMatchingNotification.restype = ctypes.c_int
        iokit.IOIteratorNext.argtypes = [io_object]
        iokit.IOIteratorNext.restype = io_object
        iokit.IOObjectRelease.argtypes = [io_object]
        iokit.IORegistryEntryCreateCFProperty.argtypes = [io_object, cf_ref, cf_ref, ctypes.c_uint32]
        iokit.IORegistryEntryCreateCFProperty.restype = cf_ref
        core_foundation.CFStringCreateWithCString.argtypes = [cf_ref, ctypes.c_char_p, ctypes.c_uint32]
        core_foundation.CFStringCreateWithCString.restype = cf_ref
        core_foundation.CFStringGetCString.argtypes = [cf_ref, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        core_foundation.CFStringGetCString.restype = ctypes.c_bool
        core_foundation.CFRunLoopGetCurrent.restype = cf_ref
        core_foundation.CFRunLoopAddSource.argtypes = [cf_ref, cf_ref, cf_ref]
        core_foundation.CFRunLoopRemoveSource.argtypes = [cf_ref, cf_ref, cf_ref]
        core_foundation.CFRunLoopRunInMode.argtypes = [cf_ref, ctypes.c_double, ctypes.c_bool]
        core_foundation.CFRunLoopRunInMode.restype = ctypes.c_int
        core_foundation.CFRunLoopStop.argtypes = [cf_ref]
        core_foundation.CFRelease.argtypes = [cf_ref]

        target = serial_port_identity(self._device, "darwin")
        notification_port = iokit.IONotificationPortCreate(0)
        if not notification_port:
            error_message = "IOKit could not create a serial-device notification port"
            raise OSError(error_message)
        run_loop = None
        source = None
        mode = None
        property_key = None
        iterator = io_object()
        source_added = False
        try:
            run_loop = core_foundation.CFRunLoopGetCurrent()
            source = iokit.IONotificationPortGetRunLoopSource(notification_port)
            if not source:
                error_message = "IOKit could not create a serial-device run-loop source"
                raise OSError(error_message)
            mode = core_foundation.CFStringCreateWithCString(None, b"kCFRunLoopDefaultMode", utf8_encoding)
            property_key = core_foundation.CFStringCreateWithCString(None, b"IOCalloutDevice", utf8_encoding)
            if not mode or not property_key:
                error_message = "IOKit could not allocate serial-device notification strings"
                raise OSError(error_message)
            core_foundation.CFRunLoopAddSource(run_loop, source, mode)
            source_added = True

            def drain_terminated_services(_context: int, service_iterator: int) -> None:
                while service := iokit.IOIteratorNext(service_iterator):
                    callout_device = None
                    try:
                        callout_device = iokit.IORegistryEntryCreateCFProperty(service, property_key, None, 0)
                        if callout_device:
                            value = ctypes.create_string_buffer(1024)
                            if core_foundation.CFStringGetCString(callout_device, value, len(value), utf8_encoding):
                                device = serial_port_identity(os.fsdecode(value.value), "darwin")
                                if device == target:
                                    self._notify_removed()
                    finally:
                        if callout_device:
                            core_foundation.CFRelease(callout_device)
                        iokit.IOObjectRelease(service)

            callback = callback_type(drain_terminated_services)
            matching = iokit.IOServiceMatching(b"IOSerialBSDClient")
            status = iokit.IOServiceAddMatchingNotification(
                notification_port,
                b"IOServiceTerminate",
                matching,
                callback,
                None,
                ctypes.byref(iterator),
            )
            if status != 0:
                error_message = f"IOKit serial removal registration failed with status {status}"
                raise OSError(error_message)
            drain_terminated_services(0, iterator.value)
            while not self._stop_event.is_set():
                return_after_source_handled = True
                core_foundation.CFRunLoopRunInMode(mode, 0.5, return_after_source_handled)
        finally:
            if iterator.value:
                iokit.IOObjectRelease(iterator.value)
            if source_added:
                core_foundation.CFRunLoopRemoveSource(run_loop, source, mode)
            if property_key:
                core_foundation.CFRelease(property_key)
            if mode:
                core_foundation.CFRelease(mode)
            iokit.IONotificationPortDestroy(notification_port)
