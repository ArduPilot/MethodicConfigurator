#!/usr/bin/env python3

"""
BDD-style tests for MAVLink signing keystore.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_signing_keystore import (
    SIGNING_KEY_LENGTH,
    SigningKeystore,
    StoredKey,
)


class TestSigningKeystoreKeyGeneration:
    """Test key generation functionality in BDD style."""

    def test_user_can_generate_secure_signing_key(self) -> None:
        """
        User can generate a cryptographically secure signing key.

        GIVEN: A signing keystore is available
        WHEN: The user generates a new signing key
        THEN: A 32-byte key suitable for HMAC-SHA256 should be returned
        AND: Each generated key should be unique
        """
        # Arrange: Create keystore
        keystore = SigningKeystore(use_keyring=False)

        # Act: Generate multiple keys
        key1 = keystore.generate_key()
        key2 = keystore.generate_key()

        # Assert: Keys are correct length and unique
        assert len(key1) == SIGNING_KEY_LENGTH
        assert len(key2) == SIGNING_KEY_LENGTH
        assert key1 != key2  # Keys should be unique


class TestSigningKeystoreStorage:
    """Test key storage and retrieval functionality in BDD style."""

    @pytest.fixture
    def temp_keystore(self, tmp_path) -> SigningKeystore:
        """Create a keystore using temporary storage."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)
            return keystore

    def test_user_can_store_key_for_vehicle(self, temp_keystore) -> None:
        """
        User can store a signing key for a specific vehicle.

        GIVEN: A signing keystore with a generated key
        WHEN: The user stores the key for a vehicle ID
        THEN: The key should be stored successfully
        AND: The function should return True
        """
        key = temp_keystore.generate_key()
        vehicle_id = "TEST-VEHICLE-001"

        result = temp_keystore.store_key(vehicle_id, key, description="Test key")

        # Assert: Key was stored
        assert result is True

    def test_user_can_retrieve_stored_key(self, temp_keystore) -> None:
        """
        User can retrieve a previously stored signing key.

        GIVEN: A signing key has been stored for a vehicle
        WHEN: The user retrieves the key using the vehicle ID
        THEN: The original key should be returned
        AND: The key should match exactly what was stored
        """
        original_key = temp_keystore.generate_key()
        vehicle_id = "TEST-VEHICLE-002"
        temp_keystore.store_key(vehicle_id, original_key)

        retrieved_key = temp_keystore.retrieve_key(vehicle_id)

        assert retrieved_key is not None
        assert retrieved_key == original_key

    def test_user_can_delete_stored_key(self, temp_keystore) -> None:
        """
        User can delete a stored signing key.

        GIVEN: A signing key has been stored for a vehicle
        WHEN: The user deletes the key
        THEN: The key should be removed from storage
        AND: Subsequent retrieval should return None
        """
        key = temp_keystore.generate_key()
        vehicle_id = "TEST-VEHICLE-003"
        temp_keystore.store_key(vehicle_id, key)
        deleted = temp_keystore.delete_key(vehicle_id)

        assert deleted is True
        assert deleted is True
        assert temp_keystore.retrieve_key(vehicle_id) is None

    def test_user_can_list_vehicles_with_keys(self, temp_keystore) -> None:
        """
        User can list all vehicles with stored signing keys.

        GIVEN: Multiple vehicles have stored signing keys
        WHEN: The user lists all vehicles
        THEN: All vehicle IDs with keys should be returned
        AND: The list should be sorted alphabetically
        """
        vehicles = ["VEHICLE-C", "VEHICLE-A", "VEHICLE-B"]
        for vehicle_id in vehicles:
            key = temp_keystore.generate_key()
            temp_keystore.store_key(vehicle_id, key)

        listed_vehicles = temp_keystore.list_vehicles()

        assert len(listed_vehicles) == 3
        assert listed_vehicles == sorted(vehicles)

    def test_keys_are_isolated_per_vehicle(self, temp_keystore) -> None:
        """
        Keys are properly isolated between different vehicles.

        GIVEN: Different keys stored for different vehicles
        WHEN: Keys are retrieved for each vehicle
        THEN: Each vehicle should get its own unique key
        AND: Keys should not be mixed between vehicles
        """
        key1 = temp_keystore.generate_key()
        key2 = temp_keystore.generate_key()
        temp_keystore.store_key("VEHICLE-1", key1)
        temp_keystore.store_key("VEHICLE-2", key2)
        retrieved1 = temp_keystore.retrieve_key("VEHICLE-1")
        retrieved2 = temp_keystore.retrieve_key("VEHICLE-2")

        assert retrieved1 == key1
        assert retrieved2 == key2
        assert retrieved1 != retrieved2


