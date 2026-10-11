#!/usr/bin/env python3

"""
Connection-loss behavior across transport sessions and serial-port naming conventions.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import errno
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from pymavlink import mavutil
from serial import SerialException

from ardupilot_methodic_configurator.backend_flightcontroller_connection import FlightControllerConnection
from ardupilot_methodic_configurator.backend_flightcontroller_factory_serial import FakeSerialPortDiscovery
from ardupilot_methodic_configurator.backend_flightcontroller_params import FlightControllerParams
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture
def serial_discovery() -> FakeSerialPortDiscovery:
    """Provide an isolated inventory containing the selected controller."""
    discovery = FakeSerialPortDiscovery()
    discovery.add_port("COM21", "Flight controller")
    return discovery


@pytest.fixture
def connection(serial_discovery: FakeSerialPortDiscovery) -> Iterator[FlightControllerConnection]:
    """Provide a connected controller without starting an OS event subscription."""
    connection = FlightControllerConnection(info=FlightControllerInfo(), serial_port_discovery=serial_discovery)
    connection.comport = mavutil.SerialPort(device="COM21", description="Flight controller")
    connection.set_master_for_testing(Mock(port=object(), portdead=False, recv=Mock(return_value=b"")))
    yield connection
    connection.disconnect()


@pytest.fixture
def tcp_transport(connection: FlightControllerConnection) -> mavutil.mavtcp:
    """Exercise real PyMAVLink TCP handling with an isolated socket boundary."""
    transport = object.__new__(mavutil.mavtcp)
    with patch.object(mavutil, "mavfile_global", None):
        mavutil.mavfile.__init__(transport, None, "tcp:localhost:5760")
    transport.port = Mock()
    transport.autoreconnect = True
    replacement = Mock()
    transport.do_connect = Mock(side_effect=lambda: setattr(transport, "port", replacement))
    connection.comport = mavutil.SerialPort(device="tcp:localhost:5760", description="SITL")
    connection.set_master_for_testing(transport)
    return transport


def test_live_unenumerated_serial_endpoint_is_not_reported_lost(serial_discovery: FakeSerialPortDiscovery) -> None:
    """GIVEN an open PTY omitted by discovery, WHEN repeated polls run, THEN live telemetry is not labelled disconnected."""
    serial_discovery.clear_ports()
    connection = FlightControllerConnection(FlightControllerInfo(), serial_port_discovery=serial_discovery)
    connection.comport = mavutil.SerialPort(device="/dev/pts/7", description="SITL serial")
    transport = Mock(portdead=False, recv=Mock(return_value=b"live telemetry"))
    connection.set_master_for_testing(transport)
    for _ in range(3):
        assert transport.recv() == b"live telemetry"
        assert connection.poll_connection() is None


@pytest.mark.parametrize("autoreconnect", [False, True])
def test_real_tcp_eof_is_reported_even_when_pymavlink_reconnects(
    connection: FlightControllerConnection, tcp_transport: mavutil.mavtcp, autoreconnect: bool
) -> None:
    """GIVEN TCP, WHEN EOF occurs without an exception, THEN loss is latched even after automatic reconnect."""
    tcp_transport.autoreconnect = autoreconnect
    tcp_transport.port.recv.return_value = b""
    assert tcp_transport.recv(1) == b""
    assert isinstance(connection.poll_connection(), str)


def test_real_tcp_idle_read_does_not_report_connection_loss(
    connection: FlightControllerConnection, tcp_transport: mavutil.mavtcp
) -> None:
    """GIVEN a connected nonblocking socket, WHEN no bytes are ready, THEN an empty receive is not treated as EOF."""
    tcp_transport.port.recv.side_effect = BlockingIOError(errno.EAGAIN, "no data available")
    assert tcp_transport.recv(1) == b""
    assert connection.poll_connection() is None


def test_late_tcp_eof_does_not_poison_a_replacement_session(
    connection: FlightControllerConnection, tcp_transport: mavutil.mavtcp
) -> None:
    """GIVEN an old TCP observer, WHEN a replacement session exists, THEN late EOF only affects the old transport."""
    late_eof = tcp_transport.handle_eof
    connection.set_master_for_testing(Mock(portdead=False))
    late_eof()
    assert connection.get_connection_lost_reason() is None


def test_previous_sessions_inventory_cannot_mark_an_unenumerated_endpoint_lost(
    connection: FlightControllerConnection, serial_discovery: FakeSerialPortDiscovery
) -> None:
    """GIVEN an enumerable old session, WHEN an unenumerated serial endpoint replaces it, THEN its presence is inconclusive."""
    serial_discovery.clear_ports()
    connection.comport = mavutil.SerialPort(device="/dev/pts/7", description="SITL serial")
    connection.set_master_for_testing(Mock(portdead=False))
    assert connection.poll_connection() is None
    assert connection.poll_connection() is None


def test_endpoint_can_be_observed_after_an_inconclusive_initial_inventory(
    connection: FlightControllerConnection, serial_discovery: FakeSerialPortDiscovery
) -> None:
    """GIVEN failed initial discovery, WHEN a later poll sees the port, THEN its subsequent disappearance is detected."""
    with patch.object(serial_discovery, "get_available_ports", side_effect=OSError("inventory failed")):
        connection.set_master_for_testing(connection.master)
        assert connection.poll_connection() is None
    assert connection.poll_connection() is None
    serial_discovery.clear_ports()
    assert connection.poll_connection() is None
    assert isinstance(connection.poll_connection(), str)


@pytest.mark.parametrize(
    ("platform", "selected", "available"),
    [
        ("win32", "COM21", "COM21"),
        ("win32", "com21", "COM21"),
        ("win32", r"\\.\COM21", "COM21"),
        ("darwin", "/dev/tty.usbmodem123", "/dev/cu.usbmodem123"),
        ("darwin", "/dev/cu.usbmodem123", "/dev/cu.usbmodem123"),
        ("linux", "/dev/ttyACM0", "/dev/ttyACM0"),
    ],
)
def test_connected_port_aliases_do_not_trigger_a_warning(
    connection: FlightControllerConnection,
    serial_discovery: FakeSerialPortDiscovery,
    platform: str,
    selected: str,
    available: str,
) -> None:
    """GIVEN a connected port alias, WHEN presence is checked twice, THEN the connection stays healthy."""
    connection.comport = mavutil.SerialPort(device=selected, description=selected)
    serial_discovery.clear_ports()
    serial_discovery.add_port(available, "Flight controller")
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.sys_platform", platform):
        connection.set_master_for_testing(connection.master)
        assert connection.poll_connection() is None
        assert connection.poll_connection() is None


def test_removal_requires_two_consecutive_missing_observations(
    connection: FlightControllerConnection, serial_discovery: FakeSerialPortDiscovery
) -> None:
    """GIVEN a healthy controller, WHEN it disappears twice, THEN loss stays latched even after reappearance."""
    serial_discovery.clear_ports()
    assert connection.poll_connection() is None
    assert isinstance(connection.poll_connection(), str)
    serial_discovery.add_port("COM21", "Flight controller")
    assert isinstance(connection.poll_connection(), str)


def test_transient_missing_port_does_not_trigger_a_warning(
    connection: FlightControllerConnection, serial_discovery: FakeSerialPortDiscovery
) -> None:
    """GIVEN one incomplete inventory, WHEN the controller reappears, THEN a later single miss is also tolerated."""
    serial_discovery.clear_ports()
    assert connection.poll_connection() is None
    serial_discovery.add_port("COM21", "Flight controller")
    assert connection.poll_connection() is None
    serial_discovery.clear_ports()
    assert connection.poll_connection() is None


def test_failed_enumeration_is_inconclusive_and_breaks_missing_sequence(connection: FlightControllerConnection) -> None:
    """GIVEN a missing observation, WHEN enumeration fails, THEN two new successful missing checks are required."""
    with patch.object(
        connection._serial_port_discovery, "get_available_ports", side_effect=[[], OSError("inventory"), [], []]
    ):
        assert connection.poll_connection() is None
        assert connection.poll_connection() is None
        assert connection.poll_connection() is None
        assert isinstance(connection.poll_connection(), str)


def test_reading_failure_state_does_not_scan_ports_or_consume_messages(connection: FlightControllerConnection) -> None:
    """GIVEN another operation owns MAVLink, WHEN status is queried or polled, THEN its receive queue is untouched."""
    receive = Mock(return_value=b"")
    connection.set_master_for_testing(Mock(portdead=False, recv=receive))
    with patch.object(connection._serial_port_discovery, "get_available_ports") as enumerate_ports:
        assert connection.get_connection_lost_reason() is None
        enumerate_ports.assert_not_called()
    assert connection.poll_connection() is None
    receive.assert_not_called()
    connection.master.recv_match.assert_not_called()


@pytest.mark.parametrize("device", ["tcp:localhost:5760", "udp:localhost:14550", "wss:localhost:443"])
def test_network_connections_are_not_compared_with_serial_inventory(
    connection: FlightControllerConnection, device: str
) -> None:
    """GIVEN a network endpoint, WHEN status is polled, THEN serial enumeration cannot produce a false warning."""
    connection.comport = mavutil.SerialPort(device=device, description=device)
    with patch.object(connection._serial_port_discovery, "get_available_ports") as enumerate_ports:
        assert connection.poll_connection() is None
        assert connection.poll_connection() is None
        enumerate_ports.assert_not_called()


@pytest.mark.parametrize("device", ["tcp:localhost:5760", "udp:localhost:14550", "wss:localhost:443"])
def test_network_receive_errors_are_reported_by_the_existing_receive_owner(
    connection: FlightControllerConnection, device: str
) -> None:
    """GIVEN an active network transport, WHEN its owner observes an I/O failure, THEN that session is reported lost."""
    connection.comport = mavutil.SerialPort(device=device, description=device)
    master = Mock(recv=Mock(side_effect=OSError("network failed")))
    connection.set_master_for_testing(master)
    with pytest.raises(OSError, match="network failed"):
        master.recv()
    assert connection.get_connection_lost_reason() == "network failed"


def test_pymavlink_write_failure_is_reported_even_if_port_is_still_present(connection: FlightControllerConnection) -> None:
    """GIVEN PyMAVLink swallowed a write failure, WHEN status is polled, THEN its portdead flag reports loss."""
    connection.master.portdead = True
    assert isinstance(connection.poll_connection(), str)


def test_first_transport_error_is_preserved_until_disconnect(connection: FlightControllerConnection) -> None:
    """GIVEN two transport failures, WHEN disconnect occurs, THEN the first failure was retained and is now cleared."""
    connection.mark_connection_lost("first failure")
    connection.mark_connection_lost("second failure")
    assert connection.get_connection_lost_reason() == "first failure"
    connection.disconnect()
    assert connection.get_connection_lost_reason() is None
    assert connection.poll_connection() is None


def test_reconnecting_replaces_failure_state_and_ignores_late_native_events(serial_discovery: FakeSerialPortDiscovery) -> None:
    """GIVEN a failed session, WHEN another connection succeeds, THEN late events cannot poison the new session."""
    callbacks: list[Callable[[], None]] = []
    subscriptions: list[Mock] = []

    def subscribe(_device: str, on_removed: Callable[[], None]) -> Mock:
        monitor = Mock()
        callbacks.append(on_removed)
        subscriptions.append(monitor)
        return monitor

    master = Mock(port=object(), portdead=False)
    factory = Mock()
    factory.create.return_value = master
    connection = FlightControllerConnection(
        info=FlightControllerInfo(),
        serial_port_discovery=serial_discovery,
        mavlink_connection_factory=factory,
        serial_port_monitor_factory=subscribe,
    )
    heartbeat = Mock(autopilot=3, type=2)
    with (
        patch.object(connection, "_detect_vehicles_from_heartbeats", return_value={(1, 1): heartbeat}),
        patch.object(connection, "_retrieve_autopilot_version_and_banner", return_value=""),
    ):
        assert connection.connect("COM21") == ""
        callbacks[0]()
        assert isinstance(connection.get_connection_lost_reason(), str)
        # Even a callback delivered during stop belongs to the old session.
        subscriptions[0].stop.side_effect = callbacks[0]
        assert connection.connect("COM21") == ""
        callbacks[0]()
        assert connection.poll_connection() is None
        subscriptions[0].stop.assert_called_once()
        callbacks[1]()
        assert isinstance(connection.get_connection_lost_reason(), str)
    connection.disconnect()
    subscriptions[1].stop.assert_called_once()


def test_old_receive_errors_cannot_mark_a_replacement_transport_lost(connection: FlightControllerConnection) -> None:
    """GIVEN an old receive callback, WHEN a new session exists, THEN an old error is re-raised without latching loss."""
    old_master = Mock(portdead=False, recv=Mock(side_effect=SerialException("old device")))
    connection.set_master_for_testing(old_master)
    old_receive = old_master.recv
    connection.set_master_for_testing(Mock(portdead=False))
    with pytest.raises(SerialException, match="old device"):
        old_receive()
    assert connection.get_connection_lost_reason() is None


def test_native_startup_failure_keeps_port_polling_available(serial_discovery: FakeSerialPortDiscovery) -> None:
    """GIVEN unavailable native notifications, WHEN the serial port later disappears, THEN polling still reports loss."""
    monitor = Mock()
    monitor.start.side_effect = OSError("native API unavailable")
    connection = FlightControllerConnection(
        info=FlightControllerInfo(),
        serial_port_discovery=serial_discovery,
        serial_port_monitor_factory=Mock(return_value=monitor),
    )
    connection.comport = mavutil.SerialPort(device="COM21", description="Flight controller")
    connection.set_master_for_testing(Mock(port=object(), portdead=False))
    connection._start_serial_port_monitor()
    monitor.stop.assert_called_once()
    assert connection.poll_connection() is None
    serial_discovery.clear_ports()
    assert connection.poll_connection() is None
    assert isinstance(connection.poll_connection(), str)


def test_polling_keeps_the_original_linux_endpoint_after_a_symlink_disappears(
    connection: FlightControllerConnection, serial_discovery: FakeSerialPortDiscovery
) -> None:
    """GIVEN a by-id connection, WHEN its link disappears, THEN monitoring still identifies the original tty endpoint."""
    identity_path = "ardupilot_methodic_configurator.backend_flightcontroller_connection.serial_port_identity"
    connection.comport = mavutil.SerialPort(device="/dev/serial/by-id/controller", description="Flight controller")
    with patch(identity_path, return_value="/dev/ttyACM0"):
        connection.set_master_for_testing(connection.master)
    serial_discovery.clear_ports()
    serial_discovery.add_port("/dev/ttyACM0", "Flight controller")
    with patch(identity_path, side_effect=lambda device, _platform: device):
        assert connection.poll_connection() is None
        assert connection.poll_connection() is None


def test_reusing_a_transport_installs_a_fresh_error_observer(connection: FlightControllerConnection) -> None:
    """GIVEN a reused transport, WHEN it fails in the new session, THEN the current session receives the failure."""
    master = connection.master
    # Replace the original read operation, then start a fresh session on the same transport.
    connection.set_master_for_testing(None)
    connection.comport = mavutil.SerialPort(device="COM21", description="Flight controller")
    master.recv.side_effect = SerialException("new device")
    connection.set_master_for_testing(master)
    with pytest.raises(SerialException, match="new device"):
        master.recv()
    assert connection.get_connection_lost_reason() == "new device"


@pytest.mark.parametrize("error", [SerialException("USB removed"), ConnectionError("connection closed")])
def test_mavftp_transport_failure_does_not_attempt_mavlink_fallback(
    connection: FlightControllerConnection, error: Exception
) -> None:
    """GIVEN a MAVFTP transfer, WHEN its transport fails, THEN no second download is attempted on the dead connection."""
    connection.info.is_mavftp_supported = True
    params = FlightControllerParams(connection_manager=connection, fc_parameters={"EXISTING": 1.0})
    mavftp = Mock()
    mavftp.cmd_getparams.side_effect = error
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_params.create_mavftp", return_value=mavftp):
        values, defaults = params.download_params()
    assert values == {}
    assert not defaults
    assert params.fc_parameters == {"EXISTING": 1.0}
    assert connection.get_connection_lost_reason() == str(error)
    connection.master.mav.param_request_list_send.assert_not_called()


@pytest.mark.parametrize("inventory_error", [False, True])
def test_mavftp_protocol_failure_still_downloads_via_mavlink(
    connection: FlightControllerConnection, inventory_error: bool
) -> None:
    """GIVEN a healthy transport, WHEN MAVFTP fails or inventory is unavailable, THEN MAVLink fallback still succeeds."""
    connection.info.is_mavftp_supported = True
    params = FlightControllerParams(connection_manager=connection)
    mavftp = Mock()
    mavftp.cmd_getparams.side_effect = ValueError("MAVFTP protocol failure")
    parameter = Mock(param_count=1)
    parameter.to_dict.return_value = {"param_id": "TEST_PARAM", "param_value": 2.0}
    connection.master.recv_match.return_value = parameter
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_params.create_mavftp", return_value=mavftp),
        patch.object(
            connection._serial_port_discovery,
            "get_available_ports",
            side_effect=OSError("inventory failed") if inventory_error else None,
            return_value=connection._serial_port_discovery.get_available_ports(),
        ),
    ):
        values, _defaults = params.download_params()
    assert values == {"TEST_PARAM": 2.0}
    assert params.fc_parameters == values
    assert connection.get_connection_lost_reason() is None


def test_mavftp_failure_after_port_removal_does_not_attempt_fallback(
    connection: FlightControllerConnection, serial_discovery: FakeSerialPortDiscovery
) -> None:
    """GIVEN one observed missing port, WHEN MAVFTP fails and the next inventory also lacks it, THEN fallback is skipped."""
    connection.info.is_mavftp_supported = True
    serial_discovery.clear_ports()
    assert connection.poll_connection() is None
    params = FlightControllerParams(connection_manager=connection)
    mavftp = Mock()
    mavftp.cmd_getparams.side_effect = ValueError("transfer incomplete")
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_params.create_mavftp", return_value=mavftp):
        values, _defaults = params.download_params()
    assert values == {}
    assert isinstance(connection.get_connection_lost_reason(), str)
    connection.master.mav.param_request_list_send.assert_not_called()


def test_unenumerated_endpoint_keeps_mavlink_fallback_available_across_downloads(
    connection: FlightControllerConnection, serial_discovery: FakeSerialPortDiscovery
) -> None:
    """GIVEN a healthy PTY, WHEN MAVFTP fails repeatedly, THEN every download can still fall back to MAVLink."""
    serial_discovery.clear_ports()
    connection.comport = mavutil.SerialPort(device="/dev/pts/7", description="SITL serial")
    connection.set_master_for_testing(connection.master)
    connection.info.is_mavftp_supported = True
    params = FlightControllerParams(connection_manager=connection)
    mavftp = Mock()
    mavftp.cmd_getparams.side_effect = ValueError("MAVFTP protocol failure")
    parameter = Mock(param_count=1)
    parameter.to_dict.return_value = {"param_id": "TEST_PARAM", "param_value": 2.0}
    connection.master.recv_match.return_value = parameter
    with patch("ardupilot_methodic_configurator.backend_flightcontroller_params.create_mavftp", return_value=mavftp):
        for _ in range(3):
            values, _defaults = params.download_params()
            assert values == {"TEST_PARAM": 2.0}
    assert connection.get_connection_lost_reason() is None
