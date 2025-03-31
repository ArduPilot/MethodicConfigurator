"""
TKinter progress window class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk
from logging import error as logging_error
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow


class ProgressWindow:
    """
    A class for creating and managing a progress window in the application.

    This class is responsible for creating a progress window that displays the progress of
    a task. It includes a progress bar and a label to display the progress message.
    """

    def __init__(self, master, title: str, message: str = "", width: int = 300, height: int = 80) -> None:  # noqa: ANN001, pylint: disable=too-many-arguments, too-many-positional-arguments
        self.parent = master
        self.message = message
        self.progress_window = tk.Toplevel(self.parent)
        self.progress_window.title(title)
        self.progress_window.geometry(f"{width}x{height}")

        main_frame = ttk.Frame(self.progress_window)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Create a progress bar
        self.progress_bar = ttk.Progressbar(main_frame, length=100, mode="determinate")
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, expand=False, padx=(5, 5), pady=(10, 10))

        # Create a label to display the progress message
        self.progress_label = ttk.Label(main_frame, text=message.format(0, 0))
        self.progress_label.pack(side=tk.TOP, fill=tk.X, expand=False, pady=(10, 10))

        self.progress_window.lift()

        # Center the progress window on the parent window
        BaseWindow.center_window(self.progress_window, self.parent)

        self.progress_bar.update()

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
            if hasattr(self, "progress_window") is False or self.progress_window is None:
                return
            self.progress_window.lift()
        except tk.TclError as _e:
            msg = _("Lifting window: {_e}")
            logging_error(msg.format(**locals()))
            return

        self.progress_bar["value"] = current_value
        self.progress_bar["maximum"] = max_value

        # Update the progress message
        self.progress_label.config(text=self.message.format(current_value, max_value))

        self.progress_bar.update()

        # Close the progress window when the process is complete
        if current_value == max_value:
            self.progress_window.destroy()

    def destroy(self) -> None:
        self.progress_window.destroy()
