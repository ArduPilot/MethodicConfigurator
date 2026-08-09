"""
Shared IMU helpers for plugin data models and Tkinter views.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from math import sqrt
from typing import Protocol

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

# Body frame: X=forward, Y=right, Z=down.
# Specific force = -gravity_in_body when stationary.
# Each entry is (unit_vector, display_name).
_ORIENTATIONS: list[tuple[tuple[float, float, float], str]] = [
    ((0.0, 0.0, -1.0), _("LEVEL")),
    ((0.0, 1.0, 0.0), _("LEFT")),
    ((0.0, -1.0, 0.0), _("RIGHT")),
    ((-1.0, 0.0, 0.0), _("NOSE DOWN")),
    ((1.0, 0.0, 0.0), _("NOSE UP")),
    ((0.0, 0.0, 1.0), _("BACK")),
]
_COS_20_DEG: float = 0.9397


def poll_scaled_imu(
    flight_controller: FlightController,
    got_imu_stream: bool,
) -> tuple[tuple[float, float, float] | None, bool]:
    """Return the latest IMU sample and updated stream state."""
    if not got_imu_stream:
        success, _ = flight_controller.request_scaled_imu_messages()
        if success:
            got_imu_stream = True
    return flight_controller.poll_scaled_imu(), got_imu_stream


def compute_movement_magnitude_ms2(xacc_mg: float, yacc_mg: float, zacc_mg: float) -> float:
    """Compute the acceleration-vector magnitude in m/s^2 from milli-g components."""
    mg_to_ms2 = 9.80665 / 1000.0
    return sqrt(xacc_mg**2 + yacc_mg**2 + zacc_mg**2) * mg_to_ms2


def compute_detected_position(xacc_mg: float, yacc_mg: float, zacc_mg: float) -> str:
    """Infer a human-readable orientation label from IMU acceleration."""
    mag = sqrt(xacc_mg**2 + yacc_mg**2 + zacc_mg**2)
    if mag < 1.0:
        return _("INDEFINITE")
    nx, ny, nz = xacc_mg / mag, yacc_mg / mag, zacc_mg / mag
    for (ex, ey, ez), name in _ORIENTATIONS:
        if nx * ex + ny * ey + nz * ez > _COS_20_DEG:
            return name
    return _("INDEFINITE")


def start_periodic_polling(
    after_callback: Callable[[int, Callable[[], None]], str],
    current_job: str | None,
    interval_ms: int,
    tick_callback: Callable[[], None],
) -> str | None:
    """Schedule a repeating tkinter callback if no job is currently pending."""
    if current_job is None:
        return after_callback(interval_ms, tick_callback)
    return current_job


def stop_periodic_polling(after_cancel_callback: Callable[[str], object], current_job: str | None) -> None:
    """Cancel a pending tkinter after() job if one exists."""
    if current_job is not None:
        with suppress(tk.TclError):
            after_cancel_callback(current_job)


class ImuPollingModel(Protocol):  # pylint: disable=too-few-public-methods
    """Model interface needed for live IMU polling."""

    def poll_imu_raw(self) -> tuple[float, float, float] | None:
        """Return the latest raw IMU sample, when available."""


class ImuPollingView(Protocol):  # pylint: disable=too-few-public-methods
    """View callbacks used to display and retain live IMU polling state."""

    @property
    def model(self) -> ImuPollingModel:
        """Return the model providing IMU samples."""

    def _handle_live_imu_sample(self, imu: tuple[float, float, float]) -> None:
        """Handle an available IMU sample."""

    def _handle_no_live_imu_sample(self) -> None:
        """Handle a polling interval without an IMU sample."""

    def _store_imu_poll_job(self, job_id: str) -> None:
        """Store the scheduled timer identifier."""


@dataclass(frozen=True)
class ImuPollHandlers:
    """Callbacks used by a repeating IMU polling timer."""

    interval_ms: int
    poll: Callable[[], tuple[float, float, float] | None]
    on_sample: Callable[[tuple[float, float, float]], None]
    on_no_sample: Callable[[], None] | None = None
    on_scheduled: Callable[[str], None] | None = None

    @classmethod
    def for_view(  # pylint: disable=protected-access
        cls, view: ImuPollingView, interval_ms: int
    ) -> "ImuPollHandlers":
        """Create handlers for a view implementing the live IMU polling callbacks."""
        return cls(
            interval_ms,
            view.model.poll_imu_raw,
            view._handle_live_imu_sample,  # noqa: SLF001
            view._handle_no_live_imu_sample,  # noqa: SLF001
            view._store_imu_poll_job,  # noqa: SLF001
        )


def poll_imu_periodically(
    after_callback: Callable[[int, Callable[[], None]], str],
    current_job: str | None,
    handlers: ImuPollHandlers,
) -> str | None:
    """Poll IMU data on a repeating tkinter timer and report each new timer id."""
    if current_job is not None:
        return current_job

    job_id: str | None = None

    def tick() -> None:
        nonlocal job_id
        imu = handlers.poll()
        if imu is not None:
            handlers.on_sample(imu)
        elif handlers.on_no_sample is not None:
            handlers.on_no_sample()
        job_id = after_callback(handlers.interval_ms, tick)
        if handlers.on_scheduled is not None:
            handlers.on_scheduled(job_id)

    job_id = after_callback(handlers.interval_ms, tick)
    if handlers.on_scheduled is not None:
        handlers.on_scheduled(job_id)
    return job_id
