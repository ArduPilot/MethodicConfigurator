#!/usr/bin/env python3

"""
Static regression checks: run mypy with --warn-unused-ignores on this file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable

from ardupilot_methodic_configurator.data_model_transfer_progress import TransferProgress
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner, TaskRunner


def download(report: Callable[[TransferProgress], None]) -> None:
    """A download emits exactly one structured argument."""
    report(TransferProgress(5, 10))


def count_progress(_current: int, _total: int) -> None:
    """An ordinary progress handler requires two integer arguments."""


def download_progress(_progress: TransferProgress) -> None:
    """A download handler accepts the worker's structured snapshot."""


def done(_result: object | None, _error: Exception | None) -> None:
    """Completion uses the independent result and error channel."""


def check_protocol(runner: TaskRunner) -> None:
    """The scheduling protocol accepts matching callbacks and rejects mismatches."""
    runner.start(download, download_progress, done)
    runner.start(download, count_progress, done)  # type: ignore[misc]


def check_implementation() -> None:
    """Keep the implementation's signature as strict as its protocol."""
    runner = BackgroundTaskRunner(lambda _delay, _callback: None)
    runner.start(download, download_progress, done)
    runner.start(download, count_progress, done)  # type: ignore[misc]
