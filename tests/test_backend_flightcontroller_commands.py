#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_commands.py.

This file focuses on command execution behavior including motor tests,
battery status requests, and parameter reset commands.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import itertools
import subprocess
import sys
import time
from math import isnan
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v10 import ardupilotmega as mavlink1
from pymavlink.dialects.v20 import ardupilotmega as mavlink2

from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands

# pylint: disable=too-many-lines


def test_command_ack_meets_pylint_statement_and_return_limits() -> None:
    """Keep the CI pylint gate green when command ACK handling changes."""
    pytest.importorskip("pylint")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pylint",
            "--persistent=n",
            "--score=n",
            "--disable=all",
            "--enable=R0911,R0915",
            "ardupilot_methodic_configurator/backend_flightcontroller_commands.py",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "R0911:" not in result.stdout
    assert "R0915:" not in result.stdout


def test_reboot_to_bootloader_holds_bootloader_without_force_flags() -> None:
    """The reboot command must hold in bootloader mode and preserve param6=0."""
    master = MagicMock()
    master.target_system = 1
    master.target_component = 1
    acknowledgement = MagicMock()
    acknowledgement.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN
    acknowledgement.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
    master.recv_match.return_value = acknowledgement

    connection = Mock()
    connection.master = master
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)

    assert commands.reboot_to_bootloader() == (True, "")

    sent_parameters = master.mav.command_long_send.call_args.args[4:11]
    assert sent_parameters == (3, 0, 0, 0, 0, 0, 0)


class TestFlightControllerCommandsInitialization:
    """Test command manager initialization and setup."""

    def test_user_can_create_commands_manager(self) -> None:
        """
        User can create command manager with required dependencies.

        GIVEN: Params manager and connection manager available
        WHEN: User creates commands manager
        THEN: Manager should be initialized successfully
        AND: Dependencies should be stored
        """
        # Given: Mock dependencies
        mock_params_mgr = Mock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        # When: Create command manager
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)
        # Then: Manager initialized
        assert commands_mgr is not None
        assert commands_mgr.master is None

    def test_commands_manager_requires_dependencies(self) -> None:
        """A command manager requires its parameter and connection managers."""
        with pytest.raises(ValueError, match=r"^params_manager is required$"):
            FlightControllerCommands(params_manager=None, connection_manager=Mock())
        with pytest.raises(ValueError, match=r"^connection_manager is required$"):
            FlightControllerCommands(params_manager=Mock(), connection_manager=None)


def test_aborting_level_calibration_allows_a_new_attempt(mock_connected_master: tuple[MagicMock, Mock]) -> None:
    """An abandoned view must not leave the command manager busy for the session."""
    master, connection = mock_connected_master
    old_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
    old_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
    master.recv_match.side_effect = [old_ack, None, None]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)

    assert commands.start_accel_calibration_level() == (True, "")
    commands.abort_level_calibration()
    assert commands.start_accel_calibration_level() == (True, "")
    assert master.mav.command_long_send.call_count == 2


def test_abandoned_level_ack_cannot_complete_a_new_attempt(mock_connected_master: tuple[MagicMock, Mock]) -> None:
    """A late ACK from an abandoned trim must be consumed before another trim starts."""
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    assert commands.start_accel_calibration_level() == (True, "")
    commands.abort_level_calibration()

    assert commands.start_accel_calibration_level() == (
        False,
        "The previous level calibration is still finishing; try again shortly",
    )
    assert master.mav.command_long_send.call_count == 1
    old_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
    old_ack.result = mavutil.mavlink.MAV_RESULT_FAILED
    master.recv_match.side_effect = [old_ack, None]
    assert commands.start_accel_calibration_level() == (True, "")
    assert master.mav.command_long_send.call_count == 2
    master.recv_match.side_effect = [None]
    assert commands.poll_accel_calibration_level() is None


def test_expired_unpolled_level_calibration_can_restart(mock_connected_master: tuple[MagicMock, Mock]) -> None:
    """The ACK deadline must also be checked when starting a later attempt."""
    master, connection = mock_connected_master
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_level() == (True, "")
        now[0] = commands.LEVEL_CALIBRATION_ACK_TIMEOUT
        assert commands.start_accel_calibration_level() == (True, "")
    assert master.mav.command_long_send.call_count == 2


def test_aborting_level_calibration_ignores_transport_errors(
    mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
) -> None:
    """Closing a calibration on a dead serial link must still release local state."""
    master, connection = mock_connected_master
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    assert commands.start_accel_calibration_level() == (True, "")
    master.recv_match.side_effect = OSError("serial link disappeared")

    with caplog.at_level("DEBUG"):
        commands.abort_level_calibration()
    assert caplog.messages == ["Could not drain abandoned level calibration messages: serial link disappeared"]

    assert commands._level_calibration.active is False  # pylint: disable=protected-access
    assert commands._abandoned_level_deadline is None  # pylint: disable=protected-access


def test_aborting_during_retry_cooldown_allows_immediate_restart(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """No stale ACK quarantine is needed after the prior command already rejected."""
    master, connection = mock_connected_master
    rejected = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
    rejected.result = mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED
    master.recv_match.side_effect = itertools.chain([rejected], itertools.repeat(None))
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]

    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_level() == (True, "")
        assert commands.poll_accel_calibration_level() is None
        now[0] = commands.COMMAND_ACK_STATUS_TEXT_GRACE + 0.1
        assert commands.poll_accel_calibration_level() is None
        commands.abort_level_calibration()
        assert commands.start_accel_calibration_level() == (True, "")

    assert master.mav.command_long_send.call_count == 2


def test_timed_out_level_calibration_quarantines_a_late_ack(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """An ACK arriving just after timeout cannot complete a newly sent command."""
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]

    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_level() == (True, "")
        now[0] = commands.LEVEL_CALIBRATION_ACK_TIMEOUT + 1
        timeout_result = commands.poll_accel_calibration_level()
        assert timeout_result is not None
        assert timeout_result[0] is False
        assert commands.start_accel_calibration_level()[0] is False

        late_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
        late_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        master.recv_match.side_effect = [late_ack, None]
        assert commands.start_accel_calibration_level() == (True, "")

    assert master.mav.command_long_send.call_count == 2


def test_timed_out_level_calibration_quarantine_expires(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """A missing late ACK must not prevent all future level calibrations."""
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]

    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_level() == (True, "")
        now[0] = commands.LEVEL_CALIBRATION_ACK_TIMEOUT + 1
        timeout_result = commands.poll_accel_calibration_level()
        assert timeout_result is not None
        assert timeout_result[0] is False
        now[0] += commands.LEVEL_CALIBRATION_LATE_ACK_GUARD + 1
        assert commands.start_accel_calibration_level() == (True, "")

    assert master.mav.command_long_send.call_count == 2


@pytest.mark.parametrize("result", [mavutil.mavlink.MAV_RESULT_FAILED, 9999])
def test_failed_ack_without_status_capture_returns_immediately(
    mock_connected_master: tuple[MagicMock, Mock], result: int
) -> None:
    """Commands that do not collect STATUSTEXT must not wait through its grace period."""
    master, connection = mock_connected_master
    ack = MagicMock(command=mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST, result=result)
    master.recv_match.return_value = ack
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)

    with patch(
        "ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep", side_effect=AssertionError
    ) as sleep:
        success, _message = commands.send_command_and_wait_ack(mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST)

    assert success is False
    sleep.assert_not_called()
    master.recv_match.assert_called_once_with(type="COMMAND_ACK", blocking=False)


class TestFlightControllerCommandsMotorTest:
    """Test motor testing command functionality."""

    def test_user_can_test_individual_motor(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can test individual motor at specified throttle.

        GIVEN: Connected flight controller ready for motor test
        WHEN: User tests motor 1 at 10% throttle
        THEN: MAVLink command should be sent correctly
        AND: Command acknowledgment should be received
        """
        # Given: Connected FC with ACK response
        # Given: Connected FC
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST)
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        # When: Test motor
        success, error = commands_mgr.test_motor(
            test_sequence_nr=1, motor_letters="A", motor_output_nr=1, throttle_percent=10, timeout_seconds=2
        )
        # Then: Command sent successfully
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once_with(
            mock_master.target_system,
            mock_master.target_component,
            mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
            0,
            2,
            0,
            10,
            2,
            0,
            0,
            0,
        )

    def test_motor_test_fails_without_connection(self) -> None:
        """
        Motor test fails gracefully without connection.

        GIVEN: No flight controller connection
        WHEN: User attempts motor test
        THEN: Operation should fail with clear error
        AND: No exceptions should be raised
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        # When: Attempt motor test
        success, error = commands_mgr.test_motor(1, "A", 1, 10, 2)
        # Then: Clear failure
        assert success is False
        assert "connection" in error.lower()


class TestFlightControllerCommandsBatteryStatus:
    """Test battery status request functionality."""

    def test_user_can_request_battery_status(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can request periodic battery status updates.

        GIVEN: Connected flight controller with battery monitoring
        WHEN: User requests battery status at 1Hz
        THEN: Data stream request should be sent
        AND: Command should be acknowledged
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL)
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        # When: Request battery status
        success, error = commands_mgr.request_periodic_battery_status(interval_microseconds=1000000)
        # Then: Request sent
        assert success is True
        assert error == ""

    def test_user_can_get_battery_status(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can get current battery status from flight controller.

        GIVEN: Flight controller with battery monitoring enabled
        WHEN: User requests current battery status
        THEN: Voltage and current should be returned
        AND: Values should be in expected ranges
        """
        # Given: FC with battery data
        mock_master, mock_conn_mgr = mock_connected_master
        mock_battery_msg = MagicMock(id=0, voltages_ext=[0] * 4)
        mock_battery_msg.voltages = [4200, 4180, 4190]
        mock_battery_msg.current_battery = 2500
        mock_master.recv_match.side_effect = [mock_battery_msg, None]
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4.0}
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)
        # When: Get battery status
        battery_data, message = commands_mgr.get_battery_statuses()
        # Then: Status retrieved
        assert battery_data is not None
        assert message == ""
        voltage, current = battery_data[0]
        assert voltage > 0
        assert current >= 0


class TestFlightControllerCommandsParameterReset:  # pylint: disable=too-few-public-methods
    """Test parameter reset command functionality."""

    def test_user_can_reset_all_parameters_to_defaults(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can reset all parameters to factory defaults.

        GIVEN: Flight controller with modified parameters
        WHEN: User resets all parameters to defaults
        THEN: Reset command should be sent
        AND: Command should be acknowledged
        """
        # Given: Connected FC
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE)
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        # When: Reset parameters
        success, error = commands_mgr.reset_all_parameters_to_default()
        # Then: Command sent
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        command_args = mock_master.mav.command_long_send.call_args.args
        assert command_args[2] == mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE
        assert command_args[:4] == (
            mock_master.target_system,
            mock_master.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE,
            0,
        )
        assert command_args[4:] == (2, 0, 0, 0, 0, 0, 0)


class TestFlightControllerCommandsSendCommandAndWaitAck:
    """Test low-level command sending with ACK waiting."""

    def test_command_waits_for_acknowledgment(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Command sending waits for proper acknowledgment.

        GIVEN: Flight controller command infrastructure
        WHEN: User sends command with ACK expected
        THEN: Function should wait for ACK message
        AND: Return success when ACK received
        """
        # Given: FC that sends ACK
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock(command=123)
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        # When: Send command
        success, error = commands_mgr.send_command_and_wait_ack(
            command=123, param1=1, param2=2, param3=3, param4=4, param5=5, param6=6, param7=7, timeout=1.0
        )
        # Then: ACK received
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once_with(
            mock_master.target_system, mock_master.target_component, 123, 0, 1, 2, 3, 4, 5, 6, 7
        )

    def test_command_timeout_returns_error(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Command timeout returns appropriate error.

        GIVEN: Flight controller not responding
        WHEN: User sends command with timeout
        THEN: Timeout error should be returned
        AND: Error message should indicate timeout
        """
        # Given: FC that doesn't respond
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=[0.0, 2.0]),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep"),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_error") as mock_err,
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_debug") as mock_dbg,
        ):
            success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=1.0)
            # Then: Timeout error
            assert success is False
            assert "timeout" in error.lower()
            mock_err.assert_not_called()
            mock_dbg.assert_called_once()


