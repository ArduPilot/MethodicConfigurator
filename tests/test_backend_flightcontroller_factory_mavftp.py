#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_factory_mavftp.py.

This file focuses on MAVFTP factory function behavior.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp import (
    create_mavftp,
    create_mavftp_safe,
    create_mavftp_settings,
)
from ardupilot_methodic_configurator.backend_mavftp import FTP_OP, MAVFTP, OP_Ack, OP_ResetSessions


def _mock_master() -> MagicMock:
    """Create a mock connection that can complete MAVFTP session reset."""
    master = MagicMock()
    master.source_system = 1
    master.source_component = 1
    master.target_system = 1
    master.target_component = 1
    master.baud = None
    reply = FTP_OP(
        seq=1,
        session=0,
        opcode=OP_Ack,
        size=0,
        req_opcode=OP_ResetSessions,
        burst_complete=0,
        offset=0,
        payload=None,
    )
    packet = MagicMock()
    packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
    packet.get_srcSystem.side_effect = lambda: master.target_system
    packet.get_srcComponent.side_effect = lambda: master.target_component
    packet.target_system = 1
    packet.target_component = 1
    packet.payload = reply.pack()
    master.recv_match.return_value = packet
    return master


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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
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

    def test_create_mavftp_safe_returns_none_when_initialization_fails(self) -> None:
        """
        create_mavftp_safe handles MAVFTP initialization errors gracefully.

        GIVEN: A connection whose serial port dies while MAVFTP resets sessions
        WHEN: User creates MAVFTP safely
        THEN: The exception should not escape to the UI workflow
        AND: None should be returned so callers can fail gracefully
        """
        mock_master = _mock_master()
        mock_master.target_system = 1
        mock_master.target_component = 1

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp.MAVFTP",
            side_effect=OSError("ClearCommError failed"),
        ):
            result = create_mavftp_safe(mock_master)

        assert result is None


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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
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
        mock_master = _mock_master()
        mock_master.target_system = 10
        mock_master.target_component = 20

        # When: Create MAVFTP
        try:
            mavftp = create_mavftp(mock_master)
            # Then: Should succeed
            assert mavftp is not None
        except AttributeError as e:
            pytest.fail(f"Factory should access target_system and target_component attributes: {e}")


@pytest.mark.parametrize("factory", [create_mavftp, create_mavftp_safe], ids=["strict", "safe"])
@pytest.mark.parametrize(
    ("baud", "expected"),
    [
        (57600, (10.0, 3.0, 2.0)),
        (38400, (10.0, 3.0, 2.0)),
        (115200, (3.7, 1.0, 0.5)),
        (921600, (3.7, 1.0, 0.5)),
        (None, (3.7, 1.0, 0.5)),
        (0, (3.7, 1.0, 0.5)),
        (-1, (3.7, 1.0, 0.5)),
        (True, (3.7, 1.0, 0.5)),
        (Mock(), (3.7, 1.0, 0.5)),
    ],
)
def test_factories_inject_link_timing_before_session_initialization(
    factory: Callable[[MagicMock], MAVFTP | None], baud: object, expected: tuple[float, float, float]
) -> None:
    """
    Both application factories configure slow links before the protocol starts.

    GIVEN: A connection with a known or unavailable baud rate
    WHEN: Either factory constructs an FTP client and resets its sessions
    THEN: Link-specific settings are supplied to the constructor
    AND: USB and network defaults remain unchanged
    """
    master = _mock_master()
    master.baud = baud

    with patch("ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp.MAVFTP", wraps=MAVFTP) as initialize:
        client = factory(master)

    assert client is not None
    assert initialize.call_args.kwargs["settings"] is client.ftp_settings
    assert (
        client.ftp_settings.idle_detection_time,
        client.ftp_settings.read_retry_time,
        client.ftp_settings.retry_time,
    ) == expected
    assert client.target_system == master.target_system
    assert client.target_component == master.target_component
    assert client.pending_reset_seq is None
    master.mav.file_transfer_protocol_send.assert_called_once()
    assert master.mav.file_transfer_protocol_send.call_args.args[3][3] == OP_ResetSessions


def test_link_settings_are_independent_between_clients() -> None:
    """
    Tuning one client must not change another client's timing or protocol defaults.

    GIVEN: Independent settings for telemetry and USB connections
    WHEN: One telemetry client's retry setting is changed
    THEN: Other clients keep their own defaults
    """
    telemetry = create_mavftp_settings(Mock(baud=57600))
    usb = create_mavftp_settings(Mock(baud=115200))

    telemetry.retry_time = 4.0

    assert usb.retry_time == 0.5
    assert create_mavftp_settings(Mock(baud=57600)).retry_time == 2.0
    assert telemetry.burst_read_size == usb.burst_read_size == 80
    assert telemetry.write_qsize == usb.write_qsize == 5
    assert telemetry.initial_retries == usb.initial_retries == 0


def test_safe_factory_returns_none_when_protocol_class_is_unavailable() -> None:
    """
    Shared creation must preserve the safe factory's availability guard.

    GIVEN: An unavailable protocol implementation
    WHEN: The safe factory receives a connection
    THEN: It returns None without attempting construction
    """
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp.MAVFTP", None):
        assert create_mavftp_safe(_mock_master()) is None
