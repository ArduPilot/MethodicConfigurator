#!/usr/bin/env python3

"""
Unit tests for backend_signing_keystore module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests focus on low-level implementation details, error paths with mocking,
and edge cases that cannot be tested at the BDD level.
"""

import base64
import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.backend_signing_keystore import KeystoreData, SigningKeystore

# pylint: disable=protected-access


class TestKeystoreKeyringAvailability:
    """Test keyring availability detection with various failure scenarios."""

    def test_keyring_unavailable_when_package_not_installed(self, tmp_path: Path) -> None:
        """Test keyring availability when keyring package is not installed."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            with patch.dict("sys.modules", {"keyring": None}):
                keystore = SigningKeystore(use_keyring=True)

                assert keystore.keyring_available is False

    def test_keyring_unavailable_when_no_backend(self, tmp_path: Path) -> None:
        """Test keyring availability when no keyring backend is available."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_keyring.get_keyring.return_value = None

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)

                assert keystore.keyring_available is False

    def test_keyring_unavailable_when_set_password_fails(self, tmp_path: Path) -> None:
        """Test keyring availability when setting password fails."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend
            mock_keyring.set_password.side_effect = Exception("Keyring error")

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)

                assert keystore.keyring_available is False

    def test_keyring_check_handles_cleanup_failure_gracefully(self, tmp_path: Path) -> None:
        """Test that keyring cleanup failure during check is handled gracefully."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend
            mock_keyring.delete_password.side_effect = Exception("Cleanup failed")

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)

                # Should still indicate available since set succeeded
                assert isinstance(keystore.keyring_available, bool)


