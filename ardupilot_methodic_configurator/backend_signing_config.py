"""
MAVLink 2.0 signing configuration persistence backend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_data_dir

from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.data_model_signing_config import VehicleSigningConfig

# Constants
SIGNING_CONFIG_FILENAME = "signing_configs.json"
SIGNING_SCHEMA_FILENAME = "schema_signing_config.json"


class SigningConfigManager(FilesystemJSONWithSchema):
    """
    Manager for loading and saving signing configurations.

    This class handles persistence of signing configurations using
    JSON schema validation via FilesystemJSONWithSchema.
    """

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_dir: Directory for storing configuration files.
                       If None, uses platform-appropriate data directory.

        """
        super().__init__(SIGNING_CONFIG_FILENAME, SIGNING_SCHEMA_FILENAME)
        self._logger = logging.getLogger(__name__)

        if config_dir is None:
            # FilesystemJSONWithSchema expects str for data_dir
            # backend_filesystem_json_with_schema usage pattern suggests passing dir to load/save methods
            # but usually we want to store the base dir here.
            self._config_dir_path = Path(user_data_dir("ArduPilot Methodic Configurator"))
        else:
            self._config_dir_path = config_dir

    @property
    def config_dir(self) -> str:
        """Get the configuration directory as string."""
        return str(self._config_dir_path)

    def load_vehicle_config(self, vehicle_id: str) -> Optional[VehicleSigningConfig]:
        """
        Load signing configuration for a specific vehicle.

        Args:
            vehicle_id: Vehicle identifier

        Returns:
            VehicleSigningConfig if found, None otherwise

        """
        if not vehicle_id or not isinstance(vehicle_id, str):
            self._logger.error("Invalid vehicle_id: must be a non-empty string, got %r", vehicle_id)
            return None

        configs_data = self._load_all_configs()
        # The schema defines patternProperties for vehicle IDs directly in the root object
        # structure: { "vehicle_id": { ... } }

        if vehicle_id in configs_data:
            try:
                return VehicleSigningConfig.from_dict(configs_data[vehicle_id])
            except (KeyError, ValueError, TypeError) as exc:
                self._logger.error(
                    "Failed to load signing configuration for vehicle '%s': %s. "
                    "The configuration file may be corrupted or have an invalid format.",
                    vehicle_id,
                    exc,
                )
        else:
            self._logger.debug("No signing configuration found for vehicle '%s'", vehicle_id)
        return None

    def save_vehicle_config(self, config: VehicleSigningConfig) -> bool:
        """
        Save signing configuration for a vehicle.

        Args:
            config: Vehicle signing configuration to save

        Returns:
            bool: True if saved successfully

        """
        if not isinstance(config, VehicleSigningConfig):
            self._logger.error(
                "Invalid config type: expected VehicleSigningConfig, got %s",
                type(config).__name__,
            )
            return False

        try:
            # Validate config before saving
            config.signing_config.validate()
        except ValueError as exc:
            self._logger.error(
                "Cannot save invalid signing configuration for vehicle '%s': %s",
                config.vehicle_id,
                exc,
            )
            return False

        try:
            configs_data = self._load_all_configs()
            configs_data[config.vehicle_id] = config.to_dict()
            success = self._save_all_configs(configs_data)
            if success:
                self._logger.info("Successfully saved signing configuration for vehicle '%s'", config.vehicle_id)
            return success
        except (OSError, PermissionError) as exc:
            self._logger.exception(
                "Failed to save signing configuration for vehicle '%s': %s. Check file permissions and disk space.",
                config.vehicle_id,
                exc,
            )
            return False
        except (KeyError, TypeError, ValueError) as exc:
            self._logger.exception(
                "Failed to save signing configuration for vehicle '%s' due to invalid data: %s",
                config.vehicle_id,
                exc,
            )
            return False

    def delete_vehicle_config(self, vehicle_id: str) -> bool:
        """
        Delete signing configuration for a vehicle.

        Args:
            vehicle_id: Vehicle identifier

        Returns:
            bool: True if deleted, False if not found

        """
        if not vehicle_id or not isinstance(vehicle_id, str):
            self._logger.error("Invalid vehicle_id: must be a non-empty string, got %r", vehicle_id)
            return False

        try:
            configs_data = self._load_all_configs()
            if vehicle_id in configs_data:
                del configs_data[vehicle_id]
                success = self._save_all_configs(configs_data)
                if success:
                    self._logger.info("Successfully deleted signing configuration for vehicle '%s'", vehicle_id)
                return success
            self._logger.debug("No signing configuration found for vehicle '%s' to delete", vehicle_id)
            return False
        except (OSError, PermissionError) as exc:
            self._logger.exception(
                "Failed to delete signing configuration for vehicle '%s': %s. Check file permissions.",
                vehicle_id,
                exc,
            )
            return False

    def list_configured_vehicles(self) -> list[str]:
        """
        List all vehicles with saved configurations.

        Returns:
            list[str]: List of vehicle IDs

        """
        configs_data = self._load_all_configs()
        return sorted(configs_data.keys())

    def _load_all_configs(self) -> dict[str, Any]:
        """Load all configurations from file."""
        # FilesystemJSONWithSchema.load_json_data returns dict
        # The schema we created matches the dictionary of vehicle configs directly
        data = self.load_json_data(self.config_dir)
        if not isinstance(data, dict):
            # FilesystemJSONWithSchema might return list/other if JSON is valid JSON but matches "any" type
            # or if validation failed but returned data anyway.
            # We enforce dict here to prevent crashes in list_configured_vehicles
            self._logger.warning(
                "Configuration file contains invalid data type %s, expected dict. Starting with empty configuration.",
                type(data).__name__,
            )
            return {}
        return data

    def _save_all_configs(self, configs: dict[str, Any]) -> bool:
        """Save all configurations to file with file locking."""
        self._config_dir_path.mkdir(parents=True, exist_ok=True)

        # Use file locking for atomic save operations
        config_file = self._config_dir_path / SIGNING_CONFIG_FILENAME
        temp_file = config_file.with_suffix(".tmp")
        lock_file = self._config_dir_path / ".signing_configs.lock"

        try:
            # Acquire lock BEFORE any file operations to prevent race conditions
            with open(lock_file, "a+", encoding="utf-8") as lock:
                if os.name != "nt":
                    import fcntl  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                else:
                    # Windows file locking using msvcrt
                    import msvcrt  # noqa: PLC0415 # pylint: disable=import-outside-toplevel,import-error

                    # Lock 1KB region (adequate for lock file)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1024)  # type: ignore[attr-defined]

                # Now perform file operations under lock protection
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(configs, f, indent=2)

                # Atomic rename
                os.replace(temp_file, config_file)

                # Set restrictive permissions on Unix
                if os.name != "nt":
                    os.chmod(config_file, 0o600)

            return True

        except (OSError, PermissionError) as exc:
            self._logger.exception("Failed to save configuration due to file operation error: %s", exc)
            # Clean up temp file on failure
            if temp_file.exists():
                with contextlib.suppress(OSError):
                    temp_file.unlink()
            return False
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self._logger.exception("Failed to save configuration due to invalid data: %s", exc)
            if temp_file.exists():
                with contextlib.suppress(OSError):
                    temp_file.unlink()
            return False
