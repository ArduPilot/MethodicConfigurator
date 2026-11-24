"""
MAVLink servo-output and flight-mode telemetry for the control surface setup plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Allister779

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterator
from logging import debug as logging_debug
from typing import Any, cast

from ardupilot_methodic_configurator.plugins.backend_rc_telemetry import RCTelemetryBackend

_MAX_MESSAGES_PER_POLL = 50
_SERVO_TELEMETRY_TYPES = frozenset({"SERVO_OUTPUT_RAW", "HEARTBEAT"})


class ServoTelemetryBackend(RCTelemetryBackend):
    """Own the SERVO_OUTPUT_RAW stream lifecycle and read packets from the selected FC."""

    def stop_monitoring(self) -> None:
        """Restore the default stream interval, only on the connection whose interval we requested."""
        if self._stream_requested and self.flight_controller.master is self.connection:
            success, error = self.flight_controller.request_servo_output_messages(0)
            if not success:
                logging_debug("Could not restore servo output telemetry interval: %s", error)
        self._stream_requested = False

    def get_servo_telemetry(self) -> Iterator[Any]:
        """Yield SERVO_OUTPUT_RAW and HEARTBEAT packets in a bounded, nonblocking batch."""
        self.sync_connection()
        master = cast("Any", self.connection)
        if master is None:
            return
        if not self._stream_requested:
            self._stream_requested = True
            success, error = self.flight_controller.request_servo_output_messages(100_000)
            if not success:
                logging_debug("Could not request servo output telemetry interval: %s", error)

        for _index in range(_MAX_MESSAGES_PER_POLL):
            # A type filter can consume an unbounded unrelated backlog inside pymavlink.
            message = master.recv_match(blocking=False)
            if message is None:
                break
            if message.get_type() in _SERVO_TELEMETRY_TYPES and self.is_selected_source(message):
                yield message
