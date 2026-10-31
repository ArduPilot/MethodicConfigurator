"""
Reusable embedded ESC telemetry table and polling lifecycle.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from contextlib import suppress
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_esc_telemetry import EscTelemetryBackend
from ardupilot_methodic_configurator.data_model_esc_telemetry import MAX_ESCS, EscTelemetryDataModel, EscTelemetrySnapshot
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import Tooltip
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason


class EscTelemetryView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Display one ESC per column and yield polling during exclusive FC operations."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: EscTelemetryDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self.backend = EscTelemetryBackend(model.flight_controller)
        self._timer_id: str | None = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        ttk.Label(self, text=_("ESC telemetry"), anchor="w").grid(row=0, column=0, sticky="ew", padx=4)
        self.table = ttk.Treeview(
            self, columns=tuple(str(i) for i in range(1, MAX_ESCS + 1)), height=6, show="tree headings", selectmode="none"
        )
        self.table.heading("#0", text=_("Measurement"))
        self.table.column("#0", width=160, minwidth=130, stretch=False)
        for index in range(1, MAX_ESCS + 1):
            self.table.heading(str(index), text=_("ESC %(number)d") % {"number": index})
            self.table.column(str(index), width=55, minwidth=50, stretch=False, anchor="e")
        self.table.grid(row=1, column=0, sticky="nsew", padx=4)
        scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.table.xview)
        scrollbar.grid(row=2, column=0, sticky="ew", padx=4)
        self.table.configure(xscrollcommand=scrollbar.set)
        self.tooltip = Tooltip(
            self.table,
            _(
                "Live ESC readings. Missing or stale data is shown as '-'. "
                "ESC numbers follow the flight controller's ESC telemetry offset. "
                "For configured bidirectional DShot outputs, 0* means the group reported zero RPM; "
                "the individual output may instead be unavailable."
            ),
        )
        self.scroll_tooltip = Tooltip(scrollbar, _("Scroll to view additional ESC columns."))
        for index, label in enumerate(model.row_labels()):
            self.table.insert("", "end", iid=str(index), text=label)
        self._show_rows(model.update(EscTelemetrySnapshot(None, 0)))
        self.on_activate()

    def _show_rows(self, rows: tuple[tuple[str, ...], ...]) -> None:
        self.table.configure(displaycolumns=tuple(str(i + 1) for i in self.model.visible_esc_indices))
        for index, values in enumerate(rows):
            self.table.item(str(index), values=values)

    def _poll(self) -> None:
        if self._timer_id is None:
            return
        self._timer_id = None
        if not self.tk.call("grab", "current", str(self)) and not self.base_window.navigation_lock.locked:
            self._show_rows(self.model.update(self.backend.poll()))
        self._timer_id = self.after(250, self._poll)

    def on_activate(self) -> None:
        """Schedule exactly one receiver loop."""
        if self._timer_id is None:
            self._timer_id = self.after(250, self._poll)

    def on_deactivate(self) -> None:
        """Cancel the receiver and clear stale observations."""
        if self._timer_id is not None:
            with suppress(tk.TclError):
                self.after_cancel(self._timer_id)
            self._timer_id = None
        self.backend.close()
        self.model.clear_live_data()
        if self.winfo_exists():
            self._show_rows(self.model.update(EscTelemetrySnapshot(None, 0)))

    def on_suspend(self, _reason: PluginPauseReason = PluginPauseReason.EXCLUSIVE_OPERATION) -> None:
        """Yield the connection to uploads and diagnostics."""
        self.on_deactivate()

    def on_resume(self) -> None:
        """Restart observations after an exclusive FC operation."""
        self.on_activate()

    def destroy(self) -> None:
        self.on_deactivate()
        super().destroy()
