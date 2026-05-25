#!/usr/bin/env python3

"""
Unit tests for data_model_signing_config module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests focus on low-level validation, file operation error handling,
and edge cases that cannot be tested at the BDD level.
"""

import json
from pathlib import Path

import pytest
from signing_test_fixtures import STANDARD_CONFIG_PARAMS, create_standard_signing_config

from ardupilot_methodic_configurator.backend_signing_config import (
    SigningConfigManager,
)
from ardupilot_methodic_configurator.data_model_signing_config import (
    SigningConfig,
    VehicleSigningConfig,
)


class TestSigningConfigTypeValidation:
    """Test strict type validation for SigningConfig fields."""

    def test_sign_outgoing_validates_type(self) -> None:
        """
        Test that sign_outgoing field validates type strictly.

        GIVEN: Parameters with non-boolean sign_outgoing value
        WHEN: Creating a SigningConfig
        THEN: Raises ValueError with descriptive message
        """
        with pytest.raises(ValueError, match="sign_outgoing must be a boolean"):
            SigningConfig(
                enabled=True,
                sign_outgoing=1,  # type: ignore[arg-type]
                allow_unsigned_in=False,
                accept_unsigned_callbacks=True,
                timestamp_offset=0,
                link_id=1,
            )

    def test_allow_unsigned_in_validates_type(self) -> None:
        """
        Test that allow_unsigned_in field validates type strictly.

        GIVEN: Parameters with non-boolean allow_unsigned_in value
        WHEN: Creating a SigningConfig
        THEN: Raises ValueError with descriptive message
        """
        with pytest.raises(ValueError, match="allow_unsigned_in must be a boolean"):
            SigningConfig(
                enabled=True,
                sign_outgoing=True,
                allow_unsigned_in="false",  # type: ignore[arg-type]
                accept_unsigned_callbacks=True,
                timestamp_offset=0,
                link_id=1,
            )

    def test_accept_unsigned_callbacks_validates_type(self) -> None:
        """
        Test that accept_unsigned_callbacks field validates type strictly.

        GIVEN: Parameters with non-boolean accept_unsigned_callbacks value
        WHEN: Creating a SigningConfig
        THEN: Raises ValueError with descriptive message
        """
        with pytest.raises(ValueError, match="accept_unsigned_callbacks must be a boolean"):
            SigningConfig(
                enabled=True,
                sign_outgoing=True,
                allow_unsigned_in=False,
                accept_unsigned_callbacks=None,  # type: ignore[arg-type]
                timestamp_offset=0,
                link_id=1,
            )

    def test_timestamp_offset_validates_type(self) -> None:
        """
        Test that timestamp_offset field validates type strictly.

        GIVEN: Parameters with non-integer timestamp_offset value
        WHEN: Creating a SigningConfig
        THEN: Raises ValueError with descriptive message
        """
        with pytest.raises(ValueError, match="timestamp_offset must be an integer"):
            SigningConfig(**{**STANDARD_CONFIG_PARAMS, "timestamp_offset": 0.5})  # type: ignore[arg-type]

    def test_link_id_validates_type_not_string(self) -> None:
        """
        Test that link_id validates type (not string).

        GIVEN: Parameters with non-integer link_id value
        WHEN: Creating a SigningConfig
        THEN: Raises ValueError with descriptive message
        """
        with pytest.raises(ValueError, match="link_id must be an integer"):
            SigningConfig(**{**STANDARD_CONFIG_PARAMS, "link_id": "1"})  # type: ignore[arg-type]