class TestFlightControllerCommandsPropertyDelegation:  # pylint: disable=too-few-public-methods
    """Test property delegation to connection manager."""

    def test_master_property_delegates_to_connection_manager(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Master property correctly delegates to connection manager.

        GIVEN: Commands manager with connection manager
        WHEN: Accessing master property
        THEN: Connection manager's master should be returned
        """
        # Given: Connection with master
        mock_master, mock_conn_mgr = mock_connected_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Access master
        retrieved_master = commands_mgr.master

        # Then: Correct master returned
        assert retrieved_master is mock_master


class TestFlightControllerCommandsEdgeCases:
    """Additional edge-case tests for battery and command handling."""

    def test_request_periodic_battery_status_denied(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """Battery status request should propagate NACK/denied responses."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_DENIED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.request_periodic_battery_status(interval_microseconds=1000000)

        assert success is False
        assert "denied" in error.lower()

    def test_get_battery_status_returns_recent_cache(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """Return cached battery data when no new telemetry is available but a recent value exists."""
        mock_master, mock_conn_mgr = mock_connected_master
        # Simulate no new telemetry
        mock_master.recv_match.return_value = None

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4.0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # Inject a recent cached battery reading
        commands_mgr._last_battery_statuses = {0: (11.1, 2.2, time.time())}  # pylint: disable=protected-access
        commands_mgr._battery_status_connection = mock_master  # pylint: disable=protected-access

        data, _ = commands_mgr.get_battery_statuses()

        assert data == {0: (11.1, 2.2)}

    def test_get_battery_status_handles_invalid_readings(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """Unavailable BATTERY_STATUS readings should remain unknown."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_battery_msg = MagicMock(id=0, voltages_ext=[0] * 4)
        mock_battery_msg.voltages = [-1]
        mock_battery_msg.current_battery = -1
        mock_master.recv_match.side_effect = [mock_battery_msg, None]
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4.0}
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        battery_data, _ = commands_mgr.get_battery_statuses()

        assert battery_data is not None
        voltage, current = battery_data[0]
        assert isnan(voltage)
        assert isnan(current)

    def test_motor_test_denied_ack(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """Motor test should fail when FC returns a DENIED acknowledgment."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_DENIED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.test_motor(1, "A", 1, 10, 2)

        assert success is False
        assert "denied" in error.lower()

    def test_send_command_unknown_result(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """send_command_and_wait_ack should return an error for unknown result codes."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = 9999  # unknown result
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        assert success is False
        assert "unknown result" in error.lower()

    def test_send_command_in_progress_then_accepted(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """send_command_and_wait_ack should handle IN_PROGRESS followed by ACCEPTED."""
        mock_master, mock_conn_mgr = mock_connected_master
        in_progress = MagicMock()
        in_progress.command = 555
        in_progress.result = mavutil.mavlink.MAV_RESULT_IN_PROGRESS
        in_progress.progress = 10

        accepted = MagicMock()
        accepted.command = 555
        accepted.result = mavutil.mavlink.MAV_RESULT_ACCEPTED

        # First return in-progress, then accepted
        mock_master.recv_match.side_effect = [in_progress, accepted]

        mock_params_mgr = Mock()
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_command_and_wait_ack(command=555, timeout=1.0)

        assert success is True
        assert error == ""


class TestFlightControllerCommandsAllMotors:
    """Test test_all_motors functionality."""

    def test_user_can_test_all_motors(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can test all motors simultaneously.

        GIVEN: Connected flight controller ready for motor test
        WHEN: User tests all 4 motors at 25% throttle
        THEN: Motor commands should be sent for each motor
        AND: Method should return success
        """
        # Given: Connected FC
        mock_master, mock_conn_mgr = mock_connected_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Test all motors
        success, error = commands_mgr.test_all_motors(nr_of_motors=4, throttle_percent=25, timeout_seconds=5)

        # Then: Commands should be sent
        assert success is True
        assert error == ""
        assert [entry.args for entry in mock_master.mav.command_long_send.call_args_list] == [
            (mock_master.target_system, mock_master.target_component, mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST, 0)
        ] * 4
        assert [entry.kwargs for entry in mock_master.mav.command_long_send.call_args_list] == [
            {"param1": motor, "param2": 0, "param3": 25, "param4": 5, "param5": 0, "param6": 0, "param7": 0}
            for motor in (1, 2, 3, 4)
        ]

    def test_test_all_motors_fails_without_connection(self) -> None:
        """
        Testing all motors fails without connection.

        GIVEN: Flight controller with no active connection
        WHEN: User attempts to test all motors
        THEN: Should return failure
        AND: Error message should indicate no connection
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When/Then
        success, error = commands_mgr.test_all_motors(nr_of_motors=4, throttle_percent=25, timeout_seconds=5)

        assert success is False
        assert "no flight controller connection" in error.lower()


class TestFlightControllerCommandsSequencedMotors:
    """Test test_motors_in_sequence functionality."""

    def test_user_can_test_motors_in_sequence(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can test motors in sequence.

        GIVEN: Connected flight controller ready for motor test
        WHEN: User tests 4 motors starting from motor 1 at 30% throttle
        THEN: Sequential motor test command should be sent with wait for ack
        AND: Method should return success
        """
        # Given: Connected FC with ACK response
        mock_master, mock_conn_mgr = mock_connected_master

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Test motors in sequence
        success, error = commands_mgr.test_motors_in_sequence(
            start_motor=1, motor_count=4, throttle_percent=30, timeout_seconds=3
        )

        # Then: Command acknowledged
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once_with(
            mock_master.target_system,
            mock_master.target_component,
            mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
            0,
            1,
            0,
            30,
            3,
            4,
            mavutil.mavlink.MOTOR_TEST_ORDER_SEQUENCE,
            0,
        )

    def test_test_motors_in_sequence_fails_without_connection(self) -> None:
        """
        Testing motors in sequence fails without connection.

        GIVEN: Flight controller with no active connection
        WHEN: User attempts to test motors in sequence
        THEN: Should return failure
        AND: Error message should indicate no connection
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When/Then
        success, error = commands_mgr.test_motors_in_sequence(
            start_motor=1, motor_count=4, throttle_percent=30, timeout_seconds=3
        )

        assert success is False
        assert "no flight controller connection" in error.lower()


class TestFlightControllerCommandsStopMotors:  # pylint: disable=too-few-public-methods
    """Test stop_all_motors functionality."""

    def test_user_can_stop_all_motors(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can stop all motors with emergency stop command.

        GIVEN: Connected flight controller with running motors
        WHEN: User executes stop all motors command
        THEN: Motor stop command should be sent
        AND: Command should be acknowledged
        """
        # Given: Connected FC with ACK response
        mock_master, mock_conn_mgr = mock_connected_master

        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Stop all motors
        success, error = commands_mgr.stop_all_motors()

        # Then: Command acknowledged
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once_with(
            mock_master.target_system, mock_master.target_component, mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST, *(0,) * 8
        )


class TestFlightControllerCommandsWrapperMethods:
    """Test wrapper methods that delegate to business logic."""

    def test_user_can_get_voltage_thresholds(self) -> None:
        """
        User can retrieve voltage thresholds for safe motor testing.

        GIVEN: Parameters manager with battery voltage parameters
        WHEN: User requests voltage thresholds
        THEN: Should return min and max voltage values
        AND: Values should be reasonable thresholds
        """
        # Given: Mock params manager with typical battery parameters
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {
            "BATT_ARM_VOLT": 9.6,
            "MOT_BAT_VOLT_MAX": 12.6,
        }

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get voltage thresholds
        min_volt, max_volt = commands_mgr.get_voltage_thresholds()

        # Then: Should return reasonable thresholds
        assert isinstance(min_volt, (int, float))
        assert isinstance(max_volt, (int, float))
        assert min_volt < max_volt
        assert min_volt == 9.6
        assert max_volt == 12.6

    def test_user_can_check_battery_monitoring_enabled(self) -> None:
        """
        User can check if battery monitoring is enabled.

        GIVEN: Parameters manager with BATT_MONITOR parameter
        WHEN: User checks battery monitoring status
        THEN: Should return True if BATT_MONITOR != 0
        """
        # Given: Battery monitoring enabled
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Check if battery monitoring enabled
        enabled = commands_mgr.is_battery_monitoring_enabled()

        # Then: Should be True
        assert enabled is True

    def test_battery_monitoring_disabled_returns_false(self) -> None:
        """
        Battery monitoring check returns False when disabled.

        GIVEN: Parameters manager with BATT_MONITOR=0
        WHEN: User checks battery monitoring status
        THEN: Should return False
        """
        # Given: Battery monitoring disabled
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 0}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Check if battery monitoring enabled
        enabled = commands_mgr.is_battery_monitoring_enabled()

        # Then: Should be False
        assert enabled is False

    def test_user_can_get_frame_info(self) -> None:
        """
        User can retrieve frame class and type information.

        GIVEN: Parameters manager with FRAME_CLASS and FRAME_TYPE
        WHEN: User requests frame information
        THEN: Should return frame class and type as integers
        """
        # Given: Mock params manager with frame parameters
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {
            "FRAME_CLASS": 1,  # Copter quadrotor
            "FRAME_TYPE": 1,  # X
        }

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get frame info
        frame_class, frame_type = commands_mgr.get_frame_info()

        # Then: Should return frame class and type
        assert frame_class == 1
        assert frame_type == 1


class TestFlightControllerCommandsAccelerometerCalibration:  # pylint: disable=too-many-public-methods
    """Test accelerometer calibration command functionality."""

    def test_user_can_start_simple_accelerometer_calibration(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can start the simple one-shot accelerometer calibration.

        GIVEN: Connected flight controller ready for calibration
        WHEN: User starts simple accelerometer calibration
        THEN: Preflight calibration command should be sent with param5=4
        AND: The command should be acknowledged successfully
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack

        mock_params_mgr = Mock()
        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_simple()

        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        args = mock_master.mav.command_long_send.call_args.args
        assert args[:4] == (
            mock_master.target_system,
            mock_master.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
        )
        assert args[4:] == (0, 0, 0, 0, 4.0, 0, 0)

    def test_simple_accelerometer_calibration_fails_without_connection(self) -> None:
        """
        Simple accelerometer calibration fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: User starts simple accelerometer calibration
        THEN: The method should return a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_simple()

        assert success is False
        assert "connection" in error.lower()

    def test_user_can_start_full_accelerometer_calibration(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        User can start the interactive 6-position accelerometer calibration.

        GIVEN: Connected flight controller ready for calibration
        WHEN: User starts full accelerometer calibration
        THEN: Preflight calibration command should be sent with param5=1
        AND: The command should be reported as sent successfully
        """
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_accel_calibration_full_start()

        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        args = mock_master.mav.command_long_send.call_args.args
        assert args[2] == mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        assert args[:4] == (
            mock_master.target_system,
            mock_master.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
        )
        assert args[4:] == (0, 0, 0, 0, 1, 0, 0)

    def test_full_accelerometer_calibration_fails_without_connection(self) -> None:
        """
        Full accelerometer calibration fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: User starts the full accelerometer calibration
        THEN: The method should return a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_accel_calibration_full_start()

        assert success is False
        assert "connection" in error.lower()

    def test_poll_accel_cal_vehicle_pos_is_non_blocking_and_parses_position(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling for accel calibration position should not block the UI thread.

        GIVEN: A COMMAND_LONG message requesting a calibration position
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: The message should be read with non-blocking recv_match
        AND: The requested position should be returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_msg = MagicMock()
        mock_msg.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        mock_msg.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT
        # Return the message once, then None to terminate the drain loop
        mock_master.recv_match.side_effect = [mock_msg, None]

        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        position = commands_mgr.poll_accel_cal_vehicle_pos()

        assert position == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT
        assert mock_master.recv_match.call_count == 2
        mock_master.recv_match.assert_called_with(type="COMMAND_LONG", blocking=False)

    def test_poll_accel_cal_vehicle_pos_returns_none_without_connection(self) -> None:
        """
        Polling accel calibration position returns None without a connection.

        GIVEN: No flight controller connection
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: The method should return None
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_simple_accelerometer_calibration_reports_backend_failure(
        self, mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A rejected simple calibration surfaces the acknowledgement failure.

        GIVEN: A connected flight controller that rejects the calibration command
        WHEN: User starts simple accelerometer calibration
        THEN: The method reports failure with the backend error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        mock_ack.result = mavutil.mavlink.MAV_RESULT_FAILED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        with caplog.at_level("ERROR"):
            success, error = commands_mgr.start_accel_calibration_simple()
        assert caplog.messages == ["Command failed", "Simple accelerometer calibration failed: Command failed"]

        assert success is False
        assert error == "Command failed"

    def test_simple_calibration_includes_firmware_failure_reason(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """A rejected simple calibration includes the following firmware status text."""
        master, connection = mock_connected_master
        ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
        ack.result = mavutil.mavlink.MAV_RESULT_FAILED
        status = MagicMock()
        status.get_type.return_value = "STATUSTEXT"
        status.text = b"Disarm to allow calibration"
        master.recv_match.side_effect = [ack, status, *([None] * 20)]
        commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)

        assert commands.start_accel_calibration_simple() == (False, "Command failed: Disarm to allow calibration")
        assert master.recv_match.call_args.kwargs["type"] == ["COMMAND_ACK", "STATUSTEXT"]

    def test_user_can_run_level_accelerometer_calibration(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Starting level trim sends its command without waiting for the ACK.

        GIVEN: A connected flight controller ready for level trim
        WHEN: User starts level calibration
        THEN: Preflight calibration is sent with param5=2 and the call returns immediately
        """
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep") as mock_sleep:
            success, error = commands_mgr.start_accel_calibration_level()

        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()
        mock_master.recv_match.assert_not_called()
        mock_sleep.assert_not_called()
        args = mock_master.mav.command_long_send.call_args.args
        assert args[2] == mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        assert args[:4] == (
            mock_master.target_system,
            mock_master.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
        )
        assert args[4:] == (0, 0, 0, 0, 2.0, 0, 0)

    def test_level_calibration_reports_success_when_polled_acknowledgment_arrives(
        self, mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
    ) -> None:
        """A later accepted ACK completes the previously started level trim."""
        mock_master, mock_conn_mgr = mock_connected_master
        accepted_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
        accepted_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = accepted_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.start_accel_calibration_level() == (True, "")
        with caplog.at_level("INFO"):
            assert commands_mgr.poll_accel_calibration_level() == (True, "")
        assert caplog.messages == ["Level calibration completed successfully"]

    def test_level_accelerometer_calibration_retries_a_temporary_rejection(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Level trim retries when the flight controller is still cooling down.

        GIVEN: The flight controller temporarily rejects the first level-trim request
        WHEN: The cooldown has elapsed and the command is retried
        THEN: The level calibration succeeds without showing the transient rejection
        """
        # Arrange (Given)
        mock_master, mock_conn_mgr = mock_connected_master
        temporary_ack = MagicMock()
        temporary_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        temporary_ack.result = mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED
        accepted_ack = MagicMock()
        accepted_ack.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        accepted_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.side_effect = [temporary_ack, None, None, accepted_ack]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # Act (When)
        now = [0.0]
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
            assert commands_mgr.start_accel_calibration_level() == (True, "")
            assert commands_mgr.poll_accel_calibration_level() is None
            now[0] = 0.6
            assert commands_mgr.poll_accel_calibration_level() is None
            now[0] = 5.6
            assert commands_mgr.poll_accel_calibration_level() is None
            result = commands_mgr.poll_accel_calibration_level()

        # Assert (Then)
        assert result == (True, "")
        assert mock_master.mav.command_long_send.call_count == 2

    def test_level_calibration_retries_until_an_in_progress_calibration_finishes(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """Repeated temporary rejections are retried without relying on translated text."""
        mock_master, mock_conn_mgr = mock_connected_master
        temporary_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
        temporary_ack.result = mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED
        accepted_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
        accepted_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        max_retries = FlightControllerCommands.LEVEL_CALIBRATION_MAX_RETRIES
        mock_master.recv_match.side_effect = [
            message for _ in range(max_retries + 1) for message in (temporary_ack, None, None)
        ]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        now = [0.0]
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
            assert commands_mgr.start_accel_calibration_level() == (True, "")
            result = None
            for retry_number in range(max_retries + 1):
                assert commands_mgr.poll_accel_calibration_level() is None
                now[0] += 0.6
                result = commands_mgr.poll_accel_calibration_level()
                if retry_number < max_retries:
                    assert result is None
                    now[0] += FlightControllerCommands.LEVEL_CALIBRATION_RETRY_DELAY
                    assert commands_mgr.poll_accel_calibration_level() is None

        assert result == (False, "Command temporarily rejected")
        assert mock_master.mav.command_long_send.call_count == max_retries + 1

    def test_level_calibration_waits_long_enough_for_firmware_gyro_convergence(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """Level trim allows the firmware's gyro-convergence window plus margin."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        now = [0.0]
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
            assert commands_mgr.start_accel_calibration_level() == (True, "")
            now[0] = 46.0
            result = commands_mgr.poll_accel_calibration_level()

        assert result is not None
        assert result[0] is False
        error = result[1]
        assert "45.0 seconds" in error

    def test_level_calibration_stops_after_the_configured_retry_limit(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """Repeated temporary rejections do not cause unbounded command retries."""
        mock_master, mock_conn_mgr = mock_connected_master
        temporary_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
        temporary_ack.result = mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED
        max_retries = FlightControllerCommands.LEVEL_CALIBRATION_MAX_RETRIES
        mock_master.recv_match.side_effect = [
            message for _ in range(max_retries + 1) for message in (temporary_ack, None, None)
        ]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        now = [0.0]
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
            assert commands_mgr.start_accel_calibration_level() == (True, "")
            result = None
            for retry_number in range(max_retries + 1):
                assert commands_mgr.poll_accel_calibration_level() is None
                now[0] += 0.6
                result = commands_mgr.poll_accel_calibration_level()
                if retry_number < max_retries:
                    assert result is None
                    now[0] += FlightControllerCommands.LEVEL_CALIBRATION_RETRY_DELAY
                    assert commands_mgr.poll_accel_calibration_level() is None

        assert result == (False, "Command temporarily rejected")
        assert mock_master.mav.command_long_send.call_count == max_retries + 1

    def test_failed_ack_collects_statustext_queued_after_it(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """A failed ACK remains pending briefly so a following STATUSTEXT can explain it."""
        mock_master, mock_conn_mgr = mock_connected_master
        failed_ack = MagicMock(command=mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION)
        failed_ack.result = mavutil.mavlink.MAV_RESULT_FAILED
        status_text = MagicMock()
        status_text.get_type.return_value = "STATUSTEXT"
        status_text.text = b"Disarm to allow calibration"
        mock_master.recv_match.side_effect = [failed_ack, status_text, None, None]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)
        now = [0.0]

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
            assert commands_mgr.start_accel_calibration_level() == (True, "")
            assert commands_mgr.poll_accel_calibration_level() is None
            now[0] = 0.6
            result = commands_mgr.poll_accel_calibration_level()

        assert result == (False, "Command failed: Disarm to allow calibration")

    def test_level_accelerometer_calibration_fails_without_connection(self) -> None:
        """
        Level calibration fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: User starts level calibration
        THEN: The method returns a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_level()

        assert success is False
        assert "connection" in error.lower()

    def test_level_accelerometer_calibration_reports_backend_failure(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        A rejected level calibration surfaces the acknowledgement failure.

        GIVEN: A connected flight controller that rejects the level command
        WHEN: User starts level calibration
        THEN: The method reports failure with the backend error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.mav.command_long_send.side_effect = RuntimeError("link down")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.start_accel_calibration_level()

        assert success is False
        assert "link down" in error

    def test_full_accelerometer_calibration_reports_send_error(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        A transport error while starting full calibration is surfaced cleanly.

        GIVEN: A connected flight controller whose link raises on send
        WHEN: User starts the full 6-position calibration
        THEN: The method returns failure with the transport error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.mav.command_long_send.side_effect = ConnectionError("link down")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.send_accel_calibration_full_start()

        assert success is False
        assert error == "Failed to send full accelerometer calibration command: link down"

    def test_poll_accel_cal_vehicle_pos_ignores_unrelated_messages(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling ignores COMMAND_LONG messages that are not position requests.

        GIVEN: A COMMAND_LONG that is not a MAV_CMD_ACCELCAL_VEHICLE_POS request
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: No position is returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_msg = MagicMock()
        mock_msg.command = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
        # Return the unrelated message once, then None to terminate the drain loop
        mock_master.recv_match.side_effect = [mock_msg, None]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_returns_none_when_no_message_waiting(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling returns None when the flight controller has sent nothing.

        GIVEN: A non-blocking poll that finds no message
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: None is returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_swallows_transport_exceptions(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        A transient link error during polling never propagates to the UI loop.

        GIVEN: A poll whose recv_match raises a transport error
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: None is returned instead of raising
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.side_effect = ConnectionError("socket reset")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_drains_duplicate_messages(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Polling drains all duplicate position messages and returns only the latest.

        GIVEN: ArduPilot sends the same position request multiple times (every second while waiting)
        WHEN: poll_accel_cal_vehicle_pos is called
        THEN: All stale duplicates are consumed and only the latest position is returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        # Simulate FC sending LEVEL position 3 times, then nothing
        msg1 = MagicMock()
        msg1.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        msg1.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        msg2 = MagicMock()
        msg2.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        msg2.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        msg3 = MagicMock()
        msg3.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        msg3.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        mock_master.recv_match.side_effect = [msg1, msg2, msg3, None]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        result = commands_mgr.poll_accel_cal_vehicle_pos()

        # Should drain all 3 duplicates and return the position once
        assert result == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        # Next poll should return None (queue is drained)
        mock_master.recv_match.side_effect = [None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

    def test_poll_accel_cal_vehicle_pos_suppresses_stale_position_after_confirmation(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling returns None when the FC re-sends the already-confirmed position.

        GIVEN: A position was already returned to the caller (user confirmed it)
        WHEN: poll_accel_cal_vehicle_pos is called and the FC sends the same position again
        THEN: None is returned so the UI does not re-enable Continue for the same orientation

        This is the core fix for #1801: after the user confirms LEVEL, ArduPilot keeps
        sending LEVEL every second.  Without deduplication the UI would immediately
        re-show the LEVEL instruction; with it, polling returns None until the FC
        advances to the next position.
        """
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        level_msg = MagicMock()
        level_msg.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        level_msg.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL

        # First poll: FC sends LEVEL → caller receives LEVEL and confirms it
        mock_master.recv_match.side_effect = [level_msg, None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL

        # Second poll: FC re-sends stale LEVEL while waiting → should be suppressed
        mock_master.recv_match.side_effect = [level_msg, None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() is None

        # Third poll: FC advances to the next position → new value must be returned
        left_msg = MagicMock()
        left_msg.command = mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        left_msg.param1 = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT
        mock_master.recv_match.side_effect = [left_msg, None]
        assert commands_mgr.poll_accel_cal_vehicle_pos() == mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT

    def test_user_can_confirm_accelerometer_calibration_position(
        self, mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        User confirmation of a position is sent back to the flight controller.

        GIVEN: A connected flight controller mid full calibration
        WHEN: confirm_accel_vehicle_pos is called with a position
        THEN: MAV_CMD_ACCELCAL_VEHICLE_POS is sent with that position in param1
        """
        mock_master, mock_conn_mgr = mock_connected_master
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        with caplog.at_level("DEBUG"):
            success, error = commands_mgr.confirm_accel_vehicle_pos(mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN)
        assert caplog.messages == ["Sent ACCELCAL_VEHICLE_POS confirmation for position 4"]

        assert success is True
        assert error == ""
        args = mock_master.mav.command_long_send.call_args.args
        assert args[2] == mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS
        assert args[:4] == (
            mock_master.target_system,
            mock_master.target_component,
            mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS,
            0,
        )
        assert args[4:] == (float(mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN), 0, 0, 0, 0, 0, 0)

    def test_confirm_accelerometer_position_fails_without_connection(self) -> None:
        """
        Position confirmation fails cleanly without a connection.

        GIVEN: No flight controller connection
        WHEN: confirm_accel_vehicle_pos is called
        THEN: The method returns a clear connection error
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.confirm_accel_vehicle_pos(mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL)

        assert success is False
        assert "connection" in error.lower()

    def test_confirm_accelerometer_position_reports_send_error(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        A transport error while confirming a position is surfaced cleanly.

        GIVEN: A connected flight controller whose link raises on send
        WHEN: confirm_accel_vehicle_pos is called
        THEN: The method returns failure with the transport error message
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.mav.command_long_send.side_effect = ConnectionError("write failed")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        success, error = commands_mgr.confirm_accel_vehicle_pos(mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT)

        assert success is False
        assert error == "Failed to send position confirmation: write failed"


class TestFlightControllerCommandsResultCodes:
    """Test command result code handling."""

    def test_send_command_temporarily_rejected(self) -> None:
        """
        send_command_and_wait_ack handles TEMPORARILY_REJECTED result.

        GIVEN: Flight controller that rejects command temporarily
        WHEN: User sends command
        THEN: Should return failure
        AND: Error message should indicate temporary rejection
        """
        # Given
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED

        mock_master.recv_match.return_value = mock_ack
        mock_params_mgr = Mock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        # Then
        assert success is False
        assert "temporarily rejected" in error.lower()

    def test_send_command_unsupported(self) -> None:
        """
        send_command_and_wait_ack handles UNSUPPORTED result.

        GIVEN: Flight controller that doesn't support command
        WHEN: User sends unsupported command
        THEN: Should return failure
        AND: Error message should indicate command unsupported
        """
        # Given
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = mavutil.mavlink.MAV_RESULT_UNSUPPORTED

        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        # Then
        assert success is False
        assert "unsupported" in error.lower()

    def test_send_command_failed(self) -> None:
        """
        send_command_and_wait_ack handles FAILED result.

        GIVEN: Flight controller that reports command failure
        WHEN: User sends command
        THEN: Should return failure
        AND: Error message should indicate command failed
        """
        # Given
        mock_master = MagicMock()
        mock_ack = MagicMock()
        mock_ack.command = 999
        mock_ack.result = mavutil.mavlink.MAV_RESULT_FAILED

        mock_master.recv_match.return_value = mock_ack

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

        # Then
        assert success is False
        assert "failed" in error.lower()


class TestFlightControllerCommandsBatteryEdgeCases:
    """Test battery status edge cases and error handling."""

    def test_get_battery_status_returns_none_when_battery_monitoring_disabled(self) -> None:
        """
        get_battery_status returns None when battery monitoring is disabled.

        GIVEN: Flight controller with BATT_MONITOR=0
        WHEN: User requests battery status
        THEN: Should return None
        AND: Error message should indicate monitoring disabled
        """
        # Given: Battery monitoring disabled
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 0}

        mock_master = MagicMock()

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 0}

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_status, error = commands_mgr.get_battery_statuses()

        # Then: Should return None
        assert battery_status is None
        assert "battery monitoring is not enabled" in error.lower()

    def test_get_battery_status_returns_none_when_no_connection(self) -> None:
        """
        get_battery_status returns None when no connection available.

        GIVEN: Flight controller with no connection
        WHEN: User requests battery status
        THEN: Should return None
        AND: Error message should indicate no connection
        """
        # Given: No connection
        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = None

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_status, error = commands_mgr.get_battery_statuses()

        # Then: Should return None
        assert battery_status is None
        assert "no flight controller connection" in error.lower()

    def test_get_battery_status_handles_exception_in_telemetry(self) -> None:
        """
        get_battery_status handles exceptions during telemetry fetch.

        GIVEN: Flight controller with exception in recv_match
        WHEN: User requests battery status
        THEN: Should handle exception gracefully
        AND: Should return None with error message
        """
        # Given: Exception in telemetry
        mock_master = MagicMock()
        mock_master.recv_match.side_effect = Exception("Connection lost")

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: Get battery status
        battery_status, error = commands_mgr.get_battery_statuses()

        # Then: Should return None
        assert battery_status is None
        assert error is not None

    def test_get_battery_status_uses_cache_when_recent(self) -> None:
        """
        get_battery_status uses cached data when recent.

        GIVEN: Flight controller with recent battery status cached
        WHEN: User requests battery status but telemetry fails
        THEN: Should return cached data
        AND: Error message should be empty
        """
        # Given: Setup with working telemetry first
        mock_master = MagicMock()
        mock_battery_msg = MagicMock(id=0, voltages_ext=[0] * 4)
        mock_battery_msg.voltages = [12000]  # 12V in millivolts
        mock_battery_msg.current_battery = 1050  # 10.5A in centiamps
        mock_master.recv_match.side_effect = [mock_battery_msg, None]

        mock_params_mgr = Mock()
        mock_params_mgr.fc_parameters = {"BATT_MONITOR": 4}

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When: First call gets data successfully
        battery_status1, error1 = commands_mgr.get_battery_statuses()

        # Then: First call succeeds
        assert battery_status1 is not None
        assert error1 == ""

        # When: Second call (telemetry fails but cache is still fresh)
        mock_master.recv_match.side_effect = Exception("Connection lost")
        battery_status2, error2 = commands_mgr.get_battery_statuses()

        # Then: Should use cached data
        assert battery_status2 == battery_status1
        assert error2 == ""

    def test_send_command_exception_in_send(self) -> None:
        """
        send_command_and_wait_ack handles exception during command send.

        GIVEN: Flight controller connection that raises exception on send
        WHEN: User sends command
        THEN: Should handle exception
        AND: Should return failure with error message
        """
        # Given: Exception on command send
        mock_master = MagicMock()
        mock_master.mav.command_long_send.side_effect = Exception("Serial port error")

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        # When
        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_error") as mock_err,
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_debug") as mock_dbg,
        ):
            success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

            # Then
            assert success is False
            assert "failed to send command" in error.lower()
            mock_err.assert_not_called()
            assert error == "Failed to send command: Serial port error"
            mock_dbg.assert_called_once_with(error)

    def test_send_command_without_connection_logs_debug(self) -> None:
        """
        send_command_and_wait_ack logs debug (not error) when connection is not available.

        GIVEN: No flight controller connection (master is None)
        WHEN: send_command_and_wait_ack is called
        THEN: Should return False with connection error message
        AND: Should log at debug level rather than error level
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_params_mgr = Mock()

        commands_mgr = FlightControllerCommands(params_manager=mock_params_mgr, connection_manager=mock_conn_mgr)

        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_error") as mock_err,
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_debug") as mock_dbg,
        ):
            success, error = commands_mgr.send_command_and_wait_ack(command=999, timeout=0.5)

            assert success is False
            assert "no flight controller connection" in error.lower()
            mock_err.assert_not_called()
            assert error == "No flight controller connection available for command"
            mock_dbg.assert_called_once_with(error)

    def test_request_periodic_battery_status_ack_timeout_logs_debug_not_error(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        request_periodic_battery_status logs debug without error spam when link is silent.

        GIVEN: Flight controller connected but silent (ACK timeout on all attempts)
        WHEN: request_periodic_battery_status is called
        THEN: Should return False
        AND: Should not call logging_error on any retry attempt
        AND: Should log attempts at debug level
        """
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # 3 attempts, each attempt evaluates time_time() twice (start and timeout check)
        time_seq = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        with (
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=time_seq),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep"),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_error") as mock_err,
            patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.logging_debug") as mock_dbg,
        ):
            success, error = commands_mgr.request_periodic_battery_status()

            assert success is False
            assert "timeout" in error.lower()
            mock_err.assert_not_called()
            assert mock_dbg.call_count >= commands_mgr.BATTERY_STATUS_REQUEST_ATTEMPTS


class TestFlightControllerCommandsAccelCalibrationCancel:  # pylint: disable=too-few-public-methods
    """The backend must not invent an unsupported flight-controller cancel command."""

    def test_commands_manager_has_no_fake_mavlink_cancel_method(self) -> None:
        """Local wizard dismissal is handled by the data model, not a MAVLink command."""
        assert not hasattr(FlightControllerCommands, "cancel_accel_calibration")


class TestFlightControllerCommandsPollScaledImu:
    """Test polling SCALED_IMU accelerometer readings (hardware-free)."""

    def test_poll_scaled_imu_returns_accelerations(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Polling SCALED_IMU returns the three axis accelerations.

        GIVEN: A connected FC that has a SCALED_IMU message available
        WHEN: User polls SCALED_IMU
        THEN: The (xacc, yacc, zacc) triple is returned as floats
        """
        # Given: Connected FC with a SCALED_IMU message
        mock_master, mock_conn_mgr = mock_connected_master
        mock_msg = MagicMock()
        mock_msg.xacc, mock_msg.yacc, mock_msg.zacc = 10, -20, 1000
        mock_master.recv_match.side_effect = [mock_msg, None]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Poll SCALED_IMU
        result = commands_mgr.poll_scaled_imu()

        # Then: Triple of floats returned, correct MAVLink message type requested
        assert result == (10.0, -20.0, 1000.0)
        assert all(isinstance(v, float) for v in result)
        mock_master.recv_match.assert_called_with(type="SCALED_IMU", blocking=False)

    def test_poll_scaled_imu_returns_none_when_no_message(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Polling SCALED_IMU returns None when no message has arrived.

        GIVEN: A connected FC with no pending SCALED_IMU message
        WHEN: User polls SCALED_IMU
        THEN: None is returned
        """
        # Given: Connected FC, no message
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.return_value = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When/Then
        assert commands_mgr.poll_scaled_imu() is None

    def test_poll_scaled_imu_returns_last_message_when_buffer_has_stale_data(
        self, mock_connected_master: tuple[MagicMock, Mock]
    ) -> None:
        """
        Polling SCALED_IMU drains the buffer and returns only the most recent message.

        GIVEN: A connected FC whose receive buffer contains two stale messages followed by a fresh one
        WHEN: User polls SCALED_IMU
        THEN: The values from the last (freshest) message are returned
        """
        mock_master, mock_conn_mgr = mock_connected_master
        stale_msg = MagicMock()
        stale_msg.xacc, stale_msg.yacc, stale_msg.zacc = 0, 0, -1000
        fresh_msg = MagicMock()
        fresh_msg.xacc, fresh_msg.yacc, fresh_msg.zacc = -1000, 0, 0
        mock_master.recv_match.side_effect = [stale_msg, stale_msg, fresh_msg, None]
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        result = commands_mgr.poll_scaled_imu()

        assert result == (-1000.0, 0.0, 0.0)

    def test_poll_scaled_imu_returns_none_without_connection(self) -> None:
        """
        Polling SCALED_IMU returns None when no FC is connected.

        GIVEN: No flight controller connection
        WHEN: User polls SCALED_IMU
        THEN: None is returned
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When/Then
        assert commands_mgr.poll_scaled_imu() is None

    def test_poll_scaled_imu_returns_none_on_exception(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        Polling SCALED_IMU returns None if reading raises.

        GIVEN: A connected FC whose recv_match raises
        WHEN: User polls SCALED_IMU
        THEN: None is returned instead of propagating the exception
        """
        # Given: Connected FC that raises on recv_match
        mock_master, mock_conn_mgr = mock_connected_master
        mock_master.recv_match.side_effect = RuntimeError("decode error")
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When/Then: Swallowed, None returned
        assert commands_mgr.poll_scaled_imu() is None


class TestFlightControllerCommandsRequestScaledImu:
    """Test requesting a periodic SCALED_IMU stream (hardware-free)."""

    def test_request_scaled_imu_stream_succeeds_on_ack(
        self, mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        Requesting the SCALED_IMU stream succeeds when the FC acknowledges.

        GIVEN: A connected FC that ACKs SET_MESSAGE_INTERVAL
        WHEN: User requests the SCALED_IMU stream
        THEN: The call reports success
        AND: A SET_MESSAGE_INTERVAL command is sent
        """
        # Given: Connected FC that accepts the command
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream
        with caplog.at_level("DEBUG"):
            success, error = commands_mgr.request_scaled_imu_messages()
        assert caplog.messages == ["SCALED_IMU stream requested at 200000 µs interval"]

        # Then: Success and command sent
        assert success is True
        assert error == ""
        mock_master.mav.command_long_send.assert_called_once()

    def test_request_scaled_imu_stream_passes_requested_interval(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        The requested interval is forwarded to the FC as a command parameter.

        GIVEN: A connected FC that ACKs the command
        WHEN: User requests the stream with a custom interval
        THEN: That interval (µs) appears as param2 in the command
        """
        # Given: Connected FC that accepts the command
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream at 10 Hz (100 000 µs)
        success, _error = commands_mgr.request_scaled_imu_messages(interval_microseconds=100_000)

        # Then: Interval forwarded as param2 (args[5]: target_sys, target_comp, cmd, confirmation, param1, param2, ...)
        assert success is True
        sent_args = mock_master.mav.command_long_send.call_args.args
        assert float(sent_args[5]) == float(100_000)

    def test_request_scaled_imu_stream_fails_without_connection(self) -> None:
        """
        Requesting the SCALED_IMU stream fails gracefully with no connection.

        GIVEN: No flight controller connection
        WHEN: User requests the SCALED_IMU stream
        THEN: The call reports failure with a descriptive message
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream
        success, error = commands_mgr.request_scaled_imu_messages()

        # Then: Graceful failure
        assert success is False
        assert "connection" in error.lower()

    def test_request_scaled_imu_stream_fails_on_denied_ack(
        self, mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        Requesting the SCALED_IMU stream fails when the FC denies the command.

        GIVEN: A connected FC that NACKs SET_MESSAGE_INTERVAL
        WHEN: User requests the SCALED_IMU stream
        THEN: The call reports failure with a descriptive message
        """
        # Given: Connected FC that denies the command
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_DENIED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream
        with caplog.at_level("DEBUG"):
            success, error = commands_mgr.request_scaled_imu_messages()
        assert caplog.messages == ["Command denied", "SCALED_IMU stream request failed: Command denied"]

        # Then: Failure propagated from the denied ACK
        assert success is False
        assert "denied" in error.lower()

    def test_request_scaled_imu_stream_uses_default_interval(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        The default 200 000 µs interval is used when none is supplied.

        GIVEN: A connected FC that ACKs the command
        WHEN: User requests the stream without specifying an interval
        THEN: The default interval (200 000 µs) is sent as param2
        """
        # Given: Connected FC that accepts the command
        mock_master, mock_conn_mgr = mock_connected_master
        mock_ack = MagicMock()
        mock_ack.command = mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL
        mock_ack.result = mavutil.mavlink.MAV_RESULT_ACCEPTED
        mock_master.recv_match.return_value = mock_ack
        commands_mgr = FlightControllerCommands(params_manager=Mock(), connection_manager=mock_conn_mgr)

        # When: Request stream with default interval
        success, _error = commands_mgr.request_scaled_imu_messages()

        # Then: Default interval (200 000 µs) forwarded as param2
        assert success is True
        sent_args = mock_master.mav.command_long_send.call_args.args
        assert float(sent_args[5]) == float(200_000)


class TestReceiverTelemetryRequests:
    """Enable receiver monitoring on controllers with disabled default streams."""

    @pytest.mark.parametrize("interval", [200_000, 0])
    def test_receiver_stream_intervals_are_requested_and_restored(self, interval: int) -> None:
        """
        Request both receiver streams through actual command handling.

        GIVEN a connected controller acknowledging message interval commands,
        WHEN the monitor requests telemetry or restores defaults,
        THEN RC_CHANNELS and SYS_STATUS receive the requested interval.
        """
        master = MagicMock(target_system=1, target_component=0)
        master.recv_match.return_value = mavlink2.MAVLink_command_ack_message(
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, mavutil.mavlink.MAV_RESULT_ACCEPTED
        )
        commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=master))
        assert commands.request_rc_receiver_messages(interval) == (True, "")
        assert [call.args for call in master.mav.command_long_send.call_args_list] == [
            (1, 0, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, message_id, interval, 0, 0, 0, 0, 0)
            for message_id in (mavutil.mavlink.MAVLINK_MSG_ID_RC_CHANNELS, mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS)
        ]

    def test_rejected_channel_request_does_not_prevent_requesting_receiver_status(self) -> None:
        """
        Attempt both telemetry requests even if one fails.

        GIVEN a controller rejecting RC_CHANNELS but accepting SYS_STATUS,
        WHEN receiver streams are requested,
        THEN status is still requested and the failure is reported.
        """
        master = MagicMock(target_system=1, target_component=0)
        master.recv_match.side_effect = [
            mavlink2.MAVLink_command_ack_message(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, result)
            for result in (mavutil.mavlink.MAV_RESULT_DENIED, mavutil.mavlink.MAV_RESULT_ACCEPTED)
        ]
        commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=master))
        success, error = commands.request_rc_receiver_messages()
        assert not success
        assert error
        assert master.mav.command_long_send.call_count == 2

    def test_disconnected_receiver_cannot_request_streams(self) -> None:
        """Given no connection, requesting receiver streams reports failure without I/O."""
        commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=None))
        success, error = commands.request_rc_receiver_messages()
        assert not success
        assert error


class TestMultipleBatteryTelemetry:
    """Keep each battery's readings independent through actual MAVLink message handling."""

    @staticmethod
    def _battery_message(battery_id: int, voltage: int, current: int = 210) -> mavlink2.MAVLink_battery_status_message:
        return mavlink2.MAVLink_battery_status_message(battery_id, 0, 0, 32767, [voltage] + [65535] * 9, current, -1, -1, -1)

    def test_cached_battery_packets_expire_independently_without_refreshing_their_age(self) -> None:
        """
        Preserve per-battery freshness when other readers consume telemetry.

        GIVEN two batteries parsed by another receiver at different times,
        WHEN the battery cache is read repeatedly and the older sample expires,
        THEN only the fresh battery remains and reconnecting clears both readings.
        """
        master = mavutil.mavfile(None, "battery-test", input=False)
        master.recv_match = Mock(return_value=None)
        connection = Mock(master=master)
        commands = FlightControllerCommands(
            params_manager=Mock(fc_parameters={"BATT_MONITOR": 4, "BATT2_MONITOR": 4}), connection_manager=connection
        )
        with patch("pymavlink.mavutil.time.time", return_value=100):
            master.post_message(self._battery_message(0, 12400))
        with patch("pymavlink.mavutil.time.time", return_value=101):
            master.post_message(self._battery_message(1, 24800))
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", return_value=101):
            assert commands.get_battery_statuses() == ({0: (12.4, 2.1), 1: (24.8, 2.1)}, "")
            assert commands.get_battery_statuses() == ({0: (12.4, 2.1), 1: (24.8, 2.1)}, "")
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time",
            return_value=100 + commands.BATTERY_STATUS_CACHE_TIME,
        ):
            assert commands.get_battery_statuses() == ({1: (24.8, 2.1)}, "")
        connection.master = mavutil.mavfile(None, "replacement-battery-test", input=False)
        connection.master.recv_match = Mock(return_value=None)
        readings, error = commands.get_battery_statuses()
        assert readings is None
        assert error

    def test_user_receives_all_batteries_through_real_pymavlink_reader(self) -> None:
        """Given queued battery messages, reading telemetry returns every ID with the latest values."""
        master = mavutil.mavfile(None, "battery-test", input=False)
        master.recv_msg = Mock(
            side_effect=[
                self._battery_message(0, 12400),
                self._battery_message(1, 24800, 350),
                self._battery_message(0, 12300),
                None,
            ]
        )
        commands = FlightControllerCommands(
            params_manager=Mock(fc_parameters={"BATT_MONITOR": 4, "BATT2_MONITOR": 4}),
            connection_manager=Mock(master=master),
        )

        readings, error = commands.get_battery_statuses()

        assert error == ""
        assert readings == {0: (12.3, 2.1), 1: (24.8, 3.5)}

    def test_user_can_monitor_second_battery_with_first_monitor_disabled(self) -> None:
        """Given only battery 2 is enabled, its telemetry remains available."""
        master = Mock()
        master.recv_match.side_effect = [self._battery_message(1, 24800), None]
        commands = FlightControllerCommands(
            params_manager=Mock(fc_parameters={"BATT_MONITOR": 0, "BATT2_MONITOR": 4}),
            connection_manager=Mock(master=master),
        )

        readings, error = commands.get_battery_statuses()

        assert error == ""
        assert readings == {1: (24.8, 2.1)}

    def test_stale_battery_expires_while_another_continues_reporting(self) -> None:
        """Given independent streams, refreshing battery 2 does not extend battery 1's lifetime."""
        master = Mock()
        commands = FlightControllerCommands(
            params_manager=Mock(fc_parameters={"BATT_MONITOR": 4, "BATT2_MONITOR": 4}),
            connection_manager=Mock(master=master),
        )
        master.recv_match.side_effect = [self._battery_message(0, 12400), self._battery_message(1, 24800), None]
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", return_value=100):
            commands.get_battery_statuses()
        master.recv_match.side_effect = [self._battery_message(1, 24700), None]
        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time",
            return_value=100 + commands.BATTERY_STATUS_CACHE_TIME,
        ):
            readings, error = commands.get_battery_statuses()

        assert error == ""
        assert readings == {1: (24.7, 2.1)}

    def test_reconnection_does_not_reuse_previous_vehicle_readings(self) -> None:
        """Given a new connection without telemetry, cached readings from the previous vehicle disappear."""
        master = Mock()
        master.recv_match.side_effect = [self._battery_message(0, 12400), None]
        connection = Mock(master=master)
        commands = FlightControllerCommands(
            params_manager=Mock(fc_parameters={"BATT_MONITOR": 4}),
            connection_manager=connection,
        )
        commands.get_battery_statuses()
        connection.master = Mock()
        connection.master.recv_match.return_value = None

        readings, error = commands.get_battery_statuses()

        assert readings is None
        assert error

    def test_cell_voltages_are_summed_and_unavailable_readings_stay_unknown(self) -> None:
        """Given cell telemetry or unavailable fields, report pack voltage and retain unknown measurements."""
        message = self._battery_message(0, 4200, -1)
        message.voltages = [4200, 4150] + [65535] * 8
        message.voltages_ext = [4100, 1, 65535, 0]
        master = Mock()
        master.recv_match.side_effect = [message, self._battery_message(1, 65535), None]
        commands = FlightControllerCommands(
            params_manager=Mock(fc_parameters={"BATT_MONITOR": 4, "BATT2_MONITOR": 4}),
            connection_manager=Mock(master=master),
        )

        readings, error = commands.get_battery_statuses()

        assert error == ""
        assert readings is not None
        assert readings[0][0] == pytest.approx(12.451)
        assert isnan(readings[0][1])
        assert isnan(readings[1][0])

    @pytest.mark.parametrize("pack_millivolts", [65534, 65535, 65536])
    def test_user_can_read_pack_voltage_across_the_cell_sentinel_value(self, pack_millivolts: int) -> None:
        """
        Valid pack totals remain readable near the cell sentinel value.

        GIVEN: A pack total encoded across valid voltage fields near 65.535 V.
        WHEN: The user reads battery telemetry.
        THEN: The sum remains a valid voltage, even when it equals the cell sentinel.
        """
        message = self._battery_message(0, 65534)
        message.voltages = [65534, pack_millivolts - 65534] + [65535] * 8
        master = Mock()
        master.recv_match.side_effect = [message, None]
        commands = FlightControllerCommands(
            params_manager=Mock(fc_parameters={"BATT_MONITOR": 4}), connection_manager=Mock(master=master)
        )

        readings, error = commands.get_battery_statuses()

        assert error == ""
        assert readings is not None
        assert readings[0][0] == pytest.approx(pack_millivolts / 1000)


@pytest.mark.parametrize(
    ("method", "arguments", "command", "message"),
    [
        (
            "test_motor",
            (2, "C", 7, 12, 4),
            mavlink2.MAV_CMD_DO_MOTOR_TEST,
            "Motor test command acknowledged: Motor C on output 7 at 12% thrust for 4 seconds",
        ),
        (
            "test_motors_in_sequence",
            (2, 3, 12, 4),
            mavlink2.MAV_CMD_DO_MOTOR_TEST,
            "Sequential motor test command confirmed at 12% for 4 seconds per motor",
        ),
        ("stop_all_motors", (), mavlink2.MAV_CMD_DO_MOTOR_TEST, "Motor stop command confirmed"),
        (
            "reset_all_parameters_to_default",
            (),
            mavlink2.MAV_CMD_PREFLIGHT_STORAGE,
            "Parameter reset to defaults command confirmed by flight controller",
        ),
        ("start_compass_calibration", (), mavlink2.MAV_CMD_DO_START_MAG_CAL, "Compass calibration start command confirmed"),
        ("cancel_compass_calibration", (), mavlink2.MAV_CMD_DO_CANCEL_MAG_CAL, "Compass calibration cancel command confirmed"),
        (
            "start_accel_calibration_simple",
            (),
            mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION,
            "Simple accelerometer calibration completed successfully",
        ),
        (
            "send_accel_calibration_full_start",
            (),
            mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION,
            "Full accelerometer calibration start command sent",
        ),
    ],
)
def test_successful_command_diagnostics_preserve_the_requested_operation(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    mock_connected_master: tuple[MagicMock, Mock],
    method: str,
    arguments: tuple,
    command: int,
    message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Diagnostic identifies the operation and its requested settings.

    GIVEN: The controller acknowledges an operator's command
    WHEN: A motor, parameter reset or calibration operation completes
    THEN: The diagnostic identifies the operation and its requested settings
    """
    master, connection = mock_connected_master
    ack = mavlink2.MAVLink_command_ack_message(command, mavlink2.MAV_RESULT_ACCEPTED)
    master.recv_match.side_effect = [None, ack]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with caplog.at_level("INFO"):
        assert getattr(commands, method)(*arguments) == (True, "")
    assert caplog.messages == [message]


@pytest.mark.parametrize(
    ("method", "arguments", "reason"),
    [
        ("reset_all_parameters_to_default", (), "parameter reset"),
        ("test_motor", (0, "A", 1, 10, 2), "motor test"),
        ("test_all_motors", (4, 10, 2), "motor test"),
        ("test_motors_in_sequence", (1, 4, 10, 2), "motor test"),
        ("stop_all_motors", (), "motor stop"),
        ("start_accel_calibration_simple", (), "accelerometer calibration"),
        ("start_accel_calibration_level", (), "level calibration"),
        ("send_accel_calibration_full_start", (), "full accelerometer calibration"),
        ("start_compass_calibration", (), "compass calibration"),
        ("request_scaled_imu_messages", (), "SCALED_IMU stream request"),
        ("request_periodic_battery_status", (), "battery status request"),
    ],
)
def test_disconnected_commands_explain_the_operation_that_requires_a_connection(
    method: str,
    arguments: tuple,
    reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    It fails with stable operation-specific guidance and the same diagnostic.

    GIVEN: The flight controller is disconnected
    WHEN: The operator requests a command
    THEN: It fails with stable operation-specific guidance and the same diagnostic
    """
    connection = Mock(master=None)
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    message = f"No flight controller connection available for {reason}"
    with caplog.at_level("DEBUG"):
        assert getattr(commands, method)(*arguments) == (False, message)
    assert caplog.messages == [message]


@pytest.mark.parametrize(
    ("method", "arguments", "command", "prefix"),
    [
        ("test_motor", (2, "C", 7, 12, 4), mavlink2.MAV_CMD_DO_MOTOR_TEST, "Motor test command failed"),
        ("test_motors_in_sequence", (2, 3, 12, 4), mavlink2.MAV_CMD_DO_MOTOR_TEST, "Sequential motor test command failed"),
        ("stop_all_motors", (), mavlink2.MAV_CMD_DO_MOTOR_TEST, "Motor stop command failed"),
        ("reset_all_parameters_to_default", (), mavlink2.MAV_CMD_PREFLIGHT_STORAGE, "Parameter reset command failed"),
        ("start_compass_calibration", (), mavlink2.MAV_CMD_DO_START_MAG_CAL, "Compass calibration start failed"),
        ("cancel_compass_calibration", (), mavlink2.MAV_CMD_DO_CANCEL_MAG_CAL, "Compass calibration cancel failed"),
    ],
)
def test_rejected_commands_report_the_requested_operation_and_preserve_cached_parameters(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    mock_connected_master: tuple[MagicMock, Mock],
    method: str,
    arguments: tuple,
    command: int,
    prefix: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Preserve the operation and controller rejection in error guidance.

    GIVEN: A controller that denies an operator's command
    WHEN: The acknowledgement arrives
    THEN: The result and diagnostic explain the rejection and cached parameters stay intact
    """
    master, connection = mock_connected_master
    ack = mavlink2.MAVLink_command_ack_message(command, mavlink2.MAV_RESULT_DENIED)
    replies = iter([None, ack])
    master.recv_match.side_effect = lambda **_kwargs: next(replies, None)
    parameters = Mock(fc_parameters={"KEEP": 42})
    commands = FlightControllerCommands(params_manager=parameters, connection_manager=connection)
    with (
        patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=itertools.count(0, 0.1)
        ),
        caplog.at_level("ERROR"),
    ):
        assert getattr(commands, method)(*arguments) == (False, f"{prefix}: Command denied")
    assert caplog.messages == ["Command denied", f"{prefix}: Command denied"]
    assert parameters.fc_parameters == {"KEEP": 42}


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (2, "Command denied"),
        (3, "Command unsupported"),
        (4, "Command failed"),
        (99, "Command acknowledgment with unknown result: 99"),
    ],
)
def test_level_failure_keeps_the_first_terminal_result_and_decodes_all_status_text(
    mock_connected_master: tuple[MagicMock, Mock],
    result: int,
    message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Preserve firmware detail across unrelated messages and duplicate terminal acknowledgements.

    GIVEN: An active level calibration with progress, status text and a failed acknowledgement
    WHEN: A different terminal acknowledgement follows and the text grace window expires
    THEN: The first failure and cleaned firmware details are reported and calibration stops
    """
    master, connection = mock_connected_master
    unrelated = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_DO_MOTOR_TEST, 0)
    progress = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, 5)
    status = Mock(text=b"  Hold \xff still  \x00", get_type=Mock(return_value="STATUSTEXT"))
    second_status = Mock(text="Check gyro X\x00", get_type=Mock(return_value="STATUSTEXT"))
    failure = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, result)
    duplicate = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, 2)
    master.recv_match.side_effect = [unrelated, progress, status, second_status, failure, duplicate, None, None]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]),
        caplog.at_level("ERROR"),
    ):
        assert commands.start_accel_calibration_level() == (True, "")
        assert commands.poll_accel_calibration_level() is None
        now[0] = 0.5
        expected = f"{message}: Hold � still; Check gyro X"
        assert commands.poll_accel_calibration_level() == (False, expected)
        assert commands.poll_accel_calibration_level() is None
    assert caplog.messages == [f"Level calibration failed: {expected}"]
    master.recv_match.assert_called_with(type=["COMMAND_ACK", "STATUSTEXT"], blocking=False)


@pytest.mark.parametrize(("timestamp", "available"), [(0, False), (1, True), (None, False), ("unknown", False)])
def test_battery_cache_uses_original_valid_receipt_times_and_skips_missing_primary_battery(
    mock_connected_master: tuple[MagicMock, Mock],
    timestamp: object,
    available: bool,
) -> None:
    """
    Recover a secondary battery from the generic pymavlink cache.

    GIVEN: Both monitors are enabled but only the secondary battery was parsed elsewhere
    WHEN: Cached telemetry is read with a valid or unavailable receipt timestamp
    THEN: Missing primary data does not hide the secondary battery and invalid times are rejected
    """
    master, connection = mock_connected_master
    battery = mavlink2.MAVLink_battery_status_message(1, 0, 0, 32767, [24800] + [65535] * 9, 210, -1, -1, -1)
    battery._timestamp = timestamp  # pylint: disable=protected-access
    master.messages = {"BATTERY_STATUS": battery}
    master.recv_match.return_value = None
    commands = FlightControllerCommands(
        params_manager=Mock(fc_parameters={"BATT_MONITOR": 4, "BATT2_MONITOR": 4}), connection_manager=connection
    )
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", return_value=1):
        assert commands.get_battery_statuses() == (
            ({1: (24.8, 2.1)}, "") if available else (None, "Battery status not available from telemetry")
        )
    master.recv_match.assert_called_once_with(type="BATTERY_STATUS", blocking=False, timeout=commands.BATTERY_STATUS_TIMEOUT)


@pytest.mark.parametrize(
    ("connected", "parameters", "message"),
    [
        (False, {"BATT_MONITOR": 4}, "No flight controller connection or parameters available"),
        (True, {}, "No flight controller connection or parameters available"),
        (True, {"BATT_MONITOR": 0}, "Battery monitoring is not enabled"),
    ],
)
def test_battery_reading_explains_missing_connection_parameters_or_enabled_monitor(
    connected: bool,
    parameters: dict[str, int],
    message: str,
) -> None:
    """
    Explain the prerequisite that prevents a battery measurement.

    GIVEN: A missing connection, parameter cache or enabled battery monitor
    WHEN: The operator requests battery readings
    THEN: The returned guidance identifies the missing prerequisite
    """
    connection = Mock(master=Mock() if connected else None)
    commands = FlightControllerCommands(params_manager=Mock(fc_parameters=parameters), connection_manager=connection)
    assert commands.get_battery_statuses() == (None, message)


@pytest.mark.parametrize(("vehicle", "expected"), [("ArduPlane", (4, 3)), ("ArduCopter", (1, 2))])
def test_motor_frame_selection_uses_the_discovered_vehicle_type(vehicle: str, expected: tuple[int, int]) -> None:
    """
    Prefer quadplane frame parameters only for the plane vehicle type.

    GIVEN: Both copter and quadplane frame groups in the parameter cache
    WHEN: The motor test asks for frame information
    THEN: Discovered vehicle type selects the appropriate group
    """
    parameters = Mock(fc_parameters={"FRAME_CLASS": 1, "FRAME_TYPE": 2, "Q_FRAME_CLASS": 4, "Q_FRAME_TYPE": 3})
    connection = Mock(info=SimpleNamespace(vehicle_type=vehicle))
    commands = FlightControllerCommands(params_manager=parameters, connection_manager=connection)
    assert commands.get_frame_info() == expected


@pytest.mark.parametrize(
    ("operation", "arguments", "boundary", "result", "diagnostic"),
    [
        ("poll_scaled_imu", (), "recv_match", None, "Exception while polling SCALED_IMU: link down"),
        ("poll_accel_cal_vehicle_pos", (), "recv_match", None, "Exception while polling ACCELCAL_VEHICLE_POS: link down"),
        (
            "get_battery_statuses",
            (),
            "recv_match",
            (None, "Battery status not available from telemetry"),
            "Failed to get battery statuses from telemetry: link down",
        ),
        (
            "confirm_accel_vehicle_pos",
            (3,),
            "send",
            (False, "Failed to send position confirmation: link down"),
            "Failed to send position confirmation: link down",
        ),
        (
            "send_accel_calibration_full_start",
            (),
            "send",
            (False, "Failed to send full accelerometer calibration command: link down"),
            "Failed to send full accelerometer calibration command: link down",
        ),
        (
            "start_accel_calibration_level",
            (),
            "send",
            (False, "Failed to send level calibration command: link down"),
            "Failed to send level calibration command: link down",
        ),
    ],
)
def test_transport_failures_keep_operation_specific_diagnostics_without_reaching_the_gui(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    mock_connected_master: tuple[MagicMock, Mock],
    operation: str,
    arguments: tuple,
    boundary: str,
    result: object,
    diagnostic: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Turn transport errors into safe results and useful operator diagnostics.

    GIVEN: The MAVLink transport fails while reading or sending
    WHEN: A calibration or battery operation runs
    THEN: The exception is contained and the diagnostic retains the operation and original reason
    """
    master, connection = mock_connected_master
    failing_io = master.recv_match if boundary == "recv_match" else master.mav.command_long_send
    failing_io.side_effect = OSError("link down")
    commands = FlightControllerCommands(params_manager=Mock(fc_parameters={"BATT_MONITOR": 4}), connection_manager=connection)
    with caplog.at_level("DEBUG"):
        assert getattr(commands, operation)(*arguments) == result
    assert caplog.messages == [diagnostic]


@pytest.mark.parametrize(
    ("operation", "ids"), [("request_scaled_imu_messages", (26,)), ("request_rc_receiver_messages", (65, 1))]
)
def test_stream_requests_preserve_default_interval_and_complete_command_payload(
    mock_connected_master: tuple[MagicMock, Mock],
    operation: str,
    ids: tuple[int, ...],
) -> None:
    """
    Request the intended telemetry streams without setting unrelated command fields.

    GIVEN: The controller acknowledges message-interval commands
    WHEN: IMU or receiver monitoring requests its default streams
    THEN: Every requested message uses a 200000-microsecond interval and zero unused parameters
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_SET_MESSAGE_INTERVAL, 0)
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    assert getattr(commands, operation)() == (True, "")
    assert [entry.args for entry in master.mav.command_long_send.call_args_list] == [
        (1, 1, mavlink2.MAV_CMD_SET_MESSAGE_INTERVAL, 0, message_id, 200000, 0, 0, 0, 0, 0) for message_id in ids
    ]


@pytest.mark.parametrize("operation", ["request_scaled_imu_messages", "request_rc_receiver_messages"])
def test_unacknowledged_monitor_stream_requests_use_the_short_gui_timeout(
    mock_connected_master: tuple[MagicMock, Mock],
    operation: str,
) -> None:
    """
    Keep unsupported stream requests from blocking the GUI for a full command timeout.

    GIVEN: A controller that never acknowledges stream-interval commands
    WHEN: Monitoring requests IMU or receiver streams
    THEN: Each failed request reports the 0.8-second acknowledgement limit
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=itertools.count()),
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep"),
    ):
        success, message = getattr(commands, operation)()
    assert success is False
    expected = "Command acknowledgment timeout after 0.8 seconds"
    assert message == (f"{expected}; {expected}" if operation == "request_rc_receiver_messages" else expected)


@pytest.mark.parametrize("failure", ["disconnect", "receive"])
def test_running_level_calibration_reports_link_failure_and_releases_its_session(
    mock_connected_master: tuple[MagicMock, Mock],
    failure: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Release a running level calibration after losing the telemetry link.

    GIVEN: Level calibration has started and the connection disappears or its read fails
    WHEN: The GUI polls for completion
    THEN: Failure explains the link problem and subsequent polls are inactive
    """
    master, connection = mock_connected_master
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    assert commands.start_accel_calibration_level() == (True, "")
    if failure == "disconnect":
        connection.master = None
        message = "No flight controller connection available"
    else:
        master.recv_match.side_effect = OSError("link down")
        message = "Failed to receive level calibration acknowledgment: link down"
    with caplog.at_level("ERROR"):
        assert commands.poll_accel_calibration_level() == (False, message)
        assert commands.poll_accel_calibration_level() is None
    assert caplog.messages == [f"Level calibration failed: {message}"]


def test_level_restart_waits_for_the_exact_abandoned_command_deadline(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Ignore unrelated or in-progress acknowledgements during abandoned calibration cleanup.

    GIVEN: A level calibration is abandoned while the controller may still be working
    WHEN: Unrelated and in-progress ACKs arrive before its deadline
    THEN: A new calibration stays blocked until the original deadline and cleanup reads never block
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_level() == (True, "")
        commands.abort_level_calibration()
        unrelated = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_DO_MOTOR_TEST, 0)
        progress = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, 5)
        status = mavlink2.MAVLink_statustext_message(6, b"Calibrating")
        master.recv_match.side_effect = [unrelated, progress, status, None]
        now[0] = 44.999
        assert commands.start_accel_calibration_level() == (
            False,
            "The previous level calibration is still finishing; try again shortly",
        )
        master.recv_match.side_effect = None
        now[0] = 45.0
        assert commands.start_accel_calibration_level() == (True, "")
    assert master.mav.command_long_send.call_count == 2
    assert all(
        entry.kwargs == {"type": ["COMMAND_ACK", "STATUSTEXT"], "blocking": False}
        for entry in master.recv_match.call_args_list
    )


def test_active_level_calibration_rejects_a_concurrent_start_until_its_exact_ack_deadline(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Prevent overlapping level calibration commands while the first is active.

    GIVEN: A level calibration is awaiting acknowledgement
    WHEN: The operator tries again before its deadline and then polls at that deadline
    THEN: The duplicate start is rejected and the active operation times out precisely
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_level() == (True, "")
        assert commands.start_accel_calibration_level() == (False, "A level calibration is already in progress")
        now[0] = 45.0
        assert commands.poll_accel_calibration_level() == (False, "Command acknowledgment timeout after 45.0 seconds")
    master.mav.command_long_send.assert_called_once()


@pytest.mark.parametrize("accepted", [True, False])
@pytest.mark.parametrize("interval", [None, 250000])
def test_battery_stream_retries_preserve_payload_interval_and_each_acknowledgement_diagnostic(
    mock_connected_master: tuple[MagicMock, Mock],
    accepted: bool,
    interval: int | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Retain battery stream retry results and the requested reporting interval.

    GIVEN: A controller consistently accepts or denies battery telemetry requests
    WHEN: The monitor requests its default or a custom interval
    THEN: Three complete requests and their diagnostics retain the chosen interval and result
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = mavlink2.MAVLink_command_ack_message(
        mavlink2.MAV_CMD_SET_MESSAGE_INTERVAL, mavlink2.MAV_RESULT_ACCEPTED if accepted else mavlink2.MAV_RESULT_DENIED
    )
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    expected_interval = 1000000 if interval is None else interval
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep") as sleep,
        caplog.at_level("DEBUG"),
    ):
        result = (
            commands.request_periodic_battery_status()
            if interval is None
            else commands.request_periodic_battery_status(interval)
        )
    final_message = (
        f"Periodic BATTERY_STATUS messages confirmed every {expected_interval} microseconds"
        if accepted
        else "Failed to request periodic battery status: Command denied"
    )
    assert result == ((True, "") if accepted else (False, final_message))
    expected_header = (1, 1, mavlink2.MAV_CMD_SET_MESSAGE_INTERVAL, 0)
    expected_parameters = (mavlink2.MAVLINK_MSG_ID_BATTERY_STATUS, expected_interval, *(0,) * 5)
    assert [entry.args for entry in master.mav.command_long_send.call_args_list] == [expected_header + expected_parameters] * 3
    expected_logs = []
    for attempt in (1, 2, 3):
        if accepted:
            expected_logs.append(f"BATTERY_STATUS stream request attempt {attempt} confirmed")
        else:
            expected_logs.extend(["Command denied", f"BATTERY_STATUS stream request attempt {attempt} failed: Command denied"])
    assert caplog.messages == [*expected_logs, final_message]
    assert [entry.args for entry in sleep.call_args_list] == [(0.3,)] * 3 + ([(1.0,)] if accepted else [])


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (0, ""),
        (1, "Command temporarily rejected"),
        (2, "Command denied"),
        (3, "Command unsupported"),
        (4, "Command failed"),
        (99, "Command acknowledgment with unknown result: 99"),
    ],
)
def test_command_results_preserve_the_controller_status_in_returned_and_logged_guidance(
    mock_connected_master: tuple[MagicMock, Mock],
    result: int,
    message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Distinguish every terminal command acknowledgement result.

    GIVEN: A controller returns an accepted, rejected, failed or unknown result
    WHEN: A command waits for its acknowledgement
    THEN: The result and diagnostic preserve the exact controller status
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = mavlink2.MAVLink_command_ack_message(999, result)
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with caplog.at_level("DEBUG"):
        assert commands.send_command_and_wait_ack(999) == (result == 0, message)
    assert caplog.messages == ([] if result == 0 else [message])


def test_failed_command_stops_receiving_at_the_exact_status_text_grace_deadline(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Stop a rejected command's receive window at its exact grace deadline.

    GIVEN: A denied command followed by firmware status text
    WHEN: The clock reaches the text grace deadline
    THEN: The first failure and its firmware detail are returned without another receive
    """
    master, connection = mock_connected_master
    now = [0.0]
    responses = iter(
        [
            mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, 2),
            mavlink2.MAVLink_statustext_message(6, b"Disarm first"),
        ]
    )

    def receive(**_kwargs: object) -> object:
        response = next(responses)
        if response.get_type() == "STATUSTEXT":
            now[0] = 0.5
        return response

    master.recv_match.side_effect = receive
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_simple() == (False, "Command denied: Disarm first")
    assert master.recv_match.call_count == 2


def test_parameter_reset_uses_the_full_ten_second_acknowledgement_window(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Allow the controller's longer storage-reset acknowledgement window.

    GIVEN: A controller sends no parameter-reset acknowledgement
    WHEN: The ten-second reset window elapses
    THEN: The failure reports that window rather than the shorter generic command limit
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=itertools.count()),
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep"),
    ):
        assert commands.reset_all_parameters_to_default() == (
            False,
            "Parameter reset command failed: Command acknowledgment timeout after 10.0 seconds",
        )


def test_level_retry_waits_through_cooldown_then_reports_a_failed_retry_send(
    mock_connected_master: tuple[MagicMock, Mock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Keep the cooldown and release calibration if its retry cannot be sent.

    GIVEN: The controller temporarily rejects level trim
    WHEN: Polling continues before cooldown and the eventual retry write fails
    THEN: No early retry is sent, the write failure is reported and the session becomes inactive
    """
    master, connection = mock_connected_master
    rejected = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, 1)
    master.recv_match.side_effect = itertools.chain([rejected], itertools.repeat(None))
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    now = [0.0]
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]),
        caplog.at_level("INFO"),
    ):
        assert commands.start_accel_calibration_level() == (True, "")
        assert commands.poll_accel_calibration_level() is None
        now[0] = 0.5
        assert commands.poll_accel_calibration_level() is None
        now[0] = 0.6
        assert commands.poll_accel_calibration_level() is None
        master.mav.command_long_send.assert_called_once()
        now[0] = 5.5
        master.mav.command_long_send.side_effect = OSError("link down")
        assert commands.poll_accel_calibration_level() == (False, "Failed to send level calibration command: link down")
        assert commands.poll_accel_calibration_level() is None
    assert caplog.messages == [
        "Level calibration was temporarily rejected; retrying after the calibration cooldown.",
        "Failed to send level calibration command: link down",
        "Level calibration failed: Failed to send level calibration command: link down",
    ]


def test_default_command_payload_and_five_second_timeout_remain_stable(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Preserve zero command parameters and the documented default response window.

    GIVEN: A connected controller sends no acknowledgement
    WHEN: A caller sends a command without optional arguments
    THEN: All seven parameters are zero and reception stops at exactly five seconds.
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=[0.0, 0.0, 5.0]),
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep") as pause,
    ):
        assert commands.send_command_and_wait_ack(999) == (False, "Command acknowledgment timeout after 5.0 seconds")
    assert master.mav.command_long_send.call_args.args == (master.target_system, master.target_component, 999, *(0,) * 8)
    master.recv_match.assert_called_once_with(type="COMMAND_ACK", blocking=False)
    pause.assert_called_once_with(0.1)


@pytest.mark.parametrize("result", [1, 3, 99])
def test_calibration_failure_keeps_multiple_firmware_details_until_the_grace_deadline(
    mock_connected_master: tuple[MagicMock, Mock], result: int
) -> None:
    """
    Preserve all firmware explanations after a failed calibration acknowledgement.

    GIVEN: A failed command followed by two firmware explanations
    WHEN: The short text grace period expires
    THEN: The first failure and both details are returned in their original order.
    """
    master, connection = mock_connected_master
    now = [0.0]
    responses = iter(
        [
            mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, result),
            mavlink2.MAVLink_statustext_message(6, b"Disarm first"),
            mavlink2.MAVLink_statustext_message(6, b"Gyro busy"),
        ]
    )

    def receive(**_kwargs: object) -> object:
        message = next(responses)
        if message.get_type() == "STATUSTEXT" and message.text == "Gyro busy":
            now[0] = 0.5
        return message

    master.recv_match.side_effect = receive
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    reason = {
        1: "Command temporarily rejected",
        3: "Command unsupported",
        99: "Command acknowledgment with unknown result: 99",
    }[result]
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_simple() == (False, f"{reason}: Disarm first; Gyro busy")
    assert master.recv_match.call_count == 3


@pytest.mark.parametrize("progress", [0, 1])
def test_generic_command_progress_logs_only_available_positive_percentages(
    mock_connected_master: tuple[MagicMock, Mock], progress: int, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Show the first positive progress report without inventing a zero-percent update.

    GIVEN: A real in-progress acknowledgement followed by acceptance
    WHEN: The command waits for its terminal acknowledgement
    THEN: One percent is logged as progress and zero is treated as unavailable.
    """
    master, connection = mock_connected_master
    master.recv_match.side_effect = [
        mavlink2.MAVLink_command_ack_message(999, mavlink2.MAV_RESULT_IN_PROGRESS, progress=progress),
        mavlink2.MAVLink_command_ack_message(999, mavlink2.MAV_RESULT_ACCEPTED),
    ]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with caplog.at_level("DEBUG"):
        assert commands.send_command_and_wait_ack(999) == (True, "")
    assert caplog.messages == (["Command in progress: 1%"] if progress else [])


def test_compass_start_bounds_stale_reply_drain_before_sending_the_new_command(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Bound the work spent clearing a busy command-response backlog.

    GIVEN: Old acknowledgements continuously arrive before a compass start
    WHEN: The new start command is sent
    THEN: At most 1000 stale replies are consumed before the new acknowledgement is read.
    """
    master, connection = mock_connected_master
    stale_reads = []
    acknowledgement = mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_DO_START_MAG_CAL, 0)

    def receive(**_kwargs: object) -> object:
        if not master.mav.command_long_send.called:
            stale_reads.append(acknowledgement)
        return acknowledgement

    master.recv_match.side_effect = receive
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    assert commands.start_compass_calibration() == (True, "")
    assert len(stale_reads) == 1000
    assert master.recv_match.call_count == 1001


def test_compass_poll_keeps_updates_after_periodic_packets_and_firmware_status(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Drain all queued calibration updates despite interleaved periodic traffic.

    GIVEN: A heartbeat and firmware status precede a compass progress update
    WHEN: The compass monitor polls
    THEN: Both the status and later progress update remain visible.
    """
    master, connection = mock_connected_master
    master.recv_msg.side_effect = [
        mavlink2.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3),
        mavlink2.MAVLink_statustext_message(6, b"Mag(0) rotate vehicle"),
        mavlink2.MAVLink_mag_cal_report_message(0, 1, 4, 1, 0.3, *([0.0] * 9)),
        mavlink2.MAVLink_mag_cal_progress_message(0, 1, 2, 0, 10, [0] * 10, 0, 0, 0),
        None,
    ]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    updates = commands.get_compass_calibration_progress()
    assert [update["type"] for update in updates] == ["STATUS_TEXT", "REPORT", "PROGRESS"]
    assert updates[0]["text"] == "Mag(0) rotate vehicle"
    assert updates[1]["fitness"] == 0.3
    assert updates[2]["completion_pct"] == 10


def test_pausing_imu_poll_without_a_sample_does_not_log_a_transport_failure(
    mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
) -> None:
    """
    Treat an empty IMU queue as normal monitoring behavior.

    GIVEN: A connected controller has not supplied an IMU sample yet
    WHEN: The monitor polls its nonblocking stream
    THEN: No sample and no error diagnostic are produced.
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with caplog.at_level("DEBUG"):
        assert commands.poll_scaled_imu() is None
    assert not caplog.records


def test_confirming_accelerometer_position_offline_explains_the_required_connection(caplog: pytest.LogCaptureFixture) -> None:
    """
    Refuse an offline calibration confirmation with actionable guidance.

    GIVEN: The flight controller is disconnected
    WHEN: The operator confirms a physical accelerometer calibration position
    THEN: The returned error and diagnostic identify the missing confirmation connection.
    """
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=None))
    message = "No flight controller connection available to confirm calibration position"
    with caplog.at_level("ERROR"):
        assert commands.confirm_accel_vehicle_pos(1) == (False, message)
    assert caplog.messages == [message]