class TestSigningKeystoreExportImport:
    """Test key export and import functionality in BDD style."""

    @pytest.fixture
    def temp_keystore(self, tmp_path) -> SigningKeystore:
        """Create a keystore using temporary storage."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)
            return keystore

    def test_user_can_export_key_with_password(self, temp_keystore) -> None:
        """
        User can export a signing key with password protection.

        GIVEN: A signing key is stored for a vehicle
        WHEN: The user exports the key with a password
        THEN: An encrypted export string should be returned
        AND: The export should contain the vehicle ID
        """
        key = temp_keystore.generate_key()
        vehicle_id = "EXPORT-VEHICLE"
        temp_keystore.store_key(vehicle_id, key)
        password = "secure-password-123"
        export_data = temp_keystore.export_key(vehicle_id, password)

        assert export_data is not None
        assert len(export_data) > 0

    def test_user_can_import_key_with_password(self, temp_keystore) -> None:
        """
        User can import a signing key using the correct password.

        GIVEN: A key has been exported with password protection
        WHEN: The user imports the key with the correct password
        THEN: The key should be imported successfully
        AND: The imported key should match the original
        """
        original_key = temp_keystore.generate_key()
        vehicle_id = "IMPORT-VEHICLE"
        temp_keystore.store_key(vehicle_id, original_key)
        password = "import-password-456"
        export_data = temp_keystore.export_key(vehicle_id, password)

        temp_keystore.delete_key(vehicle_id)

        imported_vehicle = temp_keystore.import_key(export_data, password)

        assert imported_vehicle == vehicle_id
        imported_key = temp_keystore.retrieve_key(vehicle_id)
        assert imported_key == original_key

    def test_invalid_password_fails_import(self, temp_keystore) -> None:
        """
        Import fails with incorrect password.

        GIVEN: A key has been exported with password protection
        WHEN: The user tries to import with an incorrect password
        THEN: The import should fail
        AND: None should be returned
        """
        key = temp_keystore.generate_key()
        vehicle_id = "WRONG-PASSWORD-VEHICLE"
        temp_keystore.store_key(vehicle_id, key)
        correct_password = "correct-password"
        wrong_password = "wrong-password"
        export_data = temp_keystore.export_key(vehicle_id, correct_password)

        temp_keystore.delete_key(vehicle_id)

        result = temp_keystore.import_key(export_data, wrong_password)

        assert result is None


class TestSigningKeystoreFallback:
    """Test keyring fallback functionality in BDD style."""

    def test_system_falls_back_to_file_when_keyring_unavailable(self, tmp_path) -> None:
        """
        System falls back to encrypted file storage when keyring is unavailable.

        GIVEN: OS keyring is not available
        WHEN: The user stores a signing key
        THEN: The key should be stored in an encrypted file
        AND: The key should be retrievable from the file
        """
        with (
            patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir,
        ):
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)

            assert keystore.keyring_available is False

            key = keystore.generate_key()
            vehicle_id = "FALLBACK-VEHICLE"
            result = keystore.store_key(vehicle_id, key)
            retrieved = keystore.retrieve_key(vehicle_id)

            assert result is True
            assert retrieved == key
            assert keystore.fallback_path.exists()


class TestSigningKeystoreValidation:
    """Test input validation in BDD style."""

    @pytest.fixture
    def temp_keystore(self, tmp_path) -> SigningKeystore:
        """Create a keystore using temporary storage."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)
            return keystore

    def test_invalid_key_length_raises_error(self, temp_keystore) -> None:
        """
        Storing a key with invalid length raises an error.

        GIVEN: A key with incorrect length
        WHEN: The user tries to store it
        THEN: A ValueError should be raised
        AND: The error message should indicate the length requirement
        """
        invalid_key = b"too-short"

        with pytest.raises(ValueError, match="32 bytes"):
            temp_keystore.store_key("VEHICLE", invalid_key)

    def test_empty_vehicle_id_raises_error(self, temp_keystore) -> None:
        """
        Storing a key with empty vehicle ID raises an error.

        GIVEN: A valid key but empty vehicle ID
        WHEN: The user tries to store it
        THEN: A ValueError should be raised
        """
        key = temp_keystore.generate_key()

        with pytest.raises(ValueError, match="cannot be empty"):
            temp_keystore.store_key("", key)

    def test_retrieve_nonexistent_key_returns_none(self, temp_keystore) -> None:
        """
        Retrieving a nonexistent key returns None.

        GIVEN: No key stored for a vehicle
        WHEN: The user tries to retrieve the key
        THEN: None should be returned
        AND: No error should be raised
        """
        result = temp_keystore.retrieve_key("NONEXISTENT-VEHICLE")

        assert result is None

    def test_delete_nonexistent_key_returns_false(self, temp_keystore) -> None:
        """
        Deleting a nonexistent key returns False.

        GIVEN: No key stored for a vehicle
        WHEN: The user tries to delete the key
        THEN: False should be returned
        AND: No error should be raised
        """
        result = temp_keystore.delete_key("NONEXISTENT-VEHICLE")

        assert result is False
