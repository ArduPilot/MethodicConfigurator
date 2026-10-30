"""
Reusable bounded ESC telemetry requests over the flight-controller facade.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from logging import debug as logging_debug
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

from pymavlink.dialects.v20 import ardupilotmega as mavlink
from serial import SerialException

from ardupilot_methodic_configurator.data_model_esc_telemetry import (
    ESC_FIELDS,
    MAX_ESCS,
    EscTelemetryReading,
    EscTelemetrySnapshot,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

ESC_MESSAGE_OFFSETS = {f"ESC_TELEMETRY_{start}_TO_{start + 3}": start - 1 for start in range(1, MAX_ESCS + 1, 4)}
_UNKNOWN_ESC_MESSAGES = {f"UNKNOWN_{getattr(mavlink, f'MAVLINK_MSG_ID_{name}')}" for name in ESC_MESSAGE_OFFSETS}


class EscTelemetryBackend:
    """Observe ESC packets without opening another connection or changing stream rates."""

    def __init__(self, flight_controller: "FlightController", clock: Callable[[], float] = monotonic) -> None:
        self.flight_controller = flight_controller
        self._clock = clock
        self._master: Any = None
        self._last_request: float | None = None
        self._readings: dict[int, EscTelemetryReading] = {}
        self._decoder = mavlink.MAVLink(None)

    def close(self) -> None:
        """Remove only this observer and reset request timing."""
        if self._master is not None and self._capture in self._master.message_hooks:
            self._master.message_hooks.remove(self._capture)
        self._master = None
        self._last_request = None
        self._readings.clear()

    def _target_ids(self, master: Any) -> tuple[int, int]:  # noqa: ANN401
        """Prefer discovered FC identity while retaining broadcast discovery targets."""
        info = self.flight_controller.info
        return (
            int(info.system_id) if info.system_id else int(master.target_system),
            int(info.component_id) if info.component_id else int(master.target_component),
        )

    def _capture(self, master: Any, message: Any) -> None:  # noqa: ANN401
        if message.get_type() in _UNKNOWN_ESC_MESSAGES:
            # A connection that initially detected MAVLink 1 can still receive
            # MAVLink 2 frames, but its v1 dialect does not know ESC message IDs.
            # Decode and validate the original packet without replacing the
            # shared parser or disturbing other connection consumers.
            try:
                self._decoder.signing = master.mav.signing
                message = self._decoder.decode(bytearray(message.get_msgbuf()))
            except mavlink.MAVError as exc:
                logging_debug("Invalid ESC telemetry packet: %s", exc)
                return
        offset = ESC_MESSAGE_OFFSETS.get(str(message.get_type()))
        if offset is None:
            return
        system_id, component_id = self._target_ids(master)
        if system_id > 0 and message.get_srcSystem() != system_id:
            return
        if component_id > 0 and message.get_srcComponent() != component_id:
            return
        fields = [getattr(message, name) for name in ESC_FIELDS]
        received_at = self._clock()
        for position in range(4):
            self._readings[offset + position] = EscTelemetryReading(
                tuple(int(values[position]) for values in fields), received_at=received_at
            )

    def poll(self) -> EscTelemetrySnapshot:
        """Request all groups once per second and drain at most 200 packets/10 ms."""
        # This observer lifecycle and MAVLink command layout intentionally match other backends.
        # pylint: disable=duplicate-code
        master = cast("Any", self.flight_controller.master)
        if master is not self._master:
            self.close()
            self._master = master
            if master is not None:
                master.message_hooks.append(self._capture)
        if master is None:
            return EscTelemetrySnapshot(None, self._clock())
        try:
            now = self._clock()
            if self._last_request is None or now - self._last_request >= 1.0:
                # ArduPilot maps this first group to its shared sender for ALL ESC groups.
                system_id, component_id = self._target_ids(master)
                # ESC_TELEMETRY_* IDs require MAVLink 2. Encode this request
                # as v2 even if the link initially negotiated MAVLink 1.
                master.mav.send(
                    mavlink.MAVLink_command_long_message(
                        system_id,
                        component_id,
                        mavlink.MAV_CMD_REQUEST_MESSAGE,
                        0,
                        mavlink.MAVLINK_MSG_ID_ESC_TELEMETRY_1_TO_4,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                    )
                )
                self._last_request = now
            deadline = self._clock() + 0.01
            for _index in range(200):
                if self._clock() >= deadline or master.recv_match(blocking=False) is None:
                    break
            readings, self._readings = self._readings, {}
            return EscTelemetrySnapshot(master, self._clock(), readings)
        except (OSError, SerialException, AttributeError, TypeError, ValueError) as exc:
            logging_debug("Error reading ESC telemetry: %s", exc)
            self.close()
            return EscTelemetrySnapshot(master, self._clock(), error=True)
