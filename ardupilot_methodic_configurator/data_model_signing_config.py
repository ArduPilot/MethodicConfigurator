"""
MAVLink 2.0 signing configuration data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
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
            msg = "enabled must be a boolean"
            raise ValueError(msg)

        if not isinstance(self.sign_outgoing, bool):
            msg = "sign_outgoing must be a boolean"
            raise ValueError(msg)

        if not isinstance(self.allow_unsigned_in, bool):
            msg = "allow_unsigned_in must be a boolean"
            raise ValueError(msg)

        if not isinstance(self.accept_unsigned_callbacks, bool):
            msg = "accept_unsigned_callbacks must be a boolean"
            raise ValueError(msg)

        if not isinstance(self.timestamp_offset, int):
            msg = "timestamp_offset must be an integer"
            raise ValueError(msg)

        if not isinstance(self.link_id, int) or not 0 <= self.link_id <= 255:
            msg = "link_id must be an integer between 0 and 255"
            raise ValueError(msg)

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


@dataclass
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

    This class handles persistence of signing configurations to JSON files.
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
            from platformdirs import user_data_dir  # pylint: disable=import-outside-toplevel

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

    def _load_all_configs(self) -> dict[str, dict[str, object]]:
        """Load all configurations from file."""
        if not self._config_file.exists():
            return {}

        try:
            with open(self._config_file, encoding="utf-8") as f:
                data: dict[str, dict[str, object]] = json.load(f)
                return data
        except (json.JSONDecodeError, OSError) as exc:
            self._logger.warning("Failed to load configs: %s", exc)
            return {}

    def _save_all_configs(self, configs: dict[str, dict[str, object]]) -> None:
        """Save all configurations to file."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=2)
