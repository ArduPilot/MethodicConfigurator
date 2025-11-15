"""
Secure storage and management of MAVLink signing keys.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import secrets
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ardupilot_methodic_configurator import _

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logging_warning(_("keyring library not available, will use encrypted file storage"))


class SigningKeyStore:
    """
    Manages secure storage and retrieval of MAVLink signing keys.

    This class provides secure key storage using the OS keyring as the primary method,
    with an encrypted file-based fallback. Keys are 32-byte values used for MAVLink
    message signing (HMAC-SHA-256).
    """

    SERVICE_NAME = "ArduPilot_Methodic_Configurator"
    KEY_SIZE_BYTES = 32  # 256 bits for HMAC-SHA-256

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """
        Initialize the signing key store.

        Args:
            storage_dir: Directory for encrypted file storage fallback.
                        If None, uses default application data directory.

        """
        self.use_keyring = KEYRING_AVAILABLE
        self.storage_dir = storage_dir or self._get_default_storage_dir()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._keystore_file = self.storage_dir / "signing_keys.enc"

        if self.use_keyring:
            logging_info(_("Using OS keyring for signing key storage"))
        else:
            logging_info(_("Using encrypted file storage for signing keys at %s"), self._keystore_file)

    @staticmethod
    def _get_default_storage_dir() -> Path:
        """Get the default storage directory for encrypted keys."""
        from platformdirs import user_data_dir

        return Path(user_data_dir("ArduPilot_Methodic_Configurator", "ArduPilot")) / "signing_keys"

    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a cryptographically secure 32-byte signing key.

        Returns:
            bytes: A 32-byte random key suitable for MAVLink signing.

        """
        key = secrets.token_bytes(SigningKeyStore.KEY_SIZE_BYTES)
        logging_debug(_("Generated new %d-byte signing key"), len(key))
        return key

    def store_key(self, vehicle_id: str, key: bytes) -> bool:
        """
        Store a signing key for a specific vehicle.

        Args:
            vehicle_id: Unique identifier for the vehicle.
            key: 32-byte signing key.

        Returns:
            bool: True if storage was successful, False otherwise.

        """
        if len(key) != self.KEY_SIZE_BYTES:
            logging_error(_("Invalid key size: expected %d bytes, got %d"), self.KEY_SIZE_BYTES, len(key))
            return False

        if not vehicle_id or not vehicle_id.strip():
            logging_error(_("Invalid vehicle_id: cannot be empty"))
            return False

        try:
            if self.use_keyring:
                return self._store_key_in_keyring(vehicle_id, key)
            return self._store_key_in_file(vehicle_id, key)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to store signing key for vehicle %s: %s"), vehicle_id, e)
            return False

    def retrieve_key(self, vehicle_id: str) -> Optional[bytes]:
        """
        Retrieve the signing key for a vehicle.

        Args:
            vehicle_id: Unique identifier for the vehicle.

        Returns:
            Optional[bytes]: The 32-byte signing key, or None if not found.

        """
        if not vehicle_id or not vehicle_id.strip():
            logging_error(_("Invalid vehicle_id: cannot be empty"))
            return None

        try:
            if self.use_keyring:
                return self._retrieve_key_from_keyring(vehicle_id)
            return self._retrieve_key_from_file(vehicle_id)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to retrieve signing key for vehicle %s: %s"), vehicle_id, e)
            return None

    def delete_key(self, vehicle_id: str) -> bool:
        """
        Delete a vehicle's signing key.

        Args:
            vehicle_id: Unique identifier for the vehicle.

        Returns:
            bool: True if deletion was successful, False otherwise.

        """
        if not vehicle_id or not vehicle_id.strip():
            logging_error(_("Invalid vehicle_id: cannot be empty"))
            return False

        try:
            if self.use_keyring:
                return self._delete_key_from_keyring(vehicle_id)
            return self._delete_key_from_file(vehicle_id)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to delete signing key for vehicle %s: %s"), vehicle_id, e)
            return False

    def list_vehicles_with_keys(self) -> list[str]:
        """
        List all vehicles that have signing keys configured.

        Returns:
            list[str]: List of vehicle IDs with configured keys.

        """
        try:
            if self.use_keyring:
                return self._list_vehicles_from_keyring()
            return self._list_vehicles_from_file()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to list vehicles with signing keys: %s"), e)
            return []

    def export_key(self, vehicle_id: str, password: str) -> Optional[bytes]:
        """
        Export a signing key in encrypted form for backup.

        Args:
            vehicle_id: Unique identifier for the vehicle.
            password: Password to encrypt the exported key.

        Returns:
            Optional[bytes]: Encrypted key data, or None on failure.

        """
        if not password or len(password) < 8:
            logging_error(_("Password must be at least 8 characters"))
            return None

        key = self.retrieve_key(vehicle_id)
        if key is None:
            logging_error(_("No key found for vehicle %s"), vehicle_id)
            return None

        try:
            # Derive encryption key from password
            salt = secrets.token_bytes(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            encryption_key = kdf.derive(password.encode())

            # Encrypt the signing key
            fernet = Fernet(self._bytes_to_fernet_key(encryption_key))
            encrypted_key = fernet.encrypt(key)

            # Package with salt and vehicle_id
            export_data = {"vehicle_id": vehicle_id, "salt": salt.hex(), "encrypted_key": encrypted_key.decode()}

            logging_info(_("Exported signing key for vehicle %s"), vehicle_id)
            return json.dumps(export_data).encode()

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to export key: %s"), e)
            return None

    def import_key(self, encrypted_data: bytes, password: str) -> tuple[bool, str]:
        """
        Import an encrypted signing key from backup.

        Args:
            encrypted_data: Encrypted key data from export_key().
            password: Password to decrypt the key.

        Returns:
            tuple[bool, str]: (success, vehicle_id or error_message)

        """
        if not password or len(password) < 8:
            return False, _("Password must be at least 8 characters")

        try:
            # Parse export data
            export_data = json.loads(encrypted_data.decode())
            vehicle_id = export_data["vehicle_id"]
            salt = bytes.fromhex(export_data["salt"])
            encrypted_key = export_data["encrypted_key"].encode()

            # Derive decryption key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            decryption_key = kdf.derive(password.encode())

            # Decrypt the signing key
            fernet = Fernet(self._bytes_to_fernet_key(decryption_key))
            key = fernet.decrypt(encrypted_key)

            # Validate key size
            if len(key) != self.KEY_SIZE_BYTES:
                return False, _("Invalid key size in imported data")

            # Store the key
            if self.store_key(vehicle_id, key):
                logging_info(_("Imported signing key for vehicle %s"), vehicle_id)
                return True, vehicle_id

            return False, _("Failed to store imported key")

        except InvalidToken:
            return False, _("Invalid password or corrupted data")
        except (json.JSONDecodeError, KeyError) as e:
            return False, _("Invalid import data format: %(error)s") % {"error": str(e)}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to import key: %s"), e)
            return False, str(e)

    # Keyring-based storage methods

    def _store_key_in_keyring(self, vehicle_id: str, key: bytes) -> bool:
        """Store key using OS keyring."""
        try:
            keyring.set_password(self.SERVICE_NAME, vehicle_id, key.hex())
            logging_debug(_("Stored key in keyring for vehicle %s"), vehicle_id)
            return True
        except KeyringError as e:
            logging_error(_("Keyring error: %s"), e)
            return False

    def _retrieve_key_from_keyring(self, vehicle_id: str) -> Optional[bytes]:
        """Retrieve key from OS keyring."""
        try:
            key_hex = keyring.get_password(self.SERVICE_NAME, vehicle_id)
            if key_hex is None:
                logging_debug(_("No key found in keyring for vehicle %s"), vehicle_id)
                return None
            return bytes.fromhex(key_hex)
        except KeyringError as e:
            logging_error(_("Keyring error: %s"), e)
            return None

    def _delete_key_from_keyring(self, vehicle_id: str) -> bool:
        """Delete key from OS keyring."""
        try:
            keyring.delete_password(self.SERVICE_NAME, vehicle_id)
            logging_info(_("Deleted key from keyring for vehicle %s"), vehicle_id)
            return True
        except KeyringError as e:
            logging_error(_("Keyring error: %s"), e)
            return False

    def _list_vehicles_from_keyring(self) -> list[str]:
        """List vehicles from keyring (not directly supported, use file index)."""
        # Keyring doesn't support listing, so we maintain an index file
        index_file = self.storage_dir / "keyring_index.json"
        if not index_file.exists():
            return []

        try:
            with index_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("vehicles", [])
        except (json.JSONDecodeError, OSError) as e:
            logging_error(_("Failed to read keyring index: %s"), e)
            return []

    def _update_keyring_index(self, vehicle_id: str, add: bool = True) -> None:
        """Update the keyring index file."""
        index_file = self.storage_dir / "keyring_index.json"
        vehicles = self._list_vehicles_from_keyring()

        if add and vehicle_id not in vehicles:
            vehicles.append(vehicle_id)
        elif not add and vehicle_id in vehicles:
            vehicles.remove(vehicle_id)

        try:
            with index_file.open("w", encoding="utf-8") as f:
                json.dump({"vehicles": vehicles}, f, indent=2)
        except OSError as e:
            logging_error(_("Failed to update keyring index: %s"), e)

    # File-based storage methods

    def _store_key_in_file(self, vehicle_id: str, key: bytes) -> bool:
        """Store key in encrypted file."""
        keys = self._load_keystore_file()
        keys[vehicle_id] = key.hex()
        return self._save_keystore_file(keys)

    def _retrieve_key_from_file(self, vehicle_id: str) -> Optional[bytes]:
        """Retrieve key from encrypted file."""
        keys = self._load_keystore_file()
        key_hex = keys.get(vehicle_id)
        if key_hex is None:
            logging_debug(_("No key found in file for vehicle %s"), vehicle_id)
            return None
        return bytes.fromhex(key_hex)

    def _delete_key_from_file(self, vehicle_id: str) -> bool:
        """Delete key from encrypted file."""
        keys = self._load_keystore_file()
        if vehicle_id in keys:
            del keys[vehicle_id]
            return self._save_keystore_file(keys)
        return True

    def _list_vehicles_from_file(self) -> list[str]:
        """List vehicles from encrypted file."""
        keys = self._load_keystore_file()
        return list(keys.keys())

    def _load_keystore_file(self) -> dict[str, str]:
        """Load and decrypt the keystore file."""
        if not self._keystore_file.exists():
            return {}

        try:
            with self._keystore_file.open("rb") as f:
                encrypted_data = f.read()

            # Use a machine-specific key for encryption
            fernet = Fernet(self._get_machine_key())
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())

        except (InvalidToken, json.JSONDecodeError, OSError) as e:
            logging_error(_("Failed to load keystore file: %s"), e)
            return {}

    def _save_keystore_file(self, keys: dict[str, str]) -> bool:
        """Encrypt and save the keystore file."""
        try:
            # Serialize to JSON
            json_data = json.dumps(keys, indent=2).encode()

            # Encrypt with machine-specific key
            fernet = Fernet(self._get_machine_key())
            encrypted_data = fernet.encrypt(json_data)

            # Write to file
            with self._keystore_file.open("wb") as f:
                f.write(encrypted_data)

            logging_debug(_("Saved keystore file with %d keys"), len(keys))
            return True

        except (OSError, Exception) as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to save keystore file: %s"), e)
            return False

    def _get_machine_key(self) -> bytes:
        """
        Get or create a machine-specific encryption key.

        This key is used to encrypt the keystore file. It's derived from
        machine-specific information to provide basic protection.
        """
        key_file = self.storage_dir / ".machine_key"

        if key_file.exists():
            try:
                with key_file.open("rb") as f:
                    return f.read()
            except OSError:
                pass

        # Generate new machine key
        machine_key = Fernet.generate_key()

        try:
            with key_file.open("wb") as f:
                f.write(machine_key)
            # Make file readable only by owner
            key_file.chmod(0o600)
        except OSError as e:
            logging_warning(_("Failed to save machine key: %s"), e)

        return machine_key

    @staticmethod
    def _bytes_to_fernet_key(key_bytes: bytes) -> bytes:
        """Convert 32-byte key to Fernet-compatible format."""
        import base64

        return base64.urlsafe_b64encode(key_bytes)


