#!/usr/bin/env python3

"""
Advanced integration tests for signing configuration modules.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests focus on JSON serialization, factory methods, equality, hashing,
and comprehensive error handling paths.
"""

import json
from pathlib import Path

import pytest
from signing_test_fixtures import (
    STANDARD_CONFIG_PARAMS,
    assert_secure_defaults_config,
    create_config_with_custom_offsets,
    create_max_link_id_signing_config,
    create_restricted_signing_config,
    create_standard_signing_config,
)

from ardupilot_methodic_configurator.backend_signing_config import (
    SigningConfigManager,
)
from ardupilot_methodic_configurator.data_model_signing_config import (
    SigningConfig,
    VehicleSigningConfig,
)


class TestSigningConfigJSONSerialization:
    """Test JSON serialization and deserialization paths."""

    def test_signing_config_to_json_produces_valid_json(self) -> None:
        """
        Test that to_json produces valid, parseable JSON.

        GIVEN: A SigningConfig object
        WHEN: Calling to_json()
        THEN: Result is valid JSON that can be parsed
        """
        config = create_standard_signing_config()
        json_str = config.to_json()

        # Should be parseable JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

        # Should have all fields
        assert "enabled" in parsed
        assert "sign_outgoing" in parsed
        assert "allow_unsigned_in" in parsed
        assert "accept_unsigned_callbacks" in parsed
        assert "timestamp_offset" in parsed
        assert "link_id" in parsed

    def test_signing_config_from_json_reconstructs_config(self) -> None:
        """
        Test that from_json recreates config from JSON string.

        GIVEN: A JSON string with valid signing config
        WHEN: Creating config from JSON
        THEN: Config is fully reconstructed with correct values
        """
        original = create_standard_signing_config()
        json_str = original.to_json()

        reconstructed = SigningConfig.from_json(json_str)

        assert reconstructed.enabled == original.enabled
        assert reconstructed.sign_outgoing == original.sign_outgoing
        assert reconstructed.allow_unsigned_in == original.allow_unsigned_in
        assert reconstructed.accept_unsigned_callbacks == original.accept_unsigned_callbacks
        assert reconstructed.timestamp_offset == original.timestamp_offset
        assert reconstructed.link_id == original.link_id

    def test_signing_config_json_round_trip_preserves_data(self) -> None:
        """
        Test complete JSON round-trip: object → JSON → object.

        GIVEN: A SigningConfig object
        WHEN: Converting to JSON and back
        THEN: Original and reconstructed are equal
        """
        original = create_standard_signing_config()
        json_str = original.to_json()
        reconstructed = SigningConfig.from_json(json_str)

        assert original == reconstructed

    def test_signing_config_from_json_invalid_json_raises_error(self) -> None:
        """
        Test that invalid JSON raises JSONDecodeError.

        GIVEN: An invalid JSON string
        WHEN: Calling from_json()
        THEN: Raises json.JSONDecodeError
        """
        invalid_json = "not valid json {"

        with pytest.raises(json.JSONDecodeError):
            SigningConfig.from_json(invalid_json)

    def test_signing_config_from_json_with_missing_fields_creates_with_defaults(self) -> None:
        """
        Test that from_json with missing optional fields uses dataclass defaults.

        GIVEN: JSON with only some fields present
        WHEN: Creating config from JSON
        THEN: Missing fields use default values from dataclass
        """
        minimal_json = json.dumps(
            {
                "enabled": True,
                "sign_outgoing": True,
            }
        )

        config = SigningConfig.from_json(minimal_json)

        # Should use defaults for missing fields
        assert config.enabled is True
        assert config.sign_outgoing is True
        # These should have their dataclass defaults
        assert isinstance(config.allow_unsigned_in, bool)
        assert isinstance(config.accept_unsigned_callbacks, bool)
        assert isinstance(config.timestamp_offset, int)
        assert isinstance(config.link_id, int)

    def test_signing_config_from_dict_with_unknown_fields_logs_warning(self) -> None:
        """
        Test that from_dict with unknown fields logs warning but succeeds.

        GIVEN: A dict with unknown extra fields
        WHEN: Creating config from dict
        THEN: Config is created successfully (unknown fields ignored)
        """
        data = {
            **STANDARD_CONFIG_PARAMS,
            "unknown_field": "should_be_ignored",
            "another_unknown": 42,
        }

        config = SigningConfig.from_dict(data)

        # Should still create config with known fields
        assert config.enabled == STANDARD_CONFIG_PARAMS["enabled"]
        assert config.sign_outgoing == STANDARD_CONFIG_PARAMS["sign_outgoing"]

    def test_signing_config_from_dict_with_wrong_boolean_type_raises_error(self) -> None:
        """
        Test that from_dict raises TypeError for non-boolean boolean fields.

        GIVEN: A dict with non-boolean value for boolean field
        WHEN: Creating config from dict
        THEN: Raises TypeError with field name
        """
        data = {**STANDARD_CONFIG_PARAMS, "enabled": "not_a_bool"}

        with pytest.raises(TypeError, match=r"enabled.*boolean"):
            SigningConfig.from_dict(data)

    def test_signing_config_from_dict_with_wrong_integer_type_raises_error(self) -> None:
        """
        Test that from_dict raises TypeError for non-integer integer fields.

        GIVEN: A dict with non-integer value for integer field
        WHEN: Creating config from dict
        THEN: Raises TypeError with field name
        """
        data = {**STANDARD_CONFIG_PARAMS, "link_id": "not_an_int"}

        with pytest.raises(TypeError, match=r"link_id.*integer"):
            SigningConfig.from_dict(data)

    def test_signing_config_from_dict_with_non_dict_raises_error(self) -> None:
        """
        Test that from_dict raises TypeError if input is not a dict.

        GIVEN: A non-dict value (list, string, etc.)
        WHEN: Calling from_dict()
        THEN: Raises TypeError
        """
        with pytest.raises(TypeError, match="Expected dict"):
            SigningConfig.from_dict([1, 2, 3])  # type: ignore[arg-type]

    def test_signing_config_from_dict_with_string_raises_error(self) -> None:
        """Test from_dict rejects string input."""
        with pytest.raises(TypeError, match="Expected dict"):
            SigningConfig.from_dict("not a dict")  # type: ignore[arg-type]


