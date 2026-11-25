#!/usr/bin/env python3
"""
Verify the active mode and RC switch telemetry on the flight modes step.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from telemetry_test_helpers import rc_channels_message

from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.plugins.data_model_flight_modes import FlightModesDataModel, FlightModesState
from ardupilot_methodic_configurator.plugins.frontend_tkinter_flight_modes import FlightModesView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_FLIGHT_MODES
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory


def _heartbeat(
    number: int, vehicle: int = mavlink.MAV_TYPE_QUADROTOR, source_system: int = 1
) -> mavlink.MAVLink_heartbeat_message:
    message = mavlink.MAVLink_heartbeat_message(
        vehicle,
        mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        number,
        mavlink.MAV_STATE_ACTIVE,
        3,
    )
    message._header.srcSystem = source_system  # pylint: disable=protected-access
    message._header.srcComponent = 1  # pylint: disable=protected-access
    return message


@pytest.mark.parametrize(
    ("pwm", "slot"),
    [
        (800, None),
        (801, "FLTMODE1"),
        (1230, "FLTMODE1"),
        (1231, "FLTMODE2"),
        (1360, "FLTMODE2"),
        (1361, "FLTMODE3"),
        (1490, "FLTMODE3"),
        (1491, "FLTMODE4"),
        (1620, "FLTMODE4"),
        (1621, "FLTMODE5"),
        (1749, "FLTMODE5"),
        (1750, "FLTMODE6"),
        (2199, "FLTMODE6"),
        (2200, None),
        (65535, None),
    ],
)
def test_switch_slot_follows_firmware_pwm_boundaries(rc_controller: MagicMock, pwm: int, slot: str | None) -> None:
    """
    Identify the switch slot even when several assignments use the same mode.

    GIVEN: A mode switch assigned to CH8 and duplicate flight mode assignments
    WHEN: The configured channel reports a PWM value
    THEN: The user sees the slot implied by that PWM and the reported active mode
    """
    rc_controller.fc_parameters = {"FLTMODE_CH": 8.0, "FLTMODE1": 0.0, "FLTMODE2": 0.0}
    rc_controller.master.recv_match.side_effect = [_heartbeat(0), rc_channels_message([1800] * 7 + [pwm]), None]

    state = FlightModesDataModel(rc_controller).get_flight_modes()

    assert state == FlightModesState("STABILIZE", 0, slot)
    rc_controller.set_param.assert_not_called()


def test_quadplane_uses_plane_modes_with_a_quadrotor_heartbeat(rc_controller: MagicMock) -> None:
    """
    Show the Plane mode when a QuadPlane advertises a quadrotor frame.

    GIVEN: A QuadPlane configured to advertise MAV_TYPE_QUADROTOR
    WHEN: Its heartbeat reports custom mode 6
    THEN: The active mode is FBWB
    """
    rc_controller.fc_parameters = {"FLTMODE_CH": 8.0, "Q_ENABLE": 1.0, "Q_MAV_TYPE": 2.0}
    rc_controller.master.recv_match.side_effect = [_heartbeat(6, mavlink.MAV_TYPE_QUADROTOR), None]

    assert FlightModesDataModel(rc_controller).get_flight_modes() == FlightModesState("FBWB", 6)


def test_mode_switch_can_use_an_override_above_the_receiver_channel_count(rc_controller: MagicMock) -> None:
    """
    Show the switch position from an override beyond the physical receiver channels.

    GIVEN: A six-channel receiver and a mode switch configured on channel 8
    WHEN: An override supplies PWM for channel 8
    THEN: The switch slot reflects that PWM
    """
    rc_controller.fc_parameters = {"FLTMODE_CH": 8.0}
    rc_controller.master.recv_match.side_effect = [
        rc_channels_message([1500] * 6 + [0, 1800], chancount=6),
        None,
    ]

    assert FlightModesDataModel(rc_controller).get_flight_modes() == FlightModesState(switch_slot="FLTMODE6")


def test_active_mode_and_switch_expire_independently(rc_controller: MagicMock) -> None:
    """
    Keep the numerically reported mode visible while the RC data is stale.

    GIVEN: A Plane with a valid switch sample and a fresh heartbeat with an unknown mode number
    WHEN: The RC sample expires before the heartbeat
    THEN: The numeric mode remains visible and the switch slot becomes unavailable
    """
    rc_controller.fc_parameters = {"FLTMODE_CH": 8.0}
    clock = MagicMock(return_value=10.0)
    model = FlightModesDataModel(rc_controller, clock)
    receiver = rc_controller.master.recv_match
    receiver.side_effect = [rc_channels_message([1500] * 8), None]
    assert model.get_flight_modes().switch_slot == "FLTMODE4"
    receiver.side_effect = [None]
    clock.return_value = 12.0
    assert model.get_flight_modes().switch_slot == "FLTMODE4"
    receiver.side_effect = [_heartbeat(1234, mavlink.MAV_TYPE_FIXED_WING), _heartbeat(0, source_system=2), None]
    clock.return_value = 13.0

    assert model.get_flight_modes() == FlightModesState(None, 1234)
    receiver.side_effect = [None]
    clock.return_value = 15.0
    assert model.get_flight_modes() == FlightModesState(None, 1234)
    receiver.side_effect = [None]
    clock.return_value = 16.0
    assert model.get_flight_modes() == FlightModesState()


def test_resuming_after_telemetry_backlog_requires_fresh_readings(rc_controller: MagicMock) -> None:
    """
    Keep live readings unavailable while clearing packets queued during a pause.

    GIVEN: The plugin displayed an active mode and switch slot before polling paused
    WHEN: Polling resumes after the readings expire with multiple batches of packets queued
    THEN: The readings stay unavailable until newly arriving packets report them
    """
    rc_controller.fc_parameters = {"FLTMODE_CH": 5.0}
    clock = MagicMock(return_value=10.0)
    model = FlightModesDataModel(rc_controller, clock)
    receiver = rc_controller.master.recv_match
    previous_readings = [_heartbeat(6), rc_channels_message([1800] * 5)]
    receiver.side_effect = [*previous_readings, None]
    assert model.get_flight_modes() == FlightModesState("RTL", 6, "FLTMODE6")

    clock.return_value = 13.0
    receiver.side_effect = [*(previous_readings * 60), None, None]
    for _ in range(4):
        assert model.get_flight_modes() == FlightModesState()

    receiver.side_effect = [_heartbeat(0), rc_channels_message([1000] * 5), None]
    assert model.get_flight_modes() == FlightModesState("STABILIZE", 0, "FLTMODE1")


def test_failsafe_and_disabled_channel_make_switch_slot_unavailable(rc_controller: MagicMock) -> None:
    """
    Hide the switch slot when ArduPilot reports a receiver failsafe or disables the mode channel.

    GIVEN: A Plane in RTL and a configured receiver that still reports PWM during failsafe
    WHEN: The mode is monitored during failsafe and later with the mode channel disabled
    THEN: The active mode remains visible in both cases and the switch slot is unavailable
    """
    rc_controller.fc_parameters = {"FLTMODE_CH": 7.0}
    rc_bit = mavlink.MAV_SYS_STATUS_SENSOR_RC_RECEIVER
    failsafe = mavlink.MAVLink_sys_status_message(rc_bit, rc_bit, 0, *([0] * 10))
    failsafe._header.srcSystem = failsafe._header.srcComponent = 1  # pylint: disable=protected-access
    receiver = rc_controller.master.recv_match
    receiver.side_effect = [
        _heartbeat(11, mavlink.MAV_TYPE_FIXED_WING),
        failsafe,
        rc_channels_message([1750] * 7),
        None,
    ]
    model = FlightModesDataModel(rc_controller)
    assert model.get_flight_modes() == FlightModesState("RTL", 11)

    model.stop_monitoring()
    rc_controller.fc_parameters["FLTMODE_CH"] = 0.0
    receiver.side_effect = [_heartbeat(11, mavlink.MAV_TYPE_FIXED_WING), rc_channels_message([1750] * 7), None]

    assert model.get_flight_modes() == FlightModesState("RTL", 11)


def test_switch_slot_stays_hidden_until_receiver_recovers(rc_controller: MagicMock) -> None:
    """
    Require receiver recovery before showing the switch again.

    GIVEN: The controller reports a receiver failsafe
    WHEN: Status messages stop but RC packets still arrive
    THEN: The slot stays hidden until a healthy status and fresh RC packet arrive
    """
    rc_controller.fc_parameters = {"FLTMODE_CH": 5.0}
    receiver_bit = mavlink.MAV_SYS_STATUS_SENSOR_RC_RECEIVER
    failsafe = mavlink.MAVLink_sys_status_message(receiver_bit, receiver_bit, 0, *([0] * 10))
    healthy = mavlink.MAVLink_sys_status_message(receiver_bit, receiver_bit, receiver_bit, *([0] * 10))
    for message in (failsafe, healthy):
        message._header.srcSystem = message._header.srcComponent = 1  # pylint: disable=protected-access
    clock = MagicMock(return_value=10.0)
    model = FlightModesDataModel(rc_controller, clock)
    receiver = rc_controller.master.recv_match
    pwm = rc_channels_message([1800] * 5)
    receiver.side_effect = [failsafe, pwm, None]
    assert model.get_flight_modes().switch_slot is None

    clock.return_value = 14.0
    receiver.side_effect = [pwm, None]
    assert model.get_flight_modes().switch_slot is None
    receiver.side_effect = [healthy, None]
    assert model.get_flight_modes().switch_slot is None
    receiver.side_effect = [pwm, None]
    assert model.get_flight_modes().switch_slot == "FLTMODE6"


@pytest.mark.parametrize(
    ("vehicle_type", "filename"),
    [
        ("ArduCopter", "22_flight_modes.param"),
        ("ArduPlane", "22_flight_modes.param"),
        ("Heli", "25_flight_modes.param"),
        ("Rover", "18_flight_modes.param"),
    ],
)
def test_flight_modes_step_places_the_plugin_above_the_table(vehicle_type: str, filename: str) -> None:
    """
    Load the plugin at the top of the flight modes step.

    GIVEN: A bundled configuration for a vehicle with a 22_flight_modes.param step
    WHEN: The editor loads that step
    THEN: Its configuration places the registered plugin above the parameter table
    """
    configuration = Path("ardupilot_methodic_configurator") / f"configuration_steps_{vehicle_type}.json"
    steps = json.loads(configuration.read_text(encoding="utf-8"))["steps"]

    assert steps[filename]["plugin"] == {"name": PLUGIN_FLIGHT_MODES, "placement": "top"}


def test_rover_shows_its_mode_switch_slot(rc_controller: MagicMock) -> None:
    """
    Display Rover's mode channel and slot.

    GIVEN: A Rover with its mode switch on channel 8
    WHEN: It reports HOLD and a PWM selecting the sixth slot
    THEN: The display identifies the active mode and MODE6
    """
    rc_controller.fc_parameters = {"MODE_CH": 8.0}
    rc_controller.master.recv_match.side_effect = [
        _heartbeat(4, mavlink.MAV_TYPE_GROUND_ROVER),
        rc_channels_message([1500] * 7 + [1800]),
        None,
    ]
    assert FlightModesDataModel(rc_controller).get_flight_modes() == FlightModesState("HOLD", 4, "MODE6")


def test_registered_view_shows_and_clears_live_readings(
    root: tk.Tk,
    rc_controller: MagicMock,
    fire_tk_timer: Callable[[tk.Misc, str], None],
    pause_polling_plugin_for_recovery: Callable[[tk.Misc], Callable[[], None]],
) -> None:
    """
    Show the active flight mode name, number and switch slot in the real widget.

    GIVEN: The editor creates the registered plugin with a connected flight controller
    WHEN: The plugin polls telemetry and then yields the connection
    THEN: It displays the reported values, clears them when paused and stops its timer
    """
    register_plugins()
    assert plugin_factory.requires_flight_controller(PLUGIN_FLIGHT_MODES)
    context = PluginModelContext(rc_controller, MagicMock(), MagicMock())
    model = plugin_factory.create_model(PLUGIN_FLIGHT_MODES, context)
    base_window = MagicMock(navigation_lock=NavigationLock())
    rc_controller.fc_parameters = {"FLTMODE_CH": 5.0}
    rc_controller.master.recv_match.side_effect = [_heartbeat(6), rc_channels_message([1700] * 5), None]

    with (
        patch("tkinter.Misc.update"),
        patch("tkinter.Misc.update_idletasks"),
        patch("tkinter.Misc.wait_visibility"),
        patch("tkinter.Misc.wait_window"),
    ):
        parent = ttk.Frame(root)
        view = plugin_factory.create(PLUGIN_FLIGHT_MODES, parent, model, base_window)
        assert isinstance(view, FlightModesView)
        try:
            view.on_activate()
            owner = object()
            base_window.navigation_lock.acquire(owner)
            timer = view._timer_id  # pylint: disable=protected-access
            assert timer is not None
            fire_tk_timer(view, timer)
            rc_controller.master.recv_match.assert_not_called()
            base_window.navigation_lock.release(owner)

            parent.grab_set()
            try:
                timer = view._timer_id  # pylint: disable=protected-access
                assert timer is not None
                fire_tk_timer(view, timer)
                rc_controller.master.recv_match.assert_not_called()
            finally:
                parent.grab_release()

            timer = view._timer_id  # pylint: disable=protected-access
            assert timer is not None
            fire_tk_timer(view, timer)
            assert view.active_mode.cget("text") == "Active flight mode: RTL (6)"
            assert view.switch_slot.cget("text") == "RC switch slot: FLTMODE5"

            resume = pause_polling_plugin_for_recovery(view)
            assert view.switch_slot.cget("text") == "RC switch slot: Unavailable"
            assert view.active_mode.cget("text") == "Active flight mode: Unavailable"
            assert view._timer_id is None  # pylint: disable=protected-access
            rc_controller.request_rc_receiver_messages.assert_called_once_with()

            resume()
            rc_controller.master.recv_match.side_effect = [None]
            timer = view._timer_id  # pylint: disable=protected-access
            assert timer is not None
            fire_tk_timer(view, timer)
            view.on_deactivate()
            rc_controller.request_rc_receiver_messages.assert_called_with(0)
        finally:
            parent.destroy()
