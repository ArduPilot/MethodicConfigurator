"""
Run file-browser work off the Tk thread and return results on that thread.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import queue
from collections.abc import Callable
from threading import Thread
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


class BackgroundTaskRunner:
    """Execute one task at a time, polling its queue on the UI thread."""

    POLL_INTERVAL_MS = 50

    def __init__(self, schedule: Callable[[int, Callable[[], None]], object]) -> None:
        self._schedule = schedule
        self._messages: queue.Queue[_ProgressMessage | _DoneMessage] = queue.Queue()
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
        self._on_progress = on_progress
        self._on_done = on_done

        def report_progress(current: int, total: int) -> None:
            self._messages.put(_ProgressMessage(current, total))

        def run() -> None:
            try:
                outcome = _DoneMessage(task(report_progress), None)
            except Exception as error:  # pylint: disable=broad-exception-caught
                outcome = _DoneMessage(None, error)
            self._messages.put(outcome)

        self._thread = Thread(target=run, name="mavftp-browser-task", daemon=True)
        self._thread.start()
        self._schedule(self.POLL_INTERVAL_MS, self.poll)
        return True

    def poll(self) -> None:
        """Drain progress and deliver the final result on the scheduling thread."""
        while True:
            try:
                message = self._messages.get_nowait()
            except queue.Empty:
                self._schedule(self.POLL_INTERVAL_MS, self.poll)
                return
            if isinstance(message, _ProgressMessage):
                if self._on_progress is not None:
                    self._on_progress(message.current, message.total)
                continue
            completion = self._on_done
            self._thread = None
            self._on_done = None
            self._on_progress = None
            if completion is not None:
                completion(message.result, message.error)
            return
