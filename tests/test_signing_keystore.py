#!/usr/bin/env python3

"""
Unit tests for MAVLink signing key storage.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tempfile
import unittest
from pathlib import Path

from ardupilot_methodic_configurator.backend_signing_keystore import SigningKeyStore


class TestSigningKeyStore(unittest.TestCase):
    """Test cases for SigningKeyStore class."""

    def setUp(self):
        """Set up test fixtures."""
        # Use temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.keystore = SigningKeyStore(storage_dir=Path(self.temp_dir))
        self.test_vehicle_id = "test_vehicle_001"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_key(self):
        """Test key generation."""
        key = SigningKeyStore.generate_key()
        self.assertEqual(len(key), 32, "Generated key should be 32 bytes")
        self.assertIsInstance(key, bytes, "Generated key should be bytes")

        # Generate another key and ensure it's different
        key2 = SigningKeyStore.generate_key()
        self.assertNotEqual(key, key2, "Generated keys should be unique")

    def test_store_and_retrieve_key(self):
        """Test storing and retrieving a key."""
        key = SigningKeyStore.generate_key()

        # Store the key
        success = self.keystore.store_key(self.test_vehicle_id, key)
        self.assertTrue(success, "Key storage should succeed")

        # Retrieve the key
        retrieved_key = self.keystore.retrieve_key(self.test_vehicle_id)
        self.assertIsNotNone(retrieved_key, "Key retrieval should succeed")
        self.assertEqual(key, retrieved_key, "Retrieved key should match original")

    def test_store_invalid_key_size(self):
        """Test storing a key with invalid size."""
        invalid_key = b"too_short"
        success = self.keystore.store_key(self.test_vehicle_id, invalid_key)
        self.assertFalse(success, "Storing invalid key size should fail")

    def test_store_empty_vehicle_id(self):
        """Test storing with empty vehicle ID."""
        key = SigningKeyStore.generate_key()
        success = self.keystore.store_key("", key)
        self.assertFalse(success, "Storing with empty vehicle ID should fail")

        success = self.keystore.store_key("   ", key)
        self.assertFalse(success, "Storing with whitespace vehicle ID should fail")

    def test_retrieve_nonexistent_key(self):
        """Test retrieving a key that doesn't exist."""
        retrieved_key = self.keystore.retrieve_key("nonexistent_vehicle")
        self.assertIsNone(retrieved_key, "Retrieving nonexistent key should return None")

    def test_delete_key(self):
        """Test deleting a key."""
        key = SigningKeyStore.generate_key()

        # Store the key
        self.keystore.store_key(self.test_vehicle_id, key)

        # Delete the key
        success = self.keystore.delete_key(self.test_vehicle_id)
        self.assertTrue(success, "Key deletion should succeed")

        # Verify it's gone
        retrieved_key = self.keystore.retrieve_key(self.test_vehicle_id)
        self.assertIsNone(retrieved_key, "Deleted key should not be retrievable")

    def test_list_vehicles(self):
        """Test listing vehicles with keys."""
        # Initially empty
        vehicles = self.keystore.list_vehicles_with_keys()
        self.assertEqual(len(vehicles), 0, "Initially should have no vehicles")

        # Add some keys
        vehicle_ids = ["vehicle_001", "vehicle_002", "vehicle_003"]
        for vehicle_id in vehicle_ids:
            key = SigningKeyStore.generate_key()
            self.keystore.store_key(vehicle_id, key)

        # List vehicles
        vehicles = self.keystore.list_vehicles_with_keys()
        self.assertEqual(len(vehicles), 3, "Should have 3 vehicles")
        for vehicle_id in vehicle_ids:
            self.assertIn(vehicle_id, vehicles, f"{vehicle_id} should be in list")

    def test_export_import_key(self):
        """Test exporting and importing a key."""
        key = SigningKeyStore.generate_key()
        password = "test_password_12345"

        # Store the key
        self.keystore.store_key(self.test_vehicle_id, key)

        # Export the key
        exported_data = self.keystore.export_key(self.test_vehicle_id, password)
        self.assertIsNotNone(exported_data, "Key export should succeed")
        self.assertIsInstance(exported_data, bytes, "Exported data should be bytes")

        # Delete the original key
        self.keystore.delete_key(self.test_vehicle_id)

        # Import the key back
        success, vehicle_id = self.keystore.import_key(exported_data, password)
        self.assertTrue(success, "Key import should succeed")
        self.assertEqual(vehicle_id, self.test_vehicle_id, "Imported vehicle ID should match")

        # Verify the key matches
        imported_key = self.keystore.retrieve_key(self.test_vehicle_id)
        self.assertEqual(key, imported_key, "Imported key should match original")

    def test_export_with_short_password(self):
        """Test exporting with a password that's too short."""
        key = SigningKeyStore.generate_key()
        self.keystore.store_key(self.test_vehicle_id, key)

        exported_data = self.keystore.export_key(self.test_vehicle_id, "short")
        self.assertIsNone(exported_data, "Export with short password should fail")

    def test_import_with_wrong_password(self):
        """Test importing with wrong password."""
        key = SigningKeyStore.generate_key()
        password = "correct_password_12345"
        wrong_password = "wrong_password_12345"

        self.keystore.store_key(self.test_vehicle_id, key)
        exported_data = self.keystore.export_key(self.test_vehicle_id, password)

        # Try to import with wrong password
        success, error = self.keystore.import_key(exported_data, wrong_password)
        self.assertFalse(success, "Import with wrong password should fail")
        self.assertIn("password", error.lower(), "Error should mention password")

    def test_multiple_vehicles(self):
        """Test managing keys for multiple vehicles."""
        vehicles = {
            "drone_001": SigningKeyStore.generate_key(),
            "drone_002": SigningKeyStore.generate_key(),
            "drone_003": SigningKeyStore.generate_key(),
        }

        # Store all keys
        for vehicle_id, key in vehicles.items():
            success = self.keystore.store_key(vehicle_id, key)
            self.assertTrue(success, f"Storing key for {vehicle_id} should succeed")

        # Retrieve and verify all keys
        for vehicle_id, original_key in vehicles.items():
            retrieved_key = self.keystore.retrieve_key(vehicle_id)
            self.assertEqual(original_key, retrieved_key, f"Key for {vehicle_id} should match")

        # List all vehicles
        vehicle_list = self.keystore.list_vehicles_with_keys()
        self.assertEqual(len(vehicle_list), 3, "Should have 3 vehicles")

    def test_key_persistence(self):
        """Test that keys persist across keystore instances."""
        key = SigningKeyStore.generate_key()

        # Store key with first instance
        self.keystore.store_key(self.test_vehicle_id, key)

        # Create new keystore instance with same storage directory
        keystore2 = SigningKeyStore(storage_dir=Path(self.temp_dir))

        # Retrieve key with second instance
        retrieved_key = keystore2.retrieve_key(self.test_vehicle_id)
        self.assertEqual(key, retrieved_key, "Key should persist across instances")


if __name__ == "__main__":
    unittest.main()
