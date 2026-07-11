"""
Shared base class for calibration popup windows.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from contextlib import suppress
from tkinter import ttk
from typing import Generic, TypeVar, cast

_ModelT = TypeVar("_ModelT")


class CalibrationPopupBase(tk.Toplevel, Generic[_ModelT]):  # pylint: disable=too-many-instance-attributes
    """Base class for calibration popup windows with draggable title bar and progress polling."""

    _MIN_WIDTH: int = 560
    _MIN_HEIGHT: int = 320

    def __init__(self, parent: tk.Widget, model: _ModelT) -> None:
        super().__init__(parent)
        self.model: _ModelT = model
        self._parent = parent
        self._bg_color: str = ""

        self.overrideredirect(boolean=True)
        self.transient(cast("tk.Wm", parent))
        self.grab_set()

        # Variables for custom window dragging
        self._drag_x = 0
        self._drag_y = 0

        self._timer_id: str | None = None
        self._polls_without_updates = 0
        self._no_telemetry_warning_emitted = False

    def destroy(self) -> None:
        """Stop polling before destroying the popup."""
        self._stop_polling()
        super().destroy()

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        self._bg_color = style.lookup("TFrame", "background") or self.cget("bg")
        style.configure(
            "Horizontal.TProgressbar",
            borderwidth=0,
            thickness=24,
        )
        style.configure(
            "Done.Horizontal.TProgressbar",
            background="#8fbc8f",
            borderwidth=0,
            thickness=24,
            troughcolor=style.lookup("Horizontal.TProgressbar", "troughcolor"),
        )

    def _create_framed_ui(self, title_text: str) -> ttk.Frame:
        """Create outer frame, draggable title bar, and return the content frame."""
        self.configure(bg=self._bg_color)
        outer_frame = tk.Frame(self, bg=self._bg_color, highlightthickness=0)
        outer_frame.pack(fill="both", expand=True)

        title_bar = tk.Frame(outer_frame, bg="#e0e0e0", relief="flat", bd=0)
        title_bar.pack(fill="x", side="top")
        title_bar.bind("<ButtonPress-1>", self._start_move)
        title_bar.bind("<B1-Motion>", self._do_move)

        title_label = tk.Label(title_bar, text=title_text, bg="#e0e0e0", fg="black", font=("TkDefaultFont", 11, "bold"))
        title_label.pack(side="left", padx=10, pady=5)
        title_label.bind("<ButtonPress-1>", self._start_move)
        title_label.bind("<B1-Motion>", self._do_move)

        content_frame = ttk.Frame(outer_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        return content_frame

    def _start_move(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_move(self, event: tk.Event) -> None:
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _resize_and_center(self) -> None:
        self.update_idletasks()
        self.minsize(self._MIN_WIDTH, self._MIN_HEIGHT)

        width = max(self.winfo_reqwidth(), self._MIN_WIDTH)
        height = max(self.winfo_reqheight(), self._MIN_HEIGHT)
        self.geometry(f"{width}x{height}")
        self.update_idletasks()

        parent_x = self._parent.winfo_rootx()
        parent_y = self._parent.winfo_rooty()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _stop_polling(self) -> None:
        """Cancel the periodic polling callback if it is active."""
        if self._timer_id:
            with suppress(tk.TclError):
                self.after_cancel(self._timer_id)
            self._timer_id = None
