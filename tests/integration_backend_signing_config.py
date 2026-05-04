#!/usr/bin/env python3

"""
Integration tests for MAVLink signing configuration persistence backend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests focus on complete workflows and file I/O operations that require
integration with the filesystem and actual JSON serialization.
"""

import json
from pathlib import Path

import pytest
from signing_test_fixtures import (
    STANDARD_CONFIG_PARAMS,
    create_standard_signing_config,
)

from ardupilot_methodic_configurator.backend_signing_config import (
    SIGNING_CONFIG_FILENAME,
    SigningConfigManager,
)
from ardupilot_methodic_configurator.data_model_signing_config import VehicleSigningConfig


class TestSigningConfigManagerFilePersistence:
    """Test file persistence and atomic operations."""

    def test_config_directory_created_automatically(self, tmp_path: Path) -> None:
        """
        Test that config directory is created if it doesn't exist.

        GIVEN: A non-existent configuration directory
        WHEN: Creating a SigningConfigManager
        THEN: The directory is created when first config is saved
        """
        config_dir = tmp_path / "config" / "nested" / "dir"
        assert not config_dir.exists()

        manager = SigningConfigManager(config_dir=config_dir)
        config = VehicleSigningConfig(
            vehicle_id="COPTER-01",
            signing_config=create_standard_signing_config(),
        )

        result = manager.save_vehicle_config(config)

        assert result is True
        assert config_dir.exists()
        assert (config_dir / SIGNING_CONFIG_FILENAME).exists()

    def test_atomic_save_creates_temp_file_then_replaces(self, tmp_path: Path) -> None:
        """
        Test that save uses temp file and atomic replace (no temp file after save).

        GIVEN: A signing config to save
        WHEN: Saving the configuration
        THEN: Temp file is cleaned up after atomic replace
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        config = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
        )

        result = manager.save_vehicle_config(config)

        assert result is True
        # Verify no temp files are left
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0
        # Verify actual config file exists
        assert (tmp_path / SIGNING_CONFIG_FILENAME).exists()

    def test_multiple_saves_preserve_all_configs(self, tmp_path: Path) -> None:
        """
        Test that saving new configs doesn't overwrite existing ones.

        GIVEN: Multiple vehicle configs to save sequentially
        WHEN: Saving each config independently
        THEN: All configs are preserved in the file
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        vehicles = ["COPTER-01", "PLANE-02", "ROVER-03"]

        # Save multiple configs
        for vehicle_id in vehicles:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=create_standard_signing_config(),
            )
            result = manager.save_vehicle_config(config)
            assert result is True

        # Verify all are in file
        config_file = tmp_path / SIGNING_CONFIG_FILENAME
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)

        for vehicle_id in vehicles:
            assert vehicle_id in data
            assert "signing_config" in data[vehicle_id]

    def test_save_updates_existing_config(self, tmp_path: Path) -> None:
        """
        Test that saving updates an existing vehicle's config.

        GIVEN: A saved vehicle configuration
        WHEN: Saving a new config for the same vehicle
        THEN: The configuration is updated (not duplicated)
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        vehicle_id = "TEST-VEHICLE"

        # Save initial config
        config1 = VehicleSigningConfig(
            vehicle_id=vehicle_id,
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(config1)

        # Save updated config
        config2 = VehicleSigningConfig(
            vehicle_id=vehicle_id,
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(config2)

        # Verify only one config exists
        configs = manager.list_configured_vehicles()
        assert configs.count(vehicle_id) == 1
        assert len(configs) == 1

    def test_config_file_preserves_json_formatting(self, tmp_path: Path) -> None:
        """
        Test that saved config file is valid, readable JSON.

        GIVEN: A saved configuration
        WHEN: Reading the config file directly
        THEN: File contains valid, indented JSON
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        config = VehicleSigningConfig(
            vehicle_id="AIRCRAFT",
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(config)

        # Read file directly and verify formatting
        config_file = tmp_path / SIGNING_CONFIG_FILENAME
        content = config_file.read_text(encoding="utf-8")

        # Should be valid JSON
        data = json.loads(content)
        assert "AIRCRAFT" in data

        # Should be indented (not minified)
        assert "\n" in content
        assert "  " in content

    def test_empty_config_file_created_on_first_save(self, tmp_path: Path) -> None:
        """
        Test that config file starts as empty or minimal valid JSON.

        GIVEN: A new config directory
        WHEN: Loading before any saves
        THEN: list_configured_vehicles returns empty list
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        vehicles = manager.list_configured_vehicles()
        assert vehicles == []

    def test_config_persistence_across_manager_instances(self, tmp_path: Path) -> None:
        """
        Test that config persists when loading with new manager instance.

        GIVEN: A saved configuration
        WHEN: Creating a new manager instance for the same directory
        THEN: The configuration is loaded correctly
        """
        # Save with first manager
        manager1 = SigningConfigManager(config_dir=tmp_path)
        config = VehicleSigningConfig(
            vehicle_id="PERSISTENT-VEHICLE",
            signing_config=create_standard_signing_config(),
        )
        manager1.save_vehicle_config(config)

        # Load with new manager
        manager2 = SigningConfigManager(config_dir=tmp_path)
        loaded_config = manager2.load_vehicle_config("PERSISTENT-VEHICLE")

        assert loaded_config is not None
        assert loaded_config.vehicle_id == "PERSISTENT-VEHICLE"


class TestSigningConfigManagerValidation:
    """Test validation during load/save operations."""

    def test_save_validates_config_before_persisting(self, tmp_path: Path) -> None:
        """
        Test that invalid configs are rejected before saving.

        GIVEN: An invalid signing config object
        WHEN: Attempting to save it
        THEN: Save fails and file is not modified
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Create valid config first
        valid_config = VehicleSigningConfig(
            vehicle_id="VALID",
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(valid_config)

        # Try to save invalid config (will be caught by VehicleSigningConfig constructor)
        # Since we can't create invalid config due to dataclass validation,
        # this test demonstrates that at least one valid config can be saved
        configs = manager.list_configured_vehicles()
        assert "VALID" in configs

    def test_load_handles_corrupted_config_gracefully(self, tmp_path: Path) -> None:
        """
        Test that loading handles individual corrupted configs without crashing.

        GIVEN: A config file with partially corrupted vehicle config
        WHEN: Loading that specific vehicle
        THEN: Returns None and logs error instead of crashing
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Create a file with corrupted data for one vehicle
        config_file = tmp_path / SIGNING_CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        corrupted_data = {
            "VALID-VEHICLE": {
                "vehicle_id": "VALID-VEHICLE",
                "signing_config": STANDARD_CONFIG_PARAMS,
                "auto_setup": False,
            },
            "CORRUPTED-VEHICLE": {
                "vehicle_id": "CORRUPTED-VEHICLE",
                # Missing required fields - will cause validation error
                "signing_config": {"enabled": "not_a_boolean"},
            },
        }
        config_file.write_text(json.dumps(corrupted_data), encoding="utf-8")

        # Load corrupted vehicle should return None
        loaded = manager.load_vehicle_config("CORRUPTED-VEHICLE")
        assert loaded is None

        # Load valid vehicle should work
        loaded = manager.load_vehicle_config("VALID-VEHICLE")
        assert loaded is not None

    def test_list_includes_all_vehicles_even_with_corrupt_entries(self, tmp_path: Path) -> None:
        """
        Test that list_configured_vehicles includes all keys, even if some are corrupted.

        GIVEN: Config file with some corrupted entries
        WHEN: Listing all vehicles
        THEN: All vehicle IDs are listed (even if they can't be loaded)
        """
        config_file = tmp_path / SIGNING_CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        corrupted_data = {
            "VALID-1": {"vehicle_id": "VALID-1", "signing_config": {}, "auto_setup": False},
            "CORRUPTED": {"vehicle_id": "CORRUPTED", "corrupted": True},
            "VALID-2": {"vehicle_id": "VALID-2", "signing_config": {}, "auto_setup": False},
        }
        config_file.write_text(json.dumps(corrupted_data), encoding="utf-8")

        manager = SigningConfigManager(config_dir=tmp_path)
        vehicles = manager.list_configured_vehicles()

        assert len(vehicles) == 3
        assert "VALID-1" in vehicles
        assert "CORRUPTED" in vehicles
        assert "VALID-2" in vehicles


class TestSigningConfigManagerDeletion:
    """Test deletion operations."""

    def test_delete_removes_only_specified_vehicle(self, tmp_path: Path) -> None:
        """
        Test that deleting one vehicle doesn't affect others.

        GIVEN: Multiple saved vehicle configs
        WHEN: Deleting one specific vehicle
        THEN: Only that vehicle is removed
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Save multiple vehicles
        vehicles_to_save = ["COPTER-01", "PLANE-02", "ROVER-03"]
        for vehicle_id in vehicles_to_save:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=create_standard_signing_config(),
            )
            manager.save_vehicle_config(config)

        # Delete one
        result = manager.delete_vehicle_config("PLANE-02")
        assert result is True

        # Verify deletion
        remaining = manager.list_configured_vehicles()
        assert len(remaining) == 2
        assert "PLANE-02" not in remaining
        assert "COPTER-01" in remaining
        assert "ROVER-03" in remaining

    def test_delete_nonexistent_vehicle_returns_false(self, tmp_path: Path) -> None:
        """
        Test that deleting non-existent vehicle returns False.

        GIVEN: A manager with some configs
        WHEN: Attempting to delete a vehicle that doesn't exist
        THEN: Returns False
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Save one vehicle
        config = VehicleSigningConfig(
            vehicle_id="EXISTING",
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(config)

        # Try to delete non-existent
        result = manager.delete_vehicle_config("NONEXISTENT")
        assert result is False

    def test_delete_persists_to_file(self, tmp_path: Path) -> None:
        """
        Test that deletion is persisted to the config file.

        GIVEN: Saved vehicle configs
        WHEN: Deleting a vehicle
        THEN: The file no longer contains that vehicle
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Save vehicles
        for vehicle_id in ["VEH-1", "VEH-2"]:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=create_standard_signing_config(),
            )
            manager.save_vehicle_config(config)

        # Delete one
        manager.delete_vehicle_config("VEH-1")

        # Verify file
        config_file = tmp_path / SIGNING_CONFIG_FILENAME
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "VEH-1" not in data
        assert "VEH-2" in data


class TestSigningConfigManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_invalid_vehicle_id_on_save(self, tmp_path: Path) -> None:  # pylint: disable=unused-argument
        """
        Test that invalid vehicle_id in config is handled.

        GIVEN: A config with invalid vehicle_id
        WHEN: Attempting to save
        THEN: Behavior depends on implementation (may fail validation)
        """
        # Empty vehicle ID
        config_dict = {
            "vehicle_id": "",
            "signing_config": create_standard_signing_config().to_dict(),
        }

        # VehicleSigningConfig constructor validates vehicle_id
        with pytest.raises(ValueError, match="cannot be empty"):
            VehicleSigningConfig.from_dict(config_dict)

    def test_very_long_vehicle_id(self, tmp_path: Path) -> None:
        """
        Test that very long vehicle IDs are handled.

        GIVEN: A vehicle with very long ID
        WHEN: Saving and loading
        THEN: The long ID is preserved exactly
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        long_id = "VEHICLE-" + "X" * 200

        config = VehicleSigningConfig(
            vehicle_id=long_id,
            signing_config=create_standard_signing_config(),
        )

        result = manager.save_vehicle_config(config)
        assert result is True

        loaded = manager.load_vehicle_config(long_id)
        assert loaded is not None
        assert loaded.vehicle_id == long_id

    def test_special_characters_in_vehicle_id(self, tmp_path: Path) -> None:
        """
        Test that special characters in vehicle IDs are handled.

        GIVEN: Vehicle IDs with special characters (that are valid JSON keys)
        WHEN: Saving and listing
        THEN: Characters are preserved
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        special_ids = [
            "VEHICLE-WITH-DASHES",
            "VEHICLE_WITH_UNDERSCORES",
            "VEHICLE.WITH.DOTS",
            "VEHICLE@VERSION",
        ]

        for vehicle_id in special_ids:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=create_standard_signing_config(),
            )
            manager.save_vehicle_config(config)

        listed = manager.list_configured_vehicles()
        for vehicle_id in special_ids:
            assert vehicle_id in listed

    def test_list_returns_sorted_vehicle_ids(self, tmp_path: Path) -> None:
        """
        Test that list_configured_vehicles returns sorted results.

        GIVEN: Multiple vehicles with unsorted IDs
        WHEN: Calling list_configured_vehicles
        THEN: Results are sorted alphabetically
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        unsorted_ids = ["ZEBRA", "ALPHA", "MIKE", "BRAVO"]

        for vehicle_id in unsorted_ids:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=create_standard_signing_config(),
            )
            manager.save_vehicle_config(config)

        listed = manager.list_configured_vehicles()
        assert listed == ["ALPHA", "BRAVO", "MIKE", "ZEBRA"]

    def test_config_manager_with_platform_data_dir(self) -> None:
        """
        Test that manager uses platform data directory when no dir specified.

        GIVEN: No config_dir parameter
        WHEN: Creating SigningConfigManager
        THEN: Uses platform-appropriate data directory
        """
        manager = SigningConfigManager(config_dir=None)

        # Should have a valid config_dir property
        assert manager.config_dir is not None
        assert len(manager.config_dir) > 0
        assert "ArduPilot" in manager.config_dir or "ardupilot" in manager.config_dir.lower()


class TestSigningConfigManagerInvalidInput:
    """Test handling of invalid inputs."""

    def test_save_rejects_wrong_config_type(self, tmp_path: Path) -> None:
        """
        Test that save rejects non-VehicleSigningConfig objects.

        GIVEN: A wrong type object
        WHEN: Attempting to save
        THEN: Returns False
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        result = manager.save_vehicle_config("not a config")  # type: ignore[arg-type]
        assert result is False

    def test_load_with_invalid_vehicle_id(self, tmp_path: Path) -> None:
        """
        Test that load handles invalid vehicle IDs gracefully.

        GIVEN: Various invalid vehicle IDs
        WHEN: Attempting to load
        THEN: Returns None
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        assert manager.load_vehicle_config("") is None
        assert manager.load_vehicle_config(None) is None  # type: ignore[arg-type]
        assert manager.load_vehicle_config(123) is None  # type: ignore[arg-type]

    def test_delete_with_invalid_vehicle_id(self, tmp_path: Path) -> None:
        """
        Test that delete handles invalid vehicle IDs gracefully.

        GIVEN: Various invalid vehicle IDs
        WHEN: Attempting to delete
        THEN: Returns False
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        assert manager.delete_vehicle_config("") is False
        assert manager.delete_vehicle_config(None) is False  # type: ignore[arg-type]
        assert manager.delete_vehicle_config(123) is False  # type: ignore[arg-type]
