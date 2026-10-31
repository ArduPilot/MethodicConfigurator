"""
Shared observer lifecycle and bounded reads for MAVLink telemetry backends.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class MavlinkTelemetryBackend(ABC):  # pylint: disable=too-few-public-methods
    """Attach one observer to the shared connection and keep each poll bounded."""

    def __init__(self, flight_controller: "FlightController", clock: Callable[[], float] = monotonic) -> None:
        self.flight_controller = flight_controller
        self._clock = clock
        self._master: Any = None

    def close(self) -> None:
        """Detach only this backend's hook, preserving other connection consumers."""
        if self._master is not None and self._capture in self._master.message_hooks:
            self._master.message_hooks.remove(self._capture)
        self._master = None

    def _sync_connection(self) -> Any:  # noqa: ANN401
        """Reset observations through close() before attaching to a replacement connection."""
        master = cast("Any", self.flight_controller.master)
        if master is not self._master:
            self.close()
            self._master = master
            if master is not None:
                master.message_hooks.append(self._capture)
        return master

    def _drain_messages(self) -> None:
        """Read at most 200 packets or 10 ms, counting unrelated traffic toward both limits."""
        deadline = self._clock() + 0.01
        for _index in range(200):
            if self._clock() >= deadline or self._master.recv_match(blocking=False) is None:
                break

    @abstractmethod
    def _capture(self, master: Any, message: Any, /) -> None:  # noqa: ANN401
        """Handle one parsed message according to the consumer's telemetry policy."""
