"""
MAVLink 2.0 signing configuration persistence backend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_data_dir

from ardupilot_methodic_configurator.data_model_signing_config import (
    CONFIG_VERSION,
    VehicleSigningConfig,
)


class SigningConfigManager:
    """
    Manager for loading and saving signing configurations.

    This class handles persistence of signing configurations to JSON files
    with version control and concurrent access protection.

    Config file format:
    {
        "version": 1,
        "configs": {
            "vehicle_id": {...}
        }
    }
    """

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_dir: Directory for storing configuration files.
                       If None, uses platform-appropriate data directory.

        """
        self._logger = logging.getLogger(__name__)

        if config_dir is None:
            config_dir = Path(user_data_dir("ArduPilot Methodic Configurator"))

        self._config_dir = config_dir
        self._config_file = config_dir / "signing_configs.json"

    def load_vehicle_config(self, vehicle_id: str) -> Optional[VehicleSigningConfig]:
        """
        Load signing configuration for a specific vehicle.

        Args:
            vehicle_id: Vehicle identifier

        Returns:
            VehicleSigningConfig if found, None otherwise

        """
        configs = self._load_all_configs()
        if vehicle_id in configs:
            try:
                return VehicleSigningConfig.from_dict(configs[vehicle_id])
            except (KeyError, ValueError) as exc:
                self._logger.warning("Failed to load config for %s: %s", vehicle_id, exc)
        return None

    def save_vehicle_config(self, config: VehicleSigningConfig) -> bool:
        """
        Save signing configuration for a vehicle.

        Args:
            config: Vehicle signing configuration to save

        Returns:
            bool: True if saved successfully

        """
        try:
            configs = self._load_all_configs()
            configs[config.vehicle_id] = config.to_dict()
            self._save_all_configs(configs)
            return True
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.exception("Failed to save config: %s", exc)
            return False

    def delete_vehicle_config(self, vehicle_id: str) -> bool:
        """
        Delete signing configuration for a vehicle.

        Args:
            vehicle_id: Vehicle identifier

        Returns:
            bool: True if deleted, False if not found

        """
        try:
            configs = self._load_all_configs()
            if vehicle_id in configs:
                del configs[vehicle_id]
                self._save_all_configs(configs)
                return True
            return False
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.exception("Failed to delete config: %s", exc)
            return False

    def list_configured_vehicles(self) -> list[str]:
        """
        List all vehicles with saved configurations.

        Returns:
            list[str]: List of vehicle IDs

        """
        configs = self._load_all_configs()
        return sorted(configs.keys())

    def _load_all_configs(self) -> dict[str, Any]:
        """Load all configurations from file with version handling."""
        if not self._config_file.exists():
            return {}

        try:
            with open(self._config_file, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

                if not isinstance(data, dict):
                    self._logger.warning("Config file contains invalid data structure (not a dictionary)")
                    return {}

                version = data.get("version", 1)
                if version > CONFIG_VERSION:
                    self._logger.warning(
                        "Config file version %d is newer than supported version %d. Some features may not work correctly.",
                        version,
                        CONFIG_VERSION,
                    )

                configs: dict[str, Any] = data.get("configs", data)
                configs.pop("version", None)
                return configs

        except (json.JSONDecodeError, OSError) as exc:
            self._logger.warning("Failed to load configs: %s", exc)
            return {}

    def _save_all_configs(self, configs: dict[str, Any]) -> None:
        """Save all configurations to file with version and file locking."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        versioned_data = {
            "version": CONFIG_VERSION,
            "configs": configs,
        }

        temp_file = self._config_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                if os.name != "nt":
                    import fcntl  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(versioned_data, f, indent=2)

            os.replace(temp_file, self._config_file)

            if os.name != "nt":
                os.chmod(self._config_file, 0o600)

        except Exception:
            if temp_file.exists():
                temp_file.unlink()
            raise
