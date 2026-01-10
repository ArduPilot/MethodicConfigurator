"""
MAVLink 2.0 signing keystore for secure key management.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

# Constants
SIGNING_KEY_LENGTH = 32  # 256 bits for HMAC-SHA256
APP_NAME = "ArduPilot Methodic Configurator"
KEYSTORE_FILENAME = "mavlink_signing_keys.json"
KEYSTORE_VERSION = 1


@dataclass
class StoredKey:
    """Represents a stored signing key with metadata."""

    key_id: str
    vehicle_id: str
    created_at: str
    encrypted_key: str  # Base64 encoded encrypted key
    salt: str  # Base64 encoded salt for encryption
    description: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StoredKey":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class KeystoreData:
    """Keystore file data structure."""

    version: int = KEYSTORE_VERSION
    keys: dict[str, StoredKey] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "keys": {k: v.to_dict() for k, v in self.keys.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KeystoreData":
        """Create from dictionary."""
        keys = {k: StoredKey.from_dict(v) for k, v in data.get("keys", {}).items()}
        return cls(version=data.get("version", KEYSTORE_VERSION), keys=keys)


class SigningKeystore:
    """
    Secure keystore for MAVLink 2.0 signing keys.

    This class provides secure storage for signing keys using:
    1. OS keyring (preferred) - Windows Credential Manager, macOS Keychain, Linux Secret Service
    2. Encrypted file fallback - AES-256 encrypted JSON file

    Security features:
    - Cryptographically secure key generation using secrets module
    - Per-vehicle key isolation
    - Password-protected export/import
    - Encrypted storage with key derivation

    Attributes:
        keyring_available: Whether OS keyring is available
        fallback_path: Path to encrypted fallback file

    """

    def __init__(self, use_keyring: bool = True) -> None:
        """
        Initialize the signing keystore.

        Args:
            use_keyring: Whether to attempt using OS keyring (default: True)

        """
        self._logger = logging.getLogger(__name__)
        self._use_keyring = use_keyring
        self._keyring_available = False
        self._keyring_service = "ardupilot_methodic_configurator_signing"

        # Check keyring availability
        if use_keyring:
            self._keyring_available = self._check_keyring_available()

        # Set up fallback path
        data_dir = Path(user_data_dir(APP_NAME))
        data_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_path = data_dir / KEYSTORE_FILENAME

        self._logger.debug(
            "Keystore initialized: keyring_available=%s, fallback_path=%s",
            self._keyring_available,
            self._fallback_path,
        )

    @property
    def keyring_available(self) -> bool:
        """Check if OS keyring is available."""
        return self._keyring_available

    @property
    def fallback_path(self) -> Path:
        """Get the fallback keystore file path."""
        return self._fallback_path

    def _check_keyring_available(self) -> bool:
        """Check if OS keyring is available and functional."""
        try:
            import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

            # Try to get the default keyring
            backend = keyring.get_keyring()
            if backend is None:
                return False

            # Test with a dummy operation
            test_key = f"_test_keyring_{secrets.token_hex(4)}"
            keyring.set_password(self._keyring_service, test_key, "test")
            keyring.delete_password(self._keyring_service, test_key)
            return True
        except ImportError:
            self._logger.debug("Keyring package not installed")
            return False
        except Exception as exc:  # pylint: disable=broad-except
            # Catches NoKeyringError and other keyring-specific errors
            exc_name = type(exc).__name__
            if exc_name == "NoKeyringError":
                self._logger.debug("No keyring backend available")
            else:
                self._logger.debug("Keyring test failed: %s", exc)
            return False

    def generate_key(self) -> bytes:
        """
        Generate a cryptographically secure signing key.

        Returns:
            bytes: A 32-byte (256-bit) random key suitable for HMAC-SHA256 signing.

        """
        return secrets.token_bytes(SIGNING_KEY_LENGTH)

    def store_key(self, vehicle_id: str, key: bytes, description: str = "") -> bool:
        """
        Store a signing key for a specific vehicle.

        Args:
            vehicle_id: Unique identifier for the vehicle (e.g., serial number)
            key: The 32-byte signing key to store
            description: Optional description for the key

        Returns:
            bool: True if key was stored successfully, False otherwise

        """
        if len(key) != SIGNING_KEY_LENGTH:
            msg = f"Key must be {SIGNING_KEY_LENGTH} bytes"
            raise ValueError(msg)

        if not vehicle_id:
            msg = "Vehicle ID cannot be empty"
            raise ValueError(msg)

        # Try keyring first
        if self._keyring_available:
            try:
                import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

                # Store key as base64 encoded string
                key_b64 = base64.b64encode(key).decode("ascii")
                keyring.set_password(self._keyring_service, vehicle_id, key_b64)
                self._logger.info("Stored signing key for vehicle %s in keyring", vehicle_id)
                return True
            except Exception as exc:  # pylint: disable=broad-except
                self._logger.warning("Failed to store key in keyring: %s", exc)

        # Fall back to encrypted file storage
        return self._store_key_in_file(vehicle_id, key, description)

    def _store_key_in_file(self, vehicle_id: str, key: bytes, description: str = "") -> bool:
        """Store key in encrypted file."""
        try:
            from cryptography.fernet import Fernet  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives import hashes  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives.kdf.pbkdf2 import (  # noqa: PLC0415
                PBKDF2HMAC,  # pylint: disable=import-outside-toplevel
            )

            # Load existing keystore or create new
            keystore = self._load_keystore_file()

            # Generate salt for this key
            salt = secrets.token_bytes(16)

            # Derive encryption key from vehicle_id (as a simple protection)
            # Note: This provides obfuscation, not strong encryption without a password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            derived_key = kdf.derive(vehicle_id.encode())
            fernet_key = base64.urlsafe_b64encode(derived_key)
            fernet = Fernet(fernet_key)

            # Encrypt the signing key
            encrypted_key = fernet.encrypt(key)

            # Create stored key entry
            key_id = hashlib.sha256(f"{vehicle_id}:{datetime.now(tz=timezone.utc).isoformat()}".encode()).hexdigest()[:16]
            stored_key = StoredKey(
                key_id=key_id,
                vehicle_id=vehicle_id,
                created_at=datetime.now(tz=timezone.utc).isoformat(),
                encrypted_key=base64.b64encode(encrypted_key).decode("ascii"),
                salt=base64.b64encode(salt).decode("ascii"),
                description=description,
            )

            keystore.keys[vehicle_id] = stored_key
            self._save_keystore_file(keystore)

            self._logger.info("Stored signing key for vehicle %s in file", vehicle_id)
            return True

        except Exception as exc:  # pylint: disable=broad-except
            self._logger.exception("Failed to store key in file: %s", exc)
            return False

    def retrieve_key(self, vehicle_id: str) -> Optional[bytes]:
        """
        Retrieve a stored signing key for a vehicle.

        Args:
            vehicle_id: Unique identifier for the vehicle

        Returns:
            bytes: The signing key if found, None otherwise

        """
        if not vehicle_id:
            return None

        # Try keyring first
        if self._keyring_available:
            try:
                import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

                key_b64 = keyring.get_password(self._keyring_service, vehicle_id)
                if key_b64:
                    return base64.b64decode(key_b64)
            except Exception as exc:  # pylint: disable=broad-except
                self._logger.warning("Failed to retrieve key from keyring: %s", exc)

        # Fall back to file storage
        return self._retrieve_key_from_file(vehicle_id)

    def _retrieve_key_from_file(self, vehicle_id: str) -> Optional[bytes]:
        """Retrieve key from encrypted file."""
        try:
            from cryptography.fernet import Fernet  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives import hashes  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives.kdf.pbkdf2 import (  # noqa: PLC0415
                PBKDF2HMAC,  # pylint: disable=import-outside-toplevel
            )

            keystore = self._load_keystore_file()

            if vehicle_id not in keystore.keys:
                return None

            stored_key = keystore.keys[vehicle_id]

            # Decode salt and encrypted key
            salt = base64.b64decode(stored_key.salt)
            encrypted_key = base64.b64decode(stored_key.encrypted_key)

            # Derive decryption key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            derived_key = kdf.derive(vehicle_id.encode())
            fernet_key = base64.urlsafe_b64encode(derived_key)
            fernet = Fernet(fernet_key)

            # Decrypt the signing key
            return fernet.decrypt(encrypted_key)

        except Exception as exc:  # pylint: disable=broad-except
            self._logger.exception("Failed to retrieve key from file: %s", exc)
            return None

    def delete_key(self, vehicle_id: str) -> bool:
        """
        Delete a stored signing key for a vehicle.

        Args:
            vehicle_id: Unique identifier for the vehicle

        Returns:
            bool: True if key was deleted, False if key was not found

        """
        deleted = False

        # Try keyring first
        if self._keyring_available:
            try:
                import keyring  # noqa: PLC0415 # pylint: disable=import-outside-toplevel

                keyring.delete_password(self._keyring_service, vehicle_id)
                deleted = True
                self._logger.info("Deleted signing key for vehicle %s from keyring", vehicle_id)
            except Exception as exc:  # pylint: disable=broad-except
                self._logger.debug("Key not found in keyring or deletion failed: %s", exc)

        # Also delete from file if present
        try:
            keystore = self._load_keystore_file()
            if vehicle_id in keystore.keys:
                del keystore.keys[vehicle_id]
                self._save_keystore_file(keystore)
                deleted = True
                self._logger.info("Deleted signing key for vehicle %s from file", vehicle_id)
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.debug("Failed to delete key from file: %s", exc)

        return deleted

    def list_vehicles(self) -> list[str]:
        """
        List all vehicles with stored signing keys.

        Returns:
            list[str]: List of vehicle IDs with stored keys

        """
        vehicles: set[str] = set()

        # Check keyring - this is difficult without enumerating, so we rely on file
        # Keyring doesn't support listing all entries

        # Check file storage
        try:
            keystore = self._load_keystore_file()
            vehicles.update(keystore.keys.keys())
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.debug("Failed to list vehicles from file: %s", exc)

        return sorted(vehicles)

    def export_key(self, vehicle_id: str, password: str) -> Optional[str]:
        """
        Export a signing key with password protection.

        Args:
            vehicle_id: Vehicle ID for the key to export
            password: Password to encrypt the export

        Returns:
            str: Base64 encoded encrypted export data, or None if key not found

        """
        key = self.retrieve_key(vehicle_id)
        if key is None:
            return None

        try:
            from cryptography.fernet import Fernet  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives import hashes  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives.kdf.pbkdf2 import (  # noqa: PLC0415
                PBKDF2HMAC,  # pylint: disable=import-outside-toplevel
            )

            # Generate salt
            salt = secrets.token_bytes(16)

            # Derive encryption key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=600000,  # Higher iterations for password-based
            )
            derived_key = kdf.derive(password.encode())
            fernet_key = base64.urlsafe_b64encode(derived_key)
            fernet = Fernet(fernet_key)

            # Encrypt the key
            encrypted_key = fernet.encrypt(key)

            # Create export package
            export_data = {
                "version": 1,
                "vehicle_id": vehicle_id,
                "salt": base64.b64encode(salt).decode("ascii"),
                "encrypted_key": base64.b64encode(encrypted_key).decode("ascii"),
            }

            # Encode as base64 JSON
            return base64.b64encode(json.dumps(export_data).encode()).decode("ascii")

        except Exception as exc:  # pylint: disable=broad-except
            self._logger.exception("Failed to export key: %s", exc)
            return None

    def import_key(self, export_data: str, password: str) -> Optional[str]:
        """
        Import a signing key from an encrypted export.

        Args:
            export_data: Base64 encoded encrypted export data
            password: Password to decrypt the export

        Returns:
            str: Vehicle ID of the imported key, or None if import failed

        """
        try:
            from cryptography.fernet import Fernet, InvalidToken  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives import hashes  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
            from cryptography.hazmat.primitives.kdf.pbkdf2 import (  # noqa: PLC0415
                PBKDF2HMAC,  # pylint: disable=import-outside-toplevel
            )

            # Decode export package
            data = json.loads(base64.b64decode(export_data).decode())

            vehicle_id: str = data["vehicle_id"]
            salt = base64.b64decode(data["salt"])
            encrypted_key = base64.b64decode(data["encrypted_key"])

            # Derive decryption key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=600000,
            )
            derived_key = kdf.derive(password.encode())
            fernet_key = base64.urlsafe_b64encode(derived_key)
            fernet = Fernet(fernet_key)

            # Decrypt the key
            try:
                key = fernet.decrypt(encrypted_key)
            except InvalidToken:
                self._logger.warning("Invalid password for key import")
                return None

            # Store the key
            if self.store_key(vehicle_id, key, description="Imported key"):
                return vehicle_id
            return None

        except Exception as exc:  # pylint: disable=broad-except
            self._logger.exception("Failed to import key: %s", exc)
            return None

    def _load_keystore_file(self) -> KeystoreData:
        """Load keystore from file."""
        if not self._fallback_path.exists():
            return KeystoreData()

        try:
            with open(self._fallback_path, encoding="utf-8") as f:
                data = json.load(f)
            return KeystoreData.from_dict(data)
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.warning("Failed to load keystore file: %s", exc)
            return KeystoreData()

    def _save_keystore_file(self, keystore: KeystoreData) -> None:
        """Save keystore to file."""
        # Ensure directory exists
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically using a temporary file
        temp_path = self._fallback_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(keystore.to_dict(), f, indent=2)

            # Atomic rename
            os.replace(temp_path, self._fallback_path)

            # Set restrictive permissions on Unix
            if os.name != "nt":
                os.chmod(self._fallback_path, 0o600)

        except Exception:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise
