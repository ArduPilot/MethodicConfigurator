#!/usr/bin/env python3
"""
Receiver connection, signal availability and failsafe behavior tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from jsonschema import validate
from pymavlink import mavutil

from ardupilot_methodic_configurator import data_model_parameter_editor as editor_module
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.plugins import frontend_tkinter_rc_receiver as frontend
from ardupilot_methodic_configurator.plugins.data_model_rc_receiver import RCReceiverDataModel, RCReceiverState
from ardupilot_methodic_configurator.plugins.frontend_tkinter_rc_receiver import register_rc_receiver_plugin
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_RC_RECEIVER
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory

# pylint: disable=protected-access,redefined-outer-name

_RC_BIT = mavutil.mavlink.MAV_SYS_STATUS_SENSOR_RC_RECEIVER
_PACKAGE = Path(__file__).resolve().parents[2] / "ardupilot_methodic_configurator"


def rc_message(channels: tuple[int, ...] = (1000, 1200, 1500, 1800, 2000), rssi: int = 127) -> Any:  # noqa: ANN401
    """Use real MAVLink fields, including unused channels and the source address."""
    message = mavutil.mavlink.MAVLink_rc_channels_message(
        0, len(channels), *(channels + (65535,) * (18 - len(channels))), rssi
    )
    message._header.srcSystem = 1
    message._header.srcComponent = 1
    return message


def status_message(present: int = _RC_BIT, enabled: int = _RC_BIT, health: int = _RC_BIT) -> Any:  # noqa: ANN401
    """Create actual receiver health telemetry without depending on other sensors."""
    message = mavutil.mavlink.MAVLink_sys_status_message(present, enabled, health, *([0] * 10))
    message._header.srcSystem = 1
    message._header.srcComponent = 1
    return message


@pytest.fixture
def receiver_context() -> SimpleNamespace:
    """Mock only transport and time; execute the real model and MAVLink messages."""
    messages: deque[Any] = deque()
    controller = MagicMock()
    controller.master.target_system = 1
    controller.master.target_component = 0
    controller.info.system_id = "1"
    controller.info.component_id = "1"
    controller.request_rc_receiver_messages.return_value = (True, "")
    controller.master.recv_match.side_effect = lambda **_kwargs: messages.popleft() if messages else None
    clock = MagicMock(return_value=100.0)
    return SimpleNamespace(controller=controller, clock=clock, messages=messages, model=RCReceiverDataModel(controller, clock))


def test_user_can_monitor_first_five_channels_without_writing_parameters(receiver_context: SimpleNamespace) -> None:
    """
    Monitor raw receiver input without parameter writes.

    GIVEN a receiver providing more than five channels,
    WHEN the monitor reads it,
    THEN only CH1-CH5 and receiver RSSI are exposed without parameter writes.
    """
    receiver_context.messages.extend([rc_message((1000, 1200, 1500, 1800, 2000, 1600)), status_message()])
    state = receiver_context.model.get_receiver_state()
    assert state.channels == (1000, 1200, 1500, 1800, 2000)
    assert state.rssi == 127
    assert state.receiving_channels
    assert state.receiver_present is True
    assert state.failsafe is False
    receiver_context.controller.set_param.assert_not_called()
    receiver_context.controller.request_rc_receiver_messages.assert_called_once_with()


@pytest.mark.parametrize(("rssi", "expected"), [(0, 0), (254, 254), (255, None)])
def test_rssi_distinguishes_zero_strength_from_unavailable(
    receiver_context: SimpleNamespace, rssi: int, expected: int | None
) -> None:
    """
    Preserve RSSI availability semantics.

    GIVEN valid RSSI endpoints or the MAVLink unknown sentinel,
    WHEN receiver data arrives,
    THEN zero stays visible and unavailable RSSI is explicitly absent.
    """
    receiver_context.messages.append(rc_message(rssi=rssi))
    assert receiver_context.model.get_receiver_state().rssi == expected


@pytest.mark.parametrize("channels", [(), (0, 65535), (1100, 0, 65535)])
def test_missing_channels_are_never_displayed_as_valid_centered_inputs(
    receiver_context: SimpleNamespace, channels: tuple[int, ...]
) -> None:
    """
    Expose missing channels explicitly.

    GIVEN absent or invalid channel samples,
    WHEN the receiver is polled,
    THEN no invented PWM values mask the missing channels.
    """
    receiver_context.messages.append(rc_message(channels))
    state = receiver_context.model.get_receiver_state()
    assert state.channels == ((1100, None, None, None, None) if channels == (1100, 0, 65535) else (None,) * 5)
    assert state.receiving_channels == (1100 in channels)
    assert state.failsafe is None


def test_transmitter_power_cycle_shows_failsafe_and_recovery_with_test_evidence(receiver_context: SimpleNamespace) -> None:
    """
    Retain evidence through a transmitter power cycle.

    GIVEN a working receiver and unrelated failing vehicle sensors,
    WHEN receiver health fails and later recovers,
    THEN RC failsafe follows only its own bit and retains evidence of the test.
    """
    receiver_context.messages.append(status_message())
    assert receiver_context.model.get_receiver_state().failsafe is False
    receiver_context.messages.append(status_message(health=0))
    failed = receiver_context.model.get_receiver_state()
    assert failed.failsafe is True
    assert failed.failsafe_detected
    receiver_context.messages.append(status_message())
    recovered = receiver_context.model.get_receiver_state()
    assert recovered.failsafe is False
    assert recovered.failsafe_detected


@pytest.mark.parametrize(("present", "enabled"), [(0, 0), (_RC_BIT, 0), (0, _RC_BIT)])
def test_unreported_or_disabled_receiver_is_not_mistaken_for_failsafe(
    receiver_context: SimpleNamespace, present: int, enabled: int
) -> None:
    """
    Distinguish unreported status from RC failsafe.

    GIVEN receiver status is not both present and enabled,
    WHEN SYS_STATUS arrives with no healthy receiver bit,
    THEN failsafe remains unknown rather than reporting success or failure.
    """
    receiver_context.messages.append(status_message(present, enabled, 0))
    state = receiver_context.model.get_receiver_state()
    assert state.failsafe is None
    assert not state.failsafe_detected


def test_each_stream_expires_independently_without_inventing_rc_failsafe(receiver_context: SimpleNamespace) -> None:
    """
    Expire channel and status telemetry independently.

    GIVEN healthy RC channels and receiver status,
    WHEN only channel telemetry continues and then all telemetry stops,
    THEN status becomes unknown first and stale bars clear without asserting failsafe.
    """
    receiver_context.messages.extend([rc_message(), status_message()])
    receiver_context.model.get_receiver_state()
    receiver_context.clock.return_value = 102.0
    assert receiver_context.model.get_receiver_state().receiving_channels
    receiver_context.clock.return_value = 103.0
    receiver_context.messages.append(rc_message())
    state = receiver_context.model.get_receiver_state()
    assert state.receiving_channels
    assert state.failsafe is None
    assert state.receiver_present is None
    receiver_context.clock.return_value = 106.0
    state = receiver_context.model.get_receiver_state()
    assert state.channels == (None,) * 5
    assert state.rssi is None
    assert not state.failsafe_detected


def test_disconnection_and_new_controller_clear_previous_test_results(receiver_context: SimpleNamespace) -> None:
    """
    Start a fresh test on a new connection.

    GIVEN failsafe has been observed on one flight controller,
    WHEN the FC disconnects and a new connection is supplied,
    THEN neither its live data nor its test evidence leaks into the next session.
    """
    receiver_context.messages.extend([rc_message(), status_message(health=0)])
    assert receiver_context.model.get_receiver_state().failsafe_detected
    receiver_context.controller.master = None
    assert receiver_context.model.get_receiver_state() == RCReceiverState()
    receiver_context.controller.master = MagicMock()
    receiver_context.controller.master.recv_match.return_value = None
    state = receiver_context.model.get_receiver_state()
    assert state.connected
    assert not state.failsafe_detected
    assert state.channels == (None,) * 5


@pytest.mark.parametrize("source", [(2, 1), (1, 42)])
def test_other_systems_and_components_cannot_supply_receiver_test_results(
    receiver_context: SimpleNamespace, source: tuple[int, int]
) -> None:
    """
    Accept receiver telemetry only from the selected FC.

    GIVEN another vehicle or component shares the link,
    WHEN it reports channels and RC failsafe,
    THEN this flight controller's test remains unknown.
    """
    messages = [rc_message(), status_message(health=0)]
    for message in messages:
        message._header.srcSystem, message._header.srcComponent = source
    receiver_context.messages.extend(messages)
    state = receiver_context.model.get_receiver_state()
    assert not state.receiving_channels
    assert state.failsafe is None
    assert not state.failsafe_detected


def test_queued_readings_show_latest_values_without_unbounded_gui_work(receiver_context: SimpleNamespace) -> None:
    """
    Keep polling responsive despite queued telemetry.

    GIVEN a backlog of RC telemetry,
    WHEN the GUI polls once,
    THEN it advances through queued samples but leaves bounded work for the next tick.
    """
    receiver_context.messages.extend(rc_message((1000 + i,) * 5) for i in range(60))
    assert receiver_context.model.get_receiver_state().channels == (1049,) * 5
    assert len(receiver_context.messages) == 10
    assert receiver_context.model.get_receiver_state().channels == (1059,) * 5


@pytest.mark.parametrize("discovered_component", ["", "0"])
def test_broadcast_component_accepts_receiver_telemetry_without_discovery(
    receiver_context: SimpleNamespace, discovered_component: str
) -> None:
    """
    Accept autopilot messages when the target component is broadcast.

    GIVEN no selected component and pymavlink's default target_component of zero,
    WHEN component 1 sends receiver telemetry,
    THEN both channels and receiver health are available.
    """
    receiver_context.controller.info.system_id = ""
    receiver_context.controller.info.component_id = discovered_component
    receiver_context.messages.extend([rc_message(), status_message()])
    state = receiver_context.model.get_receiver_state()
    assert state.receiving_channels
    assert state.failsafe is False


def test_discovered_vehicle_takes_precedence_over_transport_targets(receiver_context: SimpleNamespace) -> None:
    """
    Monitor the controller selected during discovery.

    GIVEN transport targets differ from the selected autopilot,
    WHEN the selected autopilot sends receiver telemetry,
    THEN discovery metadata identifies the accepted source.
    """
    receiver_context.controller.master.target_system = 42
    receiver_context.controller.master.target_component = 42
    receiver_context.messages.extend([rc_message(), status_message()])
    assert receiver_context.model.get_receiver_state().receiving_channels


def test_unrelated_backlog_cannot_monopolize_a_receiver_poll(receiver_context: SimpleNamespace) -> None:
    """
    Keep the GUI responsive even when unrelated traffic dominates the link.

    GIVEN a real pymavlink reader with 2000 unrelated packets before receiver data,
    WHEN the monitor polls once,
    THEN at most 50 packets are consumed and receiver data waits for later polls.
    """
    master = mavutil.mavfile(None, "receiver-test", input=False)
    master.target_system = 1
    master.target_component = 0
    # Use a message type outside the receiver filter to exercise pymavlink's actual draining behavior.
    unrelated = mavutil.mavlink.MAVLink_heartbeat_message(0, 0, 0, 0, 0, 3)
    master.recv_msg = MagicMock(side_effect=[unrelated] * 2000 + [rc_message(), None])
    receiver_context.controller.master = master
    assert not receiver_context.model.get_receiver_state().receiving_channels
    assert master.recv_msg.call_count == 50


def test_receiver_streams_are_requested_once_and_restored_when_monitor_pauses(receiver_context: SimpleNamespace) -> None:
    """
    Supply telemetry on default controllers and release the requested rates when paused.

    GIVEN a monitor that polls repeatedly,
    WHEN it pauses and later resumes,
    THEN streams are requested once per activation and firmware defaults are restored on pause.
    """
    request = receiver_context.controller.request_rc_receiver_messages
    receiver_context.model.get_receiver_state()
    receiver_context.model.get_receiver_state()
    request.assert_called_once_with()
    receiver_context.model.stop_monitoring()
    request.assert_called_with(0)
    receiver_context.model.stop_monitoring()
    assert request.call_count == 2
    receiver_context.model.get_receiver_state()
    assert request.call_count == 3
    request.assert_called_with()


def test_reconnection_requests_streams_without_restoring_rates_on_the_new_vehicle(receiver_context: SimpleNamespace) -> None:
    """
    Renew telemetry requests when the FC connection changes.

    GIVEN streams were requested on a previous controller,
    WHEN a different connection is supplied before pausing,
    THEN pause does not change its rates and the next poll requests its streams.
    """
    receiver_context.model.get_receiver_state()
    request = receiver_context.controller.request_rc_receiver_messages
    request.reset_mock()
    receiver_context.controller.master = MagicMock()
    receiver_context.controller.master.recv_match.return_value = None
    receiver_context.model.stop_monitoring()
    request.assert_not_called()
    receiver_context.model.get_receiver_state()
    request.assert_called_once_with()


def test_io_failure_clears_live_success_but_monitor_can_recover(receiver_context: SimpleNamespace) -> None:
    """
    Recover from a transient transport failure.

    GIVEN the FC was supplying channels,
    WHEN transport fails and later recovers,
    THEN old successes clear immediately and new telemetry restores the display.
    """
    receiver_context.messages.append(rc_message())
    receiver_context.model.get_receiver_state()
    receiver_context.controller.master.recv_match.side_effect = OSError("disconnected")
    state = receiver_context.model.get_receiver_state()
    assert not state.receiving_channels
    assert state.rssi is None
    receiver_context.controller.master.recv_match.side_effect = [rc_message(), None]
    assert receiver_context.model.get_receiver_state().receiving_channels


def test_registered_model_uses_shared_dispatch_and_requires_a_connected_fc(
    rc_staging_context: tuple[MagicMock, ParameterEditor],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Integrate through the shared plugin model dispatcher.

    GIVEN a normal parameter editor and the registered receiver plugin,
    WHEN its model is requested with and without a connection,
    THEN shared dispatch injects the FC and declines disconnected creation.
    """
    controller, editor = rc_staging_context
    factory = PluginFactory()
    monkeypatch.setattr(frontend, "plugin_factory", factory)
    monkeypatch.setattr(editor_module, "plugin_factory", factory)
    register_rc_receiver_plugin()
    model = editor.create_plugin_data_model(PLUGIN_RC_RECEIVER)
    assert isinstance(model, RCReceiverDataModel)
    assert model.flight_controller is controller
    controller.master = None
    assert editor.create_plugin_data_model(PLUGIN_RC_RECEIVER) is None


@pytest.mark.parametrize("vehicle", ["ArduCopter", "ArduPlane", "Heli", "Rover"])
def test_receiver_step_is_wired_and_schema_valid_for_each_vehicle(vehicle: str) -> None:
    """
    Make receiver monitoring available in each supported vehicle workflow.

    GIVEN a bundled vehicle configuration,
    WHEN the receiver connection step is selected,
    THEN the schema accepts rc_receiver alongside the existing parameter controls.
    """
    configuration = json.loads((_PACKAGE / f"configuration_steps_{vehicle}.json").read_text(encoding="utf-8"))
    schema = json.loads((_PACKAGE / "configuration_steps_schema.json").read_text(encoding="utf-8"))
    validate(configuration, schema)
    steps = configuration["steps"]
    assert steps["06_remote_controller_receiver.param"]["plugin"] == {"name": "rc_receiver", "placement": "left"}


@pytest.mark.parametrize("platform", ["windows", "linux", "macos"])
def test_frozen_build_collects_dynamic_receiver_modules(platform: str) -> None:
    """
    Preserve dynamic plugin collection in every frozen build.

    GIVEN a platform's frozen build configuration,
    WHEN plugin modules are imported dynamically,
    THEN the entire plugins package is included by its existing collection rule.
    """
    spec = (_PACKAGE.parent / platform / "ardupilot_methodic_configurator.spec").read_text(encoding="utf-8")
    assert 'collect_submodules("ardupilot_methodic_configurator.plugins")' in spec.replace("'", '"')
