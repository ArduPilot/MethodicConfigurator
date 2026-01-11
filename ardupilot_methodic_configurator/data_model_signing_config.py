"""
MAVLink 2.0 signing configuration data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_data_dir

# Configuration file version for managing schema changes
CONFIG_VERSION = 1


@dataclass(eq=False)
class SigningConfig:
    """
    Configuration for MAVLink 2.0 message signing.

    This configuration controls how the application handles MAVLink signing
    when communicating with flight controllers.

    Attributes:
        enabled: Whether signing is enabled for MAVLink communication
        sign_outgoing: Whether to sign outgoing messages
        allow_unsigned_in: Whether to accept unsigned incoming messages
        accept_unsigned_callbacks: Whether to call unsigned message callbacks
        timestamp_offset: Offset to add to signing timestamps (microseconds)
        link_id: Link ID for signing (0-255)

    """

    enabled: bool = False
    sign_outgoing: bool = True
    allow_unsigned_in: bool = True
    accept_unsigned_callbacks: bool = True
    timestamp_offset: int = 0
    link_id: int = 0

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """
        Validate the signing configuration.

        Raises:
            ValueError: If any configuration value is invalid

        """
        if not isinstance(self.enabled, bool):
            msg = f"enabled must be a boolean, got {type(self.enabled).__name__}: {self.enabled!r}"
            raise ValueError(msg)

        if not isinstance(self.sign_outgoing, bool):
            msg = f"sign_outgoing must be a boolean, got {type(self.sign_outgoing).__name__}: {self.sign_outgoing!r}"
            raise ValueError(msg)

        if not isinstance(self.allow_unsigned_in, bool):
            msg = (
                f"allow_unsigned_in must be a boolean, got {type(self.allow_unsigned_in).__name__}: {self.allow_unsigned_in!r}"
            )
            raise ValueError(msg)

        if not isinstance(self.accept_unsigned_callbacks, bool):
            msg = (
                f"accept_unsigned_callbacks must be a boolean, "
                f"got {type(self.accept_unsigned_callbacks).__name__}: {self.accept_unsigned_callbacks!r}"
            )
            raise ValueError(msg)

        if not isinstance(self.timestamp_offset, int):
            msg = f"timestamp_offset must be an integer, got {type(self.timestamp_offset).__name__}: {self.timestamp_offset!r}"
            raise ValueError(msg)

        if not isinstance(self.link_id, int) or not 0 <= self.link_id <= 255:
            msg = f"link_id must be an integer between 0 and 255, got {type(self.link_id).__name__}: {self.link_id!r}"
            raise ValueError(msg)

    def __eq__(self, other: object) -> bool:
        """Compare SigningConfig instances for equality."""
        if not isinstance(other, SigningConfig):
            return NotImplemented
        return asdict(self) == asdict(other)

    def __hash__(self) -> int:
        """Compute hash based on configuration values."""
        return hash(
            (
                self.enabled,
                self.sign_outgoing,
                self.allow_unsigned_in,
                self.accept_unsigned_callbacks,
                self.timestamp_offset,
                self.link_id,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            dict: Configuration as a dictionary

        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SigningConfig":
        """
        Create configuration from dictionary.

        Args:
            data: Dictionary containing configuration values

        Returns:
            SigningConfig: New configuration instance

        Raises:
            ValueError: If data contains invalid values

        """
        # Filter to only known fields to avoid unexpected arguments
        known_fields = {
            "enabled",
            "sign_outgoing",
            "allow_unsigned_in",
            "accept_unsigned_callbacks",
            "timestamp_offset",
            "link_id",
        }
        unknown = set(data.keys()) - known_fields
        if unknown:
            logger = logging.getLogger(__name__)
            logger.warning("Ignoring unknown configuration fields: %s", unknown)
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """
        Serialize configuration to JSON string.

        Returns:
            str: JSON representation of the configuration

        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "SigningConfig":
        """
        Deserialize configuration from JSON string.

        Args:
            json_str: JSON string containing configuration

        Returns:
            SigningConfig: New configuration instance

        Raises:
            ValueError: If JSON is invalid or contains invalid values
            json.JSONDecodeError: If JSON parsing fails

        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def secure_defaults(cls) -> "SigningConfig":
        """
        Create a configuration with secure default settings.

        This creates a configuration that:
        - Enables signing
        - Signs all outgoing messages
        - Rejects unsigned incoming messages

        Returns:
            SigningConfig: Secure configuration instance

        """
        return cls(
            enabled=True,
            sign_outgoing=True,
            allow_unsigned_in=False,
            accept_unsigned_callbacks=False,
            timestamp_offset=0,
            link_id=0,
        )


@dataclass(eq=False)
class VehicleSigningConfig:
    """
    Per-vehicle signing configuration.

    Combines signing configuration with vehicle-specific settings.

    Attributes:
        vehicle_id: Unique identifier for the vehicle
        signing_config: MAVLink signing configuration
        auto_setup: Whether to automatically set up signing on connect

    """

    vehicle_id: str
    signing_config: SigningConfig = field(default_factory=SigningConfig)
    auto_setup: bool = False

    def __post_init__(self) -> None:
        """Validate vehicle configuration after initialization."""
        if not self.vehicle_id or not self.vehicle_id.strip():
            msg = "vehicle_id cannot be empty or whitespace"
            raise ValueError(msg)

    def __eq__(self, other: object) -> bool:
        """Compare VehicleSigningConfig instances for equality."""
        if not isinstance(other, VehicleSigningConfig):
            return NotImplemented
        return (
            self.vehicle_id == other.vehicle_id
            and self.signing_config == other.signing_config
            and self.auto_setup == other.auto_setup
        )

    def __hash__(self) -> int:
        """Compute hash based on vehicle ID, signing config, and auto_setup."""
        return hash((self.vehicle_id, self.signing_config, self.auto_setup))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "vehicle_id": self.vehicle_id,
            "signing_config": self.signing_config.to_dict(),
            "auto_setup": self.auto_setup,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VehicleSigningConfig":
        """Create from dictionary."""
        signing_config = SigningConfig.from_dict(data.get("signing_config", {}))
        return cls(
            vehicle_id=data["vehicle_id"],
            signing_config=signing_config,
            auto_setup=data.get("auto_setup", False),
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

                # Validate data is a dictionary
                if not isinstance(data, dict):
                    self._logger.warning("Config file contains invalid data structure (not a dictionary)")
                    return {}

                # Handle versioning
                version = data.get("version", 1)
                if version > CONFIG_VERSION:
                    self._logger.warning(
                        "Config file version %d is newer than supported version %d. Some features may not work correctly.",
                        version,
                        CONFIG_VERSION,
                    )

                # For version 1, configs are under "configs" key, or at root for legacy
                configs: dict[str, Any] = data.get("configs", data)
                # Remove version key if present at root level (legacy)
                configs.pop("version", None)
                return configs

        except (json.JSONDecodeError, OSError) as exc:
            self._logger.warning("Failed to load configs: %s", exc)
            return {}

    def _save_all_configs(self, configs: dict[str, Any]) -> None:
        """Save all configurations to file with version and file locking."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        # Create versioned structure
        versioned_data = {
            "version": CONFIG_VERSION,
            "configs": configs,
        }

        # Write atomically with file locking
        temp_file = self._config_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                # Apply file lock on Unix systems to prevent concurrent writes
                if os.name != "nt":
                    import fcntl  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(versioned_data, f, indent=2)

            # Atomic rename
            os.replace(temp_file, self._config_file)

            # Set restrictive permissions on Unix
            if os.name != "nt":
                os.chmod(self._config_file, 0o600)

        except Exception:
            # Clean up temp file on failure
            if temp_file.exists():
                temp_file.unlink()
            raise
