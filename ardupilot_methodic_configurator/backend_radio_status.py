"""
Enable telemetry-radio status reports with periodic ground-station heartbeats.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from time import monotonic
from typing import Any

from pymavlink.dialects.v20 import ardupilotmega as mavlink


class RadioStatusBackend:
    """Send the local serial heartbeat SiK needs before injecting radio reports."""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._last_heartbeat: float | None = None

    def close(self) -> None:
        """Start a fresh heartbeat interval when monitoring resumes or reconnects."""
        self._last_heartbeat = None

    def poll(self, master: Any) -> None:  # noqa: ANN401
        """Send immediately on activation, then at most once per second while polled."""
        now = self._clock()
        if self._last_heartbeat is not None and now - self._last_heartbeat < 1.0:
            return
        master.mav.heartbeat_send(
            mavlink.MAV_TYPE_GCS,
            mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavlink.MAV_STATE_ACTIVE,
        )
        self._last_heartbeat = now
