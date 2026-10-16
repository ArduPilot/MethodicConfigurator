#!/usr/bin/env python3

"""
Reconnection behavior with the real PyMAVLink parser and mocked transport I/O.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from serial.tools.list_ports_common import ListPortInfo

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_reconnect import FlightControllerReconnect
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

# pylint: disable=redefined-outer-name


@pytest.fixture
def link(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, FlightControllerReconnect, list[float], Callable]:
    """Supply packets through a real parser; mock only the external connection and parameter transfer."""
    fc = MagicMock(spec=FlightController)
    fc.info = FlightControllerInfo()
    fc.info.hw_unique_id = "original-uid"
    fc.info.system_id = fc.info.component_id = "1"
    fc.comport_device = "udp:localhost:14550"
    fc.active_baudrate = 57600
    fc.get_serial_ports.return_value = []
    fc.fc_parameters = {"TEST": 1.0}
    master = mavutil.mavfile(None, "in-memory", input=False)
    master.mav = mavlink.MAVLink(master)
    master.target_system = master.target_component = 1
    master.autoreconnect = True
    fc.master = master
    wire = bytearray()

    def recv(count: int) -> bytes:
        data = bytes(wire[:count])
        del wire[:count]
        return data

    def enqueue(message: object, system: int = 1, component: int = 1) -> None:
        encoder = mavlink.MAVLink(None, srcSystem=system, srcComponent=component)
        wire.extend(message.pack(encoder))

    def disconnect() -> None:
        fc.master = None
        fc.info.reset()
        fc.fc_parameters = {}

    def connect(_device: str, **_kwargs: object) -> str:
        fc.master = master
        fc.info.hw_unique_id = "original-uid"
        fc.info.system_id = fc.info.component_id = "1"
        return ""

    def download(**_kwargs: object) -> tuple[dict, dict]:
        fc.fc_parameters = {"TEST": 2.0}
        return fc.fc_parameters, {}

    monkeypatch.setattr(master, "recv", recv)
    fc.disconnect.side_effect = disconnect
    fc.connect.side_effect = connect
    fc.download_params.side_effect = download
    clock = [0.0]
    return fc, FlightControllerReconnect(fc, clock=lambda: clock[0]), clock, enqueue


def heartbeat() -> object:
    return mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 0, 3)


def test_plugin_receives_its_reply_while_the_hook_observes_heartbeats(link: tuple) -> None:
    """GIVEN queued HB and ACK, WHEN a plugin waits for ACK, THEN the observer leaves its reply intact."""
    fc, monitor, clock, enqueue = link
    clock[0] = 20.0
    enqueue(heartbeat())
    enqueue(mavlink.MAVLink_command_ack_message(400, 0))
    reply = fc.master.recv_match(type="COMMAND_ACK", blocking=False)
    assert reply.command == 400
    assert monitor.poll(read=False)
    clock[0] = 29.0
    assert not monitor.poll(read=False)


@pytest.mark.parametrize("source", [(2, 1), (1, 100)])
def test_unrelated_heartbeats_do_not_hide_a_lost_fc(link: tuple, source: tuple[int, int]) -> None:
    """GIVEN a silent target, WHEN another vehicle or component transmits, THEN the target is still lost."""
    _fc, monitor, clock, enqueue = link
    clock[0] = 20.0
    enqueue(heartbeat(), *source)
    assert not monitor.poll(read=True)


def test_passive_checks_never_read_plugin_messages(link: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    """GIVEN reception belongs to a plugin, WHEN checking health, THEN recv_match is never called."""
    fc, monitor, _clock, _enqueue = link
    receive = MagicMock(side_effect=AssertionError("Competing reader"))
    monkeypatch.setattr(fc.master, "recv_match", receive)
    assert monitor.poll(read=False)
    receive.assert_not_called()


@pytest.mark.parametrize("backlog", [200, 1000])
def test_buffered_target_heartbeat_keeps_a_busy_link_connected(link: tuple, backlog: int) -> None:
    """GIVEN queued traffic, WHEN the target heartbeat follows it, THEN health recovers without draining later replies."""
    fc, monitor, clock, enqueue = link
    clock[0] = 20.0
    for _packet in range(backlog):
        enqueue(heartbeat(), system=2)
    enqueue(heartbeat())
    enqueue(mavlink.MAVLink_command_ack_message(400, 0))

    assert monitor.poll(read=True)
    assert fc.master.recv_match(blocking=False).get_type() == "COMMAND_ACK"
    fc.connect.assert_not_called()


def test_busy_link_without_target_heartbeat_stops_reading_at_deadline(link: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    """GIVEN continuous unrelated traffic, WHEN checking health, THEN the time budget bounds reception."""
    fc, monitor, clock, _enqueue = link
    clock[0] = 20.0

    def receive(*, blocking: bool) -> object:
        assert not blocking
        clock[0] += 0.004
        return mavlink.MAVLink_command_ack_message(400, 0)

    monkeypatch.setattr(fc.master, "recv_match", receive)
    assert not monitor.poll(read=True)
    assert 20.01 <= clock[0] < 20.014


def test_idle_editor_detects_transport_failure_without_waiting_for_timeout(
    link: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GIVEN an unplugged transport, WHEN the idle owner reads, THEN loss is reported immediately."""
    fc, monitor, _clock, _enqueue = link
    monkeypatch.setattr(fc.master, "recv_match", MagicMock(side_effect=OSError("Unplugged")))
    assert not monitor.poll(read=True)


