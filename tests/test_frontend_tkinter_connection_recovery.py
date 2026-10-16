#!/usr/bin/env python3
"""
Behavioral tests for connection ownership and the recovery coordinator lifecycle.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_reconnect import FlightControllerReconnect
from ardupilot_methodic_configurator.frontend_tkinter_connection_recovery import (
    ConnectionRecovery,
    RecoveryCallbacks,
    RecoveryState,
)

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture
def session() -> SimpleNamespace:
    """Provide a real coordinator with external FC I/O and Tk callbacks replaced."""
    root = MagicMock()
    monitor = MagicMock(spec=FlightControllerReconnect)
    monitor.cancelled = Event()
    monitor.poll.return_value = True
    monitor.reconnect.return_value = ""
    resume, unlock = MagicMock(), MagicMock()
    callbacks = RecoveryCallbacks(
        reader_busy=MagicMock(return_value=False),
        can_read=MagicMock(return_value=False),
        pause_receiver=MagicMock(return_value=resume),
        lock_controls=MagicMock(return_value=unlock),
        show_status=MagicMock(),
        on_recovered=MagicMock(),
    )
    recovery = ConnectionRecovery(root, monitor, callbacks)
    return SimpleNamespace(root=root, monitor=monitor, recovery=recovery, callbacks=callbacks, resume=resume, unlock=unlock)


def test_nested_operations_keep_replies_exclusive_until_the_last_owner_yields(session: SimpleNamespace) -> None:
    """GIVEN nested event loops, WHEN the inner operation ends, THEN the outer owner still prevents monitor reads."""
    with session.recovery.operation():
        with session.recovery.operation():
            session.recovery.check()
        session.recovery.check()
        session.monitor.poll.assert_not_called()
        assert session.recovery.operation_active
    assert not session.recovery.operation_active
    session.recovery.check()
    session.monitor.poll.assert_called_once_with(read=False)


def test_failed_operation_releases_ownership(session: SimpleNamespace) -> None:
    """GIVEN an exclusive operation, WHEN it raises, THEN later connection checks can receive again."""
    message = "Upload failed"
    with pytest.raises(OSError, match="Upload failed"), session.recovery.operation():
        raise OSError(message)
    assert not session.recovery.operation_active
    session.recovery.check()
    session.monitor.poll.assert_called_once()


def test_async_operation_release_is_idempotent_and_does_not_release_another_owner(session: SimpleNamespace) -> None:
    """GIVEN two open tools, WHEN one closes twice, THEN the other retains reception and the final close resets grace."""
    first = session.recovery.acquire_operation()
    second = session.recovery.acquire_operation()
    first()
    first()
    assert session.recovery.operation_active
    session.monitor.defer.assert_not_called()
    second()
    second()
    assert not session.recovery.operation_active
    session.monitor.defer.assert_called_once()


def test_manual_checks_and_repeated_start_keep_one_timer(session: SimpleNamespace) -> None:
    """GIVEN scheduled monitoring, WHEN start and a manual check run, THEN only one future timer remains."""
    session.recovery.start()
    session.recovery.start()
    session.root.after.assert_called_once()
    session.recovery.check()
    session.root.after_cancel.assert_called_once_with(session.root.after.return_value)
    assert session.root.after.call_count == 2


def test_an_unpausable_plugin_keeps_reception(session: SimpleNamespace) -> None:
    """GIVEN a plugin that cannot yield, WHEN its heartbeat is stale, THEN no competing read or reconnect begins."""
    session.monitor.poll.return_value = False
    session.callbacks.pause_receiver.return_value = None
    session.recovery.check()
    session.monitor.poll.assert_called_once_with(read=False)
    session.monitor.reconnect.assert_not_called()
    assert session.recovery.state is RecoveryState.MONITORING


def test_buffered_heartbeat_resumes_without_reconnecting_or_locking_controls(session: SimpleNamespace) -> None:
    """GIVEN an idle receiver, WHEN a buffered heartbeat is parsed, THEN its state resumes without recovery."""
    session.monitor.poll.side_effect = [False, True]
    session.recovery.check()
    session.resume.assert_called_once()
    session.callbacks.lock_controls.assert_not_called()
    session.monitor.reconnect.assert_not_called()
    assert session.recovery.state is RecoveryState.MONITORING


def test_retries_keep_controls_owned_and_complete_on_the_ui_thread(session: SimpleNamespace) -> None:
    """GIVEN a failed attempt, WHEN the next retry succeeds, THEN one pause spans both attempts and UI completion."""
    session.monitor.poll.return_value = False
    attempts = iter(["Unavailable", ""])
    worker_threads = []

    def reconnect() -> str:
        worker_threads.append(get_ident())
        return next(attempts)

    session.monitor.reconnect.side_effect = reconnect
    ui_threads = []
    session.callbacks.on_recovered.side_effect = lambda: ui_threads.append(get_ident())
    session.recovery.check()
    for _attempt in range(2):
        assert session.recovery.state is RecoveryState.RECOVERING
        session.resume.assert_not_called()
        session.unlock.assert_not_called()
        session.recovery._worker.join(timeout=1)
        assert not session.recovery._worker.is_alive()
        session.recovery.check()

    assert len(worker_threads) == 2
    assert all(thread != get_ident() for thread in worker_threads)
    assert ui_threads == [get_ident()]
    session.callbacks.pause_receiver.assert_called_once()
    session.resume.assert_called_once()
    session.unlock.assert_called_once()
    assert session.recovery.state is RecoveryState.MONITORING


def test_shutdown_waits_for_worker_without_resuming_plugin_or_publishing_late_success(session: SimpleNamespace) -> None:
    """GIVEN a blocked reconnect, WHEN closing, THEN ownership remains until it yields and late success is discarded."""
    started, finish = Event(), Event()

    def reconnect() -> str:
        started.set()
        assert finish.wait(timeout=5)
        return ""

    session.monitor.poll.return_value = False
    session.monitor.reconnect.side_effect = reconnect
    session.recovery.check()
    try:
        assert started.wait(timeout=1)
        assert not session.recovery.stop()
        assert session.recovery.state is RecoveryState.STOPPING
        assert session.monitor.cancelled.is_set()
        session.unlock.assert_not_called()
        session.recovery.check()
        session.callbacks.on_recovered.assert_not_called()
    finally:
        finish.set()
        session.recovery._worker.join(timeout=1)
    assert session.recovery.stop()
    assert session.recovery.state is RecoveryState.STOPPED
    session.unlock.assert_called_once()
    session.resume.assert_not_called()
    session.callbacks.on_recovered.assert_not_called()
    session.root.after.reset_mock()
    session.recovery.check()
    session.recovery.start()
    session.root.after.assert_not_called()


def test_render_failure_still_releases_controls_and_resumes_receiver(session: SimpleNamespace) -> None:
    """GIVEN recovered hardware, WHEN repaint fails, THEN controls and the receiver are still released."""
    session.monitor.poll.return_value = False
    session.recovery.check()
    session.recovery._worker.join(timeout=1)
    session.callbacks.on_recovered.side_effect = RuntimeError("Widget destroyed")
    with pytest.raises(RuntimeError, match="Widget destroyed"):
        session.recovery.check()
    session.unlock.assert_called_once()
    session.resume.assert_called_once()
    assert session.recovery.state is RecoveryState.MONITORING
