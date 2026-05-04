#!/usr/bin/env python3

"""
BDD-style tests for MAVLink signing keystore (keyring-only implementation).

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import sys
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_signing_keystore import (
    SIGNING_KEY_LENGTH,
    SigningKeystore,
)

# pylint: disable=unused-argument, redefined-outer-name


# Mock keyring before importing SigningKeystore
mock_keyring = MagicMock()
mock_backend = MagicMock()
mock_keyring.get_keyring.return_value = mock_backend
mock_keyring.set_password = MagicMock()
mock_keyring.get_password = MagicMock()
mock_keyring.delete_password = MagicMock()


# Create proper exception classes for keyring.errors
class PasswordDeleteError(Exception):
    """Mock keyring password delete error."""


class MockKeyringErrors:  # pylint: disable=too-few-public-methods
    """Mock keyring.errors module."""

    PasswordDeleteError = PasswordDeleteError


mock_keyring.errors = MockKeyringErrors()

sys.modules["keyring"] = mock_keyring
sys.modules["keyring.errors"] = mock_keyring.errors


@pytest.fixture
def reset_keyring_mock() -> Generator[None, None, None]:
    """Reset keyring mock before each test."""
    mock_keyring.reset_mock()
    mock_keyring.get_keyring.return_value = mock_backend
    mock_keyring.set_password = MagicMock()
    mock_keyring.get_password = MagicMock()
    mock_keyring.delete_password = MagicMock()
    mock_keyring.errors = MockKeyringErrors()
    yield
    mock_keyring.reset_mock()


class TestSigningKeystoreInitialization:
    """Test keystore initialization and keyring availability."""

    def test_keystore_initializes_when_keyring_available(self, reset_keyring_mock) -> None:
        """Keystore initializes when OS keyring is available."""
        keystore = SigningKeystore()
        assert keystore is not None

    def test_keystore_raises_error_when_keyring_unavailable(self, reset_keyring_mock) -> None:
        """Keystore raises ConnectionError when OS keyring is not available."""
        mock_keyring.get_keyring.return_value = None

        with pytest.raises(ConnectionError, match="OS keyring is not available"):
            SigningKeystore()

    def test_keystore_raises_error_when_keyring_test_fails(self, reset_keyring_mock) -> None:
        """Keystore raises ConnectionError when keyring test operation fails."""
        mock_keyring.set_password.side_effect = Exception("Keyring error")

        with pytest.raises(ConnectionError):
            SigningKeystore()


class TestSigningKeystoreKeyGeneration:
    """Test key generation functionality."""

    @pytest.fixture
    def keystore(self, reset_keyring_mock) -> SigningKeystore:
        """Create a keystore with mocked keyring."""
        return SigningKeystore()

    def test_user_can_generate_secure_signing_key(self, keystore: SigningKeystore) -> None:
        """User can generate a cryptographically secure signing key."""
        key1 = keystore.generate_key()
        key2 = keystore.generate_key()

        assert len(key1) == SIGNING_KEY_LENGTH
        assert len(key2) == SIGNING_KEY_LENGTH
        assert key1 != key2


class TestSigningKeystoreStorage:
    """Test key storage and retrieval functionality."""

    @pytest.fixture
    def keystore(self, reset_keyring_mock) -> SigningKeystore:
        """Create a keystore with mocked keyring."""
        keystore = SigningKeystore()
        # Reset mock after initialization to clear test keyring calls
        mock_keyring.reset_mock()
        return keystore

    def test_user_can_store_key_for_vehicle(self, keystore: SigningKeystore) -> None:
        """
        User can store a signing key for a specific vehicle.

        GIVEN: A generated signing key for a specific vehicle
        WHEN: The key is stored in the keyring
        THEN: The key is successfully stored with correct service and vehicle ID
        """
        key = keystore.generate_key()
        vehicle_id = "TEST-VEHICLE-001"
        description = "Test key"

        result = keystore.store_key(vehicle_id, key, description=description)

        assert result is True
        # Verify keyring was called with correct parameters
        mock_keyring.set_password.assert_called_once()
        call_args = mock_keyring.set_password.call_args
        assert call_args[0][0] == "ardupilot_methodic_configurator_signing"  # service
        assert call_args[0][1] == vehicle_id  # username (vehicle_id)
        # Password should be base64-encoded key
        stored_password = call_args[0][2]
        assert base64.b64decode(stored_password) == key

    def test_user_can_retrieve_stored_key(self, keystore: SigningKeystore) -> None:
        """
        User can retrieve a previously stored signing key.

        GIVEN: A key stored in the keyring for a vehicle
        WHEN: The key is retrieved for that vehicle
        THEN: The retrieved key matches the original key exactly
        """
        original_key = keystore.generate_key()
        vehicle_id = "TEST-VEHICLE-002"

        # Simulate keyring returning base64-encoded key
        key_b64 = base64.b64encode(original_key).decode("ascii")
        mock_keyring.get_password.return_value = key_b64

        retrieved_key = keystore.retrieve_key(vehicle_id)

        assert retrieved_key is not None
        assert retrieved_key == original_key
        assert len(retrieved_key) == SIGNING_KEY_LENGTH
        # Verify keyring was called with correct parameters
        mock_keyring.get_password.assert_called_once()
        call_args = mock_keyring.get_password.call_args
        assert call_args[0][0] == "ardupilot_methodic_configurator_signing"
        assert call_args[0][1] == vehicle_id

    def test_user_can_delete_stored_key(self, keystore: SigningKeystore) -> None:
        """
        User can delete a stored signing key.

        GIVEN: A stored signing key for a vehicle
        WHEN: The key is deleted
        THEN: The delete succeeds and keyring is called correctly
        """
        vehicle_id = "TEST-VEHICLE-003"

        result = keystore.delete_key(vehicle_id)

        assert result is True
        mock_keyring.delete_password.assert_called_once()
        # Verify delete was called with correct parameters
        call_args = mock_keyring.delete_password.call_args
        assert call_args[0][0] == "ardupilot_methodic_configurator_signing"
        assert call_args[0][1] == vehicle_id

    def test_list_vehicles_returns_empty_list(self, keystore: SigningKeystore) -> None:
        """List vehicles returns empty list (keyring doesn't support enumeration)."""
        vehicles = keystore.list_vehicles()
        assert vehicles == []


class TestSigningKeystoreValidation:
    """Test input validation."""

    @pytest.fixture
    def keystore(self, reset_keyring_mock) -> SigningKeystore:
        """Create a keystore with mocked keyring."""
        keystore = SigningKeystore()
        # Reset mock after initialization to clear test keyring calls
        mock_keyring.reset_mock()
        return keystore

    def test_invalid_key_length_raises_error(self, keystore: SigningKeystore) -> None:
        """Storing a key with invalid length raises an error."""
        invalid_key = b"too-short"

        with pytest.raises(ValueError, match="32 bytes"):
            keystore.store_key("VEHICLE", invalid_key)

    def test_empty_vehicle_id_raises_error(self, keystore: SigningKeystore) -> None:
        """Storing a key with empty vehicle ID raises an error."""
        key = keystore.generate_key()

        with pytest.raises(ValueError, match="non-empty string"):
            keystore.store_key("", key)

    def test_retrieve_nonexistent_key_returns_none(self, keystore: SigningKeystore) -> None:
        """Retrieving a nonexistent key returns None."""
        mock_keyring.get_password.return_value = None
        result = keystore.retrieve_key("NONEXISTENT-VEHICLE")

        assert result is None

    def test_delete_nonexistent_key_handles_error(self, keystore: SigningKeystore) -> None:
        """Deleting a nonexistent key handles errors gracefully."""
        mock_keyring.delete_password.side_effect = PasswordDeleteError("Mock error")

        result = keystore.delete_key("NONEXISTENT-VEHICLE")

        assert result is False


class TestSigningKeystoreKeyRotation:
    """Test key rotation functionality."""

    @pytest.fixture
    def keystore(self, reset_keyring_mock) -> SigningKeystore:
        """Create a keystore with mocked keyring."""
        return SigningKeystore()

    def test_user_can_rotate_key(self, keystore: SigningKeystore) -> None:
        """
        User can rotate a signing key to generate a new one.

        GIVEN: A vehicle with an existing signing key
        WHEN: A key rotation is requested
        THEN: A new unique key is generated and stored
        """
        vehicle_id = "TEST-VEHICLE"
        mock_keyring.reset_mock()

        new_key = keystore.rotate_key(vehicle_id)

        assert new_key is not None
        assert len(new_key) == SIGNING_KEY_LENGTH
        # Verify new key was stored with set_password
        mock_keyring.set_password.assert_called_once()
        call_args = mock_keyring.set_password.call_args
        assert call_args[0][0] == "ardupilot_methodic_configurator_signing"
        assert call_args[0][1] == vehicle_id
        # Verify stored key matches generated key
        stored_b64 = call_args[0][2]
        assert base64.b64decode(stored_b64) == new_key


class TestSigningKeystoreErrorHandling:
    """Test error handling in keystore operations."""

    @pytest.fixture
    def keystore(self, reset_keyring_mock) -> SigningKeystore:
        """Create a keystore with mocked keyring."""
        return SigningKeystore()

    def test_store_key_raises_connection_error_on_failure(self, keystore: SigningKeystore) -> None:
        """
        Store operation raises ConnectionError when keyring fails.

        GIVEN: A keyring that fails on set_password
        WHEN: Attempting to store a key
        THEN: ConnectionError is raised with descriptive message
        """
        key = keystore.generate_key()
        keyring_error = RuntimeError("Credential storage unavailable")
        mock_keyring.set_password.side_effect = keyring_error

        with pytest.raises(ConnectionError) as exc_info:
            keystore.store_key("VEHICLE", key)

        assert "keyring" in str(exc_info.value).lower()

    def test_retrieve_key_raises_connection_error_on_failure(self, keystore: SigningKeystore) -> None:
        """
        Retrieve operation raises ConnectionError when keyring fails.

        GIVEN: A keyring that fails on get_password
        WHEN: Attempting to retrieve a key
        THEN: ConnectionError is raised
        """
        mock_keyring.get_password.side_effect = Exception("Keyring error")

        with pytest.raises(ConnectionError):
            keystore.retrieve_key("VEHICLE")

    def test_delete_key_raises_connection_error_on_failure(self, keystore: SigningKeystore) -> None:
        """
        Delete operation raises ConnectionError when keyring fails.

        GIVEN: A keyring that fails on delete_password
        WHEN: Attempting to delete a key (other than PasswordDeleteError)
        THEN: ConnectionError is raised
        """
        mock_keyring.delete_password.side_effect = RuntimeError("Keyring error")

        with pytest.raises(ConnectionError):
            keystore.delete_key("VEHICLE")


class TestSigningKeystoreWorkflow:
    """Test complete user workflows with keystore operations."""

    @pytest.fixture
    def keystore(self, reset_keyring_mock) -> SigningKeystore:
        """Create a keystore with mocked keyring."""
        keystore = SigningKeystore()
        # Reset mock after initialization to clear test keyring calls
        mock_keyring.reset_mock()
        return keystore

    def test_complete_key_lifecycle(self, keystore: SigningKeystore) -> None:
        """
        User can complete a full key lifecycle: generate, store, retrieve, delete.

        GIVEN: A new keystore instance
        WHEN: User performs generate → store → retrieve → delete sequence
        THEN: Each operation succeeds and data is preserved correctly
        """
        vehicle_id = "AIRCRAFT-01"

        # Step 1: Generate key
        original_key = keystore.generate_key()
        assert len(original_key) == SIGNING_KEY_LENGTH

        # Step 2: Store key
        store_result = keystore.store_key(vehicle_id, original_key, description="Aircraft signing key")
        assert store_result is True

        # Step 3: Retrieve key
        key_b64 = base64.b64encode(original_key).decode("ascii")
        mock_keyring.get_password.return_value = key_b64
        retrieved_key = keystore.retrieve_key(vehicle_id)
        assert retrieved_key == original_key

        # Step 4: Delete key
        mock_keyring.reset_mock()
        delete_result = keystore.delete_key(vehicle_id)
        assert delete_result is True
        mock_keyring.delete_password.assert_called_once()

    def test_multiple_vehicles_have_independent_keys(self, keystore: SigningKeystore) -> None:
        """
        Different vehicles maintain independent signing keys.

        GIVEN: A keystore managing multiple vehicles
        WHEN: Storing different keys for different vehicles
        THEN: Each vehicle's key is stored independently with correct vehicle ID
        """
        vehicles = ["COPTER-01", "PLANE-01", "ROVER-01"]
        keys = [keystore.generate_key() for _ in vehicles]

        # Store keys for each vehicle
        for vehicle_id, key in zip(vehicles, keys):
            result = keystore.store_key(vehicle_id, key)
            assert result is True

        # Verify each set_password call used correct vehicle_id
        assert mock_keyring.set_password.call_count == 3
        for i, (vehicle_id, key) in enumerate(zip(vehicles, keys)):
            call_args = mock_keyring.set_password.call_args_list[i]
            assert call_args[0][1] == vehicle_id  # Check vehicle_id parameter
            assert base64.b64decode(call_args[0][2]) == key  # Verify stored key


class TestSigningKeystoreEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def keystore(self, reset_keyring_mock) -> SigningKeystore:
        """Create a keystore with mocked keyring."""
        keystore = SigningKeystore()
        # Reset mock after initialization to clear test keyring calls
        mock_keyring.reset_mock()
        return keystore

    def test_retrieve_nonexistent_key_returns_none(self, keystore: SigningKeystore) -> None:
        """
        Retrieving a key that doesn't exist returns None gracefully.

        GIVEN: A vehicle with no stored key
        WHEN: Attempting to retrieve a key
        THEN: Returns None indicating no key was found
        """
        mock_keyring.get_password.return_value = None

        result = keystore.retrieve_key("UNKNOWN-VEHICLE")
        assert result is None
        mock_keyring.get_password.assert_called_once()

    def test_store_and_retrieve_preserves_key_bytes(self, keystore: SigningKeystore) -> None:
        """
        Storing and retrieving a key preserves all bytes exactly.

        GIVEN: A key with specific byte patterns
        WHEN: Storing and retrieving through base64 encoding
        THEN: All 32 bytes are preserved exactly
        """
        # Create key with specific byte patterns
        test_bytes = bytes(range(256))[:SIGNING_KEY_LENGTH]

        store_result = keystore.store_key("TEST-VEHICLE", test_bytes)
        assert store_result is True

        # Verify stored bytes
        call_args = mock_keyring.set_password.call_args
        stored_b64 = call_args[0][2]
        decoded_bytes = base64.b64decode(stored_b64)
        assert decoded_bytes == test_bytes