class TestSigningConfigManagerFileErrorHandling:
    """Test config manager file operation error handling."""

    def test_load_config_with_corrupted_json(self, tmp_path: Path) -> None:
        """
        Test loading config file with corrupted JSON data.

        GIVEN: A config file with corrupted JSON syntax
        WHEN: Loading configuration and listing vehicles
        THEN: Returns empty list instead of crashing
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        config_file = tmp_path / "signing_configs.json"

        # Create corrupted JSON file
        config_file.write_text("not valid json {")

        # Should return empty list on error
        configs = manager.list_configured_vehicles()
        assert configs == []

    def test_load_config_with_non_dict_structure(self, tmp_path: Path) -> None:
        """
        Test loading config file with non-dictionary structure.

        GIVEN: A config file with non-dict JSON structure
        WHEN: Loading configuration
        THEN: Manager handles gracefully and returns empty list
        """
        SigningConfigManager(config_dir=tmp_path)
        config_file = tmp_path / "signing_configs.json"

        # Create file with list instead of dict
        config_file.write_text(json.dumps(["not", "a", "dict"]))

        manager = SigningConfigManager(config_dir=tmp_path)
        configs = manager.list_configured_vehicles()
        # Should return empty list when file structure is invalid
        assert configs == []

    def test_list_vehicles_with_invalid_vehicle_data_structure(self, tmp_path: Path) -> None:
        """
        Test list_vehicles when vehicle data has invalid structure.

        GIVEN: A config file with valid and invalid vehicle configurations
        WHEN: Listing configured vehicles
        THEN: Manager lists all vehicles but load_vehicle_config returns None for invalid ones
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        config_file = tmp_path / "signing_configs.json"

        # Create file with mix of valid and invalid vehicle data
        config_data = {
            "VALID-VEHICLE": {"vehicle_id": "VALID-VEHICLE", "signing_config": STANDARD_CONFIG_PARAMS, "auto_setup": False},
            "INVALID-VEHICLE": {
                "vehicle_id": "INVALID-VEHICLE",
                "signing_config": {
                    "enabled": "not_a_boolean",  # Invalid type
                },
                "auto_setup": False,
            },
        }
        config_file.write_text(json.dumps(config_data))

        # List should include both vehicles
        configs = manager.list_configured_vehicles()
        assert "INVALID-VEHICLE" in configs
        assert "VALID-VEHICLE" in configs
        assert len(configs) == 2

        # Loading invalid vehicle should return None
        invalid_config = manager.load_vehicle_config("INVALID-VEHICLE")
        assert invalid_config is None

        # Loading valid vehicle should succeed
        valid_config = manager.load_vehicle_config("VALID-VEHICLE")
        assert valid_config is not None
        assert valid_config.vehicle_id == "VALID-VEHICLE"


class TestSigningConfigManagerOperations:
    """Test SigningConfigManager core operations."""

    def test_save_and_load_vehicle_config(self, tmp_path: Path) -> None:
        """
        Test that saved vehicle config can be loaded back exactly.

        GIVEN: A new config manager and a vehicle signing config
        WHEN: Saving and loading the config
        THEN: The loaded config matches the saved config exactly
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        config = VehicleSigningConfig(
            vehicle_id="TEST-AIRCRAFT",
            signing_config=create_standard_signing_config(),
        )

        # Save config
        save_result = manager.save_vehicle_config(config)
        assert save_result is True

        # Load config and verify
        loaded_config = manager.load_vehicle_config("TEST-AIRCRAFT")
        assert loaded_config is not None
        assert loaded_config.vehicle_id == config.vehicle_id
        assert loaded_config.signing_config.enabled == config.signing_config.enabled
        assert loaded_config.signing_config.sign_outgoing == config.signing_config.sign_outgoing

    def test_list_vehicles_returns_all_saved_vehicles(self, tmp_path: Path) -> None:
        """
        Test that list_vehicles returns all previously saved vehicles.

        GIVEN: Multiple vehicles with saved configurations
        WHEN: Listing configured vehicles
        THEN: All saved vehicles are returned
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Save multiple vehicles
        vehicle_ids = ["COPTER-01", "PLANE-02", "ROVER-03"]
        for vehicle_id in vehicle_ids:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=create_standard_signing_config(),
            )
            manager.save_vehicle_config(config)

        # Verify all are listed
        listed_vehicles = manager.list_configured_vehicles()
        assert len(listed_vehicles) == 3
        for vehicle_id in vehicle_ids:
            assert vehicle_id in listed_vehicles

    def test_delete_vehicle_config(self, tmp_path: Path) -> None:
        """
        Test that vehicle config can be deleted.

        GIVEN: A saved vehicle configuration
        WHEN: Deleting the configuration
        THEN: The configuration is no longer available
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        vehicle_id = "TEST-VEHICLE"

        # Save config
        config = VehicleSigningConfig(
            vehicle_id=vehicle_id,
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(config)
        assert vehicle_id in manager.list_configured_vehicles()

        # Delete config
        delete_result = manager.delete_vehicle_config(vehicle_id)
        assert delete_result is True

        # Verify it's deleted
        assert vehicle_id not in manager.list_configured_vehicles()
        assert manager.load_vehicle_config(vehicle_id) is None
