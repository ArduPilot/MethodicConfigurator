#!/usr/bin/env python3

"""
BDD-style tests for dependency injection services in backend_flightcontroller_factory_mavlink.py.

These tests verify the injectable services for testability, demonstrating how to use fake
implementations in production code for better test isolation and no external dependencies.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest import mock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink import (
    FakeMavlinkConnectionFactory,
    SystemMavlinkConnectionFactory,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import (
    FlightControllerInfo,
)

# pylint: disable=protected-access


class TestMavlinkConnectionFactoryService:
    """Test MAVLink connection factory service abstraction."""

    def test_system_mavlink_factory_defaults_when_none_provided(self) -> None:
        """
        System MAVLink factory is used when no factory service provided.

        GIVEN: FlightControllerConnection without explicit factory
        WHEN: Connection initializes
        THEN: SystemMavlinkConnectionFactory should be the default
        """
        # Given: Create connection without factory
        info = FlightControllerInfo()
        connection = FlightControllerConnection(info=info)

        # Then: Default system factory is used
        assert isinstance(connection._mavlink_connection_factory, SystemMavlinkConnectionFactory)

    def test_fake_mavlink_factory_can_be_injected(self) -> None:
        """
        Custom MAVLink factory service can be injected for testing.

        GIVEN: Developer wants to test without real hardware
        WHEN: Injecting FakeMavlinkConnectionFactory
        THEN: Connection should use the injected fake factory
        """
        # Given: Create fake factory
        fake_mavlink = FakeMavlinkConnectionFactory()

        # When: Inject into connection
        info = FlightControllerInfo()
        connection = FlightControllerConnection(
            info=info,
            mavlink_connection_factory=fake_mavlink,
        )

        # Then: Injected factory is used
        assert connection._mavlink_connection_factory is fake_mavlink

    def test_fake_mavlink_factory_creates_connections_with_attributes(self) -> None:
        """
        Fake factory creates connections with retries and progress_callback attributes.

        GIVEN: Fake MAVLink factory
        WHEN: Creating connection with retries and callback
        THEN: Connection should have these attributes set
        """
        # Given: Fake factory
        fake_factory = FakeMavlinkConnectionFactory()

        # When: Create connection with attributes
        def test_callback(current: int, total: int) -> None:  # pylint: disable=unused-argument
            pass

        conn = fake_factory.create(
            device="/dev/ttyUSB0",
            baudrate=115200,
            timeout=5.0,
            retries=3,
            progress_callback=test_callback,
        )

        # Then: Connection has attributes set
        assert conn is not None
        assert conn.retries == 3
        assert conn.progress_callback is test_callback

    def test_fake_mavlink_connection_attributes(self) -> None:
        """
        Fake MAVLink connection has all expected attributes and methods.

        GIVEN: Fake connection created by factory
        WHEN: Accessing attributes
        THEN: All attributes should be present and initialized
        """
        # Given: Fake factory and connection
        fake_factory = FakeMavlinkConnectionFactory()
        conn = fake_factory.create(device="/dev/ttyUSB0", baudrate=115200)

        # Then: All attributes present
        assert conn is not None
        assert conn.device == "/dev/ttyUSB0"
        assert conn.baudrate == 115200
        assert conn.connected is True
        assert hasattr(conn, "retries")
        assert hasattr(conn, "progress_callback")

    def test_fake_mavlink_connection_message_queueing(self) -> None:
        """
        Fake MAVLink connection supports message queueing for testing.

        GIVEN: Fake connection
        WHEN: Queuing and receiving messages
        THEN: Messages should be FIFO ordered
        """
        # Given: Fake connection with messages
        fake_factory = FakeMavlinkConnectionFactory()
        conn = fake_factory.create(device="/dev/ttyUSB0", baudrate=115200)

        # When: Queue messages
        assert conn is not None
        conn.add_message("message_1")
        conn.add_message("message_2")
        conn.add_message("message_3")

        # Then: Messages received in FIFO order
        assert conn.recv_match(blocking=False) == "message_1"
        assert conn.recv_match(blocking=False) == "message_2"
        assert conn.recv_match(blocking=False) == "message_3"
        assert conn.recv_match(blocking=False) is None  # Empty queue

    def test_fake_mavlink_connection_message_clearing(self) -> None:
        """
        Fake MAVLink connection supports clearing message queue.

        GIVEN: Fake connection with queued messages
        WHEN: Clearing messages
        THEN: Queue should be empty
        """
        # Given: Fake connection with messages
        fake_factory = FakeMavlinkConnectionFactory()
        conn = fake_factory.create(device="/dev/ttyUSB0", baudrate=115200)
        assert conn is not None
        conn.add_message("msg1")
        conn.add_message("msg2")

        # When: Clear messages
        conn.clear_messages()

        # Then: Queue is empty
        assert conn.recv_match(blocking=False) is None

    def test_fake_mavlink_connection_close_method(self) -> None:
        """
        Fake MAVLink connection can be closed.

        GIVEN: Fake connection
        WHEN: Closing connection
        THEN: Connected flag should be False
        """
        # Given: Fake connection
        fake_factory = FakeMavlinkConnectionFactory()
        conn = fake_factory.create(device="/dev/ttyUSB0", baudrate=115200)
        assert conn is not None
        assert conn.connected is True

        # When: Close connection
        conn.close()

        # Then: Connected is False
        assert conn.connected is False

    def test_fake_mavlink_connection_send_method(self) -> None:
        """
        Fake MAVLink connection mav_send method accepts messages.

        GIVEN: Fake connection
        WHEN: Sending message via mav_send
        THEN: Method should accept and handle message
        """
        # Given: Fake connection
        fake_factory = FakeMavlinkConnectionFactory()
        conn = fake_factory.create(device="/dev/ttyUSB0", baudrate=115200)

        # When/Then: Send should not raise (no-op for fake)
        assert conn is not None
        conn.mav_send("test_message")  # Should not raise

    def test_fake_mavlink_factory_get_connection_not_stored(self) -> None:
        """
        FakeMavlinkConnectionFactory.get_connection returns None for unstored device.

        GIVEN: Fake factory
        WHEN: Getting connection for device that was never created
        THEN: Should return None
        """
        # Given: Fake factory (connections not explicitly stored in _connections dict)
        fake_factory = FakeMavlinkConnectionFactory()

        # When: Get connection that doesn't exist
        result = fake_factory.get_connection("/dev/ttyUSB0")

        # Then: Returns None
        assert result is None

    def test_system_mavlink_factory_preserves_oserror(self) -> None:
        """
        SystemMavlinkConnectionFactory surfaces OSError causes.

        GIVEN: mavutil.mavlink_connection raises OSError (device not found)
        WHEN: Creating connection
        THEN: ConnectionError is raised with the OSError details
        """
        # Given: Factory with mocked mavutil
        factory = SystemMavlinkConnectionFactory()

        with mock.patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink.mavutil.mavlink_connection"
        ) as mock_mavlink:
            mock_mavlink.side_effect = OSError("Device not found")

            # When/Then: Create connection and get ConnectionError containing root cause
            with pytest.raises(ConnectionError, match="Device not found"):
                factory.create(
                    device="/dev/invalid",
                    baudrate=115200,
                )
            mock_mavlink.assert_called_once()

    def test_system_mavlink_factory_preserves_timeouterror(self) -> None:
        """
        SystemMavlinkConnectionFactory surfaces TimeoutError causes.

        GIVEN: mavutil.mavlink_connection raises TimeoutError
        WHEN: Creating connection
        THEN: ConnectionError is raised with the TimeoutError details
        """
        # Given: Factory with mocked mavutil
        factory = SystemMavlinkConnectionFactory()

        with mock.patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink.mavutil.mavlink_connection"
        ) as mock_mavlink:
            mock_mavlink.side_effect = TimeoutError("Connection timeout")

            # When/Then: Create connection and get ConnectionError containing root cause
            with pytest.raises(ConnectionError, match="Connection timeout"):
                factory.create(
                    device="/dev/ttyUSB0",
                    baudrate=115200,
                    timeout=0.1,
                )
            mock_mavlink.assert_called_once()

    def test_system_mavlink_factory_preserves_valueerror(self) -> None:
        """
        SystemMavlinkConnectionFactory surfaces ValueError causes.

        GIVEN: mavutil.mavlink_connection raises ValueError (invalid parameters)
        WHEN: Creating connection
        THEN: ConnectionError is raised with the ValueError details
        """
        # Given: Factory with mocked mavutil
        factory = SystemMavlinkConnectionFactory()

        with mock.patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink.mavutil.mavlink_connection"
        ) as mock_mavlink:
            mock_mavlink.side_effect = ValueError("Invalid baudrate")

            # When/Then: Create connection and get ConnectionError containing root cause
            with pytest.raises(ConnectionError, match="Invalid baudrate"):
                factory.create(
                    device="/dev/ttyUSB0",
                    baudrate=99999,  # Invalid baudrate
                )
            mock_mavlink.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
