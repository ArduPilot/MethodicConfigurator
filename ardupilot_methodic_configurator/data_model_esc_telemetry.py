"""
Reusable ESC telemetry samples, freshness rules and table formatting.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

MAX_ESCS = 32
STALE_SECONDS = 3.0
ESC_FIELDS = ("rpm", "voltage", "current", "temperature", "totalcurrent", "count")


@dataclass(frozen=True)
class EscTelemetryReading:
    """One ESC's raw values and monotonic receipt time, when captured by a backend."""

    values: tuple[int, ...]
    received_at: float | None = None


@dataclass(frozen=True)
class EscTelemetrySnapshot:
    """A bounded batch of observations from one connection."""

    connection: object | None
    time: float
    readings: dict[int, EscTelemetryReading] = field(default_factory=dict)
    error: bool = False


class EscTelemetryDataModel:
    """Retain independent ESC readings and expire stopped telemetry counters."""

    def __init__(self, flight_controller: "FlightController") -> None:
        self.flight_controller = flight_controller
        self._connection: object | None = None
        self._telemetry: dict[int, tuple[float, EscTelemetryReading]] = {}
        self._rpm: dict[int, tuple[float, int | str]] = {}

    @property
    def visible_esc_indices(self) -> tuple[int, ...]:
        """Return detected ESC indices in FC order, including RPM-only reporters."""
        return tuple(sorted(self._telemetry.keys() | self._rpm.keys()))

    def clear_live_data(self) -> None:
        """Discard observations at a connection or lifecycle boundary."""
        self._connection = None
        self._telemetry.clear()
        self._rpm.clear()

    @staticmethod
    def row_labels() -> tuple[str, ...]:
        """Return translated measurement names with engineering units."""
        return (
            _("RPM"),
            _("Voltage (V)"),
            _("Current (A)"),
            _("Temperature (°C)"),
            _("Consumption (mAh)"),
            _("Telemetry packets"),
        )

    def _configured_bdshot_output(self, index: int) -> bool:
        """Identify configured outputs, accounting for the ESC MAVLink offset."""
        params = self.flight_controller.fc_parameters
        if not isinstance(params, dict):
            return False
        try:
            mask = int(params.get("SERVO_BLH_BDMASK", 0))
            offset = int(params.get("ESC_TLM_MAV_OFS", 0))
        except (TypeError, ValueError, OverflowError):
            return False
        output = index + offset
        return 0 <= offset < MAX_ESCS and 0 <= output < MAX_ESCS and bool(mask & (1 << output))

    def update(self, snapshot: EscTelemetrySnapshot) -> tuple[tuple[str, ...], ...]:
        """Return measurement rows; zeros remain valid for an ESC reporting telemetry."""
        if snapshot.connection is not self._connection or snapshot.error or snapshot.connection is None:
            self.clear_live_data()
            self._connection = snapshot.connection
        if not snapshot.error and snapshot.connection is not None:
            for index, reading in snapshot.readings.items():
                if not 0 <= index < MAX_ESCS or len(reading.values) != len(ESC_FIELDS):
                    continue
                if not any(reading.values):
                    # The wire format cannot distinguish a stopped BDShot motor from
                    # an unavailable member of an otherwise active group.
                    if self._configured_bdshot_output(index):
                        received_at = snapshot.time if reading.received_at is None else reading.received_at
                        self._rpm[index] = (received_at, "0*")
                    continue
                old = self._telemetry.get(index)
                count = reading.values[-1]
                received_at = snapshot.time if reading.received_at is None else reading.received_at
                fresh_counter = (count != 0 and old is None) or (old is not None and count != old[1].values[-1])
                if fresh_counter:
                    self._telemetry[index] = (received_at, reading)
                if reading.values[0] != 0 or fresh_counter:
                    self._rpm[index] = (received_at, reading.values[0])
        rows = [["-"] * MAX_ESCS for _field in ESC_FIELDS]
        for index, (timestamp, rpm) in self._rpm.items():
            if snapshot.time - timestamp < STALE_SECONDS:
                rows[0][index] = str(rpm)
        for index, (timestamp, reading) in self._telemetry.items():
            if snapshot.time - timestamp < STALE_SECONDS:
                for row in range(1, len(ESC_FIELDS)):
                    value = reading.values[row]
                    rows[row][index] = f"{value / 100:.2f}" if row in (1, 2) else str(value)
        return tuple(tuple(row) for row in rows)