def test_aborting_a_rejected_level_command_does_not_quarantine_a_completed_operation(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Allow another level attempt after cancelling an already rejected command.

    GIVEN: Level calibration was denied and only its firmware-text grace window remains
    WHEN: The operator closes the view and immediately starts another attempt
    THEN: The rejected command does not block the new operation as unfinished.
    """
    master, connection = mock_connected_master
    master.recv_match.side_effect = [
        mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, 2),
        None,
        None,
    ]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", return_value=0):
        assert commands.start_accel_calibration_level() == (True, "")
        assert commands.poll_accel_calibration_level() is None
        master.recv_match.side_effect = None
        master.recv_match.return_value = None
        commands.abort_level_calibration()
        assert commands.start_accel_calibration_level() == (True, "")
    assert master.mav.command_long_send.call_count == 2


def test_mavlink_one_battery_status_without_extension_cells_still_reports_pack_voltage(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Accept battery telemetry from MAVLink 1 controllers without extension fields.

    GIVEN: A real MAVLink 1 battery message contains pack voltage and current
    WHEN: Motor-test battery readings are requested
    THEN: Missing MAVLink 2 extension cells do not discard the measurement.
    """
    master, connection = mock_connected_master
    master.recv_match.side_effect = [
        mavlink1.MAVLink_battery_status_message(0, 0, 0, 32767, [12400] + [65535] * 9, 210, -1, -1, -1),
        None,
    ]
    master.messages = {}
    commands = FlightControllerCommands(params_manager=Mock(fc_parameters={"BATT_MONITOR": 4}), connection_manager=connection)
    assert commands.get_battery_statuses() == ({0: (12.4, 2.1)}, "")


def test_simple_calibration_timeout_preserves_firmware_guidance_and_its_full_response_window(
    mock_connected_master: tuple[MagicMock, Mock], caplog: pytest.LogCaptureFixture
) -> None:
    """
    Retain firmware guidance until the longer simple-calibration window expires.

    GIVEN: Firmware sends guidance and an unrelated command acknowledgement
    WHEN: No calibration acknowledgement arrives within thirty seconds
    THEN: The timeout includes that guidance and receive retries use a short pause.
    """
    master, connection = mock_connected_master
    now = [0.0]
    responses = iter([mavlink2.MAVLink_statustext_message(6, b"Hold still"), mavlink2.MAVLink_command_ack_message(999, 0)])

    def receive(**_kwargs: object) -> object:
        message = next(responses)
        if message.get_type() == "COMMAND_ACK":
            now[0] = 29.9
        return message

    master.recv_match.side_effect = receive
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    expected = "Command acknowledgment timeout after 30.0 seconds: Hold still"
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]),
        patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep",
            side_effect=lambda _duration: now.__setitem__(0, 30.0),
        ) as pause,
        caplog.at_level("DEBUG"),
    ):
        assert commands.start_accel_calibration_simple() == (False, expected)
    pause.assert_called_once_with(0.1)
    assert master.recv_match.call_count == 2
    assert caplog.messages == [expected, f"Simple accelerometer calibration failed: {expected}"]


