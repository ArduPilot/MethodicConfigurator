"""
Tkinter controls for additional AutoTune gain-margin back-off.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showerror, showwarning

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.plugins.data_model_autotune_gain_backoff import AutotuneGainBackoffDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import refresh_parameter_editor_table
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_AUTOTUNE_GAIN_BACKOFF
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory


class AutotuneGainBackoffView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Let users explicitly reduce staged gains without contacting the FC."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: AutotuneGainBackoffDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self.backoff = tk.StringVar(self, value=str(model.DEFAULT_BACKOFF))
        self.status = tk.StringVar(self, value="")
        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=8, pady=4)
        label = ttk.Label(controls, text=_("Gain margin back-off (0.0-0.5):"))
        label.pack(side="left")
        self.entry = ttk.Spinbox(
            controls, from_=model.MIN_BACKOFF, to=model.MAX_BACKOFF, increment=0.01, textvariable=self.backoff, width=8
        )
        self.entry.pack(side="left", padx=8)
        tooltip = _("Fraction to subtract from the current New values: 0.25 reduces the affected gains by 25%.")
        show_tooltip(label, tooltip)
        show_tooltip(self.entry, tooltip)
        self.apply_button = ttk.Button(controls, text=_("Apply back-off"), command=self._on_apply)
        self.apply_button.pack(side="left")
        show_tooltip(self.apply_button, _("Apply one additional reduction to this step's gains. Repeated clicks compound."))
        ttk.Label(
            self,
            text=_(
                "Changes only New values, not the flight controller. Firmware AutoTune results may already include "
                "back-off; each click applies an additional reduction."
            ),
            wraplength=750,
            justify="left",
        ).pack(fill="x", padx=8)
        ttk.Label(self, textvariable=self.status, wraplength=750, justify="left").pack(fill="x", padx=8, pady=4)

    def _on_apply(self) -> None:
        """Validate user input and refresh the visible staged values."""
        try:
            fraction = float(self.backoff.get())
        except ValueError:
            showerror(
                _("Gain margin back-off"),
                _("Enter a number between {minimum:.1f} and {maximum:.1f}.").format(
                    minimum=self.model.MIN_BACKOFF, maximum=self.model.MAX_BACKOFF
                ),
                parent=self,
            )
            return
        try:
            changed = self.model.apply_backoff(fraction)
        except (ValueError, TypeError) as exc:
            showerror(_("Gain margin back-off"), str(exc), parent=self)
            return
        self.status.set(_("Updated gains: {names}").format(names=", ".join(changed)) if changed else _("No gains changed."))
        if self.model.range_warnings:
            showwarning(
                _("Gain margin back-off"),
                _("The New values were changed, but some gains are outside their recommended ranges:")
                + "\n\n"
                + "\n".join(self.model.range_warnings),
                parent=self,
            )
        refresh_parameter_editor_table(self.base_window)

    def on_activate(self) -> None:
        """Clear feedback when moving between results steps."""
        self.status.set("")

    def on_deactivate(self) -> None:
        """No timers or external resources need cleanup."""


def _create_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> AutotuneGainBackoffView:
    return AutotuneGainBackoffView(parent, model, base_window)  # type: ignore[arg-type]


def _create_model(context: PluginModelContext) -> AutotuneGainBackoffDataModel:
    return AutotuneGainBackoffDataModel(context.parameter_editor)


def register_autotune_gain_backoff_plugin() -> None:
    """Register a plugin usable even when the flight controller is offline."""
    plugin_factory.register(PLUGIN_AUTOTUNE_GAIN_BACKOFF, _create_view, _create_model, requires_flight_controller=False)
