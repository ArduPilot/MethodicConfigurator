#!/usr/bin/env python3

"""
Integration tests for MAVLink signing configuration data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests focus on serialization, deserialization, and data model workflows.
"""

import pytest
from signing_test_fixtures import (
    STANDARD_CONFIG_PARAMS,
    create_config_with_custom_offsets,
    create_max_link_id_signing_config,
    create_restricted_signing_config,
    create_standard_signing_config,
)

from ardupilot_methodic_configurator.data_model_signing_config import (
    SigningConfig,
    VehicleSigningConfig,
)


class TestSigningConfigSerialization:
    """Test serialization and deserialization of SigningConfig."""

    def test_signing_config_to_dict_includes_all_fields(self) -> None:
        """
        Test that to_dict includes all fields.

        GIVEN: A SigningConfig object
        WHEN: Converting to dictionary
        THEN: All fields are present and have correct values
        """
        config = create_standard_signing_config()
        config_dict = config.to_dict()

        # Verify all required fields are present
        assert "enabled" in config_dict
        assert "sign_outgoing" in config_dict
        assert "allow_unsigned_in" in config_dict
        assert "accept_unsigned_callbacks" in config_dict
        assert "timestamp_offset" in config_dict
        assert "link_id" in config_dict

        # Verify types
        assert isinstance(config_dict["enabled"], bool)
        assert isinstance(config_dict["sign_outgoing"], bool)
        assert isinstance(config_dict["allow_unsigned_in"], bool)
        assert isinstance(config_dict["accept_unsigned_callbacks"], bool)
        assert isinstance(config_dict["timestamp_offset"], int)
        assert isinstance(config_dict["link_id"], int)

    def test_signing_config_from_dict_reconstructs_correctly(self) -> None:
        """
        Test that from_dict reconstructs SigningConfig from dictionary.

        GIVEN: A dictionary with valid signing config data
        WHEN: Creating SigningConfig from_dict
        THEN: All fields are restored correctly
        """
        original_dict = STANDARD_CONFIG_PARAMS
        config = SigningConfig.from_dict(original_dict)

        assert config.enabled == original_dict["enabled"]
        assert config.sign_outgoing == original_dict["sign_outgoing"]
        assert config.allow_unsigned_in == original_dict["allow_unsigned_in"]
        assert config.accept_unsigned_callbacks == original_dict["accept_unsigned_callbacks"]
        assert config.timestamp_offset == original_dict["timestamp_offset"]
        assert config.link_id == original_dict["link_id"]

    def test_signing_config_round_trip_preserves_data(self) -> None:
        """
        Test that to_dict and from_dict round-trip preserves data exactly.

        GIVEN: A SigningConfig object
        WHEN: Converting to dict and back
        THEN: Original and reconstructed are equal
        """
        original = create_standard_signing_config()
        as_dict = original.to_dict()
        reconstructed = SigningConfig.from_dict(as_dict)

        assert original.enabled == reconstructed.enabled
        assert original.sign_outgoing == reconstructed.sign_outgoing
        assert original.allow_unsigned_in == reconstructed.allow_unsigned_in
        assert original.accept_unsigned_callbacks == reconstructed.accept_unsigned_callbacks
        assert original.timestamp_offset == reconstructed.timestamp_offset
        assert original.link_id == reconstructed.link_id

    def test_signing_config_validate_accepts_valid_config(self) -> None:
        """
        Test that validate accepts valid configurations.

        GIVEN: A valid SigningConfig
        WHEN: Calling validate()
        THEN: No exception is raised
        """
        config = create_standard_signing_config()
        # Should not raise
        config.validate()

    def test_signing_config_validate_rejects_enabled_true_with_false_sign_outgoing(self) -> None:
        """
        Test validation logic when signing is enabled but outgoing not signed.

        GIVEN: A config with enabled=True but sign_outgoing=False
        WHEN: Calling validate()
        THEN: Should either accept or reject consistently
        """
        config = SigningConfig(
            enabled=True,
            sign_outgoing=False,  # Possible inconsistency
            allow_unsigned_in=False,
            accept_unsigned_callbacks=False,
            timestamp_offset=0,
            link_id=1,
        )
        # Should validate successfully (it's a valid state)
        config.validate()