def test_compass_start_does_not_ignore_a_rejection_after_progress_telemetry(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Respect a terminal rejection even if compass telemetry initially suggests startup.

    GIVEN: Calibration progress is followed by a denied acknowledgement
    WHEN: The compass start waits for its final response
    THEN: The denial takes precedence over the earlier progress indication.
    """
    master, connection = mock_connected_master
    connection.info = SimpleNamespace(system_id="1", component_id="1")
    progress = mavlink2.MAVLink_mag_cal_progress_message(0, 1, 2, 0, 10, [0] * 10, 0, 0, 0)
    progress._header.srcSystem, progress._header.srcComponent = 1, 1  # pylint: disable=protected-access
    master.recv_match.side_effect = [
        None,
        progress,
        mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_DO_START_MAG_CAL, 2),
        None,
    ]
    now = [0.0]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]),
        patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep",
            side_effect=lambda _duration: now.__setitem__(0, 0.5),
        ),
    ):
        assert commands.start_compass_calibration() == (False, "Compass calibration start failed: Command denied")


def test_disconnected_level_view_can_close_and_restart_after_reconnection(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Discard an abandoned level exchange when its transport has disappeared.

    GIVEN: Level calibration loses its controller before the view closes
    WHEN: Monitoring is aborted and the controller reconnects
    THEN: A fresh level calibration can start without retaining an invalid quarantine deadline.
    """
    master, connection = mock_connected_master
    master.recv_match.return_value = None
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    assert commands.start_accel_calibration_level() == (True, "")
    connection.master = None
    commands.abort_level_calibration()
    connection.master = master
    assert commands.start_accel_calibration_level() == (True, "")
    assert master.mav.command_long_send.call_count == 2


def test_missing_primary_instance_does_not_hide_cached_secondary_battery(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Recover another reader's secondary battery even when the primary instance is absent.

    GIVEN: Two monitors are enabled and pymavlink has cached only battery instance one
    WHEN: Motor-test battery data is requested after the receive queue was drained
    THEN: The available secondary voltage and current are returned.
    """
    master, connection = mock_connected_master
    battery = mavlink2.MAVLink_battery_status_message(1, 0, 0, 32767, [24800] + [65535] * 9, 210, -1, -1, -1)
    battery._timestamp = 1.0  # pylint: disable=protected-access
    master.messages = {"BATTERY_STATUS[1]": battery}
    master.recv_match.return_value = None
    commands = FlightControllerCommands(
        params_manager=Mock(fc_parameters={"BATT_MONITOR": 4, "BATT2_MONITOR": 4}), connection_manager=connection
    )
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", return_value=1.0):
        assert commands.get_battery_statuses() == ({1: (24.8, 2.1)}, "")


def test_calibration_failure_waits_for_complete_chunked_firmware_guidance(
    mock_connected_master: tuple[MagicMock, Mock],
) -> None:
    """
    Assemble a long firmware explanation before appending it to the command failure.

    GIVEN: A denied calibration is followed by two MAVLink 2 status-text chunks
    WHEN: The final chunk arrives before the status-text grace deadline
    THEN: The complete message is returned once without including an unfinished fragment.
    """
    master, connection = mock_connected_master
    first = b"Disarm before starting accelerometer calibration. ".ljust(50, b" ")
    last = b"Keep vehicle still."
    now = [0.0]
    responses = iter(
        [
            mavlink2.MAVLink_command_ack_message(mavlink2.MAV_CMD_PREFLIGHT_CALIBRATION, 2),
            mavlink2.MAVLink_statustext_message(6, first, id=7, chunk_seq=0),
            mavlink2.MAVLink_statustext_message(6, last, id=7, chunk_seq=1),
        ]
    )

    def receive(**_kwargs: object) -> object:
        message = next(responses)
        if message.get_type() == "STATUSTEXT" and message.chunk_seq == 1:
            now[0] = 0.5
        return message

    master.recv_match.side_effect = receive
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]):
        assert commands.start_accel_calibration_simple() == (False, "Command denied: " + (first + last).decode().strip())
