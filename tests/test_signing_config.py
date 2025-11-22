#!/usr/bin/env python3

"""
Unit tests for MAVLink signing configuration data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest

from ardupilot_methodic_configurator.data_model_signing_config import SigningConfig


class TestSigningConfig(unittest.TestCase):
    """Test cases for SigningConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SigningConfig()
        self.assertFalse(config.enabled, "Signing should be disabled by default")
        self.assertEqual(config.vehicle_id, "", "Vehicle ID should be empty by default")
        self.assertTrue(config.enforce_signing, "Enforce signing should be True by default")
        self.assertFalse(config.allow_unsigned_callback, "Allow unsigned callback should be False by default")
        self.assertEqual(config.timestamp_tolerance_ms, 60000, "Timestamp tolerance should be 60000ms by default")
        self.assertFalse(config.is_active, "Signing should not be active by default")
        self.assertEqual(config.last_error, "", "Last error should be empty by default")

    def test_validate_disabled_config(self):
        """Test validation of disabled configuration."""
        config = SigningConfig(enabled=False)
        is_valid, error = config.validate()
        self.assertTrue(is_valid, "Disabled config should be valid")
        self.assertEqual(error, "", "Error should be empty for valid config")

    def test_validate_enabled_without_vehicle_id(self):
        """Test validation fails when enabled without vehicle ID."""
        config = SigningConfig(enabled=True, vehicle_id="")
        is_valid, error = config.validate()
        self.assertFalse(is_valid, "Config should be invalid without vehicle ID")
        self.assertNotEqual(error, "", "Error message should be provided")

    def test_validate_enabled_with_whitespace_vehicle_id(self):
        """Test validation fails with whitespace-only vehicle ID."""
        config = SigningConfig(enabled=True, vehicle_id="   ")
        is_valid, error = config.validate()
        self.assertFalse(is_valid, "Config should be invalid with whitespace vehicle ID")

    def test_validate_enabled_with_vehicle_id(self):
        """Test validation succeeds when properly configured."""
        config = SigningConfig(enabled=True, vehicle_id="my_drone")
        is_valid, error = config.validate()
        self.assertTrue(is_valid, "Config should be valid with vehicle ID")
        self.assertEqual(error, "", "Error should be empty for valid config")

    def test_validate_negative_timestamp_tolerance(self):
        """Test validation fails with negative timestamp tolerance."""
        config = SigningConfig(enabled=True, vehicle_id="my_drone", timestamp_tolerance_ms=-1000)
        is_valid, error = config.validate()
        self.assertFalse(is_valid, "Config should be invalid with negative tolerance")

    def test_validate_excessive_timestamp_tolerance(self):
        """Test validation fails with excessive timestamp tolerance."""
        config = SigningConfig(enabled=True, vehicle_id="my_drone", timestamp_tolerance_ms=4000000)  # > 1 hour
        is_valid, error = config.validate()
        self.assertFalse(is_valid, "Config should be invalid with excessive tolerance")

    def test_to_dict(self):
        """Test serialization to dictionary."""
        config = SigningConfig(
            enabled=True,
            vehicle_id="test_vehicle",
            enforce_signing=False,
            allow_unsigned_callback=True,
            timestamp_tolerance_ms=30000,
        )

        config_dict = config.to_dict()

        self.assertEqual(config_dict["enabled"], True)
        self.assertEqual(config_dict["vehicle_id"], "test_vehicle")
        self.assertEqual(config_dict["enforce_signing"], False)
        self.assertEqual(config_dict["allow_unsigned_callback"], True)
        self.assertEqual(config_dict["timestamp_tolerance_ms"], 30000)

        # Runtime state should not be in dict
        self.assertNotIn("is_active", config_dict)
        self.assertNotIn("last_error", config_dict)

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        config_dict = {
            "enabled": True,
            "vehicle_id": "test_vehicle",
            "enforce_signing": False,
            "allow_unsigned_callback": True,
            "timestamp_tolerance_ms": 30000,
        }

        config = SigningConfig.from_dict(config_dict)

        self.assertEqual(config.enabled, True)
        self.assertEqual(config.vehicle_id, "test_vehicle")
        self.assertEqual(config.enforce_signing, False)
        self.assertEqual(config.allow_unsigned_callback, True)
        self.assertEqual(config.timestamp_tolerance_ms, 30000)

    def test_from_dict_with_missing_fields(self):
        """Test deserialization with missing fields uses defaults."""
        config_dict = {"enabled": True, "vehicle_id": "test_vehicle"}

        config = SigningConfig.from_dict(config_dict)

        self.assertEqual(config.enabled, True)
        self.assertEqual(config.vehicle_id, "test_vehicle")
        self.assertEqual(config.enforce_signing, True)  # Default value
        self.assertEqual(config.allow_unsigned_callback, False)  # Default value
        self.assertEqual(config.timestamp_tolerance_ms, 60000)  # Default value

    def test_from_dict_empty(self):
        """Test deserialization from empty dictionary."""
        config = SigningConfig.from_dict({})

        self.assertFalse(config.enabled)
        self.assertEqual(config.vehicle_id, "")
        self.assertTrue(config.enforce_signing)
        self.assertFalse(config.allow_unsigned_callback)
        self.assertEqual(config.timestamp_tolerance_ms, 60000)

    def test_roundtrip_serialization(self):
        """Test that serialization and deserialization are inverse operations."""
        original_config = SigningConfig(
            enabled=True,
            vehicle_id="roundtrip_test",
            enforce_signing=False,
            allow_unsigned_callback=True,
            timestamp_tolerance_ms=45000,
        )

        # Serialize and deserialize
        config_dict = original_config.to_dict()
        restored_config = SigningConfig.from_dict(config_dict)

        # Compare all fields
        self.assertEqual(original_config.enabled, restored_config.enabled)
        self.assertEqual(original_config.vehicle_id, restored_config.vehicle_id)
        self.assertEqual(original_config.enforce_signing, restored_config.enforce_signing)
        self.assertEqual(original_config.allow_unsigned_callback, restored_config.allow_unsigned_callback)
        self.assertEqual(original_config.timestamp_tolerance_ms, restored_config.timestamp_tolerance_ms)

    def test_get_summary_disabled(self):
        """Test summary for disabled configuration."""
        config = SigningConfig(enabled=False)
        summary = config.get_summary()
        self.assertIn("disabled", summary.lower())

    def test_get_summary_enabled(self):
        """Test summary for enabled configuration."""
        config = SigningConfig(enabled=True, vehicle_id="my_drone", enforce_signing=True, timestamp_tolerance_ms=60000)

        summary = config.get_summary()
        self.assertIn("enabled", summary.lower())
        self.assertIn("my_drone", summary)
        self.assertIn("60000", summary)

    def test_str_representation(self):
        """Test string representation."""
        config = SigningConfig(enabled=True, vehicle_id="test_drone")
        str_repr = str(config)
        self.assertIsInstance(str_repr, str)
        self.assertIn("test_drone", str_repr)


if __name__ == "__main__":
    unittest.main()
