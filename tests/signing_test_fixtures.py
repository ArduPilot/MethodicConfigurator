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


def create_standard_signing_config() -> SigningConfig:
    """Create a standard SigningConfig for testing."""
    return SigningConfig(**STANDARD_CONFIG_PARAMS)


# Standard JSON config structure for file-based tests
STANDARD_JSON_CONFIG = {
    "configs": {
        "TEST-VEHICLE": {
            "vehicle_id": "TEST-VEHICLE",
            "signing_config": STANDARD_CONFIG_PARAMS,
        }
    }
}
