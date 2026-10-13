"""
Run file-browser work off the Tk thread and return results on that thread.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Lock, Thread
from typing import NamedTuple, Protocol

ProgressCallback = Callable[[int, int], None]
Task = Callable[[ProgressCallback], object]
TaskCompletion = Callable[[object | None, Exception | None], None]


class _ProgressMessage(NamedTuple):
    current: int
    total: int


class _DoneMessage(NamedTuple):
    result: object | None
    error: Exception | None


class TaskRunner(Protocol):
    """Scheduling boundary used by the browser and its tests."""

    @property
    def active(self) -> bool: ...

    def start(
        self,
        task: Task,
        on_progress: ProgressCallback | None,
        on_done: TaskCompletion,
    ) -> bool: ...


class BackgroundTaskRunner:  # pylint: disable=too-many-instance-attributes
    """Execute one task at a time, sampling its latest progress on the UI thread."""

    POLL_INTERVAL_MS = 50

    def __init__(self, schedule: Callable[[int, Callable[[], None]], object]) -> None:
        self._schedule = schedule
        self._messages_lock = Lock()
        self._pending_progress: _ProgressMessage | None = None
        self._pending_done: _DoneMessage | None = None
        self._last_progress: _ProgressMessage | None = None
        self._polling = False
        self._thread: Thread | None = None
        self._on_progress: ProgressCallback | None = None
        self._on_done: TaskCompletion | None = None

    @property
    def active(self) -> bool:
        """Whether a task has been scheduled but not yet delivered."""
        return self._thread is not None

    @property
    def thread(self) -> Thread | None:
        """Expose the worker for orderly shutdown in integration tests."""
        return self._thread

    def start(
        self,
        task: Task,
        on_progress: ProgressCallback | None,
        on_done: TaskCompletion,
    ) -> bool:
        """Start work only if no other browser task is pending."""
        if self.active:
            return False
        with self._messages_lock:
            self._pending_progress = None
            self._pending_done = None
        self._last_progress = None
        self._on_progress = on_progress
        self._on_done = on_done

        def report_progress(current: int, total: int) -> None:
            # Progress is a snapshot, not an event history. Replacing this
            # slot keeps packet-rate reporting from growing a GUI backlog.
            with self._messages_lock:
                self._pending_progress = _ProgressMessage(current, total)

        def run() -> None:
            try:
                outcome = _DoneMessage(task(report_progress), None)
            except Exception as error:  # pylint: disable=broad-exception-caught
                outcome = _DoneMessage(None, error)
            # Completion has its own slot, so coalescing can never drop it.
            with self._messages_lock:
                self._pending_done = outcome

        self._thread = Thread(target=run, name="mavftp-browser-task", daemon=True)
        self._thread.start()
        self._schedule(self.POLL_INTERVAL_MS, self.poll)
        return True

    def poll(self) -> None:
        """Render at most one snapshot per tick, then yield to the GUI event loop."""
        # Some progress windows pump Tk events while painting on macOS.
        # A nested poll must not deliver completion inside a progress callback.
        if self._polling:
            return
        self._polling = True
        try:
            with self._messages_lock:
                progress = self._pending_progress
                outcome = self._pending_done
                self._pending_progress = None
                self._pending_done = None

            # Never hold the lock while calling Tk or user callbacks. New
            # reports arriving during rendering belong to the next tick.
            if progress is not None and progress != self._last_progress:
                self._last_progress = progress
                if self._on_progress is not None:
                    try:
                        self._on_progress(progress.current, progress.total)
                    except Exception:  # pylint: disable=broad-exception-caught
                        logging.exception("File-browser progress callback failed")

            if outcome is None:
                self._schedule(self.POLL_INTERVAL_MS, self.poll)
                return
            completion = self._on_done
            self._thread = None
            self._on_done = None
            self._on_progress = None
            # Completion may start another task and enter a modal Tk loop.
            # Its scheduled poll must be allowed to deliver the new result.
            self._polling = False
            if completion is not None:
                completion(outcome.result, outcome.error)
        finally:
            self._polling = False
