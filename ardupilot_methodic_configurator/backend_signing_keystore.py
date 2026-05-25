"""
MAVLink 2.0 signing keystore for secure key management using OS keyring.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import logging
import secrets
from typing import Optional

# Constants
SIGNING_KEY_LENGTH = 32
KEYRING_SERVICE = "ardupilot_methodic_configurator_signing"


class SigningKeystore:
    """
    Secure keystore for MAVLink 2.0 signing keys using OS keyring.

    This class provides secure storage for signing keys using the operating system's
    native keyring/credential storage:

    - **Windows**: Credential Manager (built-in, no setup required)
    - **macOS**: Keychain (built-in, no setup required)
    - **Linux**: Secret Service / GNOME Keyring / KDE Wallet (requires installation on headless systems)

    Security features:
    - Cryptographically secure key generation using secrets module
    - Per-vehicle key isolation
    - Integration with OS-level security infrastructure
    - No weak fallbacks or obfuscation

    Requirements:
    - keyring package must be installed
    - OS keyring must be available and functional
    - On Linux headless systems: gnome-keyring or kwallet must be configured

    Raises:
        ImportError: If keyring package is not available
        ConnectionError: If OS keyring is not available

    """

    def __init__(self) -> None:
        """
        Initialize the signing keystore with OS keyring backend.

        Raises:
            ImportError: If keyring package is not installed
            ConnectionError: If OS keyring is not available

        """
        self._logger = logging.getLogger(__name__)

        # Check keyring availability
        if not self._check_keyring_available():
            msg = (
                "OS keyring is not available. "
                "Install keyring support for your OS:\n"
                "  Windows/macOS: Already built-in\n"
                "  Linux: Install gnome-keyring or kwallet and ensure it's configured\n"
                "  All platforms: pip install keyring"
            )
            self._logger.error(msg)
            raise ConnectionError(msg)

        self._logger.info("Keyring initialized successfully")

    def _check_keyring_available(self) -> bool:
        """
        Check if OS keyring is available and functional.

        Returns:
            bool: True if keyring is available and working.

        """
        try:
            import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel # type: ignore[import]

            backend = keyring.get_keyring()
            if backend is None:
                self._logger.error("No keyring backend available")
                return False

            test_key = f"_test_keyring_{secrets.token_hex(4)}"
            try:
                keyring.set_password(KEYRING_SERVICE, test_key, "test")
                keyring.delete_password(KEYRING_SERVICE, test_key)
            except Exception as test_exc:  # pylint: disable=broad-except
                self._logger.warning("Keyring test operation failed: %s", test_exc)
                return False

            return True

        except ImportError:
            self._logger.error("keyring package not installed. Install with: pip install keyring")
            return False
        except Exception as exc:  # pylint: disable=broad-except
            exc_name = type(exc).__name__
            self._logger.error("Keyring availability check failed (%s): %s", exc_name, exc)
            return False

    def generate_key(self) -> bytes:
        """
        Generate a cryptographically secure signing key.

        Returns:
            bytes: A 32-byte (256-bit) random key suitable for HMAC-SHA256.

        """
        return secrets.token_bytes(SIGNING_KEY_LENGTH)

    def store_key(self, vehicle_id: str, key: bytes, description: str = "") -> bool:
        """Store a signing key for a specific vehicle in OS keyring."""
        if len(key) != SIGNING_KEY_LENGTH:
            msg = f"Key must be {SIGNING_KEY_LENGTH} bytes, got {len(key)} bytes"
            raise ValueError(msg)

        if not vehicle_id or not isinstance(vehicle_id, str):
            msg = "Vehicle ID must be a non-empty string"
            raise ValueError(msg)

        try:
            import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel # type: ignore[import]

            key_b64 = base64.b64encode(key).decode("ascii")
            keyring.set_password(KEYRING_SERVICE, vehicle_id, key_b64)

            self._logger.info(
                "Stored signing key for vehicle '%s' in OS keyring%s",
                vehicle_id,
                f" ({description})" if description else "",
            )
            return True

        except Exception as exc:
            msg = f"Failed to store key in OS keyring: {exc}"
            self._logger.error(msg)
            raise ConnectionError(msg) from exc

    def retrieve_key(self, vehicle_id: str) -> Optional[bytes]:
        """Retrieve a stored signing key for a vehicle."""
        if not vehicle_id or not isinstance(vehicle_id, str):
            return None

        try:
            import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel # type: ignore[import]

            key_b64 = keyring.get_password(KEYRING_SERVICE, vehicle_id)
            if key_b64 is None:
                self._logger.debug("No key found for vehicle '%s'", vehicle_id)
                return None

            key = base64.b64decode(key_b64)

            if len(key) != SIGNING_KEY_LENGTH:
                msg = (
                    f"Retrieved key for vehicle '{vehicle_id}' has invalid length: "
                    f"{len(key)} bytes (expected {SIGNING_KEY_LENGTH}). Key may be corrupted."
                )
                self._logger.error(msg)
                raise ValueError(msg)

            self._logger.debug("Retrieved key for vehicle '%s' from keyring", vehicle_id)
            return key

        except ValueError:
            raise
        except Exception as exc:
            msg = f"Failed to retrieve key from OS keyring: {exc}"
            self._logger.error(msg)
            raise ConnectionError(msg) from exc

    def delete_key(self, vehicle_id: str) -> bool:
        """Delete a stored signing key for a vehicle."""
        if not vehicle_id or not isinstance(vehicle_id, str):
            return False

        import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel # type: ignore[import]
        import keyring.errors  # noqa: PLC0415 # pylint: disable=import-outside-toplevel # type: ignore[import]

        try:
            keyring.delete_password(KEYRING_SERVICE, vehicle_id)
            self._logger.info("Deleted signing key for vehicle '%s'", vehicle_id)
            return True

        except keyring.errors.PasswordDeleteError:
            self._logger.debug("Key not found for vehicle '%s'", vehicle_id)
            return False
        except Exception as exc:
            msg = f"Failed to delete key from OS keyring: {exc}"
            self._logger.error(msg)
            raise ConnectionError(msg) from exc

    def list_vehicles(self) -> list[str]:
        """List all vehicles with stored signing keys."""
        self._logger.debug(
            "Keyring does not support enumerating stored keys. Use retrieve_key() with known vehicle IDs instead."
        )
        return []

    def rotate_key(self, vehicle_id: str) -> Optional[bytes]:
        """Rotate a signing key by generating a new one and updating storage."""
        try:
            new_key = self.generate_key()
            if self.store_key(vehicle_id, new_key, description="Rotated key"):
                self._logger.info("Successfully rotated signing key for vehicle '%s'", vehicle_id)
                return new_key
            return None

        except Exception as exc:  # pylint: disable=broad-except
            self._logger.error("Failed to rotate signing key for vehicle '%s': %s", vehicle_id, exc)
            return None
