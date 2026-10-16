"""
Connection telemetry snapshots and rate calculations, independent of Tkinter.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

MessageKey = tuple[int, int, str]
STALE_SECONDS = 3.0


@dataclass(frozen=True)
class MessageSample:
    """Cumulative received wire bytes and latest decoded fields for one source/type."""

    count: int
    size: int
    last_seen: float
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RadioSample:  # pylint: disable=too-many-instance-attributes
    """One modem's RADIO or RADIO_STATUS report in device-dependent units."""

    source: tuple[int, int]
    time: float
    rssi: int | None
    remrssi: int | None
    noise: int | None
    remnoise: int | None
    txbuf: int | None
    rxerrors: int
    fixed: int


@dataclass(frozen=True)
class TelemetrySample:  # pylint: disable=too-many-instance-attributes
    """Backend observation; connection identity prevents rates spanning reconnects."""

    connection: object | None
    time: float
    rx_bytes: int = 0
    tx_bytes: int = 0
    parse_errors: int = 0
    messages: dict[MessageKey, MessageSample] = field(default_factory=dict)
    radio: RadioSample | None = None
    error: bool = False


@dataclass(frozen=True)
class MessageRate:
    """A message inspector row with recent rates and latest values."""

    key: MessageKey
    sample: MessageSample
    hz: float
    bytes_per_second: float
    age: float


@dataclass(frozen=True)
class TelemetryState:  # pylint: disable=too-many-instance-attributes
    """Unavailable readings remain distinct from measured zero values."""

    connected: bool = False
    receiving: bool = False
    rx_rate: float | None = None
    tx_rate: float | None = None
    parse_error_rate: float | None = None
    radio_error_rate: float | None = None
    radio: RadioSample | None = None
    messages: tuple[MessageRate, ...] = ()
    error: bool = False


class DataTelemetryDataModel:
    """Calculate interval rates from loaded snapshots without performing external I/O."""

    def __init__(self, flight_controller: "FlightController") -> None:
        self.flight_controller = flight_controller
        self._previous: TelemetrySample | None = None
        self._state = TelemetryState()

    def clear_live_data(self) -> None:
        """Start a new measurement interval when monitoring resumes."""
        self._previous = None
        self._state = TelemetryState()

    def update(self, sample: TelemetrySample) -> TelemetryState:  # pylint: disable=too-many-locals
        """Measure at least one second; discard stale radio reports and reset counter baselines."""
        previous = self._previous
        if sample.connection is None or sample.error:
            self.clear_live_data()
            return TelemetryState(connected=sample.connection is not None, error=sample.error)
        if previous is None or previous.connection is not sample.connection:
            previous = sample
            self._previous = sample
            self._state = TelemetryState(connected=True)
        elapsed = sample.time - previous.time
        radio = sample.radio if sample.radio is not None and sample.time - sample.radio.time < STALE_SECONDS else None
        cached_radio = self._state.radio
        same_counter = (
            radio is not None
            and cached_radio is not None
            and radio.source == cached_radio.source
            and radio.rxerrors >= cached_radio.rxerrors
        )
        if not same_counter:
            # Rebaseline the radio independently; preserve byte/message measurement intervals.
            previous = replace(previous, radio=radio)
            self._previous = previous
        rates: tuple[float | None, ...] = (self._state.rx_rate, self._state.tx_rate, self._state.parse_error_rate)
        radio_error_rate = self._state.radio_error_rate if same_counter else None
        measure = elapsed >= 1.0
        if measure:
            rates = tuple(
                (current - old) / elapsed if current >= old else None
                for current, old in zip(
                    (sample.rx_bytes, sample.tx_bytes, sample.parse_errors),
                    (previous.rx_bytes, previous.tx_bytes, previous.parse_errors),
                    strict=True,
                )
            )
            old_radio = previous.radio if same_counter else None
            # Polling the same fresh report must retain its last measured rate.
            if radio is None or old_radio is None or radio.time != old_radio.time:
                radio_error_rate = None
            # Never carry an old rate through a counter reset, source change or stale interval.
            if (
                radio
                and old_radio
                and radio.source == old_radio.source
                and 0 < radio.time - old_radio.time < STALE_SECONDS
                and radio.rxerrors >= old_radio.rxerrors
            ):
                radio_error_rate = (radio.rxerrors - old_radio.rxerrors) / (radio.time - old_radio.time)
        cached = {row.key: row for row in self._state.messages}
        rows = []
        for key, message in sorted(sample.messages.items()):
            age = max(0.0, sample.time - message.last_seen)
            old = previous.messages.get(key)
            hz = cached[key].hz if key in cached else 0.0
            byte_rate = cached[key].bytes_per_second if key in cached else 0.0
            if measure:
                hz = max(0, message.count - (old.count if old else 0)) / elapsed
                byte_rate = max(0, message.size - (old.size if old else 0)) / elapsed
            if age >= STALE_SECONDS:
                hz = byte_rate = 0.0
            rows.append(MessageRate(key, message, hz, byte_rate, age))
        self._state = TelemetryState(
            connected=True,
            receiving=any(row.age < STALE_SECONDS for row in rows),
            rx_rate=rates[0],
            tx_rate=rates[1],
            parse_error_rate=rates[2],
            radio_error_rate=radio_error_rate,
            radio=radio,
            messages=tuple(rows),
        )
        if measure:
            self._previous = sample
        return self._state
