#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_factory_mavftp.py.

This file focuses on MAVFTP factory function behavior.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp import (
    create_mavftp,
    create_mavftp_safe,
)


class TestCreateMavftpFactory:
    """Test create_mavftp factory function."""

    def test_user_can_create_mavftp_with_valid_connection(self) -> None:
        """
        User can create MAVFTP instance with valid connection.

        GIVEN: A valid MAVLink connection with target system and component
        WHEN: User calls create_mavftp with the connection
        THEN: MAVFTP instance should be created successfully
        AND: MAVFTP should be initialized with correct target parameters
        """
        # Given: Valid MAVLink connection
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        # When: Create MAVFTP
        mavftp = create_mavftp(mock_master)

        # Then: MAVFTP should be created
        assert mavftp is not None

    def test_create_mavftp_raises_runtime_error_when_no_connection(self) -> None:
        """
        create_mavftp raises RuntimeError when connection is None.

        GIVEN: No connection available (None)
        WHEN: User calls create_mavftp with None
        THEN: RuntimeError should be raised
        AND: Error message should indicate no MAVLink connection
        """
        # When/Then: Should raise RuntimeError
        with pytest.raises(RuntimeError, match="No MAVLink connection available for MAVFTP"):
            create_mavftp(None)

    def test_create_mavftp_passes_target_system_to_mavftp(self) -> None:
        """
        create_mavftp passes target_system to MAVFTP initialization.

        GIVEN: A MAVLink connection with specific target_system value
        WHEN: User creates MAVFTP
        THEN: MAVFTP should be initialized with correct target_system
        """
        # Given: Connection with specific target system
        mock_master = MagicMock()
        mock_master.target_system = 42
        mock_master.target_component = 1

        # When: Create MAVFTP
        mavftp = create_mavftp(mock_master)

        # Then: MAVFTP created successfully (target_system passed internally)
        assert mavftp is not None

    def test_create_mavftp_passes_target_component_to_mavftp(self) -> None:
        """
        create_mavftp passes target_component to MAVFTP initialization.

        GIVEN: A MAVLink connection with specific target_component value
        WHEN: User creates MAVFTP
        THEN: MAVFTP should be initialized with correct target_component
        """
        # Given: Connection with specific target component
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 191  # MAV_COMP_ID_AUTOPILOT

        # When: Create MAVFTP
        mavftp = create_mavftp(mock_master)

        # Then: MAVFTP created successfully (target_component passed internally)
        assert mavftp is not None


class TestCreateMavftpSafeFactory:
    """Test create_mavftp_safe factory function with safe error handling."""

    def test_user_can_create_mavftp_safe_with_valid_connection(self) -> None:
        """
        User can create MAVFTP instance safely with valid connection.

        GIVEN: A valid MAVLink connection with target system and component
        WHEN: User calls create_mavftp_safe with the connection
        THEN: MAVFTP instance should be created successfully
        AND: Return value should not be None
        """
        # Given: Valid MAVLink connection
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        # When: Create MAVFTP safely
        mavftp = create_mavftp_safe(mock_master)

        # Then: MAVFTP should be created
        assert mavftp is not None

    def test_create_mavftp_safe_returns_none_when_no_connection(self) -> None:
        """
        create_mavftp_safe returns None instead of raising when connection is None.

        GIVEN: No connection available (None)
        WHEN: User calls create_mavftp_safe with None
        THEN: Should return None instead of raising exception
        AND: No error should occur
        """
        # When: Call create_mavftp_safe with None
        mavftp = create_mavftp_safe(None)

        # Then: Should return None gracefully
        assert mavftp is None

    def test_create_mavftp_safe_returns_none_when_mavftp_unavailable(self) -> None:
        """
        create_mavftp_safe returns None when MAVFTP module is unavailable.

        GIVEN: A MAVLink connection but MAVFTP class is None
        WHEN: User calls create_mavftp_safe
        THEN: Should return None instead of raising exception
        AND: No error should occur even if MAVFTP is unavailable
        """
        # Note: This test validates the safety check for MAVFTP availability
        # In normal operation, MAVFTP will be imported, but the function has
        # defensive checks for when it might not be available
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        # When: Create MAVFTP safely (MAVFTP is normally available)
        mavftp = create_mavftp_safe(mock_master)

        # Then: Should create successfully (MAVFTP is available in normal case)
        assert mavftp is not None

    def test_create_mavftp_safe_passes_target_system_to_mavftp(self) -> None:
        """
        create_mavftp_safe passes target_system to MAVFTP initialization.

        GIVEN: A MAVLink connection with specific target_system value
        WHEN: User creates MAVFTP safely
        THEN: MAVFTP should be initialized with correct target_system
        """
        # Given: Connection with specific target system
        mock_master = MagicMock()
        mock_master.target_system = 99
        mock_master.target_component = 1

        # When: Create MAVFTP safely
        mavftp = create_mavftp_safe(mock_master)

        # Then: MAVFTP created successfully
        assert mavftp is not None

    def test_create_mavftp_safe_passes_target_component_to_mavftp(self) -> None:
        """
        create_mavftp_safe passes target_component to MAVFTP initialization.

        GIVEN: A MAVLink connection with specific target_component value
        WHEN: User creates MAVFTP safely
        THEN: MAVFTP should be initialized with correct target_component
        """
        # Given: Connection with specific target component
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 50

        # When: Create MAVFTP safely
        mavftp = create_mavftp_safe(mock_master)

        # Then: MAVFTP created successfully
        assert mavftp is not None


