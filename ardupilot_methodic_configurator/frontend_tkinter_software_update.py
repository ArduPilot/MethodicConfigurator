"""
Check for software updates and install them if available.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.macos_utilities import is_macos_sequoia_or_older


class UpdateDialog(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Dialog for displaying software update information and handling user interaction."""

    def __init__(
        self,
        version_info: str,
        download_callback: Callable[[Callable[[float, str], None]], bool] | None = None,
    ) -> None:
        super().__init__()
        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator {version} - New version available").format(
                version=__version__
            )
        )
        self.root.geometry(self.calculate_scaled_geometry(700, 600))
        self.center_window_on_screen(self.root)
        self.download_callback = download_callback
        self._download_runner = BackgroundTaskRunner(self.root.after)
        self._close_timer_id: str | None = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.frame = ttk.Frame(self.main_frame, padding="10")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Configure main frame to expand
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_columnconfigure(1, weight=1)

        version_info_scroll_frame = ScrollFrame(self.frame)
        version_info_scroll_frame.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")

        viewport = version_info_scroll_frame.view_port
        viewport.grid_columnconfigure(0, weight=1)
        viewport.grid_rowconfigure(0, weight=1)

        self.msg = ttk.Label(viewport, text=version_info, justify="left")
        self.msg.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.progress = ttk.Progressbar(self.frame, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=1, column=0, columnspan=2, pady=10, padx=10, sticky="ew")
        self.progress.grid_remove()

        self.status_label = ttk.Label(self.frame, text="")
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.result: bool | None = None
        self._setup_buttons()

        self.root.bind("<Configure>", self._on_window_resize)

    def _setup_buttons(self) -> None:
        self.yes_btn = ttk.Button(self.frame, text=_("Update Now"), command=self.on_yes)
        self.no_btn = ttk.Button(self.frame, text=_("Not Now"), command=self.on_no)
        self.yes_btn.grid(row=3, column=0, padx=5)
        self.no_btn.grid(row=3, column=1, padx=5)

    def _on_window_resize(self, event: tk.Event) -> None:
        """Update label wraplength when window is resized."""
        # Get window width and account for padding
        window_width = event.width - 50
        self.msg.configure(wraplength=window_width)

    def update_progress(self, value: float, status: str = "") -> None:
        """Update progress directly."""
        self.progress["value"] = value
        if status:
            self.status_label["text"] = status
        if not is_macos_sequoia_or_older():
            self.root.update_idletasks()

    def on_yes(self) -> None:
        if self._download_runner.active:
            return
        self._cancel_pending_close()
        self.progress.grid()
        self.status_label.grid()
        self.yes_btn.config(state="disabled")
        self.no_btn.config(state="disabled")

        if self.download_callback:
            self._download_runner.start(self.download_callback, self.update_progress, self._on_download_complete)

    def _on_download_complete(self, result: object | None, error: Exception | None) -> None:
        """Display the worker's result on the Tk thread."""
        self.result = bool(result) and error is None
        if self.result:
            self.status_label["text"] = _("Update complete! Please restart the application.")
        else:
            self.status_label["text"] = _("Update failed!")
            self.yes_btn.config(state="normal")
            self.no_btn.config(state="normal")
        self._cancel_pending_close()
        self._close_timer_id = self.root.after(4000, self.root.destroy)

    def _cancel_pending_close(self) -> None:
        """Keep a previous attempt's close deadline from interrupting a retry."""
        if self._close_timer_id is not None:
            self.root.after_cancel(self._close_timer_id)
            self._close_timer_id = None

    def on_no(self) -> None:
        if self._download_runner.active:
            return
        self._cancel_pending_close()
        self.result = False
        self.root.destroy()

    def on_cancel(self) -> None:
        if self._download_runner.active:
            return
        self._cancel_pending_close()
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
