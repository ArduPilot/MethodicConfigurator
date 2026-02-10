"""
MAVLink connection factory service for flight controller connections.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Optional, Protocol

from pymavlink import mavutil


class MavlinkConnectionFactory(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for creating MAVLink connections."""

    def create(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device: str,
        baudrate: int,
        timeout: float = 5.0,
        retries: int = 3,
        progress_callback: Optional[object] = None,
    ) -> Optional[mavutil.mavlink_connection]:  # pyright: ignore[reportGeneralTypeIssues]
        """Create a MAVLink connection."""
        ...  # pylint: disable=unnecessary-ellipsis


class SystemMavlinkConnectionFactory:  # pylint: disable=too-few-public-methods
    """Real implementation using PyMAVLink library."""

    def create(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device: str,
        baudrate: int,
        timeout: float = 5.0,
        retries: int = 3,
        progress_callback: Optional[object] = None,
    ) -> Optional[mavutil.mavlink_connection]:  # pyright: ignore[reportGeneralTypeIssues]
        """Create connection using actual PyMAVLink library."""
        try:
            return mavutil.mavlink_connection(
                device=device,
                baud=baudrate,
                timeout=timeout,
                retries=retries,
                progress_callback=progress_callback,
            )
        except (OSError, TimeoutError, ValueError) as exc:
            # Preserve the root cause in a ConnectionError so callers can display
            # actionable information to the user.
            msg = f"{device}: {exc}"
            raise ConnectionError(msg) from exc


class FakeMavlinkConnectionFactory:
    """Mock implementation for testing without actual hardware."""

    def __init__(self) -> None:
        """Initialize mock factory."""
        self._connections: dict[str, FakeMavlinkConnection] = {}

    def create(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device: str,
        baudrate: int,
        timeout: float = 5.0,  # noqa: ARG002 # pylint: disable=unused-argument
        retries: int = 3,
        progress_callback: Optional[object] = None,
    ) -> Optional["FakeMavlinkConnection"]:
        """Create a fake MAVLink connection for testing."""
        conn = FakeMavlinkConnection(device, baudrate)
        conn.retries = retries
        conn.progress_callback = progress_callback
        return conn

    def get_connection(self, device: str) -> Optional["FakeMavlinkConnection"]:
        """Get a previously created fake connection."""
        return self._connections.get(device)


class FakeMavlinkConnection:
    """Fake MAVLink connection for testing."""

    retries: int
    progress_callback: Optional[object]

    def __init__(self, device: str, baudrate: int) -> None:
        """Initialize fake connection."""
        self.device = device
        self.baudrate = baudrate
        self.connected = True
        self._message_queue: list[object] = []

    def recv_match(
        self,
        blocking: bool = True,  # noqa: ARG002  # pylint: disable=unused-argument
        timeout: Optional[float] = None,  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> Optional[object]:
        """Receive a matched message from queue."""
        # Note: blocking and timeout parameters are accepted for API compatibility
        # but not used in fake implementation
        if self._message_queue:
            return self._message_queue.pop(0)
        return None

    def mav_send(self, msg: object) -> None:
        """Send a MAVLink message (no-op for fake)."""
        # Note: msg parameter is accepted for API compatibility but not used in fake

    def close(self) -> None:
        """Close connection."""
        self.connected = False

    def add_message(self, msg: object) -> None:
        """Add a message to the queue for testing."""
        self._message_queue.append(msg)

    def clear_messages(self) -> None:
        """Clear all queued messages."""
        self._message_queue.clear()
