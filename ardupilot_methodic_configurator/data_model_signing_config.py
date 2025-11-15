"""
Data model for MAVLink message signing configuration.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field

from ardupilot_methodic_configurator import _


@dataclass
class SigningConfig:
    """
    Configuration for MAVLink message signing.

    This class holds all configuration related to MAVLink 2.0 message signing,
    including whether signing is enabled, enforcement settings, and timing parameters.
    """

    enabled: bool = False
    vehicle_id: str = ""
    enforce_signing: bool = True  # Reject unsigned messages from FC
    allow_unsigned_callback: bool = False  # Allow some unsigned messages during connection
    timestamp_tolerance_ms: int = 60000  # 1 minute tolerance for timestamp validation

    # Runtime state (not persisted)
    is_active: bool = field(default=False, init=False)  # Whether signing is currently active
    last_error: str = field(default="", init=False)  # Last error message

    def validate(self) -> tuple[bool, str]:
        """
        Validate the signing configuration.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
                             error_message is empty string if valid

        """
        if self.enabled and not self.vehicle_id:
            return False, _("Vehicle ID is required when signing is enabled")

        if self.enabled and not self.vehicle_id.strip():
            return False, _("Vehicle ID cannot be empty or whitespace")

        if self.timestamp_tolerance_ms < 0:
            return False, _("Timestamp tolerance must be non-negative")

        if self.timestamp_tolerance_ms > 3600000:  # 1 hour
            return False, _("Timestamp tolerance cannot exceed 1 hour (3600000 ms)")

        return True, ""

    def to_dict(self) -> dict:
        """
        Serialize configuration to dictionary.

        Returns:
            dict: Configuration as dictionary (excludes runtime state)

        """
        return {
            "enabled": self.enabled,
            "vehicle_id": self.vehicle_id,
            "enforce_signing": self.enforce_signing,
            "allow_unsigned_callback": self.allow_unsigned_callback,
            "timestamp_tolerance_ms": self.timestamp_tolerance_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SigningConfig":
        """
        Deserialize configuration from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            SigningConfig: New configuration instance

        """
        return cls(
            enabled=data.get("enabled", False),
            vehicle_id=data.get("vehicle_id", ""),
            enforce_signing=data.get("enforce_signing", True),
            allow_unsigned_callback=data.get("allow_unsigned_callback", False),
            timestamp_tolerance_ms=data.get("timestamp_tolerance_ms", 60000),
        )

    def get_summary(self) -> str:
        """
        Get a human-readable summary of the configuration.

        Returns:
            str: Configuration summary

        """
        if not self.enabled:
            return _("MAVLink signing disabled")

        status = _("MAVLink signing enabled for vehicle: %(vehicle_id)s") % {"vehicle_id": self.vehicle_id}

        if self.enforce_signing:
            status += "\n" + _("Unsigned messages will be rejected")
        else:
            status += "\n" + _("Unsigned messages will be accepted (not recommended)")

        if self.allow_unsigned_callback:
            status += "\n" + _("Some unsigned messages allowed during connection")

        status += "\n" + _("Timestamp tolerance: %(ms)d ms") % {"ms": self.timestamp_tolerance_ms}

        return status

    def __str__(self) -> str:
        """String representation of the configuration."""
        return self.get_summary()


# Example usage and testing
if __name__ == "__main__":
    # Test default configuration
    config = SigningConfig()
    print("Default config:")
    print(config)
    print()

    # Test validation
    is_valid, error = config.validate()
    print(f"Default config valid: {is_valid}")
    if not is_valid:
        print(f"Error: {error}")
    print()

    # Test enabled configuration
    config.enabled = True
    config.vehicle_id = "my_drone_001"
    print("Enabled config:")
    print(config)
    print()

    is_valid, error = config.validate()
    print(f"Enabled config valid: {is_valid}")
    if not is_valid:
        print(f"Error: {error}")
    print()

    # Test serialization
    config_dict = config.to_dict()
    print("Serialized:")
    print(config_dict)
    print()

    # Test deserialization
    restored_config = SigningConfig.from_dict(config_dict)
    print("Restored config:")
    print(restored_config)
    print()

    # Test invalid configuration
    invalid_config = SigningConfig(enabled=True, vehicle_id="")
    is_valid, error = invalid_config.validate()
    print(f"Invalid config valid: {is_valid}")
    print(f"Error: {error}")
