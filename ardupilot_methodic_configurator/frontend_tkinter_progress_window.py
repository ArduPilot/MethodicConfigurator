"""
TKinter progress window class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import contextlib
import tkinter as tk
from collections.abc import Callable, Iterator
from logging import error as logging_error
from tkinter import ttk
from typing import TypeVar, cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.macos_utilites import is_macos_sequoia_or_older

_TaskResult = TypeVar("_TaskResult")


class ProgressWindow:  # pylint: disable=too-many-instance-attributes
    """
    A class for creating and managing a progress window in the application.

    This class is responsible for creating a progress window that displays the progress of
    a task. It includes a progress bar and a label to display the progress message.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        master,  # noqa: ANN001
        title: str,
        message: str = "",
        width: int = 300,
        height: int = 80,
        only_show_when_update_progress_called: bool = False,
        auto_close_on_complete: bool = True,
    ) -> None:
        self.parent = master
        self.message = message
        self.only_show_when_update_progress_called = only_show_when_update_progress_called
        self.auto_close_on_complete = auto_close_on_complete
        self._shown = False
        self._task_active = False
        self.progress_window = tk.Toplevel(self.parent)
        # Withdraw immediately to prevent flicker while setting up
        self.progress_window.withdraw()
        self.progress_window.title(title)
        try:
            dpi = self.progress_window.winfo_fpixels("1i")
            tk_scaling = float(self.progress_window.tk.call("tk", "scaling"))
            normalized_tk_scaling = tk_scaling * 72.0 / 96.0
            dpi_scaling_factor = max(1.0, dpi / 96.0, normalized_tk_scaling)
        except (tk.TclError, AttributeError):
            dpi_scaling_factor = 1.0
        self.progress_window.geometry(f"{round(width * dpi_scaling_factor)}x{round(height * dpi_scaling_factor)}")

        main_frame = ttk.Frame(self.progress_window)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Create a progress bar
        self.progress_bar = ttk.Progressbar(main_frame, length=100, mode="determinate")
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, expand=False, padx=(5, 5), pady=(10, 10))

        # Create a label to display the progress message
        self.progress_label = ttk.Label(main_frame, text=message.format(0, 0))
        self.progress_label.pack(side=tk.TOP, fill=tk.X, expand=False, pady=(10, 10))

        if not isinstance(master, (tk.Tk, tk.Toplevel)):
            logging_error("ProgressWindow: master is not a tk.Tk or tk.Toplevel instance, window centering may fail")

        if not self.only_show_when_update_progress_called:
            self.progress_window.deiconify()  # needs to be done before centering, but it does flicker :(

        if not self.only_show_when_update_progress_called:
            self._center_progress_window()
            # Show the window now that it's properly positioned
            self.progress_window.lift()
            self._shown = True
            # Idle updates repaint without dispatching queued user events.
            if not is_macos_sequoia_or_older():
                self.progress_window.update_idletasks()

    def _center_progress_window(self) -> None:
        """
        Center the progress window on screen or relative to its parent.

        Uses screen centering when the parent is not viewable (e.g., a withdrawn temp root
        in FlightControllerConnectionProgress). On Windows, withdrawn windows can report
        winfo_width() > 1, so winfo_viewable() is checked as well.
        """
        if isinstance(self.parent, tk.Tk) and (self.parent.winfo_width() <= 1 or not self.parent.winfo_viewable()):
            BaseWindow.center_window_on_screen(self.progress_window)
        else:
            BaseWindow.center_window(self.progress_window, self.parent)

    def update_progress_bar_300_pct(self, percent: int) -> None:
        self.message = _("Please be patient, {:.1f}% of {}% complete")
        self.update_progress_bar(int(percent / 3), max_value=100)

    def update_progress_bar(self, current_value: int, max_value: int) -> None:
        """
        Update the progress bar and the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value, if 0 uses percentage.

        """
        try:
            # Double check that the window still exists before updating
            if (
                hasattr(self, "progress_window") is False
                or self.progress_window is None
                or not self.progress_window.winfo_exists()
            ):
                return

            if self.only_show_when_update_progress_called and not self._shown:
                if not is_macos_sequoia_or_older():
                    self.progress_window.update_idletasks()
                self.progress_window.deiconify()
                self._center_progress_window()
                self.progress_window.lift()
                self._shown = True
                if not is_macos_sequoia_or_older():
                    self.progress_window.update_idletasks()
            elif not self.only_show_when_update_progress_called:
                self.progress_window.lift()

            # Additional safety checks before updating widgets
            if (
                hasattr(self, "progress_bar")
                and self.progress_bar is not None
                and hasattr(self, "progress_label")
                and self.progress_label is not None
            ):
                self.progress_bar["value"] = current_value
                self.progress_bar["maximum"] = max_value

                # Update the progress message
                self.progress_label.config(text=self.message.format(current_value, max_value))

                # Defer rendering on Sequoia and older; idle updates on other
                # platforms repaint without dispatching pending user events.
                if not is_macos_sequoia_or_older():
                    self.progress_window.update_idletasks()

                # Close the progress window when the process is complete
                if current_value == max_value and self.auto_close_on_complete:
                    self.progress_window.destroy()
        except tk.TclError as _e:
            msg = _("Updating progress widgets: {_e}")
            logging_error(msg.format(**locals()))

    def update_progress_bar_with_message(self, current_value: int, max_value: int, message: str) -> None:
        """Update the progress bar while replacing its displayed message."""
        self.message = message
        self.update_progress_bar(current_value, max_value)

    def run_task(self, task: Callable[[Callable[[int, int], None]], _TaskResult]) -> _TaskResult:
        """
        Run blocking work on a worker while Tk renders progress on its own thread.

        The task receives a queue-backed progress callback and must not touch Tk.
        Parent controls and close handlers are suspended until the result is
        delivered, preventing a second operation during the nested wait.
        Exceptions are re-raised on the caller's thread after restoring the UI.
        """
        if self._task_active:
            message = "A progress task is already running"
            raise RuntimeError(message)

        parent = cast("tk.Tk | tk.Toplevel", self.parent.winfo_toplevel())
        completed = tk.BooleanVar(master=parent, value=False)
        result: list[object] = []
        errors: list[BaseException] = []
        runner = BackgroundTaskRunner(parent.after)

        def work(report: Callable[[int, int], None]) -> None:
            try:
                result.append(task(report))
            except BaseException as error:  # pylint: disable=broad-exception-caught
                # SystemExit must also reach the caller instead of stranding the wait.
                errors.append(error)

        def finish(_result: object, _error: Exception | None) -> None:
            completed.set(True)

        self._task_active = True
        try:
            with self._suspend_parent_interaction(parent):
                runner.start(work, self.update_progress_bar, finish)
                parent.wait_variable(completed)
        finally:
            self._task_active = False

        if errors:
            raise errors[0]
        return cast("_TaskResult", result[0])

    @contextlib.contextmanager
    def _suspend_parent_interaction(self, parent: tk.Tk | tk.Toplevel) -> Iterator[None]:
        """Preserve control and close-handler states while a worker owns the UI."""
        lock = NavigationLock()
        pending = list(parent.winfo_children())
        while pending:
            widget = pending.pop()
            if isinstance(widget, tk.Toplevel):
                continue
            if isinstance(widget, ttk.Widget):
                lock.register(widget)
            pending.extend(widget.winfo_children())

        close_handlers: list[tuple[tk.Tk | tk.Toplevel, str, str]] = []
        try:
            lock.acquire(self)
            for window in (parent, self.progress_window):
                previous = window.protocol("WM_DELETE_WINDOW")
                window.protocol("WM_DELETE_WINDOW", lambda: None)
                close_handlers.append((window, previous, window.protocol("WM_DELETE_WINDOW")))
            yield
        finally:
            lock.release(self)
            for window, previous, temporary in close_handlers:
                with contextlib.suppress(tk.TclError):
                    window.protocol("WM_DELETE_WINDOW", previous)
                with contextlib.suppress(tk.TclError):
                    window.deletecommand(temporary)

    def destroy(self) -> None:
        try:
            if self.progress_window.winfo_exists():
                self.progress_window.destroy()
        except tk.TclError:
            pass


def update_flight_controller_restart_progress(progress_window: ProgressWindow, current: int, total: int) -> None:
    """Render reset, reboot countdown, and reconnect progress in one window."""
    if current == 10 and total == 100:
        message = _("Reset command sent")
    elif 10 < current < 30 and total == 100:
        message = _("Waiting for flight controller restart")
    elif 30 <= current < 90 and total == 100:
        # The callback supplies only normalized progress; it does not carry
        # the configured retry count. Avoid presenting a stale hard-coded
        # attempt total when callers choose a value other than three retries.
        message = _("Reconnecting to flight controller")
    elif current == 90 and total == 100:
        message = _("Retrieving flight controller information")
    elif current == 100 and total == 100:
        message = _("Flight Controller connected")
    else:
        message = _("Restarting Flight Controller")
    progress_window.update_progress_bar_with_message(current, total, message)
