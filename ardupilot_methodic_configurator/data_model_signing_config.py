"""
MAVLink 2.0 signing configuration data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

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
            TypeError: If data is not a dictionary or contains wrong types

        """
        if not isinstance(data, dict):
            msg = f"Expected dict, got {type(data).__name__}"
            raise TypeError(msg)

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

        # Validate types before creating instance
        filtered_data = {}
        for k, v in data.items():
            if k not in known_fields:
                continue

            if k in ("enabled", "sign_outgoing", "allow_unsigned_in", "accept_unsigned_callbacks") and not isinstance(v, bool):
                msg = f"Field '{k}' must be boolean, got {type(v).__name__}: {v!r}"
                raise TypeError(msg)
            if k in ("timestamp_offset", "link_id") and not isinstance(v, int):
                msg = f"Field '{k}' must be integer, got {type(v).__name__}: {v!r}"
                raise TypeError(msg)

            filtered_data[k] = v

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
        """
        Create from dictionary.

        Args:
            data: Dictionary containing vehicle configuration

        Returns:
            VehicleSigningConfig: New configuration instance

        Raises:
            TypeError: If data is not a dictionary or contains wrong types
            KeyError: If required fields are missing
            ValueError: If data contains invalid values

        """
        if not isinstance(data, dict):
            msg = f"Expected dict, got {type(data).__name__}"
            raise TypeError(msg)

        if "vehicle_id" not in data:
            msg = "Missing required field 'vehicle_id'"
            raise KeyError(msg)

        vehicle_id = data["vehicle_id"]
        if not isinstance(vehicle_id, str):
            msg = f"Field 'vehicle_id' must be string, got {type(vehicle_id).__name__}: {vehicle_id!r}"
            raise TypeError(msg)

        # Validate signing_config if present
        signing_config_data = data.get("signing_config", {})
        if not isinstance(signing_config_data, dict):
            msg = f"Field 'signing_config' must be dict, got {type(signing_config_data).__name__}"
            raise TypeError(msg)
        signing_config = SigningConfig.from_dict(signing_config_data)

        # Validate auto_setup if present
        auto_setup = data.get("auto_setup", False)
        if not isinstance(auto_setup, bool):
            msg = f"Field 'auto_setup' must be boolean, got {type(auto_setup).__name__}: {auto_setup!r}"
            raise TypeError(msg)

        return cls(
            vehicle_id=vehicle_id,
            signing_config=signing_config,
            auto_setup=auto_setup,
        )
