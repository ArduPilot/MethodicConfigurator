#!/usr/bin/env python3

"""
File-browser task-runner tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner


class TestBackgroundTaskRunner:
    """The single scheduling boundary serializes work and delivers on poll."""

    def test_progress_and_success_are_delivered_in_order(self) -> None:
        """Worker messages stay queued until the UI polls."""
        scheduled = MagicMock()
        runner = BackgroundTaskRunner(scheduled)
        progress = MagicMock()
        done = MagicMock()

        def task(report) -> str:
            report(3, 10)
            return "ready"

        assert runner.start(task, progress, done)
        assert not runner.start(task, progress, done)
        assert runner.thread is not None
        runner.thread.join(timeout=2)
        done.assert_not_called()
        runner.poll()
        progress.assert_called_once_with(3, 10)
        done.assert_called_once_with("ready", None)
        assert not runner.active
        assert runner.start(lambda _report: "next", None, MagicMock())
        assert runner.thread is not None
        runner.thread.join(timeout=2)
        runner.poll()

    def test_failure_is_delivered_without_progress(self) -> None:
        """An exception is reported on the UI side rather than lost in a thread."""
        runner = BackgroundTaskRunner(MagicMock())
        done = MagicMock()

        def task(_report) -> None:
            message = "broken"
            raise ValueError(message)

        assert runner.start(task, None, done)
        assert runner.thread is not None
        runner.thread.join(timeout=2)
        runner.poll()
        result, error = done.call_args.args
        assert result is None
        assert isinstance(error, ValueError)
        assert not runner.active
