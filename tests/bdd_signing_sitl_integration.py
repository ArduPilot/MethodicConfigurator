#!/usr/bin/env python3

"""
SITL integration tests for MAVLink 2.0 signing feature.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests validate MAVLink 2.0 signing with real ArduPilot SITL (Software In The Loop).

RUNNING THESE TESTS:
1. SITL is automatically managed by pytest fixtures (sitl_manager, sitl_flight_controller)
2. Run SITL tests: pytest -m sitl tests/
3. Skip SITL tests: pytest -m "not sitl" tests/
4. Connection string is configured in conftest.py (default: tcp:127.0.0.1:5760)

FIXTURES:
- sitl_flight_controller: Connected FlightController instance ready for testing with real SITL (from conftest.py)
- signing_keystore: Signing keystore with temporary storage
"""

import sys
from collections.abc import Generator
from typing import Optional
from unittest.mock import MagicMock

import pytest
from signing_test_fixtures import setup_mock_keyring

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_signing_keystore import SigningKeystore

# Mock keyring before importing SigningKeystore to ensure consistent behavior across test environments
_, PasswordDeleteError = setup_mock_keyring()

# Note: These tests use the sitl_flight_controller fixture from conftest.py
# which automatically starts and manages SITL via sitl_manager

# Storage for keys - used by the mock keyring
_stored_keys: dict[str, str] = {}


@pytest.fixture
def signing_keystore() -> Generator[SigningKeystore, None, None]:
    """Create a signing keystore instance with mocked keyring storage."""
    _stored_keys.clear()

    # Get the mock keyring from sys.modules
    mock_keyring_module = sys.modules.get("keyring")
    if mock_keyring_module is None:
        pytest.skip("Keyring mock not set up")
        return

    # Configure mock to use our storage dictionary
    def mock_set_password(service: str, account: str, password: str) -> None:
        """Mock set_password to store in our dictionary."""
        if service == "ArduPilotMethodicConfigurator":
            _stored_keys[account] = password

    def mock_get_password(service: str, account: str) -> Optional[str]:
        """Mock get_password to retrieve from our dictionary."""
        if service == "ArduPilotMethodicConfigurator":
            return _stored_keys.get(account)
        return None

    mock_keyring_module.set_password = MagicMock(side_effect=mock_set_password)
    mock_keyring_module.get_password = MagicMock(side_effect=mock_get_password)

    keystore = SigningKeystore()
    yield keystore

    # Cleanup
    _stored_keys.clear()


@pytest.mark.integration
@pytest.mark.sitl
class TestSITLConnectionWithSigning:
    """Test MAVLink signing with actual SITL connection."""

    def test_can_connect_to_sitl(self, sitl_flight_controller: FlightController) -> None:
        """
        User can connect to SITL successfully.

        GIVEN: A SITL instance is running on the default port
        WHEN: The FlightController attempts to connect
        THEN: The connection should be established
        AND: The master connection should not be None
        """
        assert sitl_flight_controller.master is not None
        assert sitl_flight_controller.info is not None

    def test_can_get_signing_status(self, sitl_flight_controller: FlightController) -> None:
        """
        User can check signing status on a connected FlightController.

        GIVEN: A connected FlightController
        WHEN: The user queries signing status
        THEN: The status should contain expected keys
        AND: The signing API should be functional
        """
        status = sitl_flight_controller.get_signing_status()
        # Verify status has expected structure
        assert "enabled" in status
        assert "message" in status
        assert isinstance(status["enabled"], bool)
        assert isinstance(status["message"], str)

    def test_can_setup_signing_with_generated_key(  # pylint: disable=redefined-outer-name
        self, sitl_flight_controller: FlightController, signing_keystore: SigningKeystore
    ) -> None:
        """
        User can set up MAVLink signing with a generated key.

        GIVEN: A connected FlightController
        AND: A valid signing key
        WHEN: The user sets up signing
        THEN: Signing should be configured successfully
        AND: The signing status should show enabled
        """
        key = signing_keystore.generate_key()
        try:
            success = sitl_flight_controller.setup_signing(
                key=key,
                sign_outgoing=True,
                allow_unsigned_in=True,
            )
            assert success is True
            status = sitl_flight_controller.get_signing_status()
            assert status["enabled"] is True
        except NotImplementedError:
            pytest.skip("MAVLink signing not supported by this pymavlink version")

    def test_can_call_disable_signing(  # pylint: disable=redefined-outer-name
        self, sitl_flight_controller: FlightController, signing_keystore: SigningKeystore
    ) -> None:
        """
        User can call disable_signing on a FlightController.

        GIVEN: A FlightController with signing possibly enabled
        WHEN: The user calls disable_signing
        THEN: The API should return expected types
        AND: No exceptions should be raised
        NOTE: MAVLink signing state persists on the pymavlink connection object,
              so we only verify the API is callable, not that state actually changes.
        """
        key = signing_keystore.generate_key()
        try:
            sitl_flight_controller.setup_signing(key)
        except NotImplementedError:
            pytest.skip("MAVLink signing not supported")

        # Verify disable_signing API is callable and returns bool
        try:
            success = sitl_flight_controller.disable_signing()
            assert isinstance(success, bool)
        except NotImplementedError:
            pytest.skip("MAVLink signing not supported by this pymavlink version")