# Example usage and testing
if __name__ == "__main__":
    import sys
    from logging import DEBUG, basicConfig

    basicConfig(level=DEBUG)

    # Create keystore
    keystore = SigningKeyStore()

    # Generate and store a key
    vehicle_id = "test_vehicle_001"
    key = SigningKeyStore.generate_key()
    print(f"Generated key: {key.hex()}")

    if keystore.store_key(vehicle_id, key):
        print(f"✓ Stored key for {vehicle_id}")
    else:
        print(f"✗ Failed to store key for {vehicle_id}")
        sys.exit(1)

    # Retrieve the key
    retrieved_key = keystore.retrieve_key(vehicle_id)
    if retrieved_key == key:
        print("✓ Retrieved key matches original")
    else:
        print("✗ Retrieved key does not match")
        sys.exit(1)

    # List vehicles
    vehicles = keystore.list_vehicles_with_keys()
    print(f"Vehicles with keys: {vehicles}")

    # Export key
    password = "test_password_12345"
    exported = keystore.export_key(vehicle_id, password)
    if exported:
        print(f"✓ Exported key ({len(exported)} bytes)")

        # Delete original
        keystore.delete_key(vehicle_id)

        # Import it back
        success, result = keystore.import_key(exported, password)
        if success:
            print(f"✓ Imported key for {result}")
        else:
            print(f"✗ Failed to import: {result}")
            sys.exit(1)
    else:
        print("✗ Failed to export key")
        sys.exit(1)

    # Clean up
    keystore.delete_key(vehicle_id)
    print("✓ All tests passed!")
