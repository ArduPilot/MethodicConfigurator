"""
Bounded MAVLink monitoring through the existing flight-controller facade.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from logging import debug as logging_debug
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

from serial import SerialException

from ardupilot_methodic_configurator.data_model_data_telemetry import (
    MessageKey,
    MessageSample,
    RadioSample,
    TelemetrySample,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

_MAX_MESSAGE_TYPES = 512


class DataTelemetryBackend:
    """Observe parsed packets without replacing hooks or reading from a second connection."""

    def __init__(self, flight_controller: "FlightController", clock: Callable[[], float] = monotonic) -> None:
        self.flight_controller = flight_controller
        self._clock = clock
        self._master: Any = None
        self._messages: dict[MessageKey, MessageSample] = {}
        self._radio: RadioSample | None = None

    def close(self) -> None:
        """Detach only our observer and discard data at lifecycle boundaries."""
        if self._master is not None and self._capture in self._master.message_hooks:
            self._master.message_hooks.remove(self._capture)
        self._master = None
        self._messages.clear()
        self._radio = None

    def _capture(self, _master: object, message: Any) -> None:  # noqa: ANN401
        """Count all sources independently, including modem-injected RADIO messages."""
        name = str(message.get_type())
        if name == "BAD_DATA":
            return
        now = self._clock()
        source = (int(message.get_srcSystem()), int(message.get_srcComponent()))
        if name in {"RADIO", "RADIO_STATUS"}:
            # These are injected by the radio on this transport. Source IDs are not link IDs.
            self._radio = RadioSample(
                source=source,
                time=now,
                rssi=self._radio_value(message.rssi, 254),
                remrssi=self._radio_value(message.remrssi, 254),
                noise=self._radio_value(message.noise, 254),
                remnoise=self._radio_value(message.remnoise, 254),
                txbuf=self._radio_value(message.txbuf, 100),
                rxerrors=int(message.rxerrors),
                fixed=int(message.fixed),
            )
        key = (*source, name)
        old = self._messages.get(key)
        if old is None and len(self._messages) >= _MAX_MESSAGE_TYPES:
            return
        self._messages[key] = MessageSample(
            count=(old.count if old else 0) + 1,
            size=(old.size if old else 0) + len(message.get_msgbuf()),
            last_seen=now,
            fields=tuple((key, str(value)[:512]) for key, value in message.to_dict().items() if key != "mavpackettype"),
        )

    @staticmethod
    def _radio_value(value: int, maximum: int) -> int | None:
        return int(value) if 0 <= value <= maximum else None

    def poll(self) -> TelemetrySample:
        """Enable connection-owned heartbeats and drain at most 200 packets/10 ms."""
        master = cast("Any", self.flight_controller.master)
        if master is not self._master:
            self.close()
            self._master = master
            if master is not None:
                master.message_hooks.append(self._capture)
        if master is None:
            return TelemetrySample(None, self._clock())
        try:
            self.flight_controller.start_gcs_heartbeat()
            deadline = self._clock() + 0.01
            for _index in range(200):
                if self._clock() >= deadline or master.recv_match(blocking=False) is None:
                    break
            return TelemetrySample(
                connection=master,
                time=self._clock(),
                rx_bytes=int(master.mav.total_bytes_received),
                tx_bytes=int(master.mav.total_bytes_sent),
                parse_errors=int(master.mav.total_receive_errors),
                messages=dict(self._messages),
                radio=self._radio,
            )
        except (OSError, SerialException, AttributeError, TypeError, ValueError) as exc:
            logging_debug("Error reading data telemetry: %s", exc)
            self.close()
            return TelemetrySample(master, self._clock(), error=True)
