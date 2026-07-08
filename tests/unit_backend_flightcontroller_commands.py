#!/usr/bin/env python3

"""
Unit tests for backend_flightcontroller_commands.py.

These tests target specific implementation branches and internal code paths for
coverage purposes. For behavior-driven tests of flight controller command functionality,
see test_backend_flightcontroller_commands.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from unittest.mock import MagicMock, Mock, patch

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands


class TestSendCommandAndWaitAckBranches:
    """Unit tests for the internal branch logic of send_command_and_wait_ack."""

    def test_in_progress_ack_with_zero_progress_does_not_log_percentage(self) -> None:
        """
        Branch: MAV_RESULT_IN_PROGRESS with progress=0 skips the debug log call.

        The source code contains:
            if msg.progress is not None and msg.progress > 0:
                logging_debug(...)

        This test exercises the else path (progress <= 0) and verifies that
        logging_debug is not called with the percentage format string, then
        confirms the command eventually times out.
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = mavutil.mavlink.MAV_RESULT_IN_PROGRESS
        mock_ack.progress = 0  # <= 0 means logging_debug is NOT called for percentage

        call_count = [0]

        def side_effect_recv_match(*_args, **_kwargs) -> object:
            call_count[0] += 1
            if call_count[0] <= 2:
                return mock_ack
            return None  # Stop returning ACK so the loop times out

        mock_master.recv_match.side_effect = side_effect_recv_match

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_debug") as mock_debug:
            success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.3)

        assert success is False
        assert "timeout" in error.lower()
        # logging_debug should NOT have been called with the progress format string
        progress_log_calls = [c for c in mock_debug.call_args_list if c.args and "progress" in str(c.args[0]).lower()]
        assert progress_log_calls == [], "logging_debug should not have logged progress when progress=0"

    def test_in_progress_ack_with_positive_progress_logs_percentage(self) -> None:
        """
        Branch: MAV_RESULT_IN_PROGRESS with progress>0 triggers the debug log call.

        Exercises the complementary path to the test above: when progress is
        positive, logging_debug IS called with the percentage format string.
        After logging, the loop continues and eventually times out.
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        mock_ack = MagicMock()
        mock_ack.command = 888
        mock_ack.result = mavutil.mavlink.MAV_RESULT_IN_PROGRESS
        mock_ack.progress = 50  # > 0 → should trigger the debug log

        call_count = [0]

        def side_effect_recv_match(*_args, **_kwargs) -> object:
            call_count[0] += 1
            if call_count[0] <= 1:
                return mock_ack
            return None  # Time out after one in-progress message

        mock_master.recv_match.side_effect = side_effect_recv_match

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_debug") as mock_debug:
            success, _ = commands_mgr.send_command_and_wait_ack(command=888, timeout=0.3)

        assert success is False  # Timed out
        # logging_debug SHOULD have been called with a progress-related message
        progress_log_calls = [c for c in mock_debug.call_args_list if c.args and "progress" in str(c.args[0]).lower()]
        assert progress_log_calls != [], "logging_debug should have logged progress when progress=50"

    @pytest.mark.parametrize(
        ("result_code", "expected_keyword"),
        [
            (mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED, "rejected"),
            (mavutil.mavlink.MAV_RESULT_DENIED, "denied"),
            (mavutil.mavlink.MAV_RESULT_UNSUPPORTED, "unsupported"),
            (mavutil.mavlink.MAV_RESULT_FAILED, "failed"),
        ],
    )
    def test_known_failure_result_codes_map_to_correct_error_messages(self, result_code: int, expected_keyword: str) -> None:
        """
        Branch: each known non-ACCEPTED result code maps to a specific error string.

        Exercises the result_messages dict lookup for every non-success, non-progress
        result code defined by the protocol.
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        mock_ack = MagicMock()
        mock_ack.command = 777
        mock_ack.result = result_code
        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_command_and_wait_ack(command=777, timeout=1.0)

        assert success is False
        assert expected_keyword in error.lower(), f"Expected '{expected_keyword}' in error: {error!r}"


class TestFlightControllerCommandsMissingConnectionBranches:
    """Branch tests for commands when master is None (no active connection)."""

    @pytest.fixture
    def disconnected_commands_mgr(self) -> FlightControllerCommands:
        """Provide a FlightControllerCommands instance with no active connection."""
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        return FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

    def test_send_command_and_wait_ack_fails_without_connection(
        self, disconnected_commands_mgr: FlightControllerCommands
    ) -> None:
        """
        send_command_and_wait_ack returns (False, error) when master is None.

        GIVEN: No flight controller connection (master is None)
        WHEN: send_command_and_wait_ack is called
        THEN: False should be returned with an error mentioning the missing connection
        AND: No exceptions should be raised
        """
        success, error = disconnected_commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        assert success is False
        assert error != ""
        assert "connection" in error.lower()

    def test_stop_all_motors_fails_without_connection(self, disconnected_commands_mgr: FlightControllerCommands) -> None:
        """
        stop_all_motors returns (False, error) when master is None.

        GIVEN: No flight controller connection
        WHEN: stop_all_motors is called
        THEN: False should be returned with an error mentioning the missing connection
        AND: No exceptions should be raised
        """
        success, error = disconnected_commands_mgr.stop_all_motors()

        assert success is False
        assert error != ""
        assert "connection" in error.lower()

    def test_request_periodic_battery_status_fails_without_connection(
        self, disconnected_commands_mgr: FlightControllerCommands
    ) -> None:
        """
        request_periodic_battery_status returns (False, error) when master is None.

        GIVEN: No flight controller connection
        WHEN: request_periodic_battery_status is called
        THEN: False should be returned with an error mentioning the missing connection
        AND: No exceptions should be raised
        """
        success, error = disconnected_commands_mgr.request_periodic_battery_status()

        assert success is False
        assert error != ""
        assert "connection" in error.lower()


