#!/usr/bin/env python3

"""
File-browser task-runner tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections import deque
from collections.abc import Callable
from threading import Event
from unittest.mock import MagicMock, call
from weakref import ref

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner, ProgressCallback


class TestBackgroundTaskRunner:
    """The single scheduling boundary serializes work and delivers on poll."""

    def test_user_receives_keyword_progress_arguments_on_the_ui_thread(self) -> None:
        """Given a typed callback boundary, preserve positional and keyword arguments."""
        runner = BackgroundTaskRunner(MagicMock())
        updates: list[tuple[int, int]] = []

        def task(report) -> None:
            report(2, total=10)

        def render(current: int, *, total: int) -> None:
            updates.append((current, total))

        assert runner.start(task, render, MagicMock())
        assert runner.thread is not None
        runner.thread.join(2)
        assert not updates
        runner.poll()
        assert updates == [(2, 10)]

    def test_completed_task_releases_its_progress_handler(self) -> None:
        """Given completed progress, deduplication must not retain a handler's widgets."""
        runner = BackgroundTaskRunner(MagicMock())

        class Handler:  # pylint: disable=too-few-public-methods
            """Stand in for a bound GUI progress handler."""

            def __call__(self, _current: int, _total: int) -> None:
                pass

        handler = Handler()
        reference = ref(handler)

        def task(report: ProgressCallback) -> None:
            report(1, 2)

        assert runner.start(task, handler, MagicMock())
        assert runner.thread is not None
        runner.thread.join(2)
        del handler
        runner.poll()
        assert reference() is None

    def test_user_receives_next_task_result_while_previous_completion_pumps_events(self) -> None:
        """
        Starting a task inside a modal completion callback must not strand it.

        GIVEN: A completion callback starts another task and processes scheduled events
        WHEN: The next task's poll runs before that callback returns
        THEN: Its result is delivered and the runner becomes idle
        """
        scheduled: deque[Callable[[], None]] = deque()
        deliveries: list[object] = []

        def schedule(_delay: int, callback: Callable[[], None]) -> None:
            scheduled.append(callback)

        runner = BackgroundTaskRunner(schedule)

        def next_done(result: object | None, error: Exception | None) -> None:
            assert error is None
            deliveries.append(result)

        def first_done(result: object | None, error: Exception | None) -> None:
            assert error is None
            deliveries.append(result)
            assert runner.start(lambda _report: "next result", None, next_done)
            assert runner.thread is not None
            runner.thread.join(timeout=2)
            assert not runner.thread.is_alive()
            # Dispatch the timer as a modal dialog's nested event loop would.
            scheduled.popleft()()
            deliveries.append("first callback returned")

        assert runner.start(lambda _report: "first result", None, first_done)
        assert runner.thread is not None
        runner.thread.join(timeout=2)
        assert not runner.thread.is_alive()

        scheduled.popleft()()

        assert deliveries == ["first result", "next result", "first callback returned"]
        assert not runner.active
        assert not scheduled

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

    def test_progress_callback_failure_does_not_strand_completion(self) -> None:
        """A broken UI progress handler must not leave the runner active forever."""
        runner = BackgroundTaskRunner(MagicMock())
        done = MagicMock()

        def task(report) -> str:
            report(1, 2)
            return "ready"

        def broken_progress(_current: int, _total: int) -> None:
            message = "progress display failed"
            raise ValueError(message)

        assert runner.start(task, broken_progress, done)
        assert runner.thread is not None
        runner.thread.join(timeout=2)
        runner.poll()

        done.assert_called_once_with("ready", None)
        assert not runner.active

    def test_idle_poll_reschedules_without_completing_a_task(self) -> None:
        """
        An idle UI poll keeps listening without inventing a task completion.

        GIVEN: No worker has posted a progress or completion message
        WHEN: The UI polls the task queue
        THEN: Another poll is scheduled and no completion is delivered
        """
        scheduled = MagicMock()
        runner = BackgroundTaskRunner(scheduled)

        runner.poll()

        scheduled.assert_called_once_with(runner.POLL_INTERVAL_MS, runner.poll)
        assert not runner.active

    @pytest.mark.parametrize("fail_download", [False, True])
    def test_user_sees_latest_progress_and_completion_after_three_large_downloads(self, fail_download: bool) -> None:
        """
        Packet-level progress must not delay a completed batch behind stale repaints.

        GIVEN: Three large downloads report thousands of packet-level progress updates
        WHEN: The GUI polls after the worker finishes or fails
        THEN: Only the latest progress is displayed before the terminal result
        """
        runner = BackgroundTaskRunner(MagicMock())
        progress = MagicMock()
        done = MagicMock()
        deliveries = MagicMock()
        deliveries.attach_mock(progress, "progress")
        deliveries.attach_mock(done, "done")
        downloaded = ("first.bin", "second.bin", "third.bin")
        failure = OSError("Download interrupted")

        def task(report: ProgressCallback) -> tuple[str, ...]:
            for file_index, _filename in enumerate(downloaded):
                for packet in range(5000):
                    report(file_index * 5000 + packet + 1, 15000)
            if fail_download:
                raise failure
            return downloaded

        assert runner.start(task, progress, done)
        assert runner.thread is not None
        runner.thread.join(timeout=2)
        assert not runner.thread.is_alive()

        runner.poll()

        assert progress.call_count == 1
        progress.assert_called_once_with(15000, 15000)
        done.assert_called_once_with(None if fail_download else downloaded, failure if fail_download else None)
        assert [delivery[0] for delivery in deliveries.mock_calls] == ["progress", "done"]
        assert not runner.active

    def test_user_can_process_gui_events_while_download_progress_keeps_arriving(self) -> None:
        """
        A progress poll yields even when the worker replenishes progress during rendering.

        GIVEN: A download worker waits for the GUI to start rendering progress
        WHEN: Rendering allows another burst of packet progress to arrive
        THEN: The current poll returns and the next poll displays the newest value
        """
        scheduled = MagicMock()
        runner = BackgroundTaskRunner(scheduled)
        initial_progress_ready = Event()
        rendering_started = Event()
        next_burst_ready = Event()
        release_worker = Event()
        seen: list[tuple[int, int]] = []
        done = MagicMock()

        def task(report: ProgressCallback) -> str:
            report(1, 100)
            initial_progress_ready.set()
            assert rendering_started.wait(timeout=2)
            for current in range(2, 101):
                report(current, 100)
            next_burst_ready.set()
            assert release_worker.wait(timeout=2)
            return "downloaded"

        def render(current: int, total: int) -> None:
            seen.append((current, total))
            rendering_started.set()
            assert next_burst_ready.wait(timeout=2)

        try:
            assert runner.start(task, render, done)
            assert initial_progress_ready.wait(timeout=2)
            runner.poll()

            assert seen == [(1, 100)]
            done.assert_not_called()
            assert runner.active
            assert scheduled.call_args.args == (runner.POLL_INTERVAL_MS, runner.poll)

            release_worker.set()
            assert runner.thread is not None
            runner.thread.join(timeout=2)
            assert not runner.thread.is_alive()
            runner.poll()

            assert seen == [(1, 100), (100, 100)]
            done.assert_called_once_with("downloaded", None)
        finally:
            rendering_started.set()
            release_worker.set()
            if runner.thread is not None:
                runner.thread.join(timeout=2)

    @pytest.mark.parametrize("next_total", [100, 200])
    def test_user_sees_progress_repainted_only_when_current_or_total_changes(self, next_total: int) -> None:
        """
        Unchanged packet progress does not repaint, but a changed total does.

        GIVEN: A worker repeatedly reports the same current value between GUI polls
        WHEN: The GUI polls again while the worker remains active
        THEN: Only a changed total causes a repaint, and completion is still delivered
        """
        runner = BackgroundTaskRunner(MagicMock())
        initial_progress_ready = Event()
        repeat_progress = Event()
        repeated_progress_ready = Event()
        release_worker = Event()
        progress = MagicMock()
        done = MagicMock()

        def task(report: ProgressCallback) -> str:
            report(30, 100)
            initial_progress_ready.set()
            assert repeat_progress.wait(timeout=2)
            for _packet in range(5000):
                report(30, next_total)
            repeated_progress_ready.set()
            assert release_worker.wait(timeout=2)
            return "downloaded"

        try:
            assert runner.start(task, progress, done)
            assert initial_progress_ready.wait(timeout=2)
            runner.poll()
            repeat_progress.set()
            assert repeated_progress_ready.wait(timeout=2)
            runner.poll()

            expected = [call(30, 100)]
            if next_total != 100:
                expected.append(call(30, next_total))
            assert progress.call_count == len(expected)
            assert progress.call_args_list == expected
            done.assert_not_called()

            release_worker.set()
            assert runner.thread is not None
            runner.thread.join(timeout=2)
            assert not runner.thread.is_alive()
            runner.poll()
            done.assert_called_once_with("downloaded", None)
        finally:
            repeat_progress.set()
            release_worker.set()
            if runner.thread is not None:
                runner.thread.join(timeout=2)

    def test_user_sees_the_same_progress_again_when_starting_another_download(self) -> None:
        """
        Progress coalescing is isolated to one download attempt.

        GIVEN: A completed download reported a particular progress value
        WHEN: The next download reports that same value
        THEN: The new attempt displays it and receives its own completion
        """
        runner = BackgroundTaskRunner(MagicMock())
        progress = MagicMock()
        done = MagicMock()

        def task(report: ProgressCallback) -> str:
            report(100, 100)
            return "downloaded"

        for _attempt in range(2):
            assert runner.start(task, progress, done)
            assert runner.thread is not None
            runner.thread.join(timeout=2)
            assert not runner.thread.is_alive()
            runner.poll()

        assert progress.call_args_list == [call(100, 100), call(100, 100)]
        assert done.call_args_list == [call("downloaded", None), call("downloaded", None)]

    def test_user_receives_completion_after_progress_rendering_even_if_tk_reenters_poll(self) -> None:
        """
        Reentrant painting cannot finalize a task inside its progress callback.

        GIVEN: A completed worker has both final progress and completion pending
        WHEN: Painting that progress reenters the task poll, as Tk can on macOS
        THEN: Completion is delivered exactly once after the progress callback returns
        """
        runner = BackgroundTaskRunner(MagicMock())
        deliveries: list[str] = []

        def task(report: ProgressCallback) -> str:
            report(100, 100)
            return "downloaded"

        def render(_current: int, _total: int) -> None:
            deliveries.append("render started")
            runner.poll()
            deliveries.append("render finished")

        def done(_result: object | None, _error: Exception | None) -> None:
            deliveries.append("done")

        assert runner.start(task, render, done)
        assert runner.thread is not None
        runner.thread.join(timeout=2)
        assert not runner.thread.is_alive()
        runner.poll()

        assert deliveries == ["render started", "render finished", "done"]
        assert not runner.active