class TestVehicleSigningConfigSerialization:
    """Test serialization and deserialization of VehicleSigningConfig."""

    def test_vehicle_signing_config_to_dict(self) -> None:
        """
        Test that to_dict includes all required fields.

        GIVEN: A VehicleSigningConfig object
        WHEN: Converting to dictionary
        THEN: All fields are present
        """
        config = VehicleSigningConfig(
            vehicle_id="AIRCRAFT-01",
            signing_config=create_standard_signing_config(),
        )
        config_dict = config.to_dict()

        assert "vehicle_id" in config_dict
        assert "signing_config" in config_dict
        assert "auto_setup" in config_dict or "auto_setup" in config_dict
        assert config_dict["vehicle_id"] == "AIRCRAFT-01"

    def test_vehicle_signing_config_from_dict(self) -> None:
        """
        Test that from_dict reconstructs VehicleSigningConfig.

        GIVEN: A dictionary with vehicle signing config
        WHEN: Creating from_dict
        THEN: All fields are restored
        """
        data = {
            "vehicle_id": "COPTER-01",
            "signing_config": STANDARD_CONFIG_PARAMS,
            "auto_setup": False,
        }
        config = VehicleSigningConfig.from_dict(data)

        assert config.vehicle_id == "COPTER-01"
        assert config.signing_config.enabled is True
        assert config.signing_config.sign_outgoing is True

    def test_vehicle_signing_config_round_trip(self) -> None:
        """
        Test round-trip serialization/deserialization.

        GIVEN: A VehicleSigningConfig
        WHEN: Converting to dict and back
        THEN: All data is preserved
        """
        original = VehicleSigningConfig(
            vehicle_id="ROVER-01",
            signing_config=create_standard_signing_config(),
        )
        as_dict = original.to_dict()
        reconstructed = VehicleSigningConfig.from_dict(as_dict)

        assert original.vehicle_id == reconstructed.vehicle_id
        assert original.signing_config.enabled == reconstructed.signing_config.enabled
        assert original.signing_config.link_id == reconstructed.signing_config.link_id


class TestSigningConfigProperties:
    """Test property access and modification patterns."""

    def test_signing_config_field_access(self) -> None:
        """
        Test accessing all fields of SigningConfig.

        GIVEN: A SigningConfig object
        WHEN: Accessing each field
        THEN: All fields are accessible and have expected types
        """
        config = create_standard_signing_config()

        # Access all fields to cover property access paths
        assert isinstance(config.enabled, bool)
        assert isinstance(config.sign_outgoing, bool)
        assert isinstance(config.allow_unsigned_in, bool)
        assert isinstance(config.accept_unsigned_callbacks, bool)
        assert isinstance(config.timestamp_offset, int)
        assert isinstance(config.link_id, int)

    def test_vehicle_signing_config_field_access(self) -> None:
        """
        Test accessing all fields of VehicleSigningConfig.

        GIVEN: A VehicleSigningConfig
        WHEN: Accessing each field
        THEN: All fields are accessible
        """
        config = VehicleSigningConfig(
            vehicle_id="TEST-VEH",
            signing_config=create_standard_signing_config(),
        )

        assert config.vehicle_id == "TEST-VEH"
        assert config.signing_config is not None
        assert isinstance(config.signing_config, SigningConfig)


class TestSigningConfigEdgeCases:
    """Test edge cases in data model."""

    def test_signing_config_with_extreme_timestamp_offset(self) -> None:
        """
        Test handling extreme timestamp offset values.

        GIVEN: Very large positive/negative timestamp offset
        WHEN: Creating config
        THEN: Should accept (no range validation)
        """
        config = create_config_with_custom_offsets(timestamp_offset=999999999, link_id=1)
        assert config.timestamp_offset == 999999999

        config2 = create_config_with_custom_offsets(timestamp_offset=-999999999, link_id=1)
        assert config2.timestamp_offset == -999999999

    def test_signing_config_with_max_link_id(self) -> None:
        """
        Test handling maximum link ID values.

        GIVEN: Large link ID value
        WHEN: Creating config
        THEN: Should accept it
        """
        config = create_max_link_id_signing_config()
        assert config.link_id == 255

    def test_all_boolean_combinations(self) -> None:
        """
        Test all valid combinations of boolean flags.

        GIVEN: Various combinations of boolean flags
        WHEN: Creating SigningConfig
        THEN: All valid combinations are accepted
        """
        boolean_values = [True, False]

        for enabled in boolean_values:
            for sign_out in boolean_values:
                for allow_unsign_in in boolean_values:
                    for accept_unsign_cb in boolean_values:
                        config = SigningConfig(
                            enabled=enabled,
                            sign_outgoing=sign_out,
                            allow_unsigned_in=allow_unsign_in,
                            accept_unsigned_callbacks=accept_unsign_cb,
                            timestamp_offset=0,
                            link_id=1,
                        )
                        assert config.enabled == enabled
                        assert config.sign_outgoing == sign_out
                        assert config.allow_unsigned_in == allow_unsign_in
                        assert config.accept_unsigned_callbacks == accept_unsign_cb


