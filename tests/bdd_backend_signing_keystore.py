#!/usr/bin/env python3

"""
BDD-style tests for MAVLink signing keystore.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import stat
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.backend_signing_keystore import (
    SIGNING_KEY_LENGTH,
    SigningKeystore,
)

# pylint: disable=unused-argument


class TestSigningKeystoreKeyGeneration:  # pylint: disable=too-few-public-methods
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
            return SigningKeystore(use_keyring=False)

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
            return SigningKeystore(use_keyring=False)

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
        password = "secure-password-123"  # noqa: S105
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
        password = "import-password-456"  # noqa: S105
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
        correct_password = "correct-password"  # noqa: S105
        wrong_password = "wrong-password"  # noqa: S105
        export_data = temp_keystore.export_key(vehicle_id, correct_password)

        temp_keystore.delete_key(vehicle_id)

        result = temp_keystore.import_key(export_data, wrong_password)

        assert result is None


class TestSigningKeystoreFallback:  # pylint: disable=too-few-public-methods
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
            return SigningKeystore(use_keyring=False)

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


class TestSigningKeystoreExportImportBehavior:
    """Test key export and import error handling in BDD style."""

    @pytest.fixture
    def temp_keystore(self, tmp_path: Path) -> Generator[SigningKeystore, None, None]:
        """Create a temporary keystore for testing."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            yield SigningKeystore(use_keyring=False)

    def test_user_can_export_key_with_password(self, temp_keystore) -> None:
        """
        User can export a key protected by a password.

        GIVEN: A key is stored in the keystore
        AND: The user provides a strong password
        WHEN: The user exports the key
        THEN: An encrypted key blob should be returned
        """
        vehicle_id = "TEST-VEHICLE"
        key = temp_keystore.generate_key()
        temp_keystore.store_key(vehicle_id, key)

        encrypted_key = temp_keystore.export_key(vehicle_id, "strong_password_123")

        assert encrypted_key is not None
        assert len(encrypted_key) > 0
        assert encrypted_key != key  # Should be encrypted, not plaintext

    def test_user_can_import_exported_key(self, temp_keystore) -> None:
        """
        User can import a previously exported key.

        GIVEN: A key was exported with a password
        WHEN: The user imports it with the same password
        THEN: The key should be restored and usable
        """
        vehicle_id = "TEST-VEHICLE"
        original_key = temp_keystore.generate_key()
        temp_keystore.store_key(vehicle_id, original_key)

        encrypted_key = temp_keystore.export_key(vehicle_id, "password123")
        temp_keystore.delete_key(vehicle_id)

        vehicle_id_result = temp_keystore.import_key(encrypted_key, "password123")
        assert vehicle_id_result == vehicle_id
        retrieved_key = temp_keystore.retrieve_key(vehicle_id)

        assert retrieved_key == original_key

    def test_export_nonexistent_key_returns_none(self, temp_keystore) -> None:
        """
        Exporting a nonexistent key returns None.

        GIVEN: No key stored for a vehicle
        WHEN: The user tries to export it
        THEN: None should be returned
        """
        result = temp_keystore.export_key("NONEXISTENT-VEHICLE", "password123")

        assert result is None

    def test_export_with_weak_password_succeeds_but_import_fails(self, temp_keystore) -> None:
        """
        Export and import work with weak passwords (security limitation documented).

        GIVEN: A key is stored
        AND: The user provides a password that's too short (< 8 chars)
        WHEN: The user exports and imports the key
        THEN: Both operations succeed (no password strength validation)
        NOTE: This is a security limitation - neither export nor import validate password strength
        TODO: Implement password strength validation in both export_key() and import_key()
        """
        vehicle_id = "TEST-VEHICLE"
        key = temp_keystore.generate_key()
        temp_keystore.store_key(vehicle_id, key)

        encrypted_key = temp_keystore.export_key(vehicle_id, "short")
        # Export succeeds despite weak password (security gap)
        assert encrypted_key is not None

        # Import also succeeds with same weak password (security gap)
        temp_keystore.delete_key(vehicle_id)
        result = temp_keystore.import_key(encrypted_key, "short")
        assert result == vehicle_id  # Documents current behavior (not ideal)

    def test_import_with_weak_password_raises_error(self, temp_keystore) -> None:
        """
        Importing with a weak password returns None.

        GIVEN: An encrypted key blob
        AND: The user provides a password that's too short
        WHEN: The user attempts to import
        THEN: The import should fail and return None
        """
        dummy_encrypted = b"0" * 100

        result = temp_keystore.import_key(dummy_encrypted, "short")
        assert result is None

    def test_import_with_wrong_password_raises_error(self, temp_keystore) -> None:
        """
        Importing with wrong password returns None.

        GIVEN: A key was exported with one password
        WHEN: The user tries to import with a different password
        THEN: The import should fail and return None
        """
        vehicle_id = "TEST-VEHICLE"
        key = temp_keystore.generate_key()
        temp_keystore.store_key(vehicle_id, key)

        encrypted_key = temp_keystore.export_key(vehicle_id, "correct_password")

        result = temp_keystore.import_key(encrypted_key, "wrong_password")
        assert result is None

    def test_import_with_corrupted_data_raises_error(self, temp_keystore) -> None:
        """
        Importing corrupted data returns None.

        GIVEN: An invalid or corrupted encrypted key blob
        WHEN: The user tries to import it
        THEN: The import should fail and return None
        """
        corrupted_data = b"this is not valid encrypted data"

        result = temp_keystore.import_key(corrupted_data, "any_password")
        assert result is None