def test_failed_serial_write_cannot_reopen_a_port_behind_the_monitor(link: tuple) -> None:
    """GIVEN a monitored serial transport, WHEN a heartbeat write fails, THEN pymavlink cannot reopen an unverified FC."""
    fc, monitor, _clock, _enqueue = link
    master = fc.master
    master.port = MagicMock()
    master.port.write.side_effect = OSError("Unplugged")
    master.portdead = False
    master.device = "COM1"
    master.reset = MagicMock()

    assert mavutil.mavserial.write(master, b"heartbeat") == -1

    master.reset.assert_not_called()
    assert not monitor.poll(read=False)
    assert not monitor.poll(read=True)
    monitor.close()
    assert master.autoreconnect is True


def test_recovered_transport_cannot_reopen_during_parameter_refresh(link: tuple) -> None:
    """GIVEN a verified reconnect, WHEN parameters download, THEN transport recovery still belongs to the monitor."""
    fc, monitor, _clock, _enqueue = link
    download = fc.download_params.side_effect

    def refresh(**kwargs: object) -> tuple[dict, dict]:
        assert fc.master.autoreconnect is False
        return download(**kwargs)

    fc.download_params.side_effect = refresh
    assert monitor.reconnect() == ""
    assert fc.master.autoreconnect is False
    master = fc.master
    monitor.close()
    assert master.autoreconnect is True


def test_intentionally_paused_reception_gets_a_new_grace_period(link: tuple) -> None:
    """GIVEN a long exclusive operation, WHEN it yields reception, THEN stale timestamps do not force a reconnect."""
    _fc, monitor, clock, _enqueue = link
    clock[0] = 30.0
    monitor.defer()
    assert monitor.poll(read=False)
    clock[0] = 39.0
    assert not monitor.poll(read=False)


def test_same_hardware_reconnects_at_selected_baudrate_and_refreshes_values(link: tuple) -> None:
    """GIVEN a lost link, WHEN the original UID returns, THEN fresh parameters become available without writes."""
    fc, monitor, _clock, _enqueue = link
    assert monitor.reconnect() == ""
    fc.connect.assert_called_once_with("udp:localhost:14550", log_errors=False, baudrate=57600)
    assert fc.fc_parameters == {"TEST": 2.0}
    assert monitor.poll(read=False)
    fc.set_param.assert_not_called()
    fc.download_params.assert_called_once()
    # Recovery must use the backend's link-aware budget, including slow serial links.
    assert fc.download_params.call_args.kwargs.get("response_timeout") is None
    assert fc.download_params.call_args.kwargs["cancellation_requested"] == monitor.cancelled.is_set


@pytest.mark.parametrize("uid", ["replacement-uid", ""])
def test_replacement_or_unknown_hardware_is_rejected_before_parameters_are_read(link: tuple, uid: str) -> None:
    """GIVEN a replacement FC, WHEN it answers on the same endpoint, THEN it is closed before reading or writing parameters."""
    fc, monitor, _clock, _enqueue = link
    connect = fc.connect.side_effect

    def replacement(*args: object, **kwargs: object) -> str:
        connect(*args, **kwargs)
        fc.info.hw_unique_id = uid
        return ""

    fc.connect.side_effect = replacement
    assert "hardware ID" in monitor.reconnect()
    assert fc.master is None
    assert fc.fc_parameters == {}
    fc.download_params.assert_not_called()
    fc.set_param.assert_not_called()


def test_failed_attempt_can_be_retried_until_original_controller_returns(link: tuple) -> None:
    """GIVEN an unavailable link, WHEN a later retry succeeds, THEN the saved original UID still authorizes reconnection."""
    fc, monitor, _clock, _enqueue = link
    connect = fc.connect.side_effect
    fc.connect.side_effect = None
    fc.connect.return_value = "Unavailable"
    assert monitor.reconnect() == "Unavailable"
    assert fc.master is None
    fc.connect.side_effect = connect
    assert monitor.reconnect() == ""


