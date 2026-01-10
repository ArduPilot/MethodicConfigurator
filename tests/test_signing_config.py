#!/usr/bin/env python3

"""
BDD-style tests for MAVLink signing configuration data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json

import pytest

from ardupilot_methodic_configurator.data_model_signing_config import (
    SigningConfig,
    SigningConfigManager,
    VehicleSigningConfig,
)


class TestSigningConfigCreation:
    """Test signing configuration creation in BDD style."""

    def test_user_can_create_valid_signing_config(self) -> None:
        """
        User can create a valid signing configuration.

        GIVEN: Default configuration parameters
        WHEN: The user creates a SigningConfig instance
        THEN: A valid configuration should be created
        AND: All default values should be set correctly
        """
        config = SigningConfig()

        assert config.enabled is False
        assert config.sign_outgoing is True
        assert config.allow_unsigned_in is True
        assert config.accept_unsigned_callbacks is True
        assert config.timestamp_offset == 0
        assert config.link_id == 0

    def test_user_can_create_config_with_custom_values(self) -> None:
        """
        User can create a configuration with custom values.

        GIVEN: Custom configuration parameters
        WHEN: The user creates a SigningConfig with those values
        THEN: The configuration should reflect the custom values
        """
        config = SigningConfig(
            enabled=True,
            sign_outgoing=True,
            allow_unsigned_in=False,
            accept_unsigned_callbacks=False,
            timestamp_offset=1000,
            link_id=5,
        )

        assert config.enabled is True
        assert config.sign_outgoing is True
        assert config.allow_unsigned_in is False
        assert config.accept_unsigned_callbacks is False
        assert config.timestamp_offset == 1000
        assert config.link_id == 5

    def test_config_defaults_are_secure_with_factory_method(self) -> None:
        """
        Secure defaults factory creates a security-focused configuration.

        GIVEN: A need for secure defaults
        WHEN: The user creates a config using secure_defaults()
        THEN: The configuration should have security-focused settings
        AND: Signing should be enabled, unsigned messages rejected
        """
        config = SigningConfig.secure_defaults()

        assert config.enabled is True
        assert config.sign_outgoing is True
        assert config.allow_unsigned_in is False
        assert config.accept_unsigned_callbacks is False


class TestSigningConfigSerialization:
    """Test signing configuration serialization in BDD style."""

    def test_user_can_serialize_config_to_json(self) -> None:
        """
        User can serialize configuration to JSON format.

        GIVEN: A signing configuration
        WHEN: The user serializes it to JSON
        THEN: A valid JSON string should be returned
        AND: All configuration values should be preserved
        """
        config = SigningConfig(
            enabled=True,
            sign_outgoing=True,
            allow_unsigned_in=False,
            timestamp_offset=500,
            link_id=3,
        )

        json_str = config.to_json()

        parsed = json.loads(json_str)
        assert parsed["enabled"] is True
        assert parsed["sign_outgoing"] is True
        assert parsed["allow_unsigned_in"] is False
        assert parsed["timestamp_offset"] == 500
        assert parsed["link_id"] == 3

    def test_user_can_deserialize_config_from_json(self) -> None:
        """
        User can deserialize configuration from JSON format.

        GIVEN: A valid JSON configuration string
        WHEN: The user deserializes it
        THEN: A SigningConfig instance should be created
        AND: All values should match the JSON input
        """
        json_str = json.dumps(
            {
                "enabled": True,
                "sign_outgoing": False,
                "allow_unsigned_in": True,
                "accept_unsigned_callbacks": True,
                "timestamp_offset": 100,
                "link_id": 7,
            }
        )

        config = SigningConfig.from_json(json_str)

        assert config.enabled is True
        assert config.sign_outgoing is False
        assert config.allow_unsigned_in is True
        assert config.timestamp_offset == 100
        assert config.link_id == 7

    def test_user_can_convert_config_to_dict(self) -> None:
        """
        User can convert configuration to dictionary.

        GIVEN: A signing configuration
        WHEN: The user converts it to a dictionary
        THEN: A dictionary with all configuration values should be returned
        """
        config = SigningConfig(enabled=True, link_id=10)

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["enabled"] is True
        assert config_dict["link_id"] == 10

    def test_user_can_create_config_from_dict(self) -> None:
        """
        User can create configuration from dictionary.

        GIVEN: A dictionary with configuration values
        WHEN: The user creates a config from the dictionary
        THEN: A SigningConfig instance should be created with those values
        """
        config_dict = {
            "enabled": True,
            "sign_outgoing": True,
            "allow_unsigned_in": False,
            "accept_unsigned_callbacks": False,
            "timestamp_offset": 0,
            "link_id": 255,
        }

        config = SigningConfig.from_dict(config_dict)

        assert config.enabled is True
        assert config.link_id == 255


class TestSigningConfigValidation:
    """Test signing configuration validation in BDD style."""

    def test_invalid_link_id_raises_validation_error(self) -> None:
        """
        Invalid link_id raises validation error.

        GIVEN: A link_id value outside valid range (0-255)
        WHEN: The user tries to create a config with this value
        THEN: A ValueError should be raised
        AND: The error should indicate the valid range
        """
        with pytest.raises(ValueError, match="link_id"):
            SigningConfig(link_id=256)

        with pytest.raises(ValueError, match="link_id"):
            SigningConfig(link_id=-1)

    def test_invalid_boolean_type_raises_validation_error(self) -> None:
        """
        Invalid boolean type raises validation error.

        GIVEN: A non-boolean value for a boolean field
        WHEN: The user tries to create a config with this value
        THEN: A ValueError should be raised
        """
        with pytest.raises(ValueError, match="enabled"):
            SigningConfig(enabled="true")

    def test_invalid_timestamp_type_raises_validation_error(self) -> None:
        """
        Invalid timestamp type raises validation error.

        GIVEN: A non-integer value for timestamp_offset
        WHEN: The user tries to create a config with this value
        THEN: A ValueError should be raised
        """
        with pytest.raises(ValueError, match="timestamp_offset"):
            SigningConfig(timestamp_offset="100")


class TestVehicleSigningConfig:
    """Test vehicle-specific signing configuration in BDD style."""

    def test_user_can_create_vehicle_config(self) -> None:
        """
        User can create a vehicle-specific signing configuration.

        GIVEN: A vehicle ID and signing configuration
        WHEN: The user creates a VehicleSigningConfig
        THEN: A configuration should be created with the vehicle ID
        AND: The signing config should be associated with the vehicle
        """
        signing_config = SigningConfig.secure_defaults()

        vehicle_config = VehicleSigningConfig(
            vehicle_id="VEHICLE-001",
            signing_config=signing_config,
            auto_setup=True,
        )

        assert vehicle_config.vehicle_id == "VEHICLE-001"
        assert vehicle_config.signing_config.enabled is True
        assert vehicle_config.auto_setup is True

    def test_user_can_serialize_vehicle_config(self) -> None:
        """
        User can serialize vehicle configuration to dictionary.

        GIVEN: A vehicle signing configuration
        WHEN: The user converts it to a dictionary
        THEN: A dictionary with vehicle ID and signing config should be returned
        """
        vehicle_config = VehicleSigningConfig(
            vehicle_id="VEHICLE-002",
            signing_config=SigningConfig(enabled=True),
            auto_setup=False,
        )

        config_dict = vehicle_config.to_dict()

        assert config_dict["vehicle_id"] == "VEHICLE-002"
        assert config_dict["signing_config"]["enabled"] is True
        assert config_dict["auto_setup"] is False

    def test_user_can_deserialize_vehicle_config(self) -> None:
        """
        User can deserialize vehicle configuration from dictionary.

        GIVEN: A dictionary with vehicle configuration
        WHEN: The user creates a VehicleSigningConfig from it
        THEN: A configuration should be created with correct values
        """
        config_dict = {
            "vehicle_id": "VEHICLE-003",
            "signing_config": {"enabled": True, "link_id": 5},
            "auto_setup": True,
        }

        vehicle_config = VehicleSigningConfig.from_dict(config_dict)

        assert vehicle_config.vehicle_id == "VEHICLE-003"
        assert vehicle_config.signing_config.enabled is True
        assert vehicle_config.signing_config.link_id == 5
        assert vehicle_config.auto_setup is True


class TestSigningConfigManager:
    """Test signing configuration manager in BDD style."""

    @pytest.fixture
    def temp_config_manager(self, tmp_path) -> SigningConfigManager:
        """Create a config manager using temporary storage."""
        return SigningConfigManager(config_dir=tmp_path)

    def test_user_can_save_vehicle_config(self, temp_config_manager) -> None:
        """
        User can save a vehicle signing configuration.

        GIVEN: A vehicle signing configuration
        WHEN: The user saves it using the config manager
        THEN: The configuration should be persisted
        AND: The function should return True
        """
        vehicle_config = VehicleSigningConfig(
            vehicle_id="SAVE-VEHICLE",
            signing_config=SigningConfig(enabled=True),
        )
        result = temp_config_manager.save_vehicle_config(vehicle_config)

        assert result is True

    def test_user_can_load_vehicle_config(self, temp_config_manager) -> None:
        """
        User can load a saved vehicle signing configuration.

        GIVEN: A vehicle configuration has been saved
        WHEN: The user loads it using the vehicle ID
        THEN: The configuration should be returned
        AND: All values should match what was saved
        """
        original_config = VehicleSigningConfig(
            vehicle_id="LOAD-VEHICLE",
            signing_config=SigningConfig(enabled=True, link_id=10),
            auto_setup=True,
        )
        temp_config_manager.save_vehicle_config(original_config)

        loaded_config = temp_config_manager.load_vehicle_config("LOAD-VEHICLE")

        assert loaded_config is not None
        assert loaded_config.vehicle_id == "LOAD-VEHICLE"
        assert loaded_config.signing_config.enabled is True
        assert loaded_config.signing_config.link_id == 10
        assert loaded_config.auto_setup is True

    def test_user_can_delete_vehicle_config(self, temp_config_manager) -> None:
        """
        User can delete a vehicle signing configuration.

        GIVEN: A vehicle configuration has been saved
        WHEN: The user deletes it
        THEN: The configuration should be removed
        AND: Subsequent loads should return None
        """
        vehicle_config = VehicleSigningConfig(
            vehicle_id="DELETE-VEHICLE",
            signing_config=SigningConfig(),
        )
        temp_config_manager.save_vehicle_config(vehicle_config)

        result = temp_config_manager.delete_vehicle_config("DELETE-VEHICLE")

        assert result is True
        assert temp_config_manager.load_vehicle_config("DELETE-VEHICLE") is None

    def test_user_can_list_configured_vehicles(self, temp_config_manager) -> None:
        """
        User can list all vehicles with saved configurations.

        GIVEN: Multiple vehicle configurations have been saved
        WHEN: The user lists configured vehicles
        THEN: All vehicle IDs should be returned
        AND: The list should be sorted alphabetically
        """
        for vehicle_id in ["VEHICLE-C", "VEHICLE-A", "VEHICLE-B"]:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=SigningConfig(),
            )
            temp_config_manager.save_vehicle_config(config)

        vehicles = temp_config_manager.list_configured_vehicles()

        assert len(vehicles) == 3
        assert vehicles == ["VEHICLE-A", "VEHICLE-B", "VEHICLE-C"]

    def test_load_nonexistent_config_returns_none(self, temp_config_manager) -> None:
        """
        Loading a nonexistent configuration returns None.

        GIVEN: No configuration saved for a vehicle
        WHEN: The user tries to load the configuration
        THEN: None should be returned
        AND: No error should be raised
        """
        result = temp_config_manager.load_vehicle_config("NONEXISTENT-VEHICLE")

        assert result is None

    def test_delete_nonexistent_config_returns_false(self, temp_config_manager) -> None:
        """
        Deleting a nonexistent configuration returns False.

        GIVEN: No configuration saved for a vehicle
        WHEN: The user tries to delete the configuration
        THEN: False should be returned
        AND: No error should be raised
        """
        result = temp_config_manager.delete_vehicle_config("NONEXISTENT-VEHICLE")

        assert result is False
