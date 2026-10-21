"""
Coordinate editor connection recovery and exclusive FC operation lifetimes.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import Enum, auto
from logging import exception as logging_exception
from threading import Thread
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from ardupilot_methodic_configurator.backend_flightcontroller_reconnect import FlightControllerReconnect


class RecoveryState(Enum):
    """The connection lifecycle, independent of widget state."""

    MONITORING = auto()
    RECOVERING = auto()
    STOPPING = auto()
    STOPPED = auto()


@dataclass(frozen=True)
class RecoveryCallbacks:
    """UI work performed exclusively on the Tk thread."""

    reader_busy: Callable[[], bool]
    can_read: Callable[[], bool]
    pause_receiver: Callable[[], Callable[[], None] | None]
    lock_controls: Callable[[object], Callable[[], None]]
    show_status: Callable[[str], None]
    on_recovered: Callable[[], None]
    can_refresh: Callable[[], bool] = lambda: True


class ConnectionRecovery:  # pylint: disable=too-many-instance-attributes
    """Own one timer, one recovery worker, and explicit leases for other FC users."""

    def __init__(self, root: tk.Misc, monitor: FlightControllerReconnect, callbacks: RecoveryCallbacks) -> None:
        self._root = root
        self._monitor = monitor
        self._callbacks = callbacks
        self._state = RecoveryState.MONITORING
        self._job: str | None = None
        self._worker: Thread | None = None
        self._error = ""
        self._resume: Callable[[], None] | None = None
        self._unlock: Callable[[], None] | None = None
        self._operations: set[object] = set()

    @property
    def state(self) -> RecoveryState:
        """The lifecycle state owned by this coordinator."""
        return self._state

    @property
    def operation_active(self) -> bool:
        """Whether another FC user still owns an operation lease."""
        return bool(self._operations)

    def acquire_operation(self) -> Callable[[], None]:
        """Retain reception until the returned idempotent release callback runs."""
        owner = object()
        self._operations.add(owner)

        def release() -> None:
            if owner in self._operations:
                self._operations.remove(owner)
                if not self._operations:
                    self._monitor.defer()

        return release

    @contextmanager
    def operation(self) -> Generator[None, None, None]:
        """Retain ownership across nested Tk event loops and release it on errors."""
        release = self.acquire_operation()
        try:
            yield
        finally:
            release()

    def start(self) -> None:
        """Schedule at most one connection check."""
        if self._job is None and self.state in (RecoveryState.MONITORING, RecoveryState.RECOVERING):
            self._job = self._root.after(1000, self.check)

    def stop(self) -> bool:
        """Cancel recovery without blocking Tk or releasing a running worker's controls."""
        if self.state is RecoveryState.STOPPED:
            return True
        self._state = RecoveryState.STOPPING
        self._monitor.cancelled.set()
        if self._job is not None:
            with suppress(tk.TclError):
                self._root.after_cancel(self._job)
            self._job = None
        if self._worker is not None and self._worker.is_alive():
            return False
        self._worker = None
        self._monitor.close()
        self._release_controls(resume=False)
        self._state = RecoveryState.STOPPED
        return True

    def check(self) -> None:
        """Check liveness or complete one retry; all UI transitions stay on Tk."""
        # Manual checks and timer callbacks share the same scheduling contract.
        if self._job is not None:
            self._root.after_cancel(self._job)
            self._job = None
        if self.state in (RecoveryState.STOPPING, RecoveryState.STOPPED):
            return
        try:
            self._check_connection()
        finally:
            self.start()

    def _check_connection(self) -> None:
        if self._worker is not None:
            if self._worker.is_alive() or (not self._error and not self._callbacks.can_refresh()):
                return
            self._worker = None
            if not self._error:
                self._state = RecoveryState.MONITORING
                try:
                    self._callbacks.on_recovered()
                finally:
                    self._release_controls(resume=True)
                return
            self._callbacks.show_status(self._error)

        if self.state is RecoveryState.MONITORING:
            if self.operation_active or self._callbacks.reader_busy():
                self._monitor.defer()
                return
            if self._monitor.poll(read=self._callbacks.can_read()):
                return
            self._resume = self._callbacks.pause_receiver()
            if self._resume is None:
                self._monitor.defer()
                return
            # A receiver may be idle: parse buffered heartbeats before recovery.
            if self._monitor.poll(read=True):
                self._release_controls(resume=True)
                return
            self._state = RecoveryState.RECOVERING
            self._unlock = self._callbacks.lock_controls(self)
            self._callbacks.show_status(_("Flight-controller connection lost. Reconnecting…"))

        self._worker = Thread(target=self._reconnect, name="fc-reconnect", daemon=True)
        self._worker.start()

    def _reconnect(self) -> None:
        try:
            self._error = self._monitor.reconnect()
        except Exception:  # pylint: disable=broad-exception-caught
            logging_exception("Automatic flight-controller reconnection failed")
            self._error = _("Could not reconnect to the flight controller. Retrying.")
        finally:
            # Destruction can end Tk's event loop before stop() is retried.
            if self._monitor.cancelled.is_set():
                self._monitor.close()

    def _release_controls(self, *, resume: bool) -> None:
        unlock, self._unlock = self._unlock, None
        callback, self._resume = self._resume, None
        try:
            if unlock is not None:
                unlock()
        finally:
            if resume and callback is not None:
                callback()
