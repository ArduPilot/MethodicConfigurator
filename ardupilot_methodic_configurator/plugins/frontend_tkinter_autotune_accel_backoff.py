"""
Tkinter controls for takeoff-weight compensation after AutoTune.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showerror, showwarning

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.plugins.data_model_autotune_accel_backoff import AutotuneAccelBackoffDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import refresh_parameter_editor_table
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_AUTOTUNE_ACCEL_BACKOFF
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason


class AutotuneAccelBackoffView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Let users explicitly scale staged limits using the vehicle's weight range."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: AutotuneAccelBackoffDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        min_tow, max_tow = model.takeoff_weights()
        self.min_tow = tk.StringVar(self, value=min_tow)
        self.max_tow = tk.StringVar(self, value=max_tow)
        self.status = tk.StringVar(self, value="")
        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=8, pady=4)
        for label_text, variable in ((_("Minimum TOW (kg):"), self.min_tow), (_("Maximum TOW (kg):"), self.max_tow)):
            label = ttk.Label(controls, text=label_text)
            label.pack(side="left")
            entry = ttk.Entry(controls, textvariable=variable, width=8)
            entry.pack(side="left", padx=8)
            tooltip = _("Takeoff weight in kilograms, initially read from the vehicle's Frame specifications.")
            show_tooltip(label, tooltip)
            show_tooltip(entry, tooltip)
        self.apply_button = ttk.Button(controls, text=_("Scale acceleration limits"), command=self._on_apply)
        self.apply_button.pack(side="left")
        if self.model.has_applied:
            self.apply_button.state(["disabled"])
        show_tooltip(
            self.apply_button,
            _("Multiply current New acceleration limits by minimum / maximum takeoff weight once. The button then disables."),
        )
        ttk.Label(
            self,
            text=_(
                "After AutoTune at minimum takeoff weight, scale roll, pitch and yaw acceleration limits by "
                "minimum / maximum takeoff weight. This reduction can only be applied once."
            ),
            wraplength=750,
            justify="left",
        ).pack(fill="x", padx=8)
        ttk.Label(self, textvariable=self.status, wraplength=750, justify="left").pack(fill="x", padx=8, pady=4)

    def _on_apply(self) -> None:
        """Validate the weights, stage the reduction and refresh the table."""
        if self.model.has_applied:
            return
        try:
            min_tow, max_tow = float(self.min_tow.get()), float(self.max_tow.get())
        except ValueError:
            showerror(
                _("AutoTune acceleration limits"), _("Enter numeric minimum and maximum takeoff weights in kg."), parent=self
            )
            return
        try:
            changed = self.model.apply_backoff(min_tow, max_tow)
        except (ValueError, TypeError) as exc:
            showerror(_("AutoTune acceleration limits"), str(exc), parent=self)
            return
        self.apply_button.state(["disabled"])
        self.status.set(
            _("Updated acceleration limits: {names}").format(names=", ".join(changed))
            if changed
            else _("No acceleration limits changed.")
        )
        if self.model.range_warnings:
            showwarning(
                _("AutoTune acceleration limits"),
                _("The New values were changed, but some acceleration limits are outside their recommended ranges:")
                + "\n\n"
                + "\n".join(self.model.range_warnings),
                parent=self,
            )
        refresh_parameter_editor_table(self.base_window)

    def on_activate(self) -> None:
        """Retain the disabled button and feedback after applying the reduction."""
        if self.model.has_applied:
            self.apply_button.state(["disabled"])
        else:
            self.status.set("")

    def on_deactivate(self) -> None:
        """No timers or external resources need cleanup."""

    def on_suspend(self, reason: PluginPauseReason = PluginPauseReason.EXCLUSIVE_OPERATION) -> None:
        """Retain input while another operation owns the flight controller."""

    def on_resume(self) -> None:
        """No receiver needs restarting."""


def _create_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> AutotuneAccelBackoffView:
    return AutotuneAccelBackoffView(parent, model, base_window)  # type: ignore[arg-type]


def _create_model(context: PluginModelContext) -> AutotuneAccelBackoffDataModel:
    return AutotuneAccelBackoffDataModel(context.parameter_editor, context.local_filesystem)


def register_autotune_accel_backoff_plugin() -> None:
    """Register an offline-capable staging plugin."""
    plugin_factory.register(PLUGIN_AUTOTUNE_ACCEL_BACKOFF, _create_view, _create_model, requires_flight_controller=False)
