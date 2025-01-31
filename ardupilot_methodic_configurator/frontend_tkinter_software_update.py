"""
Check for software updates and install them if available.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ardupilot_methodic_configurator import _, __version__


class UpdateDialog:  # pylint: disable=too-many-instance-attributes
    """Dialog for displaying software update information and handling user interaction."""

    def __init__(self, version_info: str, download_callback: Optional[Callable[[], bool]] = None) -> None:
        self.root = tk.Tk()
        self.root.title(_("Amilcar Lucas's - ArduPilot methodic configurator ") + __version__ + _(" - New version available"))
        self.download_callback = download_callback
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.frame = ttk.Frame(self.root, padding="20")
        self.frame.grid(sticky="nsew")

        self.msg = ttk.Label(self.frame, text=version_info, wraplength=650, justify="left")
        self.msg.grid(row=0, column=0, columnspan=2, pady=20)

        self.progress = ttk.Progressbar(self.frame, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=1, column=0, columnspan=2, pady=10, padx=10)
        self.progress.grid_remove()

        self.status_label = ttk.Label(self.frame, text="")
        self.status_label.grid(row=2, column=0, columnspan=2)

        self.result: Optional[bool] = None
        self._setup_buttons()

    def _setup_buttons(self) -> None:
        self.yes_btn = ttk.Button(self.frame, text=_("Update Now"), command=self.on_yes)
        self.no_btn = ttk.Button(self.frame, text=_("Not Now"), command=self.on_no)
        self.yes_btn.grid(row=3, column=0, padx=5)
        self.no_btn.grid(row=3, column=1, padx=5)

    def update_progress(self, value: float, status: str = "") -> None:
        """Update progress directly."""
        self.progress["value"] = value
        if status:
            self.status_label["text"] = status
        self.root.update()

    def on_yes(self) -> None:
        self.progress.grid()
        self.status_label.grid()
        self.yes_btn.config(state="disabled")
        self.no_btn.config(state="disabled")

        if self.download_callback:
            success = self.download_callback()
            if success:
                self.status_label["text"] = _("Update complete! Please restart the application.")
                self.result = True
            else:
                self.status_label["text"] = _("Update failed!")
                self.yes_btn.config(state="normal")
                self.no_btn.config(state="normal")
                self.result = False
            self.root.after(4000, self.root.destroy)

    def on_no(self) -> None:
        self.result = False
        self.root.destroy()

    def on_cancel(self) -> None:
        self.result = False
        self.root.destroy()

    def show(self) -> bool:
        """
        Display the update dialog and return user's choice.

        Returns:
            bool: True if user chose to update and the update was successful, False otherwise

        """
        self.root.mainloop()
        return bool(self.result)