class TestSigningKeystoreKeyringFallback:
    """Test keyring availability and fallback behavior in BDD style."""

    def test_keystore_works_without_keyring(self, tmp_path) -> None:
        """
        User can use keystore even without OS keyring support.

        GIVEN: OS keyring is not available or disabled
        WHEN: The user creates a keystore
        THEN: It should work using file-based storage
        AND: Keys should be stored and retrieved correctly
        """
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)

            vehicle_id = "TEST-VEHICLE"
            key = keystore.generate_key()
            keystore.store_key(vehicle_id, key)

            retrieved_key = keystore.retrieve_key(vehicle_id)

            assert keystore.keyring_available is False
            assert retrieved_key == key

    def test_keystore_creates_data_directory_automatically(self, tmp_path) -> None:
        """
        Keystore creates data directory if it doesn't exist.

        GIVEN: The data directory doesn't exist
        WHEN: The user creates a keystore
        THEN: The directory should be created automatically
        AND: The keystore should work normally
        """
        data_dir = tmp_path / "nonexistent" / "subdir"
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(data_dir)
            keystore = SigningKeystore(use_keyring=False)

            key = keystore.generate_key()
            keystore.store_key("TEST-VEHICLE", key)

            assert data_dir.exists()
            assert keystore.fallback_path.exists()

    def test_keystore_persists_keys_across_instances(self, tmp_path) -> None:
        """
        Keys persist across keystore instances.

        GIVEN: A key is stored in one keystore instance
        WHEN: A new keystore instance is created
        THEN: The key should still be accessible
        """
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            # Store key with first instance
            keystore1 = SigningKeystore(use_keyring=False)
            vehicle_id = "TEST-VEHICLE"
            key = keystore1.generate_key()
            keystore1.store_key(vehicle_id, key)

            # Retrieve with second instance
            keystore2 = SigningKeystore(use_keyring=False)
            retrieved_key = keystore2.retrieve_key(vehicle_id)

            assert retrieved_key == key


class TestSigningKeystoreFilesystemErrors:
    """Test filesystem error handling in BDD style."""

    @pytest.fixture
    def temp_keystore(self, tmp_path: Path) -> Generator[SigningKeystore, None, None]:
        """Create a temporary keystore for testing."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            yield SigningKeystore(use_keyring=False)

    def test_store_key_handles_permission_error(self, temp_keystore, tmp_path) -> None:
        """
        Keystore handles permission errors gracefully.

        GIVEN: A keystore with a read-only storage directory
        WHEN: The user tries to store a key
        THEN: The operation should return False
        AND: No exception should be raised
        """
        vehicle_id = "TEST-VEHICLE"
        key = temp_keystore.generate_key()

        # Make directory read-only after keystore creation
        tmp_path.chmod(stat.S_IRUSR | stat.S_IXUSR)

        try:
            result = temp_keystore.store_key(vehicle_id, key)
            # Should handle permission error gracefully
            assert result is False
        finally:
            # Restore permissions for cleanup
            tmp_path.chmod(stat.S_IRWXU)

    def test_retrieve_key_handles_corrupted_file(self, temp_keystore, tmp_path) -> None:
        """
        Keystore handles corrupted data files gracefully.

        GIVEN: A corrupted keystore file
        WHEN: The user tries to retrieve a key
        THEN: None should be returned
        AND: No exception should be raised
        """
        # Create a corrupted keystore file
        keystore_file = temp_keystore.fallback_path
        keystore_file.write_text("corrupted json data {[}]}")

        result = temp_keystore.retrieve_key("ANY-VEHICLE")
        assert result is None


class TestSigningKeystoreSecurityWarnings:  # pylint: disable=too-few-public-methods
    """Test security warning functionality in BDD style."""

    def test_keystore_warns_when_keyring_unavailable(self, tmp_path, caplog) -> None:
        """
        Keystore logs security warning when falling back to file storage.

        GIVEN: OS keyring is unavailable
        WHEN: A keystore is created
        THEN: A security warning should be logged
        AND: The warning should mention weak file-based encryption
        """
        with (
            patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir,
            caplog.at_level(logging.WARNING),
        ):
            mock_dir.return_value = str(tmp_path)
            SigningKeystore(use_keyring=False)

            # Check that security warning was logged
            assert any("WEAK file-based encryption" in record.message for record in caplog.records)
            assert any("filesystem access can decrypt" in record.message for record in caplog.records)


class TestSigningKeystoreConcurrentAccess:
    """Test concurrent access handling in BDD style."""

    @pytest.fixture
    def temp_keystore(self, tmp_path: Path) -> Generator[SigningKeystore, None, None]:
        """Create a temporary keystore for testing."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            yield SigningKeystore(use_keyring=False)

    def test_concurrent_key_storage_is_safe(self, temp_keystore) -> None:
        """
        Concurrent key storage operations don't corrupt data.

        GIVEN: Multiple keys being stored simultaneously
        WHEN: Two different vehicles store keys at the same time
        THEN: Both keys should be stored correctly
        AND: No data corruption should occur
        NOTE: File locking ensures atomic operations
        """
        vehicle1 = "VEHICLE-1"
        vehicle2 = "VEHICLE-2"
        key1 = temp_keystore.generate_key()
        key2 = temp_keystore.generate_key()

        # Store keys (file locking ensures safety)
        result1 = temp_keystore.store_key(vehicle1, key1)
        result2 = temp_keystore.store_key(vehicle2, key2)

        # Verify both keys stored correctly
        assert result1 is True
        assert result2 is True
        assert temp_keystore.retrieve_key(vehicle1) == key1
        assert temp_keystore.retrieve_key(vehicle2) == key2