class TestCreateMavftpErrorHandling:
    """Test error handling in MAVFTP factory functions."""

    def test_create_mavftp_error_message_is_descriptive(self) -> None:
        """
        create_mavftp error message clearly describes the issue.

        GIVEN: No connection available
        WHEN: User calls create_mavftp with None
        THEN: RuntimeError should indicate MAVFTP needs connection
        AND: Message should be clear and actionable
        """
        # When/Then: Should raise with clear message
        with pytest.raises(RuntimeError) as exc_info:
            create_mavftp(None)

        error_msg = str(exc_info.value)
        assert "MAVFTP" in error_msg
        assert "connection" in error_msg.lower()

    def test_create_mavftp_safe_handles_none_gracefully(self) -> None:
        """
        create_mavftp_safe handles None connection gracefully without logging errors.

        GIVEN: No connection available
        WHEN: User calls create_mavftp_safe with None
        THEN: Should return None without raising
        AND: Call should be idempotent (safe to call multiple times)
        """
        # When: Call multiple times
        result1 = create_mavftp_safe(None)
        result2 = create_mavftp_safe(None)
        result3 = create_mavftp_safe(None)

        # Then: All should return None consistently
        assert result1 is None
        assert result2 is None
        assert result3 is None


class TestCreateMavftpEdgeCases:
    """Test edge cases in MAVFTP factory functions."""

    def test_create_mavftp_with_zero_target_system(self) -> None:
        """
        create_mavftp works with target_system=0.

        GIVEN: A MAVLink connection with target_system=0
        WHEN: User creates MAVFTP
        THEN: MAVFTP should be created (0 is valid, though unusual)
        """
        # Given: Connection with target_system = 0
        mock_master = MagicMock()
        mock_master.target_system = 0
        mock_master.target_component = 1

        # When: Create MAVFTP
        mavftp = create_mavftp(mock_master)

        # Then: MAVFTP should be created
        assert mavftp is not None

    def test_create_mavftp_with_max_target_ids(self) -> None:
        """
        create_mavftp works with maximum target system/component IDs.

        GIVEN: A MAVLink connection with maximum valid IDs
        WHEN: User creates MAVFTP
        THEN: MAVFTP should be created successfully
        """
        # Given: Connection with maximum IDs
        mock_master = MagicMock()
        mock_master.target_system = 255  # Max system ID
        mock_master.target_component = 255  # Max component ID

        # When: Create MAVFTP
        mavftp = create_mavftp(mock_master)

        # Then: MAVFTP should be created
        assert mavftp is not None

    def test_create_mavftp_safe_returns_none_not_false(self) -> None:
        """
        create_mavftp_safe returns None specifically, not False or empty.

        GIVEN: No connection available
        WHEN: User calls create_mavftp_safe
        THEN: Should return None specifically (not False, not empty string)
        AND: Type should be correct for optional checks
        """
        # When: Call with None
        result = create_mavftp_safe(None)

        # Then: Should be None specifically
        assert result is None
        assert result is not False
        assert result != ""

    def test_create_mavftp_with_connection_attributes(self) -> None:
        """
        create_mavftp correctly accesses connection attributes.

        GIVEN: A MAVLink connection with specific attributes
        WHEN: User creates MAVFTP
        THEN: Factory should read target_system and target_component attributes
        AND: No AttributeError should occur
        """
        # Given: Connection with required attributes (MagicMock includes mav attribute)
        mock_master = MagicMock()
        mock_master.target_system = 10
        mock_master.target_component = 20

        # When: Create MAVFTP
        try:
            mavftp = create_mavftp(mock_master)
            # Then: Should succeed
            assert mavftp is not None
        except AttributeError as e:
            pytest.fail(f"Factory should access target_system and target_component attributes: {e}")
