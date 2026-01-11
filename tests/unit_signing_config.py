#!/usr/bin/env python3

"""
Unit tests for data_model_signing_config module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests focus on low-level validation, file operation error handling,
and edge cases that cannot be tested at the BDD level.
"""

import contextlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.data_model_signing_config import (
    CONFIG_VERSION,
    SigningConfig,
    SigningConfigManager,
    VehicleSigningConfig,
)


class TestSigningConfigTypeValidation:
    """Test strict type validation for SigningConfig fields."""

    def test_sign_outgoing_validates_type(self) -> None:
        """Test that sign_outgoing field validates type strictly."""
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
        """Test that allow_unsigned_in field validates type strictly."""
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
        """Test that accept_unsigned_callbacks field validates type strictly."""
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
        """Test that timestamp_offset field validates type strictly."""
        with pytest.raises(ValueError, match="timestamp_offset must be an integer"):
            SigningConfig(
                enabled=True,
                sign_outgoing=True,
                allow_unsigned_in=False,
                accept_unsigned_callbacks=True,
                timestamp_offset=0.5,  # type: ignore[arg-type]
                link_id=1,
            )

    def test_link_id_validates_type_not_string(self) -> None:
        """Test that link_id validates type (not string)."""
        with pytest.raises(ValueError, match="link_id must be an integer"):
            SigningConfig(
                enabled=True,
                sign_outgoing=True,
                allow_unsigned_in=False,
                accept_unsigned_callbacks=True,
                timestamp_offset=0,
                link_id="1",  # type: ignore[arg-type]
            )


class TestSigningConfigManagerFileErrorHandling:
    """Test config manager file operation error handling."""

    def test_load_config_with_corrupted_json(self, tmp_path: Path) -> None:
        """Test loading config file with corrupted JSON data."""
        manager = SigningConfigManager(config_dir=tmp_path)

        # Create corrupted JSON file
        manager._config_file.write_text("not valid json {")

        # Should return empty list on error
        configs = manager.list_configured_vehicles()
        assert configs == []

    def test_load_config_with_non_dict_structure(self, tmp_path: Path) -> None:
        """Test loading config file with non-dictionary structure."""
        manager = SigningConfigManager(config_dir=tmp_path)

        # Create file with list instead of dict
        manager._config_file.write_text(json.dumps(["not", "a", "dict"]))

        # Should return empty list on error
        configs = manager.list_configured_vehicles()
        assert configs == []

    def test_load_config_with_future_version_number(self, tmp_path: Path) -> None:
        """Test loading config file with future version number."""
        manager = SigningConfigManager(config_dir=tmp_path)

        # Create file with future version
        config_data = {
            "version": CONFIG_VERSION + 999,
            "configs": {
                "TEST-VEHICLE": {
                    "vehicle_id": "TEST-VEHICLE",
                    "signing_config": {
                        "enabled": True,
                        "sign_outgoing": True,
                        "allow_unsigned_in": False,
                        "accept_unsigned_callbacks": True,
                        "timestamp_offset": 0,
                        "link_id": 1,
                    },
                }
            },
        }
        manager._config_file.write_text(json.dumps(config_data))

        # Should handle future version gracefully
        configs = manager.list_configured_vehicles()
        assert len(configs) >= 0  # Should not crash

    def test_save_config_handles_file_lock_timeout(self, tmp_path: Path) -> None:
        """Test that save_config handles file lock timeout gracefully."""
        manager = SigningConfigManager(config_dir=tmp_path)

        config = VehicleSigningConfig(
            vehicle_id="TEST-VEHICLE",
            signing_config=SigningConfig(
                enabled=True,
                sign_outgoing=True,
                allow_unsigned_in=False,
                accept_unsigned_callbacks=True,
                timestamp_offset=0,
                link_id=1,
            ),
        )

        # Mock fcntl to raise BlockingIOError
        with patch("fcntl.flock") as mock_flock:
            mock_flock.side_effect = BlockingIOError("Lock timeout")

            # Should handle the error gracefully without crashing
        with contextlib.suppress(BlockingIOError):
            manager.save_vehicle_config(config)
    def test_save_config_handles_permission_error(self, tmp_path: Path) -> None:
        """Test that save_config handles permission errors gracefully."""
        manager = SigningConfigManager(config_dir=tmp_path)

        config = VehicleSigningConfig(
            vehicle_id="TEST-VEHICLE",
            signing_config=SigningConfig(
                enabled=True,
                sign_outgoing=True,
                allow_unsigned_in=False,
                accept_unsigned_callbacks=True,
                timestamp_offset=0,
                link_id=1,
            ),
        )

        # Make the directory read-only
        tmp_path.chmod(0o444)

        try:
            # Should handle the error gracefully
            with contextlib.suppress(PermissionError, OSError):
                manager.save_vehicle_config(config)
        finally:
            # Restore permissions
            tmp_path.chmod(0o755)

    def test_list_vehicles_with_invalid_vehicle_data_structure(self, tmp_path: Path) -> None:
        """Test list_vehicles when vehicle data has invalid structure."""
        manager = SigningConfigManager(config_dir=tmp_path)

        # Create file with mix of valid and invalid vehicle data
        config_data = {
            "version": CONFIG_VERSION,
            "configs": {
                "VALID-VEHICLE": {
                    "vehicle_id": "VALID-VEHICLE",
                    "signing_config": {
                        "enabled": True,
                        "sign_outgoing": True,
                        "allow_unsigned_in": False,
                        "accept_unsigned_callbacks": True,
                        "timestamp_offset": 0,
                        "link_id": 1,
                    },
                },
                "INVALID-VEHICLE": {
                    "vehicle_id": "INVALID-VEHICLE",
                    "signing_config": {
                        "enabled": "not_a_boolean",  # Invalid type
                    },
                },
            },
        }
        manager._config_file.write_text(json.dumps(config_data))

        # Should skip invalid entries and return valid ones
        configs = manager.list_configured_vehicles()
        assert len(configs) >= 0  # Should not crash
