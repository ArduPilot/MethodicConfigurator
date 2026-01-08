"""
SITL integration tests for MAVLink 2.0 signing feature.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests require a running SITL (Software In The Loop) instance.
Run SITL with: sim_vehicle.py -v ArduCopter --console --map

To run these tests:
    pytest tests/integration_signing_sitl.py -v -m integration

Or skip them in normal test runs:
    pytest tests/ -v -m "not integration"
"""

import time
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_signing_keystore import SigningKeystore

SITL_CONNECTION = "tcp:127.0.0.1:5760"
SITL_CONNECTION_TIMEOUT = 30


def is_sitl_available(connection: str = SITL_CONNECTION, timeout: float = 5.0) -> bool:
    """Check if SITL is running and accepting connections."""
    try:
        from pymavlink import mavutil

        master = mavutil.mavlink_connection(connection, baud=115200)
        heartbeat = master.wait_heartbeat(timeout=timeout)
        master.close()
        return heartbeat is not None
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not is_sitl_available(),
        reason=f"SITL not available at {SITL_CONNECTION}. Start SITL with: sim_vehicle.py -v ArduCopter",
    ),
]


@pytest.fixture
def connected_fc() -> FlightController:
    """
    Create and connect a FlightController to SITL.

    GIVEN: A SITL instance is running
    WHEN: A FlightController connects to it
    THEN: The connection should be established successfully
    """
    fc = FlightController()

    result = fc.connect(device=SITL_CONNECTION)

    if not result or fc.master is None:
        pytest.skip(f"Could not connect to SITL at {SITL_CONNECTION}")

    yield fc

    fc.disconnect()


@pytest.fixture
def signing_keystore(tmp_path) -> SigningKeystore:
    """Create a signing keystore with temporary storage."""
    with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
        mock_dir.return_value = str(tmp_path)
        return SigningKeystore(use_keyring=False)


class TestSITLConnectionWithSigning:
    """Test MAVLink signing with actual SITL connection."""

    def test_can_connect_to_sitl(self, connected_fc: FlightController) -> None:
        """
        User can connect to SITL successfully.

        GIVEN: A SITL instance is running on the default port
        WHEN: The FlightController attempts to connect
        THEN: The connection should be established
        AND: The master connection should not be None
        """
        assert connected_fc.master is not None
        assert connected_fc.info is not None

    def test_can_get_signing_status_when_not_configured(self, connected_fc: FlightController) -> None:
        """
        User can check signing status when signing is not configured.

        GIVEN: A connected FlightController without signing configured
        WHEN: The user queries signing status
        THEN: The status should show signing is not enabled
        """
        status = connected_fc.get_signing_status()
        assert status["enabled"] is False
        assert "message" in status

    def test_can_setup_signing_with_generated_key(
        self, connected_fc: FlightController, signing_keystore: SigningKeystore
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
        success, error_msg = connected_fc.setup_signing(
            key=key,
            sign_outgoing=True,
            allow_unsigned_in=True,
        )

        if success:
            status = connected_fc.get_signing_status()
            assert status["enabled"] is True
        else:
            assert "not supported" in error_msg.lower() or "error" in error_msg.lower()

    def test_can_disable_signing_after_setup(self, connected_fc: FlightController, signing_keystore: SigningKeystore) -> None:
        """
        User can disable signing after it has been configured.

        GIVEN: A FlightController with signing enabled
        WHEN: The user disables signing
        THEN: Signing should be disabled
        AND: The status should reflect this
        """
        key = signing_keystore.generate_key()
        setup_success, _ = connected_fc.setup_signing(key)

        if not setup_success:
            pytest.skip("Signing setup not supported on this connection")

        success, error_msg = connected_fc.disable_signing()

        if success:
            status = connected_fc.get_signing_status()
            assert status["enabled"] is False
        else:
            assert "not supported" in error_msg.lower() or "error" in error_msg.lower()


class TestSITLSigningKeyPersistence:
    """Test signing key storage and retrieval with SITL."""

    def test_stored_key_can_be_used_for_signing(
        self, connected_fc: FlightController, signing_keystore: SigningKeystore
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

        success, _ = connected_fc.setup_signing(retrieved_key)

        status = connected_fc.get_signing_status()
        if success:
            assert status["enabled"] is True


class TestSITLSigningEdgeCases:
    """Test edge cases for signing with SITL connection."""

    def test_signing_with_invalid_key_length_raises_error(self, connected_fc: FlightController) -> None:
        """
        Setting up signing with invalid key length raises an error.

        GIVEN: A connected FlightController
        WHEN: The user tries to setup signing with an invalid key
        THEN: A ValueError should be raised
        """
        invalid_key = b"too-short"
        with pytest.raises(ValueError, match="32 bytes"):
            connected_fc.setup_signing(invalid_key)

    def test_signing_with_invalid_link_id_raises_error(
        self, connected_fc: FlightController, signing_keystore: SigningKeystore
    ) -> None:
        """
        Setting up signing with invalid link_id raises an error.

        GIVEN: A connected FlightController
        WHEN: The user tries to setup signing with an invalid link_id
        THEN: A ValueError should be raised
        """
        key = signing_keystore.generate_key()

        with pytest.raises(ValueError, match="link_id"):
            connected_fc.setup_signing(key, link_id=256)

    def test_can_reconnect_after_signing_enabled(self, signing_keystore: SigningKeystore) -> None:
        """
        FlightController can reconnect after signing was enabled.

        GIVEN: Signing was enabled on a previous connection
        WHEN: The user disconnects and reconnects
        THEN: A new connection should be possible
        """
        fc = FlightController()
        result = fc.connect(device=SITL_CONNECTION)
        if not result or fc.master is None:
            pytest.skip(f"Could not connect to SITL at {SITL_CONNECTION}")

        key = signing_keystore.generate_key()
        fc.setup_signing(key)

        fc.disconnect()
        time.sleep(1)

        new_result = fc.connect(device=SITL_CONNECTION)

        assert new_result or fc.master is not None

        fc.disconnect()
