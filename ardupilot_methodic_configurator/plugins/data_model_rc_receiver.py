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
from typing import TYPE_CHECKING, Any, cast

from pymavlink.dialects.v20.ardupilotmega import MAV_SYS_STATUS_SENSOR_RC_RECEIVER

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

_CHANNEL_COUNT = 5
_TELEMETRY_TIMEOUT = 3.0
_MAX_MESSAGES_PER_POLL = 50
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
        self._connection: object | None = None
        self._stream_requested = False
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
        if self._stream_requested and self.flight_controller.master is self._connection:
            success, error = self.flight_controller.request_rc_receiver_messages(0)
            if not success:
                logging_debug("Could not restore RC receiver telemetry intervals: %s", error)
        self._stream_requested = False
        self.clear_live_data()

    def _read_channels(self, message: Any, now: float) -> None:  # noqa: ANN401
        count = max(0, min(int(message.chancount), _CHANNEL_COUNT))
        raw = [int(getattr(message, f"chan{channel}_raw")) for channel in range(1, count + 1)]
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
        master = cast("Any", self.flight_controller.master)
        if master is not self._connection:
            self.clear_live_data()
            self._failsafe_detected = False
            self._connection = master
            self._stream_requested = False
        if master is None:
            return RCReceiverState()

        if not self._stream_requested:
            # Request once per activation/connection, even if only one command is accepted.
            # Telemetry remains usable when older firmware rejects interval requests.
            self._stream_requested = True
            success, error = self.flight_controller.request_rc_receiver_messages()
            if not success:
                logging_debug("Could not request RC receiver telemetry intervals: %s", error)

        info = self.flight_controller.info
        system_id, component_id = info.system_id, info.component_id
        target_system = int(system_id) if isinstance(system_id, str) and system_id else master.target_system
        target_component = int(component_id) if isinstance(component_id, str) and component_id else master.target_component
        now = self._clock()
        try:
            for _index in range(_MAX_MESSAGES_PER_POLL):
                # Count every packet: a type filter can drain an unbounded unrelated backlog.
                message = master.recv_match(blocking=False)
                if message is None:
                    break
                if not isinstance(target_system, int) or target_system <= 0 or message.get_srcSystem() != target_system:
                    continue
                if (
                    isinstance(target_component, int)
                    and target_component > 0
                    and message.get_srcComponent() != target_component
                ):
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
