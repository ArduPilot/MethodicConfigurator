"""
Display the active flight mode and RC switch slot above the parameter table.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.plugins.data_model_flight_modes import FlightModesDataModel, FlightModesState
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import cancel_plugin_timer
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_FLIGHT_MODES
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

_POLL_MS = 200


class FlightModesView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Show the reported flight mode alongside the slot indicated by the RC switch."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: FlightModesDataModel, base_window: "BaseWindow") -> None:
        super().__init__(parent, padding=4)
        self.model = model
        self._navigation_lock = base_window.navigation_lock
        self._timer_id: str | None = None
        self.mode_status_note = ttk.Label(
            self,
            text=_(
                "The active mode can differ during failsafe, when a mode change is rejected, "
                "or when another input selects the mode."
            ),
        )
        self.mode_status_note.pack(anchor="w")
        self.active_mode = ttk.Label(self)
        self.active_mode.pack(anchor="w")
        self.switch_slot = ttk.Label(self)
        self.switch_slot.pack(anchor="w")
        self._show_state(FlightModesState())

    def _show_state(self, state: FlightModesState) -> None:
        mode = _("Unavailable")
        if state.mode_number is not None:
            mode = _("{name} ({number})").format(name=state.mode_name or _("Unknown mode"), number=state.mode_number)
        self.active_mode.configure(text=_("Active flight mode: {mode}").format(mode=mode))
        self.switch_slot.configure(text=_("RC switch slot: {slot}").format(slot=state.switch_slot or _("Unavailable")))

    def _poll(self) -> None:
        self._timer_id = None
        if not self._navigation_lock.locked and not self.tk.call("grab", "current", str(self)):
            self._show_state(self.model.get_flight_modes())
        self.on_activate()

    def on_activate(self) -> None:
        """Schedule exactly one polling loop."""
        if self._timer_id is None:
            self._timer_id = self.after(_POLL_MS, self._poll)

    def on_deactivate(self) -> None:
        """Stop polling and release the shared telemetry stream."""
        self.on_suspend(PluginPauseReason.EXCLUSIVE_OPERATION)

    def on_suspend(self, reason: PluginPauseReason = PluginPauseReason.EXCLUSIVE_OPERATION) -> None:
        """Yield the connection and clear displayed telemetry."""
        cancel_plugin_timer(self, self._timer_id)
        self._timer_id = None
        self._show_state(FlightModesState())
        self.model.stop_monitoring(restore_intervals=reason is not PluginPauseReason.CONNECTION_RECOVERY)

    def on_resume(self) -> None:
        """Resume polling once the editor returns the connection."""
        self.on_activate()

    def destroy(self) -> None:
        self.on_deactivate()
        super().destroy()


def _create_model(context: PluginModelContext) -> FlightModesDataModel:
    return FlightModesDataModel(context.flight_controller)


def _create_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> FlightModesView:
    return FlightModesView(parent, cast("FlightModesDataModel", model), cast("BaseWindow", base_window))


def register_flight_modes_plugin() -> None:
    """Register both factories for this live flight-controller plugin."""
    plugin_factory.register(PLUGIN_FLIGHT_MODES, _create_view, _create_model)
