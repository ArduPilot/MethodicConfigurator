#!/usr/bin/env python3

"""
Behavior tests for compass start acknowledgments and telemetry fallback.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import itertools
from unittest.mock import Mock, patch

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink

from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands
from ardupilot_methodic_configurator.backend_flightcontroller_connection import FlightControllerConnection
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

# pylint: disable=protected-access,redefined-outer-name


def _progress(status: int = mavlink.MAG_CAL_RUNNING_STEP_ONE, system: int = 1) -> mavlink.MAVLink_mag_cal_progress_message:
    message = mavlink.MAVLink_mag_cal_progress_message(0, 1, status, 1, 10, [0] * 10, 0.0, 0.0, 0.0)
    message._header.srcSystem = system  # pylint: disable=protected-access
    message._header.srcComponent = 1  # pylint: disable=protected-access
    return message


@pytest.mark.parametrize("progress_first", [False, True])
def test_explicit_rejection_wins_over_progress_and_preserves_diagnostic_details(progress_first: bool) -> None:
    """GIVEN a denied start and progress in either order, WHEN received, THEN rejection and its details win."""
    master = Mock(target_system=1, target_component=1)
    ack = mavlink.MAVLink_command_ack_message(mavlink.MAV_CMD_DO_START_MAG_CAL, mavlink.MAV_RESULT_DENIED)
    replies = [_progress(), ack] if progress_first else [ack, _progress()]
    replies.append(mavlink.MAVLink_statustext_message(4, b"Disarm to allow compass calibration"))
    master.recv_match.side_effect = itertools.chain([None], replies, itertools.repeat(None))
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=master))
    now = [0.0]

    def advance(_seconds: float) -> None:
        now[0] += 1.0

    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=lambda: now[0]),
        patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_sleep", side_effect=advance),
    ):
        success, error = commands.start_compass_calibration()
    assert not success
    assert "Command denied" in error
    assert "Disarm to allow compass calibration" in error


@pytest.mark.parametrize(("status", "system"), [(mavlink.MAG_CAL_FAILED, 1), (mavlink.MAG_CAL_RUNNING_STEP_ONE, 2)])
def test_failed_or_foreign_calibration_telemetry_cannot_confirm_start(status: int, system: int) -> None:
    """GIVEN inactive or unrelated telemetry, WHEN no ACK arrives, THEN calibration start times out."""
    master = Mock(target_system=1, target_component=1)
    master.recv_match.side_effect = [None, _progress(status, system)]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=master))
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=[0, 0, 6]):
        success, error = commands.start_compass_calibration()
    assert not success
    assert "timeout" in error


def test_queued_progress_from_an_old_attempt_cannot_confirm_a_new_command() -> None:
    """GIVEN old queued progress, WHEN a new command receives no replies, THEN the old attempt cannot confirm it."""
    master = Mock(target_system=1, target_component=1)
    master.recv_match.side_effect = [_progress(), None]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=master))
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=[0, 6]):
        success, error = commands.start_compass_calibration()
    assert not success
    assert "timeout" in error


@pytest.fixture
def discovered_compass_controller(monkeypatch: pytest.MonkeyPatch) -> tuple[FlightControllerConnection, bytearray]:
    """Discover a controller through real heartbeat parsing without assigning a target component."""
    master = mavutil.mavfile(None, "in-memory", input=False)
    master.mav = mavlink.MAVLink(master)
    encoder = mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
    heartbeat = mavlink.MAVLink_heartbeat_message(
        mavlink.MAV_TYPE_QUADROTOR, mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA, 0, 0, mavlink.MAV_STATE_STANDBY, 3
    )
    wire = bytearray(heartbeat.pack(encoder))

    # pylint: disable=duplicate-code  # Shared in-memory PyMAVLink transport setup.
    def recv(count: int) -> bytes:
        data = bytes(wire[:count])
        del wire[:count]
        return data

    monkeypatch.setattr(master, "recv", recv)
    connection = FlightControllerConnection(info=FlightControllerInfo())
    connection.set_master_for_testing(master)
    # pylint: enable=duplicate-code
    detected = connection._detect_vehicles_from_heartbeats(1, return_after_first_heartbeat=True)
    assert connection._select_supported_autopilot(detected) == ""
    assert (master.target_system, master.target_component) == (1, 0)
    return connection, wire


@pytest.mark.parametrize(
    ("status", "system", "component", "metadata_available", "expected"),
    [
        (mavlink.MAG_CAL_WAITING_TO_START, 1, 1, True, True),
        (mavlink.MAG_CAL_RUNNING_STEP_ONE, 1, 1, True, True),
        (mavlink.MAG_CAL_RUNNING_STEP_TWO, 1, 1, True, True),
        (mavlink.MAG_CAL_RUNNING_STEP_ONE, 1, 1, False, True),
        (mavlink.MAG_CAL_RUNNING_STEP_ONE, 2, 1, True, False),
        (mavlink.MAG_CAL_RUNNING_STEP_ONE, 1, 100, True, False),
        (mavlink.MAG_CAL_FAILED, 1, 1, True, False),
    ],
)
def test_discovered_controller_can_confirm_compass_start_without_ack(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    discovered_compass_controller: tuple[FlightControllerConnection, bytearray],
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    system: int,
    component: int,
    metadata_available: bool,
    expected: bool,
) -> None:
    """
    Compass startup works with the application's actual discovered connection defaults.

    GIVEN an application-selected controller with target component zero,
    WHEN only fresh calibration progress arrives after sending the command,
    THEN active progress from that controller confirms startup, not foreign or failed progress.
    """
    connection, wire = discovered_compass_controller
    master = connection.master
    assert master is not None
    if not metadata_available:
        connection.info.reset()
    encoder = mavlink.MAVLink(None, srcSystem=system, srcComponent=component)
    packet = _progress(status).pack(encoder)
    monkeypatch.setattr(master, "write", lambda _data: wire.extend(packet))
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=connection)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=[0, 0, 6]):
        success, error = commands.start_compass_calibration()
    assert success is expected
    if expected:
        assert error == ""
    else:
        assert "timeout" in error


def test_compass_start_timeout_preserves_received_diagnostic_details() -> None:
    """
    Missing acknowledgments do not hide the controller's explanation of a failed start.

    GIVEN a controller reporting why calibration cannot start but no ACK,
    WHEN the command times out,
    THEN the error includes the received diagnostic instead of only a generic timeout.
    """
    master = Mock(target_system=1, target_component=1)
    master.recv_match.side_effect = [
        None,
        mavlink.MAVLink_statustext_message(4, b"Disarm to allow compass calibration"),
    ]
    commands = FlightControllerCommands(params_manager=Mock(), connection_manager=Mock(master=master))
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_commands.time_time", side_effect=[0, 0, 6]):
        success, error = commands.start_compass_calibration()
    assert not success
    assert "timeout" in error
    assert "Disarm to allow compass calibration" in error
