"""
Live ArduPilot flight mode and RC switch slot.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from logging import debug as logging_debug
from time import monotonic
from typing import TYPE_CHECKING

from pymavlink.dialects.v20.ardupilotmega import (
    MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
    MAV_SYS_STATUS_SENSOR_RC_RECEIVER,
    MAV_TYPE_FIXED_WING,
)
from pymavlink.mavutil import mode_mapping_bynumber

from ardupilot_methodic_configurator.plugins.backend_rc_telemetry import RCTelemetryBackend

if TYPE_CHECKING:
    from pymavlink.dialects.v20.ardupilotmega import MAVLink_rc_channels_message

    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

_SWITCH_THRESHOLDS = (1231, 1361, 1491, 1621, 1750)
_MIN_PWM = 800
_MAX_PWM = 2200
_MAX_CHANNELS = 18
_TELEMETRY_TIMEOUT = 3.0
_RECEIVER_BIT = MAV_SYS_STATUS_SENSOR_RC_RECEIVER


@dataclass(frozen=True)
class FlightModesState:
    """The FC's active mode and the slot indicated by the RC mode switch."""

    mode_name: str | None = None
    mode_number: int | None = None
    switch_slot: str | None = None


@dataclass
class _TelemetryState:
    """Cached telemetry and polling state for the flight-modes model."""

    mode: tuple[str | None, int, float] | None = None
    channels: tuple["MAVLink_rc_channels_message", float] | None = None
    rc_failsafe: bool = False
    last_poll: float | None = None
    discard_buffered: bool = False


class FlightModesDataModel:
    """Report live flight-mode status without editing parameters or changing modes."""

    def __init__(self, flight_controller: "FlightController", clock: Callable[[], float] = monotonic) -> None:
        self._flight_controller = flight_controller
        self._telemetry = RCTelemetryBackend(flight_controller)
        self._clock = clock
        self._state = _TelemetryState()

    def _clear_readings(self) -> None:
        self._state.mode = None
        self._state.channels = None

    def stop_monitoring(self, *, restore_intervals: bool = True) -> None:
        """Discard mode and PWM samples, retaining known failsafe on the same connection."""
        try:
            self._telemetry.stop_monitoring(restore_intervals=restore_intervals)
        finally:
            self._clear_readings()

    def _read_telemetry(self) -> None:
        for message in self._telemetry.get_rc_telemetry():
            message_type = message.get_type()
            if message_type == "HEARTBEAT":
                if message.base_mode & MAV_MODE_FLAG_CUSTOM_MODE_ENABLED:
                    parameters = self._flight_controller.fc_parameters
                    # Q_MAV_TYPE can change the advertised frame without changing the Plane mode numbers.
                    is_quadplane = "Q_ENABLE" in parameters or "Q_MAV_TYPE" in parameters
                    modes = mode_mapping_bynumber(MAV_TYPE_FIXED_WING if is_quadplane else message.type) or {}
                    number = int(message.custom_mode)
                    self._state.mode = (modes.get(number), number, self._clock())
                else:
                    self._state.mode = None
            elif message_type == "RC_CHANNELS":
                self._state.channels = (message, self._clock())
            elif message_type == "SYS_STATUS":
                enabled = message.onboard_control_sensors_present & message.onboard_control_sensors_enabled & _RECEIVER_BIT
                healthy = message.onboard_control_sensors_health & _RECEIVER_BIT
                if enabled and not healthy:
                    self._state.rc_failsafe = True
                    self._state.channels = None
                elif enabled and healthy and self._state.rc_failsafe:
                    self._state.rc_failsafe = False
                    self._state.channels = None

    def _switch_slot(self, now: float) -> str | None:
        samples = self._state.channels
        if self._state.rc_failsafe or samples is None or now - samples[1] >= _TELEMETRY_TIMEOUT:
            return None
        parameters = self._flight_controller.fc_parameters
        rover = "MODE_CH" in parameters
        channel = parameters.get("MODE_CH" if rover else "FLTMODE_CH", 0)
        if not 1 <= channel <= _MAX_CHANNELS or int(channel) != channel:
            return None
        # ArduPilot reports the physical receiver count even when overrides populate higher channels.
        pwm = getattr(samples[0], f"chan{int(channel)}_raw", 0)
        if not _MIN_PWM < pwm < _MAX_PWM:
            return None
        prefix = "MODE" if rover else "FLTMODE"
        return f"{prefix}{bisect_right(_SWITCH_THRESHOLDS, pwm) + 1}"

    def get_flight_modes(self) -> FlightModesState:
        """Read a bounded telemetry batch and independently expire stale mode and switch values."""
        if self._telemetry.sync_connection():
            self._clear_readings()
            self._state.rc_failsafe = False
            self._state.last_poll = None
            self._state.discard_buffered = False
        if self._state.last_poll is not None and self._clock() - self._state.last_poll >= _TELEMETRY_TIMEOUT:
            # After a polling gap the receive queue may still hold samples from before the gap.
            self._clear_readings()
            self._state.discard_buffered = True
        try:
            if self._state.discard_buffered:
                self._state.discard_buffered = not self._telemetry.discard_pending_telemetry()
            else:
                self._read_telemetry()
        except (OSError, AttributeError, TypeError, ValueError) as exc:
            logging_debug("Error reading flight mode telemetry: %s", exc)
            self._clear_readings()
        now = self._clock()
        self._state.last_poll = now
        slot = self._switch_slot(now)
        if self._state.mode is None or now - self._state.mode[2] >= _TELEMETRY_TIMEOUT:
            return FlightModesState(switch_slot=slot)
        name, number, _received_at = self._state.mode
        return FlightModesState(name, number, slot)
