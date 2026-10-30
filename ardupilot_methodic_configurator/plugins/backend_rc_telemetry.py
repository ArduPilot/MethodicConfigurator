"""
Shared MAVLink telemetry transport for RC monitoring and calibration.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterator
from logging import debug as logging_debug
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

_MAX_MESSAGES_PER_POLL = 50


def rc_channel_values(message: Any, channel_count: int) -> list[int]:  # noqa: ANN401
    """Decode only advertised RC channels, capped at the consumer's display limit."""
    count = max(0, min(int(message.chancount), channel_count))
    return [int(getattr(message, f"chan{channel}_raw")) for channel in range(1, count + 1)]


class RCTelemetryBackend:
    """Own one monitor's stream lifecycle and bounded reads from the shared MAVLink link."""

    def __init__(self, flight_controller: "FlightController") -> None:
        self.flight_controller = flight_controller
        self.connection: object | None = None
        self._stream_requested = False

    def sync_connection(self) -> bool:
        """Reset stream ownership on a new connection; tell consumers to clear cached readings."""
        master = self.flight_controller.master
        if master is self.connection:
            return False
        self.connection = master
        self._stream_requested = False
        return True

    def stop_monitoring(self) -> None:
        """Restore defaults once, only on the connection whose intervals we requested."""
        if self._stream_requested and self.flight_controller.master is self.connection:
            success, error = self.flight_controller.request_rc_receiver_messages(0)
            if not success:
                logging_debug("Could not restore RC receiver telemetry intervals: %s", error)
        self._stream_requested = False

    def get_rc_telemetry(self) -> Iterator[Any]:
        """Yield every packet in a bounded, nonblocking batch, in order."""
        self.sync_connection()
        master = cast("Any", self.connection)
        if master is None:
            return
        if not self._stream_requested:
            # Older firmware may reject the interval request while already streaming data.
            self._stream_requested = True
            success, error = self.flight_controller.request_rc_receiver_messages()
            if not success:
                logging_debug("Could not request RC receiver telemetry intervals: %s", error)

        for _index in range(_MAX_MESSAGES_PER_POLL):
            # A type filter can consume an unbounded unrelated backlog inside pymavlink.
            message = master.recv_match(blocking=False)
            if message is None:
                break
            yield message

    def is_selected_source(self, message: Any) -> bool:  # noqa: ANN401
        """Identify receiver-health packets belonging to the selected flight controller."""
        master = cast("Any", self.connection)
        if master is None:
            return False
        info = self.flight_controller.info
        system_id, component_id = info.system_id, info.component_id
        target_system = int(system_id) if isinstance(system_id, str) and system_id else master.target_system
        target_component = int(component_id) if isinstance(component_id, str) and component_id else master.target_component
        if not isinstance(target_system, int) or target_system <= 0 or message.get_srcSystem() != target_system:
            return False
        return not (
            isinstance(target_component, int) and target_component > 0 and message.get_srcComponent() != target_component
        )