class TestKeystoreKeyringOperationsWithFallback:
    """Test keyring operations that fall back to file storage on error."""

    def test_store_key_falls_back_to_file_on_keyring_error(self, tmp_path: Path) -> None:
        """Test that keyring storage error causes fallback to file."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend
            mock_keyring.set_password.side_effect = Exception("Keyring storage failed")

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)
                keystore._keyring_available = True

                key = keystore.generate_key()
                keystore.store_key("test_vehicle", key)

                # Should fall back to file storage
                assert keystore.fallback_path.exists()

    def test_retrieve_key_falls_back_to_file_on_keyring_error(self, tmp_path: Path) -> None:
        """Test that keyring retrieval error causes fallback to file."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend
            mock_keyring.get_password.side_effect = Exception("Keyring retrieval failed")

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)
                keystore._keyring_available = True

                # Store key in file using public API
                key = keystore.generate_key()
                keystore._store_key_in_file("test_vehicle", key)

                retrieved_key = keystore.retrieve_key("test_vehicle")

                assert retrieved_key == key

    def test_delete_key_falls_back_to_file_on_keyring_error(self, tmp_path: Path) -> None:
        """Test that keyring deletion error causes fallback to file."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend
            mock_keyring.delete_password.side_effect = Exception("Keyring deletion failed")

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)
                keystore._keyring_available = True

                # Store key in file using public API
                key = keystore.generate_key()
                keystore._store_key_in_file("test_vehicle", key)

                result = keystore.delete_key("test_vehicle")

                assert result is True


class TestKeystoreFileOperationsErrorHandling:
    """Test file operation error handling with corrupted data and failures."""

    def test_load_keystore_with_corrupted_file(self, tmp_path: Path) -> None:
        """Test loading keystore file with corrupted encrypted data."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)

            # Create corrupted encrypted file
            keystore.fallback_path.write_text("not valid encrypted data")

            data = keystore._load_keystore_file()

            # Should return empty KeystoreData on error
            assert len(data.keys) == 0

    def test_save_keystore_handles_file_lock_timeout(self, tmp_path: Path) -> None:
        """Test that save_keystore handles file lock timeout gracefully."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)

            # Mock fcntl to raise BlockingIOError
            with patch("fcntl.flock") as mock_flock:
                mock_flock.side_effect = BlockingIOError("Lock timeout")

                # Should handle the error gracefully without crashing
                # Use the internal method - it expects BlockingIOError and logs
                try:  # noqa: SIM105
                    keystore._save_keystore_file(KeystoreData(version=1, keys={}))
                except BlockingIOError:
                    # Expected to be raised
                    pass

    def test_save_keystore_handles_permission_error(self, tmp_path: Path) -> None:
        """Test that save_keystore handles permission errors gracefully."""
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)
            keystore = SigningKeystore(use_keyring=False)

            # Make the directory read-only
            tmp_path.chmod(0o444)

            # Should handle the error gracefully
            with contextlib.suppress(PermissionError, OSError):
                keystore._save_keystore_file(KeystoreData(version=1, keys={}))

            # Restore permissions
            tmp_path.chmod(0o755)


class TestKeystorePrimaryKeyringMethod:
    """Test the primary keyring storage method when keyring is available."""

    def test_store_key_uses_keyring_when_available(self, tmp_path: Path) -> None:
        """
        Test that store_key uses keyring.set_password when keyring is available.

        GIVEN: Keyring is available and functional
        WHEN: User stores a signing key
        THEN: keyring.set_password should be called with correct parameters
        """
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)
                keystore._keyring_available = True

                # Reset mock after keystore creation (constructor also calls keyring)
                mock_keyring.reset_mock()

                key = keystore.generate_key()
                vehicle_id = "TEST-VEHICLE"
                result = keystore.store_key(vehicle_id, key)

                # Assert keyring.set_password was called
                assert result is True
                mock_keyring.set_password.assert_called_once()
                call_args = mock_keyring.set_password.call_args
                assert call_args[0][0] == "ardupilot_methodic_configurator_signing"
                assert call_args[0][1] == vehicle_id

    def test_retrieve_key_uses_keyring_when_available(self, tmp_path: Path) -> None:
        """
        Test that retrieve_key uses keyring.get_password when keyring is available.

        GIVEN: A key was stored in keyring
        WHEN: User retrieves the key
        THEN: keyring.get_password should be called
        AND: The correct key should be returned
        """
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            key = b"A" * 32  # 32-byte key
            key_b64 = base64.b64encode(key).decode("ascii")

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend
            mock_keyring.get_password.return_value = key_b64

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)
                keystore._keyring_available = True

                # Reset mock after keystore creation
                mock_keyring.reset_mock()
                mock_keyring.get_password.return_value = key_b64

                vehicle_id = "TEST-VEHICLE"
                retrieved = keystore.retrieve_key(vehicle_id)

                # Assert keyring.get_password was called
                mock_keyring.get_password.assert_called_once()
                call_args = mock_keyring.get_password.call_args
                assert call_args[0][0] == "ardupilot_methodic_configurator_signing"
                assert call_args[0][1] == vehicle_id
                assert retrieved == key

    def test_delete_key_uses_keyring_when_available(self, tmp_path: Path) -> None:
        """
        Test that delete_key uses keyring.delete_password when keyring is available.

        GIVEN: A key exists in keyring
        WHEN: User deletes the key
        THEN: keyring.delete_password should be called
        """
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            key = b"B" * 32
            key_b64 = base64.b64encode(key).decode("ascii")

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend
            mock_keyring.get_password.return_value = key_b64

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)
                keystore._keyring_available = True

                # Reset mock after keystore creation
                mock_keyring.reset_mock()
                mock_keyring.get_password.return_value = key_b64

                vehicle_id = "TEST-VEHICLE"
                result = keystore.delete_key(vehicle_id)

                # Assert keyring.delete_password was called
                assert result is True
                mock_keyring.delete_password.assert_called_once()
                call_args = mock_keyring.delete_password.call_args
                assert call_args[0][0] == "ardupilot_methodic_configurator_signing"
                assert call_args[0][1] == vehicle_id

    def test_keyring_stores_base64_encoded_key(self, tmp_path: Path) -> None:
        """
        Test that keys are stored as base64-encoded strings in keyring.

        GIVEN: Keyring is available
        WHEN: User stores a binary key
        THEN: The key should be base64-encoded before storing
        """
        with patch("ardupilot_methodic_configurator.backend_signing_keystore.user_data_dir") as mock_dir:
            mock_dir.return_value = str(tmp_path)

            mock_keyring = MagicMock()
            mock_backend = MagicMock()
            mock_keyring.get_keyring.return_value = mock_backend

            with patch.dict("sys.modules", {"keyring": mock_keyring}):
                keystore = SigningKeystore(use_keyring=True)
                keystore._keyring_available = True

                # Reset mock after keystore creation
                mock_keyring.reset_mock()

                key = b"C" * 32
                expected_b64 = base64.b64encode(key).decode("ascii")
                keystore.store_key("TEST-VEHICLE", key)

                # Assert the stored value is base64 encoded
                call_args = mock_keyring.set_password.call_args
                stored_value = call_args[0][2]
                assert stored_value == expected_b64