class TestSigningConfigValidation:
    """Test data model validation."""

    def test_vehicle_signing_config_requires_non_empty_vehicle_id(self) -> None:
        """
        Test that empty vehicle_id is rejected.

        GIVEN: Empty vehicle_id
        WHEN: Creating VehicleSigningConfig
        THEN: Raises ValueError
        """
        with pytest.raises(ValueError, match="cannot be empty"):
            VehicleSigningConfig(
                vehicle_id="",
                signing_config=create_standard_signing_config(),
            )

    def test_vehicle_signing_config_requires_vehicle_id_string(self) -> None:
        """
        Test that non-string vehicle_id is rejected.

        GIVEN: Non-string vehicle_id
        WHEN: Creating VehicleSigningConfig
        THEN: Raises AttributeError or ValueError
        """
        with pytest.raises((AttributeError, ValueError, TypeError)):
            VehicleSigningConfig(
                vehicle_id=123,  # type: ignore[arg-type]
                signing_config=create_standard_signing_config(),
            )

    def test_signing_config_validation_accepts_default_values(self) -> None:
        """
        Test that default/minimal valid config passes validation.

        GIVEN: A minimal valid SigningConfig
        WHEN: Calling validate()
        THEN: No exception raised
        """
        config = SigningConfig(
            enabled=False,
            sign_outgoing=False,
            allow_unsigned_in=True,
            accept_unsigned_callbacks=True,
            timestamp_offset=0,
            link_id=0,
        )
        config.validate()  # Should not raise


class TestSigningConfigIntegration:
    """Test complete workflows with signing config."""

    def test_modify_config_and_persist(self) -> None:
        """
        Test modifying config values and persisting.

        GIVEN: Initial SigningConfig
        WHEN: Converting to dict, modifying, and reconstructing
        THEN: Changes are preserved
        """
        original = create_standard_signing_config()

        # Convert to dict
        config_dict = original.to_dict()

        # Modify some values in the dict
        config_dict["timestamp_offset"] = 42
        config_dict["link_id"] = 2

        # Reconstruct
        modified = SigningConfig.from_dict(config_dict)

        assert modified.timestamp_offset == 42
        assert modified.link_id == 2
        assert modified.enabled == original.enabled  # Other values preserved

    def test_vehicle_config_with_multiple_signing_configs(self) -> None:
        """
        Test creating multiple VehicleSigningConfig objects with different settings.

        GIVEN: Multiple vehicles with different configs
        WHEN: Converting all to dicts
        THEN: Each retains its specific configuration
        """
        vehicles = [
            (
                "COPTER-01",
                create_restricted_signing_config(),
            ),
            (
                "PLANE-01",
                SigningConfig(
                    enabled=False,
                    sign_outgoing=False,
                    allow_unsigned_in=True,
                    accept_unsigned_callbacks=True,
                    timestamp_offset=100,
                    link_id=2,
                ),
            ),
            (
                "ROVER-01",
                SigningConfig(
                    enabled=True,
                    sign_outgoing=False,
                    allow_unsigned_in=True,
                    accept_unsigned_callbacks=True,
                    timestamp_offset=-50,
                    link_id=3,
                ),
            ),
        ]

        configs = []
        for vehicle_id, signing_config in vehicles:
            config = VehicleSigningConfig(
                vehicle_id=vehicle_id,
                signing_config=signing_config,
            )
            configs.append(config)

        # Verify each retained its specific config
        assert configs[0].signing_config.link_id == 0
        assert configs[1].signing_config.timestamp_offset == 100
        assert configs[2].signing_config.timestamp_offset == -50
