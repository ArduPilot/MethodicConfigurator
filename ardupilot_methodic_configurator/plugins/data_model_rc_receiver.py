"""
Live receiver checks independent of the GUI and parameter editing.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from dataclasses import dataclass
from logging import debug as logging_debug
from time import monotonic
from typing import TYPE_CHECKING, Any

from pymavlink.dialects.v20.ardupilotmega import MAV_SYS_STATUS_SENSOR_RC_RECEIVER

from ardupilot_methodic_configurator.plugins.backend_rc_telemetry import RCTelemetryBackend, rc_channel_values

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

_CHANNEL_COUNT = 5
_TELEMETRY_TIMEOUT = 3.0
_RC_RECEIVER = MAV_SYS_STATUS_SENSOR_RC_RECEIVER


@dataclass(frozen=True)
class RCReceiverState:
    """Immutable display data; None means unavailable, never a successful check."""

    connected: bool = False
    channels: tuple[int | None, ...] = (None,) * _CHANNEL_COUNT
    rssi: int | None = None
    receiving_channels: bool = False
    receiver_present: bool | None = None
    failsafe: bool | None = None
    failsafe_detected: bool = False


class RCReceiverDataModel:  # pylint: disable=too-many-instance-attributes
    """Read only RC_CHANNELS and receiver SYS_STATUS from the shared FC facade."""

    def __init__(self, flight_controller: "FlightController", clock: Callable[[], float] = monotonic) -> None:
        self.flight_controller = flight_controller
        self._clock = clock
        self._telemetry = RCTelemetryBackend(flight_controller)
        self._channels: tuple[int | None, ...] = (None,) * _CHANNEL_COUNT
        self._rssi: int | None = None
        self._rc_time: float | None = None
        self._status_time: float | None = None
        self._receiver_present: bool | None = None
        self._failsafe: bool | None = None
        self._failsafe_detected = False

    def clear_live_data(self) -> None:
        """Invalidate hidden/stale readings, preserving the test's failsafe evidence."""
        self._channels = (None,) * _CHANNEL_COUNT
        self._rssi = None
        self._rc_time = None
        self._status_time = None
        self._receiver_present = None
        self._failsafe = None

    def stop_monitoring(self) -> None:
        """Restore default stream rates and invalidate readings when yielding the link."""
        self._telemetry.stop_monitoring()
        self.clear_live_data()

    def _read_channels(self, message: Any, now: float) -> None:  # noqa: ANN401
        raw = rc_channel_values(message, _CHANNEL_COUNT)
        count = len(raw)
        self._channels = tuple(raw[i] if i < count and 0 < raw[i] < 65535 else None for i in range(_CHANNEL_COUNT))
        rssi = int(message.rssi)
        self._rssi = rssi if 0 <= rssi <= 254 else None
        self._rc_time = now

    def _read_status(self, message: Any, now: float) -> None:  # noqa: ANN401
        self._receiver_present = bool(message.onboard_control_sensors_present & _RC_RECEIVER)
        enabled = bool(message.onboard_control_sensors_enabled & _RC_RECEIVER)
        healthy = bool(message.onboard_control_sensors_health & _RC_RECEIVER)
        self._failsafe = not healthy if self._receiver_present and enabled else None
        self._failsafe_detected |= self._failsafe is True
        self._status_time = now

    def get_receiver_state(self) -> RCReceiverState:
        """Poll without blocking; expire each stream independently and bound work per GUI tick."""
        if self._telemetry.sync_connection():
            self.clear_live_data()
            self._failsafe_detected = False
        if self._telemetry.connection is None:
            return RCReceiverState()

        now = self._clock()
        try:
            for message in self._telemetry.get_rc_telemetry():
                if not self._telemetry.is_selected_source(message):
                    continue
                if message.get_type() == "RC_CHANNELS":
                    self._read_channels(message, now)
                elif message.get_type() == "SYS_STATUS":
                    self._read_status(message, now)
        except (OSError, AttributeError, TypeError, ValueError) as exc:
            logging_debug("Error reading RC receiver telemetry: %s", exc)
            self.clear_live_data()

        rc_fresh = self._rc_time is not None and now - self._rc_time < _TELEMETRY_TIMEOUT
        status_fresh = self._status_time is not None and now - self._status_time < _TELEMETRY_TIMEOUT
        return RCReceiverState(
            connected=True,
            channels=self._channels if rc_fresh else (None,) * _CHANNEL_COUNT,
            rssi=self._rssi if rc_fresh else None,
            receiving_channels=rc_fresh and any(value is not None for value in self._channels),
            receiver_present=self._receiver_present if status_fresh else None,
            failsafe=self._failsafe if status_fresh else None,
            failsafe_detected=self._failsafe_detected,
        )
