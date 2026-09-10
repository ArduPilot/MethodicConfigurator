"""
MAVLink connection factory service for flight controller connections.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections import deque
from time import monotonic
from typing import TYPE_CHECKING, Optional, Protocol

from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_mavlink_param_error import install_param_error_message

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller_protocols import MavlinkConnection


class MavlinkConnectionFactory(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for creating MAVLink connections."""

    def create(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device: str,
        baudrate: int,
        timeout: float = 5.0,
        retries: int = 3,
        progress_callback: object | None = None,
    ) -> Optional["MavlinkConnection"]:
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
        progress_callback: object | None = None,
    ) -> Optional["MavlinkConnection"]:
        """Create connection using actual PyMAVLink library."""
        try:
            # PARAM_ERROR has id 345 and is therefore MAVLink-2 only.  Select
            # the v2 dialect before mavutil constructs its parser.
            install_param_error_message()
            connection = mavutil.mavlink_connection(  # pyright: ignore[reportReturnType]
                device=device,
                baud=baudrate,
                timeout=timeout,
                retries=retries,
                progress_callback=progress_callback,
                autoreconnect=True,
            )
            return BufferedMavlinkConnection(connection)
        except PermissionError:
            # PermissionError subclasses OSError; preserve it for permission-specific UI guidance.
            raise
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
        progress_callback: object | None = None,
    ) -> Optional["FakeMavlinkConnection"]:
        """Create a fake MAVLink connection for testing."""
        conn = FakeMavlinkConnection(device, baudrate)
        conn.retries = retries
        conn.progress_callback = progress_callback
        self._connections[device] = conn
        return conn

    def get_connection(self, device: str) -> Optional["FakeMavlinkConnection"]:
        """Get a previously created fake connection."""
        return self._connections.get(device)


class BufferedMavlinkConnection:
    """MAVLink connection adapter that preserves messages skipped by filters."""

    def __init__(self, connection: object) -> None:
        """Initialize the adapter around a pymavlink connection."""
        self._connection = connection
        self._pending_messages: deque[object] = deque()

    def __getattr__(self, name: str) -> object:
        """Expose the underlying connection's normal MAVLink attributes."""
        return getattr(self._connection, name)

    def recv_msg(self) -> object | None:
        """Return the next message, including one preserved by a prior filter."""
        if self._pending_messages:
            return self._pending_messages.popleft()
        recv_msg = self._connection.recv_msg  # type: ignore[attr-defined]
        return recv_msg()

    def recv_match(
        self,
        condition: str | None = None,
        type: str | list[str] | set[str] | None = None,  # noqa: A002  # pylint: disable=redefined-builtin
        blocking: bool = False,
        timeout: float | None = None,
    ) -> object | None:
        """Return a matching message while retaining messages of other types."""
        if condition is not None:
            error_message = "Buffered receive does not support conditions"
            raise NotImplementedError(error_message)

        message_types = None if type is None else {type} if isinstance(type, str) else set(type)
        start_time = monotonic()
        while True:
            # A busy telemetry link can always have another unrelated message
            # ready.  Check the deadline before every read so a filtered wait
            # cannot indefinitely drain and buffer that stream.
            if timeout is not None and monotonic() - start_time >= timeout:
                return None
            message = self._pop_pending_matching(message_types)
            if message is None:
                recv_msg = self._connection.recv_msg  # type: ignore[attr-defined]
                message = recv_msg()
            if message is not None:
                if message_types is None or getattr(message, "get_type", lambda: None)() in message_types:
                    return message
                self._pending_messages.append(message)
                # A non-blocking call must be bounded even when the transport
                # is continuously receiving telemetry.  The next poll resumes
                # the search, with this message safely retained.
                if not blocking:
                    return None
                continue

            if not blocking:
                return None
            if timeout is not None:
                remaining = timeout - (monotonic() - start_time)
                if remaining <= 0:
                    return None
            else:
                remaining = 0.05
            select = getattr(self._connection, "select", None)
            if callable(select):
                select(min(remaining, 0.05))

    def _pop_pending_matching(self, message_types: set[str] | None) -> object | None:
        """Remove the first buffered message matching the requested types."""
        for index, message in enumerate(self._pending_messages):
            if message_types is None or getattr(message, "get_type", lambda: None)() in message_types:
                del self._pending_messages[index]
                return message
        return None


class FakeMavlinkConnection:
    """Fake MAVLink connection for testing."""

    retries: int
    progress_callback: object | None

    def __init__(self, device: str, baudrate: int) -> None:
        """Initialize fake connection."""
        self.device = device
        self.baudrate = baudrate
        self.connected = True
        self._message_queue: list[object] = []

    def recv_match(
        self,
        type: str | None = None,  # noqa: A002  # pylint: disable=redefined-builtin
        blocking: bool = True,  # noqa: ARG002  # pylint: disable=unused-argument
        timeout: float | None = None,  # noqa: ARG002  # pylint: disable=unused-argument
    ) -> object | None:
        """Receive the next queued message matching an optional MAVLink type."""
        # Note: blocking and timeout parameters are accepted for API compatibility
        # but not used in fake implementation
        if type is None:
            if self._message_queue:
                return self._message_queue.pop(0)
            return None

        for index, message in enumerate(self._message_queue):
            get_type = getattr(message, "get_type", None)
            if callable(get_type) and get_type() == type:
                return self._message_queue.pop(index)
        return None

    def recv_msg(self) -> object | None:
        """Receive the next queued message without filtering by MAVLink type."""
        if self._message_queue:
            return self._message_queue.pop(0)
        return None

    def mav_send(self, msg: object) -> None:
        """Send a MAVLink message (no-op for fake)."""
        # Note: msg parameter is accepted for API compatibility but not used in fake

    def param_set_send(self, param_name: str, param_value: float) -> None:
        """Send a parameter write (no-op for fake)."""

    def close(self) -> None:
        """Close connection."""
        self.connected = False

    def add_message(self, msg: object) -> None:
        """Add a message to the queue for testing."""
        self._message_queue.append(msg)

    def clear_messages(self) -> None:
        """Clear all queued messages."""
        self._message_queue.clear()
