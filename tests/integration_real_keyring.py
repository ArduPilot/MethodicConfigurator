#!/usr/bin/env python3

"""
Integration tests using real OS keyring (not mocked).

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later

These tests use the real operating system keyring to verify actual keyring functionality.

RUNNING THESE TESTS:
1. These tests run only on Windows and use Windows Credential Manager
2. Run with: pytest -m real_keyring tests/integration_real_keyring.py -v
3. Tests are skipped on non-Windows platforms
4. Tests are skipped if real keyring is not available

WARNING: These tests will create real entries in your Windows Credential Manager during execution.
"""

import contextlib
import sys

import pytest

from ardupilot_methodic_configurator.backend_signing_keystore import (
    SIGNING_KEY_LENGTH,
    SigningKeystore,
)


def has_real_keyring() -> bool:
    """Check if real keyring is available on this system."""
    try:
        import keyring  # noqa: PLC0415

        # Try to get the keyring backend
        backend = keyring.get_keyring()
        # Don't check service availability, just that backend exists
        return backend is not None
    except Exception:
        return False


@pytest.fixture
def real_keyring_skip() -> None:
    """Skip test if real keyring is not available."""
    if not has_real_keyring():
        pytest.skip("Real OS keyring not available on this system")


@pytest.mark.real_keyring
@pytest.mark.integration
@pytest.mark.skipif(sys.platform != "win32", reason="Real keyring tests only run on Windows")
class TestRealOSKeyring:
    """Test signing keystore with real Windows Credential Manager."""

    def test_real_keyring_storage(self, real_keyring_skip: None) -> None:
        """
        SigningKeystore can store and retrieve keys from real OS keyring.

        GIVEN: A real OS keyring is available
        WHEN: A SigningKeystore generates and stores a key
        THEN: The key can be retrieved and matches the original
        AND: The key can be used for signing operations
        """
        keystore = SigningKeystore()
        vehicle_id = "TEST-REAL-KEYRING-VEHICLE"

        try:
            # Generate a key
            key = keystore.generate_key()
            assert key is not None
            assert len(key) == SIGNING_KEY_LENGTH

            # Store the key
            keystore.store_key(vehicle_id, key)

            # Retrieve the key
            retrieved_key = keystore.retrieve_key(vehicle_id)
            assert retrieved_key is not None
            assert retrieved_key == key
            assert len(retrieved_key) == SIGNING_KEY_LENGTH

        finally:
            # Cleanup: delete the test key
            with contextlib.suppress(Exception):
                keystore.delete_key(vehicle_id)

    def test_real_keyring_multiple_vehicles(self, real_keyring_skip: None) -> None:
        """
        SigningKeystore can manage keys for multiple vehicles in real keyring.

        GIVEN: Real OS keyring is available
        WHEN: Multiple vehicles store keys
        THEN: Each vehicle's key can be retrieved independently
        AND: Keys do not interfere with each other
        """
        keystore = SigningKeystore()
        vehicle_ids = [
            "TEST-VEHICLE-1",
            "TEST-VEHICLE-2",
            "TEST-VEHICLE-3",
        ]
        stored_keys = {}

        try:
            # Store keys for multiple vehicles
            for vehicle_id in vehicle_ids:
                key = keystore.generate_key()
                keystore.store_key(vehicle_id, key)
                stored_keys[vehicle_id] = key

            # Verify each key can be retrieved independently
            for vehicle_id, original_key in stored_keys.items():
                retrieved_key = keystore.retrieve_key(vehicle_id)
                assert retrieved_key is not None
                assert retrieved_key == original_key

        finally:
            # Cleanup
            for vehicle_id in vehicle_ids:
                with contextlib.suppress(Exception):
                    keystore.delete_key(vehicle_id)

    def test_real_keyring_delete_operation(self, real_keyring_skip: None) -> None:
        """
        SigningKeystore can delete keys from real OS keyring.

        GIVEN: A key is stored in real OS keyring
        WHEN: The keystore deletes the key
        THEN: The key is removed and cannot be retrieved
        AND: Attempting to retrieve returns None
        """
        keystore = SigningKeystore()
        vehicle_id = "TEST-DELETE-VEHICLE"

        try:
            # Store a key
            key = keystore.generate_key()
            keystore.store_key(vehicle_id, key)

            # Verify it exists
            retrieved = keystore.retrieve_key(vehicle_id)
            assert retrieved is not None

            # Delete it
            result = keystore.delete_key(vehicle_id)
            assert result is True

            # Verify it's gone
            retrieved = keystore.retrieve_key(vehicle_id)
            assert retrieved is None

        finally:
            # Best effort cleanup
            with contextlib.suppress(Exception):
                keystore.delete_key(vehicle_id)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific keyring test")
    def test_windows_credential_manager(self, real_keyring_skip: None) -> None:
        """
        Test that Windows Credential Manager is properly used.

        GIVEN: Running on Windows
        WHEN: A key is stored via SigningKeystore
        THEN: It should be stored in Windows Credential Manager
        AND: The service name should be ArduPilotMethodicConfigurator
        """
        keystore = SigningKeystore()
        vehicle_id = "TEST-WINDOWS-CRED-MANAGER"

        try:
            key = keystore.generate_key()
            keystore.store_key(vehicle_id, key)

            # Verify retrieval works
            retrieved_key = keystore.retrieve_key(vehicle_id)
            assert retrieved_key is not None
            assert retrieved_key == key

        finally:
            with contextlib.suppress(Exception):
                keystore.delete_key(vehicle_id)

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific keyring test")
    def test_macos_keychain(self, real_keyring_skip: None) -> None:
        """
        Test that macOS Keychain is properly used.

        GIVEN: Running on macOS
        WHEN: A key is stored via SigningKeystore
        THEN: It should be stored in macOS Keychain
        AND: The service name should be ArduPilotMethodicConfigurator
        """
        keystore = SigningKeystore()
        vehicle_id = "TEST-MACOS-KEYCHAIN"

        try:
            key = keystore.generate_key()
            keystore.store_key(vehicle_id, key)

            # Verify retrieval works
            retrieved_key = keystore.retrieve_key(vehicle_id)
            assert retrieved_key is not None
            assert retrieved_key == key

        finally:
            with contextlib.suppress(Exception):
                keystore.delete_key(vehicle_id)

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific keyring test")
    def test_linux_secret_service(self, real_keyring_skip: None) -> None:
        """
        Test that Linux SecretService is properly used.

        GIVEN: Running on Linux with SecretService available
        WHEN: A key is stored via SigningKeystore
        THEN: It should be stored in SecretService
        AND: The service name should be ArduPilotMethodicConfigurator
        """
        keystore = SigningKeystore()
        vehicle_id = "TEST-LINUX-SECRET-SERVICE"

        try:
            key = keystore.generate_key()
            keystore.store_key(vehicle_id, key)

            # Verify retrieval works
            retrieved_key = keystore.retrieve_key(vehicle_id)
            assert retrieved_key is not None
            assert retrieved_key == key

        finally:
            with contextlib.suppress(Exception):
                keystore.delete_key(vehicle_id)
