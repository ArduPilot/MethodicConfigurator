"""
TKinter progress window class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

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

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        master,  # noqa: ANN001
        title: str,
        message: str = "",
        width: int = 300,
        height: int = 80,
        only_show_when_update_progress_called: bool = False,
    ) -> None:
        self.parent = master
        self.message = message
        self.only_show_when_update_progress_called = only_show_when_update_progress_called
        self._shown = False
        self.progress_window = tk.Toplevel(self.parent)
        # Withdraw immediately to prevent flicker while setting up
        self.progress_window.withdraw()
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

        if not isinstance(master, tk.Tk):
            logging_error("ProgressWindow: master is not a tk.Tk instance, window centering will fail")

        if not self.only_show_when_update_progress_called:
            self.progress_window.deiconify()  # needs to be done before centering, but it does flicker :(

        # Center the progress window on the parent window while still withdrawn
        BaseWindow.center_window(self.progress_window, self.parent)

        if not self.only_show_when_update_progress_called:
            # Show the window now that it's properly positioned
            self.progress_window.lift()
            self._shown = True
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
            # Double check that the window still exists before updating
            if (
                hasattr(self, "progress_window") is False
                or self.progress_window is None
                or not self.progress_window.winfo_exists()
            ):
                return

            if self.only_show_when_update_progress_called and not self._shown:
                self.progress_window.deiconify()
                # Re-center the window when it's first shown
                BaseWindow.center_window(self.progress_window, self.parent)
                self.progress_window.lift()
                self._shown = True
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

                self.progress_bar.update()

                # Close the progress window when the process is complete
                if current_value == max_value:
                    self.progress_window.destroy()
        except tk.TclError as _e:
            msg = _("Updating progress widgets: {_e}")
            logging_error(msg.format(**locals()))

    def destroy(self) -> None:
        self.progress_window.destroy()