@pytest.mark.parametrize("target", [("2", "1"), ("1", "100"), ("", "")])
def test_matching_uid_cannot_authorize_a_different_or_unknown_mavlink_target(link: tuple, target: tuple[str, str]) -> None:
    """GIVEN routed autopilots, WHEN another target borrows the original UID, THEN it is rejected before parameter access."""
    fc, monitor, _clock, _enqueue = link
    connect = fc.connect.side_effect

    def routed_target(*args: object, **kwargs: object) -> str:
        connect(*args, **kwargs)
        fc.info.system_id, fc.info.component_id = target
        return ""

    fc.connect.side_effect = routed_target

    assert "MAVLink system or component ID" in monitor.reconnect()
    assert fc.master is None
    assert fc.fc_parameters == {}
    fc.download_params.assert_not_called()
    fc.set_param.assert_not_called()

    # A rejected candidate must not change the target retained for later retries.
    fc.connect.side_effect = connect
    assert monitor.reconnect() == ""
    assert (fc.info.system_id, fc.info.component_id) == ("1", "1")
    assert fc.fc_parameters == {"TEST": 2.0}


def test_incomplete_refresh_leaves_no_usable_connection_or_stale_cache(link: tuple) -> None:
    """GIVEN the correct FC but an incomplete download, WHEN reconnecting, THEN the editor remains disconnected."""
    fc, monitor, _clock, _enqueue = link
    fc.download_params.side_effect = None
    fc.download_params.return_value = {}, {}
    assert monitor.reconnect()
    assert fc.master is None
    assert fc.fc_parameters == {}


def test_usb_renumbering_uses_endpoint_metadata_but_still_verifies_fc_uid(link: tuple) -> None:
    """GIVEN the same USB interface under a new port name, WHEN reconnecting, THEN the new endpoint is tried."""
    fc, original_monitor, clock, _enqueue = link
    original_monitor.close()
    old, new = ListPortInfo("/dev/ttyACM0"), ListPortInfo("/dev/ttyACM1")
    old.serial_number = new.serial_number = "serial123"
    old.vid = new.vid = 0x1234
    old.pid = new.pid = 0x5678
    fc.comport_device = old.device
    fc.get_serial_ports.return_value = [old]
    monitor = FlightControllerReconnect(fc, clock=lambda: clock[0])
    fc.get_serial_ports.return_value = [new]
    assert monitor.reconnect() == ""
    fc.connect.assert_called_once_with(new.device, log_errors=False, baudrate=57600)


def test_closing_removes_only_our_hook_and_cancels_further_attempts(link: tuple) -> None:
    """GIVEN other observers, WHEN the editor closes, THEN only its own observer is removed and no reconnect begins."""
    fc, monitor, _clock, _enqueue = link
    master = fc.master
    other_hook = MagicMock()
    master.message_hooks.append(other_hook)
    monitor.close()
    assert master.message_hooks == [other_hook]
    assert monitor.reconnect()
    fc.connect.assert_not_called()


@pytest.mark.parametrize("stage", ["connect", "download"])
def test_closing_during_recovery_never_publishes_a_connection(link: tuple, stage: str) -> None:
    """GIVEN an in-flight recovery, WHEN the editor closes, THEN no late success leaves a reusable FC connection."""
    fc, monitor, _clock, _enqueue = link
    operation = fc.connect if stage == "connect" else fc.download_params
    original = operation.side_effect

    def cancel(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)
        monitor.cancelled.set()
        return result

    operation.side_effect = cancel
    assert monitor.reconnect()
    assert fc.master is None
    assert fc.fc_parameters == {}
    if stage == "connect":
        fc.download_params.assert_not_called()


def test_unknown_original_hardware_cannot_authorize_reconnection(link: tuple) -> None:
    """GIVEN no original UID, WHEN constructing recovery, THEN it cannot connect to a replacement by endpoint alone."""
    fc, original, _clock, _enqueue = link
    original.close()
    fc.info.hw_unique_id = ""
    monitor = FlightControllerReconnect(fc)
    assert not monitor.enabled
    assert monitor.reconnect()
    fc.connect.assert_not_called()
    fc.disconnect.assert_not_called()


