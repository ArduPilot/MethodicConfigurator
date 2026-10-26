#!/usr/bin/env python3

"""
Tests for shared IMU polling and orientation helpers.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from math import sqrt
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from ardupilot_methodic_configurator.plugins.imu_helpers import (
    ImuPollHandlers,
    compute_detected_position,
    compute_movement_magnitude_ms2,
    poll_imu_periodically,
    poll_scaled_imu,
    start_periodic_polling,
    stop_periodic_polling,
)


def test_poll_scaled_imu_requests_stream_only_until_request_succeeds() -> None:
    flight_controller = MagicMock()
    flight_controller.request_scaled_imu_messages.side_effect = [(False, "busy"), (True, "")]
    flight_controller.poll_scaled_imu.return_value = (1.0, 2.0, 3.0)

    _, stream_started = poll_scaled_imu(flight_controller, got_imu_stream=False)
    sample, stream_started = poll_scaled_imu(flight_controller, stream_started)
    _, stream_started = poll_scaled_imu(flight_controller, stream_started)

    assert sample == (1.0, 2.0, 3.0)
    assert stream_started is True
    assert flight_controller.request_scaled_imu_messages.call_count == 2


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        ((0.0, 0.0, -1000.0), "LEVEL"),
        ((0.0, 1000.0, 0.0), "LEFT"),
        ((0.0, -1000.0, 0.0), "RIGHT"),
        ((-1000.0, 0.0, 0.0), "NOSE DOWN"),
        ((1000.0, 0.0, 0.0), "NOSE UP"),
        ((0.0, 0.0, 1000.0), "BACK"),
        ((1000.0, 1000.0, 0.0), "INDEFINITE"),
        ((0.0, 0.0, 0.0), "INDEFINITE"),
    ],
)
def test_compute_detected_position(sample: tuple[float, float, float], expected: str) -> None:
    """
    Identify all supported stationary poses and reject ambiguous acceleration.

    GIVEN: A sensor vector aligned with a supported pose, between poses or at rest
    WHEN: The monitor interprets the orientation
    THEN: It reports the matching pose or an indefinite orientation
    """
    assert compute_detected_position(*sample) == expected


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        ((1000.0, 0.0, 0.0), 9.80665),
        ((0.0, 1000.0, 0.0), 9.80665),
        ((0.0, 0.0, 1000.0), 9.80665),
        ((-300.0, 400.0, 0.0), 4.903325),
        ((0.0, 0.0, 0.0), 0.0),
    ],
)
def test_compute_movement_magnitude_converts_milligravity_to_metres_per_second_squared(
    sample: tuple[float, float, float], expected: float
) -> None:
    """
    Report physical acceleration independently of axis and sign.

    GIVEN: A stationary or moving sensor reporting acceleration in milli-g
    WHEN: Its movement magnitude is calculated
    THEN: Every axis contributes to the magnitude in metres per second squared
    """
    assert compute_movement_magnitude_ms2(*sample) == pytest.approx(expected)


@pytest.mark.parametrize(("magnitude", "expected"), [(0.999, "INDEFINITE"), (1.0, "BACK"), (1.001, "BACK")])
def test_orientation_requires_a_large_enough_sample(magnitude: float, expected: str) -> None:
    """
    Avoid reporting a pose from a near-zero sensor vector.

    GIVEN: A sample aligned with the back orientation
    WHEN: Its magnitude is below, at or above the detection minimum
    THEN: Only sufficiently large samples produce an orientation
    """
    assert compute_detected_position(0.0, 0.0, magnitude) == expected


@pytest.mark.parametrize(
    ("alignment", "expected", "scale"),
    [
        (0.9396, "INDEFINITE", 1.0),
        (0.9397, "INDEFINITE", 1.0),
        (0.9398, "BACK", 1.0),
        (0.9396, "INDEFINITE", 1000.0),
        (0.9398, "BACK", 1000.0),
    ],
)
def test_orientation_rejects_samples_outside_the_pose_cone(alignment: float, expected: str, scale: float) -> None:
    """
    Require alignment with a supported pose rather than just its nearest axis.

    GIVEN: A sensor vector near the supported pose's angular limit
    WHEN: The orientation is detected
    THEN: A sample inside the cone is accepted and one outside is indefinite
    """
    assert compute_detected_position(scale * sqrt(1.0 - alignment**2), 0.0, scale * alignment) == expected


def test_monitor_view_receives_samples_missing_data_and_replacement_timer_ids() -> None:
    """
    Wire a monitor's polling handlers to its model and display callbacks.

    GIVEN: A monitor model yielding a sample followed by a telemetry gap
    WHEN: Two scheduled polling callbacks fire
    THEN: The view receives the sample, missing-data feedback and current timer ids
    """
    sample = (100.0, 200.0, -900.0)
    on_sample = MagicMock()
    on_missing = MagicMock()
    on_scheduled = MagicMock()
    view = SimpleNamespace(
        model=SimpleNamespace(poll_imu_raw=MagicMock(side_effect=[sample, None])),
        _handle_live_imu_sample=on_sample,
        _handle_no_live_imu_sample=on_missing,
        _store_imu_poll_job=on_scheduled,
    )
    callbacks: list[Callable[[], None]] = []

    def schedule(interval: int, callback: Callable[[], None]) -> str:
        assert interval == 175
        callbacks.append(callback)
        return f"timer-{len(callbacks)}"

    handlers = ImuPollHandlers.for_view(view, 175)
    assert poll_imu_periodically(schedule, None, handlers) == "timer-1"
    callbacks[0]()
    callbacks[1]()

    on_sample.assert_called_once_with(sample)
    on_missing.assert_called_once_with()
    assert on_scheduled.call_args_list == [call("timer-1"), call("timer-2"), call("timer-3")]


def test_periodic_polling_reports_replacement_job_id_for_cancellation() -> None:
    scheduled_callbacks = []
    scheduled_ids = iter(("after-1", "after-2"))

    def schedule(_interval_ms: int, callback: Callable[[], None]) -> str:
        scheduled_callbacks.append(callback)
        return next(scheduled_ids)

    on_scheduled = MagicMock()
    on_sample = MagicMock()
    job_id = poll_imu_periodically(
        schedule,
        None,
        ImuPollHandlers(200, lambda: (1.0, 2.0, 3.0), on_sample, on_scheduled=on_scheduled),
    )
    scheduled_callbacks[0]()

    assert job_id == "after-1"
    assert on_scheduled.call_args_list == [call("after-1"), call("after-2")]
    on_sample.assert_called_once_with((1.0, 2.0, 3.0))


def test_stop_periodic_polling_ignores_tcl_error() -> None:
    cancel = MagicMock(side_effect=tk.TclError("already cancelled"))

    stop_periodic_polling(cancel, "after-1")

    cancel.assert_called_once_with("after-1")


@pytest.mark.parametrize("pending", [None, "existing-timer"])
def test_reopening_a_monitor_keeps_only_one_pending_timer(pending: str | None) -> None:
    """
    Prevent duplicate monitor timers.

    GIVEN: A monitor with or without a pending timer
    WHEN: Polling is started again
    THEN: A timer is created only when none is already pending
    """
    # Given: The scheduler represents the external Tk event queue.
    schedule = MagicMock(return_value="new-timer")
    tick = MagicMock()
    # When: Request periodic monitoring.
    result = start_periodic_polling(schedule, pending, 200, tick)
    # Then: Existing work is retained without adding another timer.
    assert result == (pending or "new-timer")
    if pending:
        schedule.assert_not_called()
    else:
        schedule.assert_called_once_with(200, tick)


@pytest.mark.parametrize("notify_missing_sample", [True, False])
def test_monitor_keeps_polling_when_no_imu_sample_arrives(notify_missing_sample: bool) -> None:
    """
    Recover from a telemetry gap with optional missing-sample feedback.

    GIVEN: No IMU reading and a monitor with optional callbacks
    WHEN: Its timer fires
    THEN: It reports no fresh sample when requested and schedules another poll
    """
    # Given: Capture actual timer callbacks so the tick can be driven deterministically.
    callbacks: list[Callable[[], None]] = []

    def schedule(interval: int, callback: Callable[[], None]) -> str:
        assert interval == 200
        callbacks.append(callback)
        return f"timer-{len(callbacks)}"

    on_sample = MagicMock()
    on_missing = MagicMock()
    handlers = ImuPollHandlers(200, lambda: None, on_sample, on_no_sample=on_missing if notify_missing_sample else None)
    # When: Start monitoring and fire one scheduled poll.
    assert poll_imu_periodically(schedule, None, handlers) == "timer-1"
    callbacks[0]()
    # Then: Missing data does not stop monitoring or invent a reading.
    assert len(callbacks) == 2
    on_sample.assert_not_called()
    assert on_missing.called is notify_missing_sample
