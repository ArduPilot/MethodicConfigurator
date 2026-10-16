"""
Data telemetry connectivity checks and a shared-stream MAVLink inspector.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from contextlib import suppress
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_data_telemetry import DataTelemetryBackend
from ardupilot_methodic_configurator.data_model_data_telemetry import DataTelemetryDataModel, TelemetryState
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_radio_status import RadioStatusView
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_DATA_TELEMETRY
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason


class DataTelemetryView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Present connectivity measurements and bench-test instructions at step 08."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: DataTelemetryDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self.backend = DataTelemetryBackend(model.flight_controller)
        self._timer_id: str | None = None
        self._state = TelemetryState()
        self._setup_ui()
        self._show_state(self._state)
        self.on_activate()

    def _setup_ui(self) -> None:
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        content = scroll.view_port
        content.columnconfigure(1, weight=1)
        self.instructions = ttk.Label(
            content,
            text=_(
                "If necessary change the parameters below and press 'Upload selected params to FC' to activate them. "
                "A USB connection measures USB traffic, not the radio link. Once telemetry is configured, with propellers "
                "removed and the vehicle disarmed, connect AMC through the telemetry link you want to test. "
                "Check RX/TX datarates and local/remote RSSI while changing antenna orientation and separation within a "
                "safe bench-test range. Interrupt the telemetry link briefly, check that readings become unavailable, "
                "then restore it and check recovery. Press 'MAVLink inspector' above to check messages and their rates."
            ),
            wraplength=500,
            justify="left",
        )
        self.instructions.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        content.bind("<Configure>", self._resize_instructions, add="+")
        self.radio_status = RadioStatusView(content)
        self.radio_status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2))

    def _resize_instructions(self, event: tk.Event) -> None:
        self.instructions.configure(wraplength=max(100, event.width - 12))

    def _show_state(self, state: TelemetryState) -> None:
        self.radio_status.update_state(state)

    def _check_telemetry(self) -> None:
        self._timer_id = None
        # Modal FC tools (including the file browser) own their receive loop.
        # Native Tk dialogs may hold the grab without a Python widget wrapper.
        # Query the Tcl path directly; grab_current() tries to resolve that path
        # to a Python widget and raises KeyError for such dialogs.
        modal_open = bool(self.tk.call("grab", "current", str(self)))
        if modal_open or self.base_window.navigation_lock.locked:
            self._timer_id = self.after(250, self._check_telemetry)
            return
        self._state = self.model.update(self.backend.poll())
        self._show_state(self._state)
        self._timer_id = self.after(250, self._check_telemetry)

    def on_activate(self) -> None:
        """Resume exactly one measurement loop."""
        if self._timer_id is None:
            self._timer_id = self.after(250, self._check_telemetry)

    # pylint: disable-next=unused-argument
    def on_suspend(self, reason: PluginPauseReason = PluginPauseReason.EXCLUSIVE_OPERATION) -> None:  # noqa: ARG002
        """Pause observations while uploads or diagnostics own the FC connection."""
        self.on_deactivate()

    def on_resume(self) -> None:
        """Resume with fresh measurement baselines after an exclusive FC operation."""
        self.on_activate()

    def on_deactivate(self) -> None:
        """Yield the connection, cancel callbacks and close child windows when hidden."""
        if self._timer_id is not None:
            with suppress(tk.TclError):
                self.after_cancel(self._timer_id)
            self._timer_id = None
        self.backend.close()
        self.model.clear_live_data()
        self._state = TelemetryState()
        if self.winfo_exists():
            self._show_state(self._state)

    def destroy(self) -> None:
        self.on_deactivate()
        super().destroy()


def _create_data_telemetry_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> DataTelemetryView:
    return DataTelemetryView(parent, model, base_window)  # type: ignore[arg-type]


def _create_data_telemetry_model(context: PluginModelContext) -> DataTelemetryDataModel:
    return DataTelemetryDataModel(context.flight_controller)


def register_data_telemetry_plugin() -> None:
    """Register the FC-required monitor and its model through the shared dispatcher."""
    plugin_factory.register(PLUGIN_DATA_TELEMETRY, _create_data_telemetry_view, _create_data_telemetry_model)
