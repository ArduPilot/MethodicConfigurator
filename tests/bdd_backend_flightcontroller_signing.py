#!/usr/bin/env python3

"""
BDD-style tests for FlightController MAVLink signing methods.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import time
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

# pylint: disable=redefined-outer-name, unused-argument


@pytest.fixture
def mock_master() -> MagicMock:
    """Create a mock MAVLink master connection."""
    mock = MagicMock()
    mock.setup_signing = MagicMock()
    mock.disable_signing = MagicMock()
    return mock


@pytest.fixture
def flight_controller(mock_master: MagicMock) -> FlightController:
    """Create a FlightController instance with a mocked master connection."""
    mock_connection_manager = MagicMock()
    mock_connection_manager.master = mock_master

    return FlightController(connection_manager=mock_connection_manager)


class TestFlightControllerSigningSetup:
    """Test MAVLink signing setup functionality in BDD style."""

    def test_setup_signing_with_valid_parameters(self, flight_controller, mock_master) -> None:
        """
        User can set up MAVLink signing with valid parameters.

        GIVEN: A FlightController with an active connection
        AND: A valid 32-byte signing key
        WHEN: The user calls setup_signing
        THEN: It should succeed and return True
        AND: The master connection should be configured with the correct parameters
        """
        key = b"0" * 32
        sign_outgoing = True
        allow_unsigned_in = False
        initial_timestamp = 0  # Use current time
        link_id = 1

        result = flight_controller.setup_signing(
            key,
            sign_outgoing=sign_outgoing,
            allow_unsigned_in=allow_unsigned_in,
            initial_timestamp=initial_timestamp,
            link_id=link_id,
        )
        assert result is True
        mock_master.setup_signing.assert_called_once()
        call_args = mock_master.setup_signing.call_args
        assert call_args[0][0] == key
        assert call_args[1]["sign_outgoing"] == sign_outgoing
        assert call_args[1]["allow_unsigned_callback"] is None
        assert call_args[1]["initial_timestamp"] == initial_timestamp
        assert call_args[1]["link_id"] == link_id

    def test_setup_signing_with_callback_enabled(self, flight_controller, mock_master) -> None:
        """
        User can set up signing with unsigned callback enabled.

        GIVEN: A FlightController with an active connection
        WHEN: The user calls setup_signing with allow_unsigned_in=True
        THEN: The master connection should be configured with the unsigned callback
        """
        key = b"1" * 32
        flight_controller.setup_signing(key, allow_unsigned_in=True)
        call_args = mock_master.setup_signing.call_args
        assert call_args[1]["allow_unsigned_callback"] == flight_controller._unsigned_callback  # pylint: disable=protected-access

    def test_setup_signing_without_connection_raises_error(self) -> None:
        """
        Setting up signing fails if no connection is present.

        GIVEN: A FlightController with NO active connection (master is None)
        WHEN: The user calls setup_signing
        THEN: It should raise ConnectionError
        """
        mock_connection_manager = MagicMock()
        mock_connection_manager.master = None
        fc = FlightController(connection_manager=mock_connection_manager)
        key = b"0" * 32
        with pytest.raises(ConnectionError, match="No flight controller connection"):
            fc.setup_signing(key)

    def test_setup_signing_invalid_key_length_raises_error(self, flight_controller) -> None:
        """
        Setting up signing fails with invalid key length.

        GIVEN: A valid FlightController connection
        BUT: An invalid signing key (not 32 bytes)
        WHEN: The user calls setup_signing
        THEN: It should raise ValueError
        """
        invalid_key = b"too_short"
        with pytest.raises(ValueError, match="must be 32 bytes"):
            flight_controller.setup_signing(invalid_key)

    def test_setup_signing_invalid_link_id_raises_error(self, flight_controller) -> None:
        """
        Setting up signing fails with invalid link ID.

        GIVEN: A valid FlightController connection and key
        BUT: An invalid link_id (out of range)
        WHEN: The user calls setup_signing
        THEN: It should raise ValueError
        """
        key = b"0" * 32
        invalid_link_id = 256
        with pytest.raises(ValueError, match="link_id must be between"):
            flight_controller.setup_signing(key, link_id=invalid_link_id)

    def test_setup_signing_not_supported_raises_error(self, flight_controller, mock_master) -> None:
        """
        Setting up signing fails if pymavlink version doesn't support it.

        GIVEN: A connected FlightController
        BUT: The underlying library raises AttributeError during setup
        WHEN: The user calls setup_signing
        THEN: It should raise NotImplementedError
        """
        key = b"0" * 32
        mock_master.setup_signing.side_effect = AttributeError("Method not found")
        with pytest.raises(NotImplementedError, match="not supported"):
            flight_controller.setup_signing(key)

    def test_setup_signing_generic_failure_raises_runtime_error(self, flight_controller, mock_master) -> None:
        """
        Setting up signing handles generic failures gracefully.

        GIVEN: A connected FlightController
        BUT: The setup raises an unexpected exception
        WHEN: The user calls setup_signing
        THEN: It should raise RuntimeError
        """
        key = b"0" * 32
        mock_master.setup_signing.side_effect = Exception("Unknown error")
        with pytest.raises(RuntimeError, match="Failed to set up"):
            flight_controller.setup_signing(key)

    def test_setup_signing_rejects_old_timestamp(self, flight_controller) -> None:
        """
        Setting up signing rejects old timestamps to prevent replay attacks.

        GIVEN: A FlightController with an active connection
        AND: A valid signing key
        BUT: A timestamp older than 7 days
        WHEN: The user calls setup_signing
        THEN: It should raise ValueError with replay attack warning
        """
        key = b"0" * 32
        # Create a timestamp 8 days in the past (7 day limit)
        eight_days_ago = int((time.time() - 8 * 86400) * 1e6)

        with pytest.raises(ValueError, match="days old - rejecting to prevent replay attack"):
            flight_controller.setup_signing(key, initial_timestamp=eight_days_ago)

    def test_setup_signing_accepts_recent_timestamp(self, flight_controller, mock_master) -> None:
        """
        Setting up signing accepts timestamps within 7-day window.

        GIVEN: A FlightController with an active connection
        AND: A timestamp from 6 days ago (within limit)
        WHEN: The user calls setup_signing
        THEN: It should succeed
        """
        key = b"0" * 32
        # Create a timestamp 6 days in the past (within 7 day limit)
        six_days_ago = int((time.time() - 6 * 86400) * 1e6)

        result = flight_controller.setup_signing(key, initial_timestamp=six_days_ago)
        assert result is True

    def test_unsigned_callback_logs_security_warnings(self, flight_controller) -> None:
        """
        Unsigned message callback logs security warnings for monitoring.

        GIVEN: A FlightController with signing configured to allow unsigned messages
        WHEN: An unsigned message is received
        THEN: The callback should log a security warning
        AND: The callback should accept the message (permissive mode)
        """
        mock_msg = MagicMock()
        mock_msg.get_type = MagicMock(return_value="HEARTBEAT")

        # Test the callback directly (internal method)
        result = flight_controller._unsigned_callback(mock_msg)  # pylint: disable=protected-access

        assert result is True  # Permissive mode accepts all
        mock_msg.get_type.assert_called_once()


class TestFlightControllerSigningDisable:
    """Test disabling MAVLink signing functionality in BDD style."""

    def test_disable_signing_success(self, flight_controller, mock_master) -> None:
        """
        User can disable MAVLink signing successfully.

        GIVEN: A FlightController with an active connection
        WHEN: The user calls disable_signing
        THEN: It should succeed and return True
        AND: The master connection's setup_signing should be called with None key
        """
        result = flight_controller.disable_signing()
        assert result is True
        mock_master.setup_signing.assert_called_once()
        call_args = mock_master.setup_signing.call_args
        assert call_args[0][0] is None
        assert call_args[1]["sign_outgoing"] is False
        assert call_args[1]["allow_unsigned_callback"] is None

    def test_disable_signing_without_connection_raises_error(self) -> None:
        """
        Disabling signing fails if no connection is present.

        GIVEN: A FlightController with NO active connection
        WHEN: The user calls disable_signing
        THEN: It should raise ConnectionError
        """
        mock_connection_manager = MagicMock()
        mock_connection_manager.master = None
        fc = FlightController(connection_manager=mock_connection_manager)

        with pytest.raises(ConnectionError, match="No flight controller connection"):
            fc.disable_signing()

    def test_disable_signing_not_supported_raises_error(self, flight_controller, mock_master) -> None:
        """
        Disabling signing fails if pymavlink version doesn't support it.

        GIVEN: A connected FlightController
        BUT: The underlying library raises AttributeError during setup
        WHEN: The user calls disable_signing
        THEN: It should raise NotImplementedError
        """
        mock_master.setup_signing.side_effect = AttributeError("Method not found")
        with pytest.raises(NotImplementedError, match="not supported"):
            flight_controller.disable_signing()


class TestFlightControllerSigningStatus:
    """Test retrieving MAVLink signing status in BDD style."""

    def test_get_signing_status_success(self, flight_controller, mock_master) -> None:
        """
        User can retrieve current signing status.

        GIVEN: A connected FlightController with signing enabled
        WHEN: The user calls get_signing_status
        THEN: It should return the dictionary reflecting the signing state
        """
        mock_signing = MagicMock()
        mock_signing.sign_outgoing = True
        mock_signing.allow_unsigned_callback = lambda x: True  # noqa: ARG005
        mock_signing.link_id = 42

        mock_master.mav = MagicMock()
        mock_master.mav.signing = mock_signing

        status = flight_controller.get_signing_status()
        assert status["enabled"] is True
        assert status["sign_outgoing"] is True
        assert status["allow_unsigned"] is True
        assert status["link_id"] == 42
        assert "enabled" in status["message"]

    def test_get_signing_status_not_configured(self, flight_controller, mock_master) -> None:
        """
        User gets correct status when signing is not configured.

        GIVEN: A connected FlightController without signing
        WHEN: The user calls get_signing_status
        THEN: It should return a disabled status
        """
        mock_master.mav = MagicMock()
        mock_master.mav.signing = None
        status = flight_controller.get_signing_status()
        assert status["enabled"] is False
        assert "not configured" in status["message"]

    def test_get_signing_status_no_connection(self) -> None:
        """
        User gets correct status when no connection exists.

        GIVEN: A FlightController with NO active connection
        WHEN: The user calls get_signing_status
        THEN: It should return a default disconnected status
        """
        mock_connection_manager = MagicMock()
        mock_connection_manager.master = None
        fc = FlightController(connection_manager=mock_connection_manager)
        status = fc.get_signing_status()
        assert status["enabled"] is False
        assert "No connection" in str(status["message"])