@pytest.mark.parametrize("renumbered", [False, True])
def test_recovery_finds_mavlink_among_usb_interfaces_with_identical_metadata(link: tuple, renumbered: bool) -> None:
    """GIVEN two indistinguishable USB interfaces, WHEN the board returns, THEN recovery reaches its MAVLink endpoint."""
    fc, previous, clock, _enqueue = link
    previous.close()
    original = ListPortInfo("/dev/ttyACM0")
    wrong = ListPortInfo("/dev/ttyACM1")
    returned = ListPortInfo("/dev/ttyACM2" if renumbered else original.device)
    for port in (original, wrong, returned):
        port.serial_number, port.vid, port.pid, port.interface = "board123", 0x1234, 0x5678, None
    fc.comport_device = original.device
    fc.get_serial_ports.return_value = [original]
    monitor = FlightControllerReconnect(fc, clock=lambda: clock[0])
    fc.get_serial_ports.return_value = [wrong, returned]
    connect = fc.connect.side_effect

    def connect_interface(device: str, **kwargs: object) -> str:
        if device == wrong.device:
            return "No MAVLink heartbeat received"
        return connect(device, **kwargs)

    fc.connect.side_effect = connect_interface
    assert monitor.reconnect() == ""
    expected = [wrong.device, returned.device] if renumbered else [returned.device]
    assert [call.args[0] for call in fc.connect.call_args_list] == expected
    assert fc.info.hw_unique_id == "original-uid"
    assert fc.fc_parameters == {"TEST": 2.0}
    fc.download_params.assert_called_once()


def test_usb_interface_description_changes_do_not_prevent_recovery(link: tuple) -> None:
    """GIVEN a re-enumerated USB interface with changed metadata, WHEN its UID matches, THEN recovery still succeeds."""
    fc, previous, clock, _enqueue = link
    previous.close()
    original, returned = ListPortInfo("/dev/ttyACM0"), ListPortInfo("/dev/ttyACM1")
    for port in (original, returned):
        port.serial_number, port.vid, port.pid = "board123", 0x1234, 0x5678
    original.interface, returned.interface = "MAVLink", None
    fc.comport_device = original.device
    fc.get_serial_ports.return_value = [original]
    monitor = FlightControllerReconnect(fc, clock=lambda: clock[0])
    fc.get_serial_ports.return_value = [returned]
    assert monitor.reconnect() == ""
    fc.connect.assert_called_once_with(returned.device, log_errors=False, baudrate=57600)


def test_wrong_hardware_on_one_candidate_does_not_hide_original_fc_on_another(link: tuple) -> None:
    """GIVEN ambiguous USB metadata, WHEN one candidate has another UID, THEN only the original FC supplies parameters."""
    fc, previous, clock, _enqueue = link
    previous.close()
    first, second = ListPortInfo("/dev/ttyACM0"), ListPortInfo("/dev/ttyACM1")
    for port in (first, second):
        port.serial_number, port.vid, port.pid = "shared-serial", 0x1234, 0x5678
    fc.comport_device = first.device
    fc.get_serial_ports.return_value = [first, second]
    monitor = FlightControllerReconnect(fc, clock=lambda: clock[0])
    connect = fc.connect.side_effect

    def connect_candidate(device: str, **kwargs: object) -> str:
        result = connect(device, **kwargs)
        if device == first.device:
            fc.info.hw_unique_id = "other-uid"
        return result

    fc.connect.side_effect = connect_candidate
    assert monitor.reconnect() == ""
    assert [call.args[0] for call in fc.connect.call_args_list] == [first.device, second.device]
    assert fc.info.hw_unique_id == "original-uid"
    fc.download_params.assert_called_once()


def test_usb_without_a_serial_number_can_recover_using_vid_pid_and_fc_uid(link: tuple) -> None:
    """GIVEN no USB serial number, WHEN the endpoint changes, THEN USB metadata and the FC UID enable recovery."""
    fc, previous, clock, _enqueue = link
    previous.close()
    original, returned = ListPortInfo("/dev/ttyACM0"), ListPortInfo("/dev/ttyACM1")
    for port in (original, returned):
        port.vid, port.pid = 0x1234, 0x5678
    fc.comport_device = original.device
    fc.get_serial_ports.return_value = [original]
    monitor = FlightControllerReconnect(fc, clock=lambda: clock[0])
    fc.get_serial_ports.return_value = [returned]
    assert monitor.reconnect() == ""
    fc.connect.assert_called_once_with(returned.device, log_errors=False, baudrate=57600)


def test_failed_candidate_is_closed_and_its_error_is_logged(link: tuple, caplog: pytest.LogCaptureFixture) -> None:
    """GIVEN a silent endpoint, WHEN reconnecting fails, THEN operators see the actual reason and its transport is released."""
    fc, monitor, _clock, _enqueue = link
    fc.connect.side_effect = None
    fc.connect.return_value = "No MAVLink heartbeat received"
    with caplog.at_level("INFO"):
        assert monitor.reconnect() == "No MAVLink heartbeat received"
    assert "udp:localhost:14550" in caplog.text
    assert "No MAVLink heartbeat received" in caplog.text
    assert fc.master is None
