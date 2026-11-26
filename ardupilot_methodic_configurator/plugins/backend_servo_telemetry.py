"""
MAVLink servo-output and flight-mode telemetry for the control surface setup plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Allister779

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterator
from logging import debug as logging_debug
from typing import Any

from ardupilot_methodic_configurator.plugins.backend_rc_telemetry import RCTelemetryBackend

_SERVO_OUTPUT_INTERVAL_US = 100_000
_SERVO_TELEMETRY_TYPES = frozenset({"SERVO_OUTPUT_RAW", "HEARTBEAT"})


class ServoTelemetryBackend(RCTelemetryBackend):
    """Own the SERVO_OUTPUT_RAW stream lifecycle and read packets from the selected FC."""

    def _request_stream(self) -> None:
        success, error = self.flight_controller.request_servo_output_messages(_SERVO_OUTPUT_INTERVAL_US)
        if not success:
            logging_debug("Could not request servo output telemetry interval: %s", error)

    def _restore_stream(self) -> None:
        success, error = self.flight_controller.request_servo_output_messages(0)
        if not success:
            logging_debug("Could not restore servo output telemetry interval: %s", error)

    def get_servo_telemetry(self) -> Iterator[Any]:
        """Yield SERVO_OUTPUT_RAW and HEARTBEAT packets in a bounded, nonblocking batch."""
        for message in self.get_rc_telemetry():
            if message.get_type() in _SERVO_TELEMETRY_TYPES:
                yield message