class TestFlightControllerCommandsFailureBranches:
    """Branch tests for failure result codes returned by the flight controller."""

    @pytest.fixture
    def commands_mgr_motor_ack(self) -> Callable[[int], FlightControllerCommands]:
        """Factory fixture: returns a callable that builds a commands manager with a given MAV_CMD_DO_MOTOR_TEST ACK."""

        def _make(result_code: int) -> FlightControllerCommands:
            mock_master = MagicMock()
            mock_master.target_system = 1
            mock_master.target_component = 1

            mock_ack = MagicMock()
            mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
            mock_ack.result = result_code

            mock_master.recv_match.return_value = mock_ack
            mock_conn_mgr = Mock()
            mock_conn_mgr.master = mock_master
            mock_params_mgr = Mock()
            mock_params_mgr.fc_parameters = {}

            return FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        return _make  # type: ignore[return-value]

    def test_reset_all_parameters_handles_command_failure(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        reset_all_parameters_to_default returns (False, error) when the FC denies the command.

        GIVEN: Connected flight controller that denies the parameter reset command
        WHEN: reset_all_parameters_to_default is called
        THEN: False should be returned with "denied" in the error message
        AND: fc_parameters should NOT be cleared on failure
        """
        mock_master, mock_conn_mgr = mock_connected_master

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE
        mock_ack.result = mavutil.mavlink.MAV_RESULT_DENIED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"PARAM1": 1.0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.reset_all_parameters_to_default()

        assert success is False
        assert "denied" in error.lower()
        assert len(mock_params_mgr.fc_parameters) > 0, "fc_parameters must NOT be cleared on failure"

    def test_test_motors_in_sequence_handles_command_failure(
        self, commands_mgr_motor_ack: Callable[[int], FlightControllerCommands]
    ) -> None:
        """
        test_motors_in_sequence returns (False, error) when the FC reports FAILED.

        GIVEN: Connected flight controller that rejects the sequential motor test command
        WHEN: test_motors_in_sequence is called
        THEN: False should be returned with "failed" in the error message
        """
        commands_mgr = commands_mgr_motor_ack(mavutil.mavlink.MAV_RESULT_FAILED)

        success, error = commands_mgr.test_motors_in_sequence(
            start_motor=1, motor_count=4, throttle_percent=10, timeout_seconds=2
        )

        assert success is False
        assert error != ""
        assert "failed" in error.lower()

    def test_stop_all_motors_handles_command_failure(
        self, commands_mgr_motor_ack: Callable[[int], FlightControllerCommands]
    ) -> None:
        """
        stop_all_motors returns (False, error) when the FC reports UNSUPPORTED.

        GIVEN: Connected flight controller that reports the motor stop command as unsupported
        WHEN: stop_all_motors is called
        THEN: False should be returned with "unsupported" in the error message
        """
        commands_mgr = commands_mgr_motor_ack(mavutil.mavlink.MAV_RESULT_UNSUPPORTED)

        success, error = commands_mgr.stop_all_motors()

        assert success is False
        assert error != ""
        assert "unsupported" in error.lower()


class TestCompassCalibrationProgressPolling:
    """Tests for compass calibration MAVLink polling behavior."""

    def test_get_compass_calibration_progress_preserves_mixed_progress_and_report_messages(self) -> None:
        """
        Progress polling should drain raw messages without discarding non-report updates.

        GIVEN: The MAVLink buffer contains both progress and report messages
        WHEN: get_compass_calibration_progress is called
        THEN: Both message types are returned in the order they were received
        AND: The backend does not filter progress away while looking for reports
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        mock_progress = MagicMock()
        mock_progress.get_type.return_value = "MAG_CAL_PROGRESS"
        mock_progress.compass_id = 0
        mock_progress.cal_status = 1
        mock_progress.completion_pct = 42
        mock_progress.direction_x = 1
        mock_progress.direction_y = 2
        mock_progress.direction_z = 3

        mock_report = MagicMock()
        mock_report.get_type.return_value = "MAG_CAL_REPORT"
        mock_report.compass_id = 0
        mock_report.cal_status = 4
        mock_report.fitness = 0.12
        mock_report.autosaved = True

        mock_master.recv_msg.side_effect = [mock_progress, mock_report, None]

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        result = commands_mgr.get_compass_calibration_progress()

        assert result == [
            {
                "type": "PROGRESS",
                "compass_id": 0,
                "status": 1,
                "completion_pct": 42,
                "direction_x": 1,
                "direction_y": 2,
                "direction_z": 3,
            },
            {
                "type": "REPORT",
                "compass_id": 0,
                "status": 4,
                "fitness": 0.12,
                "saved": True,
            },
        ]

    def test_get_compass_calibration_progress_surfaces_status_text_feedback(self) -> None:
        """
        Progress polling should preserve calibration status text as user feedback.

        GIVEN: The MAVLink buffer contains a compass-related STATUSTEXT
        WHEN: get_compass_calibration_progress is called
        THEN: The status text is returned with the compass id if it can be inferred
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        mock_status = MagicMock()
        mock_status.get_type.return_value = "STATUSTEXT"
        mock_status.text = "Mag(0) good orientation: 12 21.2"
        mock_status.severity = 6

        mock_master.recv_msg.side_effect = [mock_status, None]

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        result = commands_mgr.get_compass_calibration_progress()

        assert result == [
            {
                "type": "STATUS_TEXT",
                "compass_id": 0,
                "status": 6,
                "text": "Mag(0) good orientation: 12 21.2",
            },
        ]
