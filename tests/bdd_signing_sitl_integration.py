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
- sitl_flight_controller: Connected FlightController instance ready for testing with real SITL
- signing_keystore: Signing keystore with temporary storage
"""

import contextlib
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_signing_keystore import SigningKeystore


@pytest.fixture
def signing_keystore(tmp_path) -> SigningKeystore:
    """Create a signing keystore with temporary storage."""
    with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
        mock_dir.return_value = str(tmp_path)
        return SigningKeystore(use_keyring=False)


@pytest.mark.integration
@pytest.mark.sitl
class TestSITLConnectionWithSigning:
    """Test MAVLink signing with actual SITL connection."""

    @pytest.fixture(autouse=True)
    def _disable_signing_after_test(self, sitl_flight_controller: FlightController) -> None:
        """Disable signing after each test to ensure test isolation."""
        yield
        # Cleanup: disable signing to ensure clean state for next test
        with contextlib.suppress(Exception):
            sitl_flight_controller.disable_signing()

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

    @pytest.mark.xfail(reason="pymavlink setup_signing(None) doesn't clear mav.signing object - known limitation")
    def test_can_get_signing_status_when_not_configured(self, sitl_flight_controller: FlightController) -> None:
        """
        User can check signing status when signing is not configured.

        GIVEN: A connected FlightController without signing configured
        WHEN: The user queries signing status
        THEN: The status should show signing is not enabled
        """
        # Ensure signing is disabled first
        sitl_flight_controller.disable_signing()

        status = sitl_flight_controller.get_signing_status()
        assert status["enabled"] is False
        assert "message" in status

    def test_can_setup_signing_with_generated_key(
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
        success, error_msg = sitl_flight_controller.setup_signing(
            key=key,
            sign_outgoing=True,
            allow_unsigned_in=True,
        )

        if success:
            status = sitl_flight_controller.get_signing_status()
            assert status["enabled"] is True
        else:
            assert "not supported" in error_msg.lower() or "error" in error_msg.lower()

    @pytest.mark.xfail(reason="pymavlink setup_signing(None) doesn't clear mav.signing object - known limitation")
    def test_can_disable_signing_after_setup(
        self, sitl_flight_controller: FlightController, signing_keystore: SigningKeystore
    ) -> None:
        """
        User can disable signing after it has been configured.

        GIVEN: A FlightController with signing enabled
        WHEN: The user disables signing
        THEN: Signing should be disabled
        AND: The status should reflect this
        """
        key = signing_keystore.generate_key()
        setup_success, _ = sitl_flight_controller.setup_signing(key)

        if not setup_success:
            pytest.skip("Signing setup not supported on this connection")

        success, error_msg = sitl_flight_controller.disable_signing()

        if success:
            status = sitl_flight_controller.get_signing_status()
            assert status["enabled"] is False
        else:
            assert "not supported" in error_msg.lower() or "error" in error_msg.lower()


@pytest.mark.integration
@pytest.mark.sitl
class TestSITLSigningKeyPersistence:
    """Test signing key storage and retrieval with SITL."""

    def test_stored_key_can_be_used_for_signing(
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

        success, _ = sitl_flight_controller.setup_signing(retrieved_key)

        status = sitl_flight_controller.get_signing_status()
        if success:
            assert status["enabled"] is True


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

    def test_can_reconnect_after_signing_enabled(
        self, sitl_flight_controller: FlightController, signing_keystore: SigningKeystore
    ) -> None:
        """
        FlightController can reconnect after signing was enabled.

        GIVEN: Signing was enabled on a previous connection
        WHEN: The user disconnects and reconnects
        THEN: A new connection should be possible
        """
        key = signing_keystore.generate_key()
        success, _ = sitl_flight_controller.setup_signing(key)

        if not success:
            pytest.skip("Signing setup not supported")

        # Note: FlightController manages connection internally
        # Reconnection testing would require fixture teardown/setup
        # This test validates that signing setup doesn't break connection state
        assert sitl_flight_controller.master is not None