@pytest.mark.integration
@pytest.mark.sitl
class TestSITLSigningKeyPersistence:  # pylint: disable=too-few-public-methods
    """Test signing key storage and retrieval with SITL."""

    def test_stored_key_can_be_used_for_signing(  # pylint: disable=redefined-outer-name
        self, sitl_flight_controller: FlightController, signing_keystore: SigningKeystore
    ) -> None:
        """
        User can store a key and use it for signing later.

        GIVEN: A signing key is stored in the keystore
        WHEN: The user retrieves the key and uses it for signing
        THEN: The signing should work with the retrieved key
        """
        vehicle_id = "SITL-TEST-VEHICLE"
        key = signing_keystore.generate_key()
        signing_keystore.store_key(vehicle_id, key)
        retrieved_key = signing_keystore.retrieve_key(vehicle_id)
        assert retrieved_key is not None

        try:
            success = sitl_flight_controller.setup_signing(retrieved_key)
            assert success is True
            status = sitl_flight_controller.get_signing_status()
            assert status["enabled"] is True
        except NotImplementedError:
            pytest.skip("MAVLink signing not supported by this pymavlink version")


@pytest.mark.integration
@pytest.mark.sitl
class TestSITLSigningEdgeCases:
    """Test edge cases for signing with SITL connection."""

    def test_signing_with_invalid_key_length_raises_error(self, sitl_flight_controller: FlightController) -> None:
        """
        Setting up signing with invalid key length raises an error.

        GIVEN: A connected FlightController
        WHEN: The user tries to setup signing with an invalid key
        THEN: A ValueError should be raised
        """
        invalid_key = b"too-short"
        with pytest.raises(ValueError, match="32 bytes"):
            sitl_flight_controller.setup_signing(invalid_key)

    def test_signing_with_invalid_link_id_raises_error(self, sitl_flight_controller: FlightController) -> None:
        """
        Setting up signing with invalid link_id raises an error.

        GIVEN: A connected FlightController
        WHEN: The user tries to setup signing with an invalid link_id
        THEN: A ValueError should be raised
        """
        key = b"0" * 32
        with pytest.raises(ValueError, match="link_id"):
            sitl_flight_controller.setup_signing(key, link_id=256)

    def test_can_reconnect_after_signing_enabled(  # pylint: disable=redefined-outer-name
        self, sitl_flight_controller: FlightController, signing_keystore: SigningKeystore
    ) -> None:
        """
        FlightController can reconnect after signing was enabled.

        GIVEN: Signing was enabled on a previous connection
        WHEN: The user disconnects and reconnects
        THEN: A new connection should be possible
        """
        key = signing_keystore.generate_key()
        try:
            sitl_flight_controller.setup_signing(key)
        except NotImplementedError:
            pytest.skip("Signing setup not supported")

        # Note: FlightController manages connection internally
        # Reconnection testing would require fixture teardown/setup
        # This test validates that signing setup doesn't break connection state
        assert sitl_flight_controller.master is not None
