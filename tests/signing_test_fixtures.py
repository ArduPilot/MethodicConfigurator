#!/usr/bin/env python3

"""
Shared test fixtures for signing tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.data_model_signing_config import SigningConfig

# Standard test config parameters - reused across multiple tests
STANDARD_CONFIG_PARAMS = {
    "enabled": True,
    "sign_outgoing": True,
    "allow_unsigned_in": False,
    "accept_unsigned_callbacks": True,
    "timestamp_offset": 0,
    "link_id": 1,
}

# Restricted config (no unsigned callbacks) - for security testing
RESTRICTED_CONFIG_PARAMS = {
    "enabled": True,
    "sign_outgoing": True,
    "allow_unsigned_in": False,
    "accept_unsigned_callbacks": False,
    "timestamp_offset": 0,
    "link_id": 0,
}

# Maximum link ID config - for boundary testing
MAX_LINK_ID_CONFIG_PARAMS = {
    "enabled": True,
    "sign_outgoing": True,
    "allow_unsigned_in": False,
    "accept_unsigned_callbacks": False,
    "timestamp_offset": 0,
    "link_id": 255,  # MAVLink link ID max
}


def create_standard_signing_config() -> SigningConfig:
    """Create a standard SigningConfig for testing."""
    return SigningConfig(**STANDARD_CONFIG_PARAMS)


def create_restricted_signing_config() -> SigningConfig:
    """Create a restricted SigningConfig for security testing."""
    return SigningConfig(**RESTRICTED_CONFIG_PARAMS)


def create_max_link_id_signing_config() -> SigningConfig:
    """Create a SigningConfig with maximum link ID for boundary testing."""
    return SigningConfig(**MAX_LINK_ID_CONFIG_PARAMS)


# JSON dict representations for file/serialization tests
RESTRICTED_CONFIG_JSON = {
    "enabled": True,
    "sign_outgoing": True,
    "allow_unsigned_in": False,
    "accept_unsigned_callbacks": False,
    "timestamp_offset": 0,
    "link_id": 0,
}

MAX_LINK_ID_CONFIG_JSON = {
    "enabled": True,
    "sign_outgoing": True,
    "allow_unsigned_in": False,
    "accept_unsigned_callbacks": False,
    "timestamp_offset": 0,
    "link_id": 255,  # MAVLink link ID max
}

# Standard JSON config structure for file-based tests
STANDARD_JSON_CONFIG = {
    "configs": {
        "TEST-VEHICLE": {
            "vehicle_id": "TEST-VEHICLE",
            "signing_config": STANDARD_CONFIG_PARAMS,
        }
    }
}


# Assertion helper functions to verify common config properties
def assert_secure_defaults_config(config: SigningConfig) -> None:
    """Assert that a config matches secure_defaults() expectations."""
    assert config.enabled is True
    assert config.sign_outgoing is True
    assert config.allow_unsigned_in is False
    assert config.accept_unsigned_callbacks is False


# Aliases for backward compatibility and semantic clarity in tests
assert_restricted_config = assert_secure_defaults_config
assert_core_restricted_fields = assert_secure_defaults_config


def create_config_with_custom_offsets(timestamp_offset: int, link_id: int) -> SigningConfig:
    """Create a restricted config with custom timestamp offset and link ID for testing."""
    return SigningConfig(
        enabled=True,
        sign_outgoing=True,
        allow_unsigned_in=False,
        accept_unsigned_callbacks=False,
        timestamp_offset=timestamp_offset,
        link_id=link_id,
    )