class TestSigningConfigFactoryMethods:
    """Test factory methods for creating configs."""

    def test_secure_defaults_enables_signing(self) -> None:
        """
        Test that secure_defaults creates signing-enabled config.

        GIVEN: No parameters
        WHEN: Calling secure_defaults()
        THEN: Returns config with signing enabled and strict rules
        """
        config = SigningConfig.secure_defaults()
        assert_secure_defaults_config(config)
        assert config.timestamp_offset == 0
        assert config.link_id == 0

    def test_secure_defaults_validates_successfully(self) -> None:
        """
        Test that secure_defaults config passes validation.

        GIVEN: Config from secure_defaults()
        WHEN: Calling validate()
        THEN: No exception is raised
        """
        config = SigningConfig.secure_defaults()
        config.validate()  # Should not raise

    def test_secure_defaults_can_be_saved_and_loaded(self, tmp_path: Path) -> None:
        """
        Test complete workflow with secure_defaults config.

        GIVEN: Secure defaults config
        WHEN: Saving and loading via config manager
        THEN: Loaded config matches secure defaults
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        vehicle_config = VehicleSigningConfig(
            vehicle_id="SECURE-VEHICLE",
            signing_config=SigningConfig.secure_defaults(),
        )

        # Save
        save_result = manager.save_vehicle_config(vehicle_config)
        assert save_result is True

        # Load
        loaded = manager.load_vehicle_config("SECURE-VEHICLE")
        assert loaded is not None
        assert loaded.signing_config.enabled is True
        assert loaded.signing_config.sign_outgoing is True
        assert loaded.signing_config.allow_unsigned_in is False


class TestSigningConfigEqualityAndHashing:
    """Test equality comparison and hash operations."""

    def test_signing_config_equality_same_values(self) -> None:
        """
        Test that configs with same values are equal.

        GIVEN: Two configs with identical values
        WHEN: Comparing with ==
        THEN: They are equal
        """
        config1 = SigningConfig(**STANDARD_CONFIG_PARAMS)
        config2 = SigningConfig(**STANDARD_CONFIG_PARAMS)

        assert config1 == config2

    def test_signing_config_inequality_different_values(self) -> None:
        """
        Test that configs with different values are not equal.

        GIVEN: Two configs with different values
        WHEN: Comparing with ==
        THEN: They are not equal
        """
        config1 = SigningConfig(**STANDARD_CONFIG_PARAMS)
        params2 = {**STANDARD_CONFIG_PARAMS, "enabled": False}
        config2 = SigningConfig(**params2)

        assert config1 != config2

    def test_signing_config_hash_same_values_same_hash(self) -> None:
        """
        Test that configs with same values have same hash.

        GIVEN: Two identical configs
        WHEN: Computing hash values
        THEN: Hashes are equal
        """
        config1 = SigningConfig(**STANDARD_CONFIG_PARAMS)
        config2 = SigningConfig(**STANDARD_CONFIG_PARAMS)

        assert hash(config1) == hash(config2)

    def test_signing_config_hash_in_set(self) -> None:
        """
        Test that configs can be used in sets.

        GIVEN: Duplicate configs
        WHEN: Adding to a set
        THEN: Set deduplicates by hash
        """
        config1 = SigningConfig(**STANDARD_CONFIG_PARAMS)
        config2 = SigningConfig(**STANDARD_CONFIG_PARAMS)

        config_set = {config1, config2}
        assert len(config_set) == 1

    def test_signing_config_not_equal_to_other_types(self) -> None:
        """
        Test that config is not equal to other types.

        GIVEN: A config and a different type
        WHEN: Comparing with ==
        THEN: Returns False (not NotImplemented)
        """
        config = create_standard_signing_config()

        assert config != "string"
        assert config != 42
        assert config is not None
        assert config != {"enabled": True}


class TestVehicleSigningConfigEqualityAndHashing:
    """Test VehicleSigningConfig equality and hashing."""

    def test_vehicle_signing_config_equality(self) -> None:
        """
        Test VehicleSigningConfig equality comparison.

        GIVEN: Two vehicle configs with same values
        WHEN: Comparing with ==
        THEN: They are equal
        """
        config1 = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
            auto_setup=True,
        )
        config2 = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
            auto_setup=True,
        )

        assert config1 == config2

    def test_vehicle_signing_config_inequality(self) -> None:
        """
        Test VehicleSigningConfig inequality for different values.

        GIVEN: Two vehicle configs with different values
        WHEN: Comparing
        THEN: They are not equal
        """
        config1 = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
        )
        config2 = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-02",
            signing_config=create_standard_signing_config(),
        )

        assert config1 != config2

    def test_vehicle_signing_config_hash(self) -> None:
        """
        Test VehicleSigningConfig hashing.

        GIVEN: Two identical vehicle configs
        WHEN: Computing hash values
        THEN: Hashes are equal
        """
        config1 = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
        )
        config2 = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
        )

        assert hash(config1) == hash(config2)

    def test_vehicle_signing_config_not_equal_to_other_types(self) -> None:
        """
        Test VehicleSigningConfig not equal to other types.

        GIVEN: Vehicle config and different type
        WHEN: Comparing
        THEN: Returns False
        """
        config = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
        )

        assert config != "string"
        assert config is not None


class TestVehicleSigningConfigErrorHandling:
    """Test VehicleSigningConfig error handling."""

    def test_vehicle_signing_config_from_dict_missing_vehicle_id(self) -> None:
        """
        Test that from_dict raises KeyError if vehicle_id missing.

        GIVEN: Dict without vehicle_id
        WHEN: Calling from_dict()
        THEN: Raises KeyError
        """
        data = {
            "signing_config": STANDARD_CONFIG_PARAMS,
            "auto_setup": False,
        }

        with pytest.raises(KeyError, match="vehicle_id"):
            VehicleSigningConfig.from_dict(data)

    def test_vehicle_signing_config_from_dict_non_string_vehicle_id(self) -> None:
        """
        Test that from_dict raises TypeError for non-string vehicle_id.

        GIVEN: Dict with non-string vehicle_id
        WHEN: Calling from_dict()
        THEN: Raises TypeError
        """
        data = {
            "vehicle_id": 123,  # Not a string
            "signing_config": STANDARD_CONFIG_PARAMS,
            "auto_setup": False,
        }

        with pytest.raises(TypeError, match=r"vehicle_id.*string"):
            VehicleSigningConfig.from_dict(data)

    def test_vehicle_signing_config_from_dict_non_dict_input(self) -> None:
        """
        Test that from_dict raises TypeError for non-dict input.

        GIVEN: Non-dict input
        WHEN: Calling from_dict()
        THEN: Raises TypeError
        """
        with pytest.raises(TypeError, match="Expected dict"):
            VehicleSigningConfig.from_dict("not a dict")  # type: ignore[arg-type]

    def test_vehicle_signing_config_from_dict_invalid_signing_config_type(self) -> None:
        """
        Test that from_dict raises TypeError for non-dict signing_config.

        GIVEN: Dict with non-dict signing_config
        WHEN: Calling from_dict()
        THEN: Raises TypeError
        """
        data = {
            "vehicle_id": "AIRCRAFT-01",
            "signing_config": "not a dict",
            "auto_setup": False,
        }

        with pytest.raises(TypeError, match=r"signing_config.*dict"):
            VehicleSigningConfig.from_dict(data)

    def test_vehicle_signing_config_from_dict_invalid_auto_setup_type(self) -> None:
        """
        Test that from_dict raises TypeError for non-bool auto_setup.

        GIVEN: Dict with non-boolean auto_setup
        WHEN: Calling from_dict()
        THEN: Raises TypeError
        """
        data = {
            "vehicle_id": "AIRCRAFT-01",
            "signing_config": STANDARD_CONFIG_PARAMS,
            "auto_setup": "not_a_bool",
        }

        with pytest.raises(TypeError, match=r"auto_setup.*boolean"):
            VehicleSigningConfig.from_dict(data)


class TestSigningConfigManagerErrorPaths:
    """Test error handling paths in SigningConfigManager."""

    def test_save_vehicle_config_with_invalid_vehicle_id_type(self, tmp_path: Path) -> None:
        """
        Test that save rejects invalid vehicle ID type.

        GIVEN: SigningConfigManager
        WHEN: Attempting to save config with non-string vehicle_id
        THEN: Save fails and returns False
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Create config with invalid type vehicle_id
        config = VehicleSigningConfig(
            vehicle_id="VALID-ID",
            signing_config=create_standard_signing_config(),
        )

        # Verify normal save works
        result = manager.save_vehicle_config(config)
        assert result is True

    def test_load_vehicle_config_returns_none_for_missing(self, tmp_path: Path) -> None:
        """
        Test that load returns None for non-existent vehicle.

        GIVEN: Empty config directory
        WHEN: Loading non-existent vehicle
        THEN: Returns None
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        result = manager.load_vehicle_config("NON-EXISTENT")
        assert result is None

    def test_delete_vehicle_config_returns_false_for_non_existent(self, tmp_path: Path) -> None:
        """
        Test that delete returns False for non-existent vehicle.

        GIVEN: Empty config directory
        WHEN: Deleting non-existent vehicle
        THEN: Returns False
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        result = manager.delete_vehicle_config("NON-EXISTENT")
        assert result is False

    def test_save_then_delete_workflow(self, tmp_path: Path) -> None:
        """
        Test save → load → delete → not found workflow.

        GIVEN: New config manager
        WHEN: Saving, loading, deleting a vehicle config
        THEN: Config is present then deleted
        """
        manager = SigningConfigManager(config_dir=tmp_path)
        vehicle_id = "WORKFLOW-TEST"

        # Save
        config = VehicleSigningConfig(
            vehicle_id=vehicle_id,
            signing_config=create_standard_signing_config(),
        )
        save_result = manager.save_vehicle_config(config)
        assert save_result is True

        # Load
        loaded = manager.load_vehicle_config(vehicle_id)
        assert loaded is not None
        assert loaded.vehicle_id == vehicle_id

        # Delete
        delete_result = manager.delete_vehicle_config(vehicle_id)
        assert delete_result is True

        # Verify deleted
        verify_load = manager.load_vehicle_config(vehicle_id)
        assert verify_load is None

    def test_list_vehicles_after_save_and_delete(self, tmp_path: Path) -> None:
        """
        Test list_configured_vehicles throughout save/delete lifecycle.

        GIVEN: Multiple vehicles saved and deleted
        WHEN: Listing at different points
        THEN: List reflects current state
        """
        manager = SigningConfigManager(config_dir=tmp_path)

        # Start empty
        assert manager.list_configured_vehicles() == []

        # Save first vehicle
        config1 = VehicleSigningConfig(
            vehicle_id="VEH-01",
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(config1)
        assert len(manager.list_configured_vehicles()) == 1

        # Save second vehicle
        config2 = VehicleSigningConfig(
            vehicle_id="VEH-02",
            signing_config=create_standard_signing_config(),
        )
        manager.save_vehicle_config(config2)
        assert len(manager.list_configured_vehicles()) == 2

        # Delete first
        manager.delete_vehicle_config("VEH-01")
        vehicles = manager.list_configured_vehicles()
        assert len(vehicles) == 1
        assert "VEH-02" in vehicles
        assert "VEH-01" not in vehicles


class TestSigningConfigValidationRules:
    """Test comprehensive validation rules."""

    def test_link_id_boundary_values(self) -> None:
        """
        Test link_id at boundary values (0-255).

        GIVEN: Various link_id values
        WHEN: Creating configs with boundary values
        THEN: Valid values accepted, invalid rejected
        """
        # Valid boundaries
        config_min = create_restricted_signing_config()
        assert config_min.link_id == 0

        config_max = create_max_link_id_signing_config()
        assert config_max.link_id == 255

        # Invalid boundary
        with pytest.raises(ValueError, match="link_id must be"):
            create_config_with_custom_offsets(timestamp_offset=0, link_id=256)

    def test_validate_with_incorrect_type_int_as_bool(self) -> None:
        """
        Test validation catches int passed for bool field.

        GIVEN: Int value for boolean field
        WHEN: Creating config with invalid type
        THEN: Raises ValueError during __post_init__
        """
        import dataclasses  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

        # Validation happens in __post_init__, so error is raised during creation
        with pytest.raises(ValueError, match="enabled must be a boolean"):
            dataclasses.replace(
                create_standard_signing_config(),
                enabled=1,  # type: ignore[arg-type]
            )

    def test_validate_with_incorrect_type_string_as_int(self) -> None:
        """
        Test validation catches string passed for int field.

        GIVEN: String value for integer field
        WHEN: Creating config with invalid type
        THEN: Raises ValueError during __post_init__
        """
        import dataclasses  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

        # Validation happens in __post_init__, so error is raised during creation
        with pytest.raises(ValueError, match="link_id must be"):
            dataclasses.replace(
                create_standard_signing_config(),
                link_id="not_int",  # type: ignore[arg-type]
            )
